"""GlowProof preflight: verify Perfect Corp auth, then optionally run one
real skin analysis and save the response as a reusable fixture.

    python scripts/preflight.py                  # auth + cost check, 0 units
    python scripts/preflight.py selfie.jpg       # full flow, SPENDS UNITS

Stage 1 hits GET /s2s/v2.0/credit/feature-cost, which proves the key works
and prints the per-call unit price without consuming anything. Only run
stage 2 once stage 1 passes.
"""
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE = os.getenv("PERFECTCORP_BASE_URL", "https://yce-api-01.makeupar.com").rstrip("/")
KEY = os.getenv("PERFECTCORP_API_KEY", "").strip()

# Keep this list at 4 or fewer to stay in the cheaper SD tier.
# Do NOT mix SD and HD concern names in one request - the API 400s.
CONCERNS = ["wrinkle", "pore", "texture", "acne"]

FIXTURE = ROOT / "fixtures" / "skin_analysis.json"


def headers():
    return {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


def die(msg):
    print(f"[fail] {msg}")
    sys.exit(1)


def stage1_auth():
    print(f"[..] GET {BASE}/s2s/v2.0/credit/feature-cost")
    try:
        r = requests.get(f"{BASE}/s2s/v2.0/credit/feature-cost",
                         headers=headers(), timeout=30)
    except requests.RequestException as e:
        die(f"network error: {e}\n       Try PERFECTCORP_BASE_URL="
            f"https://yce-api-01.perfectcorp.com instead.")
    if r.status_code == 401:
        die("401 unauthorized. Key is wrong, or your account is on the V1\n"
            "       client_id/id_token flow rather than V2 Bearer.")
    if r.status_code == 404:
        die(f"404. Wrong host or path. Body: {r.text[:300]}")
    if not r.ok:
        die(f"HTTP {r.status_code}: {r.text[:400]}")
    print("[ok] auth works. Feature cost table:")
    print(json.dumps(r.json(), indent=2)[:1500])
    return r.json()


def stage2_analyze(image_path: Path):
    if not image_path.exists():
        die(f"no such file: {image_path}")
    size = image_path.stat().st_size
    if size > 10 * 1024 * 1024:
        die(f"image is {size/1e6:.1f}MB; limit is 10MB")
    ctype = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"

    print(f"\n[..] POST /s2s/v2.0/file/skin-analysis ({size} bytes, {ctype})")
    r = requests.post(
        f"{BASE}/s2s/v2.0/file/skin-analysis",
        headers=headers(),
        json={"files": [{"content_type": ctype,
                         "file_name": image_path.name,
                         "file_size": size}]},
        timeout=30)
    if not r.ok:
        die(f"upload-url request failed HTTP {r.status_code}: {r.text[:400]}")
    f = r.json()["data"]["files"][0]
    file_id = f["file_id"]
    req = f["requests"][0]

    print(f"[..] PUT presigned URL -> file_id {file_id}")
    put = requests.put(req["url"], data=image_path.read_bytes(),
                       headers=req.get("headers", {}), timeout=120)
    if not put.ok:
        die(f"presigned upload failed HTTP {put.status_code}: {put.text[:300]}")

    print(f"[..] POST /s2s/v2.0/task/skin-analysis concerns={CONCERNS}")
    r = requests.post(
        f"{BASE}/s2s/v2.0/task/skin-analysis",
        headers=headers(),
        json={"src_file_id": file_id,
              "dst_actions": CONCERNS,
              "miniserver_args": {"enable_mask_overlay": True},
              "format": "json"},
        timeout=30)
    if not r.ok:
        die(f"task create failed HTTP {r.status_code}: {r.text[:400]}")
    task_id = r.json()["data"]["task_id"]
    print(f"[ok] task_id {task_id}")

    t0 = time.time()
    for attempt in range(60):
        time.sleep(2)
        r = requests.get(f"{BASE}/s2s/v2.0/task/skin-analysis/{task_id}",
                         headers=headers(), timeout=30)
        if not r.ok:
            die(f"poll failed HTTP {r.status_code}: {r.text[:300]}")
        body = r.json()
        status = body.get("data", {}).get("task_status")
        print(f"     [{time.time()-t0:5.1f}s] {status}")
        if status == "success":
            FIXTURE.parent.mkdir(exist_ok=True)
            FIXTURE.write_text(json.dumps(body, indent=2), encoding="utf-8")
            print(f"\n[ok] saved -> {FIXTURE}")
            print(f"[!!] END-TO-END LATENCY: {time.time()-t0:.1f}s "
                  f"- this is your demo's dead air. Design around it.")
            for o in body["data"]["results"]["output"]:
                print(f"     {o.get('type'):12} ui={o.get('ui_score')} "
                      f"raw={o.get('raw_score')} masks={len(o.get('mask_urls') or [])}")
            return body
        if status == "error":
            die(f"engine error (no units consumed): {json.dumps(body)[:400]}")
    die("timed out after 120s")


if __name__ == "__main__":
    if not KEY:
        die("PERFECTCORP_API_KEY is empty. Copy .env.example to .env first.")
    stage1_auth()
    if len(sys.argv) > 1:
        stage2_analyze(Path(sys.argv[1]))
    else:
        print("\nStage 1 only. Re-run with an image path to spend units:")
        print("    python scripts/preflight.py selfie.jpg")
