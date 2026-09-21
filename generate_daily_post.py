"""ローカルPC(Windowsタスクスケジューラ)で毎日実行する画像生成+キュー登録スクリプト

HiggsField(有料プラン必須になったため)の代わりに、ローカルのStable Diffusion Forgeで
画像生成する。GitHub Actions側の「商品選定(pick-product.yml)」「投稿(post-to-instagram.yml)」
の2ステップはそのまま流用し、真ん中のHiggsFieldクラウドルーティンだけをこのスクリプトに置き換える。

Forgeが起動していなければ自動で起動を試みる(StabilityMatrix管理下の
D:\Data\Packages\Stable Diffusion WebUI Forge を想定)。タスクスケジューラでの
無人実行では、誰かがForgeを手動で開き忘れていると失敗し続けるため、
この自動起動が要になる(2026-09-21、TikTok側の同種の障害を踏まえて追加)。

使い方:
  python generate_daily_post.py
"""
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")

from load_env import load_env
from generate_media import generate_image_forge
from publish_media import publish_to_github_pages
from caption_templates import build_template_caption, build_template_comment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_TODAY = os.path.join(BASE_DIR, "queue", "today_item.json")
QUEUE_READY = os.path.join(BASE_DIR, "queue", "ready_to_post.json")

FORGE_URL = "http://127.0.0.1:7860"
FORGE_DIR = r"D:\Data\Packages\Stable Diffusion WebUI Forge"


def _forge_alive():
    try:
        urllib.request.urlopen(f"{FORGE_URL}/sdapi/v1/sd-models", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


def ensure_forge_running(timeout=240):
    if _forge_alive():
        print("Forge: 起動済み")
        return
    print("Forge: 未起動のため自動起動します...")
    python_exe = os.path.join(FORGE_DIR, "venv", "Scripts", "python.exe")
    log_path = os.path.join(BASE_DIR, "forge_startup.log")
    with open(log_path, "a", encoding="utf-8") as log_file:
        subprocess.Popen(
            [python_exe, "launch.py", "--api", "--nowebui"],
            cwd=FORGE_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    waited = 0
    while waited < timeout:
        if _forge_alive():
            print(f"Forge: 起動確認できました({waited}秒待機)")
            return
        time.sleep(5)
        waited += 5
    raise RuntimeError(f"Forgeが{timeout}秒待っても起動しませんでした。forge_startup.logを確認してください")


def build_prompt(item):
    return (
        f"soft pastel product photography flat lay, {item['name'][:60]}, "
        "cozy japanese home aesthetic, warm natural light, no text, no logo, no watermark"
    )


def git(*args):
    subprocess.run(["git", *args], cwd=BASE_DIR, check=True)


def git_push_with_retry(max_retries=5):
    """他の自動投稿(post-to-instagram.yml側のlog.jsonlコミット等)との競合に備え、
    pull --rebase→push をリトライする"""
    for attempt in range(max_retries):
        subprocess.run(["git", "pull", "--rebase"], cwd=BASE_DIR, check=True)
        result = subprocess.run(["git", "push"], cwd=BASE_DIR)
        if result.returncode == 0:
            return
    raise RuntimeError(f"instagram-affiliate-botへのpushが{max_retries}回失敗しました")


def main():
    subprocess.run(["git", "pull"], cwd=BASE_DIR, check=True)

    if not os.path.exists(QUEUE_TODAY):
        print("今日はまだ queue/today_item.json がありません。何もせず終了します。")
        return

    with open(QUEUE_TODAY, encoding="utf-8") as f:
        today = json.load(f)
    item = today["item"]

    env = load_env()

    ensure_forge_running()

    print(f"画像生成中(Forge): {item['name'][:40]}...")
    prompt = build_prompt(item)
    local_path = generate_image_forge(prompt)[0]
    print(f"生成完了: {local_path}")

    public_url = publish_to_github_pages(env, local_path)
    print(f"公開URL: {public_url}")

    caption = build_template_caption(item)
    comment = build_template_comment(item)

    ready = {
        "image_url": public_url,
        "caption": caption,
        "comment": comment,
        "item": item,
        "product": True,
    }
    with open(QUEUE_READY, "w", encoding="utf-8") as f:
        json.dump(ready, f, ensure_ascii=False, indent=2)

    os.remove(QUEUE_TODAY)

    git("add", "queue/ready_to_post.json", "queue/today_item.json")
    git("commit", "-m", f"queue: ready to post {datetime.date.today().isoformat()} (local Forge)")
    git_push_with_retry()
    print("push完了。post-to-instagram.ymlが自動起動します。")


if __name__ == "__main__":
    main()
