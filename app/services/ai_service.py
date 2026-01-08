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


# Equipment cache for reducing database queries
_equipment_cache: Dict[str, Any] = {
    "data": None,
    "timestamp": 0,
    "ttl": 4 * 60 * 60,  # 4 hours in seconds
}


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
            self._client = ollama.Client(host=self.settings.ai.ollama_host)
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
        preferred_start: Optional[date],
        preferred_end: Optional[date],
        db: Session,
        user: User,
    ) -> Dict[str, Any]:
        """Analyze booking request and return recommendations.

        Uses a two-stage pipeline:
        1. Extract specs from prompt and pre-filter equipment
        2. Send filtered list to AI for final recommendations

        Also includes availability checking for recommended equipment.
        """
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

        user_prompt = f"""User request: {prompt}{specs_info}

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
                            db, eq_id, preferred_start, preferred_end
                        )

                # Always include available slots
                rec["available_slots"] = self._find_available_slots(
                    db, eq_id, preferred_start, preferred_end
                )

        # Estimate token usage
        input_tokens = len(system_prompt.split()) + len(user_prompt.split())
        output_tokens = len(response_text.split())

        return {
            "recommendations": recommendations,
            "reasoning": response_text,
            "extracted_specs": extracted_specs,
            "filter_info": filter_info,
            "input_tokens": input_tokens * 2,  # Rough estimate
            "output_tokens": output_tokens * 2,
        }

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
