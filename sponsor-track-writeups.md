# Sponsor track write-ups

Copy the relevant section into each track's submission field on Devpost.
Both are written to satisfy the exact requirements listed in VERIFIED.md.

---

## Perfect Corp track

**Requirement (verbatim from the challenge page):** "Must integrate at least
1 Perfect Corp API and demonstrate clear consumer or retail value."

### Which API, and how

GlowProof integrates the **YouCam Skin Analysis API** (S2S v2.0) as the
foundation of the entire product, not a bolted-on feature. The flow:
presigned file upload → task creation against `dst_actions` for four SD-tier
concerns (wrinkle, pore, texture, acne) → poll to completion → parsed into
per-concern scores, raw values, and mask overlay URLs. This is the *only*
source of truth in the product for what a person's skin actually needs —
nothing downstream (the routine, the product recommendations) is allowed to
override or second-guess it.

### The consumer/retail value

Every brand's skin quiz maps your answers onto that brand's own shelf —
structural bias, not malice, but bias all the same. GlowProof's entire
pitch only works *because* it has no shelf: Perfect Corp's measurement is
the trusted, independent input that a downstream LLM (Claude/Gemini) turns
into a routine naming only a product **type** and **active ingredient** —
never a brand — and a separate live product search (SerpApi) finds a real,
currently-priced item to satisfy it. Perfect Corp's data is what makes the
"we sell nothing" claim credible rather than just a slogan: the measurement
is real, objective, and independently verifiable, so the advice built on
top of it can be trusted the way a self-reported quiz can't be.

### What a judge will see in the demo

A live capture (2026-08-27) surfaced a real defect in how the response was
being parsed — see `VERIFIED.md` "Real capture" for the full account. That
capture is also what confirmed real latency (8.89s), real mask overlay URLs
(signed S3 links), and the plausible score direction. This wasn't treated
as a one-off test; it's documented as evidence the integration was
validated against the live API, not just fixtures.

### Format notes

Demo video: 2:45, well within the 1–3 minute cap (script: `demo-video-script.md`).
Screenshots: pull from the results view (score reveal + mask overlay) and
the routine/product band — both are the money shots for this track.

---

## Xano track

**Requirement (verbatim):** "Rebuild a SaaS Tool You Hate... your project
must use Xano as the backend in a meaningful way." Submission asks: what
software was replaced, why, which AI tools were used, and how long it took.

### What was replaced, and why

GlowProof doesn't rebuild a single named SaaS product — it replaces a
*pattern*: the paid, brand-operated skin-quiz backend that every skincare
company runs to power its own quiz funnel. That pattern is the thing we
"hate" here, and it's the entire premise of the product: a quiz backend
that maps your answers onto its owner's own catalog isn't a neutral
measurement tool, it's a sales funnel wearing a diagnostic's coat. Xano
backs the *opposite* of that: a persistence layer with no product catalog,
no upsell logic, and no brand relationship to protect — it holds exactly
one thing, scan history, and nothing else.

### How it's used — meaningfully, not as a checkbox

Xano isn't a bolted-on database call. It's a hand-written XanoScript API
(not the default per-table REST CRUD), built and version-controlled in its
own pulled workspace (`xano-workspace/`), with schema changes going through
Xano's own sandbox → review → promote safety flow rather than a direct
write. It replaced an in-memory Python dictionary that lost every session
on restart — with Xano, `/api/routine/{id}` is a real, bookmarkable,
shareable link, and a "Recent scans" panel on the landing page lets someone
revisit a past baseline and (eventually) compare against it. That's a
genuine feature unlock, not integration theater.

### AI tools used

Claude Code (Anthropic) for the full build — architecture, the FastAPI
backend, the XanoScript table/API definitions, the Vercel deployment fix,
and this documentation. Claude (via the Anthropic SDK) and Google Gemini
are also *runtime* dependencies of the product itself (routine generation).

### How long

Built across roughly one week under the hackathon's own timeline (see
`VERIFIED.md`), with the Xano integration itself — CLI setup, schema design,
sandbox push, and the sandbox → review → promote flow — completed in a
single focused session once the account was live.

### Format notes

Demo video: 2:45 fits the 2–4 minute ask (same script as Perfect Corp — see
`demo-video-script.md`, which already includes a dedicated "Xano: it
remembers" beat at 2:05–2:30 timed specifically for this track's judges).
