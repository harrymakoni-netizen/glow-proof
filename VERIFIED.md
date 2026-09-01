# GlowProof — Verified Hackathon Facts
Source: https://api-cloud-ai-hackathon-2026.devpost.com/ (checked 2026-08-21)

## Hard constraints
- **Deadline: Thursday, Sep 3, 2026 @ 10:00 AM PT.** "Projects submitted after
  10:00 AM PST on Thursday, September 3, 2026, will not be accepted."
- Online window: Aug 17 - Sep 3. In person + awards: Sep 2-3, Santa Clara CC.
- Teams 1-5. "Teams with over 5 members are not eligible to win anything."
- Multi-track CONFIRMED: "Teams can solve as many 'Challenges' as desired
  (zero, one, or multiple)."
- Two judging rounds, both Sep 3, 10:00-12:00 PT. Round 1 = Overall
  (Progress / Concept / Feasibility). Round 2 = Sponsor. "The sponsors will
  choose their own prize and choose their own prize winners."
- Top 5 (Round 1) pitch on the Main Stage.
- Demo video for the Overall round: "Recommended ... (This is NOT Required)."
  But every sponsor track requires one.

## Prize reality check
| Track | 1st place | Actual cash |
|---|---|---|
| **Overall** | Amazon Echos (up to 5) + 2027 all-access passes + email blast | **$0 cash** |
| SerpApi | $1,000 cash + $1,000 credits | $1,000 |
| Perfect Corp | $1,500 | $1,500 |
| Xano | $1,000 cash + $500 credit | $1,000 |
| name.com | $1,500 Amazon gift card | $0 (GC) |
| Nutrient | $750 Visa GC + $250 credits | $0 (GC) |
| Foxit | $700 | $700 |
| Doctavian | $500 cash + $150 subscription | $500 |

The Overall prize is "$12,500 in cash value" — hardware and conference
passes, NOT cash. The cash is in the sponsor tracks.

## Sponsor judges sit on the panel
- Wayne Liu — Chief Growth Officer @ Perfect Corp
- Alaa Abdulridha — Engineering Director @ SerpApi
- Nick Winder — Core Staff Software Engineer @ Nutrient
- Katie Wokasch — Head of Product Engineering @ name.com

## Perfect Corp track (anchor)
- Prize: 1st $1,500 / 2nd $1,000. Contact: valerie_torres@perfectcorp.com
- Redeem code URL: https://yce.perfectcorp.com/api-console/en/redeem-code/
- Requirements (verbatim):
  - "Must integrate at least 1 Perfect Corp API and demonstrate clear consumer
    or retail value"
  - "Project page with short write-up & screenshots"
  - "Demo video (1-3 minutes) showing the experience end-to-end"
  - "Must participate in an exit interview if chosen as winner"

## Xano track (missed by the original research)
- "Rebuild a SaaS Tool You Hate" — $1,000 + $500 credit / $500 + $500 credit
- "Your project must use Xano as the backend in a meaningful way."
- Free Essential instance + static hosting + CLI/MCP + a Claude Code
  onboarding prompt. Signup: https://go.xano.co/devpost-challenge
  Coupon: M_Xano_PER_100_2608_1_DevpostHackathon
- Submit asks: what software you replaced, why, which AI tools, how long.
- Demo video 2-4 min.

## SerpApi track
- Largest sponsor prize ($3,000 pool). "Build an innovative AI application
  using one or more SerpApi APIs ... Judging will consider originality,
  technical execution, SerpApi integration, usability, and potential impact."

## name.com — deliberately skipped
Their rubric punishes shallow use: "Judges favor integrations that combine
multiple endpoints (search plus registration plus DNS, for example) over a
single surface-level call."

## Video length
Perfect Corp caps at 3 min; Xano wants 2-4. **One video at 2:00-3:00
satisfies both.** Target 2:45.

## Still unverified
- Perfect Corp API host, endpoint paths, MCP package name, per-call unit cost.
  Verify against official docs at setup. Unit cost gates dev iteration budget.
- Whether pre-Aug-17 code is allowed (no rule found either way).

---

# API status - CONFIRMED WORKING (2026-08-22)

## Auth
- V2 Bearer. `Authorization: Bearer <key>` against
  `https://yce-api-01.makeupar.com`.
- Both hosts are live and equivalent: `yce-api-01.makeupar.com` and
  `yce-api-01.perfectcorp.com` return identical responses.
- The pasted key had a trailing "." (sentence punctuation) which produced
  `401 InvalidApiKey`. Header format is irrelevant - Bearer, raw, and
  x-api-key all fail identically on a bad value, so a 401 means the KEY,
  not the scheme.

## Endpoints - all verified against the live API
| Call | Result |
|---|---|
| `GET  /s2s/v2.0/credit/feature-cost` | 200, returns 20 SKUs |
| `POST /s2s/v2.0/file/skin-analysis` | 200, returns file_id + presigned S3 PUT |
| `PUT  <presigned url>` | 200 |
| `POST /s2s/v2.0/task/skin-analysis` | 200, returns task_id |
| `GET  /s2s/v2.0/task/skin-analysis/{id}` | 200, task_status running -> error |
| `GET  /s2s/v2.0/credit/balance` (and /credit, /credit/summary) | 404 - no such endpoint |

## Skin analysis IS provisioned
A faceless probe image was accepted, queued, ran, and failed with an ENGINE
error, not a permission error:

    {"data": {"error": "[DLQ] Max retries exhausted. Last error: list index
     out of range", "results": null, "task_status": "error"}}

That is face detection failing on a blank image. Units are consumed only on
`success`, so the probe cost nothing.

## Still unknown
- **Unit cost of skin analysis.** `feature-cost` lists only the YouCam photo
  editing / hair try-on SKUs (Photo Enhance, Object Removal, Hair Style VTO,
  etc.) at 1-2 units each. Skin analysis is NOT in that list despite being
  provisioned - so the documented "9 units for 1-4 SD concerns" is still
  unconfirmed for this account. Measure it empirically: no balance endpoint
  exists, so the only way is to watch the console after a successful run.
- **Successful latency.** The failed probe took ~36s, but that was a DLQ
  retry path and is not representative.
- **Score direction** and **mask_urls shape** - need one successful capture.

## What is needed to close these
One real front-facing selfie. Everything else is wired.

---

# Real capture - CONFIRMED (2026-08-27)

Two live captures ran (same photo, submitted twice - the second was not a
separate deliberate spend, just a duplicate request; both consumed a unit
since Perfect Corp only credits on success).

## Bug found, not just an assumption confirmed
`output` in the response carries non-concern housekeeping entries alongside
the real concerns: `all` (the overall-score container), `skin_age`, and
`resize_image` (the resized working image) - each with `ui_score: 0`. The
parser in `perfectcorp._parse()` was treating every entry in `output` as a
concern, so those three zero-score entries **won `priorities`** (lowest
score sorts first) over every real measurement - the routine would have
been generated for concerns named "All" and "Resize Image" instead of pore/
wrinkle/texture/acne. Fixed by filtering `output` to `config.CONCERNS`
before building the concern list. This is the kind of bug that only a real
capture surfaces - fixtures never had these extra entries.

## Real numbers (post-fix)
| concern | ui_score | raw_score |
|---|---|---|
| texture | 95 | 97.39 |
| acne    | 96 | 97.86 |
| wrinkle | 81 | 90.67 |
| pore    | 73 | 61.89 |

Derived overall (mean of the 4, now that the fix excludes the bogus zeros):
**86**, not the 49 the unfiltered bug produced.

## Score direction - provisionally CONFIRMED
`SCORE_HIGHER_IS_BETTER = True` in `perfectcorp.py` is consistent with this
result: scores cluster high (73-96) with no `needs_attention` flags tripped,
plausible for skin without severe concerns. Not proof from Perfect Corp's
own docs, but no evidence against it either, and the alternative (lower is
better) would mean the same skin scored 95-96/100 *bad* on texture and acne
- implausible. Treating as confirmed unless contradicted by a future capture
with an actual visible concern (e.g. a deliberately blemished or wrinkled
test photo) that also scores high.

## Still unknown
- **`skin_age`**: consistently `0` across both captures (both the top-level
  search in `_find_num` and the bogus `output` entry). Either not returned
  by this endpoint at all, or under a field name not yet tried. Not a bug in
  the app - the UI already treats `0` as "not present" and shows "—"
  ([app.js](static/app.js) `renderResults`) - just an open question, not
  worth another live spend to chase given the deadline.
- **Real unit cost**: still not directly observable (no balance endpoint -
  see above). Two units were consumed by this session; watch the Perfect
  Corp console balance before/after the next real capture to get an actual
  number.
- **Mask URLs**: confirmed real - presigned S3 URLs (`yce-us.s3-accelerate
  .amazonaws.com`), **2-hour expiry** (`X-Amz-Expires=7200`). A scan viewed
  from history more than 2 hours after capture would have dead mask links -
  not currently a problem since the app never shows the mask/photo panel for
  past scans at all ([static/styles.css](static/styles.css) `.split.no-photo`
  hides it), but worth remembering if that ever changes.
- **Real latency**: 8.89s for a successful live analysis (vs. ~36s measured
  earlier, which was a DLQ retry path on a failed probe - not representative
  of a real success).

---

# SerpApi - CONFIRMED WORKING (2026-08-22)

- Plan: **Free, 250 searches/month** (not the 100 assumed earlier). 249 left.
- `engine=google_shopping` returns real listings with real prices from real
  retailers (The Ordinary $6.00, CeraVe at Target/Walmart, Ulta).
- **Latency ~9.6s per search.** This is the important number. A routine has
  up to 6 product steps; sequential lookups would be ~60s of dead air.
  `products.enrich()` now fans them out with a ThreadPoolExecutor AND dedupes
  by query (AM/PM share a cleanser and moisturiser), so 6 steps = 4 unique
  searches = 14.5s wall clock.
- Results are cached to `fixtures/products.json` on disk and in memory, so
  repeated demo runs cost zero searches.

## Known limitation
`product_link` is a Google Shopping redirect
(`google.com/search?ibp=oshop&...`), NOT a direct retailer product page.
Clicking "buy" lands on Google Shopping, not on Target. Acceptable for the
demo; worth a sentence in the write-up rather than letting a judge discover
it. Fixing it properly would need the separate `google_product` engine per
item, which multiplies both latency and quota.

---

# Gemini - CONFIRMED WORKING (2026-08-22)

Key authenticates. `gemini-2.5-pro` and `gemini-2.5-flash` both 404 with
"no longer available to new users" - the docs and most guides are stale.

## Model reliability, measured (3 calls each, same prompt + schema)
| model | success | avg latency |
|---|---|---|
| gemini-3.7-flash | **1/3** | 6.2s | congested, repeated 503 |
| gemini-3.6-flash | 3/3 | 14.1s | reliable but slow |
| gemini-3.5-flash | 3/3 | 8.6s | solid backup |
| gemini-2.5-flash | **0/3** | - | 404, retired |
| **gemini-3.5-flash-lite** | **3/3** | **2.8s** | chosen |

Chose `gemini-3.5-flash-lite` on reliability and speed, not on version
number. This is a constrained formatting task against a fixed schema, so the
lite tier loses nothing that matters, and 2.8s vs 14.1s is the difference
between a smooth demo and dead air. `gemini-3.5-flash` is the fallback if
lite ever degrades.

## Free tier 503s are real
Observed: a call succeeds, the next two return "This model is currently
experiencing high demand." `routine.generate()` now retries transient
failures (503/429/UNAVAILABLE/timeout) up to 3 times with escalating backoff
before degrading to the canned routine.

## Personalisation verified
Two opposite profiles, same code path:
- oily + acne -> salicylic acid cleanser, niacinamide, oil-free gel
  moisturiser, fluid mineral sunscreen
- dry + lined -> glycerin cleanser, hyaluronic acid, ceramide barrier cream,
  peptide serum, rich night cream

The canned fallback returned near-identical text for both. This is the gap
that closes.
