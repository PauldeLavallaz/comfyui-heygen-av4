"""
ComfyUI node: HeyGen Avatar IV (AV4)
Generates realistic talking-head videos using HeyGen's Avatar IV API.
Takes a portrait image + audio file and produces a lip-synced video.
"""

from .media_utils import image_tensor_to_png_bytes, audio_tensor_to_uploadable, _make_video_output
from .heygen_api import (
    upload_asset, generate_av4, generate_v2, poll_video_status, download_video,
)

ASPECT_RATIOS = ["9:16", "16:9", "1:1"]

DIMENSION_MAP = {
    "9:16": {"width": 1080, "height": 1920},
    "16:9": {"width": 1920, "height": 1080},
    "1:1":  {"width": 1080, "height": 1080},
}


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
                "custom_motion_prompt": ("STRING", {"multiline": True, "default": ""}),
                "enhance_custom_motion_prompt": ("BOOLEAN", {"default": True}),
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
        custom_motion_prompt: str = "",
        enhance_custom_motion_prompt: bool = True,
    ):
        if not api_key.strip():
            raise ValueError("[HeyGen] api_key is required")

        dimension = DIMENSION_MAP[aspect_ratio]
        print(f"[HeyGen] aspect_ratio={aspect_ratio}, dimension={dimension}")

        # ── 1. Upload image ──────────────────────────────────────────────────
        print("[HeyGen] Uploading image...")
        png_bytes = image_tensor_to_png_bytes(image)
        img_resp = upload_asset(api_key, png_bytes, "image/png")
        image_key = img_resp.get("image_key", "")
        image_asset_id = img_resp.get("id", "")
        image_url = img_resp.get("url", "")

        # ── 2. Upload audio ──────────────────────────────────────────────────
        print("[HeyGen] Uploading audio...")
        audio_bytes, content_type, filename = audio_tensor_to_uploadable(audio)
        aud_resp = upload_asset(api_key, audio_bytes, content_type)
        audio_asset_id = aud_resp.get("id", "")

        # ── 3. Generate video (AV4 primary, v2 fallback) ────────────────────
        video_id = None
        used_endpoint = None

        # AV4 endpoint
        print(f"[HeyGen] Trying AV4 endpoint with aspect_ratio={aspect_ratio}...")
        av4_params = {
            "image_key": image_key,
            "video_title": "ComfyUI AV4",
            "audio_asset_id": audio_asset_id,
            "aspect_ratio": aspect_ratio,
        }
        if custom_motion_prompt.strip():
            av4_params["custom_motion_prompt"] = custom_motion_prompt
            av4_params["enhance_custom_motion_prompt"] = enhance_custom_motion_prompt

        try:
            video_id = generate_av4(api_key, av4_params)
            used_endpoint = "av4"
        except Exception as e:
            print(f"[HeyGen] AV4 FAILED: {e}")

        # v2 fallback
        if video_id is None:
            print(f"[HeyGen] Trying v2 fallback with dimension={dimension}...")
            try:
                video_id = generate_v2(
                    api_key=api_key,
                    image_asset_id=image_asset_id,
                    image_url=image_url,
                    voice_config={"type": "audio", "audio_asset_id": audio_asset_id},
                    dimension=dimension,
                    aspect_ratio=aspect_ratio,
                    title="ComfyUI AV4",
                    avatar_iv_motion_prompt=custom_motion_prompt,
                    enhance_motion_prompt=enhance_custom_motion_prompt,
                )
                used_endpoint = "v2"
            except Exception as e:
                print(f"[HeyGen] v2 FAILED: {e}")

        if video_id is None:
            raise RuntimeError("[HeyGen] Both endpoints failed. Check ComfyUI console for details.")

        print(f"[HeyGen] Video submitted via {used_endpoint}: {video_id}")

        # ── 4. Poll + Download ───────────────────────────────────────────────
        print("[HeyGen] Waiting for render...")
        result = poll_video_status(api_key, video_id, interval=5, max_checks=120)
        video_url_result = result.get("video_url", "")
        if not video_url_result:
            raise RuntimeError(f"[HeyGen] No video_url. video_id={video_id}")

        local_path = download_video(video_url_result)
        return (_make_video_output(local_path), str(video_id), str(video_url_result))


NODE_CLASS_MAPPINGS = {
    "HeyGenAvatarIV": HeyGenAvatarIV,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HeyGenAvatarIV": "HeyGen Avatar IV (AV4)",
}
