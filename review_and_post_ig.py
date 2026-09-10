"""生成→確認→Instagram投稿までを一括で行うCLI

使い方:
  python review_and_post_ig.py --prompt "プロンプト" --caption "投稿キャプション"
  python review_and_post_ig.py --file generated/既存の画像.png --caption "投稿キャプション"
  python review_and_post_ig.py --file generated/既存の動画.mp4 --caption "..." --video
  python review_and_post_ig.py --file generated/... --caption "..." --product   # 商品紹介の投稿(PR表記necessary)

--productを付けると、キャプションの末尾に「プロフィールのリンクから」の誘導文と[PR]表記を自動で追加する
(景品表示法のステマ規制対応。Instagramはキャプション内のURLがクリックできないため、
実際のリンク先は楽天ROOM等をプロフィールのリンク欄に設定しておく前提)
"""
import argparse
import sys
import os
import json
import datetime

sys.stdout.reconfigure(encoding="utf-8")

from load_env import load_env
from generate_media import generate_image_forge, generate_video_ltx
from publish_media import publish_to_github_pages
from instagram_api import post_image, post_video

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.jsonl")

PRODUCT_DISCLOSURE = "\n\n気になった方はプロフィールのリンクから見てみてね\n[PR]"


def build_caption(text, is_product):
    return text + PRODUCT_DISCLOSURE if is_product else text


def append_log(record):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", help="Forgeで生成する場合の画像プロンプト")
    parser.add_argument("--file", help="生成済みファイルをそのまま使う場合のパス")
    parser.add_argument("--caption", required=True, help="投稿キャプション")
    parser.add_argument("--video", action="store_true", help="動画/リールとして投稿する")
    parser.add_argument("--duration", type=int, default=5, help="動画の長さ(秒、2〜20)")
    parser.add_argument("--product", action="store_true", help="商品紹介の投稿([PR]表記とプロフィールリンク誘導を自動で付ける)")
    args = parser.parse_args()

    caption = build_caption(args.caption, args.product)

    if args.file:
        media_path = args.file
    elif args.prompt:
        if args.video:
            print(f"動画生成中(LTX-2.5, {args.duration}秒)... 数分かかります")
            media_path = generate_video_ltx(args.prompt, duration=args.duration)[0]
        else:
            media_path = generate_image_forge(args.prompt)[0]
    else:
        print("--prompt か --file のどちらかを指定してください")
        sys.exit(1)

    print(f"生成物: {os.path.abspath(media_path)}")
    print(f"キャプション:\n{caption}")
    print("この内容で投稿しますか? [y/N]: ", end="")
    if input().strip().lower() != "y":
        print("投稿を中止しました。ファイルは残っています。")
        return

    env = load_env()
    public_url = publish_to_github_pages(env, media_path)
    print(f"公開URL: {public_url}")
    if args.video:
        post_id = post_video(env, caption, public_url)
    else:
        post_id = post_image(env, caption, public_url)

    append_log({
        "date": datetime.date.today().isoformat(),
        "platform": "instagram",
        "caption": caption,
        "product": args.product,
        "media_path": media_path,
        "post_id": post_id,
    })
    print(f"投稿成功: post_id={post_id}")


if __name__ == "__main__":
    main()
