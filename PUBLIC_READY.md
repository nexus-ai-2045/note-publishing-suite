---
title: note-publishing-suite 新規公開候補の確認
type: 公開準備確認
status: 公開前のローカル検査済み・リモート照合待ち
---

# 新規公開候補の確認

## 対象と履歴の境界

対象は`nexus-ai-2045/note-publishing-suite`の新しい公開候補。
旧リポジトリは非公開で保全し、この候補には旧`.git`、PR、tag、Release、
commit履歴を移植しない。旧mainの検査・公開実績は新リポジトリの合格証拠にしない。
ソースの著作権と正当な依存ライブラリの表示はLICENSE等に従って維持する。

## 現在の確認状態

- README、LICENSE、SECURITY.md: 今回の候補を確認済み。既存copyrightを保持。
- ROADMAP 確認済み: はい。`ROADMAP.md`の公開前停止、人間レビュー境界、未完了項目を機械的に確認した。ロードマップ全項目の完了、人間による採用、公開承認を意味しない。
- 秘密情報、個人パス、非公開名義、author・committer: 新しい全公開対象へのrepo-preflight検査で各項目pass。旧履歴は持ち込まない。
- 独立した読取り監査: 対象の個人情報・無関係な人物名・抽出CSS・旧記事DOMについて新たな指摘なし。機械走査や公開結果の代用にはしない。
- CSS: Noteから抽出したCSSを除去し、NPS独自の近似CSSに置換。
- 文書・fixture: 実記事URLを除いた合成例と、明示した合成fixtureを使用。
- GitHub作成、push、公開範囲、CI: 外部実行と読戻しのreceiptで別途確認。
- 端末のbundle、退避ref、実記事workspace、認証情報は公開候補に追加しない。

ローカル検査は2124成功・18skip。origin未設定を検出する名義guardの1件は、リモート作成と接続後に再確認する。Node22の入力guardは135成功。文書同期と変更PythonのRuffも成功。
利用者は対象名での新規public作成を指定している。外部実行前には対象と公開内容を再提示し、その許可範囲で実行する。この文書だけを公開済み・CI成功・本人承認の証明にしない。
バージョン表記やCHANGELOGはソースの変更履歴であり、新リポジトリに同名のtagやReleaseが存在する証拠ではない。

## 既存の検査入口

```sh
sh scripts/verify_public_package.sh
python scripts/docs_sync_check.py --base-ref origin/main
```

初回履歴で比較元が未作成の場合は、その未実行理由を記録する。
Windowsでは `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1` を使う。
必須CIの失敗・未起動をローカル成功で置き換えず、break-glassを使わない。

共通の正式検査はrepo-preflightの現行版とPREFLIGHT.mdに従う。
公開前にREADME、LICENSE、SECURITY.md、ファイルと全公開履歴、個人情報を確認し、
人間レビューと対象を指定した公開承認を照合する。
公開範囲変更は既存の`repo-preflight/scripts/publish_gate.py`を通し、
専用コマンドの結果とGitHub側の読戻しを別々に確認する。

公開されるファイルと新しいコミット履歴はウェブ上で見える。
Note投稿、外部告知、追加tagやReleaseは、この準備文書で承認されたものとは扱わない。
