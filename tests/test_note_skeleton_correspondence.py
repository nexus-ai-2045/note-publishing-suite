"""Hostで観測した原文・現稿・表示対応の5つの回帰を共通NPSで保持する。"""
import importlib.util
import tempfile
import unittest
from pathlib import Path


class SkeletonDraftCorrespondenceTests(unittest.TestCase):
    def checker(self):
        script = Path(__file__).resolve().parents[1] / "scripts/note_skeleton_review_check.py"
        spec = importlib.util.spec_from_file_location("_correspondence_regression", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.draft_correspondence_errors

    def fixture(self, root):
        import hashlib
        target = root / "draft.md"
        target.write_text("---\ntitle: test\n---\n\n第一段落。\n続き。\n\n## 節\n\n第二段落。\n", encoding="utf-8")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        row = {"text": "保存原文", "edited_text": "［本文 第1段落］\n第一段落。\n続き。",
               "draft_correspondence": {"draft_sha256": digest,
                  "source_text_sha256": hashlib.sha256("保存原文".encode()).hexdigest(),
                  "draft_paragraphs": [1]}}
        return {"sections": [{"paragraphs": [row]}], "draft_correspondence": {
            "draft_path": "draft.md", "draft_sha256": digest, "draft_body_paragraphs": 2,
            "source_paragraphs": 1, "draft_only_paragraphs": [{"paragraph": 2, "text": "第二段落。"}]}}, row, target

    def test_saved_source_and_draft_pair_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode, _, _ = self.fixture(root)
            self.assertEqual(self.checker()(episode, root), [])

    def test_changed_draft_rejects_old_skeleton_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode, _, target = self.fixture(root)
            target.write_text(target.read_text().replace("第二段落", "変更した本文"))
            self.assertIn("draft correspondence is stale", self.checker()(episode, root))

    def test_wrong_displayed_prose_rejects_pair_even_with_current_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode, row, _ = self.fixture(root)
            row["edited_text"] = "本文と違う編集案"
            self.assertIn("displayed draft paragraph differs from saved draft", self.checker()(episode, root))

    def test_extra_old_snippet_is_rejected_even_when_current_snippet_remains(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode, row, _ = self.fixture(root)
            row["edited_text"] += "\n\n［本文 第1段落］\n古い本文。"
            self.assertIn("displayed draft paragraph differs from saved draft", self.checker()(episode, root))

    def test_changed_source_rejects_old_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episode, row, _ = self.fixture(root)
            row["text"] = "変更された原文"
            self.assertIn("paragraph correspondence hash mismatch", self.checker()(episode, root))


