"""Perfect Corp YouCam Skin Analysis client.

Flow (per https://yce.perfectcorp.com/document/index.html):
    POST /s2s/v2.0/file/skin-analysis   -> file_id + presigned PUT
    PUT  <presigned url>                 -> upload bytes
    POST /s2s/v2.0/task/skin-analysis    -> task_id
    GET  /s2s/v2.0/task/skin-analysis/{task_id} -> poll to success

Units are consumed only on task_status == "success", so failed experiments
are free. Successes are not: budget ~9 units per 1-4 SD concerns.
"""
import json
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from . import config

# ASSUMPTION FLAGGED: we treat ui_score as "higher is better" (100 = ideal
# skin for that concern). This matches the usual convention but has NOT been
# confirmed against a live response. Verify with the first real capture -
# if it is inverted, every piece of copy in the UI flips meaning.
SCORE_HIGHER_IS_BETTER = True

CONCERN_META = {
    "wrinkle": ("Fine lines", "Line depth around forehead, eyes and mouth"),
    "pore":    ("Pore visibility", "How visible pores are across the T-zone and cheeks"),
    "texture": ("Smoothness", "Evenness of the skin surface"),
    "acne":    ("Blemishes", "Active breakouts and spots"),
    "redness": ("Redness", "Visible irritation and flushing"),
    "moisture":("Hydration", "Surface moisture levels"),
    "oiliness":("Oil balance", "Sebum across the T-zone"),
    "radiance":("Radiance", "Light reflection and dullness"),
    "dark_circle": ("Dark circles", "Shadowing under the eyes"),
    "age_spot":("Even tone", "Pigmentation and sun spots"),
}


class SkinAnalysisError(RuntimeError):
    pass


@dataclass
class Concern:
    key: str
    label: str
    blurb: str
    ui_score: int
    raw_score: float
    mask_urls: list = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        return self.ui_score < 70 if SCORE_HIGHER_IS_BETTER else self.ui_score > 30


@dataclass
class Analysis:
    concerns: list
    latency_s: float
    live: bool
    raw: dict
    # Both documented but UNVERIFIED against a live response. Parsed
    # defensively and rendered only when present.
    overall: int = 0
    skin_age: int = 0

    def _derived_overall(self) -> int:
        """Mean of the concern scores, used when the API gives no overall.

        Flagged as derived in the payload so the UI can label it honestly
        rather than passing our arithmetic off as a vendor measurement.
        """
        if not self.concerns:
            return 0
        return int(round(sum(c.ui_score for c in self.concerns) / len(self.concerns)))

    @property
    def priorities(self) -> list:
        """The 2-3 concerns most worth acting on - the heart of the pitch."""
        ordered = sorted(self.concerns,
                         key=lambda c: c.ui_score,
                         reverse=not SCORE_HIGHER_IS_BETTER)
        return ordered[:3]

    @classmethod
    def from_dict(cls, d: dict) -> "Analysis":
        """Reconstruct from to_dict() output.

        Used when a scan is reloaded from Xano rather than held in the
        in-process session dict - routine.generate() and _fallback() both
        expect an Analysis (Concern objects with .key/.label/.blurb/.ui_score),
        not the plain dict Xano stores. `raw` is dropped: it was only ever
        needed to build to_dict() once, and is never read again.
        """
        concerns = [Concern(key=c["key"], label=c["label"], blurb=c["blurb"],
                            ui_score=c["ui_score"], raw_score=c["raw_score"],
                            mask_urls=c.get("mask_urls", []))
                   for c in d["concerns"]]
        return cls(concerns=concerns, latency_s=d.get("latency_s", 0.0),
                  live=d.get("live", False), raw={},
                  overall=d.get("overall", 0), skin_age=d.get("skin_age", 0))

    def to_dict(self) -> dict:
        return {
            "live": self.live,
            "latency_s": round(self.latency_s, 2),
            "overall": self.overall or self._derived_overall(),
            "overall_derived": not self.overall,
            "skin_age": self.skin_age,
            "concerns": [
                {"key": c.key, "label": c.label, "blurb": c.blurb,
                 "ui_score": c.ui_score, "raw_score": c.raw_score,
                 "mask_urls": c.mask_urls, "needs_attention": c.needs_attention}
                for c in self.concerns
            ],
            "priorities": [c.key for c in self.priorities],
        }


def _find_num(node, *keys):
    """Depth-first hunt for a numeric field. The exact nesting of overall
    score / skin age is not confirmed, so search rather than assume."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in keys and isinstance(v, (int, float)):
                return float(v)
            hit = _find_num(v, *keys)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = _find_num(v, *keys)
            if hit is not None:
                return hit
    return None


def _parse(body: dict, latency: float, live: bool) -> Analysis:
    try:
        output = body["data"]["results"]["output"]
    except (KeyError, TypeError) as e:
        raise SkinAnalysisError(f"unexpected response shape: {e} :: "
                                f"{json.dumps(body)[:300]}") from e
    # A real capture (2026-08-27) showed `output` also carries non-concern
    # housekeeping entries - "all" (the overall-score container), "skin_age",
    # "resize_image" (the resized working image) - each with ui_score 0.
    # Unfiltered, those three zero-score entries won `priorities` (lowest
    # score first) over every real concern, so the routine would have been
    # generated for "All" and "Resize Image" instead of the actual skin
    # measurements. Only keep entries for concerns we actually requested.
    concerns = []
    for o in output:
        key = o.get("type", "unknown")
        if key not in config.CONCERNS:
            continue
        label, blurb = CONCERN_META.get(key, (key.replace("_", " ").title(), ""))
        concerns.append(Concern(
            key=key, label=label, blurb=blurb,
            ui_score=int(round(o.get("ui_score") or 0)),
            raw_score=float(o.get("raw_score") or 0.0),
            mask_urls=[u for u in (o.get("mask_urls") or [])
                       if not str(u).startswith("synthetic://")],
        ))
    results = body.get("data", {}).get("results", {})
    overall = _find_num(results.get("all"), "score", "ui_score") or 0
    age = _find_num(results, "skin_age", "age") or 0
    return Analysis(concerns=concerns, latency_s=latency, live=live, raw=body,
                    overall=int(round(overall)), skin_age=int(round(age)))


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.PC_KEY}",
            "Content-Type": "application/json"}


def from_fixture(simulate_latency: float = 0.0) -> Analysis:
    body = json.loads((config.FIXTURES / "skin_analysis.json").read_text("utf-8"))
    if simulate_latency:
        time.sleep(simulate_latency)
    return _parse(body, latency=simulate_latency, live=False)


def analyze(image_bytes: bytes, filename: str, content_type: str) -> Analysis:
    """Run one live analysis. Consumes units on success."""
    if not config.LIVE_SKIN:
        return from_fixture()

    t0 = time.time()
    b = config.PC_BASE

    r = requests.post(f"{b}/s2s/v2.0/file/skin-analysis", headers=_headers(),
                      json={"files": [{"content_type": content_type,
                                       "file_name": filename,
                                       "file_size": len(image_bytes)}]},
                      timeout=30)
    if not r.ok:
        raise SkinAnalysisError(f"upload-url HTTP {r.status_code}: {r.text[:300]}")
    f = r.json()["data"]["files"][0]
    file_id, req = f["file_id"], f["requests"][0]

    put = requests.put(req["url"], data=image_bytes,
                       headers=req.get("headers", {}), timeout=120)
    if not put.ok:
        raise SkinAnalysisError(f"presigned PUT HTTP {put.status_code}")

    r = requests.post(f"{b}/s2s/v2.0/task/skin-analysis", headers=_headers(),
                      json={"src_file_id": file_id,
                            "dst_actions": config.CONCERNS,
                            "miniserver_args": {"enable_mask_overlay": True},
                            "format": "json"},
                      timeout=30)
    if not r.ok:
        raise SkinAnalysisError(f"task create HTTP {r.status_code}: {r.text[:300]}")
    task_id = r.json()["data"]["task_id"]

    for _ in range(60):
        time.sleep(2)
        r = requests.get(f"{b}/s2s/v2.0/task/skin-analysis/{task_id}",
                         headers=_headers(), timeout=30)
        if not r.ok:
            raise SkinAnalysisError(f"poll HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        status = body.get("data", {}).get("task_status")
        if status == "success":
            return _parse(body, latency=time.time() - t0, live=True)
        if status == "error":
            raise SkinAnalysisError(f"engine error (no units spent): "
                                    f"{json.dumps(body)[:300]}")
    raise SkinAnalysisError("timed out after 120s")


def feature_cost() -> dict:
    """Free call. Verifies auth and returns the unit price table."""
    r = requests.get(f"{config.PC_BASE}/s2s/v2.0/credit/feature-cost",
                     headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()
