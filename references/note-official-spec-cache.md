---
title: note official spec cache
type: reference
status: active
created: 2026-06-28
source_scope: note official help and official announcements
external_action: none
---

# note公式仕様のローカル保存

## 目的

Note 公式仕様を、毎回ブラウザ検索だけに頼らずローカルで参照できるようにする。
この cache は公式扱いの入口であり、運用論や local observation は混ぜない。

## 保存先

| 用途 | path |
|---|---|
| URL manifest | `references/official-note-specs/sources.json` |
| HTML cache | 明示したworkspace保存先の `html/` |
| Markdown extract | 明示したworkspace保存先の `markdown/` |
| 再取得 script | `scripts/fetch_note_official_specs.py` |

## 更新手順

```bash
python3 scripts/fetch_note_official_specs.py --output-dir <private-workspace>/official-note-specs --json
# 計画確認後、公式公開HTTPSの取得を明示許可
python3 scripts/fetch_note_official_specs.py --output-dir <private-workspace>/official-note-specs --allow-public-http --json
```

既定は取得計画の表示だけで、通信・ファイル作成を行わない。出力先は必須で、NPS package内への保存を拒否する。既存の同梱cacheは参照できるが、再取得でpackageへ書き戻さない。

ログイン、Cookie、非公開URL、投稿操作は使わない。対象は `www.help-note.com` / `help-note.com` の `/hc/ja/articles/` 以下のHTTPS記事。redirect先にも同じ制約を適用する。manifest全体の型・重複key・URL・保存先を通信前に検査する。

HTMLとMarkdownは原子的に保存し、保存後のbytes読戻しを照合する。結果JSONには実際に使用したmanifest、HTML、MarkdownのSHA-256と絶対保存先を返す。これはローカル確認用であり、公開packageに個人の保存先や取得記録を追加しない。

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
