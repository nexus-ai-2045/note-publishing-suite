---
title: note-publishing-suite 公開準備確認
type: 公開準備確認
status: 人間レビュー待ち
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
- GitHub へのプッシュ実行済み: はい。人間レビュー用ブランチまで
- リポジトリ公開範囲の変更: なし
- CHINJU CLI 確認: 未実行

## 検証コマンド

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
```

ROADMAP 確認済み: はい

これはクリーン環境での検証経路。PowerShell から起動し、Python と git も
使って、パッケージ契約、必須ファイル、JSON 解析可能性、公開ゲート文言、
画像アップロード境界、描画済み README の存在、個人ローカルパスと
シークレットらしい値の公開安全走査、embedded copy / standalone clone
fixture を確認する。

pytest が使える環境では、Python 系テストも開発者向けの追加検査として有用。
ただし公開準備の必須コマンドは上記の PowerShell 検証である。

`pre_publish_check.py` には、`C:\\Users`、`/Users/`、`localhost`、`file://`
などのローカルパス検出パターンが含まれる。これは走査ルールであり、
公開された個人情報ではない。

個人リンク走査は、この公開リポジトリの作業コピーに対して実行済み。
個人名、アカウント、実在 Note URL、ローカルユーザープロファイル値は検出されていない。
`pre_publish_check.py` 内の走査ルール文字列は想定内。

シークレットらしい値の走査も、この公開リポジトリの作業コピーに対して実行済み。
トークン、Cookie、パスワード、API キー、シークレットらしい値は検出されていない。

CHINJU CLI は公開前検査の候補として検討したが、ローカル PATH では利用できず、
公開 CHINJU サイトはクローズドベータ登録と使用例（`chinju`、`/scan`、
`/regression`）のみを提示していた。認証済みローカル CHINJU CLI 実行が完了するまで、
CHINJU 検証完了とは扱わない。

## 公開ゲート

GitHub へのプッシュ、公開リリース、公開リポジトリ作成、リポジトリ公開範囲変更の前に停止し、
対象操作ごとの明示承認を確認する。公開後は、コミット履歴とファイルがウェブ上で
見える可能性がある。
