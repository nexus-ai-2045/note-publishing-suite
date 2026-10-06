---
title: note official spec cache
type: reference
status: active
created: 2026-06-28
source_scope: note official help and official announcements
external_action: none
---

# note official spec cache

## 目的

Note 公式仕様を、毎回ブラウザ検索だけに頼らずローカルで参照できるようにする。
この cache は公式扱いの入口であり、運用論や local observation は混ぜない。

## 保存先

| 用途 | path |
|---|---|
| URL manifest | `references/official-note-specs/sources.json` |
| HTML cache | `references/official-note-specs/html/` |
| Markdown extract | `references/official-note-specs/markdown/` |
| 再取得 script | `scripts/fetch_note_official_specs.py` |

## 更新手順

```bash
python3 scripts/fetch_note_official_specs.py --json
```

実行場所は `note-publishing-suite/`。ログイン、Cookie、非公開URL、投稿操作は使わない。

## 現在の対象

- 推奨環境
- エディタ機能
- 記事編集画面
- 画像仕様
- ハッシュタグ
- 価格設定と支払い
- 有料記事
- 有料マガジン
- メンバーシップ
- メンバー特典記事
- メンバー特典マガジン
- 共同運営マガジン

## 公式扱いのルール

- 公式扱いできるのは、`sources.json` にある URL から取得した内容と、
  `note-editor-capability-inventory.md` の `公式ソース` 表へ反映した要点だけ。
- HTML / Markdown cache は参照補助。仕様判断では取得日と公式URLを併記する。
- 公式ページが更新された可能性がある場合は、再取得して差分を見る。
- 有料、公開範囲、メンバー限定、共同運営などの課金・権限まわりは、
  公式ページの文言と現行画面の両方を確認するまで自動操作しない。
