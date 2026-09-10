"""複数シーンのプロンプトから短いクリップを連続生成し、1本の動画に結合するCLI

使い方:
  python make_sequence.py --duration 10 "シーン1のプロンプト" "シーン2のプロンプト" ...
  python make_sequence.py --duration 10 --image generated/reference.png "シーン1" "シーン2" ...
  python make_sequence.py --duration 10 --image generated/reference.png --chain "シーン1" "シーン2" ...

--imageを指定すると、全クリップの開始フレームに同じ画像を使う(image-to-video)ので
シーンをまたいでキャラクターの見た目が揃う。
--chainを併用すると、2クリップ目以降は「同じ画像」ではなく「直前のクリップの最後のフレーム」を
開始フレームに使う。動きが完全に連続するワンカット風になる(--imageは最初のクリップにのみ使う)。
どちらも指定しなければ従来通りtext-to-videoで生成する
"""
import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8")

from generate_media import generate_video_ltx, generate_video_ltx_i2v, concat_videos, extract_last_frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompts", nargs="+", help="各シーンのプロンプト(渡した順番につながる)")
    parser.add_argument("--duration", type=int, default=10, help="各クリップの秒数(2〜20)")
    parser.add_argument("--image", help="開始フレームに使う参照画像(指定するとimage-to-video)")
    parser.add_argument("--chain", action="store_true",
                         help="2クリップ目以降、直前クリップの最後のフレームを開始フレームにして繋げる(要--image)")
    args = parser.parse_args()

    if args.chain and not args.image:
        print("--chainには--imageも指定してください(最初のクリップの開始フレームになります)")
        sys.exit(1)

    clip_paths = []
    next_start_image = args.image
    for i, prompt in enumerate(args.prompts, 1):
        print(f"[{i}/{len(args.prompts)}] 生成中: {prompt[:60]}...")
        if next_start_image:
            path = generate_video_ltx_i2v(prompt, next_start_image, duration=args.duration)[0]
        else:
            path = generate_video_ltx(prompt, duration=args.duration)[0]
        print(f"  -> {path}")
        clip_paths.append(path)
        if args.chain:
            next_start_image = extract_last_frame(path)
        elif args.image:
            next_start_image = args.image

    print("結合中...")
    out = concat_videos(clip_paths)
    print(f"完成: {out}")


if __name__ == "__main__":
    main()
