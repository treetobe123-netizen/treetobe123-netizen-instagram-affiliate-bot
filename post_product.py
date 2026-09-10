"""楽天商品を選び、その商品の雰囲気に寄せた画像/動画を生成してInstagramに投稿するCLI

使い方:
  python post_product.py --keyword "ベビー服 セール" --caption "本文"
  python post_product.py --keyword "抱っこ紐" --caption "本文" --video

[PR]表記とプロフィールリンクへの誘導は自動で付く(review_and_post_ig.pyのbuild_captionを利用)。
商品ページのURLは楽天ROOMへの掲載用にコンソールへ表示するだけで、投稿本文には含めない
(Instagramはキャプション内のURLがクリックできないため)。
"""
import argparse
import sys
import os
import datetime

sys.stdout.reconfigure(encoding="utf-8")

from load_env import load_env
from rakuten_research import search_items
from generate_media import generate_image_forge, generate_video_ltx
from publish_media import publish_to_github_pages
from instagram_api import post_image, post_video
from review_and_post_ig import build_caption, append_log


def build_prompt(item):
    return (
        f"soft pastel product photography flat lay, {item['name'][:60]}, "
        "cozy japanese home aesthetic, warm natural light, no text, no logo, no watermark"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True, help="楽天の検索キーワード")
    parser.add_argument("--caption", required=True, help="投稿本文([PR]表記は自動で付く)")
    parser.add_argument("--video", action="store_true", help="動画/リールとして投稿する")
    parser.add_argument("--duration", type=int, default=5, help="動画の長さ(秒、2〜20)")
    args = parser.parse_args()

    env = load_env()
    items = search_items(env, args.keyword, hits=10)
    if not items:
        print("商品が見つかりませんでした")
        sys.exit(1)
    item = items[0]

    print(f"商品候補: {item['name']}")
    print(f"価格: {item['price']}円 / レビュー{item['review_count']}件 / {item['shop']}")
    print(f"URL(楽天ROOMに載せる用): {item['url']}")
    print("この商品でよろしいですか? [y/N]: ", end="")
    if input().strip().lower() != "y":
        print("中止しました。")
        return

    prompt = build_prompt(item)
    print(f"生成プロンプト: {prompt}")
    if args.video:
        print(f"動画生成中(LTX-2.5, {args.duration}秒)... 数分かかります")
        media_path = generate_video_ltx(prompt, duration=args.duration)[0]
    else:
        media_path = generate_image_forge(prompt)[0]

    caption = build_caption(args.caption, is_product=True)
    print(f"生成物: {os.path.abspath(media_path)}")
    print(f"キャプション:\n{caption}")
    print("この内容で投稿しますか? [y/N]: ", end="")
    if input().strip().lower() != "y":
        print("投稿を中止しました。ファイルは残っています。")
        return

    public_url = publish_to_github_pages(env, media_path)
    print(f"公開URL: {public_url}")
    post_id = post_video(env, caption, public_url) if args.video else post_image(env, caption, public_url)

    append_log({
        "date": datetime.date.today().isoformat(),
        "platform": "instagram",
        "caption": caption,
        "product": True,
        "item": item,
        "media_path": media_path,
        "post_id": post_id,
    })
    print(f"投稿成功: post_id={post_id}")
    print(f"忘れずに楽天ROOMにもこの商品を追加してください: {item['url']}")


if __name__ == "__main__":
    main()
