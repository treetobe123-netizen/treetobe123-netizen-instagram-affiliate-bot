"""ローカルのStable Diffusion系ツールで画像/動画を生成するモジュール

- generate_image_forge: Stable Diffusion WebUI Forgeのtxt2img API(要 --api 起動)
- generate_with_workflow: ComfyUIのAPI(要ComfyUI起動)。ComfyUIの画面で
  ワークフローを組んだ後、メニューの「Save (API Format)」でJSON書き出ししたものを渡す
"""
import urllib.request
import urllib.parse
import json
import base64
import os
import time
import datetime
import uuid

FORGE_BASE = "http://127.0.0.1:7860"
COMFY_BASE = "http://127.0.0.1:8188"


def generate_image_forge(prompt, negative_prompt="", steps=25, width=1024, height=1024, out_dir="generated"):
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "width": width,
        "height": height,
    }
    req = urllib.request.Request(
        f"{FORGE_BASE}/sdapi/v1/txt2img",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        result = json.loads(res.read().decode())

    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = []
    for i, b64 in enumerate(result["images"]):
        path = os.path.join(out_dir, f"{timestamp}_{i}.png")
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64.split(",", 1)[-1]))
        paths.append(path)
    return paths


def _queue_prompt(workflow):
    client_id = str(uuid.uuid4())
    payload = {"prompt": workflow, "client_id": client_id}
    req = urllib.request.Request(
        f"{COMFY_BASE}/prompt",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode())["prompt_id"]


def _wait_for_result(prompt_id, timeout=900, interval=2):
    waited = 0
    while waited < timeout:
        with urllib.request.urlopen(f"{COMFY_BASE}/history/{prompt_id}", timeout=30) as res:
            history = json.loads(res.read().decode())
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(interval)
        waited += interval
    raise TimeoutError(f"ComfyUIの処理がタイムアウトしました(prompt_id={prompt_id})")


def _download_outputs(history_entry, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = []
    for node_output in history_entry.get("outputs", {}).values():
        for key in ("images", "gifs", "videos"):
            for item in node_output.get(key, []):
                params = urllib.parse.urlencode({
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                out_path = os.path.join(out_dir, f"{timestamp}_{item['filename']}")
                urllib.request.urlretrieve(f"{COMFY_BASE}/view?{params}", out_path)
                paths.append(out_path)
    return paths


def generate_with_workflow(workflow_path, out_dir="generated"):
    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)
    prompt_id = _queue_prompt(workflow)
    history_entry = _wait_for_result(prompt_id)
    return _download_outputs(history_entry, out_dir)


LTX_WORKFLOW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows", "ltx_text_to_video.json")
LTX_PROMPT_NODE_ID = "405:376"


def generate_video_ltx(prompt, out_dir="generated", workflow_path=LTX_WORKFLOW_PATH, prompt_node_id=LTX_PROMPT_NODE_ID):
    """LTX-2.5のtext-to-videoワークフロー(ComfyUIの画面でExport (API)して保存したもの)で動画を生成する"""
    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)
    workflow[prompt_node_id]["inputs"]["value"] = prompt
    prompt_id = _queue_prompt(workflow)
    history_entry = _wait_for_result(prompt_id, timeout=1800, interval=3)
    return _download_outputs(history_entry, out_dir)
