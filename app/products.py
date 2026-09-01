"""Live product lookup via SerpApi Google Shopping.

GlowProof does not sell skincare. That is the point: a brand-owned skin quiz
maps your results onto that brand's own SKUs, so its recommendations are
structurally biased. We have no catalog to defend, so Claude names WHAT you
need (an ingredient and a product type) and this module finds WHICH real
product currently satisfies it, at a real price.

Falls back to a cached fixture when no SerpApi key is set, so the whole flow
still demos offline.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from . import config

ENDPOINT = "https://serpapi.com/search.json"
CACHE_PATH = config.FIXTURES / "products.json"

# Vercel's deployment filesystem is read-only outside /tmp, so writes there
# would raise. Locally this is the same path as CACHE_PATH, so behavior is
# unchanged for local dev; on Vercel, reads still fall back to the bundled
# seed file below when /tmp is empty (a fresh cold start), only writes are
# redirected. /tmp is per-instance and ephemeral - fine, this is a
# performance cache, never the only path to a result (see search() below).
_WRITE_PATH = Path("/tmp/products.json") if os.environ.get("VERCEL") else CACHE_PATH

# Cheap in-process cache. A demo re-runs the same few queries constantly and
# the free SerpApi tier is 100 searches/month.
_MEM: dict = {}


def _cache() -> dict:
    for p in (_WRITE_PATH, CACHE_PATH):
        if p.exists():
            try:
                return json.loads(p.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
    return {}


def _save_cache(data: dict) -> None:
    try:
        _WRITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _WRITE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # best-effort cache; a write failure must never break a live lookup


def _clean_price(item: dict):
    p = item.get("extracted_price")
    if isinstance(p, (int, float)):
        return round(float(p), 2)
    m = re.search(r"[\d.]+", str(item.get("price", "")))
    return float(m.group()) if m else None


def _shape(item: dict) -> dict:
    return {
        "title": item.get("title", "").strip(),
        "price": _clean_price(item),
        "currency": "USD",
        "source": item.get("source") or item.get("store") or "",
        "link": item.get("product_link") or item.get("link"),
        "thumbnail": item.get("thumbnail"),
        "rating": item.get("rating"),
        "reviews": item.get("reviews"),
    }


def search(query: str, limit: int = 3) -> dict:
    """Find real buyable products for a query. Never raises."""
    key = query.strip().lower()
    if key in _MEM:
        return _MEM[key]

    disk = _cache()
    if not config.SERPAPI_KEY:
        hit = disk.get(key)
        return {"query": query, "live": False,
                "results": hit["results"] if hit else [],
                "note": "no SerpApi key - cached results only"}

    t0 = time.time()
    try:
        r = requests.get(ENDPOINT, timeout=20, params={
            "engine": "google_shopping",
            "q": query,
            "api_key": config.SERPAPI_KEY,
            "num": max(limit * 2, 10),
            "hl": "en",
            "gl": "us",
        })
        r.raise_for_status()
        body = r.json()
    except (requests.RequestException, ValueError) as e:
        hit = disk.get(key)
        return {"query": query, "live": False,
                "results": hit["results"] if hit else [],
                "note": f"lookup failed: {e}"}

    if body.get("error"):
        return {"query": query, "live": False, "results": [],
                "note": str(body["error"])}

    items = body.get("shopping_results") or []
    shaped = [_shape(i) for i in items if i.get("title")][:limit]
    out = {"query": query, "live": True, "results": shaped,
           "latency_s": round(time.time() - t0, 2)}

    _MEM[key] = out
    disk[key] = {"results": shaped, "cached_at": time.time()}
    _save_cache(disk)
    return out


def build_query(product_type: str, ingredient: str) -> str:
    """Turn Claude's recommendation into a shopping query."""
    pt = (product_type or "").strip()
    ing = " ".join((ingredient or "").split()[:4]).strip()
    # Don't repeat the ingredient when the product type already names it
    # ("ceramides ceramide moisturiser" is a worse search than "ceramide
    # moisturiser").
    if ing and ing.rstrip("s").lower() in pt.lower():
        ing = ""
    base = f"{ing} {pt}".strip() if ing else pt
    return f"{base} skincare".strip()


def enrich(steps: list) -> list:
    """Attach a real product to each routine step that names one.

    Searches run in PARALLEL. A single SerpApi call measured ~9.6s, and a
    routine has up to six product steps - done sequentially that is a minute
    of dead air. Fanning them out keeps the whole enrichment at roughly the
    cost of the slowest single lookup.
    """
    wanted = []
    for s in steps:
        pt = (s.get("product_type") or "").strip()
        if not pt:
            s["product"] = None
            s["alternatives"] = []
            continue
        s["query"] = build_query(pt, s.get("key_ingredient", ""))
        wanted.append(s)

    if not wanted:
        return steps

    # Dedupe first - AM and PM routinely share a cleanser and a moisturiser,
    # and every duplicate is a wasted search against a 100/month free tier.
    uniq = list({s["query"] for s in wanted})
    with ThreadPoolExecutor(max_workers=min(8, len(uniq))) as pool:
        found = dict(zip(uniq, pool.map(lambda q: search(q, limit=3), uniq)))

    for s in wanted:
        f = found[s["query"]]
        s["product"] = f["results"][0] if f["results"] else None
        s["alternatives"] = f["results"][1:]
        s["product_live"] = f["live"]
    return steps
