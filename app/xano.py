"""Xano-backed persistence for scan sessions.

Sessions used to live only in main.py's in-memory dict, which loses every
scan on a restart and gives no way to revisit a past result - the module
docstring there says as much ("Fine for a hackathon demo; do not ship
this"). Xano is the persistence layer instead: one row per scan in a single
`scans` table, analysis written on POST /api/analyze, routine merged in on
GET /api/routine/{id}. That single row is also what /api/history lists.

This is a hand-written XanoScript API (workspace pulled to ./xano-workspace,
edited, pushed via `xano sandbox push`, promoted via `xano sandbox review`),
not Xano's default per-table REST CRUD - the endpoint names below (create /
get / save_routine / list) come from api/scans/*.xs in that folder, and were
verified live against the real workspace before this client was written to
match. Notably `get` returns HTTP 200 with a `null` body for a missing id,
not a 404 - Xano's auto-generated GET-by-id endpoint would 404, but this
custom one doesn't, so the check below is on the body, not the status code.

Selfies themselves are still never sent here or anywhere else - only the
analysis output (see perfectcorp.py / Analysis.to_dict). Falls back to
nothing when unconfigured; main.py switches to the in-memory dict in that
case, same mode-detection pattern as the rest of this app (config.py).
"""
import requests

from . import config

_BASE = f"{config.XANO_INSTANCE_BASE_URL}{config.XANO_API_GROUP_BASE}"


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if config.XANO_TOKEN:
        h["Authorization"] = f"Bearer {config.XANO_TOKEN}"
    return h


def create_scan(analysis: dict) -> dict:
    """POST a new scans row. Raises requests.RequestException on failure -
    callers fall back to the in-memory session rather than break the demo."""
    r = requests.post(f"{_BASE}/create", headers=_headers(),
                      json={"analysis": analysis}, timeout=15)
    r.raise_for_status()
    return r.json()


def get_scan(scan_id) -> dict | None:
    """None for both a network/lookup failure and a genuinely missing id -
    the `get` endpoint returns 200 + null body rather than 404, by design."""
    r = requests.get(f"{_BASE}/get", headers=_headers(),
                     params={"id": scan_id}, timeout=15)
    r.raise_for_status()
    return r.json()  # null (-> None) when the id doesn't exist


def save_routine(scan_id, routine: dict) -> dict:
    r = requests.post(f"{_BASE}/save_routine", headers=_headers(),
                      json={"id": int(scan_id), "routine": routine}, timeout=15)
    r.raise_for_status()
    return r.json()


def list_scans(limit: int = 20) -> list:
    """Most recent scans first. Sorted by id (always present, monotonic) -
    the `list` endpoint itself returns rows in no guaranteed order."""
    r = requests.get(f"{_BASE}/list", headers=_headers(), timeout=15)
    r.raise_for_status()
    rows = r.json() or []
    rows.sort(key=lambda x: x.get("id", 0), reverse=True)
    return rows[:limit]
