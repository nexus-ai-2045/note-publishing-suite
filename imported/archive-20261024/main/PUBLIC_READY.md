---
title: note-publishing-suite 公開準備確認
type: 公開準備確認
status: 2026-10-20 公開範囲変更の検査対象
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
- リポジトリ公開範囲: 2026-10-20の読戻しではPRIVATE。今回の本人依頼で、repo-preflightの全履歴検査と公開ゲートを通過した版だけPUBLICへ切り替える。
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

`pre_publish_check.py` には、Windows・macOS のホーム配下、ローカルホスト、ローカルファイル URL
などのローカルパス検出パターンが含まれる。これは走査ルールであり、
公開された個人情報ではない。

個人リンク走査は、この公開リポジトリの作業コピーに対して実行済み。
公開用アカウントと検査用fixtureを実在人物の個人情報と区別し、個人用名義・個人path・秘密情報を別途検査する。
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

## 末尾選定契約の候補変更

記事ごとの選定計画とDOM順snapshotの照合を追加。fixture試験はlive観測や公開承認を代替しない。
この変更のpublic push・PR・runtime配布は別の人間確認が必要。

## 初回導入と検査経路の更新

初回設定は既存のworkspace契約で案内し、実記事の保存先はsettings読戻しのstorageから解決する。packageの利用許諾はLICENSEのMIT。repo-preflightとratchetは既存test workflowの前提jobで毎回実行する。検査結果・本人による初回UAT・公開許可は別に判定する。

## 2026-10-20の再検査と継続ゲート

過去文書の「既にPUBLIC」という記録は、現在値の証拠にならない。公開範囲はGitHub APIで再確認する。
公開対象はGitHub上のmainと全tagの履歴。端末の退避ref・reports・実記事workspaceは公開対象へ追加しない。
現行本文・過去blob・commit/tag名義の検査結果と、例示文字列の個別レビューは利用者workspaceの実行receiptに保持する。
公開範囲の変更は`repo-preflight/scripts/publish_gate.py --apply --confirm nexus-ai-2045/note-publishing-suite`に限る。
専用コマンドのpublishedと、GitHub側PUBLICの読戻しが揃うまで切替済みと扱わない。
共通CIゲートとratchet基準値はPREFLIGHT.mdを参照。CI未起動、ローカル検査成功、公開承認を別々に記録する。
