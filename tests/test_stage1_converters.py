from __future__ import annotations

import unittest
from pathlib import Path

from autoempirical_dataset.stage1_converters import (
    STAGE1_COLUMNS,
    convert_all_stage1_sources,
    merge_stage1_frames,
)


ROOT = Path(__file__).resolve().parents[1]


class Stage1ConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.converted = convert_all_stage1_sources(ROOT)

    def test_each_converter_uses_unified_columns(self) -> None:
        for paper_id, frame in self.converted.items():
            with self.subTest(paper_id=paper_id):
                self.assertEqual(list(frame.columns), STAGE1_COLUMNS)
                self.assertGreater(len(frame), 0)

    def test_sources_without_root_cause_are_excluded(self) -> None:
        self.assertNotIn("ase2020_cp_detector_using_configuration_related", self.converted)
        self.assertNotIn("icpc2025_combining_language_and_app_ui", self.converted)

    def test_tfjs_maps_symptom_and_root_cause(self) -> None:
        frame = self.converted["ase2022_towards_understanding_the_faults_of"]
        labeled = frame[(frame["symptom"].astype(str).str.len() > 0) & (frame["root_cause"].astype(str).str.len() > 0)]
        self.assertGreater(len(labeled), 0)
        self.assertIn("tensorflow", frame.iloc[0]["source_project"].lower())

    def test_pytorch_maps_symptom_and_root_cause(self) -> None:
        frame = self.converted["icse2023_an_empirical_study_on_bugs"]
        self.assertGreater(len(frame), 0)
        self.assertTrue((frame["symptom"].astype(str).str.len() > 0).all())
        self.assertTrue((frame["root_cause"].astype(str).str.len() > 0).all())

    def test_txbug_maps_symptom_and_root_cause(self) -> None:
        frame = self.converted["icse2024_understanding_transaction_bugs_in_database"]
        labeled = frame[(frame["symptom"].astype(str).str.len() > 0) & (frame["root_cause"].astype(str).str.len() > 0)]
        self.assertGreater(len(labeled), 0)
        self.assertTrue(frame["issue_url"].astype(str).str.startswith("http").all())
        self.assertTrue((frame["title"].astype(str).str.len() > 0).all())
        text_columns = [column for column in STAGE1_COLUMNS if column != "source_row_index"]
        self.assertFalse(frame[text_columns].astype(str).apply(lambda column: column.str.contains(r"[\r\n]").any()).any())

    def test_multilevel_header_source_converts(self) -> None:
        frame = self.converted["ase2021_an_empirical_study_of_bugs"]
        self.assertGreater(len(frame), 0)
        self.assertIn("github.com", frame.iloc[0]["issue_url"])
        self.assertGreater((frame["root_cause"].astype(str).str.len() > 0).sum(), 0)

    def test_merged_record_ids_are_unique(self) -> None:
        merged = merge_stage1_frames(list(self.converted.values()))
        self.assertEqual(len(merged), merged["record_id"].nunique())


if __name__ == "__main__":
    unittest.main()
