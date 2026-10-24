---
name: note-postpublish-ledger
description: "note-publishing-suiteで、明示承認済みのNote公開・予約公開の完了後に、公開状態を確認してローカル台帳を更新する。"
---

# note-postpublish-ledger

初回または採用settingsが未確認なら、親スキルの「初回利用・設定が未採用の場合」と [初回設定の案内](../../references/note-workflow-review-contract.md#初回設定の案内)を先に適用する。既存設定を再初期化せず、未確認の設定で制作・保存へ進まない。

## 役割

公開または予約が明示承認済みで完了した後、公開状態とローカル台帳を確認する。

## 入力

- note 公開 URL または予約完了 URL。
- ローカル原稿のパス（初回公開で存在する場合）。
- 公開/予約の完了表示。
- Note 表示日時。ユーザー手動確認値があれば優先。
- tags、image_url、source、plain_status の記録値。
- diff check で確認する phrase。未指定なら共通チェックのみ。

## 実行コマンド

```powershell
python scripts\post_publish.py --url <note_url> --draft <draft.md> --ledger-dir <LEDGER_DIR> --dry-run
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...> --snapshot-out <local-snapshot.txt> --json
python scripts\engagement_tracker.py report --ledger-dir <LEDGER_DIR>
python scripts\verify_published_update.py --url <note_url> --expected-title <title> --expected-eyecatch-url <image_url> --contains <new_phrase> --absent <old_phrase> --ledger <private-published_notes.json>
```

## 手順

1. 公開または予約が現在会話で明示承認済みか確認する。
2. Note 側の URL、公開状態、表示日時、予約日時を確認する。
3. `post_publish.py --dry-run` で本文/ledger 更新案を確認する。
4. 必要 phrase を指定して `note_diff_check.py` を実行し、公開本文 snapshot と SHA-256 を残す。
5. `<LEDGER_DIR>/published_notes.json` と `<LEDGER_DIR>/note_drafts.json` の更新案を作る。`LEDGER_DIR` は `storage.ledgers` または本人が既に採用した外部台帳先から選び、すべての呼出しで `post_publish.py --ledger-dir <LEDGER_DIR>` または両台帳pathを明示する。未採用なら保存を止め、package/dataへfallbackせず、scriptsや既存台帳を複製しない。
6. 公開観測を既存 `post_publish.py` へ渡すと、公開本文の機械lintと独立AI点検・feedbackの状態を毎回返す。`postpublication_complete` がfalseなら公開後点検を完了扱いにしない。
7. 現在のtrusted agent runtimeが公開本文全体を実際に読み、誤字・脱字・読みやすさ・本人の語り口を点検する。実tool回答と実worker/turn IDを回収し、既存観測の `editorial_review` と実回答fileへ結線する。AI未実行を0件に置き換えない。
8. 回収ownerが共通 `note_postpublish_review.check_postpublish_review` の `runtime_verifier` で実回答と実IDを照合し、既存feedbackへのAI/pending提案保存と読戻しまで行う。CLIのJSONだけではruntime実行を確認しない。スキーマと接続は `references/post-publish-context-proof.md` の公開後本文点検を使う。
9. `review_required` は候補と機械lint指摘をチャットへ提示し、本人の採否を待つ。本人の本文・語り口や採否を自動変更しない。公開事実の台帳記録と本文点検の完了は別に扱う。
10. 実更新する場合も、X 投稿 option は使わない。

公開済み記事の扉絵・本文を再更新した場合は、`references/post-publish-context-proof.md` の更新記事ルートを使う。公開APIの現在値で記事ID・所有者・公開状態・題名・アイキャッチ素材IDと必要な本文句を照合する。元draftがなければ仮のdraftを作らず、`post_publish.py` のdraft遷移も使わない。台帳は利用側の既存writer/RSS経路で更新し、`--ledger`で同じ記事の1行を読み取り再照合する。検査器はファイルを書き出さない。

## 記事データと実行コードの分離

- 実行コードの正本はこの package の `scripts/` に置く。
- private / workspace 固有の draft・snapshot・ledger は package 外に置いてよい。
- package 外の台帳へ書く時は `--ledger-dir` を明示し、`note_drafts.json` と `published_notes.json` を同じ directory で管理する。
- 公開版が editor で変わった場合は、`published_snapshot`、`published_body_sha256`、`local_draft_differs_from_published` を記録する。
- `note_id` または draft filename が一致する既存 draft 行は上書き遷移し、同じ公開処理の再実行で行を増やさない。

## 台帳

- `<LEDGER_DIR>/published_notes.json`: 公開済み Note の一次台帳。URL、title、published_at、tags、image_url、local_source、source、plain_status を置く。
- `<LEDGER_DIR>/note_drafts.json`: draft、stale、superseded、published_from_note_editor_record など Note editor 記録を置く。
- Note 表示日時はユーザーの手動確認値を優先する。

## 禁止

`scripts/post_publish.py` の `--x-text` と `--x-schedule` はこの suite から使わない。X 投稿、いいね、外部告知は別依頼と別承認で扱う。

## 停止条件

- 公開 URL が不明。
- Note 側の公開/予約状態が未確認。
- draft と公開本文の差分が未確認。
- ledger に token、Cookie、非公開 URL が混ざる可能性がある。

## 終了時に残す証拠

- note URL。
- 公開/予約 status。
- 表示日時。
- 更新した、または更新予定の ledger path。
- 実行しなかった X/SNS action。

## ローカル観測の公開後処理

`--local-observation` のJSONは `schema: note-public-observation/v1`、canonical公開 `url`、`note_id`、`title`、公開本文plain textの `body`、timezone付き `captured_at`、`captured_by: codex-internal-browser` を持つ。任意の `body_sha256` を実本文と照合し、タグは選択済み領域の観測ができた場合のみ `tags` に入れる。証跡指定時はネットワークへ戻らず、不正JSON・対象不一致・原稿不在で停止する。

```sh
python scripts/post_publish.py --url NOTE_URL --draft DRAFT_PATH --published-ledger WORKSPACE_PUBLISHED_LEDGER --draft-ledger WORKSPACE_DRAFT_LEDGER --local-observation OBSERVATION_JSON
python scripts/sync_note_public_snapshot.py --url NOTE_URL --source-draft DRAFT_PATH --output PUBLIC_SNAPSHOT_PATH --ledger WORKSPACE_PUBLISHED_LEDGER --workspace-root WORKSPACE_ROOT --local-observation OBSERVATION_JSON
```

両CLIは既定dry-run。案を確認した後に `--write-ledger` を付ける。snapshotと原稿・aliasが同じファイルなら停止する。snapshot保存後、`post_publish.py` の `--workspace-root WORKSPACE_ROOT --archive-path WORKSPACE_RELATIVE_SNAPSHOT` で両台帳へ同値を結線する。公開済みの観測は、全ゲート通過や本文全体の一致を証明しない。

queueや定期測定は利用者workspaceの接続が所有する。このpackageはそれらを起動しない。内部ブラウザの手動観測を登録する接続は `manual_observation`／`enabled:false` を保持し、ネットワーク定期取得を無断で開始しない。workspace固有の実接続は別の受入証拠で検証する。

公開本文の機械lintだけでは日本語の助詞脱落や誤字を網羅しない。`post_publish.py` のexit0は公開事実の記録処理が成功した意味で、点検完了ではない。`postpublish_review` のmechanical/ai_review/feedbackと `postpublication_complete` を確認する。予約状態・公開未観測なら `waiting_for_publication` とし、公開後に同じ入口で点検する。AI実点検をできないruntimeはpendingと担当する親runtimeへ返す。

公開本文の機械検査は `collect_published_issues` を使い、入力を `published_plain` として返す。題名は別フィールドであり、公開本文にMarkdownのH1・見出し数・冒頭定型句を要求しない。秘密情報と内部メモのerror、文字残骸などの指摘は保持する。制作原稿の公開前構成要件は `collect_issues` の責務として維持する。
