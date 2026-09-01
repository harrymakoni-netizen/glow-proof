# GlowProof

By **HJM Technologies**. Turns one selfie into measured skin scores and a
personalized red-light + skincare routine, then finds the real products to
buy — from anywhere on the open market.

Built for the DevNetwork [API + Cloud + AI] Hackathon 2026, deadline
**Sep 3, 2026 @ 10:00 AM PT** ([VERIFIED.md](VERIFIED.md)).

## The position

Every brand's skin quiz maps your results onto that brand's own shelf. That
bias is structural, not malicious — it's what happens when the company
diagnosing you also sells the cure.

GlowProof sells nothing. It measures, then searches the open market. That is
a claim only a company without a skincare line can make, and it's the reason
the recommendation is worth trusting.

## Run it

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000 --reload
```

http://localhost:8000. Runs with no keys at all — fixtures and a canned
routine — and the badge at the top always says which mode you're in.

## Modes

| Env | Effect |
|---|---|
| `GLOWPROOF_FORCE_FIXTURE=1` | **currently set.** Fixtures even though the key works |
| unset / `0` | real Perfect Corp call — **spends units** |
| `ANTHROPIC_API_KEY` set | routine via Claude (wins if both set) |
| `GEMINI_API_KEY` set | routine via Gemini — free tier, no card |
| neither set | canned routine from `routine._fallback` |
| no `SERPAPI_API_KEY` | product lookup returns cached results, or nothing |
| `XANO_INSTANCE_BASE_URL` + `XANO_API_GROUP_BASE` set | scans persist in Xano — bookmarkable `/routine/{id}`, past scans on the landing page |
| neither set | sessions live only in memory for the life of the process, same as before |

`GLOWPROOF_FORCE_FIXTURE=1` is deliberately on. The Perfect Corp key is live,
skin-analysis unit cost is still unmeasured, and there is no balance endpoint
— so a page refresh must not be able to silently spend credit. Flip it off
only for a deliberate real capture.

## Pipeline

```
selfie ──► Perfect Corp Skin Analysis ──► scores + mask overlays
                                            │
                                            ├──────────► Xano
                                            │            one row per scan:
                                            │            analysis, then routine
                                            ▼            merged in once generated
                              Claude (structured output)
                              names WHAT: product type + active ingredient
                              never a brand
                                            │
                                            ▼
                              SerpApi Google Shopping
                              finds WHICH: real listing, live price
```

Splitting "what" from "which" is what keeps the advice unbiased and stops
the model inventing products that don't exist. Xano is pure persistence, not
a decision point — same reason: nothing about the recommendation should
depend on where the data happens to be stored.

## Layout

```
app/config.py        env, mode detection, concern list
app/perfectcorp.py   upload -> task -> poll, fixture fallback, parsing
app/routine.py       Claude structured output -> Routine schema + fallback
app/products.py      SerpApi lookup, disk + memory cache
app/xano.py          scan persistence: create/get/save_routine/list
app/main.py          /api/health, /api/analyze, /api/scan/{id},
                      /api/routine/{id}, /api/history
static/              no-build frontend
scripts/preflight.py free auth check, then one real analysis -> fixture
```

### Xano — what it's actually for

Sessions used to live only in an in-memory dict: gone on restart, no way to
revisit a result. Xano replaces that with one `scans` table (`analysis` JSON,
`routine` JSON, nullable until generated). `/api/analyze` writes the row;
`/api/routine/{id}` reads it, generates once, writes the routine back;
`/api/history` lists recent rows for the landing page's "Recent scans" panel.
Falls back to the in-memory dict automatically when Xano isn't configured, or
if a Xano call fails mid-demo — same mode-detection pattern as the Perfect
Corp / LLM / SerpApi switches above. Selfies are still never sent anywhere
for storage, Xano included — only the analysis output.

**Live and wired up.** Workspace: Harry Workspace #1, instance
`x54j-fyug-haz1`. Built as hand-written XanoScript rather than Xano's default
per-table REST CRUD, because the `save_routine` merge and the not-a-404
`get` (see below) needed exact control:

- `./xano-workspace/` — the workspace pulled locally via the Xano CLI, under
  its own git repo. `table/scans.xs` is the table; `api/scans/*.xs` are the
  four endpoints (`create` POST, `get` GET, `save_routine` POST, `list` GET).
  Edit here and `xano sandbox push` + `xano sandbox review` (promote in the
  browser — Xano's own safety gate, no CLI command for it) to change the
  live schema.
- `app/xano.py` calls these by name (`/create`, `/get?id=`, `/save_routine`,
  `/list`), not generic `/scans/{id}` REST paths. One quirk worth knowing:
  `get` returns HTTP 200 with a `null` body for a missing id, not a 404 -
  `get_scan()` checks the body, not the status code.
- No auth on these endpoints (analysis data only, no PII) - `.env`'s
  `XANO_PERSONAL_ACCESS_TOKEN` is deliberately blank.
- Verified end-to-end: analyze → routine (written to Xano) → killed the
  server → fresh process → `/api/scan/{id}` and `/api/routine/{id}` both
  still returned the same data, straight from Xano, no in-memory hit.

To point at a different workspace: `xano workspace pull -d ./xano-workspace
-w <id>`, adjust the `.xs` files, push, then update `XANO_INSTANCE_BASE_URL`
/ `XANO_API_GROUP_BASE` in `.env` from the new API group's `canonical` id
(`https://<instance>.xano.io` + `/api:<canonical>`).

`/api/analyze` and `/api/routine` are separate on purpose: scores paint the
instant they land, routine generates underneath. One endpoint would stack two
slow calls behind one spinner.

## Status

Working: auth verified, all endpoints confirmed live, skin analysis
provisioned, full flow runs end to end.

Open:

- [x] ~~One real selfie~~ — done 2026-08-27. Found and fixed a real bug in
      the process (see VERIFIED.md "Real capture"): the parser was treating
      Perfect Corp's non-concern housekeeping entries as concerns, which
      would have silently generated a routine for fake concerns named "All"
      and "Resize Image". Latency 8.89s, mask URLs are real S3 links
      (2h expiry). Unit cost and `skin_age` still open - see VERIFIED.md.
- [x] ~~`SCORE_HIGHER_IS_BETTER`~~ — provisionally confirmed by the real
      capture (high scores, no false "needs attention" trips). Not proven
      from Perfect Corp's own docs, but no evidence against it - see
      VERIFIED.md for the reasoning.
- [x] ~~SerpApi key~~ — live, 250 searches/month, cached to disk
- [x] ~~LLM key~~ — Gemini live on `gemini-3.5-flash-lite` (2.8s, 3/3 reliable).
      Model chosen by measured reliability, not version number — see VERIFIED.md.
- [x] ~~Xano decision~~ — live: scans persist in the real workspace, verified
      end-to-end including a fresh-process restart (see Xano section above).
- [x] ~~Demo video script~~ — [demo-video-script.md](demo-video-script.md),
      2:45, beat-by-beat with VO + on-screen cues. Recording it is still open.

## Claims discipline

`routine.py`'s system prompt forbids diagnosis, disease names, brand names,
and promised results, and requires hedged efficacy language. The disclaimer
is permanent UI, not a footer. Several judges come from privacy- and
compliance-heavy companies.
