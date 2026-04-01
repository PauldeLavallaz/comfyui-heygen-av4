"""
Media conversion utilities for HeyGen Avatar IV ComfyUI node.
Handles IMAGE tensor → PNG, AUDIO tensor → MP3/WAV, and VIDEO output wrapping.
"""

import io
import os
import time
import shutil
import subprocess
import tempfile
import numpy as np
import torch
from PIL import Image

try:
    import folder_paths
    COMFY_AVAILABLE = True
except ImportError:
    COMFY_AVAILABLE = False


# ─── VIDEO type helper ──────────────────────────────────────────────────────

def _make_video_output(path: str):
    """Wrap video path as ComfyUI VIDEO type for SaveVideo compatibility."""
    try:
        from comfy_api.input_impl import VideoFromFile
        return VideoFromFile(path)
    except ImportError:
        pass
    try:
        from comfy_api.latest._input_impl import VideoFromFile
        return VideoFromFile(path)
    except (ImportError, AttributeError):
        pass
    return path


# ─── IMAGE conversion ───────────────────────────────────────────────────────

def image_tensor_to_png_bytes(image_tensor: torch.Tensor) -> bytes:
    """Convert ComfyUI IMAGE tensor [B, H, W, 3] float32 [0,1] → PNG bytes."""
    if image_tensor.ndim == 4:
        image_tensor = image_tensor[0]

    np_img = (image_tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    pil = Image.fromarray(np_img)

    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


# ─── AUDIO conversion ───────────────────────────────────────────────────────

def _find_ffmpeg() -> str | None:
    """Find ffmpeg binary in common locations."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    for p in [
        "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/conda/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/opt/ffmpeg/bin/ffmpeg",
    ]:
        if os.path.exists(p):
            return p
    return None


def audio_tensor_to_uploadable(audio: dict) -> tuple:
    """
    Convert ComfyUI AUDIO dict {'waveform': Tensor[B,C,T], 'sample_rate': int}
    to (bytes, content_type, filename).

    Cascade: ffmpeg MP3 → torchaudio MP3 → torchaudio WAV → stdlib wave WAV.
    """
    waveform = audio["waveform"]   # [B, C, T]
    sample_rate = audio["sample_rate"]

    if waveform.ndim == 3:
        waveform = waveform[0]     # [C, T]
    if waveform.shape[0] > 2:
        waveform = waveform[:2]    # max stereo

    channels = waveform.shape[0]

    # 1. ffmpeg: PCM s16le → MP3
    try:
        pcm = (waveform.cpu().numpy() * 32767).clip(-32768, 32767).astype("int16")
        pcm_bytes = pcm.T.flatten().tobytes()
        ffmpeg = _find_ffmpeg()
        if ffmpeg:
            cmd = [ffmpeg, "-y",
                   "-f", "s16le", "-ar", str(sample_rate), "-ac", str(channels),
                   "-i", "pipe:0",
                   "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k",
                   "-f", "mp3", "pipe:1"]
            result = subprocess.run(cmd, input=pcm_bytes, capture_output=True, timeout=30)
            if result.returncode == 0 and len(result.stdout) > 0:
                print(f"[HeyGen] Audio via ffmpeg MP3: {len(result.stdout)/1024:.1f} KB")
                return result.stdout, "audio/mpeg", "heygen_audio.mp3"
    except Exception as e:
        print(f"[HeyGen] ffmpeg PCM→MP3 failed ({e}), trying torchaudio...")

    # 2. torchaudio MP3
    try:
        import torchaudio
        buf = io.BytesIO()
        torchaudio.save(buf, waveform.cpu(), sample_rate, format="mp3")
        data = buf.getvalue()
        print(f"[HeyGen] Audio via torchaudio MP3: {len(data)/1024:.1f} KB")
        return data, "audio/mpeg", "heygen_audio.mp3"
    except Exception as e:
        print(f"[HeyGen] torchaudio MP3 failed ({e}), trying WAV...")

    # 3. torchaudio WAV
    try:
        import torchaudio
        buf = io.BytesIO()
        torchaudio.save(buf, waveform.cpu(), sample_rate, format="wav")
        data = buf.getvalue()
        print(f"[HeyGen] Audio via torchaudio WAV: {len(data)/1024:.1f} KB")
        return data, "audio/wav", "heygen_audio.wav"
    except Exception as e:
        print(f"[HeyGen] torchaudio WAV failed ({e}), trying wave module...")

    # 4. Pure-Python wave (stdlib)
    import wave as wavemod
    pcm = (waveform.cpu().numpy() * 32767).clip(-32768, 32767).astype("int16")
    pcm_bytes = pcm.T.flatten().tobytes()
    buf = io.BytesIO()
    with wavemod.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    data = buf.getvalue()
    print(f"[HeyGen] Audio via wave module WAV: {len(data)/1024:.1f} KB")
    return data, "audio/wav", "heygen_audio.wav"


# ─── Output path helper ─────────────────────────────────────────────────────

def get_output_path(prefix: str = "heygen_av4", ext: str = "mp4") -> str:
    """Get a unique output path in ComfyUI's output directory."""
    if COMFY_AVAILABLE:
        out_dir = folder_paths.get_output_directory()
    else:
        out_dir = tempfile.gettempdir()
    ts = int(time.time())
    return os.path.join(out_dir, f"{prefix}_{ts}.{ext}")
