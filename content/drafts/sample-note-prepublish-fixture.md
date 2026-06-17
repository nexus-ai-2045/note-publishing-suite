---
title: Note QA fixture draft
status: draft
article_lane: editor_fixture
source_mode: fixture_only
based_on:
  fixture: references/note-article-provenance-design.md
allowed_use:
  - Note editor 操作検証
  - local QA contract test
not_allowed:
  - 公開候補扱い
  - 個人情報や秘密情報の混入
  - 実記事の根拠扱い
editor_test_allowed: true
publication_gate: human_review_required
external_action: none
---

# Note QA fixture draft

これは Note editor 操作検証用の fixture です。
実記事ではなく、公開候補でもありません。

## Fixture heading

Shift+Enter、目次、埋め込み、保存表示などの検査で使うための
無害な短文です。

Source marker: fixture-only package contract test.
Review marker: TODO keep this synthetic marker so pre-publish QA returns a warning.
