# コントリビューションガイド

このリポジトリへの変更は、公開・外部送信・利用者データの取り扱いを自動化しすぎないことを前提にしています。

## 変更の進め方

1. 変更目的と対象外を明確にします。
2. 挙動変更では、先に失敗するテストを追加します。
3. 関連する `SKILL.md`、`package.yaml`、`README.md`、`CHANGELOG.md` の更新要否を確認します。
4. 次の検証を実行します。

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check scripts tests
python -m pytest scripts/test_skill_integration.py tests -q
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
python scripts/docs_sync_check.py --base-ref origin/main
```

未定義変数などの静的な不具合は固定版Ruff、CLI引数・保存先・拒否条件は既存pytestと共通verifierで検査します。verifierは同梱sample台帳のreportも実行するため、CIだけでCLI引数漏れが見つかる経路を減らします。コードの自動整形・本文の言い換えは行いません。

## NPS 運用スモーク（公開なし）

動画なし・公開なしで「使える」ことをローカルで証明する最短経路。
新規スクリプトは増やさず、既存 checker / installer だけを使う。

Windows / PowerShell の例:

```powershell
# 1) package 契約
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
python -m pytest scripts/test_skill_integration.py tests -q

# 2) ローカル QA 一気通貫（fixture・公開停止）
python scripts/run_local_draft_qa_proof.py --json

# 3) Codex pointer を一時先へ install（ホームは汚さない）
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("nps-skills-" + [guid]::NewGuid().ToString("N"))
$workspace = Join-Path $tmp "workspace"
$skills = Join-Path $tmp "skills"
New-Item -ItemType Directory -Path $workspace -Force | Out-Null
pwsh -NoProfile -File adapters/codex/install.ps1 `
  -PackageRoot (Resolve-Path .) `
  -WorkspaceRoot $workspace `
  -DestinationRoot $skills
python scripts/skill_pointer_check.py --installed-root $skills --json
```

macOS / Linuxのpointer smokeも既存installerを使う（homeへは登録しない）。

```sh
nps_smoke_dir=$(mktemp -d)
mkdir -p "$nps_smoke_dir/workspace"
NOTE_SKILL_RUNTIME=codex CODEX_SKILLS_DIR="$nps_smoke_dir/skills" bash adapters/claude-code/install.sh "$nps_smoke_dir/workspace"
python3 scripts/skill_pointer_check.py --installed-root "$nps_smoke_dir/skills" --json
```

公開・予約・SNS・本番 Note 操作は含めない。

## 安全上の注意

- Cookie、token、非公開URL、個人の絶対パス、実記事の非公開本文、実運用台帳をcommitしません。
- 公開、予約投稿、SNS共有、外部告知はテストや自動処理から実行しません。
- NoteエディタのUI操作は、対象記事と操作面を固定し、失敗時の無断fallbackを行いません。
- 生成物の差分は自動commitせず、検査結果として人間レビューへ戻します。

## 開発保証ゲート（repo-preflight / ai-ratchet-gate）

検査ロジックは本リポジトリへコピーせず、上流を直接呼びます。手順と契約は
[`PREFLIGHT.md`](PREFLIGHT.md) を参照してください。GitHub Actions の
`repository-guarantees` は `test.yml` から毎回再利用し、`package-smoke` の成功前提とします。通常テストからの呼出しと、単独の全体release検査の詳細は上記の正本に従います。
マージは人が行います。

## プルリクエスト

- 変更内容、検証結果、未確認事項、公開境界を日本語で記載します。
- CIが成功しても、人間レビューや公開承認が完了したことにはなりません。
- `main`への直接push、release、repository visibility変更は行いません。
