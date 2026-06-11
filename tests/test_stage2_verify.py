from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from autoempirical_mas.datasets import load_records
from autoempirical_mas.llm import MockLLMClient
from autoempirical_mas.pipeline import MASPipeline
from autoempirical_mas.stage2 import (
    body_quality,
    synthesize_stage2_evidence,
)


class Stage2VerifyTests(unittest.TestCase):
    def test_body_quality_detects_url_only_and_absent(self) -> None:
        self.assertEqual(body_quality("https://github.com/example/project/issues/1"), "url_only")
        self.assertEqual(body_quality(""), "absent")
        self.assertEqual(body_quality("short but meaningful crash report"), "short")
        self.assertEqual(body_quality("error " * 120), "rich")

    def test_synthesizer_accepts_strong_link_and_comment_evidence(self) -> None:
        result = synthesize_stage2_evidence(
            text={"text_verdict": "likely_bug", "confidence": 0.7, "body_quality": "rich"},
            comments={"developer_verdict": "confirmed_bug", "confidence": 0.9},
            links={"fix_evidence": "merged_fix", "confidence": 0.95, "linked_commits": ["abc123"]},
            metadata={"metadata_verdict": "likely_bug", "confidence": 0.8},
        )

        self.assertEqual(result["synthesized_verdict"], "Accepted")
        self.assertGreaterEqual(result["confidence"], 0.75)
        self.assertIn("abc123", result["supporting_evidence"])
        self.assertEqual(result["linked_commits"], ["abc123"])

    def test_synthesizer_downweights_url_only_text(self) -> None:
        result = synthesize_stage2_evidence(
            text={"text_verdict": "likely_bug", "confidence": 1.0, "body_quality": "url_only"},
            comments={"developer_verdict": "no_comments", "confidence": 0.0},
            links={"fix_evidence": "no_fix", "confidence": 0.0},
            metadata={"metadata_verdict": "ambiguous", "confidence": 0.0},
        )

        self.assertEqual(result["evidence_summary"]["text"]["weight"], 0.05)
        self.assertLess(result["confidence"], 0.45)

    def test_loader_accepts_stage1_enriched_columns(self) -> None:
        temp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        temp.close()
        path = Path(temp.name)
        try:
            pd.DataFrame(
                [
                    {
                        "record_id": "paper:abc",
                        "issue_url": "https://github.com/example/project/issues/1",
                        "title": "Crash on import",
                        "body": "Fails with stack trace",
                        "comments": "Maintainer confirmed and fixed in PR #2",
                        "state": "closed",
                    }
                ]
            ).to_csv(path, index=False)

            records = list(load_records("filtering", str(path), limit=1))
        finally:
            path.unlink()

        self.assertEqual(records[0].record_id, "paper:abc")
        self.assertEqual(records[0].comments_content, "Maintainer confirmed and fixed in PR #2")
        self.assertEqual(records[0].issue_url, "https://github.com/example/project/issues/1")

    def test_pipeline_stage2_verify_v2_runs_with_mock_backend(self) -> None:
        issue = next(load_records("filtering", "data/processed/stage1_enriched.csv", limit=1))
        pipeline = MASPipeline(llm=MockLLMClient(), base_prompts={}, variant="stage2_verify_v2")

        result = pipeline.run(issue)

        self.assertEqual(result.final_output["record_id"], issue.record_id)
        self.assertIn(result.final_output["verdict"], {"Accepted", "Rejected", "Uncertain"})
        self.assertIn("text_available", result.final_output)
        self.assertGreaterEqual(result.api_calls, 4)


if __name__ == "__main__":
    unittest.main()
