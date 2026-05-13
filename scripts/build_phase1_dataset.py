from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoempirical_dataset.analysis import build_summary_tables, validate_schema, write_data_dictionary, write_quality_report
from autoempirical_dataset.converters import convert_all_local_datasets, merge_and_deduplicate
from autoempirical_dataset.manifest import build_source_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AutoEmpirical phase-1 unified bug dataset.")
    parser.add_argument("--excel", default="Attachments/AutoEmpirical-Dataset-Collection.xlsx", help="Dataset collection workbook.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--manifest-dir", default="data/manifest", help="Output directory for source manifest.")
    parser.add_argument("--interim-dir", default="data/interim", help="Output directory for converted per-source data.")
    parser.add_argument("--processed-dir", default="data/processed", help="Output directory for merged dataset and reports.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    manifest_dir = root / args.manifest_dir
    interim_dir = root / args.interim_dir
    processed_dir = root / args.processed_dir
    manifest_dir.mkdir(parents=True, exist_ok=True)
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    manifest = build_source_manifest(root / args.excel)
    manifest_path = manifest_dir / "dataset_sources.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")

    converted = convert_all_local_datasets(root)
    for source_name, frame in converted.items():
        source_dir = interim_dir / source_name
        source_dir.mkdir(parents=True, exist_ok=True)
        frame.to_csv(source_dir / "records.csv", index=False, encoding="utf-8-sig")

    dataset = merge_and_deduplicate(converted.values())
    dataset_path = processed_dir / "autoempirical_bug_dataset.csv"
    dataset.to_csv(dataset_path, index=False, encoding="utf-8-sig")

    schema_issues = validate_schema(dataset)
    write_data_dictionary(processed_dir / "data_dictionary.md")
    write_quality_report(processed_dir / "quality_report.md", dataset, manifest, schema_issues)

    for name, table in build_summary_tables(dataset, manifest).items():
        table.to_csv(processed_dir / f"{name}.csv", index=False, encoding="utf-8-sig")

    print(f"Wrote manifest: {manifest_path}")
    print(f"Wrote dataset: {dataset_path}")
    print(f"Records: {len(dataset)}")
    if schema_issues:
        print("Schema issues:")
        for issue in schema_issues:
            print(f"- {issue}")


if __name__ == "__main__":
    main()
