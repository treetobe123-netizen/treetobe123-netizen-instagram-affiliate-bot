"""HiggsFieldで生成した画像(公開URL)をInstagramに投稿するCLI

3段階のバトンリレー構成(IG/楽天トークンをクラウドルーティンに渡せないための設計):
  1. [GitHub Actions・secrets] pick_product.py で商品を選び queue/today_item.json に書く
  2. [クラウドルーティン・HiggsField MCP] それを読んで画像生成・キャプション作成し、
     queue/ready_to_post.json に書いてpush(トークン不要)
  3. [GitHub Actions・secrets] ready_to_post.jsonのpushをトリガーに、このスクリプトが
     --from-queue で読み込んで投稿・コメント・ログ記録まで行う

使い方:
  python post_result.py --from-queue queue/ready_to_post.json
  python post_result.py --image-url "https://.../xxx.png" --caption "本文" \
      --item-json '{"name": "...", "url": "...", ...}' [--comment "コメント文"]
"""
import argparse
import datetime
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from load_env import load_env
from instagram_api import post_image, post_comment
from review_and_post_ig import build_caption, append_log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-queue", help="queue/ready_to_post.json のパス。指定時は他の引数より優先される")
    parser.add_argument("--image-url", help="HiggsFieldなどで生成した画像の公開URL")
    parser.add_argument("--caption", help="投稿本文(PR表記は--productで自動付与)")
    parser.add_argument("--item-json", help="pick_product.pyが出力したitemのJSON文字列(ログ記録用)")
    parser.add_argument("--comment", help="投稿後に追加するコメント文(商品名・誘導など)")
    parser.add_argument("--product", action="store_true", default=True, help="商品紹介投稿として[PR]表記を付ける(デフォルトON)")
    args = parser.parse_args()

    if args.from_queue:
        with open(args.from_queue, encoding="utf-8") as f:
            queued = json.load(f)
        image_url = queued["image_url"]
        raw_caption = queued["caption"]
        item = queued.get("item")
        comment = queued.get("comment")
        is_product = queued.get("product", True)
    else:
        if not args.image_url or not args.caption:
            print("--from-queue か、--image-url/--caption の組を指定してください")
            sys.exit(1)
        image_url = args.image_url
        raw_caption = args.caption
        item = json.loads(args.item_json) if args.item_json else None
        comment = args.comment
        is_product = args.product

    env = load_env()
    caption = build_caption(raw_caption, is_product=is_product)

    post_id = post_image(env, caption, image_url)
    print(f"投稿成功: post_id={post_id}")

    record = {
        "date": datetime.date.today().isoformat(),
        "platform": "instagram",
        "caption": caption,
        "product": is_product,
        "media_path": image_url,
        "post_id": post_id,
    }
    if item:
        record["item"] = item

    if comment:
        comment_id = post_comment(env, post_id, comment)
        record["comment"] = comment
        record["comment_id"] = comment_id
        print(f"コメント追加: comment_id={comment_id}")

    append_log(record)

    if args.from_queue and os.path.exists(args.from_queue):
        os.remove(args.from_queue)


if __name__ == "__main__":
    main()
