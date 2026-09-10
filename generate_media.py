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
import subprocess
import shutil

FORGE_BASE = "http://127.0.0.1:7860"
COMFY_BASE = "http://127.0.0.1:8188"

FFMPEG = shutil.which("ffmpeg") or (
    r"C:\Users\treet\AppData\Local\Microsoft\WinGet\Packages"
    r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
)


def concat_videos(paths, out_dir="generated"):
    """複数の動画ファイルを1本につなげる(すべて再エンコードするので、解像度/フレームレートが
    多少違うクリップ同士でも結合できる)"""
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    list_path = os.path.join(out_dir, f"{timestamp}_concat_list.txt")
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            escaped = os.path.abspath(p).replace("'", "'\\''")
            f.write(f"file '{escaped}'\n")

    out_path = os.path.join(out_dir, f"{timestamp}_concat.mp4")
    subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
         "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", out_path],
        check=True, capture_output=True,
    )
    os.remove(list_path)
    return out_path


def extract_last_frame(video_path, out_dir="generated"):
    """動画の最後のフレームを1枚の画像として書き出す(次クリップの開始フレームに使う)"""
    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"{timestamp}_lastframe.png")
    subprocess.run(
        [FFMPEG, "-y", "-sseof", "-1", "-i", video_path, "-update", "1", "-q:v", "2", out_path],
        check=True, capture_output=True,
    )
    return out_path


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


def _upload_image(path):
    """ローカル画像をComfyUIのinput領域にアップロードし、ComfyUI側でのファイル名を返す"""
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        file_data = f.read()
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{COMFY_BASE}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode())["name"]


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
LTX_DURATION_NODE_ID = "405:362"


def generate_video_ltx(prompt, duration=5, out_dir="generated", workflow_path=LTX_WORKFLOW_PATH,
                        prompt_node_id=LTX_PROMPT_NODE_ID, duration_node_id=LTX_DURATION_NODE_ID):
    """LTX-2.5のtext-to-videoワークフロー(ComfyUIの画面でExport (API)して保存したもの)で動画を生成する。
    durationは秒数(2〜20。12秒を超えると自動的に720p/1080pに解像度が下がる仕様)"""
    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)
    workflow[prompt_node_id]["inputs"]["value"] = prompt
    workflow[duration_node_id]["inputs"]["value"] = duration
    prompt_id = _queue_prompt(workflow)
    # 長尺になるほど生成時間も伸びるため、秒数に応じてタイムアウトを延ばす
    timeout = max(1800, duration * 300)
    history_entry = _wait_for_result(prompt_id, timeout=timeout, interval=3)
    return _download_outputs(history_entry, out_dir)


LTX_I2V_WORKFLOW_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows", "ltx_image_to_video.json")
LTX_I2V_PROMPT_NODE_ID = "398:376"
LTX_I2V_DURATION_NODE_ID = "398:362"
LTX_I2V_IMAGE_NODE_ID = "395"


def generate_video_ltx_i2v(prompt, image_path, duration=5, out_dir="generated", workflow_path=LTX_I2V_WORKFLOW_PATH,
                            prompt_node_id=LTX_I2V_PROMPT_NODE_ID, duration_node_id=LTX_I2V_DURATION_NODE_ID,
                            image_node_id=LTX_I2V_IMAGE_NODE_ID):
    """LTX-2.5のimage-to-videoワークフローで、開始フレーム画像を固定したまま動画を生成する。
    複数クリップで同じimage_pathを使えば、シーンをまたいでキャラクターの見た目が揃う"""
    uploaded_name = _upload_image(image_path)
    with open(workflow_path, encoding="utf-8") as f:
        workflow = json.load(f)
    workflow[image_node_id]["inputs"]["image"] = uploaded_name
    workflow[prompt_node_id]["inputs"]["value"] = prompt
    workflow[duration_node_id]["inputs"]["value"] = duration
    prompt_id = _queue_prompt(workflow)
    timeout = max(1800, duration * 300)
    history_entry = _wait_for_result(prompt_id, timeout=timeout, interval=3)
    return _download_outputs(history_entry, out_dir)
