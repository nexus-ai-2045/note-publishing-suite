---
name: note-postpublish-ledger
description: "Use inside note-publishing-suite after explicitly approved Note publication or scheduled publication to verify status and update local ledgers."
---

# note-postpublish-ledger

## 役割

公開または予約が明示承認済みで完了した後、公開状態とローカル台帳を確認する。

## 入力

- note 公開 URL または予約完了 URL。
- local draft path。
- 公開/予約の完了表示。
- Note 表示日時。ユーザー手動確認値があれば優先。
- tags、image_url、source、plain_status の記録値。
- diff check で確認する phrase。未指定なら共通チェックのみ。

## Commands

```powershell
python scripts\post_publish.py --url <note_url> --draft <draft.md> --dry-run
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...> --snapshot-out <local-snapshot.txt> --json
python scripts\engagement_tracker.py report
```

## 手順

1. 公開または予約が現在会話で明示承認済みか確認する。
2. Note 側の URL、公開状態、表示日時、予約日時を確認する。
3. `post_publish.py --dry-run` で本文/ledger 更新案を確認する。
4. 必要 phrase を指定して `note_diff_check.py` を実行し、公開本文 snapshot と SHA-256 を残す。
5. `data/published_notes.json` と `data/note_drafts.json` の更新案を作る。記事データを package 外で管理する場合は `post_publish.py --ledger-dir <dir>` を使い、scripts を複製しない。
6. 実更新する場合も、X 投稿 option は使わない。

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

## 保存先と完了判定

台帳更新は package の `scripts/post_publish.py` に `--ledger-dir <workspace>/data` を必ず渡す。既定はdry-run。実記録には `--write-ledger` を用い、URLから導出されたnote_idと保存先を読み戻す。公開確認済みは `--verification-status published_verified --verified-at <観測時刻>` を渡す。`--published-at` を取得できないときは未確認（null）のまま保持する。

順序は、公開状態の読取り→workspaceの台帳登録→`sync_note_public_snapshot.py --ledger <workspace>/data/published_notes.json`→公開後チェック→結果回収。各段階で成功・失敗・未確認を分ける。`register_post_publish_check.py` がpackageにない場合はworkspace固有入口を使う。Chromeを使わない運用では、その入口の `--public-api-only` を指定し、取得不能時に別browserへ切り替えない。

`status: ok` だけで完了にしない。`closeout_ready` がfalse、`diff.matches` がfalse、台帳未結線、観測欠落なら残務を明記する。人間編集後の公開版と古い草稿の差を自動的に消したり、両者が一致したと記録したりしない。確認結果の時刻・registered.id・保存先まで回収する。
