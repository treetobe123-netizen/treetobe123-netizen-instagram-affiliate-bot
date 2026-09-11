"""HiggsFieldで生成した画像(公開URL)をInstagramに投稿するCLI

HiggsField移行後の流れ:
  1. pick_product.py で商品を選ぶ
  2. (Claude側)HiggsFieldのMCPツールで画像を生成し、公開URLを得る
  3. このスクリプトで投稿・コメント追加・ログ記録まで行う

使い方:
  python post_result.py --image-url "https://.../xxx.png" --caption "本文" \
      --item-json '{"name": "...", "url": "...", ...}' [--comment "コメント文"]
"""
import argparse
import datetime
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from load_env import load_env
from instagram_api import post_image, post_comment
from review_and_post_ig import build_caption, append_log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-url", required=True, help="HiggsFieldなどで生成した画像の公開URL")
    parser.add_argument("--caption", required=True, help="投稿本文(PR表記は--productで自動付与)")
    parser.add_argument("--item-json", help="pick_product.pyが出力したitemのJSON文字列(ログ記録用)")
    parser.add_argument("--comment", help="投稿後に追加するコメント文(商品名・誘導など)")
    parser.add_argument("--product", action="store_true", default=True, help="商品紹介投稿として[PR]表記を付ける(デフォルトON)")
    args = parser.parse_args()

    env = load_env()
    caption = build_caption(args.caption, is_product=args.product)

    post_id = post_image(env, caption, args.image_url)
    print(f"投稿成功: post_id={post_id}")

    record = {
        "date": datetime.date.today().isoformat(),
        "platform": "instagram",
        "caption": caption,
        "product": args.product,
        "media_path": args.image_url,
        "post_id": post_id,
    }
    if args.item_json:
        record["item"] = json.loads(args.item_json)

    if args.comment:
        comment_id = post_comment(env, post_id, args.comment)
        record["comment"] = args.comment
        record["comment_id"] = comment_id
        print(f"コメント追加: comment_id={comment_id}")

    append_log(record)


if __name__ == "__main__":
    main()
