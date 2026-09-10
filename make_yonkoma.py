"""商品を買う動機になるようなミニストーリーを4コマ漫画にして投稿するCLI

各パネルはCounterfeit-V3.0でマンガ風(白黒線画)に生成し、2x2グリッドに合成する。
パネルのプロンプトには「crying / dark circles / sweat drops / exhausted」等の
怖く見えやすい単語を避け、優しい言葉(a little tired but smiling等)を使うこと。
「なぜ欲しくなったか」等の説明はInstagramのキャプション側で書く想定
(画像内に日本語テキストを描画すると崩れやすいため、パネルには入れない)。

使い方:
  python make_yonkoma.py --caption "本文" --product \
    "パネル1のプロンプト" "パネル2のプロンプト" "パネル3のプロンプト" "パネル4のプロンプト"
"""
import argparse
import sys
import os
import datetime

sys.stdout.reconfigure(encoding="utf-8")

from PIL import Image, ImageDraw, ImageFont

from generate_media import generate_image_forge
from publish_media import publish_to_github_pages
from instagram_api import post_image, post_comment
from load_env import load_env
from review_and_post_ig import build_caption, append_log

MANGA_STYLE = "cute shoujo manga style, soft colors, pastel palette, clean lineart, kawaii"
MANGA_NEGATIVE = ("scary, horror, intense, speed lines, crying, tears, dark, grunge, "
                   "photorealistic, 3d render, text, watermark, blurry, extra limbs, deformed")

PANEL_SIZE = 768
GUTTER = 16
BORDER = 24
FONT_PATH = r"C:\Windows\Fonts\YuGothM.ttc"


def generate_panel(prompt, out_dir="generated"):
    paths = generate_image_forge(
        f"{prompt}, {MANGA_STYLE}",
        negative_prompt=MANGA_NEGATIVE,
        width=PANEL_SIZE, height=PANEL_SIZE,
        out_dir=out_dir,
    )
    return paths[0]


def compose_yonkoma(panel_paths, out_dir="generated"):
    if len(panel_paths) != 4:
        raise ValueError("4コマなのでパネルは4枚必要です")

    canvas_size = PANEL_SIZE * 2 + GUTTER + BORDER * 2
    canvas = Image.new("RGB", (canvas_size, canvas_size), "white")
    draw = ImageDraw.Draw(canvas)

    positions = [
        (BORDER, BORDER),
        (BORDER + PANEL_SIZE + GUTTER, BORDER),
        (BORDER, BORDER + PANEL_SIZE + GUTTER),
        (BORDER + PANEL_SIZE + GUTTER, BORDER + PANEL_SIZE + GUTTER),
    ]

    try:
        font = ImageFont.truetype("arialbd.ttf", 28)
    except OSError:
        font = ImageFont.load_default()

    for i, (path, (x, y)) in enumerate(zip(panel_paths, positions), 1):
        panel = Image.open(path).convert("RGB").resize((PANEL_SIZE, PANEL_SIZE))
        canvas.paste(panel, (x, y))
        draw.rectangle([x, y, x + PANEL_SIZE, y + PANEL_SIZE], outline="black", width=3)
        badge_r = 18
        cx, cy = x + badge_r + 6, y + badge_r + 6
        draw.ellipse([cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r], fill="white", outline="black", width=2)
        draw.text((cx, cy), str(i), fill="black", font=font, anchor="mm")

    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"{timestamp}_yonkoma.png")
    canvas.save(out_path)
    return out_path


def _wrap_text(text, font, max_width, draw):
    lines = []
    current = ""
    for ch in text:
        candidate = current + ch
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = ch
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _draw_speech_bubble(draw, text, x, y, max_width, font_size=32):
    font = ImageFont.truetype(FONT_PATH, font_size)
    lines = _wrap_text(text, font, max_width - 40, draw)
    line_height = font_size + 10
    bubble_w = max_width
    bubble_h = line_height * len(lines) + 30

    draw.rounded_rectangle([x, y, x + bubble_w, y + bubble_h], radius=20,
                            fill="white", outline="black", width=3)
    tail_x = x + bubble_w * 0.2
    draw.polygon(
        [(tail_x, y + bubble_h - 2), (tail_x + 24, y + bubble_h - 2), (tail_x - 4, y + bubble_h + 26)],
        fill="white", outline="black",
    )

    ty = y + 15
    for line in lines:
        draw.text((x + 20, ty), line, fill="black", font=font)
        ty += line_height


def add_dialogues(composite_path, dialogues, out_dir="generated"):
    """既存の4コマ合成画像に、パネルごとのセリフ吹き出しを重ねて保存する。
    dialogues: 4要素のリスト(空文字ならそのパネルは吹き出しなし)"""
    canvas = Image.open(composite_path).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    positions = [
        (BORDER, BORDER),
        (BORDER + PANEL_SIZE + GUTTER, BORDER),
        (BORDER, BORDER + PANEL_SIZE + GUTTER),
        (BORDER + PANEL_SIZE + GUTTER, BORDER + PANEL_SIZE + GUTTER),
    ]
    for text, (x, y) in zip(dialogues, positions):
        if text:
            _draw_speech_bubble(draw, text, x + 30, y + 30, PANEL_SIZE - 60)

    os.makedirs(out_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(out_dir, f"{timestamp}_yonkoma_dialogue.png")
    canvas.save(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("panels", nargs="*", default=[], help="4コマ分のプロンプト(順番通り、--file/--panel-files指定時は不要)")
    parser.add_argument("--file", help="生成済みの合成済み4コマ画像をそのまま投稿する場合のパス")
    parser.add_argument("--panel-files", nargs=4, default=None,
                         help="ChatGPT等で手動生成した4枚の画像パス(順番通り。合成はこちらで行う)")
    parser.add_argument("--caption", required=True, help="投稿キャプション")
    parser.add_argument("--product", action="store_true", help="商品紹介の投稿([PR]表記とプロフィールリンク誘導を自動で付ける)")
    parser.add_argument("--comment", help="投稿直後にコメント欄へ追加するテキスト(商品紹介など)")
    parser.add_argument("--dialogues", nargs=4, default=None,
                         help="各パネルのセリフ(4つ、空文字で吹き出しなし)")
    args = parser.parse_args()

    caption = build_caption(args.caption, args.product)

    if args.file:
        composite_path = args.file
    elif args.panel_files:
        print("合成中...")
        composite_path = compose_yonkoma(args.panel_files)
    else:
        if len(args.panels) != 4:
            print("パネルのプロンプトを4つ指定するか、--file/--panel-filesで画像を指定してください")
            sys.exit(1)
        panel_paths = []
        for i, prompt in enumerate(args.panels, 1):
            print(f"[{i}/4] パネル生成中: {prompt[:50]}...")
            panel_paths.append(generate_panel(prompt))
        print("合成中...")
        composite_path = compose_yonkoma(panel_paths)

    if args.dialogues:
        composite_path = add_dialogues(composite_path, args.dialogues)

    print(f"生成物: {os.path.abspath(composite_path)}")
    print(f"キャプション:\n{caption}")
    print("この内容で投稿しますか? [y/N]: ", end="")
    if input().strip().lower() != "y":
        print("投稿を中止しました。ファイルは残っています。")
        return

    env = load_env()
    public_url = publish_to_github_pages(env, composite_path)
    print(f"公開URL: {public_url}")
    post_id = post_image(env, caption, public_url)

    comment_id = None
    if args.comment:
        comment_id = post_comment(env, post_id, args.comment)
        print(f"コメント投稿成功: comment_id={comment_id}")

    append_log({
        "date": datetime.date.today().isoformat(),
        "platform": "instagram",
        "caption": caption,
        "product": args.product,
        "media_path": composite_path,
        "post_id": post_id,
        "comment": args.comment,
        "comment_id": comment_id,
    })
    print(f"投稿成功: post_id={post_id}")


if __name__ == "__main__":
    main()
