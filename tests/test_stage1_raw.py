from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from autoempirical_dataset.stage1_raw import (
    candidate_priority,
    copy_tree_without_overwrite,
    ranked_candidate_targets,
    prepare_stage1_raw,
    split_stage1_groups,
    validate_candidate_content,
)


class Stage1RawTests(unittest.TestCase):
    def make_workspace(self) -> Path:
        return Path(tempfile.mkdtemp(prefix="autoempirical_stage1_test_"))

    def cleanup_workspace(self, root: Path) -> None:
        for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        root.rmdir()

    def test_split_stage1_groups(self) -> None:
        frame = pd.DataFrame(
            [
                {"paper_id": "ok", "is_manual_checked_OK": "true", "is_existing_in_raw": "true"},
                {"paper_id": "bad", "is_manual_checked_OK": "false", "is_existing_in_raw": "true"},
                {"paper_id": "missing", "is_manual_checked_OK": "", "is_existing_in_raw": "false"},
            ]
        )
        groups = split_stage1_groups(frame)
        self.assertEqual(groups.accepted["paper_id"].tolist(), ["ok"])
        self.assertEqual(groups.redownload["paper_id"].tolist(), ["bad"])
        self.assertEqual(groups.stage2_missing["paper_id"].tolist(), ["missing"])

    def test_candidate_validation_accepts_normalized_required_columns(self) -> None:
        content = b"Issue URL,Symptoms,Root_Cause\nhttps://example.com/1,crash,null pointer\n"
        result = validate_candidate_content("bugs.csv", content)
        self.assertTrue(result.accepted)
        self.assertEqual(result.matched_symptom_column, "Symptoms")
        self.assertEqual(result.matched_root_cause_column, "Root_Cause")

    def test_candidate_validation_rejects_missing_required_columns(self) -> None:
        readme = b"# Dataset\nThis repository has requirements and scripts.\n"
        no_root_cause = b"Issue URL,Symptom,Category\nhttps://example.com/1,crash,ui\n"
        self.assertFalse(validate_candidate_content("README.md", readme).accepted)
        result = validate_candidate_content("bugs.csv", no_root_cause)
        self.assertFalse(result.accepted)
        self.assertIn("root cause", result.reject_reason)

    def test_ranked_candidates_skip_readme_and_prioritize_label_keywords(self) -> None:
        targets = [
            {"target_url": "https://example.com/README.md", "filename": "README.md"},
            {"target_url": "https://example.com/issues.csv", "filename": "issues.csv"},
            {"target_url": "https://example.com/root_cause_symptom_taxonomy.csv", "filename": "root_cause_symptom_taxonomy.csv"},
            {"target_url": "https://example.com/requirements.txt", "filename": "requirements.txt"},
        ]
        ranked = ranked_candidate_targets(targets)
        self.assertEqual([target["filename"] for target in ranked], ["root_cause_symptom_taxonomy.csv", "issues.csv"])
        self.assertGreater(candidate_priority("root_cause_symptom_taxonomy.csv"), candidate_priority("issues.csv"))

    def test_copy_tree_without_overwrite(self) -> None:
        root = self.make_workspace()
        try:
            source = root / "source"
            target = root / "target"
            (source / "nested").mkdir(parents=True)
            (target / "nested").mkdir(parents=True)
            (source / "nested" / "data.csv").write_text("new", encoding="utf-8")
            (target / "nested" / "data.csv").write_text("old", encoding="utf-8")
            copied, already_exists = copy_tree_without_overwrite(source, target)
            self.assertEqual(copied, 0)
            self.assertEqual(already_exists, 1)
            self.assertEqual((target / "nested" / "data.csv").read_text(encoding="utf-8"), "old")
        finally:
            self.cleanup_workspace(root)

    def test_prepare_stage1_raw_outputs_manifests(self) -> None:
        root = self.make_workspace()
        try:
            raw = root / "raw"
            stage1 = root / "raw_stage1"
            manifest = root / "manifest"
            (raw / "ok").mkdir(parents=True)
            (raw / "ok" / "data.csv").write_text("Symptom,Root Cause\nx,y\n", encoding="utf-8")
            checklist = root / "manual_checklist.csv"
            pd.DataFrame(
                [
                    {
                        "paper_id": "ok",
                        "source_index": 1,
                        "is_manual_checked_OK": "true",
                        "is_existing_in_raw": "true",
                    },
                    {
                        "paper_id": "missing",
                        "source_index": 2,
                        "is_manual_checked_OK": "",
                        "is_existing_in_raw": "false",
                    },
                ]
            ).to_csv(checklist, index=False)
            accepted, missing = prepare_stage1_raw(checklist, raw, stage1, manifest)
            self.assertEqual(len(accepted), 1)
            self.assertEqual(len(missing), 1)
            self.assertTrue((stage1 / "ok" / "data.csv").exists())
            self.assertTrue((manifest / "stage1_accepted.csv").exists())
            self.assertTrue((manifest / "stage2_missing_raw.csv").exists())
        finally:
            self.cleanup_workspace(root)


if __name__ == "__main__":
    unittest.main()
