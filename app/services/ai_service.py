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
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.equipment import Equipment, AISpecificationRule
from app.models.booking import Booking
from app.models.user import User


class AIService:
    """AI Service for equipment recommendation."""

    def __init__(self):
        self.settings = get_settings()
        self._client = None

    @property
    def client(self):
        """Lazy-load Ollama client."""
        if self._client is None:
            import ollama
            self._client = ollama.Client(host=self.settings.ai.ollama_host)
        return self._client

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
        """Analyze booking request and return recommendations."""
        system_prompt = self._build_system_prompt(rules)
        equipment_context = self._build_equipment_context(equipment_list)

        user_prompt = f"""User request: {prompt}

Available equipment:
{equipment_context}

Please recommend the most suitable equipment for this request.
Respond with a JSON array of recommendations."""

        # Call Ollama
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
        recommendations = self._parse_recommendations(response_text, equipment_list)

        # Add availability info
        for rec in recommendations:
            eq_id = rec.get("equipment_id")
            if eq_id:
                if preferred_start and preferred_end:
                    conflicts = self._check_availability(db, eq_id, preferred_start, preferred_end)
                    rec["conflicts"] = conflicts
                    rec["available"] = len(conflicts) == 0

                rec["available_slots"] = self._find_available_slots(
                    db, eq_id, preferred_start, preferred_end
                )

        # Estimate token usage
        input_tokens = len(system_prompt.split()) + len(user_prompt.split())
        output_tokens = len(response_text.split())

        return {
            "recommendations": recommendations,
            "reasoning": response_text,
            "input_tokens": input_tokens * 2,  # Rough estimate
            "output_tokens": output_tokens * 2,
        }

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
