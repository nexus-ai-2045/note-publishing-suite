# 本人が採用した記事構成のレビュー記録

冒頭の結論先出し検査は、本人が意図して採用した物語構成と衝突することがある。本人の原文や採用構成を自動で変更せず、現在の記事・本文・会話に結び付く根拠記録がある場合だけ `missing_early_takeaway` を `review_required` へ分類する。検査合格や公開許可には変換しない。

`nps-prepublish-review/v1` は記事ID、会話ID、現稿SHA-256、frontmatterを除いた本文SHA-256、対象issue、本人の採用理由、証拠参照、timezone付き観測日時を保持する。JSONの自己申告は真正性の証明ではなく、trusted runtimeが実際の本人回答に基づいて記録する。別記事・旧稿・別会話、欠落・不正な記録は停止する。

公開packageに個別記事の非公開内容や承認記録を含めない。利用者の外部保存先に記録し、`pre_publish_check.py` と `review_draft.py` の `--prepublish-review-receipt`、`--article-id`、`--conversation-id` で照合する。workflow packetに記録ファイルを含める場合は `prepublish_review_receipt` とし、現在内容に結び付く承認を改めて照合する。記録が変われば以前のworkflow承認は失効する。

対象は結論先出しだけ。秘密情報、著者性、原稿構造、設定、出典確認、その他のerrorを解除しない。`review_required` のCLI終了コードは1のままで、人間レビューへの移行を示す。公開・投稿・予約・共有の最終操作は既存の人間判断境界を維持する。

CLI と `review_draft.py` は `pre_publish_check.check_draft` を共通入口にする。frontmatter がない場合も article_lane を省略できない。production_candidate の文体参照は `--settings` と `--article-id` を指定して既存の外部 workspace 設定から読み戻し、特定アプリの URI prefix だけを証拠にしない。本人語りの根拠と比較元からの原文保持は `note_authorship_gate.evaluate` の結果を引き継ぐ。ローカル検査成功は公開承認ではない。
