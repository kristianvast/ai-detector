# AI Detector Project

This project contains the source code for an AI-powered detection system.

## Components

- **[Detector](detector/README.md)**: The core service that runs object detection (YOLO) and VLM verification. Configurable to export detections to Disk, Telegram, or Webhooks.
- **Web**: Frontend interface (see `web/` directory). In development.

## Quick Start

To run the detector with the example configuration:

```bash
cd example
docker compose up -d
```
