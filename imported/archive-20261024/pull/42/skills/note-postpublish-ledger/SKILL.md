---
name: note-postpublish-ledger
description: "Use inside note-publishing-suite after explicitly approved Note publication or scheduled publication to verify status and update local ledgers."
---

# note-postpublish-ledger

## 役割

公開または予約が明示承認済みで完了した後、公開状態とローカル台帳を確認する。

## 入力

- note 公開 URL または予約完了 URL。
- local draft path（初回公開で存在する場合）。
- 公開/予約の完了表示。
- Note 表示日時。ユーザー手動確認値があれば優先。
- tags、image_url、source、plain_status の記録値。
- diff check で確認する phrase。未指定なら共通チェックのみ。

## Commands

```powershell
python scripts\post_publish.py --url <note_url> --draft <draft.md> --dry-run
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...> --snapshot-out <local-snapshot.txt> --json
python scripts\engagement_tracker.py report
python scripts\verify_published_update.py --url <note_url> --expected-title <title> --expected-eyecatch-url <image_url> --contains <new_phrase> --absent <old_phrase> --ledger <private-published_notes.json>
```

## 手順

1. 公開または予約が現在会話で明示承認済みか確認する。
2. Note 側の URL、公開状態、表示日時、予約日時を確認する。
3. `post_publish.py --dry-run` で本文/ledger 更新案を確認する。
4. 必要 phrase を指定して `note_diff_check.py` を実行し、公開本文 snapshot と SHA-256 を残す。
5. `data/published_notes.json` と `data/note_drafts.json` の更新案を作る。記事データを package 外で管理する場合は `post_publish.py --ledger-dir <dir>` を使い、scripts を複製しない。
6. 実更新する場合も、X 投稿 option は使わない。

公開済み記事の扉絵・本文を再更新した場合は、`references/post-publish-context-proof.md` の更新記事ルートを使う。公開APIの現在値で記事ID・所有者・公開状態・題名・アイキャッチ素材IDと必要な本文句を照合する。元draftがなければ仮のdraftを作らず、`post_publish.py` のdraft遷移も使わない。台帳は利用側の既存writer/RSS経路で更新し、`--ledger`で同じ記事の1行を読み取り再照合する。検査器はファイルを書き出さない。

## 記事データと実行コードの分離

- 実行コードの正本はこの package の `scripts/` に置く。
- private / workspace 固有の draft・snapshot・ledger は package 外に置いてよい。
- package 外の台帳へ書く時は `--ledger-dir` を明示し、`note_drafts.json` と `published_notes.json` を同じ directory で管理する。
- 公開版が editor で変わった場合は、`published_snapshot`、`published_body_sha256`、`local_draft_differs_from_published` を記録する。
- `note_id` または draft filename が一致する既存 draft 行は上書き遷移し、同じ公開処理の再実行で行を増やさない。

## 台帳

- `data/published_notes.json`: 公開済み Note の一次台帳。URL、title、published_at、tags、image_url、local_source、source、plain_status を置く。
- `data/note_drafts.json`: draft、stale、superseded、published_from_note_editor_record など Note editor 記録を置く。
- Note 表示日時はユーザーの手動確認値を優先する。

## 禁止

`scripts/post_publish.py` の `--x-text` と `--x-schedule` はこの suite から使わない。X 投稿、いいね、外部告知は別依頼と別承認で扱う。

## 停止条件

- 公開 URL が Unknown。
- Note 側の公開/予約状態が未確認。
- draft と公開本文の差分が未確認。
- ledger に token、Cookie、非公開 URL が混ざる可能性がある。

## Closeout Evidence

- note URL。
- 公開/予約 status。
- 表示日時。
- 更新した、または更新予定の ledger path。
- 実行しなかった X/SNS action。

## ローカル観測の公開後処理

`--local-observation` のJSONは `schema: note-public-observation/v1`、canonical公開 `url`、`note_id`、`title`、公開本文plain textの `body`、timezone付き `captured_at`、`captured_by: codex-internal-browser` を持つ。任意の `body_sha256` を実本文と照合し、タグは選択済み領域の観測ができた場合のみ `tags` に入れる。証跡指定時はネットワークへ戻らず、不正JSON・対象不一致・原稿不在で停止する。

```sh
python scripts/post_publish.py --url NOTE_URL --draft DRAFT_PATH --published-ledger WORKSPACE_PUBLISHED_LEDGER --draft-ledger WORKSPACE_DRAFT_LEDGER --local-observation OBSERVATION_JSON
python scripts/sync_note_public_snapshot.py --url NOTE_URL --source-draft DRAFT_PATH --output PUBLIC_SNAPSHOT_PATH --ledger WORKSPACE_PUBLISHED_LEDGER --local-observation OBSERVATION_JSON
```

両CLIは既定dry-run。案を確認した後に `--write-ledger` を付ける。snapshotと原稿・aliasが同じファイルなら停止する。snapshot保存後、`post_publish.py` の `--archive-path WORKSPACE_RELATIVE_SNAPSHOT` で両台帳へ同値を結線する。公開済みの観測は、全ゲート通過や本文全体の一致を証明しない。

queueや定期測定は利用者workspaceの接続が所有する。このpackageはそれらを起動しない。内部ブラウザの手動観測を登録する接続は `manual_observation`／`enabled:false` を保持し、ネットワーク定期取得を無断で開始しない。workspace固有の実接続は別の受入証拠で検証する。
