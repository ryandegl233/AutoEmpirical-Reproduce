from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoempirical_dataset.download_sources import classify_source, download_source, manual_needed_frame, results_to_frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download raw phase-1 AutoEmpirical source datasets.")
    parser.add_argument("--manifest", default="data/manifest/dataset_sources.csv", help="Source manifest CSV.")
    parser.add_argument("--raw-dir", default="data/raw", help="Directory for raw downloads.")
    parser.add_argument("--output-dir", default="data/manifest", help="Directory for download status CSVs.")
    parser.add_argument("--dry-run", action="store_true", help="Classify and plan downloads without writing raw files.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit after filtering.")
    parser.add_argument("--source-indexes", default="", help="Optional comma-separated source_index values to include.")
    parser.add_argument(
        "--categories",
        default="auto_direct,auto_repo_or_dir,try_auto_then_manual,manual_review,deferred_large_secondary,deferred_secondary",
        help="Comma-separated categories to include.",
    )
    parser.add_argument("--max-mb", type=int, default=500, help="Maximum size per file before manual fallback.")
    parser.add_argument("--max-github-files", type=int, default=250, help="Maximum files to scan per GitHub source.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-source progress output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = pd.read_csv(args.manifest)
    categories = {item.strip() for item in args.categories.split(",") if item.strip()}
    source_indexes = {int(item.strip()) for item in args.source_indexes.split(",") if item.strip()}
    raw_dir = Path(args.raw_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_rows = []
    selected_plans = []

    for _, row in manifest.iterrows():
        if source_indexes and int(row.get("source_index", -1)) not in source_indexes:
            continue
        plan = classify_source(row)
        if plan.category in categories:
            selected_rows.append(row)
            selected_plans.append(plan)
        if args.limit is not None and len(selected_rows) >= args.limit:
            break

    all_results = []
    total_sources = len(selected_rows)
    if not args.quiet:
        mode = "dry-run" if args.dry_run else "download"
        print(f"Starting {mode}: {total_sources} sources", flush=True)

    for source_number, (row, plan) in enumerate(zip(selected_rows, selected_plans), start=1):
        source_index = row.get("source_index", "")
        paper_id = row.get("paper_id", "")
        if not args.quiet:
            print(
                f"[{source_number}/{total_sources}] start "
                f"#{source_index} {paper_id} ({plan.category}, {plan.mode})",
                flush=True,
            )

        def progress(message: str) -> None:
            if not args.quiet:
                print(f"  [{source_number}/{total_sources}] {message}", flush=True)

        source_results = download_source(
            row,
            raw_dir=raw_dir,
            dry_run=args.dry_run,
            max_bytes=args.max_mb * 1024 * 1024,
            max_github_files=args.max_github_files,
            progress=progress,
        )
        all_results.extend(source_results)
        if not args.quiet:
            counts = pd.Series([result.status for result in source_results]).value_counts().to_dict()
            status_summary = ", ".join(f"{key}={value}" for key, value in counts.items()) or "no_results"
            print(f"[{source_number}/{total_sources}] done #{source_index} {paper_id}: {status_summary}", flush=True)

    status = results_to_frame(all_results)
    status_path = output_dir / "download_status.csv"
    manual_path = output_dir / "manual_download_needed.csv"
    status.to_csv(status_path, index=False, encoding="utf-8-sig")
    manual_needed_frame(status).to_csv(manual_path, index=False, encoding="utf-8-sig")

    print(f"Wrote status: {status_path}")
    print(f"Wrote manual list: {manual_path}")
    if not status.empty:
        print(status["status"].value_counts(dropna=False).to_string())
        print(status["category"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
