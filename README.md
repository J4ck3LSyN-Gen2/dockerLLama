# dockerLamma

![Python 3.12](https://img.shields.io/badge/python-3.12-green)
![Ollama Supported](https://img.shields.io/badge/Ollama%20Supported-blue)
![MCP](https://img.shields.io/badge/Network%20Traffic%20Obfuscation-green)
![Version 0.0.3](https://img.shields.io/badge/Version%200.0.3-yellow)

---

Author: J4ck3LSyN

Version: 0.0.3

---

Hardened local Ollama deployment with a separate MCP gateway service.

- `ollama-node` runs the Ollama model runtime on an internal network.
- `mcp-gateway` is the only service exposed for app/tool integration.
- Both services are bound to localhost (`127.0.0.1`) by default.
- Model weights persist on the host under `./models`; Ollama runtime state is kept in a Docker volume.

## Architecture

- **Ollama service**: `ollama-node` (`ollama/ollama:latest`)
- **Gateway service**: `mcp-gateway` (FastAPI proxy in `src/main.py`)
- **Network isolation**:
  - `backendIsolated` (internal-only)
  - `frontendAccess` (for local client access)

## Prerequisites

- Linux host
- Docker Engine + `docker-compose` (legacy CLI is fine)
- NVIDIA GPU + drivers (required for GPU acceleration)
- NVIDIA container runtime toolkit (`nvidia-container-toolkit`)

**NOTE:** You will possibly need to create a `models` directory to allow for the ollama models.

## Quick Start

From the repo root:

### CPU mode (default / fallback-safe)

```bash
sudo docker-compose up -d --build
sudo docker-compose ps
```

### GPU mode (when NVIDIA runtime is healthy)

```bash
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
sudo docker-compose ps
```

## GPU-Ready Bring-Up Checklist (Do This First)

Run these in order before expecting fast inference:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
sudo docker-compose ps
sudo docker exec -it ollamaNode ollama ps
```

Expected result:

- `nvidia-smi` works on host
- CUDA test container sees the GPU
- `ollamaNode` is `Up (healthy)`
- `ollama ps` shows active runner after a request

Check logs:

```bash
sudo docker-compose logs -f ollama-node
sudo docker-compose logs -f mcp-gateway
```

## Pulling and Managing Models

Pull models directly inside the Ollama container:

```bash
sudo docker exec -it ollamaNode ollama pull llama3.1:8b
sudo docker exec -it ollamaNode ollama pull qwen2.5:7b
```

List available models:

```bash
sudo docker exec -it ollamaNode ollama list
```

See active runners:

```bash
sudo docker exec -it ollamaNode ollama ps
```

Remove a model:

```bash
sudo docker exec -it ollamaNode ollama rm qwen2.5:7b
```

Model files persist on host under `./models` via `OLLAMA_MODELS=/models`.
Ollama runtime state such as generated keys persists in the Docker volume `ollamaState` mounted at `/root/.ollama`.

### Target Lab Model (Abliterated)

Pull the model:

```bash
sudo docker exec -it ollamaNode ollama pull huihui_ai/qwen3.5-abliterated:9b-Claude
```

Confirm it is available:

```bash
sudo docker exec -it ollamaNode ollama list
```

Quick inference smoke test directly against Ollama:

```bash
curl -X POST http://127.0.0.1:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "huihui_ai/qwen3.5-abliterated:9b-Claude",
    "messages": [{"role":"user","content":"Reply with only: gpu_online"}],
    "stream": false
  }'
```

Gateway smoke test with the same model:

```bash
curl -X POST http://127.0.0.1:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "huihui_ai/qwen3.5-abliterated:9b-Claude",
    "messages": [{"role":"user","content":"Reply with only: gateway_online"}],
    "stream": false
  }'
```

## Gateway API Usage

Gateway endpoint:

- `POST http://127.0.0.1:8080/v1/chat`

Example:

```bash
curl -X POST http://127.0.0.1:8080/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:7b",
    "messages": [{"role":"user","content":"Hello"}],
    "stream": false
  }'
```

If you set `MCP_API_KEY` in compose, include:

```bash
-H "Authorization: Bearer <your_key>"
```

## NVIDIA / GPU Setup

### 1) Check what driver Ubuntu/Zorin recommends

Use these tools:

```bash
ubuntu-drivers devices
nvidia-detector
ubuntu-drivers list
```

Install the recommended **driver meta-package** (example):

```bash
sudo apt update
sudo apt --fix-broken install
sudo apt install -y nvidia-driver-580
sudo reboot
```

> Do not install both `nvidia-utils-XXX` and `nvidia-utils-XXX-server` together.
> Prefer `nvidia-driver-XXX` so dependencies stay consistent.

### 2) Verify NVIDIA userspace is installed

After reboot:

```bash
nvidia-smi
```

If `nvidia-smi` is missing, the driver stack is incomplete and Docker GPU mode will fail.

### 3) Configure Docker runtime for NVIDIA

```bash
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Test GPU passthrough in a container:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

If this command fails, fix host GPU runtime first before starting Ollama.

### CPU fallback mode

If GPU runtime breaks, start in CPU mode without the override file:

```bash
sudo docker-compose down
sudo docker-compose up -d --build
```

When GPU is repaired, switch back:

```bash
sudo docker-compose down
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
```

### 4) If you need to determine "which NVIDIA package should I install"

Use this decision path:

1. Run `ubuntu-drivers devices` and use the package marked `recommended`.
2. Install the matching `nvidia-driver-XXX` meta-package (not mixed utils/server pairs).
3. Reboot and verify with `nvidia-smi`.
4. Only then run Docker GPU tests and start compose.

Avoid this common mistake:

- Do **not** install `nvidia-utils-XXX` and `nvidia-utils-XXX-server` together.
- Do **not** mix unrelated major versions (example: `535` libs with `580` driver).

## Troubleshooting

### Error: `failed to initialize NVML: ERROR_LIBRARY_NOT_FOUND`

Cause: Docker can see NVIDIA toolkit, but host driver/NVML userspace is missing or mismatched.

Fix path:

1. Install a consistent NVIDIA driver package (`nvidia-driver-XXX`)
2. Reboot
3. Confirm `nvidia-smi` works on host
4. Reconfigure Docker runtime via `nvidia-ctk`
5. Retry compose bring-up

### Error: `open /root/.ollama/id_ed25519: permission denied`

Cause: Ollama is trying to generate runtime state inside `/root/.ollama`, but the host bind mount is not writable for that path.

Fix path:

1. Keep model weights on the host in `./models`
2. Keep `/root/.ollama` on a Docker-managed volume
3. Recreate the stack so the new volume layout is applied

Example:

```bash
sudo docker-compose down
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
```

### Error: `mkdir /models/blobs: permission denied`

Cause: the model directory is bind-mounted from a path under a private home directory, and dropping all Linux capabilities from `ollama-node` can prevent the container process from traversing or writing through that host path.

Fix path:

1. Do not drop all capabilities from `ollama-node` when using a host bind mount for models
2. Recreate the stack
3. If the host path is still restricted, ensure the parent path is traversable for the containerized process or move the model directory to a less restrictive path

Example:

```bash
sudo docker-compose down
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
```

### Error: `lookup registry.ollama.ai on 127.0.0.11:53: server misbehaving`

Cause: `ollama-node` is on an internal-only Docker network, so it cannot resolve or reach external registries to pull models.

Fix path:

1. Keep `backendIsolated` for private service-to-service traffic
2. Also attach `ollama-node` to a non-internal network for outbound DNS and HTTPS egress
3. Recreate the stack, then retry the `ollama pull`

Example:

```bash
sudo docker-compose down
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d --build
sudo docker exec -it ollamaNode ollama pull huihui_ai/qwen3.5-abliterated:9b-Claude
```

### Error: uppercase compose service names invalid

Service keys in compose must be lowercase for image-name derivation. Current file already uses lowercase service keys.

## Security Notes

- Services bind to localhost only (`127.0.0.1`) by default.
- `backendIsolated` is internal-only; `mcp-gateway` is the intended entry point.
- `mcp-gateway` drops Linux capabilities and runs read-only root fs with tmpfs for `/tmp`.
- Set `MCP_API_KEY` before exposing gateway beyond localhost.

## Thermal / CPU Tuning

Ollama can saturate all cores during inference, especially when a model does not fit fully in VRAM and spills to CPU.

Two independent knobs are configured in `docker-compose.yaml`:

| Setting | Where | Effect |
|---|---|---|
| `cpus: "4.0"` | `ollama-node` service | Hard Docker cap: container cannot consume more than N cores of CPU time |
| `OMP_NUM_THREADS=4` | `ollama-node` environment | Controls thread count inside llama.cpp (OpenMP). Most directly affects heat |
| `OLLAMA_NUM_PARALLEL=1` | `ollama-node` environment | Limits concurrent inference requests to 1, avoids compounding load |

To reduce heat, lower both values and restart the stack:

```bash
# In docker-compose.yaml, under ollama-node:
#   cpus: "2.0"
#   OMP_NUM_THREADS=2
sudo docker-compose down
sudo docker-compose -f docker-compose.yaml -f docker-compose.gpu.yaml up -d
```

Smaller models (3B or 4-bit quants) will also dramatically reduce CPU spill and heat vs. a 9B model.

## Remaining Recommended Work

The critical bugs are fixed, but these are the next high-value tasks:

1. Add `MCP_API_KEY` to compose environment and require auth for all clients.
2. Add request validation/rules in gateway for allowed models and max token/timeout limits.
3. Add log rotation (`json-file` max-size/max-file or journald) to avoid disk growth.
4. CPU fallback is now implemented via base compose + `docker-compose.gpu.yaml` override.
5. Pin image versions (instead of `latest`) for reproducible deployments.

## Stop / Reset

Stop stack:

```bash
sudo docker-compose down
```

Stop and remove volumes/networks for a clean reset:

```bash
sudo docker-compose down -v --remove-orphans
```
