---
title: note post-publish context proof
type: reference
status: active
created: 2026-07-16
updated: 2026-07-16
tags: [note, post-publish, ledger, snapshot, provenance]
---

# note post-publish context proof

## 目的

Note editorで公開直前に本文が変わっても、ローカルdraftを公開版の正本と誤認せず、公開ページ・snapshot・hash・台帳状態を接続する。

## 境界

- 実行コードの正本: `note-publishing-suite/scripts/`
- workspace固有データ: 利用側が指定するdraft、snapshot、ledger directory
- 公開本文の正本: 確認時点の公開URL
- 再現証跡: 取得snapshotとSHA-256
- 状態遷移: `note_drafts.json`の既存行を`published_from_note_editor_record`へ更新
- 公開済み一次台帳: `published_notes.json`

packageをworkspaceへコピーしてscriptsを二重化しない。利用側は`post_publish.py --ledger-dir <dir>`でprivate台帳を注入する。

## 最小フロー

```bash
python scripts/note_diff_check.py \
  <public-note-url> <local-draft> <required-phrase...> \
  --snapshot-out <workspace-snapshot.txt> --json

python scripts/post_publish.py \
  --url <public-note-url> \
  --draft <local-draft> \
  --note-id <note-id> \
  --verification-status published_verified \
  --published-snapshot <workspace-snapshot.txt> \
  --published-body-sha256 <sha256> \
  --ledger-dir <workspace-data-dir> \
  --write-ledger
```

公開版がlocal draftと異なる場合だけ`--local-draft-differs-from-published`を追加する。見出し画像を公開ページで確認した場合だけ`--cover-image-verified`を追加する。

## 完了条件

- 公開URL・表示日時・title・image・tagsを実測済み。
- 必須phraseが公開本文に存在する。
- snapshot pathとSHA-256を記録済み。
- published ledgerはURLごとに1行。
- draft ledgerはnote idまたはdraft filenameごとに1行で、公開状態へ遷移済み。
- 再実行しても台帳行数が増えない。
- SNS共有や外部告知は別承認のまま。
