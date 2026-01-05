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

"""AI Assistant routes for equipment recommendation."""

from datetime import date, datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user, require_admin
from app.models.equipment import Equipment, EquipmentTypeUser, AIUsage, AIQueryLog, AISpecificationRule
from app.models.user import User

router = APIRouter(prefix="/api/ai")


class AnalyzeRequest(BaseModel):
    """AI analyze request."""

    prompt: str
    preferred_start: Optional[date] = None
    preferred_end: Optional[date] = None


class ChatRequest(BaseModel):
    """AI chat request."""

    message: str
    system_prompt: Optional[str] = None


@router.post("/analyze")
async def analyze_booking_request(
    data: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Analyze booking request with AI and return equipment recommendations."""
    settings = get_settings()

    if not settings.ai.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is disabled",
        )

    # Get AI service
    from app.services.ai_service import get_ai_service

    ai_service = get_ai_service()

    # Get user's accessible equipment
    if current_user.is_admin:
        equipment_list = (
            db.query(Equipment)
            .filter(Equipment.is_active == True)
            .all()
        )
    else:
        accessible_type_ids = (
            db.query(EquipmentTypeUser.type_id)
            .filter(EquipmentTypeUser.user_id == current_user.id)
            .all()
        )
        accessible_type_ids = [t[0] for t in accessible_type_ids]

        equipment_list = (
            db.query(Equipment)
            .filter(
                Equipment.is_active == True,
                (Equipment.type_id.in_(accessible_type_ids)) | (Equipment.type_id.is_(None)),
            )
            .all()
        )

    if not equipment_list:
        return {
            "success": True,
            "message": "No equipment available for booking",
            "recommendations": [],
        }

    # Get AI specification rules
    rules = (
        db.query(AISpecificationRule)
        .filter(AISpecificationRule.is_enabled == True)
        .order_by(AISpecificationRule.display_order)
        .all()
    )

    try:
        # Call AI service
        result = await ai_service.analyze_booking_request(
            prompt=data.prompt,
            equipment_list=equipment_list,
            rules=rules,
            preferred_start=data.preferred_start,
            preferred_end=data.preferred_end,
            db=db,
            user=current_user,
        )

        # Log usage
        today = date.today()
        usage = db.query(AIUsage).filter(AIUsage.date == today).first()
        if not usage:
            usage = AIUsage(date=today)
            db.add(usage)

        usage.queries_count += 1
        usage.input_tokens += result.get("input_tokens", 0)
        usage.output_tokens += result.get("output_tokens", 0)

        # Log query
        query_log = AIQueryLog(
            user_id=current_user.id,
            prompt=data.prompt,
            response=str(result.get("recommendations", [])),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            model=settings.ai.model,
            success=True,
        )
        db.add(query_log)
        db.commit()

        return {
            "success": True,
            "recommendations": result.get("recommendations", []),
            "reasoning": result.get("reasoning"),
            "available_slots": result.get("available_slots", []),
            "usage": {
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
            },
        }

    except Exception as e:
        # Log error
        query_log = AIQueryLog(
            user_id=current_user.id,
            prompt=data.prompt,
            model=settings.ai.model,
            success=False,
            error_message=str(e),
        )
        db.add(query_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(e)}",
        )


@router.post("/chat")
async def chat_with_ai(
    data: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Direct chat with AI (admin only)."""
    settings = get_settings()

    if not settings.ai.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI Assistant is disabled",
        )

    from app.services.ai_service import get_ai_service

    ai_service = get_ai_service()

    try:
        result = await ai_service.chat(
            message=data.message,
            system_prompt=data.system_prompt,
        )

        # Log usage
        today = date.today()
        usage = db.query(AIUsage).filter(AIUsage.date == today).first()
        if not usage:
            usage = AIUsage(date=today)
            db.add(usage)

        usage.queries_count += 1
        usage.input_tokens += result.get("input_tokens", 0)
        usage.output_tokens += result.get("output_tokens", 0)

        # Log query
        query_log = AIQueryLog(
            user_id=current_user.id,
            prompt=data.message,
            response=result.get("response", ""),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            model=settings.ai.model,
            success=True,
        )
        db.add(query_log)
        db.commit()

        return {
            "success": True,
            "response": result.get("response"),
            "usage": {
                "input_tokens": result.get("input_tokens", 0),
                "output_tokens": result.get("output_tokens", 0),
            },
        }

    except Exception as e:
        query_log = AIQueryLog(
            user_id=current_user.id,
            prompt=data.message,
            model=settings.ai.model,
            success=False,
            error_message=str(e),
        )
        db.add(query_log)
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI chat failed: {str(e)}",
        )


@router.get("/usage")
async def get_ai_usage(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Get AI usage statistics (admin only)."""
    from datetime import timedelta

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    usage_records = (
        db.query(AIUsage)
        .filter(AIUsage.date >= start_date, AIUsage.date <= end_date)
        .order_by(AIUsage.date)
        .all()
    )

    total_queries = sum(u.queries_count for u in usage_records)
    total_input_tokens = sum(u.input_tokens for u in usage_records)
    total_output_tokens = sum(u.output_tokens for u in usage_records)

    daily_data = [
        {
            "date": u.date.isoformat(),
            "queries": u.queries_count,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
        }
        for u in usage_records
    ]

    return {
        "success": True,
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
        "summary": {
            "total_queries": total_queries,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        },
        "daily": daily_data,
    }
