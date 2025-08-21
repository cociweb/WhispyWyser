# WhispyWyser - Voice Assistant for Home Assistant

WhispyWyser is a flexible and efficient voice assistant for Home Assistant, leveraging Faster Whisper for speech recognition and the Wyoming protocol for seamless integration. It supports both CPU and CUDA architectures for optimized performance.

## Features

- 🎙️ High-accuracy speech-to-text with Faster Whisper
- 🏠 Deep Home Assistant integration
- 🐳 Docker support for easy deployment
- 🚀 GPU acceleration support (CUDA)
- 🔌 Wyoming protocol for extensibility
- 🔒 Secure authentication with long-lived tokens

## Prerequisites

- Docker and Docker Compose
- Home Assistant instance (local or remote)
- NVIDIA GPU with drivers (for CUDA support)

## Quick Start

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/whispywyser.git
   cd whispywyser
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   nano .env
   ```

3. **Start the service**
   ```bash
   # For CPU
   docker-compose up -d whispywyser-cpu
   
   # For GPU (CUDA)
   docker-compose up -d whispywyser-gpu
   ```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HA_TOKEN` | ✅ | Home Assistant long-lived access token |
| `HOME_ASSISTANT_URL` | ✅ | URL of your Home Assistant instance |
| `HF_TOKEN` | ❌ | Hugging Face Hub token (for private models) |
| `MODEL` | ❌ | Model name (default: `openai/whisper-large-v3`) |
| `DEVICE` | ❌ | `cuda` or `cpu` (auto-detected) |
| `LANGUAGE` | ❌ | Language code (e.g., `en`, `de`) |

### Generating a Long-Lived Access Token

1. In Home Assistant, click on your profile
2. Scroll down to "Long-Lived Access Tokens"
3. Click "Create Token"
4. Copy the token and add it to your `.env` file

## Docker Compose

The project includes two services:

1. **whispywyser-gpu**: For systems with NVIDIA GPU
2. **whispywyser-cpu**: For CPU-only systems

### Volumes

- `/data`: Stores models and configuration

### Ports

- `10300`: Wyoming protocol port

## Development

### Building the Image

```bash
# For CPU
docker-compose build whispywyser-cpu

# For GPU
docker-compose build whispywyser-gpu
```

### Running Tests

```bash
docker-compose run whispywyser-cpu python -m pytest
```

## Troubleshooting

### Common Issues

1. **CUDA errors**
   - Ensure NVIDIA drivers are installed
   - Run `nvidia-smi` to verify GPU detection
   - Check Docker has access to GPU: `docker run --gpus all nvidia/cuda:11.0-base nvidia-smi`

2. **Connection to Home Assistant**
   - Verify `HOME_ASSISTANT_URL` is correct
   - Check if the token has the right permissions
   - Ensure Home Assistant is accessible from the container

## License

MIT

## Acknowledgements

- [Faster Whisper](https://github.com/guillaumekln/faster-whisper)
- [Wyoming Protocol](https://github.com/rhasspy/wyoming)
- [Home Assistant](https://www.home-assistant.io/)
