"""ローカルPC(Windowsタスクスケジューラ)で毎日実行する画像生成+キュー登録スクリプト

HiggsField(有料プラン必須になったため)の代わりに、ローカルのStable Diffusion Forgeで
画像生成する。GitHub Actions側の「商品選定(pick-product.yml)」「投稿(post-to-instagram.yml)」
の2ステップはそのまま流用し、真ん中のHiggsFieldクラウドルーティンだけをこのスクリプトに置き換える。

前提: Forgeが http://127.0.0.1:7860 で --api 付きで起動していること

使い方:
  python generate_daily_post.py
"""
import datetime
import json
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

from load_env import load_env
from generate_media import generate_image_forge
from publish_media import publish_to_github_pages
from caption_templates import build_template_caption, build_template_comment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_TODAY = os.path.join(BASE_DIR, "queue", "today_item.json")
QUEUE_READY = os.path.join(BASE_DIR, "queue", "ready_to_post.json")


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
