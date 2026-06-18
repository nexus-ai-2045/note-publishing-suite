---
title: Caramel future-date guard fixture
status: draft
source_mode: fixture_only
publication_date: 2026-06-18
publication_gate: human_review_required
external_action: none
---

# Caramel future-date guard fixture

これは caramel materials の未来配信予定ケースを最小再現する
ローカル QA fixture です。実記事ではなく、公開候補でもありません。

## OFF-005 OPテーマ配信予定

- URL: https://www.monogatari-series.com/oms/2024/news/?article_id=70268
- 確認したこと:
  - 2026-07-01 0:00 配信予定として、オフ&モンスターシーズンOPテーマ4曲の情報が出ている。
  - 撫物語なでこドローより `caramel ribbon cursetard`、販売価格250円、収録曲数1曲と記載。
- 境界:
  - 現在日は 2026-06-17。配信予定は未来情報なので、記事公開時に再確認する。

この fixture は future-date guard が公開日時より未来の事実と再確認マーカーを
pre-publish QA で止められることだけを検証します。
