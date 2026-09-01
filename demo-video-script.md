# GlowProof — demo video script

Target length: **2:45** (satisfies Perfect Corp's 1–3 min cap and Xano's 2–4
min ask in one cut — see VERIFIED.md "Video length"). One take, screen
recording + voiceover. Timestamps are cues, not hard marks — pace to the
screen, not the clock.

Record with `GLOWPROOF_FORCE_FIXTURE=1` unset for the one real capture
(see README "Modes"), or on fixtures if the real capture isn't ready yet —
either is honest as long as the on-screen mode badge is visible and never
covered by a window/cursor. The badge saying "sample data" openly is better
than a real badge implying a claim that isn't backed yet.

---

## 0:00–0:15 — Cold open: the problem

**Screen:** blank, or a quick montage of 2–3 real brand skin-quiz sites
(no need to name them on camera).

**VO:**
> Every brand's skin quiz asks you five questions, then maps your answers
> onto that brand's own shelf. That's not malicious — it's just what
> happens when the company diagnosing you also sells the cure.

## 0:15–0:35 — The pitch

**Screen:** GlowProof landing page (`v-landing`), full width, mode badge
clearly visible top-right.

**VO:**
> GlowProof sells nothing. It measures your skin with a real AI scan
> from Perfect Corp, then goes looking for what actually fits — on the
> open market, wherever it's sold. That's a claim only a company with no
> skincare line to defend can make.

**Action:** click "Scan my skin" (or "Upload a photo" if webcam is
unreliable on the recording machine).

## 0:35–1:05 — The scan

**Screen:** capture view → working view (scan line animation, staged
progress: "Uploading over TLS" → "Locating facial landmarks" → "Measuring
each concern region" → "Scoring against the reference set").

**VO:**
> One photo goes to Perfect Corp's skin analysis API — not a filter, an
> actual measurement across wrinkles, pores, texture, and acne. The photo
> itself is never stored — we only keep the scores.

**Action:** let the staged progress play out fully — this is a natural
beat, don't rush it in editing.

## 1:05–1:35 — The reveal

**Screen:** results view. Overlay auto-plays through each concern, settles
on the worst one. Overall score counts up.

**VO:**
> Here's the baseline: an overall score, a plain-language read on each
> concern, and a visual overlay showing exactly where it was measured.
> No jargon, no diagnosis — just numbers you can act on.

**Action:** click one or two concern cards manually to show the overlay
responds to interaction, not just the auto-play.

## 1:35–2:05 — The routine + real products

**Screen:** scroll to the consultation/routine band. AM/PM steps populate,
each with a real product card (thumbnail, price, source).

**VO:**
> Claude reads those scores and writes a routine — but it only ever names
> a product *type* and an active ingredient, never a brand. A separate
> lookup against live Google Shopping data finds the actual product that
> satisfies it, at today's real price. Splitting "what you need" from
> "which product" is what keeps this from just becoming another shelf.

**Action:** hover/click one "buy" product link to show it's a real,
priced listing — don't actually navigate away.

## 2:05–2:30 — Xano: it remembers

**Screen:** navigate back to the landing page (or open a fresh tab to
`localhost:8000`). The "Recent scans" panel is visible with at least one
past scan. Click into it — results repopulate instantly from history.

**VO:**
> And unlike a one-off quiz result, this doesn't disappear when you close
> the tab. Every scan is persisted in Xano — so you can come back days
> later, pull up your baseline, and actually track whether anything
> changed.

**Action:** this is the moment that's specifically for the Xano judges —
don't rush it, let the click-through play out fully so it's obviously a
real round trip, not a mockup.

## 2:30–2:45 — Close

**Screen:** back to landing page, or the disclaimer line on the results
band.

**VO:**
> GlowProof: measured, not sold to. This is cosmetic guidance, not a
> diagnosis — if something's changing or painful, see a clinician. Thanks
> for watching.

---

## Shot list checklist

- [ ] Mode badge visible and legible in every screen segment
- [ ] At least one full concern-overlay cycle shown uninterrupted
- [ ] At least one real product card with visible price + source
- [ ] Recent-scans panel click-through shown in full (Xano beat)
- [ ] Disclaimer/claims-discipline line spoken or shown on screen
- [ ] No cursor covering the badge, scores, or price at the moment they're
      mentioned in the VO

## Submission notes (write-up, not video)

Both tracks want a short write-up alongside the video:

- **Perfect Corp:** "consumer or retail value" — lead with the bias
  argument from the README's "The position" section.
- **Xano:** the track is framed as "rebuild a SaaS tool you hate." The
  honest angle here: GlowProof replaces the *pattern* of a paid,
  brand-biased skin-quiz backend with a neutral one — Xano holds nothing
  but scan history, no product catalog, no upsell logic. Say plainly what
  it replaced (nothing pre-existing, since GlowProof is novel) and why
  Xano specifically (real persistence without hand-rolling auth/hosting
  under a one-week deadline).
