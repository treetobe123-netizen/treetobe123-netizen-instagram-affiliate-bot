"""Instagram Graph API 投稿モジュール(threads_api.pyと同じコンテナ作成→公開の2段階方式)"""
import urllib.request
import urllib.parse
import json
import time

BASE = "https://graph.instagram.com/v21.0"


def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode())


def _get(url):
    with urllib.request.urlopen(url, timeout=30) as res:
        return json.loads(res.read().decode())


def create_media_container(env, caption, image_url=None, video_url=None, is_reel=True):
    """画像 or 動画の投稿コンテナを作成し、コンテナIDを返す"""
    user_id = env["IG_USER_ID"]
    data = {
        "caption": caption,
        "access_token": env["IG_ACCESS_TOKEN"],
    }
    if video_url:
        data["media_type"] = "REELS" if is_reel else "VIDEO"
        data["video_url"] = video_url
    elif image_url:
        data["image_url"] = image_url
    else:
        raise ValueError("image_url か video_url のどちらかが必要です")
    result = _post(f"{BASE}/{user_id}/media", data)
    return result["id"]


def wait_until_ready(env, container_id, timeout=600, interval=5):
    """コンテナの処理完了(FINISHED)を待つ。動画は数十秒〜数分かかることがある"""
    params = urllib.parse.urlencode({
        "fields": "status_code",
        "access_token": env["IG_ACCESS_TOKEN"],
    })
    waited = 0
    while waited < timeout:
        result = _get(f"{BASE}/{container_id}?{params}")
        status = result.get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"コンテナ処理に失敗しました: {result}")
        time.sleep(interval)
        waited += interval
    raise TimeoutError(f"コンテナ処理がタイムアウトしました(container_id={container_id})")


def publish_container(env, container_id):
    """コンテナIDから実際に投稿を公開し、投稿IDを返す"""
    user_id = env["IG_USER_ID"]
    data = {
        "creation_id": container_id,
        "access_token": env["IG_ACCESS_TOKEN"],
    }
    result = _post(f"{BASE}/{user_id}/media_publish", data)
    return result["id"]


def post_image(env, caption, image_url):
    """画像投稿の作成〜公開までを一括実行"""
    container_id = create_media_container(env, caption, image_url=image_url)
    wait_until_ready(env, container_id)
    return publish_container(env, container_id)


def post_video(env, caption, video_url, is_reel=True):
    """動画/リール投稿の作成〜公開までを一括実行"""
    container_id = create_media_container(env, caption, video_url=video_url, is_reel=is_reel)
    wait_until_ready(env, container_id, timeout=900, interval=10)
    return publish_container(env, container_id)


def post_comment(env, media_id, message):
    """投稿にコメントを追加し、コメントIDを返す"""
    data = {
        "message": message,
        "access_token": env["IG_ACCESS_TOKEN"],
    }
    result = _post(f"{BASE}/{media_id}/comments", data)
    return result["id"]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from load_env import load_env
    env = load_env()

    if len(sys.argv) < 2:
        print("使い方: python instagram_api.py <公開済み画像URL>")
        sys.exit(1)
    post_id = post_image(env, "投稿テストです。", sys.argv[1])
    print(f"投稿成功: post_id={post_id}")
