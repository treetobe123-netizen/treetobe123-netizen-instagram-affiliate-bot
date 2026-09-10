"""楽天市場APIから商品候補を取得するモジュール"""
import urllib.request
import urllib.parse
import urllib.error
import json

SEARCH_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"

# 日替わりでローテーションするリサーチキーワード
# アカウントの軸を「子育て中心」に再設定：ベビー用品・ママ応援グッズ・美容を主軸に、
# プチプラファッションも引き続き織り交ぜる（旅行系はrakuten_travel_research.py側で別途ローテーション）
KEYWORDS = [
    "ベビー服 セール",
    "出産祝い 人気",
    "抱っこ紐",
    "ベビーカー 軽量",
    "離乳食 グッズ",
    "おむつ まとめ買い",
    "授乳服",
    "骨盤ベルト 産後",
    "マザーズバッグ 軽量",
    "時短家電",
    "プチプラ 美容液",
    "韓国コスメ 人気",
    "ヘアケア 集中ケア",
    "日焼け止め 顔用",
    "プチプラ レディース トップス",
    "スニーカー レディース 人気",
    "カーディガン レディース",
]


def _get_json(url, headers=None, env=None):
    """envにRAKUTEN_PROXY_URLがあれば、固定IPの中継プロキシ経由で取得する
    （楽天APIのIP許可リストがGitHub Actionsの流動IPと相性が悪いための回避策）
    """
    proxy_url = (env or {}).get("RAKUTEN_PROXY_URL")
    if proxy_url:
        target = f"{proxy_url}?{urllib.parse.urlencode({'url': url})}"
        req = urllib.request.Request(
            target, headers={"X-Proxy-Secret": env["RAKUTEN_PROXY_SECRET"]}
        )
    else:
        req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode())


def search_items(env, keyword, hits=10, sort="-reviewCount"):
    """キーワードで商品検索し、候補リストを返す"""
    params = urllib.parse.urlencode({
        "applicationId": env["RAKUTEN_APPLICATION_ID"],
        "accessKey": env["RAKUTEN_ACCESS_KEY"],
        "affiliateId": env["RAKUTEN_AFFILIATE_ID"],
        "keyword": keyword,
        "hits": hits,
        "sort": sort,
        "format": "json",
    })
    data = _get_json(
        f"{SEARCH_ENDPOINT}?{params}",
        headers={"Referer": env.get("GITHUB_PAGES_URL", "https://example.com")},
        env=env,
    )
    items = []
    for entry in data.get("Items", []):
        it = entry["Item"]
        items.append({
            "name": it.get("itemName"),
            "price": it.get("itemPrice"),
            "url": it.get("affiliateUrl") or it.get("itemUrl"),
            "image": (it.get("mediumImageUrls") or [{}])[0].get("imageUrl", ""),
            "shop": it.get("shopName"),
            "review_avg": it.get("reviewAverage"),
            "review_count": it.get("reviewCount"),
            "keyword": keyword,
            # ショップが書いたキャッチコピー・商品説明。悩み訴求やFAQが含まれることが多く、
            # 投稿文で「本当の売りポイント」を探すのに使う。説明文は長いため先頭700文字に切る
            "catchcopy": it.get("catchcopy", ""),
            "caption": (it.get("itemCaption") or "")[:700],
        })
    return items


def daily_candidates(env, keyword_index, hits=10):
    """その日のキーワードで候補を取得する。keyword_indexは0始まりの通し番号（例：経過日数）"""
    keyword = KEYWORDS[keyword_index % len(KEYWORDS)]
    return keyword, search_items(env, keyword, hits=hits)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from load_env import load_env
    env = load_env()
    kw, items = daily_candidates(env, keyword_index=0)
    print(f"keyword={kw} / {len(items)} items")
    for it in items[:5]:
        print(f" - [{it['review_count']}件] {it['name'][:40]} ({it['price']}円)")
