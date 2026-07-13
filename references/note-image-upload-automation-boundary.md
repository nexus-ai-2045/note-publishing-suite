---
title: note image upload automation boundary
type: reference
status: active
created: 2026-06-14
publication_gate: human_review_required
---

# note image upload automation boundary

## 目的

note editor の画像アップロードを、できる経路、ユーザー確認待ちの経路、
禁止経路に分ける。運用保証は
`python scripts/note_image_upload_boundary_check.py --json` で確認する。
この正本 file は `references/note-image-upload-automation-boundary.md`。

## 保証すること

- 内部ブラウザ単体の画像アップロード完全自動化は保証しない。
- Codex in-app Browser が file upload API を提供しない場合がある。この場合は
  `File uploads are not supported` を停止原因として扱い、画像候補選定までで止める。
- cmux browser の画面に見えている active editor を DOM で特定でき、現在会話で明示確認がある場合は、
  local file bytes から生成した `File` を `DataTransfer` に追加する browser-scoped
  paste を別経路として扱う。これは OS clipboard や Cookie、note API を使わない。
- Chrome、note API、Cookie、セッション読み取り、隠れた画面操作、
  OSフォーカス奪取は禁止する。
- 公開、予約投稿、SNS共有、外部告知はしない。
- 画面に見えている Windows ファイル選択ダイアログだけを扱う場合も、
  別境界として現在会話での明示確認を必須にする。
- 失敗時は画像未設定、または直前の見えている状態へ戻して停止する。

## 経路

| route | 状態 | 境界 | smoke | rollback |
|---|---|---|---|---|
| manual_user_upload | allowed_now | ユーザーが見えている note editor で手動 upload | 対象 editor / 画像対象 / 公開未クリック | 画像未設定または直前状態で停止 |
| visible_windows_file_dialog | requires_user_confirmation | 画面に見えている Windows ファイル選択ダイアログだけをユーザー監督下で操作 | ダイアログ可視 / 対象 file 確認 / 公開未クリック | ダイアログをキャンセルして停止 |
| cmux_dom_file_paste | requires_user_confirmation | cmux browser で画面に見えている active editor と local file を特定し、browser-scoped `File` paste を行う。OS clipboard、Cookie、note API は使わない | visible active editor identity / file name・MIME / paste 前後の画像件数・順序 / 公開未クリック | Undo または直前の検証済み下書き状態へ戻し、復旧不能なら保存せず停止 |
| codex_iab_file_upload | blocked | Codex in-app Browser の file upload 非対応時は実uploadしない | `File uploads are not supported` を停止原因として記録 | 画像未設定で停止し、候補pathを返す |
| chrome_api_cookie_hidden_os | blocked | Chrome、note API、Cookie、セッション読み取り、隠れた画面、OSフォーカス奪取 | 実行しない | 対象外 |

`cmux_dom_file_paste` の clipboard は browser 内で生成する `DataTransfer` / `ClipboardEvent`
だけを指す。OS clipboard injection、一般的な隠れた window 操作、対象不明の DOM 操作を
許可する例外ではない。CDN URL の再取得は 2026-07-13 実測で5枚中1枚を取りこぼしたため、
確実な upload route として扱わない。

## Windows / Mac 環境差

note 公式の推奨環境は、PC ブラウザでは Windows 10 以上の
Google Chrome / Microsoft Edge / Mozilla Firefox、macOS 14 以上の
Safari / Google Chrome。各ブラウザは最新版を前提にする。

ただし、公式推奨環境でも OS と browser の組み合わせにより、一部表示や
機能が使えない場合がある。そのため、この境界で保証するのは
「成功」ではなく「stopline と禁止経路」。

| OS | 推奨環境 | 保証 | 停止条件 |
|---|---|---|---|
| Windows | Windows 10 以上 / Chrome, Edge, Firefox 最新版 | attach または可視ダイアログが使える場合だけ進め、使えなければ止まる | attach 不可、可視ダイアログなし、推奨環境外、OS/browser 機能不可、公開/予約が必要 |
| Mac | macOS 14 以上 / Safari, Chrome 最新版 | attach またはユーザー監督下の可視ダイアログ相当が使える場合だけ進め、使えなければ止まる | attach 不可、可視ダイアログなし、推奨環境外、OS/browser 機能不可、公開/予約が必要 |

Mac では Windows 固有の「Windows ファイル選択ダイアログ」という名称は
使わず、ユーザーに見えている OS 標準のファイル選択ダイアログ相当として扱う。
いずれの OS でも、見えていない画面、別 monitor、隠れた window、
OS focus steal は使わない。

## 残務ゼロの定義

残務ゼロとは、現行境界の中で実装すべき安全 gate が残っていない状態。
つまり、禁止経路が blocked で固定され、確認待ち経路が
requires_user_confirmation で固定され、保証 checker が ok を返す状態。

可視 Windows ファイル選択ダイアログの実操作は、ユーザーが明示確認した後の
別境界であり、この境界の未実装残務ではない。

## 運用コマンド

```powershell
python scripts/note_image_upload_boundary_check.py --json
```

`ok: true`、`residual_work_zero: true`、`stop_causes: []` なら、
この境界の運用保証は通っている。

## Closeout

報告では次を分ける。

- 実行した local guarantee。
- 実行していない公開、予約投稿、外部共有。
- ユーザー確認なしには進めない別境界。
