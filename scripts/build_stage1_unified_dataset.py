from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoempirical_dataset.stage1_converters import (
    build_conversion_report,
    convert_all_stage1_sources,
    label_dictionary_markdown,
    merge_stage1_frames,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the stage1 unified manually labeled dataset.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--interim-dir", default="data/interim/stage1_converted", help="Per-paper converted output directory.")
    parser.add_argument("--processed-dir", default="data/processed", help="Processed output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    interim_dir = root / args.interim_dir
    processed_dir = root / args.processed_dir
    interim_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    converted = convert_all_stage1_sources(root)
    for paper_id, frame in converted.items():
        paper_dir = interim_dir / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)
        frame.to_csv(paper_dir / "records.csv", index=False, encoding="utf-8-sig")

    dataset = merge_stage1_frames(list(converted.values()))
    dataset.to_csv(processed_dir / "stage1_unified_labels.csv", index=False, encoding="utf-8-sig")

    report = build_conversion_report(converted)
    report.to_csv(processed_dir / "stage1_conversion_report.csv", index=False, encoding="utf-8-sig")
    (processed_dir / "stage1_label_dictionary.md").write_text(label_dictionary_markdown(), encoding="utf-8")

    print(f"Wrote stage1 dataset: {processed_dir / 'stage1_unified_labels.csv'}")
    print(f"Records: {len(dataset)}")
    print(f"Sources: {len(converted)}")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()

