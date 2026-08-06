# コントリビューションガイド

このリポジトリへの変更は、公開・外部送信・利用者データの取り扱いを自動化しすぎないことを前提にしています。

## 変更の進め方

1. 変更目的と対象外を明確にします。
2. 挙動変更では、先に失敗するテストを追加します。
3. 関連する `SKILL.md`、`package.yaml`、`README.md`、`CHANGELOG.md` の更新要否を確認します。
4. 次の検証を実行します。

```powershell
python -m pytest scripts/test_skill_integration.py tests -q
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
python scripts/docs_sync_check.py --base-ref origin/main
```

## 安全上の注意

- Cookie、token、非公開URL、個人の絶対パス、実記事の非公開本文、実運用台帳をcommitしません。
- 公開、予約投稿、SNS共有、外部告知はテストや自動処理から実行しません。
- NoteエディタのUI操作は、対象記事と操作面を固定し、失敗時の無断fallbackを行いません。
- 生成物の差分は自動commitせず、検査結果として人間レビューへ戻します。

## プルリクエスト

- 変更内容、検証結果、未確認事項、公開境界を日本語で記載します。
- CIが成功しても、人間レビューや公開承認が完了したことにはなりません。
- `main`への直接push、release、repository visibility変更は行いません。
