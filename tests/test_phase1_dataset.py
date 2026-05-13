from __future__ import annotations

import json
import unittest
from pathlib import Path

import pandas as pd

from autoempirical_dataset.converters import convert_all_local_datasets, merge_and_deduplicate
from autoempirical_dataset.manifest import build_source_manifest
from autoempirical_dataset.schema import UNIFIED_COLUMNS


ROOT = Path(__file__).resolve().parents[1]


class Phase1DatasetTests(unittest.TestCase):
    def test_manifest_contains_all_collection_rows(self) -> None:
        manifest = build_source_manifest(ROOT / "Attachments/AutoEmpirical-Dataset-Collection.xlsx")
        self.assertEqual(len(manifest), 52)
        self.assertIn("paper_id", manifest.columns)
        self.assertTrue(manifest["paper_id"].is_unique)

    def test_local_conversion_uses_unified_schema(self) -> None:
        converted = convert_all_local_datasets(ROOT)
        dataset = merge_and_deduplicate(converted.values())
        self.assertGreater(len(dataset), 0)
        self.assertEqual(list(dataset.columns), UNIFIED_COLUMNS)
        labels = json.loads(dataset.iloc[0]["normalized_labels"])
        self.assertIn("mapping_method", labels)

    def test_deduplication_removes_duplicate_issue_urls(self) -> None:
        frame = pd.DataFrame(
            [
                {column: "" for column in UNIFIED_COLUMNS},
                {column: "" for column in UNIFIED_COLUMNS},
            ]
        )
        frame.loc[0, ["record_id", "paper_id", "issue_url", "original_labels"]] = ["p:a", "p", "https://example.com/1", "{}"]
        frame.loc[1, ["record_id", "paper_id", "issue_url", "original_labels"]] = ["p:b", "p", "https://example.com/1", '{"x":"y"}']
        merged = merge_and_deduplicate([frame])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged.iloc[0]["record_id"], "p:b")


if __name__ == "__main__":
    unittest.main()
