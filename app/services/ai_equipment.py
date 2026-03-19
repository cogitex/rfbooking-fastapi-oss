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

"""Equipment filtering and requirement extraction for AI Assistant."""

import re
import json
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models.equipment import Equipment, AISpecificationRule


class AIEquipmentFilter:
    """Filter equipment based on technical requirements extracted from prompts."""

    # Power requirement patterns (in Watts)
    POWER_PATTERNS = [
        r'(?:at\s+)?(?:power\s+)?(\d+)\s*W(?:att)?s?',
        r'(\d+)\s*W\s+power',
        r'power\s+handling.*?(\d+)\s*W',
        r'(\d+)\s*watts?'
    ]

    # Frequency requirement patterns (in GHz)
    FREQUENCY_PATTERNS = [
        r'(\d+\.?\d*)\s*GHz\s*[-–]\s*(\d+\.?\d*)\s*GHz',  # Range: "1.3 GHz - 1.5 GHz"
        r'(?:at\s+)?(\d+\.?\d*)\s*GHz'  # Single: "at 2.4 GHz"
    ]

    # Temperature requirement patterns (in °C)
    TEMPERATURE_PATTERNS = [
        r'(?:at\s+)?(-?\d+)\s*deg\s*C',
        r'(?:at\s+)?(-?\d+)\s*°\s*C',
        r'(?:at\s+)?(-?\d+)\s*C(?!\w)',
        r'temperature.*?(-?\d+)\s*(?:deg|°)?\s*C',
        r'(-?\d+)\s*degrees?\s+C'
    ]

    # Voltage requirement patterns (in V)
    VOLTAGE_PATTERNS = [
        r'(?:at\s+)?(\d+)\s*V(?:olt)?s?',
        r'voltage.*?(\d+)\s*V',
        r'(\d+)\s*volts?'
    ]

    # Current requirement patterns (in A)
    CURRENT_PATTERNS = [
        r'(?:at\s+)?(\d+\.?\d*)\s*A(?:mp)?s?',
        r'current.*?(\d+\.?\d*)\s*A',
        r'(\d+\.?\d*)\s*amps?'
    ]

    @staticmethod
    def extract_power_requirement(prompt: str) -> Optional[int]:
        """Extract power requirement from user prompt (in Watts)."""
        for pattern in AIEquipmentFilter.POWER_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def extract_frequency_requirement(prompt: str) -> Optional[Dict[str, float]]:
        """Extract frequency requirement from user prompt (in GHz)."""
        for pattern in AIEquipmentFilter.FREQUENCY_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                if match.group(2):
                    # Range found
                    return {'min': float(match.group(1)), 'max': float(match.group(2))}
                else:
                    # Single frequency - treat as exact
                    freq = float(match.group(1))
                    return {'min': freq, 'max': freq}
        return None

    @staticmethod
    def extract_temperature_requirement(prompt: str) -> Optional[int]:
        """Extract temperature requirement from user prompt (in °C)."""
        for pattern in AIEquipmentFilter.TEMPERATURE_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                # Find the first capturing group that captured a number
                for i in range(1, len(match.groups()) + 1):
                    if match.group(i):
                        return int(match.group(i))
        return None

    @staticmethod
    def extract_voltage_requirement(prompt: str) -> Optional[int]:
        """Extract voltage requirement from user prompt (in V)."""
        for pattern in AIEquipmentFilter.VOLTAGE_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def extract_current_requirement(prompt: str) -> Optional[float]:
        """Extract current requirement from user prompt (in A)."""
        for pattern in AIEquipmentFilter.CURRENT_PATTERNS:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def extract_equipment_power(description: str) -> Optional[Dict[str, int]]:
        """Extract power specs from equipment description."""
        if not description:
            return None
        power_pattern = r'Power\s+Handling.*?(\d+)\s*/\s*(\d+)'
        match = re.search(power_pattern, description, re.IGNORECASE)
        if match:
            return {'cw': int(match.group(1)), 'pulsed': int(match.group(2))}
        return None

    @staticmethod
    def extract_equipment_frequency(description: str) -> Optional[Dict[str, float]]:
        """Extract frequency range from equipment description."""
        if not description:
            return None
        freq_pattern = r'(?:Bandwidth|Frequency).*?(\d+\.?\d*)\s*[–-]\s*(\d+\.?\d*)'
        match = re.search(freq_pattern, description, re.IGNORECASE)
        if match:
            return {'min': float(match.group(1)), 'max': float(match.group(2))}
        return None

    @staticmethod
    def extract_equipment_temperature(description: str) -> Optional[Dict[str, int]]:
        """Extract temperature range from equipment description."""
        if not description:
            return None
        temp_pattern = r'Temperature.*?(-?\d+)\s*°?\s*C\s*to\s*[+]?(-?\d+)\s*°?\s*C'
        match = re.search(temp_pattern, description, re.IGNORECASE)
        if match:
            return {'min': int(match.group(1)), 'max': int(match.group(2))}
        return None

    @staticmethod
    def extract_equipment_voltage(description: str) -> Optional[Dict[str, int]]:
        """Extract voltage range from equipment description."""
        if not description:
            return None
        voltage_pattern = r'Voltage.*?(\d+)\s*[–-]\s*(\d+)\s*V'
        match = re.search(voltage_pattern, description, re.IGNORECASE)
        if match:
            return {'min': int(match.group(1)), 'max': int(match.group(2))}
        return None

    @staticmethod
    def extract_equipment_current(description: str) -> Optional[Dict[str, float]]:
        """Extract current range from equipment description."""
        if not description:
            return None
        current_pattern = r'Current.*?(\d+\.?\d*)\s*[–-]\s*(\d+\.?\d*)\s*A'
        match = re.search(current_pattern, description, re.IGNORECASE)
        if match:
            return {'min': float(match.group(1)), 'max': float(match.group(2))}
        return None

    @staticmethod
    def filter_equipment_by_requirements(equipment_list: List[Equipment], prompt: str) -> List[Equipment]:
        """Pre-filter equipment based on extracted requirements from user prompt."""
        filtered = []

        # Extract requirements from user prompt
        temp_req = AIEquipmentFilter.extract_temperature_requirement(prompt)
        power_req = AIEquipmentFilter.extract_power_requirement(prompt)
        voltage_req = AIEquipmentFilter.extract_voltage_requirement(prompt)
        current_req = AIEquipmentFilter.extract_current_requirement(prompt)

        print(f'[Filter] Requirements: {{temp: {temp_req}, power: {power_req}, voltage: {voltage_req}, current: {current_req}}}')

        for eq in equipment_list:
            matches = True
            reasons = []

            # TEMPERATURE filtering (STRICT)
            if temp_req is not None:
                eq_temp = AIEquipmentFilter.extract_equipment_temperature(eq.description or '')
                if eq_temp:
                    if eq_temp['max'] < temp_req:
                        print(f'[Filter] REJECT "{eq.name}": max temp {eq_temp["max"]}°C < required {temp_req}°C')
                        reasons.append(f'temperature max {eq_temp["max"]}°C < {temp_req}°C')
                        matches = False
                    else:
                        print(f'[Filter] ACCEPT "{eq.name}": temp range {eq_temp["min"]}-{eq_temp["max"]}°C covers {temp_req}°C')
                else:
                    # No temperature spec found - include (cannot verify)
                    print(f'[Filter] INCLUDE "{eq.name}": no temperature spec (cannot verify)')

            # POWER filtering (STRICT)
            if matches and power_req is not None:
                eq_power = AIEquipmentFilter.extract_equipment_power(eq.description or '')
                if eq_power:
                    max_power = max(eq_power['cw'], eq_power['pulsed'])
                    if max_power < power_req:
                        print(f'[Filter] REJECT "{eq.name}": max power {max_power}W < required {power_req}W')
                        reasons.append(f'power max {max_power}W < {power_req}W')
                        matches = False
                    else:
                        print(f'[Filter] ACCEPT "{eq.name}": max power {max_power}W >= {power_req}W')
                else:
                    # No power spec found - include (cannot verify)
                    print(f'[Filter] INCLUDE "{eq.name}": no power spec (cannot verify)')

            # VOLTAGE filtering (STRICT)
            if matches and voltage_req is not None:
                eq_voltage = AIEquipmentFilter.extract_equipment_voltage(eq.description or '')
                if eq_voltage:
                    if eq_voltage['max'] < voltage_req:
                        print(f'[Filter] REJECT "{eq.name}": max voltage {eq_voltage["max"]}V < required {voltage_req}V')
                        reasons.append(f'voltage max {eq_voltage["max"]}V < {voltage_req}V')
                        matches = False
                    else:
                        print(f'[Filter] ACCEPT "{eq.name}": voltage range {eq_voltage["min"]}-{eq_voltage["max"]}V covers {voltage_req}V')
                else:
                    print(f'[Filter] INCLUDE "{eq.name}": no voltage spec (cannot verify)')

            # CURRENT filtering (STRICT)
            if matches and current_req is not None:
                eq_current = AIEquipmentFilter.extract_equipment_current(eq.description or '')
                if eq_current:
                    if eq_current['max'] < current_req:
                        print(f'[Filter] REJECT "{eq.name}": max current {eq_current["max"]}A < required {current_req}A')
                        reasons.append(f'current max {eq_current["max"]}A < {current_req}A')
                        matches = False
                    else:
                        print(f'[Filter] ACCEPT "{eq.name}": current range {eq_current["min"]}-{eq_current["max"]}A covers {current_req}A')
                else:
                    print(f'[Filter] INCLUDE "{eq.name}": no current spec (cannot verify)')

            if matches:
                filtered.append(eq)
            else:
                print(f'[Filter] Equipment "{eq.name}" excluded: {", ".join(reasons)}')

        print(f'[Filter] Results: {len(filtered)}/{len(equipment_list)} equipment items pass requirements')
        return filtered

    @staticmethod
    def build_equipment_context_from_list(equipment_list: List[Equipment]) -> str:
        """Build equipment context for AI from pre-filtered equipment list."""
        if not equipment_list:
            return "No equipment available matching your requirements."

        lines = []
        for eq in equipment_list:
            lines.append(f"- Equipment ID {eq.id}: \"{eq.name}\" ({eq.equipment_type.name if eq.equipment_type else 'Unknown type'})")
            lines.append(f"  Description: {eq.description or 'N/A'}")
            lines.append(f"  Location: {eq.location or 'N/A'}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def build_equipment_context(db: Session, org_id: int, prompt: Optional[str] = None) -> str:
        """Build equipment context for AI (loads from DB and optionally filters)."""
        equipment = db.query(Equipment).filter(Equipment.is_active == True).order_by(Equipment.name).all()

        if not equipment:
            return "No equipment available in your organization."

        # If prompt provided, pre-filter equipment based on requirements
        equipment_list = equipment
        if prompt:
            equipment_list = AIEquipmentFilter.filter_equipment_by_requirements(equipment, prompt)

        return AIEquipmentFilter.build_equipment_context_from_list(equipment_list)

    @staticmethod
    def build_equipment_types_context(db: Session) -> str:
        """Build equipment types list with descriptions."""
        from app.models.equipment import EquipmentType
        types = db.query(EquipmentType).filter(EquipmentType.is_active == True).order_by(EquipmentType.name).all()

        if not types:
            return "No equipment types defined."

        lines = []
        for t in types:
            if t.description and t.description.strip():
                lines.append(f"- {t.name}: {t.description}")
            else:
                lines.append(f"- {t.name}")

        return "\n".join(lines)

    @staticmethod
    def load_specification_rules(db: Session, org_id: int) -> List[AISpecificationRule]:
        """Load AI specification rules from database for current organization."""
        rules = db.query(AISpecificationRule)\
            .filter(AISpecificationRule.is_enabled == True)\
            .order_by(AISpecificationRule.display_order)\
            .all()
        return rules

    @staticmethod
    def build_specification_matching_prompt(rules: List[AISpecificationRule]) -> str:
        """Build specification matching section of AI prompt dynamically from database rules."""
        if not rules:
            return ''  # No rules configured

        sections = [rule.prompt_text for rule in rules]
        return '\n\nSPECIFICATION MATCHING (STRICT REQUIREMENTS):\n\n' + '\n\n'.join(sections)

    @staticmethod
    def extract_parameter_from_prompt(prompt: str, patterns: str, parameter_name: str) -> Any:
        """Extract parameter value from user prompt using DB-defined patterns."""
        if not patterns:
            return None

        try:
            pattern_array = json.loads(patterns)
        except json.JSONDecodeError as e:
            print(f'[AI Assistant] Invalid JSON in user_prompt_patterns for {parameter_name}: {e}')
            return None

        for pattern_str in pattern_array:
            try:
                regex = re.compile(pattern_str, re.IGNORECASE)
                match = regex.search(prompt)
                if match:
                    # For ranges (frequency), return object with min/max
                    if match.lastindex >= 2 and match.group(2):
                        return {
                            'min': float(match.group(1)),
                            'max': float(match.group(2))
                        }
                    # For single values, return the number
                    if parameter_name == 'current':
                        return float(match.group(1))
                    else:
                        return int(match.group(1))
            except re.error as e:
                print(f'[AI Assistant] Invalid regex pattern for {parameter_name}: {pattern_str} - {e}')
                continue

        return None

    @staticmethod
    def extract_parameter_from_equipment(description: str, patterns: str, parameter_name: str) -> Any:
        """Extract parameter range from equipment description using DB-defined patterns."""
        if not description or not patterns:
            return None

        try:
            pattern_array = json.loads(patterns)
        except json.JSONDecodeError as e:
            print(f'[AI Assistant] Invalid JSON in equipment_patterns for {parameter_name}: {e}')
            return None

        for pattern_str in pattern_array:
            try:
                regex = re.compile(pattern_str, re.IGNORECASE)
                match = regex.search(description)
                if match:
                    # Special case for power: CW/Pulsed format
                    if parameter_name == 'power' and match.lastindex >= 2 and match.group(2):
                        return {
                            'cw': int(match.group(1)),
                            'pulsed': int(match.group(2))
                        }
                    # For ranges, return min/max
                    if match.lastindex >= 2 and match.group(2):
                        if parameter_name == 'current':
                            return {
                                'min': float(match.group(1)),
                                'max': float(match.group(2))
                            }
                        else:
                            return {
                                'min': int(match.group(1)),
                                'max': int(match.group(2))
                            }
            except re.error as e:
                print(f'[AI Assistant] Invalid regex pattern for {parameter_name}: {pattern_str} - {e}')
                continue

        return None

    @staticmethod
    async def validate_equipment(equipment_name: str, user_requirements: Dict[str, Any],
                                 db: Session, spec_rules: List[AISpecificationRule]) -> bool:
        """Validate equipment against user requirements using DB-defined rules."""
        # Get equipment details from database
        equipment = db.query(Equipment).filter(
            Equipment.name == equipment_name,
            Equipment.is_active == True
        ).first()

        if not equipment:
            print(f'[Validation] Equipment "{equipment_name}" not found')
            return False

        description = equipment.description or ''

        # Validate each required parameter against equipment specs
        for param_name, user_value in user_requirements.items():
            # Find the rule for this parameter
            rule = next((r for r in spec_rules if r.parameter_name == param_name), None)
            if not rule or not rule.equipment_patterns:
                continue

            # Extract equipment capability for this parameter
            equip_value = AIEquipmentFilter.extract_parameter_from_equipment(
                description, rule.equipment_patterns, param_name
            )

            if not equip_value:
                print(f'[Validation] Cannot extract {param_name} specs from "{equipment_name}"')
                continue  # Trust AI if we can't extract (avoid false negatives)

            # Validate based on parameter type
            if param_name == 'power':
                # Power: check max capability (higher of CW/Pulsed)
                max_power = max(equip_value['cw'], equip_value['pulsed'])
                if max_power < user_value:
                    print(f'[Validation] REJECTED "{equipment_name}": max power {max_power}{rule.parameter_unit} < required {user_value}{rule.parameter_unit}')
                    return False
            elif param_name == 'frequency':
                # Frequency: check if user range is within equipment range
                if user_value['min'] < equip_value['min'] or user_value['max'] > equip_value['max']:
                    print(f'[Validation] REJECTED "{equipment_name}": freq range {equip_value["min"]}-{equip_value["max"]}{rule.parameter_unit} doesn\'t cover required {user_value["min"]}-{user_value["max"]}{rule.parameter_unit}')
                    return False
            else:
                # Other parameters (temperature, voltage, current): check if user value is within range
                if equip_value['min'] is not None and equip_value['max'] is not None:
                    if user_value < equip_value['min'] or user_value > equip_value['max']:
                        print(f'[Validation] REJECTED "{equipment_name}": {param_name} range {equip_value["min"]}-{equip_value["max"]}{rule.parameter_unit} doesn\'t cover required {user_value}{rule.parameter_unit}')
                        return False

        print(f'[Validation] ACCEPTED "{equipment_name}"')
        return True