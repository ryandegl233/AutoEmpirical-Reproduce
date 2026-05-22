from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoempirical_dataset.stage1_raw import redownload_stage1_candidates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Redownload and validate stage-1 candidate datasets.")
    parser.add_argument("--checklist", default="data/manifest/manual_checklist.csv", help="Manual checklist CSV.")
    parser.add_argument("--sources", default="data/manifest/dataset_sources.csv", help="Dataset source manifest CSV.")
    parser.add_argument(
        "--candidates-dir",
        default="data/raw_stage1_candidates",
        help="Directory for validated redownloaded candidates.",
    )
    parser.add_argument("--manifest-dir", default="data/manifest/stage1", help="Stage-1 manifest output directory.")
    parser.add_argument("--max-mb", type=int, default=500, help="Maximum size per candidate file.")
    parser.add_argument("--max-github-files", type=int, default=250, help="Maximum GitHub files to scan per source.")
    parser.add_argument("--source-indexes", default="", help="Optional comma-separated source_index values to include.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_indexes = {int(item.strip()) for item in args.source_indexes.split(",") if item.strip()}

    def progress(message: str) -> None:
        if not args.quiet:
            print(message, flush=True)

    status, accepted = redownload_stage1_candidates(
        checklist_path=Path(args.checklist),
        sources_path=Path(args.sources),
        candidates_dir=Path(args.candidates_dir),
        manifest_dir=Path(args.manifest_dir),
        max_bytes=args.max_mb * 1024 * 1024,
        max_github_files=args.max_github_files,
        source_indexes=source_indexes or None,
        progress=progress,
    )
    print(f"Wrote status rows: {len(status)}")
    print(f"Accepted candidate rows: {len(accepted)}")
    if not status.empty:
        print(status["status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()

