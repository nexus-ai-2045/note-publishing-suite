---
title: note-publishing-suite 公開準備確認
type: 公開準備確認
status: v0.2.20 main・tag・Release 反映済み
---

# 公開準備確認

## 対象範囲

対象成果物:

- `nexus-ai-2045/note-publishing-suite` のリポジトリ直下

このパッケージは、Note 投稿支援ワークフローの公開確認用コピー。実運用中の
台帳、認証情報、ローカルブラウザプロファイル、Cookie、個人ワークスペースの
パスは含めない。

## 確認項目

- README 確認済み: はい
- SECURITY.md 確認済み: はい
- LICENSE 確認済み: はい
- シークレット走査済み: はい
- 個人パス走査済み: はい
- 公開境界確認済み: はい
- GitHub へのプッシュ: main 反映済み（PR #17）
- tag: `v0.2.20` @ `34befc7` 作成・push 済み
- GitHub Release: https://github.com/nexus-ai-2045/note-publishing-suite/releases/tag/v0.2.20
- リポジトリ公開範囲の変更: なし（既に PUBLIC。変更しない）
- docs-sync read-only検査: 実装済み・CI 成功
- Windows installer CI: 専用 job で検証
- Browser transport 復旧: read-only 計画専用。process 終了は公開 package 外
- 外部追加スキャナ（旧候補含む）: **採用しない**。正本検証は本 package の
  `verify_public_package` / pytest / docs_sync / provenance 走査に閉じる

## 検証コマンド

```powershell
sh scripts/verify_public_package.sh
python scripts/docs_sync_check.py --base-ref origin/main
```

ROADMAP 確認済み: はい

これはクリーン環境での primary 検証経路。Mac / Linux の `sh` から起動し、Python と git も
使って、パッケージ契約、必須ファイル、JSON 解析可能性、公開ゲート文言、
画像アップロード境界、描画済み README の存在、個人ローカルパスと
シークレットらしい値の公開安全走査、embedded copy / standalone clone
fixture を確認する。

pytest が使える環境では、Python 系テストも開発者向けの追加検査として有用。
Windows / PowerShell 環境では、等価 gate として
`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1`
を使える。

`pre_publish_check.py` には、`C:\\Users`、`/Users/`、`localhost`、`file://`
などのローカルパス検出パターンが含まれる。これは走査ルールであり、
公開された個人情報ではない。

個人リンク走査は、この公開リポジトリの作業コピーに対して実行済み。
個人名、アカウント、実在 Note URL、ローカルユーザープロファイル値は検出されていない。
`pre_publish_check.py` 内の走査ルール文字列は想定内。

シークレットらしい値の走査も、この公開リポジトリの作業コピーに対して実行済み。
トークン、Cookie、パスワード、API キー、シークレットらしい値は検出されていない。

## 公開ゲート

公開リリース済みの版でも、次の操作は対象ごとの明示承認が要る。

- 追加の tag / Release
- リポジトリ公開範囲の変更
- Note 投稿、予約投稿、SNS 共有、外部告知

公開後は、コミット履歴とファイルがウェブ上で見える可能性がある。

docs-sync workflow は `contents: read` のみを使い、検査結果と生成物 patch の artifact 以外を
書き込まない。repository への commit、push、PR 編集は行わない。
