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

"""AI Specification Rules API Routes."""

from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_admin
from app.models.equipment import AISpecificationRule
from app.models.user import User

router = APIRouter()


# Pydantic Schemas
class RuleBase(BaseModel):
    """Base schema for AI specification rules."""
    rule_type: Literal['general', 'parameter', 'example']
    parameter_name: Optional[str] = None
    parameter_unit: Optional[str] = None
    is_enabled: bool = True
    prompt_text: str
    user_prompt_patterns: Optional[str] = None  # JSON string
    equipment_patterns: Optional[str] = None  # JSON string
    display_order: int = 0

    @validator('parameter_name')
    def validate_parameter_name(cls, v, values):
        if v and 'rule_type' in values and values['rule_type'] == 'parameter':
            if not v.strip():
                raise ValueError('parameter_name is required for parameter rules')
        return v

    @validator('rule_type')
    def validate_rule_type_dependencies(cls, v, values):
        if v == 'parameter' and not values.get('parameter_name'):
            # This might be caught by validate_parameter_name but good to double check
            pass # Validation logic handled in individual field validators or root validator
        return v


class RuleCreate(RuleBase):
    """Schema for creating a new rule."""
    @validator('parameter_name')
    def check_parameter_name_required(cls, v, values):
        if values.get('rule_type') == 'parameter' and not v:
            raise ValueError('parameter_name is required for parameter rules')
        return v


class RuleUpdate(BaseModel):
    """Schema for updating an existing rule."""
    rule_type: Optional[Literal['general', 'parameter', 'example']] = None
    parameter_name: Optional[str] = None
    parameter_unit: Optional[str] = None
    is_enabled: Optional[bool] = None
    prompt_text: Optional[str] = None
    user_prompt_patterns: Optional[str] = None
    equipment_patterns: Optional[str] = None
    display_order: Optional[int] = None


# Endpoints

@router.get("/api/admin/ai-specification-rules")
async def list_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """List all AI specification rules."""
    rules = (
        db.query(AISpecificationRule)
        .order_by(AISpecificationRule.display_order, AISpecificationRule.id)
        .all()
    )
    return {
        "success": True,
        "rules": [rule.to_dict() for rule in rules],
    }


@router.post("/api/admin/ai-specification-rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a new AI specification rule."""
    # Create rule instance
    new_rule = AISpecificationRule(
        rule_type=data.rule_type,
        parameter_name=data.parameter_name if data.rule_type == 'parameter' else None,
        parameter_unit=data.parameter_unit,
        is_enabled=data.is_enabled,
        prompt_text=data.prompt_text,
        user_prompt_patterns=data.user_prompt_patterns,
        equipment_patterns=data.equipment_patterns,
        display_order=data.display_order,
    )

    try:
        db.add(new_rule)
        db.commit()
        db.refresh(new_rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create rule: {str(e)}",
        )

    return {
        "success": True,
        "rule": new_rule.to_dict(),
    }


@router.patch("/api/admin/ai-specification-rules/{rule_id}")
async def update_rule(
    rule_id: int,
    data: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update an existing AI specification rule."""
    rule = db.query(AISpecificationRule).filter(AISpecificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    update_data = data.dict(exclude_unset=True)

    # Basic validation for rule type change
    if 'rule_type' in update_data and update_data['rule_type'] == 'parameter':
        # If switching TO parameter, ensure parameter_name exists (either in update or existing)
        param_name = update_data.get('parameter_name') or rule.parameter_name
        if not param_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="parameter_name is required when rule_type is parameter",
            )

    for field, value in update_data.items():
        setattr(rule, field, value)

    try:
        db.commit()
        db.refresh(rule)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update rule: {str(e)}",
        )

    return {
        "success": True,
        "rule": rule.to_dict(),
    }


@router.delete("/api/admin/ai-specification-rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete an AI specification rule."""
    rule = db.query(AISpecificationRule).filter(AISpecificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rule not found",
        )

    try:
        db.delete(rule)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete rule: {str(e)}",
        )

    return {
        "success": True,
        "message": "Rule deleted successfully",
    }
