# UI Alignment Log: rfbooking-fastapi-oss → rfbooking-core

Tracking all visual alignment changes to match the rfbooking-core design system.

## Step 1: CSS Brand Colors (orange → charcoal)
- **Commit**: `7a48430`
- **File**: `static/css/styles.css`
- **Changes**:
  - Replaced `--brand-*` CSS variables from orange/amber palette to charcoal
  - `--brand-600`: `#ea580c` → `#2c3e50`
  - Updated `input:focus` box-shadow from `rgba(249, 115, 22, 0.15)` → `rgba(44, 62, 80, 0.15)`
  - Updated `.form-input:focus` from purple accent to `var(--brand-600)`
  - Updated `.equipment-card.selected` box-shadow to charcoal

## Step 2: Card Styling (sharp corners, thicker borders)
- **Commit**: `0ebd5b7`
- **File**: `static/css/styles.css`
- **Changes**:
  - `.card` border-radius: `8px` → `0`
  - `.card` border: `1px solid var(--gray-200)` → `2px solid var(--brand-200)`
  - `.card-header` border-bottom: `1px` → `2px solid var(--brand-200)`
  - Added `.card:hover` shadow effect
  - Added responsive padding (16px mobile, 24px desktop)

## Step 3: Body Background + Sidebar Active Color
- **Commit**: `53f5bc7`
- **Files**: `templates/dashboard.html`, `static/css/styles.css`
- **Changes**:
  - Dashboard wrapper background: `bg-gray-50` → `#e5e7eb`
  - Sidebar active link: `var(--brand-600)` → `#c2410c` (orange accent, matching core nav)

## Step 4: Sidebar Navigation Labels
- **Commit**: `107889a`
- **File**: `templates/dashboard.html`
- **Changes**:
  - "Type Access" → "Equipment Type Access"
  - "Users" → "User Management"
  - "Equipment" (admin) → "Equipment Management"
  - "AI Rules" → "AI Specification Rules"
  - "Manager" section title → "Management"
  - Added "Quick Start Guide" link pointing to `/setup`

## Step 5: Toast Notifications Redesign
- **Commit**: `7d44e1d`
- **Files**: `static/css/styles.css`, `templates/dashboard.html`
- **Changes**:
  - Repositioned from bottom-right to bottom-center
  - Background: solid color → white with 95% opacity
  - Added SVG icon circles (green checkmark, red exclamation, etc.)
  - Dismiss timer: 3-4s → 6s with fade-out transition
  - Updated CSS `.toast-container` and `.toast-*` classes
  - Updated JS `showToast()` function with icon rendering

## Step 6: Login Page Colors
- **Commit**: `9fc96d8`
- **File**: `templates/login.html`
- **Changes**:
  - Button: `bg-orange-600` → `bg-gray-800`
  - Focus rings: `ring-orange-500` → `ring-gray-700`
  - Verify link: `text-orange-600` → `text-gray-700`

## Step 7: Form Placeholder + dashboard.js Cleanup
- **Commit**: `1e7be5d`
- **Files**: `templates/dashboard.html`, `static/js/dashboard.js`
- **Changes**:
  - Equipment description placeholder: "Include technical specs for AI recommendations" → "Optional description or specifications"
  - Updated `dashboard.js` fallback `showToast` for non-dashboard pages (bottom-center, 6s, charcoal/white style)
