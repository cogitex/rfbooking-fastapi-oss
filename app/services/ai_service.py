# RFBooking FastAPI OSS - Self-hosted Equipment Booking System
# Copyright (C) 2025 Oleg Tokmakov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""AI Service for equipment recommendation using Ollama."""

import json
import re
import time
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.equipment import Equipment, AISpecificationRule
from app.models.booking import Booking
from app.models.user import User
from app.services.ai_temporal import TemporalParser
from app.services.ai_equipment import AIEquipmentFilter


# AI Model Configuration (mapped from Cloudflare AI models)
AI_MODELS = {
    'LLAMA': {
        'id': 'llama3.1:8b',  # Ollama model name
        'name': 'Llama 3.1 8B Instruct',
        'neurons_per_m_input': 4119,
        'neurons_per_m_output': 34868,
        'cost_per_m_input': 0.045,
        'cost_per_m_output': 0.384
    },
    'GRANITE': {
        'id': 'granite-4.0-h-micro',  # Not available in Ollama, placeholder
        'name': 'IBM Granite 4.0 H Micro',
        'neurons_per_m_input': 1542,
        'neurons_per_m_output': 10158,
        'cost_per_m_input': 0.017,
        'cost_per_m_output': 0.11
    }
}

# Default model selection (can be changed via environment variable)
def get_selected_model():
    """Get selected AI model based on configuration."""
    settings = get_settings()
    model_key = getattr(settings.ai, 'model_key', 'LLAMA')  # Default to LLAMA
    return AI_MODELS.get(model_key, AI_MODELS['LLAMA'])

FREE_TIER_DAILY_LIMIT = 10000  # Free tier: 10,000 neurons/day
MAX_BOOKING_OPTIONS = 5  # Maximum options to present to user
SEARCH_DAYS_AHEAD = 60  # How far ahead to search for availability
DEFAULT_SEARCH_DAYS = 30  # Default search window for availability

# Rate limiting (in-memory)
RATE_LIMIT_WINDOW_MS = 5 * 60 * 1000  # 5 minutes
RATE_LIMIT_MAX_REQUESTS = 10  # Maximum requests per window
_rate_limit_cache = {}  # user_id:window -> count

# Equipment cache for reducing database queries
_equipment_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0,
    "ttl": 4 * 60 * 60,  # 4 hours in seconds
}

def calculate_neurons(input_tokens, output_tokens, model):
    """Calculate neurons used based on token counts and model."""
    input_neurons = (input_tokens / 1000000) * model['neurons_per_m_input']
    output_neurons = (output_tokens / 1000000) * model['neurons_per_m_output']
    return int(input_neurons + output_neurons)

def check_rate_limit(user_id, db):
    """Check if user has exceeded rate limit. Admin users are exempt."""
    # Check if user is admin
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.is_admin:
        return {'allowed': True, 'isAdmin': True}

    import time
    now = int(time.time() * 1000)  # milliseconds
    window_start = (now // RATE_LIMIT_WINDOW_MS) * RATE_LIMIT_WINDOW_MS
    key = f'{user_id}:{window_start}'

    current = _rate_limit_cache.get(key, 0)

    if current >= RATE_LIMIT_MAX_REQUESTS:
        retry_after = ((window_start + RATE_LIMIT_WINDOW_MS - now) // 1000) + 1
        return {
            'allowed': False,
            'retry_after': retry_after,
            'current': current,
            'limit': RATE_LIMIT_MAX_REQUESTS
        }

    _rate_limit_cache[key] = current + 1

    # Cleanup old windows to prevent memory leak
    for k in list(_rate_limit_cache.keys()):
        _, ws = k.split(':')
        if int(ws) < window_start - RATE_LIMIT_WINDOW_MS:
            del _rate_limit_cache[k]

    return {
        'allowed': True,
        'remaining': RATE_LIMIT_MAX_REQUESTS - current - 1,
        'isAdmin': False
    }


def get_today_usage(db, org_id=1):
    """Get or create today's usage record."""
    today = date.today().isoformat()

    from app.models.equipment import AIUsage
    usage = db.query(AIUsage).filter(AIUsage.date == today).first()

    if not usage:
        usage = AIUsage(date=today, queries_count=0, neurons_used=0, input_tokens=0, output_tokens=0)
        db.add(usage)
        db.commit()

    return usage


def update_usage(db, org_id, neurons_used, input_tokens, output_tokens):
    """Update usage statistics."""
    today = date.today().isoformat()

    from app.models.equipment import AIUsage
    from sqlalchemy import func

    # Try to update existing record, or insert if not exists
    # This is a simplified version - for production, use proper upsert
    usage = db.query(AIUsage).filter(AIUsage.date == today).first()
    if usage:
        usage.neurons_used += neurons_used
        usage.queries_count += 1
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
    else:
        usage = AIUsage(
            date=today,
            neurons_used=neurons_used,
            queries_count=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )
        db.add(usage)
    db.commit()


def log_query(db, org_id, user_id, prompt, response, input_tokens, output_tokens,
              neurons_used, model, success, error_message=None):
    """Log AI query for debugging and analytics."""
    from app.models.equipment import AIQueryLog

    query_log = AIQueryLog(
        org_id=org_id,
        user_id=user_id,
        prompt=prompt,
        response=response,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        neurons_used=neurons_used,
        model=model,
        success=success,
        error_message=error_message
    )
    db.add(query_log)
    db.commit()


def invalidate_equipment_cache():
    """Invalidate the equipment cache (call on equipment create/update/delete)."""
    global _equipment_cache
    _equipment_cache["data"] = None
    _equipment_cache["timestamp"] = 0


class SpecificationExtractor:
    """Extract technical specifications from natural language prompts."""

    # Common unit patterns for various specifications
    SPEC_PATTERNS = {
        "power": [
            # Watts: 800W, 1.5kW, 2 kW, 500 watts
            r'(\d+(?:\.\d+)?)\s*(?:k)?[wW](?:atts?)?',
            r'(\d+(?:\.\d+)?)\s*kilo\s*watts?',
        ],
        "frequency": [
            # Frequency: 2.4GHz, 5.8 GHz, 900MHz, 2.4 ghz
            r'(\d+(?:\.\d+)?)\s*[gG][hH][zZ]',
            r'(\d+(?:\.\d+)?)\s*[mM][hH][zZ]',
            r'(\d+(?:\.\d+)?)\s*[tT][hH][zZ]',
        ],
        "temperature": [
            # Temperature: 85°C, -40C, 200 degrees, 150°
            r'(-?\d+(?:\.\d+)?)\s*°?\s*[cC](?:elsius)?',
            r'(-?\d+(?:\.\d+)?)\s*degrees?\s*(?:[cC](?:elsius)?)?',
        ],
        "voltage": [
            # Voltage: 28V, 12 volts, 3.3V
            r'(\d+(?:\.\d+)?)\s*[vV](?:olts?)?',
        ],
        "current": [
            # Current: 10A, 500mA, 2.5 amps
            r'(\d+(?:\.\d+)?)\s*[mM]?[aA](?:mps?)?',
        ],
        "bandwidth": [
            # Bandwidth: 100MHz, 1GHz bandwidth
            r'(\d+(?:\.\d+)?)\s*[gGmM][hH][zZ]\s*(?:bandwidth|bw)',
        ],
    }

    # Unit normalization (convert everything to base units)
    UNIT_MULTIPLIERS = {
        "kW": 1000,
        "kw": 1000,
        "W": 1,
        "w": 1,
        "GHz": 1e9,
        "ghz": 1e9,
        "MHz": 1e6,
        "mhz": 1e6,
        "THz": 1e12,
        "thz": 1e12,
        "mA": 0.001,
        "ma": 0.001,
        "A": 1,
        "a": 1,
    }

    @classmethod
    def extract_specs(cls, prompt: str) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all technical specifications from a prompt.

        Args:
            prompt: Natural language prompt

        Returns:
            Dictionary with spec types and extracted values
        """
        specs = {}

        for spec_type, patterns in cls.SPEC_PATTERNS.items():
            matches = []
            for pattern in patterns:
                for match in re.finditer(pattern, prompt, re.IGNORECASE):
                    value_str = match.group(1)
                    try:
                        value = float(value_str)
                        unit = cls._extract_unit(match.group(0), spec_type)
                        normalized_value = cls._normalize_value(value, unit)
                        matches.append({
                            "raw": match.group(0),
                            "value": value,
                            "unit": unit,
                            "normalized_value": normalized_value,
                        })
                    except ValueError:
                        continue

            if matches:
                specs[spec_type] = matches

        return specs

    @classmethod
    def _extract_unit(cls, match_str: str, spec_type: str) -> str:
        """Extract the unit from a matched string."""
        match_str = match_str.strip()

        if spec_type == "power":
            if re.search(r'k[wW]', match_str):
                return "kW"
            return "W"
        elif spec_type == "frequency":
            if re.search(r'[gG][hH][zZ]', match_str):
                return "GHz"
            elif re.search(r'[mM][hH][zZ]', match_str):
                return "MHz"
            elif re.search(r'[tT][hH][zZ]', match_str):
                return "THz"
            return "Hz"
        elif spec_type == "temperature":
            return "°C"
        elif spec_type == "voltage":
            return "V"
        elif spec_type == "current":
            if re.search(r'm[aA]', match_str):
                return "mA"
            return "A"

        return ""

    @classmethod
    def _normalize_value(cls, value: float, unit: str) -> float:
        """Normalize value to base unit."""
        multiplier = cls.UNIT_MULTIPLIERS.get(unit, 1)
        return value * multiplier


class AIService:
    """AI Service for equipment recommendation."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None
        self.spec_extractor = SpecificationExtractor()

    @property
    def client(self):
        """Lazy-load Ollama client."""
        if self._client is None:
            import ollama
            self._client = ollama.Client(host=self.settings.ai.ollama_host, timeout=300)
        return self._client

    def get_cached_equipment(self, db: Session) -> Optional[List[Dict[str, Any]]]:
        """Get equipment from cache if valid, otherwise return None.

        Args:
            db: Database session (used if cache miss)

        Returns:
            Cached equipment data or None if cache expired
        """
        global _equipment_cache

        current_time = time.time()
        if (
            _equipment_cache["data"] is not None
            and (current_time - _equipment_cache["timestamp"]) < _equipment_cache["ttl"]
        ):
            return _equipment_cache["data"]

        return None

    def update_equipment_cache(self, equipment_list: List[Equipment]) -> List[Dict[str, Any]]:
        """Update the equipment cache with fresh data.

        Args:
            equipment_list: List of equipment objects

        Returns:
            Cached equipment data
        """
        global _equipment_cache

        cache_data = []
        for eq in equipment_list:
            cache_data.append({
                "id": eq.id,
                "name": eq.name,
                "description": eq.description,
                "location": eq.location,
                "type_id": eq.type_id,
                "is_active": eq.is_active,
            })

        _equipment_cache["data"] = cache_data
        _equipment_cache["timestamp"] = time.time()

        return cache_data

    def filter_equipment_by_specs(
        self,
        equipment_list: List[Equipment],
        extracted_specs: Dict[str, List[Dict[str, Any]]],
    ) -> Tuple[List[Equipment], Dict[str, Any]]:
        """Filter equipment based on extracted specifications.

        Stage 1 of the two-stage AI pipeline: pre-filter equipment by specs
        before sending to AI for final matching.

        Args:
            equipment_list: Full list of equipment
            extracted_specs: Specs extracted from prompt

        Returns:
            Tuple of (filtered equipment list, filter info)
        """
        if not extracted_specs:
            return equipment_list, {"filtered": False, "reason": "No specs extracted"}

        filtered = []
        filter_info = {
            "filtered": True,
            "specs_used": list(extracted_specs.keys()),
            "original_count": len(equipment_list),
        }

        for eq in equipment_list:
            if not eq.description:
                # Include equipment without description (can't filter)
                filtered.append(eq)
                continue

            description_lower = eq.description.lower()
            matches_any = False

            # Check each extracted spec against equipment description
            for spec_type, specs in extracted_specs.items():
                for spec in specs:
                    # Look for the raw value or normalized patterns in description
                    raw_value = spec["raw"].lower()
                    if raw_value in description_lower:
                        matches_any = True
                        break

                    # Also check for numeric patterns
                    value = spec["value"]
                    unit = spec["unit"]

                    # Build pattern to match in description
                    patterns = [
                        f"{value}\\s*{unit}",
                        f"{int(value)}\\s*{unit}" if value == int(value) else None,
                    ]
                    patterns = [p for p in patterns if p]

                    for pattern in patterns:
                        if re.search(pattern, eq.description, re.IGNORECASE):
                            matches_any = True
                            break

                if matches_any:
                    break

            if matches_any:
                filtered.append(eq)

        filter_info["filtered_count"] = len(filtered)

        # If filtering removed all equipment, fall back to full list
        if not filtered:
            return equipment_list, {
                "filtered": False,
                "reason": "No equipment matched specs, using full list",
            }

        return filtered, filter_info

    def _build_system_prompt(self, rules: List[AISpecificationRule]) -> str:
        """Build system prompt from specification rules."""
        prompt_parts = [
            "You are an AI assistant helping users find and book laboratory equipment.",
            "Your role is to recommend equipment based on user requirements.",
            "",
            "When recommending equipment:",
            "1. Match technical specifications to user requirements",
            "2. Consider equipment availability",
            "3. Explain your reasoning clearly",
            "4. Suggest alternatives if the best match is unavailable",
            "",
        ]

        # Add rules from database
        for rule in rules:
            if rule.is_enabled:
                prompt_parts.append(rule.prompt_text)
                prompt_parts.append("")

        prompt_parts.extend([
            "",
            "Response format:",
            "Provide recommendations as a JSON array with the following structure:",
            '[{"equipment_id": <id>, "name": "<name>", "reasoning": "<why this equipment>", "confidence": <0-100>}]',
            "",
            "Always respond with valid JSON only, no additional text.",
        ])

        return "\n".join(prompt_parts)

    def _build_equipment_context(self, equipment_list: List[Equipment]) -> str:
        """Build equipment context for the prompt."""
        equipment_info = []
        for eq in equipment_list:
            info = f"- ID: {eq.id}, Name: {eq.name}"
            if eq.description:
                info += f", Description: {eq.description[:500]}"
            if eq.location:
                info += f", Location: {eq.location}"
            equipment_info.append(info)

        return "\n".join(equipment_info)

    def _check_availability(
        self,
        db: Session,
        equipment_id: int,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        """Check equipment availability for a date range."""
        conflicts = (
            db.query(Booking)
            .filter(
                Booking.equipment_id == equipment_id,
                Booking.status == "active",
                Booking.start_date <= end_date,
                Booking.end_date >= start_date,
            )
            .all()
        )

        return [
            {
                "start_date": c.start_date.isoformat(),
                "end_date": c.end_date.isoformat(),
                "start_time": c.start_time.isoformat() if c.start_time else None,
                "end_time": c.end_time.isoformat() if c.end_time else None,
            }
            for c in conflicts
        ]

    def _find_available_slots(
        self,
        db: Session,
        equipment_id: int,
        preferred_start: Optional[date],
        preferred_end: Optional[date],
        search_days: int = 14,
    ) -> List[Dict[str, Any]]:
        """Find available time slots for equipment."""
        start = preferred_start or date.today()
        end = preferred_end or (start + timedelta(days=search_days))

        # Get all bookings in range
        bookings = (
            db.query(Booking)
            .filter(
                Booking.equipment_id == equipment_id,
                Booking.status == "active",
                Booking.start_date <= end,
                Booking.end_date >= start,
            )
            .order_by(Booking.start_date)
            .all()
        )

        # Find gaps (simplified - assumes full-day bookings)
        available_slots = []
        current = start

        for booking in bookings:
            if current < booking.start_date:
                available_slots.append({
                    "start_date": current.isoformat(),
                    "end_date": (booking.start_date - timedelta(days=1)).isoformat(),
                })
            current = max(current, booking.end_date + timedelta(days=1))

        if current <= end:
            available_slots.append({
                "start_date": current.isoformat(),
                "end_date": end.isoformat(),
            })

        return available_slots[:5]  # Limit to 5 slots

    async def analyze_booking_request(
        self,
        prompt: str,
        equipment_list: List[Equipment],
        rules: List[AISpecificationRule],
        date_constraints: Dict[str, Any],
        db: Session,
        user: User,
        search_days: int = 30,
        max_options: int = 5,
        # Deprecated parameters (kept for backward compatibility)
        preferred_start: Optional[date] = None,
        preferred_end: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Analyze booking request and return recommendations.

        Uses a two-stage pipeline:
        1. Extract specs from prompt and pre-filter equipment
        2. Send filtered list to AI for final recommendations

        Also includes availability checking for recommended equipment.
        """
        # Extract date constraints
        preferred_start = date_constraints.get('preferred_start') or preferred_start
        preferred_end = date_constraints.get('preferred_end') or preferred_end
        duration = date_constraints.get('duration')
        flexibility = date_constraints.get('flexibility', 'any')
        intent = date_constraints.get('intent', 'booking')
        print(f'[AI Assistant] Date constraints: {date_constraints}')

        # Calculate end date from start + duration if needed
        if preferred_start and duration and not preferred_end:
            from datetime import timedelta
            preferred_end = preferred_start + timedelta(days=duration - 1)
            print(f'[AI Assistant] Calculated end date: {preferred_end} from start {preferred_start}, duration {duration}')

        # Stage 1: Extract specifications from prompt
        extracted_specs = self.spec_extractor.extract_specs(prompt)

        # Stage 1.5: Pre-filter equipment by extracted specs
        filtered_equipment, filter_info = self.filter_equipment_by_specs(
            equipment_list, extracted_specs
        )

        # Update cache with equipment list
        self.update_equipment_cache(equipment_list)

        # Build prompts for Stage 2
        system_prompt = self._build_system_prompt(rules)
        equipment_context = self._build_equipment_context(filtered_equipment)

        # Include extracted specs in the prompt for better AI matching
        specs_info = ""
        if extracted_specs:
            specs_parts = []
            for spec_type, specs in extracted_specs.items():
                for spec in specs:
                    specs_parts.append(f"- {spec_type}: {spec['raw']}")
            specs_info = f"\n\nExtracted requirements:\n" + "\n".join(specs_parts)

        # Add duration hint if available (like Core)
        duration_hint = ""
        if duration:
            duration_hint = f"\n\nThe user needs equipment for {duration} working days."
        elif preferred_start and preferred_end:
            duration = (preferred_end - preferred_start).days + 1
            duration_hint = f"\n\nThe user needs equipment for {duration} days."

        # Add date constraint hint (like Core)
        date_constraint_hint = ""
        if preferred_start and preferred_end:
            date_constraint_hint = f"\n\nDate preference: {preferred_start.isoformat()} to {preferred_end.isoformat()}."
        elif preferred_start:
            date_constraint_hint = f"\n\nStart date preference: {preferred_start.isoformat()}."

        user_prompt = f"""User request: {prompt}{specs_info}{duration_hint}{date_constraint_hint}

Available equipment (pre-filtered based on specifications):
{equipment_context}

Please recommend the most suitable equipment for this request.
Consider the technical specifications and match them to equipment capabilities.
Respond with a JSON array of recommendations."""

        # Stage 2: Call Ollama for AI-based matching
        response = self.client.chat(
            model=self.settings.ai.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={
                "num_predict": self.settings.ai.max_tokens,
                "temperature": self.settings.ai.temperature,
            },
        )

        response_text = response.get("message", {}).get("content", "")

        # Parse recommendations
        recommendations = self._parse_recommendations(response_text, filtered_equipment)

        # Extract equipment type from recommendations
        equipment_types = set()
        for rec in recommendations:
            eq_id = rec.get("equipment_id")
            if eq_id:
                # Find equipment in filtered list
                eq = next((e for e in filtered_equipment if e.id == eq_id), None)
                if eq and eq.equipment_type and eq.equipment_type.name:
                    equipment_types.add(eq.equipment_type.name)

        equipment_type = ", ".join(sorted(list(equipment_types))) if equipment_types else "Equipment"

        # Add availability info for each recommendation
        for rec in recommendations:
            eq_id = rec.get("equipment_id")
            if eq_id:
                # Check availability for requested dates
                if preferred_start and preferred_end:
                    conflicts = self._check_availability(db, eq_id, preferred_start, preferred_end)
                    rec["conflicts"] = conflicts
                    rec["available"] = len(conflicts) == 0

                    # If not available, find alternative dates
                    if not rec["available"]:
                        rec["alternative_dates"] = self._find_alternative_dates(
                            db, eq_id, preferred_start, preferred_end, search_days
                        )

                # Always include available slots
                rec["available_slots"] = self._find_available_slots(
                    db, eq_id, preferred_start, preferred_end, search_days
                )

        # Flatten options for frontend and summary generation
        options = self._generate_flattened_options(
            recommendations,
            preferred_start,
            preferred_end,
            date_constraints,
            max_options
        )

        # Generate summary and tips
        summary = self.generate_summary(options, search_days)
        tips = self.generate_conversational_tips(options, date_constraints, search_days)

        # Estimate token usage
        input_tokens = len(system_prompt.split()) + len(user_prompt.split())
        output_tokens = len(response_text.split())

        return {
            "options": options,
            "equipment_analysis": response_text,
            "equipment_type": equipment_type,
            "summary": summary,
            "tips": tips,
            "extracted_specs": extracted_specs,
            "filter_info": filter_info,
            "tokens": {
                "input": input_tokens * 2,
                "output": output_tokens * 2
            },
            "recommendations": recommendations,  # Deprecated: keep for backward compatibility
        }

    def _generate_flattened_options(self, recommendations: List[Dict[str, Any]], preferred_start, preferred_end, date_constraints: Dict[str, Any], max_options: int = 10) -> List[Dict[str, Any]]:
        """Flatten nested recommendations into a list of booking options."""
        from datetime import date, timedelta
        options = []
        
        for rec in recommendations:
            # If exact match found (available for preferred dates)
            if rec.get("available", False) and preferred_start and preferred_end:
                options.append({
                    "equipment_id": rec["equipment_id"],
                    "equipment_name": rec["name"],
                    "start_date": preferred_start.isoformat(),
                    "end_date": preferred_end.isoformat(),
                    "duration_days": (preferred_end - preferred_start).days + 1,
                    "reason": rec.get("reasoning", ""),
                    "exact_match": True
                })
            
            # Add alternative dates if available
            elif rec.get("alternative_dates"):
                for alt in rec["alternative_dates"]:
                    options.append({
                        "equipment_id": rec["equipment_id"],
                        "equipment_name": rec["name"],
                        "start_date": alt["start_date"],
                        "end_date": alt["end_date"],
                        "duration_days": (date.fromisoformat(alt["end_date"]) - date.fromisoformat(alt["start_date"])).days + 1,
                        "reason": rec.get("reasoning", ""),
                        "nearest_alternative": True,
                        "requested_date": preferred_start.isoformat() if preferred_start else None
                    })
            
            # Add general available slots if no specific preference or no match yet
            elif rec.get("available_slots"):
                # Limit to 3 slots per equipment to avoid clutter
                for slot in rec["available_slots"][:3]:
                    # Calculate slot duration
                    slot_start = date.fromisoformat(slot["start_date"])
                    slot_end = date.fromisoformat(slot["end_date"])
                    slot_duration = (slot_end - slot_start).days + 1

                    # Check if we have a requested duration from date constraints
                    requested_duration = date_constraints.get('duration')

                    if requested_duration and slot_duration >= requested_duration:
                        # Create option of requested duration (use earliest part of slot)
                        option_end = slot_start + timedelta(days=requested_duration - 1)
                        options.append({
                            "equipment_id": rec["equipment_id"],
                            "equipment_name": rec["name"],
                            "start_date": slot_start.isoformat(),
                            "end_date": option_end.isoformat(),
                            "duration_days": requested_duration,
                            "reason": rec.get("reasoning", "") + f" (showing {requested_duration}-day slot within available period)"
                        })
                    else:
                        # Use full slot (or skip if slot too short for requested duration)
                        if not requested_duration or slot_duration >= requested_duration:
                            options.append({
                                "equipment_id": rec["equipment_id"],
                                "equipment_name": rec["name"],
                                "start_date": slot["start_date"],
                                "end_date": slot["end_date"],
                                "duration_days": slot_duration,
                                "reason": rec.get("reasoning", "")
                            })

        return options[:max_options] # Limit total options

    def generate_summary(self, results: List[Dict[str, Any]], search_days: int) -> str:
        """Generate a human-friendly summary of the results."""
        total_options = len(results)
        equipment_ids = {r["equipment_id"] for r in results if "equipment_id" in r}
        equipment_names = {r["equipment_name"] for r in results if "equipment_name" in r}
        nearest_alternatives = any(r.get("nearest_alternative") for r in results)

        if total_options == 0:
            return f"No available slots found in the next {search_days} days. Try extending your search window or selecting different equipment."

        # Handle nearest alternatives case
        if nearest_alternatives and results[0].get("requested_date"):
            requested_date = results[0]["requested_date"] 
            
            if len(equipment_ids) == 1:
                return f"Your requested date ({requested_date}) is booked. Showing {total_options} nearest available alternative{'s' if total_options > 1 else ''} for {list(equipment_names)[0]}."
            
            return f"Your requested date ({requested_date}) is booked. Showing {total_options} nearest available alternative{'s' if total_options > 1 else ''} across {len(equipment_ids)} equipment item{'s' if len(equipment_ids) > 1 else ''}."

        if len(equipment_ids) == 1:
            return f"Found {list(equipment_names)[0]} with {total_options} available time slot{'s' if total_options > 1 else ''} in the next {search_days} days."

        if total_options <= 3:
            return f"Found {total_options} available booking option{'s' if total_options > 1 else ''} across {len(equipment_ids)} equipment item{'s' if len(equipment_ids) > 1 else ''}."

        return f"Great news! Found {total_options} available slots across {len(equipment_ids)} equipment items. Showing the soonest available dates."

    def generate_conversational_tips(self, results: List[Dict[str, Any]], date_constraints: Dict[str, Any], search_days: int) -> List[str]:
        """Generate helpful tips based on the results."""
        tips = []
        
        # Check if showing nearest alternatives
        has_nearest_alternatives = any(r.get("nearest_alternative") for r in results)

        if has_nearest_alternatives:
            tips.append("💡 Tip: Your preferred date was booked, but these are the closest available slots for the same equipment.")

        if 0 < len(results) <= 2 and not has_nearest_alternatives:
            tips.append("💡 Tip: This equipment is in high demand. Book soon to secure your preferred dates.")

        if date_constraints.get("flexibility") == 'exact' and len(results) == 0:
            tips.append("💡 Tip: Try being flexible with your dates - more slots may be available nearby.")

        # Check duration (assuming duration_days is in result)
        if any(r.get("duration_days", 0) > 7 for r in results):
            tips.append("💡 Tip: Consider shorter booking periods if possible - this helps other researchers access equipment.")

        if search_days < 30 and len(results) == 0:
            tips.append(f"💡 Tip: Try searching further ahead - currently only searching {search_days} days.")

        return tips

    def _find_alternative_dates(
        self,
        db: Session,
        equipment_id: int,
        preferred_start: date,
        preferred_end: date,
        search_range_days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Find alternative available dates when preferred dates are unavailable.

        Args:
            db: Database session
            equipment_id: Equipment ID
            preferred_start: Preferred start date
            preferred_end: Preferred end date
            search_range_days: How far ahead to search

        Returns:
            List of alternative date ranges
        """
        duration = (preferred_end - preferred_start).days + 1
        alternatives = []

        # Search forward from preferred dates
        search_start = preferred_end + timedelta(days=1)
        search_end = search_start + timedelta(days=search_range_days)

        # Get all bookings in search range
        bookings = (
            db.query(Booking)
            .filter(
                Booking.equipment_id == equipment_id,
                Booking.status == "active",
                Booking.start_date <= search_end,
                Booking.end_date >= search_start,
            )
            .order_by(Booking.start_date)
            .all()
        )

        # Find gaps that can fit the requested duration
        current = search_start

        for booking in bookings:
            gap_days = (booking.start_date - current).days
            if gap_days >= duration:
                alternatives.append({
                    "start_date": current.isoformat(),
                    "end_date": (current + timedelta(days=duration - 1)).isoformat(),
                    "days_from_preferred": (current - preferred_start).days,
                })

            current = booking.end_date + timedelta(days=1)

            if len(alternatives) >= 3:
                break

        # Check remaining space after last booking
        if len(alternatives) < 3 and current <= search_end:
            remaining_days = (search_end - current).days + 1
            if remaining_days >= duration:
                alternatives.append({
                    "start_date": current.isoformat(),
                    "end_date": (current + timedelta(days=duration - 1)).isoformat(),
                    "days_from_preferred": (current - preferred_start).days,
                })

        return alternatives[:3]

    def _parse_recommendations(
        self,
        response_text: str,
        equipment_list: List[Equipment],
    ) -> List[Dict[str, Any]]:
        """Parse AI response into structured recommendations."""
        # Try to extract JSON from response
        try:
            # Look for JSON array in response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                recommendations = json.loads(json_match.group())
                # Validate equipment IDs
                valid_ids = {eq.id for eq in equipment_list}
                valid_recs = []
                for rec in recommendations:
                    if rec.get("equipment_id") in valid_ids:
                        valid_recs.append(rec)
                return valid_recs[:5]  # Limit to 5 recommendations
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: try to extract equipment mentions
        recommendations = []
        for eq in equipment_list:
            if eq.name.lower() in response_text.lower():
                recommendations.append({
                    "equipment_id": eq.id,
                    "name": eq.name,
                    "reasoning": "Mentioned in AI response",
                    "confidence": 50,
                })

        return recommendations[:5]

    async def chat(
        self,
        message: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Direct chat with AI."""
        default_system = "You are a helpful AI assistant for an equipment booking system."

        response = self.client.chat(
            model=self.settings.ai.model,
            messages=[
                {"role": "system", "content": system_prompt or default_system},
                {"role": "user", "content": message},
            ],
            options={
                "num_predict": self.settings.ai.max_tokens,
                "temperature": self.settings.ai.temperature,
            },
        )

        response_text = response.get("message", {}).get("content", "")

        # Estimate tokens
        input_tokens = len(message.split()) * 2
        output_tokens = len(response_text.split()) * 2

        return {
            "response": response_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }


# Global service instance
_ai_service: Optional[AIService] = None


def get_ai_service() -> AIService:
    """Get the global AI service instance."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service
