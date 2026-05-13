from __future__ import annotations

import unittest

import pandas as pd

from autoempirical_dataset.download_sources import (
    classify_source,
    github_blob_raw_url,
    github_contents_api_url,
    gitlab_archive_fallback_urls,
    google_sheet_export_url,
    zenodo_record_id,
)


class DownloadSourceTests(unittest.TestCase):
    def test_google_sheet_export_url(self) -> None:
        url = "https://docs.google.com/spreadsheets/d/abc123/edit?gid=0#gid=0"
        self.assertEqual(
            google_sheet_export_url(url),
            "https://docs.google.com/spreadsheets/d/abc123/export?format=xlsx",
        )

    def test_github_blob_raw_url(self) -> None:
        url = "https://github.com/o/r/blob/main/data/file.csv"
        self.assertEqual(
            github_blob_raw_url(url),
            "https://raw.githubusercontent.com/o/r/main/data/file.csv",
        )

    def test_github_tree_api_url(self) -> None:
        url = "https://github.com/o/r/tree/master/data/files"
        self.assertEqual(
            github_contents_api_url(url),
            "https://api.github.com/repos/o/r/contents/data/files?ref=master",
        )

    def test_zenodo_record_id_from_doi(self) -> None:
        self.assertEqual(zenodo_record_id("https://doi.org/10.5281/zenodo.3653444"), "3653444")

    def test_gitlab_archive_fallback_urls(self) -> None:
        self.assertEqual(
            gitlab_archive_fallback_urls("https://gitlab.com/group/project"),
            [
                "https://gitlab.com/group/project/-/archive/main/project-main.zip",
                "https://gitlab.com/group/project/-/archive/master/project-master.zip",
            ],
        )

    def test_manual_and_deferred_classification(self) -> None:
        manual = classify_source(pd.Series({"source_index": 9, "supplementary_link": "https://sites.google.com/view/x"}))
        deferred = classify_source(pd.Series({"source_index": 48, "supplementary_link": "https://archive.org/download/stackexchange"}))
        self.assertEqual(manual.category, "manual_review")
        self.assertEqual(manual.mode, "manual")
        self.assertEqual(deferred.category, "deferred_large_secondary")
        self.assertEqual(deferred.mode, "manual")


if __name__ == "__main__":
    unittest.main()
