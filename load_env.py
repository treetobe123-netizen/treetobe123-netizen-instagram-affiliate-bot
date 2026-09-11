"""共通の.env読み込みユーティリティ

ローカルでは.envファイルから読み込む。.envが存在しない環境(GitHub Actions等のCI)では、
同名のOS環境変数(Secretsから注入される)を代わりに使う。
"""
import os

REQUIRED_KEYS = [
    "IG_ACCESS_TOKEN",
    "IG_USER_ID",
    "RAKUTEN_APPLICATION_ID",
    "RAKUTEN_AFFILIATE_ID",
    "RAKUTEN_ACCESS_KEY",
]
OPTIONAL_KEYS = [
    "GITHUB_PAGES_URL", "RAKUTEN_PROXY_URL", "RAKUTEN_PROXY_SECRET",
]

def load_env(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    if not os.path.exists(path):
        missing = [k for k in REQUIRED_KEYS if k not in os.environ]
        if missing:
            raise RuntimeError(f".envが見つからず、環境変数にも不足があります: {missing}")
        env = {k: os.environ[k] for k in REQUIRED_KEYS}
        env.update({k: os.environ[k] for k in OPTIONAL_KEYS if k in os.environ})
        return env

    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env
