"""
HeyGen API client for Avatar IV video generation.
Uses the v2/videos endpoint which natively supports aspect_ratio.
"""

import json
import os
import time
import requests

from .media_utils import get_output_path

UPLOAD_URL = "https://upload.heygen.com/v1/asset"
GENERATE_URL = "https://api.heygen.com/v2/videos"
STATUS_URL = "https://api.heygen.com/v1/video_status.get"


def _headers(api_key: str, content_type: str = "application/json") -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": content_type,
        "Accept": "application/json",
    }


# ─── Asset Upload ────────────────────────────────────────────────────────────

def upload_asset(api_key: str, data: bytes, content_type: str) -> dict:
    """Upload binary data to HeyGen. Returns the response 'data' dict."""
    resp = requests.post(UPLOAD_URL, headers=_headers(api_key, content_type), data=data, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 100:
        raise RuntimeError(f"[HeyGen] Upload failed: {json.dumps(body)}")
    result = body.get("data", {})
    print(f"[HeyGen] Uploaded: id={result.get('id')}")
    return result


# ─── Video Generation (v2/videos) ───────────────────────────────────────────

def generate_video(api_key: str, params: dict) -> str:
    """Call POST /v2/videos. Returns video_id."""
    print(f"[HeyGen] Request: {json.dumps(params, indent=2)}")
    resp = requests.post(GENERATE_URL, headers=_headers(api_key), json=params, timeout=60)
    print(f"[HeyGen] Response: {resp.status_code} {resp.text[:300]}")
    resp.raise_for_status()
    body = resp.json()
    data = body.get("data", body)
    video_id = data.get("video_id", "")
    if not video_id:
        raise RuntimeError(f"[HeyGen] No video_id: {json.dumps(body)}")
    print(f"[HeyGen] Video submitted: {video_id}")
    return video_id


# ─── Status Polling ──────────────────────────────────────────────────────────

def poll_video_status(api_key: str, video_id: str, interval: int = 5, max_checks: int = 120) -> dict:
    """Poll until completed or failed."""
    headers = {"Accept": "application/json", "X-Api-Key": api_key}
    for i in range(max_checks):
        resp = requests.get(STATUS_URL, params={"video_id": video_id}, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        status = data.get("status", "unknown")
        if status == "completed":
            print(f"[HeyGen] Completed after {(i+1)*interval}s")
            return data
        elif status == "failed":
            raise RuntimeError(f"[HeyGen] Failed: {json.dumps(data.get('error', {}))}")
        if i % 6 == 0:
            print(f"[HeyGen] {status} ({i+1}/{max_checks})")
        time.sleep(interval)
    raise RuntimeError(f"[HeyGen] Timed out after {max_checks*interval}s")


# ─── Video Download ──────────────────────────────────────────────────────────

def download_video(video_url: str) -> str:
    """Download video to ComfyUI output directory."""
    out_path = get_output_path("heygen_av4", "mp4")
    resp = requests.get(video_url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"[HeyGen] Downloaded {os.path.getsize(out_path)/(1024*1024):.1f} MB → {out_path}")
    return out_path
