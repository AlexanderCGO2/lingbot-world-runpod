"""
RunPod Serverless Handler for LingBot-World Video Generation

This handler receives generation requests from the Scenica web app,
generates videos using the LingBot-World model, and uploads results
to a provided URL (e.g., Vercel Blob presigned URL).
"""

import base64
import os
import tempfile
import time
import traceback
import urllib.request
import uuid
from urllib.parse import urlparse

import requests
import runpod

import generate


def _write_base64_to_file(data_b64: str, suffix: str) -> str:
    """Write base64 data to a temporary file."""
    file_id = uuid.uuid4().hex
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{suffix}")
    with open(file_path, "wb") as file:
        file.write(base64.b64decode(data_b64))
    return file_path


def _download_to_file(url: str, suffix: str) -> str:
    """Download a file from URL to a temporary file."""
    file_id = uuid.uuid4().hex
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{suffix}")
    urllib.request.urlretrieve(url, file_path)
    return file_path


def _upload_file(file_path: str, upload_url: str) -> dict:
    """Upload a file to a presigned URL (e.g., Vercel Blob)."""
    with open(file_path, "rb") as f:
        file_data = f.read()
    
    # Determine content type
    content_type = "video/mp4"
    
    response = requests.put(
        upload_url,
        data=file_data,
        headers={"Content-Type": content_type},
        timeout=300,  # 5 minute timeout for large files
    )
    
    if response.status_code not in (200, 201):
        raise Exception(f"Upload failed with status {response.status_code}: {response.text}")
    
    return {
        "status_code": response.status_code,
        "uploaded_bytes": len(file_data),
    }


def _build_args(payload: dict, image_path: str, output_path: str):
    """Build argument namespace for generate.py."""
    return generate.argparse.Namespace(
        task=payload.get("task", "i2v-A14B"),
        size=payload.get("size", "480*832"),
        frame_num=payload.get("frame_num", 81),
        ckpt_dir=payload.get("ckpt_dir") or os.getenv("LINGBOT_CKPT_DIR"),
        offload_model=payload.get("offload_model", True),
        ulysses_size=payload.get("ulysses_size", 1),
        t5_fsdp=payload.get("t5_fsdp", False),
        t5_cpu=payload.get("t5_cpu", True),  # Default to CPU for T5 to save VRAM
        dit_fsdp=payload.get("dit_fsdp", False),
        save_file=output_path,
        prompt=payload.get("prompt"),
        use_prompt_extend=payload.get("use_prompt_extend", False),
        prompt_extend_method=payload.get("prompt_extend_method", "local_qwen"),
        prompt_extend_model=payload.get("prompt_extend_model"),
        prompt_extend_target_lang=payload.get("prompt_extend_target_lang", "zh"),
        base_seed=payload.get("seed", -1),  # Random seed by default
        image=image_path,
        action_path=payload.get("action_path"),
        sample_solver=payload.get("sample_solver", "unipc"),
        sample_steps=payload.get("sample_steps"),
        sample_shift=payload.get("sample_shift"),
        sample_guide_scale=payload.get("sample_guide_scale"),
        convert_model_dtype=payload.get("convert_model_dtype", False),
    )


def handler(event: dict) -> dict:
    """
    Main handler for RunPod serverless.
    
    Expected input payload:
    {
        "prompt": str,              # Required: Text description
        "image_url": str,           # Required: URL to input image
        "image_base64": str,        # Alternative: Base64 encoded image
        "size": str,                # Optional: "480*832", "720*1280", etc.
        "frame_num": int,           # Optional: Number of frames (4n+1)
        "upload_url": str,          # Optional: Presigned URL to upload result
        "seed": int,                # Optional: Random seed (-1 for random)
        "return_base64": bool,      # Optional: Return video as base64
    }
    
    Returns:
    {
        "output_url": str,          # URL where video was uploaded (if upload_url provided)
        "output_path": str,         # Local path to generated video
        "file_size_bytes": int,     # Size of generated video
        "duration_seconds": float,  # Generation time
        "output_base64": str,       # Base64 video (if return_base64=True)
    }
    """
    start_time = time.time()
    payload = event.get("input", {})
    
    # Validate required fields
    if not payload.get("prompt"):
        return {"error": "Missing required field: prompt"}

    # Handle input image
    image_path = None
    if payload.get("image_base64"):
        image_path = _write_base64_to_file(payload["image_base64"], ".jpg")
    elif payload.get("image_url"):
        try:
            image_path = _download_to_file(payload["image_url"], ".jpg")
        except Exception as e:
            return {"error": f"Failed to download image: {str(e)}"}

    # Validate image for i2v task
    task = payload.get("task", "i2v-A14B")
    if task == "i2v-A14B" and image_path is None:
        return {"error": "Missing image. Provide image_base64 or image_url."}

    # Validate checkpoint directory
    ckpt_dir = payload.get("ckpt_dir") or os.getenv("LINGBOT_CKPT_DIR")
    if not ckpt_dir:
        return {"error": "Missing ckpt_dir. Provide ckpt_dir or set LINGBOT_CKPT_DIR env var."}
    
    if not os.path.isdir(ckpt_dir):
        return {"error": f"Checkpoint directory not found: {ckpt_dir}"}

    # Validate frame_num (must be 4n+1)
    frame_num = payload.get("frame_num", 81)
    if (frame_num - 1) % 4 != 0:
        return {"error": f"frame_num must be 4n+1 (e.g., 17, 81, 161, 321). Got: {frame_num}"}

    # Prepare output path
    output_dir = os.path.join(tempfile.gettempdir(), "lingbot_outputs")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.mp4")

    try:
        # Build arguments and run generation
        args = _build_args(payload, image_path, output_path)
        generate._validate_args(args)
        
        print(f"Starting generation: {payload.get('size', '480*832')}, {frame_num} frames")
        generate.generate(args)
        print(f"Generation complete: {output_path}")

        # Verify output was created
        if not os.path.exists(output_path):
            return {"error": "Generation completed but output file not found"}

        file_size = os.path.getsize(output_path)
        duration = time.time() - start_time

        response = {
            "output_path": output_path,
            "file_size_bytes": file_size,
            "duration_seconds": round(duration, 2),
            "frame_num": frame_num,
            "size": payload.get("size", "480*832"),
        }

        # Upload to presigned URL if provided
        if payload.get("upload_url"):
            try:
                upload_result = _upload_file(output_path, payload["upload_url"])
                response["upload_status"] = "success"
                response["output_url"] = payload["upload_url"].split("?")[0]  # URL without query params
            except Exception as e:
                response["upload_status"] = "failed"
                response["upload_error"] = str(e)

        # Return base64 if requested
        if payload.get("return_base64"):
            with open(output_path, "rb") as f:
                response["output_base64"] = base64.b64encode(f.read()).decode("utf-8")

        # Clean up
        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
            if os.path.exists(output_path):
                os.remove(output_path)
        except Exception:
            pass  # Ignore cleanup errors

        return response

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Generation error: {error_trace}")
        return {
            "error": str(e),
            "traceback": error_trace,
            "duration_seconds": round(time.time() - start_time, 2),
        }


# Start the RunPod serverless handler
runpod.serverless.start({"handler": handler})
