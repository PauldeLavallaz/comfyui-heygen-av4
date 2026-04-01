"""
HeyGen API client for Avatar IV video generation.
Handles: asset upload, AV4 generation, v2 generation (fallback), status polling, video download.
"""

import json
import os
import time
import requests

from .media_utils import get_output_path

UPLOAD_URL = "https://upload.heygen.com/v1/asset"
AV4_GENERATE_URL = "https://api.heygen.com/v2/video/av4/generate"
V2_GENERATE_URL = "https://api.heygen.com/v2/video/generate"
STATUS_URL = "https://api.heygen.com/v1/video_status.get"


def _headers(api_key: str, content_type: str = "application/json") -> dict:
    return {
        "X-Api-Key": api_key,
        "Content-Type": content_type,
        "Accept": "application/json",
    }


# ─── Asset Upload ────────────────────────────────────────────────────────────

def upload_asset(api_key: str, data: bytes, content_type: str) -> dict:
    """Upload binary data to HeyGen. Returns the response 'data' dict.
    For images: data["image_key"] is needed by AV4 endpoint.
    For audio: data["id"] is the audio_asset_id.
    """
    resp = requests.post(
        UPLOAD_URL,
        headers=_headers(api_key, content_type),
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 100:
        raise RuntimeError(f"[HeyGen] Upload failed: {json.dumps(body)}")
    return body.get("data", {})


# ─── AV4 Video Generation ───────────────────────────────────────────────────

def generate_av4(api_key: str, params: dict) -> str:
    """Call the dedicated Avatar IV endpoint. Returns video_id."""
    resp = requests.post(
        AV4_GENERATE_URL,
        headers=_headers(api_key),
        json=params,
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()

    # Extract video_id from response
    video_id = None
    if isinstance(body.get("data"), dict):
        video_id = body["data"].get("video_id")
    if not video_id:
        raise RuntimeError(f"[HeyGen] AV4 generate: no video_id in response: {json.dumps(body)}")
    print(f"[HeyGen] AV4 video submitted: {video_id}")
    return video_id


# ─── V2 Video Generation (fallback) ─────────────────────────────────────────

def generate_v2(
    api_key: str,
    image_asset_id: str,
    image_url: str,
    voice_config: dict,
    dimension: dict,
    title: str = "",
    background: dict | None = None,
    avatar_iv_motion_prompt: str = "",
    enhance_motion_prompt: bool = True,
) -> str:
    """Call the general v2/video/generate endpoint with use_avatar_iv_model=True.
    Returns video_id.
    """
    character = {
        "type": "talking_photo",
        "talking_photo_id": image_asset_id,
        "use_avatar_iv_model": True,
    }
    if avatar_iv_motion_prompt:
        character["prompt"] = avatar_iv_motion_prompt
        character["keep_original_prompt"] = not enhance_motion_prompt

    scene = {
        "character": character,
        "voice": voice_config,
    }
    if background:
        scene["background"] = background

    payload = {
        "video_inputs": [scene],
        "dimension": dimension,
    }
    if title:
        payload["title"] = title

    resp = requests.post(
        V2_GENERATE_URL,
        headers=_headers(api_key),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()

    video_id = None
    if isinstance(body.get("data"), dict):
        video_id = body["data"].get("video_id")
    if not video_id:
        raise RuntimeError(f"[HeyGen] v2 generate: no video_id in response: {json.dumps(body)}")
    print(f"[HeyGen] v2 video submitted: {video_id}")
    return video_id


# ─── Status Polling ──────────────────────────────────────────────────────────

def poll_video_status(api_key: str, video_id: str, interval: int = 5, max_checks: int = 120) -> dict:
    """Poll video status until completed or failed. Returns full response data dict."""
    headers = {"Accept": "application/json", "X-Api-Key": api_key}

    for i in range(max_checks):
        resp = requests.get(
            STATUS_URL,
            params={"video_id": video_id},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data", {})
        status = data.get("status", "unknown")

        if status == "completed":
            print(f"[HeyGen] Video completed after {i+1} checks ({(i+1)*interval}s)")
            return data
        elif status == "failed":
            error = data.get("error", {})
            raise RuntimeError(f"[HeyGen] Video generation failed: {json.dumps(error)}")

        if i % 6 == 0:
            print(f"[HeyGen] Status: {status} (check {i+1}/{max_checks})")
        time.sleep(interval)

    raise RuntimeError(
        f"[HeyGen] Video generation timed out after {max_checks} checks "
        f"({max_checks * interval}s). video_id={video_id}"
    )


# ─── Video Download ──────────────────────────────────────────────────────────

def download_video(video_url: str, prefix: str = "heygen_av4") -> str:
    """Download video from URL to ComfyUI output directory. Returns local path."""
    out_path = get_output_path(prefix, "mp4")
    print(f"[HeyGen] Downloading video to {out_path}...")

    resp = requests.get(video_url, stream=True, timeout=300)
    resp.raise_for_status()

    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"[HeyGen] Downloaded {size_mb:.1f} MB → {out_path}")
    return out_path
