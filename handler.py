import base64
import os
import tempfile
import urllib.request
import uuid

import runpod

import generate


def _write_base64_to_file(data_b64, suffix):
    file_id = uuid.uuid4().hex
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{suffix}")
    with open(file_path, "wb") as file:
        file.write(base64.b64decode(data_b64))
    return file_path


def _download_to_file(url, suffix):
    file_id = uuid.uuid4().hex
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{suffix}")
    urllib.request.urlretrieve(url, file_path)
    return file_path


def _build_args(payload, image_path, output_path):
    return generate.argparse.Namespace(
        task=payload.get("task", "i2v-A14B"),
        size=payload.get("size", "480*832"),
        frame_num=payload.get("frame_num"),
        ckpt_dir=payload.get("ckpt_dir") or os.getenv("LINGBOT_CKPT_DIR"),
        offload_model=payload.get("offload_model"),
        ulysses_size=payload.get("ulysses_size", 1),
        t5_fsdp=payload.get("t5_fsdp", False),
        t5_cpu=payload.get("t5_cpu", False),
        dit_fsdp=payload.get("dit_fsdp", False),
        save_file=output_path,
        prompt=payload.get("prompt"),
        use_prompt_extend=payload.get("use_prompt_extend", False),
        prompt_extend_method=payload.get("prompt_extend_method", "local_qwen"),
        prompt_extend_model=payload.get("prompt_extend_model"),
        prompt_extend_target_lang=payload.get("prompt_extend_target_lang", "zh"),
        base_seed=payload.get("seed", 42),
        image=image_path,
        action_path=payload.get("action_path"),
        sample_solver=payload.get("sample_solver", "unipc"),
        sample_steps=payload.get("sample_steps"),
        sample_shift=payload.get("sample_shift"),
        sample_guide_scale=payload.get("sample_guide_scale"),
        convert_model_dtype=payload.get("convert_model_dtype", False),
    )


def handler(event):
    payload = event.get("input", {})
    if not payload.get("prompt"):
        return {"error": "Missing required field: prompt"}

    image_path = None
    if payload.get("image_base64"):
        image_path = _write_base64_to_file(payload["image_base64"], ".jpg")
    elif payload.get("image_url"):
        image_path = _download_to_file(payload["image_url"], ".jpg")

    if payload.get("task", "i2v-A14B") == "i2v-A14B" and image_path is None:
        return {"error": "Missing image. Provide image_base64 or image_url."}

    if not (payload.get("ckpt_dir") or os.getenv("LINGBOT_CKPT_DIR")):
        return {"error": "Missing ckpt_dir. Provide ckpt_dir or set LINGBOT_CKPT_DIR."}

    output_dir = os.path.join(tempfile.gettempdir(), "lingbot_outputs")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{uuid.uuid4().hex}.mp4")

    args = _build_args(payload, image_path, output_path)
    generate._validate_args(args)
    generate.generate(args)

    response = {
        "output_path": output_path,
        "file_size_bytes": os.path.getsize(output_path),
    }

    if payload.get("return_base64"):
        with open(output_path, "rb") as file:
            response["output_base64"] = base64.b64encode(file.read()).decode("utf-8")

    return response


runpod.serverless.start({"handler": handler})
