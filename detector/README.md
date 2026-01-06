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
uv sync

# Run the detector (requires config.json in the current directory)
uv run main
```

## Configuration

The application is configured via a `config.json` file. Below is the structure and description of the configuration options.

### Structure

The root configuration object contains a list of detectors.

```json
{
  "detectors": [
    {
      "sources": ["..."],
      "detection": { ... },
      "vlm": { ... },
      "exporters": { ... }
    }
  ]
}
```

### Detector Configuration

| Field       | Type            | Description                                   |
| :---------- | :-------------- | :-------------------------------------------- |
| `source`    | `str` or `list` | Video file path(s) or stream URL(s).          |
| `detection` | `object`        | Settings for the YOLO object detection model. |
| `vlm`       | `object`        | (Optional) Settings for the VLM verification. |
| `exporters` | `object`        | (Optional) Where to send valid detections.    |

#### Detection (`detection`)

| Field        | Type    | Default | Description                                                                 |
| :----------- | :------ | :------ | :-------------------------------------------------------------------------- |
| `yolo`       | `str`   | `None`  | URL or path to the YOLO model (`.pt`).                                      |
| `confidence` | `float` | `0`     | Minimum confidence threshold for YOLO detections.                           |
| `frames_min` | `int`   | `1`     | Minimum number of consecutive frames required to trigger a detection event. |
| `time_max`   | `int`   | `0`     | Max duration (seconds) to group detections into one event.                  |
| `interval`   | `int`   | `0`     | Minimum time (seconds) between separate detection events.                   |
| `timeout`    | `int`   | `None`  | Seconds to wait before considering a detection sequence ended.              |

#### VLM (`vlm`)

The VLM block is used to verify detections using a Vision Language Model. It can be a single object or a list of VLM configurations.

| Field    | Type            | Description                                                                                        |
| :------- | :-------------- | :------------------------------------------------------------------------------------------------- |
| `prompt` | `str`           | The question to ask the VLM about the image (e.g., "Is there a person?").                          |
| `model`  | `str` or `list` | Model name(s) to use (e.g., `gemini-pro-vision`). If a list, models are tried in order on failure. |
| `key`    | `str`           | (Optional) API key for the VLM provider.                                                           |
| `url`    | `str`           | (Optional) API URL for the VLM provider.                                                           |

#### Exporters (`exporters`)

Configure where to send the detection results.

**Disk (`disk`)**
| Field | Type | Description |
| :---------- | :------ | :----------------------------------------------- |
| `directory` | `str` | Path to the directory where images will be saved.|
| `confidence`| `float` | (Optional) Min confidence to export to disk. |

**Telegram (`telegram`)**
| Field | Type | Description |
| :----------- | :------ | :-------------------------------------------- |
| `token` | `str` | Telegram Bot API token. |
| `chat` | `str` | Telegram Chat ID. |
| `confidence` | `float` | (Optional) Min confidence to send to Telegram.|

**Webhook (`webhook`)**
| Field | Type | Default | Description |
| :----------- | :------ | :------- | :-------------------------------------------- |
| `url` | `str` | | The webhook endpoint URL. |
| `token` | `str` | | Authorization token sent in headers. |
| `data_type` | `str` | `binary` | Payload type: `binary` (raw bytes) or `base64`.|
| `data_max` | `int` | `None` | Max data size in bytes. |
| `confidence` | `float` | `None` | (Optional) Min confidence to trigger webhook. |

### Example Config

```json
{
  "detectors": [
    {
      "source": ["rtsp://camera1", "rtsp://camera2"],
      "detection": {
        "yolo": "https://github.com/CowCatcherAI/CowCatcherAI/releases/download/modelv-14/cowcatcherV15.pt",
        "confidence": 0.7,
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

## License

This project is licensed under the AGPL (see [LICENSE](LICENSE)).
