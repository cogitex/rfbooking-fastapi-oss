# AI Assistant & Specification Rules: Porting Status

This document analyzes the status of porting AI features from `rfbooking-core` (Cloudflare Workers) to `rfbooking-fastapi-oss` (FastAPI).

## Overview

The core AI Assistant logic (date extraction, equipment filtering, AI matching) has been largely ported to the `app/services/` modules in the FastAPI project. However, the management interface for **AI Specification Rules** is entirely missing, and some user experience refinements (summaries/tips) are not yet implemented.

## Missing Implementation: AI Specification Rules API

In `rfbooking-core`, `src/routes/ai-specification-rules.js` provides a CRUD interface for administrators to define how the AI interprets user prompts and matches them to equipment (e.g., regex patterns for power, frequency). This allows the system to be tuned without code changes.

**These endpoints are missing in `rfbooking-fastapi-oss` and need to be implemented:**

| Method | Route | Description | Source File |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/admin/ai-specification-rules` | List all specification rules. | `ai-specification-rules.js` |
| `POST` | `/api/admin/ai-specification-rules` | Create a new rule (types: `general`, `parameter`, `example`). | `ai-specification-rules.js` |
| `PATCH` | `/api/admin/ai-specification-rules/:id` | Update an existing rule. | `ai-specification-rules.js` |
| `DELETE` | `/api/admin/ai-specification-rules/:id` | Delete a rule. | `ai-specification-rules.js` |

### Requirements for Porting
1.  **New Router**: Create `app/routes/ai_specification_rules.py`.
2.  **Access Control**: Ensure endpoints are protected by `require_admin` dependency (replacing the hardcoded email check from core).
3.  **Database**: Use the existing `AISpecificationRule` SQLAlchemy model.
4.  **Validation**: Replicate input validation (e.g., valid JSON for patterns, required fields).

## Functional Differences & Enhancements

### 1. User Experience (Summaries & Tips)
`rfbooking-core` generates human-friendly text summaries and tips based on the search results. This logic is **missing** in the FastAPI port, which returns raw JSON.

*   **Missing Function**: `generateSummary(results, searchDays, dateConstraints)`
*   **Missing Function**: `generateConversationalTips(results, dateConstraints, searchDays)`
*   **Impact**: The frontend receives raw data but lacks the "conversational" feel of the assistant (e.g., "Great news! Found 3 available slots...").

### 2. Validation Workflow
*   **Core**: Uses a "sandwich" approach:
    1.  **Pre-filter** equipment based on strict regex.
    2.  **AI Match** suitable equipment types.
    3.  **Post-validate** AI suggestions against rules (`validateEquipment`).
*   **FastAPI**: Currently implements **Pre-filtering** (`AIEquipmentFilter`) and **AI Matching**. The strict **Post-validation** step (verifying the *specific* items returned by the AI still meet criteria) appears less explicit or merged into the pre-filtering stage.
*   **Action**: Verify if `AIEquipmentFilter` alone is sufficient or if the explicit post-validation step from `ai-assistant.js` (`validateEquipment`) should be reintroduced to prevent hallucinations.

### 3. Rate Limiting
*   **Core**: Uses Cloudflare KV/Durable Objects or in-memory map for rate limiting.
*   **FastAPI**: Uses a simple in-memory dictionary `_rate_limit_cache`.
*   **Note**: For a single-instance OSS deployment, in-memory is acceptable. If scaling with multiple workers (e.g., Gunicorn), this will need Redis.

## Multi-tenancy Notes
*   **`org_id`**: The `rfbooking-core` uses `org_id` for almost all queries. In `rfbooking-fastapi-oss` (single-tenant), this parameter should be removed or ignored. The ported code should operate on the global scope or per-user scope where appropriate.
*   **Super Admin**: The concept of "Super Admin" (hardcoded email) in Core should map to the standard `is_admin` flag in the `User` model.

## Action Plan

1.  **Implement `app/routes/ai_rules.py`**: Port the CRUD logic for specification rules.
2.  **Enhance `AI Service`**: Port `generateSummary` and `generateConversationalTips` to Python to enrich the API response.
3.  **Review Validation**: Ensure the pre-filtering logic in `AIEquipmentFilter` is robust enough to replace the post-validation step.

