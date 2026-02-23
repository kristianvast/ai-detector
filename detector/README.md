# AI Detector

A lightweight, configurable AI detector that leverages Ultralytics YOLO models for object detection and Visual Language Models (VLMs) for validation said detections. Detections can be exported to local disk, Telegram, or via Webhooks.

## Usage

The `example/` folder contains a complete setup:

- `config.json` - Sample configuration.
- `compose.yml` - Docker Compose file.
- `sprong24.mp4` - Sample video.

### Running with Docker

```bash
cd example
docker compose up -d
docker compose logs -f aidetector
```

### Running in development

```bash
# Install dependencies
uv sync --extra default

# Run the detector (requires config.json in the current directory)
uv run --extra default main

# Sync JSON schema with the Pydantic data models
uv run generate-schema
```

## Configuration

The application is configured via a `config.json` file. Below is the structure and description of the configuration options.

### Structure

The root configuration object contains a list of detectors.

```json
{
  "detectors": [
    {
      "detection": { ... },
      "yolo": { ... },
      "vlm": { ... },
      "exporters": { ... }
    }
  ]
}
```

### Detector Configuration

| Field       | Type     | Description                                              |
| :---------- | :------- | :------------------------------------------------------- |
| `detection` | `object` | Settings for detection sources and intervals.            |
| `yolo`      | `object` | (Optional) Settings for the YOLO object detection model. |
| `vlm`       | `object` | (Optional) Settings for the VLM verification.            |
| `exporters` | `object` | (Optional) Where to send valid detections.               |

#### Detection (`detection`)

| Field             | Type            | Default | Description                                       |
| :---------------- | :-------------- | :------ | :------------------------------------------------ |
| `source`          | `str` or `list` |         | Video file path(s) or stream URL(s).              |
| `interval`        | `float`         | `0`     | (Optional) Minimum time (seconds) between frames. |
| `frame_retention` | `int`           | `30`    | Number of frames to retain per detection event.   |

#### YOLO (`yolo`)

| Field                   | Type                | Default    | Description                                                                                                                                                                   |
| :---------------------- | :------------------ | :--------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`                 | `str`               |            | URL or path to the YOLO model (`.pt` or `.onnx`).                                                                                                                            |
| `confidence`            | `float` or `object` | `0`        | Minimum confidence threshold for YOLO detections. You can also pass per-class thresholds, e.g. `{ "mounting": 0.8, "jumping": 0.75 }`; only configured classes are evaluated. |
| `time_max`              | `int`               | `60`       | Max duration (seconds) to group detections into one event.                                                                                                                    |
| `timeout`               | `int`               | `5`        | Seconds to wait before considering a detection sequence ended.                                                                                                                |
| `cooldown`              | `float` or `object` | `0`        | Seconds to wait after an event before starting a new one. Can be a single value or per-class, e.g. `{ "mounting": 30 }`.                                                     |
| `include_trailing_time` | `int`               | `1`        | Seconds of trailing frames to include at the end of detection event.                                                                                                          |
| `frames_min`            | `int`               | `6` / `3`  | Minimum consecutive frames for detection (6 with GPU, 3 with CPU).                                                                                                            |
| `imgsz`                 | `int`               | `640`      | Input image size for the YOLO model.                                                                                                                                          |
| `strategy`              | `str`               | `"LATEST"` | Frame selection strategy: `"LATEST"` (most recent frame) or `"ALL"` (all frames).                                                                                            |

#### VLM (`vlm`)

The VLM block is used to verify detections using a Vision Language Model. It can be a single object or a list of VLM configurations.

| Field      | Type            | Default   | Description                                                                                        |
| :--------- | :-------------- | :-------- | :------------------------------------------------------------------------------------------------- |
| `prompt`   | `str`           |           | The question to ask the VLM about the image (e.g., "Is there a person?").                          |
| `model`    | `str` or `list` |           | Model name(s) to use (e.g., `gemini-pro-vision`). If a list, models are tried in order on failure. |
| `key`      | `str`           |           | (Optional) API key for the VLM provider.                                                           |
| `url`      | `str`           |           | (Optional) API URL for the VLM provider.                                                           |
| `strategy` | `str`           | `"VIDEO"` | Validation strategy: `"IMAGE"` (single frame) or `"VIDEO"` (full detection sequence).              |

#### Exporters (`exporters`)

Configure where to send the detection results.

**Disk (`disk`)**
| Field | Type | Default | Description |
| :---------- | :------ | :------ | :----------------------------------------------- |
| `directory` | `str` | | Path to the directory where images will be saved.|
| `confidence`| `float` or `object` | | (Optional) Min confidence to export to disk. For object values, only matching classes are exported and each class uses its own threshold. |
| `strategy` | `str` | `"BEST"` | Save `"ALL"` frames or only the `"BEST"` one. |
| `export_rejected`| `bool` | `true` | Export detections rejected by VLM. |

**Telegram (`telegram`)**
| Field | Type | Default | Description |
| :------------- | :------ | :------ | :-------------------------------------------------- |
| `token` | `str` | | Telegram Bot API token. |
| `chat` | `str` | | Telegram Chat ID. |
| `confidence` | `float` or `object` | | (Optional) Min confidence to send to Telegram. For object values, only matching classes are exported and each class uses its own threshold. |
| `alert_every` | `int` | `1` | Send notification sound every Nth detection. |
| `include_plot` | `bool` | `false` | Include full frame with detection overlay. |
| `include_crop` | `bool` | `false` | Include cropped detection area. |
| `include_video`| `bool` | `true` | Include MP4 video of detection sequence. |
| `video_width` | `int` | `1280` | Video width in pixels (height auto-calculated). |
| `video_crf` | `int` | `28` | H.264 compression quality (0-51, lower = better). |
| `export_rejected`| `bool` | `false` | Export detections rejected by VLM. |

**Webhook (`webhook`)**
| Field              | Type                | Default    | Description                                                                                                                               |
| :----------------- | :------------------ | :--------- | :---------------------------------------------------------------------------------------------------------------------------------------- |
| `url`              | `str`               |            | The webhook endpoint URL.                                                                                                                 |
| `token`            | `str`               |            | (Optional) Authorization token sent in headers.                                                                                           |
| `confidence`       | `float` or `object` |            | (Optional) Min confidence to trigger webhook. For object values, only matching classes are exported and each class uses its own threshold. |
| `data_type`        | `str`               | `"binary"` | Payload type: `"binary"` (raw bytes) or `"base64"`.                                                                                      |
| `data_max`         | `int`               |            | (Optional) Max data size in bytes (compresses if exceeded).                                                                               |
| `include_plot`     | `bool`              | `false`    | Include full frame with detection overlay.                                                                                                |
| `include_crop`     | `bool`              | `true`     | Include cropped detection area.                                                                                                           |
| `include_video`    | `bool`              | `false`    | Include MP4 video of detection sequence.                                                                                                  |
| `video_width`      | `int`               | `1280`     | Video width in pixels (height auto-calculated).                                                                                           |
| `video_crf`        | `int`               | `28`       | H.264 compression quality (0-51, lower = better).                                                                                        |
| `export_rejected`  | `bool`              | `false`    | Export detections rejected by VLM.                                                                                                        |

### Example Config

```json
{
  "detectors": [
    {
      "detection": {
        "source": ["rtsp://camera1", "rtsp://camera2"]
      },
      "yolo": {
        "model": "https://github.com/CowCatcherAI/CowCatcherAI/releases/download/modelv-14/cowcatcherV15.pt",
        "confidence": 0.8,
        "frames_min": 3,
        "timeout": 5
      },
      "vlm": {
        "prompt": "Do you see cows that are mounting each other?",
        "model": [
          "gemini/gemini-3-flash-preview",
          "gemini/gemini-2.5-flash-lite",
          "gemini/gemini-2.5-flash"
        ],
        "key": "<your_api_key>"
      },
      "exporters": {
        "disk": { "directory": "mounts" },
        "telegram": {
          "token": "<your_bot_token>",
          "chat": "<your_chat_id>"
        }
      }
    }
  ]
}
```

## Built With

- **[Ultralytics YOLO](https://github.com/ultralytics/ultralytics)**: State-of-the-art real-time object detection.
- **[LiteLLM](https://docs.litellm.ai/)**: Unified interface for calling various LLM APIs (OpenAI, Anthropic, Gemini, etc.).
- **[Pydantic](https://docs.pydantic.dev/)**: Data validation and settings management using Python type hints.

## License

This project is licensed under the AGPL (see [LICENSE](LICENSE)).
