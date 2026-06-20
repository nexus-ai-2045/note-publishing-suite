# 公開リリース確認表

Note Publishing Suite を公開 GitHub リポジトリにプッシュする前の確認リストです。

## 対象リポジトリ

- remote が意図した Nexus organization / repository を指している。
- git author name / email が公開リポジトリに適している。
- リリース用コミットに無関係なローカル作業ツリー変更を含めていない。

## プライバシーとシークレット

- 非公開ハンドル、個人名、個人メール、ローカルパスを検索した。
- 認証情報、トークン、Cookie、非公開 URL、API キーを検索した。
- `data/*.json` が空、または共有可能な台帳例だけを含む。
- 未公開記事下書き、非公開出典ノート、個人素材が追跡ファイルに入っていない。

## パッケージ品質

- `README.md` が日本語でパッケージの目的と使い方を説明している。
- `README.rendered.html` を `README.md` から再生成した。
- `SKILL.md` と全子スキルが同じ公開境界を説明している。
- `package.yaml` が現在のファイル / スクリプトを指している。
- `scripts/post_publish.py` はローカル台帳専用で、SNS 投稿オプションを持たない。
- `LICENSE`、`SECURITY.md`、`PUBLIC_READY.md` が root にある。
- `PUBLIC_READY.md` に未実行の外部検証と人間レビューゲートを明記している。

## 検証

```powershell
sh scripts/verify_public_package.sh
python -m pytest scripts/test_skill_integration.py tests -q
python -m pytest tests/test_review_draft_cli.py -q
python scripts/engagement_tracker.py report --json
python scripts/note_image_upload_boundary_check.py --json
python scripts/note_editor_prepublish_verify.py data/note_editor_prepublish_observation.fixture.json --json
python scripts/review_draft.py review-draft content/drafts/sample-note-prepublish-fixture.md --json
python scripts/render_readme.py
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/verify_public_package.ps1
```

## プッシュ前の人間判断

- 公開プッシュは、現在の会話で対象リポジトリと可視化される差分を明示してから行う。
- リポジトリ公開範囲変更は、この確認表とは別にリポジトリ別確認を取る。
- Note 公開、予約投稿、SNS 共有、外部告知は、このパッケージ更新とは別承認で扱う。
