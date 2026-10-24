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
python scripts\note_diff_check.py <note_url> <draft.md> <phrase...>
python scripts\engagement_tracker.py report
```

## 手順

1. 公開または予約が現在会話で明示承認済みか確認する。
2. Note 側の URL、公開状態、表示日時、予約日時を確認する。
3. `post_publish.py --dry-run` で本文/ledger 更新案を確認する。
4. 必要 phrase を指定して `note_diff_check.py` を実行する。
5. `data/published_notes.json` と `data/note_drafts.json` の更新案を作る。
6. 実更新する場合も、X 投稿 option は使わない。

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
