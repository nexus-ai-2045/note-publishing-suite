---
title: note post-publish context proof
type: reference
status: active
created: 2026-07-16
updated: 2026-10-02
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

### 初回公開（元draftあり）

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

### 公開済み記事の更新（元draftなしでも可）

公開URLを渡してNoteの公開APIを毎回読み直し、URLのnote IDと所有者、`published`状態、題名、アイキャッチ画像の素材ID（HTTPSホストとパス）を照合する。Noteが付ける画像変換クエリは比較から除くが、異なるホスト・パスやuserinfo付きURLは拒否する。公開APIが返した生URLは結果に残す。必要なら新しい本文句の存在と古い本文句の不在も確認する。編集画面や完了トースト、過去のsnapshotだけでは成功としない。

```bash
python scripts/verify_published_update.py \
  --url <public-note-url> \
  --expected-title <published-title> \
  --expected-eyecatch-url <expected-image-url> \
  --contains <new-body-phrase> \
  --absent <old-body-phrase> \
  --ledger <private-published_notes.json>
```

出力が`overall=ok`のときだけ公開APIの現在値と期待値が一致する。`body_sha256`と`verified_at`を確認し、記事固有の照合結果を利用側のprivate workspaceへ保存する。この検査器はファイルを書き出さない。本文snapshotが必要なら既存の`scripts/sync_note_public_snapshot.py`を別途使い、出力先を確認する。`--contains`/`--absent`は任意だが、本文を変更した場合はその差分を指定する。アイキャッチは期待するNote公開画像URLを指定し、画像変換クエリを除いた素材IDを比較する。視覚的な同一性や画像バイトの一致まで保証するものではない。URLを取得できない、期待値がない、画像が違う場合は保留する。

`--ledger`は既存のprivate公開済み台帳を**読み取るだけ**の任意引数で、指定時は同じnote IDの行が1件だけあり、URL・題名・画像素材ID・公開本文SHA-256が現在値と一致しなければ停止する。本文ハッシュは`published_body_sha256`または`public_body_sha256`を読み、両方あれば両方とも現在値に一致することを要求する。機械判定用の`verification_status`があれば`published_verified`を必須とし、ない場合にだけ従来NPS形式の`plain_status: published_verified`を使う。`status`があれば`published`でなければ停止する。人が読む`plain_status`の文章は書き換えない。台帳の作成・更新は利用側の既存writer/RSS経路で行い、書込後にこのコマンドで再照合する。元draftがない場合、`post_publish.py --draft`へ仮のpathを渡してdraft台帳を作らない。元draftの来歴は不明のまま保持する。

## 完了条件

- 公開URL・表示日時・title・image・tagsを実測済み。
- 必須phraseが公開本文に存在する。
- snapshot pathとSHA-256を記録済み。
- published ledgerはURLごとに1行。
- draft ledgerはnote idまたはdraft filenameごとに1行で、公開状態へ遷移済み。
- 再実行しても台帳行数が増えない。
- SNS共有や外部告知は別承認のまま。

公開済み記事の更新では、公開APIの現在値の照合と、台帳を管理している場合は`--ledger`の一致を完了条件とする。元draftの存在やdraft台帳遷移は要求しない。
