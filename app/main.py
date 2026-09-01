"""GlowProof API.

Analysis and routine generation are deliberately SEPARATE endpoints so the
frontend can paint the scores the instant they land and generate the routine
underneath. Doing both in one request would stack two slow calls behind a
single spinner, which is how demos die.
"""
import uuid

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, perfectcorp, products, routine, xano

app = FastAPI(title="GlowProof")

# Hot cache for this process - avoids a round trip to Xano for the routine
# call that immediately follows an analyze in the normal flow. When Xano is
# not configured this is the ONLY store, same as before: fine for a demo,
# do not ship it. Selfies are never persisted either way - we hold analysis
# output, not the image.
_SESSIONS: dict = {}

MAX_UPLOAD = 10 * 1024 * 1024


@app.get("/api/health")
def health():
    return {
        "mode": config.mode_banner(),
        "skin_live": config.LIVE_SKIN,
        "llm_live": config.LIVE_LLM,
        "llm_provider": config.LLM_PROVIDER,
        "serpapi_live": bool(config.SERPAPI_KEY),
        "xano_live": config.LIVE_XANO,
        "concerns": config.CONCERNS,
    }


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty upload")
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, f"image is {len(data)/1e6:.1f}MB; limit is 10MB")

    try:
        result = perfectcorp.analyze(
            data,
            filename=file.filename or "selfie.jpg",
            content_type=file.content_type or "image/jpeg",
        )
    except perfectcorp.SkinAnalysisError as e:
        raise HTTPException(502, str(e)) from e

    if config.LIVE_XANO:
        try:
            row = xano.create_scan(result.to_dict())
            sid = str(row["id"])
        except requests.RequestException:
            # Xano hiccup shouldn't kill the demo - fall back to a local id,
            # same as running with no Xano configured at all.
            sid = uuid.uuid4().hex[:12]
    else:
        sid = uuid.uuid4().hex[:12]

    _SESSIONS[sid] = result
    return JSONResponse({"id": sid, **result.to_dict()})


@app.get("/api/scan/{sid}")
def get_scan(sid: str):
    """The analysis half of a session, without generating a routine.

    Used to reopen a past scan from /api/history - the routine is fetched
    separately (and lazily) via /api/routine/{sid}, same as a fresh scan.
    """
    analysis = _SESSIONS.get(sid)
    if analysis is not None:
        return JSONResponse({"id": sid, **analysis.to_dict()})
    if config.LIVE_XANO:
        row = xano.get_scan(sid)
        if row is not None:
            return JSONResponse({"id": sid, **row["analysis"]})
    raise HTTPException(404, "unknown session - re-run the scan")


@app.get("/api/routine/{sid}")
def get_routine(sid: str):
    analysis = _SESSIONS.get(sid)
    if analysis is None and config.LIVE_XANO:
        row = xano.get_scan(sid)
        if row is None:
            raise HTTPException(404, "unknown session - re-run the scan")
        if row.get("routine"):
            return JSONResponse(row["routine"])
        analysis = perfectcorp.Analysis.from_dict(row["analysis"])
        _SESSIONS[sid] = analysis
    if analysis is None:
        raise HTTPException(404, "unknown session - re-run the scan")

    out = routine.generate(analysis)
    # Claude names what is needed; SerpApi finds what to actually buy.
    rt = out["routine"]
    products.enrich(rt["am"])
    products.enrich(rt["pm"])

    if config.LIVE_XANO:
        try:
            xano.save_routine(sid, out)
        except requests.RequestException:
            pass  # already generated - a Xano hiccup here shouldn't fail the request

    return JSONResponse(out)


@app.get("/api/history")
def history(limit: int = 20):
    """Recent scans for the landing page's "recent scans" panel.

    Empty (not an error) when Xano isn't configured - the app has never
    needed history to function, this only adds to what already works."""
    if not config.LIVE_XANO:
        return JSONResponse({"live": False, "scans": []})
    try:
        rows = xano.list_scans(limit=limit)
    except requests.RequestException as e:
        return JSONResponse({"live": False, "scans": [], "error": str(e)})

    scans = [{
        "id": r["id"],
        "created_at": r.get("created_at"),
        "overall": (r.get("analysis") or {}).get("overall"),
        "priorities": (r.get("analysis") or {}).get("priorities", []),
        "has_routine": bool(r.get("routine")),
    } for r in rows]
    return JSONResponse({"live": True, "scans": scans})


@app.get("/")
def index():
    return FileResponse(config.STATIC / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC), name="static")
