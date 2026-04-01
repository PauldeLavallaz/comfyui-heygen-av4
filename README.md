# ComfyUI HeyGen Avatar IV (AV4)

ComfyUI custom node for generating realistic talking-head videos using [HeyGen's Avatar IV API](https://docs.heygen.com/).

Upload a portrait photo + audio clip and get back a lifelike AI video with natural lip-sync, micro-expressions, and gestures.

## Features

- **Image + Audio in, Video out** -- Connect `Load Image` + `Load Audio`, get a lip-synced video
- **Avatar IV motion prompts** -- Guide gestures and expressions with natural language
- **Automatic polling** -- The node waits for the video to render and returns it ready for `Save Video`
- **Fallback endpoint** -- If the AV4 endpoint fails, automatically falls back to HeyGen's v2 Studio API

## Installation

### Option 1: Clone

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/PauldeLavallaz/comfyui-heygen-av4.git
pip install -r comfyui-heygen-av4/requirements.txt
```

### Option 2: Manual

Download this repository and place the `comfyui-heygen-av4` folder inside `ComfyUI/custom_nodes/`. Restart ComfyUI.

## Requirements

- Python 3.10+
- `requests` (auto-installed with ComfyUI)
- A [HeyGen API key](https://app.heygen.com/settings?nav=API)
- ffmpeg recommended (for best audio conversion quality)

## Node: HeyGen Avatar IV (AV4)

**Category:** `HeyGen`

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `api_key` | STRING | Yes | Your HeyGen API key |
| `image` | IMAGE | Yes | Portrait photo (from Load Image) |
| `audio` | AUDIO | Yes | Audio clip (from Load Audio) |
| `video_title` | STRING | Yes | Title for the generated video |
| `custom_motion_prompt` | STRING | No | Motion instructions for avatar gestures and expressions |
| `enhance_custom_motion_prompt` | BOOLEAN | No | Let HeyGen AI enhance the motion prompt (default: true) |
| `width` | INT | No | Output video width (default: 1920) |
| `height` | INT | No | Output video height (default: 1080) |
| `background_type` | COMBO | No | transparent or color (default: transparent) |
| `background_color` | STRING | No | Hex color when background is color type (default: #FFFFFF) |
| `poll_interval` | INT | No | Seconds between status checks (default: 5) |
| `max_poll_checks` | INT | No | Max polls before timeout (default: 120 = 10 min) |
| `endpoint_mode` | COMBO | No | av4_with_fallback / av4_only / v2_only |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `video` | VIDEO | Generated video (connect to Save Video) |
| `video_id` | STRING | HeyGen video ID for reference |
| `video_url` | STRING | Direct URL to the generated video (expires in 7 days) |

## Usage

```
Load Image --> [image]
Load Audio --> [audio]   --> HeyGen Avatar IV (AV4) --> [video] --> Save Video
                             api_key: "your-key"
```

## How It Works

1. Uploads your image to HeyGen's asset API (returns `image_key`)
2. Uploads your audio to HeyGen's asset API (returns `audio_asset_id`)
3. Calls the Avatar IV generation endpoint with your parameters
4. Polls the status endpoint until the video is ready
5. Downloads the video and returns it as a ComfyUI VIDEO type

## License

MIT
