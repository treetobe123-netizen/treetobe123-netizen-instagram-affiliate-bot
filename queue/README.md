# queue/

自動化のバトンリレー用フォルダ。中身は自動生成・自動削除されるので通常は空。

- `today_item.json` — GitHub Actions（pick-product.yml）が書く、今日選ばれた商品
- `ready_to_post.json` — クラウドルーティン（HiggsField生成）が書く、投稿準備完了データ

詳しくは `../higgsfield_daily_prompt.md` と `.github/workflows/` を参照。
