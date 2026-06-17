# セキュリティ方針

Note Publishing Suite は、ローカルファーストのワークフローパッケージです。

追跡ファイルには認証情報、Cookie、トークン、非公開 URL、個人識別子、
未公開記事素材を含めない方針です。

## 対象範囲

現時点のセキュリティレビュー対象は次です。

- `scripts/` 配下のローカルスクリプト
- `SKILL.md` と `skills/` 配下のスキル指示
- `adapters/` 配下のアダプター指示
- `data/` 配下のローカル台帳スキーマ

このパッケージはホスト型サービスを運用しません。

## 報告方法

公開リポジトリで使う場合、セキュリティ課題は GitHub Issues または
リポジトリで有効化されている GitHub Security Advisories から報告してください。

公開課題には実認証情報、Cookie、トークン、非公開 URL、個人情報を
書かないでください。再現手順と伏せ字済み例だけを載せてください。

## 公開前チェック

公開プッシュ前に最低限これを実行します。

```bash
python -m pytest scripts/test_skill_integration.py tests/test_content_pdca_check.py -q
python scripts/engagement_tracker.py report --json
```

認証情報や個人痕跡も検索します。

```bash
rg -n -i "api[_-]?key|secret|token|cookie|password|BEGIN .*PRIVATE|xox[baprs]-|ghp_|github_pat_" .
```

期待される検出は、文書または検出ロジックだけです。
