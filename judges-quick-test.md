# 2-minute test guide for judges

Live URL: **https://glow-proof.vercel.app** — deployed in fixture mode, so
nothing here spends real API credit or requires a webcam/real photo. Every
score, mask, and product shown is real *code*, running against a real
(cached) response shape — only the specific upstream call is swapped for a
fixture.

## The four things worth seeing (~2 minutes total)

### 1. Upload → measured scores (30s)
Click **"Upload a photo"** on the landing page and pick any image file.
Watch the staged progress ("Uploading over TLS" → "Locating facial
landmarks" → ...) — this isn't decorative pacing, it mirrors the real
Perfect Corp call's actual phases. Land on the results view: an overall
score, a per-concern breakdown, and a colored region overlay that auto-plays
once through every concern before settling on the worst one.

**What to notice:** click two or three concern cards directly — the overlay
responds to your click, it's not just a fixed animation.

### 2. The routine never names a brand (30s)
Scroll to "Your routine." Each step names an action, a product *type*
("niacinamide serum"), and why — never a brand. That's enforced in the
system prompt (`app/routine.py`), not just a formatting choice.

**What to notice:** the product card attached to each step (thumbnail,
price, source store) is a *separate* system finding that product — the
LLM never picked it. That split is the core of the whole pitch.

### 3. Recent scans — real persistence (30s)
Go back to the landing page. Below the claims list, a "Recent scans" panel
lists past scans with a score and date. Click one — it reopens instantly
from Xano, not from your browser's local state (open it in a fresh
incognito window if you want to confirm that directly).

**What to notice:** this is a real database round trip, not a mock —
`api/history` and `api/scan/{id}` in the source both hit a live Xano API.

### 4. The disclaimer is permanent, not a footer (10s)
On the results view, note the cosmetic-guidance language throughout — this
is enforced in the system prompt (`routine.py`'s `SYSTEM` constant forbids
diagnosis language, disease names, and unhedged efficacy claims) and is
visible UI copy, not a dismissible banner.

## If you want to go deeper

- `/api/health` on the live URL shows exactly which integrations are live
  vs. fixture at that moment — no guessing about what's "real."
- `glowproof-technical-architecture.pdf` (submitted alongside this) covers
  the full system design, the Xano persistence architecture, the Vercel
  deployment, and a real bug the team caught during one deliberate live
  Perfect Corp capture — cited there as the argument for gating real calls
  behind a fixture flag rather than iterating against the live API.
- `VERIFIED.md` in the GitHub repo timestamps every claim above against a
  real, dated API response — nothing in this guide is asserted without a
  receipt somewhere in that file.
