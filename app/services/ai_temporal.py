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

"""Temporal expression parsing for AI Assistant."""

import re
import json
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, Tuple


class TemporalParser:
    """Parse natural language date expressions into structured constraints."""

    # Weekday names (Monday=0 to match date.weekday())
    WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

    # Month names
    MONTHS = [
        'january', 'february', 'march', 'april', 'may', 'june',
        'july', 'august', 'september', 'october', 'november', 'december'
    ]

    # Number words to digits
    NUMBER_WORDS = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }

    @staticmethod
    def get_next_weekday(weekday_name: str, from_date: date) -> Optional[date]:
        """Get the next occurrence of a specific weekday."""
        weekday_lower = weekday_name.lower()
        target_day = TemporalParser.WEEKDAYS.index(weekday_lower)
        # Find next occurrence
        days_until = target_day - from_date.weekday()  # weekday() returns Monday=0..Sunday=6
        if days_until <= 0:
            days_until += 7  # Next week if today or past
        result = from_date + timedelta(days=days_until)
        print(f'[TemporalParser] get_next_weekday: {weekday_lower} from {from_date}, target_day={target_day}, from_date.weekday()={from_date.weekday()}, days_until={days_until}, result={result}')
        return result

    @staticmethod
    def get_next_week_range(from_date: date) -> Dict[str, date]:
        """Get the start and end of next week (Monday to Friday)."""
        # Get to next Monday
        days_until_monday = (7 - from_date.weekday()) % 7 or 7  # Monday=0
        monday = from_date + timedelta(days=days_until_monday)
        # Friday of that week
        friday = monday + timedelta(days=4)
        return {'start': monday, 'end': friday}

    @staticmethod
    def get_end_of_next_week(from_date: date) -> Dict[str, date]:
        """Get end of next week (Thursday-Friday)."""
        next_week = TemporalParser.get_next_week_range(from_date)
        thursday = next_week['end'] - timedelta(days=1)  # Friday - 1 day = Thursday
        return {'start': thursday, 'end': next_week['end']}

    @staticmethod
    def get_first_week_of_month(month_name: str, year: int, from_date: date) -> Optional[Dict[str, date]]:
        """Get the first week of a specific month (Monday to Friday)."""
        try:
            month_index = TemporalParser.MONTHS.index(month_name.lower())
        except ValueError:
            return None

        # Adjust year if month is in the past
        current_month = from_date.month - 1  # zero-indexed
        if month_index < current_month:
            year += 1

        first_day = date(year, month_index + 1, 1)  # month_index is zero-based

        # Find first Monday
        monday = first_day
        while monday.weekday() != 0:  # Monday = 0
            monday += timedelta(days=1)

        # First Friday
        friday = monday + timedelta(days=4)
        return {'start': monday, 'end': friday}

    @staticmethod
    def extract_number(text: str) -> Optional[int]:
        """Extract number from text (handles both digits and words)."""
        # Try digit first
        digit_match = re.search(r'\b(\d+)\b', text)
        if digit_match:
            return int(digit_match.group(1))

        # Try word
        lower = text.lower()
        for word, num in TemporalParser.NUMBER_WORDS.items():
            if word in lower:
                return num

        return None

    @staticmethod
    def detect_user_intent(prompt: str) -> str:
        """Detect user intent from prompt structure: 'query' or 'booking'."""
        lower = prompt.lower()

        # Query intent patterns: user is asking what's available
        query_patterns = [
            r'\b(which|what|show|list|tell me)\b.*\bavailable\b',
            r'\bavailable\b.*\b(which|what)\b',
            r'\bcan (i|you) (see|show|get|find)\b'
        ]

        for pattern in query_patterns:
            if re.search(pattern, lower, re.IGNORECASE):
                return 'query'

        # Booking intent patterns: user wants to make a booking
        booking_patterns = [
            r'\b(i need|i want|need|want|book|reserve|looking for)\b',
            r'\bstarting\b.*\b(on|next|monday|tuesday|wednesday|thursday|friday)\b'
        ]

        for pattern in booking_patterns:
            if re.search(pattern, lower, re.IGNORECASE):
                return 'booking'

        # Default: if unclear, treat as booking intent (more helpful)
        return 'booking'

    @staticmethod
    def parse_temporal_expression(prompt: str, today: date) -> Dict[str, Any]:
        """Rule-based temporal expression parser.

        Returns: {
            'preferred_start': date or None,
            'preferred_end': date or None,
            'duration': int or None,
            'flexibility': 'exact'|'flexible'|'any',
            'confidence': 'high'|'medium'|'low',
            'intent': 'query'|'booking'
        }
        """
        lower = prompt.lower()
        intent = TemporalParser.detect_user_intent(prompt)
        print(f'[TemporalParser] parse_temporal_expression: prompt="{prompt}", today={today}, intent={intent}')

        # Pattern 1: "tomorrow"
        if re.search(r'\btomorrow\b', lower, re.IGNORECASE):
            tomorrow = today + timedelta(days=1)
            return {
                'preferred_start': tomorrow,
                'flexibility': 'exact',
                'confidence': 'high',
                'intent': intent
            }

        # Pattern 2: "today"
        if re.search(r'\btoday\b', lower, re.IGNORECASE):
            return {
                'preferred_start': today,
                'flexibility': 'exact',
                'confidence': 'high',
                'intent': intent
            }

        # Pattern 3: "[X] days starting next [weekday]" (e.g., "two days starting next Tuesday")
        days_starting_match = re.search(
            r'(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten) days?(?: starting| beginning| from)? next (monday|tuesday|wednesday|thursday|friday|saturday|sunday)|for (\d+|one|two|three|four|five|six|seven|eight|nine|ten) days? starting next (monday|tuesday|wednesday|thursday|friday|saturday|sunday))',
            lower, re.IGNORECASE
        )
        if days_starting_match:
            # Extract duration and weekday from match groups
            duration_str = days_starting_match.group(1) or days_starting_match.group(3)
            weekday = days_starting_match.group(2) or days_starting_match.group(4)
            duration = TemporalParser.extract_number(duration_str)
            next_date = TemporalParser.get_next_weekday(weekday, today)
            if duration and next_date:
                print(f'[TemporalParser] Matched "X days starting next Y": duration={duration}, weekday={weekday}, next_date={next_date}')
                return {
                    'preferred_start': next_date,
                    'duration': duration,
                    'flexibility': 'exact',
                    'confidence': 'high',
                    'intent': intent
                }

        # Pattern 4: "next [weekday]"
        next_weekday_match = re.search(
            r'next (monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            lower, re.IGNORECASE
        )
        if next_weekday_match:
            weekday = next_weekday_match.group(1)
            next_date = TemporalParser.get_next_weekday(weekday, today)
            if next_date:
                print(f'[TemporalParser] Matched "next [weekday]": weekday={weekday}, next_date={next_date}')
                return {
                    'preferred_start': next_date,
                    'flexibility': 'exact',
                    'confidence': 'high',
                    'intent': intent
                }

        # Pattern 5: "end of next week"
        if re.search(r'end of next week', lower, re.IGNORECASE):
            range = TemporalParser.get_end_of_next_week(today)
            return {
                'preferred_start': range['start'],
                'preferred_end': range['end'],
                'flexibility': 'flexible',
                'confidence': 'high',
                'intent': intent
            }

        # Pattern 6: "next week"
        if re.search(r'\bnext week\b', lower, re.IGNORECASE):
            range = TemporalParser.get_next_week_range(today)
            return {
                'preferred_start': range['start'],
                'preferred_end': range['end'],
                'flexibility': 'flexible',
                'confidence': 'high',
                'intent': intent
            }

        # Pattern 7: "first week of [month]"
        first_week_match = re.search(
            r'first week of (january|february|march|april|may|june|july|august|september|october|november|december)',
            lower, re.IGNORECASE
        )
        if first_week_match:
            month = first_week_match.group(1)
            range = TemporalParser.get_first_week_of_month(month, today.year, today)
            if range:
                return {
                    'preferred_start': range['start'],
                    'preferred_end': range['end'],
                    'flexibility': 'flexible',
                    'confidence': 'high',
                    'intent': intent
                }

        # Pattern 8: "[number] days next week" or "next week for [number] days"
        days_next_week_match = re.search(
            r'(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten) days?.+next week|next week.+?(\d+|one|two|three|four|five|six|seven|eight|nine|ten) days?)',
            lower, re.IGNORECASE
        )
        if days_next_week_match:
            duration_str = days_next_week_match.group(1) or days_next_week_match.group(2)
            duration = TemporalParser.extract_number(duration_str)
            if duration:
                range = TemporalParser.get_next_week_range(today)
                return {
                    'preferred_start': range['start'],
                    'duration': duration,
                    'flexibility': 'flexible',
                    'confidence': 'high',
                    'intent': intent
                }

        # Pattern 9: "[number] days" (extract duration only)
        duration_match = re.search(
            r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten) days?',
            lower, re.IGNORECASE
        )
        if duration_match:
            duration = TemporalParser.extract_number(duration_match.group(1))
            if duration:
                return {
                    'duration': duration,
                    'flexibility': 'any',
                    'confidence': 'medium',
                    'intent': intent
                }

        # No pattern matched
        return {
            'flexibility': 'any',
            'confidence': 'low',
            'intent': intent
        }

    @staticmethod
    def ai_date_extraction(prompt: str, today: date, ai_client, model_config: Dict) -> Dict[str, Any]:
        """AI-based fallback for complex temporal expressions."""
        intent = TemporalParser.detect_user_intent(prompt)

        # Prepare examples using helper functions
        next_monday = TemporalParser.get_next_weekday('monday', today)
        end_of_next_week = TemporalParser.get_end_of_next_week(today)
        next_week_range = TemporalParser.get_next_week_range(today)

        # Calculate more examples
        next_tuesday = TemporalParser.get_next_weekday('tuesday', today)
        two_days_from_today = today + timedelta(days=2)

        date_extraction_prompt = f"""Current date: {today.isoformat()} (today is {today.strftime('%A')})

Extract date constraints from this booking request: "{prompt}"

Return ONLY valid JSON in this exact format:
{{
  "preferred_start_date": "YYYY-MM-DD" or null,
  "preferred_end_date": "YYYY-MM-DD" or null,
  "duration_days": number or null,
  "date_flexibility": "exact" or "flexible" or "any"
}}

Examples:
"Next Monday" → {{"preferred_start_date": "{next_monday.isoformat() if next_monday else ''}", "date_flexibility": "exact"}}
"Next Tuesday" → {{"preferred_start_date": "{next_tuesday.isoformat() if next_tuesday else ''}", "date_flexibility": "exact"}}
"Two days starting next Tuesday" → {{"preferred_start_date": "{next_tuesday.isoformat() if next_tuesday else ''}", "duration_days": 2, "date_flexibility": "exact"}}
"Three days next week" → {{"preferred_start_date": "{next_week_range['start'].isoformat()}", "duration_days": 3, "date_flexibility": "flexible"}}
"Two days from today" → {{"preferred_start_date": "{today.isoformat()}", "preferred_end_date": "{two_days_from_today.isoformat()}", "date_flexibility": "exact"}}
"End of next week" → {{"preferred_start_date": "{end_of_next_week['start'].isoformat()}", "preferred_end_date": "{end_of_next_week['end'].isoformat()}", "date_flexibility": "flexible"}}
"Two days" → {{"duration_days": 2, "date_flexibility": "any"}}
"One week" → {{"duration_days": 7, "date_flexibility": "any"}}
"No specific date" → {{"date_flexibility": "any"}}

IMPORTANT: Return ONLY the JSON object, no other text."""

        try:
            # Call AI client synchronously (Ollama)
            response = ai_client.chat(
                model=model_config['id'],
                messages=[
                    {"role": "system", "content": "You are a date extraction assistant. Return only valid JSON."},
                    {"role": "user", "content": date_extraction_prompt}
                ],
                options={
                    "num_predict": 150,
                    "temperature": 0.1
                }
            )

            response_text = response.get("message", {}).get("content", "").strip()

            # Clean response
            if response_text.startswith('```json'):
                response_text = re.sub(r'```json\n?', '', response_text)
                response_text = re.sub(r'```\n?', '', response_text)
            elif response_text.startswith('```'):
                response_text = re.sub(r'```\n?', '', response_text)

            parsed = json.loads(response_text)
            print(f'[AI Assistant] AI date extraction parsed: {parsed}')

            # Convert string dates to date objects
            result = {
                'preferred_start': parsed.get('preferred_start_date'),
                'preferred_end': parsed.get('preferred_end_date'),
                'duration': parsed.get('duration_days'),
                'flexibility': parsed.get('date_flexibility', 'any'),
                'confidence': 'medium',
                'intent': intent
            }

            # Convert string dates to date objects if present
            if result['preferred_start'] and isinstance(result['preferred_start'], str):
                result['preferred_start'] = date.fromisoformat(result['preferred_start'])
            if result['preferred_end'] and isinstance(result['preferred_end'], str):
                result['preferred_end'] = date.fromisoformat(result['preferred_end'])

            print(f'[AI Assistant] AI date extraction result: {result}')
            return result
        except Exception as error:
            print(f'[AI Assistant] Date extraction failed: {error}')
            return {
                'flexibility': 'any',
                'confidence': 'low',
                'intent': intent
            }

    @staticmethod
    def extract_date_constraints(prompt: str, today: date, ai_client, model_config) -> Dict[str, Any]:
        """Hybrid date extraction: Rule-based first, AI fallback for complex cases."""
        # Try rule-based parser first
        rule_parsed = TemporalParser.parse_temporal_expression(prompt, today)

        if rule_parsed.get('confidence') == 'high':
            # Check if we have a start date but missing duration when prompt contains duration words
            duration_pattern = r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten) days?'
            has_duration = re.search(duration_pattern, prompt, re.IGNORECASE)

            if rule_parsed.get('duration') is None and has_duration:
                print(f'[AI Assistant] Rule-based parsed start date but missing duration, using AI fallback')
                return TemporalParser.ai_date_extraction(prompt, today, ai_client, model_config)

            print(f'[AI Assistant] Date parsed using rules: {rule_parsed}')
            return rule_parsed

        # Fallback to AI for complex/ambiguous cases
        print('[AI Assistant] Falling back to AI for date extraction')
        return TemporalParser.ai_date_extraction(prompt, today, ai_client, model_config)