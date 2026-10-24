---
name: note-editor-constraint-debug
description: "Use inside note-publishing-suite to debug practical Note editor constraints without publishing: embeds, table of contents, Shift+Enter line breaks, image captions/alt, cursor placement, responsive toolbar differences, save states, and editor behavior that must become a measured manual boundary or checker."
---

# note-editor-constraint-debug

## 役割

Note editor の実画面で起きる制約を、再現手順、実測結果、手動境界、
再発防止に落とす。公開や予約投稿はしない。

## 入力

- 対象 editor / draft URL。未指定なら Unknown。
- 対象 draft path。
- デバッグする制約。例: 埋め込み、目次、Shift+Enter、画像 caption、
  alt、タグ、マガジン、保存表示。
- 操作可能な Browser surface。通常は in-app Browser。

## 手順

1. `note-editor-ops` を読む。
2. `../../references/note-editor-capability-inventory.md` を読み、公式ソースと
   local observation を分ける。
3. 既存の live 実測境界として
   `../../references/note-editor-live-constraint-boundaries.md` を読み、
   `figure[data-src]`、`iframe.note-embed`、`table-of-contents`、
   `toc`、`H2` / `H3`、Shift+Enter の `<br>`、Undo 手動境界を
   先行条件として扱う。
4. 公式確認が必要なら先に `note-official-guidance-intake` を読む。
5. 1 cycle 1 action で実測する。例: cursor 確認、URL 単独行貼り付け、
   Enter 1回、DOM 確認、Undo 1回。
6. 実測ごとに、再現手順、期待結果、実結果、DOM 証跡、復旧可否を記録する。
7. 自動化できる境界は checker / contract test / skill 文言へ落とす。
8. UI 状態に依存して保証できないものは、手動境界として公開 gate に残す。
9. 変更後は `scripts/test_skill_integration.py` と関係する checker を実行する。

## 対象制約

この節の `figure[data-src]`、`iframe.note-embed`、`table-of-contents`、
`toc`、`H2` / `H3`、`<br>`、Undo 境界は、2026-06-16 の
local live measurement と checker 用の成功条件。公式仕様として扱うのは、
`../../references/note-editor-capability-inventory.md` の `公式ソース` 表に
source URL と `confirmed_on` がある内容だけ。

- 埋め込み: URL 単独行、Enter 変換、通常リンク残り、カード位置。
  成功は `figure[data-src]` と `iframe.note-embed`。raw URL、
  `a[href]` だけ、重複 URL は失敗扱い。
- 目次: 挿入メニューの `大見出し` は `H2`、`小見出し` は `H3`。
  成功は `table-of-contents contenteditable="false"` と `toc` 属性内の
  heading list。表示/非表示、長い目次、公開後表示は別途手動確認。
- Shift+Enter: 段落内改行は同一 `p` 内の `<br>` として確認する。
  automation surface の通常 Enter 段落分割は保証しない。
- Undo: 埋め込み変換後と目次挿入後の `Control+Z` 1回では DOM が残ったため、
  この surface では復旧保証しない。誤位置の場合は手動境界へ戻す。
- 画像: upload 境界、alt、caption、圧縮、GIF、TOP画像、本文画像。
- toolbar: viewport、overflow menu、固定 selector 破綻、候補再列挙。
- 保存: 自動保存、手動保存、保存通知、複数タブ競合、Undo 復旧。

## 実測ログの最小形

```text
constraint:
surface:
viewport:
cursor_or_selection:
goal:
action:
expected:
actual:
dom_or_visible_evidence:
recovery:
manual_boundary:
ratchet:
```

## 停止条件

- in-app Browser で attach / inspect できない。
- 同じ操作が2回連続で失敗した。
- 公開、投稿、予約確定、外部共有が必要になる。
- 画像 upload が内部ブラウザ単体で完了しない。
- Cookie、token、非公開URL、個人情報がログに入りそうになる。

## Closeout Evidence

- 実測した制約と再現手順。
- 成功/失敗/手動境界の分類。
- `note-editor-ops`、reference、checker、contract test へ反映した内容。
- 復旧した失敗と、復旧できなかった理由。
- 未実行の公開、保存、共有、SNS action。
