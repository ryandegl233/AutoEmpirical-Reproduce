from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoempirical_dataset.stage1_raw import prepare_stage1_raw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare accepted stage-1 raw datasets.")
    parser.add_argument("--checklist", default="data/manifest/manual_checklist.csv", help="Manual checklist CSV.")
    parser.add_argument("--raw-dir", default="data/raw", help="Existing raw source directory.")
    parser.add_argument("--stage1-dir", default="data/raw_stage1", help="Accepted stage-1 output directory.")
    parser.add_argument("--manifest-dir", default="data/manifest/stage1", help="Stage-1 manifest output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    accepted, missing = prepare_stage1_raw(
        checklist_path=Path(args.checklist),
        raw_dir=Path(args.raw_dir),
        stage1_dir=Path(args.stage1_dir),
        manifest_dir=Path(args.manifest_dir),
    )
    print(f"Accepted copied/listed: {len(accepted)}")
    print(f"Stage2 missing raw: {len(missing)}")
    if not accepted.empty:
        print(accepted["status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()

