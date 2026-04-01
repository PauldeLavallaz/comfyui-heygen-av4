"""
ComfyUI node: HeyGen Avatar IV (AV4)
Generates realistic talking-head videos using HeyGen's Avatar IV API.
Takes a portrait image + audio file and produces a lip-synced video.
Automatically detects the image aspect ratio for the output video.
"""

from .media_utils import image_tensor_to_png_bytes, audio_tensor_to_uploadable, _make_video_output
from .heygen_api import upload_asset, generate_av4, generate_v2, poll_video_status, download_video


def _get_image_dimensions(image_tensor) -> tuple:
    """Extract (width, height) from IMAGE tensor [B, H, W, 3] and round to even."""
    if image_tensor.ndim == 4:
        h, w = image_tensor.shape[1], image_tensor.shape[2]
    else:
        h, w = image_tensor.shape[0], image_tensor.shape[1]
    # Round to nearest even number (required by most video codecs)
    w = w if w % 2 == 0 else w + 1
    h = h if h % 2 == 0 else h + 1
    return int(w), int(h)


class HeyGenAvatarIV:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"multiline": False, "default": ""}),
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
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
        custom_motion_prompt: str = "",
        enhance_custom_motion_prompt: bool = True,
    ):
        if not api_key.strip():
            raise ValueError("[HeyGen] api_key is required")

        # ── Detect image dimensions ──────────────────────────────────────────
        img_w, img_h = _get_image_dimensions(image)
        print(f"[HeyGen] Image dimensions: {img_w}x{img_h}")

        # ── 1. Upload image ──────────────────────────────────────────────────
        print("[HeyGen] Converting and uploading image...")
        png_bytes = image_tensor_to_png_bytes(image)
        img_resp = upload_asset(api_key, png_bytes, "image/png")
        image_key = img_resp.get("image_key", "")
        image_asset_id = img_resp.get("id", "")
        image_url = img_resp.get("url", "")
        print(f"[HeyGen] Image uploaded — image_key={image_key}, id={image_asset_id}")

        # ── 2. Upload audio ──────────────────────────────────────────────────
        print("[HeyGen] Converting and uploading audio...")
        audio_bytes, content_type, filename = audio_tensor_to_uploadable(audio)
        aud_resp = upload_asset(api_key, audio_bytes, content_type)
        audio_asset_id = aud_resp.get("id", "")
        audio_url = aud_resp.get("url", "")
        print(f"[HeyGen] Audio uploaded — id={audio_asset_id}")

        # ── 3. Generate video (v2 first for dimension support, AV4 fallback) ─
        video_id = None

        # Try v2 endpoint first — it respects the dimension parameter
        voice_config = {"type": "audio", "audio_asset_id": audio_asset_id}
        try:
            video_id = generate_v2(
                api_key=api_key,
                image_asset_id=image_asset_id,
                image_url=image_url,
                voice_config=voice_config,
                dimension={"width": img_w, "height": img_h},
                title="ComfyUI AV4",
                background=None,
                avatar_iv_motion_prompt=custom_motion_prompt,
                enhance_motion_prompt=enhance_custom_motion_prompt,
            )
        except Exception as e:
            print(f"[HeyGen] v2 endpoint failed: {e}")
            print("[HeyGen] Falling back to AV4 endpoint...")

        # Fallback to AV4
        if video_id is None:
            av4_params = {
                "image_key": image_key,
                "video_title": "ComfyUI AV4",
                "audio_asset_id": audio_asset_id,
            }
            if custom_motion_prompt.strip():
                av4_params["custom_motion_prompt"] = custom_motion_prompt
                av4_params["enhance_custom_motion_prompt"] = enhance_custom_motion_prompt
            video_id = generate_av4(api_key, av4_params)

        # ── 4. Poll for completion ───────────────────────────────────────────
        print("[HeyGen] Waiting for video to render...")
        result = poll_video_status(api_key, video_id, interval=5, max_checks=120)
        video_url_result = result.get("video_url", "")

        if not video_url_result:
            raise RuntimeError(f"[HeyGen] Video completed but no video_url returned. video_id={video_id}")

        # ── 5. Download and return ───────────────────────────────────────────
        local_path = download_video(video_url_result)
        video_output = _make_video_output(local_path)
        return (video_output, str(video_id), str(video_url_result))


NODE_CLASS_MAPPINGS = {
    "HeyGenAvatarIV": HeyGenAvatarIV,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HeyGenAvatarIV": "HeyGen Avatar IV (AV4)",
}
