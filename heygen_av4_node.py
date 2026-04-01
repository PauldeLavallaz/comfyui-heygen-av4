"""
ComfyUI node: HeyGen Avatar IV (AV4)
Uses POST /v2/videos — the correct endpoint that supports aspect_ratio natively.
"""

from .media_utils import image_tensor_to_png_bytes, audio_tensor_to_uploadable, _make_video_output
from .heygen_api import upload_asset, generate_video, poll_video_status, download_video

ASPECT_RATIOS = ["9:16", "16:9"]
RESOLUTIONS = ["1080p", "720p"]


class HeyGenAvatarIV:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"multiline": False, "default": ""}),
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
                "aspect_ratio": (ASPECT_RATIOS, {"default": "9:16"}),
            },
            "optional": {
                "motion_prompt": ("STRING", {"multiline": True, "default": ""}),
                "resolution": (RESOLUTIONS, {"default": "1080p"}),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING")
    RETURN_NAMES = ("video", "video_id", "video_url")
    FUNCTION = "execute"
    CATEGORY = "HeyGen"
    OUTPUT_NODE = True

    def execute(
        self,
        api_key: str,
        image,
        audio,
        aspect_ratio: str = "9:16",
        motion_prompt: str = "",
        resolution: str = "1080p",
    ):
        if not api_key.strip():
            raise ValueError("[HeyGen] api_key is required")

        # ── 1. Upload image ──────────────────────────────────────────────────
        print("[HeyGen] Uploading image...")
        png_bytes = image_tensor_to_png_bytes(image)
        img_resp = upload_asset(api_key, png_bytes, "image/png")
        image_asset_id = img_resp.get("id", "")

        # ── 2. Upload audio ──────────────────────────────────────────────────
        print("[HeyGen] Uploading audio...")
        audio_bytes, content_type, filename = audio_tensor_to_uploadable(audio)
        aud_resp = upload_asset(api_key, audio_bytes, content_type)
        audio_asset_id = aud_resp.get("id", "")

        # ── 3. Generate video ────────────────────────────────────────────────
        params = {
            "image_asset_id": image_asset_id,
            "audio_asset_id": audio_asset_id,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "remove_background": False,
        }
        if motion_prompt.strip():
            params["motion_prompt"] = motion_prompt

        video_id = generate_video(api_key, params)

        # ── 4. Poll + Download ───────────────────────────────────────────────
        print("[HeyGen] Waiting for render...")
        result = poll_video_status(api_key, video_id)
        video_url = result.get("video_url", "")
        if not video_url:
            raise RuntimeError(f"[HeyGen] No video_url. video_id={video_id}")

        local_path = download_video(video_url)
        return (_make_video_output(local_path), str(video_id), str(video_url))


NODE_CLASS_MAPPINGS = {
    "HeyGenAvatarIV": HeyGenAvatarIV,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HeyGenAvatarIV": "HeyGen Avatar IV (AV4)",
}
