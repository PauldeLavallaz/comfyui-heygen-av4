"""
ComfyUI node: HeyGen Avatar IV (AV4)
Generates realistic talking-head videos using HeyGen's Avatar IV API.
Supports audio input mode (pre-recorded audio) and TTS mode (text-to-speech).
"""

from .media_utils import image_tensor_to_png_bytes, audio_tensor_to_uploadable, _make_video_output
from .heygen_api import upload_asset, generate_av4, generate_v2, poll_video_status, download_video


EMOTIONS = ["Friendly", "Serious", "Soothing", "Excited", "Cheerful", "Broadcaster"]
ENDPOINT_MODES = ["av4_with_fallback", "av4_only", "v2_only"]
BACKGROUND_TYPES = ["transparent", "color"]


class HeyGenAvatarIV:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"multiline": False, "default": ""}),
                "image": ("IMAGE",),
                "video_title": ("STRING", {"multiline": False, "default": "ComfyUI AV4 Video"}),
            },
            "optional": {
                # Audio mode (takes priority over TTS when connected)
                "audio": ("AUDIO",),

                # TTS mode (used when audio is NOT connected)
                "script": ("STRING", {"multiline": True, "default": ""}),
                "voice_id": ("STRING", {"multiline": False, "default": ""}),
                "speed": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 1.5, "step": 0.1}),
                "pitch": ("INT", {"default": 0, "min": -50, "max": 50, "step": 1}),
                "emotion": (EMOTIONS, {"default": "Friendly"}),

                # Avatar IV motion control
                "custom_motion_prompt": ("STRING", {"multiline": True, "default": ""}),
                "enhance_custom_motion_prompt": ("BOOLEAN", {"default": True}),

                # Video dimensions
                "width": ("INT", {"default": 1920, "min": 256, "max": 3840, "step": 2}),
                "height": ("INT", {"default": 1080, "min": 256, "max": 2160, "step": 2}),

                # Background (v2 fallback)
                "background_type": (BACKGROUND_TYPES, {"default": "transparent"}),
                "background_color": ("STRING", {"multiline": False, "default": "#FFFFFF"}),

                # Polling
                "poll_interval": ("INT", {"default": 5, "min": 1, "max": 30, "step": 1}),
                "max_poll_checks": ("INT", {"default": 120, "min": 10, "max": 1000, "step": 10}),

                # Endpoint selection
                "endpoint_mode": (ENDPOINT_MODES, {"default": "av4_with_fallback"}),
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
        video_title: str = "ComfyUI AV4 Video",
        audio=None,
        script: str = "",
        voice_id: str = "",
        speed: float = 1.0,
        pitch: int = 0,
        emotion: str = "Friendly",
        custom_motion_prompt: str = "",
        enhance_custom_motion_prompt: bool = True,
        width: int = 1920,
        height: int = 1080,
        background_type: str = "transparent",
        background_color: str = "#FFFFFF",
        poll_interval: int = 5,
        max_poll_checks: int = 120,
        endpoint_mode: str = "av4_with_fallback",
    ):
        # ── 1. Validate ─────────────────────────────────────────────────────
        if not api_key.strip():
            raise ValueError("[HeyGen] api_key is required")

        audio_mode = audio is not None
        if not audio_mode:
            if not script.strip():
                raise ValueError("[HeyGen] Either connect an AUDIO input or provide a script for TTS")
            if not voice_id.strip():
                raise ValueError("[HeyGen] voice_id is required for TTS mode (no audio connected)")

        # ── 2. Upload image ──────────────────────────────────────────────────
        print("[HeyGen] Converting and uploading image...")
        png_bytes = image_tensor_to_png_bytes(image)
        img_resp = upload_asset(api_key, png_bytes, "image/png")
        image_key = img_resp.get("image_key", "")
        image_asset_id = img_resp.get("id", "")
        image_url = img_resp.get("url", "")
        print(f"[HeyGen] Image uploaded — image_key={image_key}, id={image_asset_id}")

        # ── 3. Upload audio (if provided) ────────────────────────────────────
        audio_asset_id = ""
        audio_url = ""
        if audio_mode:
            print("[HeyGen] Converting and uploading audio...")
            audio_bytes, content_type, filename = audio_tensor_to_uploadable(audio)
            aud_resp = upload_asset(api_key, audio_bytes, content_type)
            audio_asset_id = aud_resp.get("id", "")
            audio_url = aud_resp.get("url", "")
            print(f"[HeyGen] Audio uploaded — id={audio_asset_id}")

        # ── 4. Generate video ────────────────────────────────────────────────
        video_id = None

        # Try AV4 endpoint
        if endpoint_mode in ("av4_with_fallback", "av4_only"):
            av4_params = {
                "image_key": image_key,
                "video_title": video_title,
            }
            if audio_mode:
                av4_params["audio_asset_id"] = audio_asset_id
            else:
                av4_params["script"] = script
                av4_params["voice_id"] = voice_id

            if custom_motion_prompt.strip():
                av4_params["custom_motion_prompt"] = custom_motion_prompt
                av4_params["enhance_custom_motion_prompt"] = enhance_custom_motion_prompt

            try:
                video_id = generate_av4(api_key, av4_params)
            except Exception as e:
                if endpoint_mode == "av4_only":
                    raise
                print(f"[HeyGen] AV4 endpoint failed: {e}")
                print("[HeyGen] Falling back to v2 endpoint...")

        # Fallback to v2 endpoint
        if video_id is None and endpoint_mode in ("av4_with_fallback", "v2_only"):
            if audio_mode:
                voice_config = {
                    "type": "audio",
                    "audio_asset_id": audio_asset_id,
                }
            else:
                voice_config = {
                    "type": "text",
                    "input_text": script,
                    "voice_id": voice_id,
                    "speed": speed,
                    "pitch": pitch,
                }
                if emotion and emotion != "Friendly":
                    voice_config["emotion"] = emotion

            bg = None
            if background_type == "color":
                bg = {"type": "color", "value": background_color}
            elif background_type == "transparent":
                bg = {"type": "transparent"}

            video_id = generate_v2(
                api_key=api_key,
                image_asset_id=image_asset_id,
                image_url=image_url,
                voice_config=voice_config,
                dimension={"width": width, "height": height},
                title=video_title,
                background=bg,
                avatar_iv_motion_prompt=custom_motion_prompt,
                enhance_motion_prompt=enhance_custom_motion_prompt,
            )

        if video_id is None:
            raise RuntimeError("[HeyGen] Failed to generate video with all attempted endpoints")

        # ── 5. Poll for completion ───────────────────────────────────────────
        print(f"[HeyGen] Polling video status (every {poll_interval}s, max {max_poll_checks} checks)...")
        result = poll_video_status(api_key, video_id, poll_interval, max_poll_checks)
        video_url_result = result.get("video_url", "")

        if not video_url_result:
            raise RuntimeError(f"[HeyGen] Video completed but no video_url returned. video_id={video_id}")

        # ── 6. Download video ────────────────────────────────────────────────
        local_path = download_video(video_url_result)

        # ── 7. Return ────────────────────────────────────────────────────────
        video_output = _make_video_output(local_path)
        return (video_output, str(video_id), str(video_url_result))


NODE_CLASS_MAPPINGS = {
    "HeyGenAvatarIV": HeyGenAvatarIV,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HeyGenAvatarIV": "HeyGen Avatar IV (AV4)",
}
