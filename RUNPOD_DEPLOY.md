# RunPod Serverless Deployment Guide for LingBot-World

## Overview - Pay-Per-Use Model

This guide sets up **serverless GPU compute** - you only pay when videos are generated.

### Cost Comparison

| Model | Monthly Cost (100 users) | Monthly Cost (idle) |
|-------|--------------------------|---------------------|
| Dedicated GPU | $8,000-13,000 | $8,000-13,000 |
| **Serverless** | **~$150-300** | **$0** |

### Per-Video Cost Estimate

| GPU | Price/Hour | 5-sec video | 20-sec video | 60-sec video |
|-----|------------|-------------|--------------|--------------|
| A100 80GB | $1.99/hr | ~$0.07 | ~$0.15 | ~$0.33 |
| H100 80GB | $3.79/hr | ~$0.13 | ~$0.25 | ~$0.63 |

---

## Prerequisites

1. RunPod account (https://runpod.io)
2. Docker installed locally
3. Docker Hub account (free)

---

## Step 1: Create Network Volume for Model

The model (~160GB) needs persistent storage.

1. Go to https://www.runpod.io/console/user/storage
2. Click **"New Network Volume"**
3. Configure:
   - **Name**: `lingbot-models`
   - **Size**: **250 GB**
   - **Region**: US-East or EU (closest to users)
4. Click **"Create"**

**Cost**: ~$0.07/GB/month = ~$17.50/month for storage

---

## Step 2: Download Model to Volume

Start a **cheap temporary pod** to download:

1. Go to https://www.runpod.io/console/pods
2. Click **"Deploy"**
3. Select cheapest GPU (RTX 3090 is fine, ~$0.30/hr)
4. **Attach** your `lingbot-models` volume
5. Click **"Deploy"**
6. Click **"Connect"** → **"Start Web Terminal"**
7. Run these commands:

```bash
# Install huggingface CLI
pip install "huggingface_hub[cli]"

# Download model (~30-60 min depending on connection)
huggingface-cli download robbyant/lingbot-world-base-cam \
    --local-dir /runpod-volume/lingbot-world-base-cam

# Verify download
du -sh /runpod-volume/lingbot-world-base-cam
# Should show ~160GB
```

8. **Stop the pod** (click "Stop" - don't delete!)
9. **Terminate the pod** after confirming model is saved

**Cost**: ~$0.50-1.00 one-time for download

---

## Step 3: Build & Push Docker Image

**Important**: Building requires an x86_64 Linux machine with CUDA. If you're on Mac/Windows, build on RunPod.

### Option A: Build on RunPod Pod (Recommended)

1. Start a **GPU Pod** on RunPod:
   - Go to https://www.runpod.io/console/pods
   - Deploy a cheap GPU (RTX 3090, ~$0.30/hr)
   - Select template: **RunPod Pytorch** (has Docker)
   - Attach your `lingbot-models` volume

2. SSH into the pod and clone your code:
```bash
# Clone or copy your code
git clone https://github.com/YOUR_USERNAME/lingbot-world.git
cd lingbot-world

# Or use SCP to copy files
```

3. Build and push:
```bash
# Set your Docker Hub username
export DOCKER_USERNAME=alexandergorny

# Login to Docker Hub
docker login

# Build (10-15 min with CUDA compilation)
docker build -t $DOCKER_USERNAME/lingbot-world:latest .

# Push
docker push $DOCKER_USERNAME/lingbot-world:latest
```

4. **Stop the pod** after pushing

### Option B: Build Locally (Linux x86_64 with CUDA only)

```bash
cd /Volumes/Monster/Development/KIAcademy/FluxAI/LingBot/lingbot-world

docker login
docker build -t alexandergorny/lingbot-world:latest .
docker push alexandergorny/lingbot-world:latest
```

### Option C: Use GitHub Actions with Self-Hosted Runner

Set up a self-hosted runner on a GPU machine and use the workflow in `.github/workflows/docker-build.yml`.

---

## Step 4: Create Serverless Endpoint

1. Go to https://www.runpod.io/console/serverless
2. Click **"New Endpoint"**
3. Configure:

### Basic Settings
| Setting | Value |
|---------|-------|
| **Name** | `lingbot-world` |
| **Container Image** | `YOUR_DOCKERHUB_USERNAME/lingbot-world:latest` |

### GPU Selection
| Setting | Value |
|---------|-------|
| **GPU Type** | A100 80GB (recommended) or H100 |

### Scaling Settings (Pay-Per-Use)
| Setting | Value | Why |
|---------|-------|-----|
| **Min Workers** | `0` | **$0 when idle** |
| **Max Workers** | `3` | Handle concurrent users |
| **Idle Timeout** | `60` seconds | Quick scale-down |
| **Execution Timeout** | `900` seconds | 15 min for long videos |

### Volume
| Setting | Value |
|---------|-------|
| **Network Volume** | `lingbot-models` |
| **Mount Path** | `/runpod-volume` |

### Environment Variables
| Key | Value |
|-----|-------|
| `LINGBOT_CKPT_DIR` | `/runpod-volume/lingbot-world-base-cam` |

4. Click **"Create Endpoint"**

---

## Step 5: Get API Credentials

1. **Endpoint ID**: Copy from the endpoint dashboard (e.g., `abc123xyz`)
2. **API Key**: Go to https://www.runpod.io/console/user/settings → API Keys

---

## Step 6: Add to Scenica (Vercel)

```bash
cd /Volumes/Monster/Development/KIAcademy/FluxAI/LingBot/scenica

# Add RunPod API Key
npx vercel env add RUNPOD_API_KEY production
# Paste your API key

# Add Endpoint ID  
npx vercel env add RUNPOD_ENDPOINT_ID production
# Paste your endpoint ID

# Redeploy
npx vercel --prod
```

---

## Step 7: Test the Endpoint

### Submit a job:
```bash
curl -X POST "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "prompt": "A cinematic flythrough of a neon city at sunset",
      "image_url": "https://example.com/your-image.jpg",
      "size": "480*832",
      "frame_num": 81
    }
  }'
```

Response:
```json
{"id": "job-abc123", "status": "IN_QUEUE"}
```

### Check status:
```bash
curl "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/status/job-abc123" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

---

## Monthly Cost Breakdown

### MVP Phase (0-100 users)
| Item | Cost |
|------|------|
| Network Volume (250GB) | $17.50 |
| GPU compute (est. 500 videos) | $35-100 |
| **Total** | **$50-120/month** |

### Growth Phase (100-1000 users)
| Item | Cost |
|------|------|
| Network Volume | $17.50 |
| GPU compute (est. 5000 videos) | $350-1000 |
| **Total** | **$400-1000/month** |

### When to Switch to Dedicated
Consider dedicated GPUs when:
- Consistent 50+ concurrent users
- Cold start latency is unacceptable
- Monthly serverless cost exceeds $5,000

---

## Troubleshooting

### Cold start is slow (30-60 sec)
This is normal for serverless. Options:
- Set `Min Workers: 1` (~$1,500/month) to keep one GPU warm
- Show loading UI to users explaining "Starting GPU..."

### Model not found
```
Error: Checkpoint directory not found
```
- Verify model at `/runpod-volume/lingbot-world-base-cam`
- Check `LINGBOT_CKPT_DIR` env var

### Out of memory
```
CUDA out of memory
```
- Use H100 for 60-second videos
- Request includes `t5_cpu: true` automatically

### Job timeout
- Increase `Execution Timeout` to 900+ seconds
- 60-second videos can take 8-10 minutes

---

## API Reference

### Input Parameters
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `prompt` | string | Yes | - | Text description |
| `image_url` | string | Yes* | - | URL to input image |
| `image_base64` | string | Yes* | - | Base64 encoded image |
| `size` | string | No | `480*832` | Resolution |
| `frame_num` | int | No | `81` | Frames (4n+1) |
| `seed` | int | No | `-1` | Random seed |
| `upload_url` | string | No | - | Presigned URL for result |

*Either `image_url` or `image_base64` required

### Frame Options
| Frames | Duration | Use Case |
|--------|----------|----------|
| 81 | 5 sec | TikTok, quick clips |
| 161 | 10 sec | Instagram Reels |
| 321 | 20 sec | YouTube Shorts |
| 641 | 40 sec | Extended scenes |
| 961 | 60 sec | Full scenes |
