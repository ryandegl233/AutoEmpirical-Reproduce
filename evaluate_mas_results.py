from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from autoempirical_mas.datasets import load_records
from autoempirical_mas.json_utils import normalize_filter_label


def extract_id(text: str) -> str:
    match = re.search(r"\[?([A-Z](?:\.\d+)*)\]?", str(text or ""))
    return match.group(1) if match else ""


def accuracy(items: Iterable[Tuple[str, str]]) -> float:
    pairs = list(items)
    if not pairs:
        return 0.0
    return sum(1 for pred, gt in pairs if pred == gt) / len(pairs)


def macro_f1(preds: List[str], gts: List[str]) -> float:
    labels = sorted(set(preds) | set(gts))
    if not labels:
        return 0.0
    scores = []
    for label in labels:
        tp = sum(1 for pred, gt in zip(preds, gts) if pred == label and gt == label)
        fp = sum(1 for pred, gt in zip(preds, gts) if pred == label and gt != label)
        fn = sum(1 for pred, gt in zip(preds, gts) if pred != label and gt == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def load_jsonl(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate MAS JSONL outputs.")
    parser.add_argument("--task", choices=["filtering", "classification"], required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--input", default=None, help="Ground-truth CSV override.")
    return parser.parse_args()


def evaluate_filtering(results: List[Dict], gt_by_id: Dict[str, object]) -> Dict:
    preds, gts = [], []
    confusion = Counter()
    for result in results:
        rid = str(result["record_id"])
        output = result.get("final_output", {})
        pred = "1" if normalize_filter_label(output.get("label")) == "Accepted" else "0"
        gt = str(gt_by_id[rid].ground_truth_filter)
        preds.append(pred)
        gts.append(gt)
        confusion[(gt, pred)] += 1
    return {
        "accuracy": accuracy(zip(preds, gts)),
        "macro_f1": macro_f1(preds, gts),
        "confusion_matrix": {f"gt={gt},pred={pred}": count for (gt, pred), count in confusion.items()},
    }


def evaluate_classification(results: List[Dict], gt_by_id: Dict[str, object]) -> Dict:
    symptom_preds, symptom_gts = [], []
    root_preds, root_gts = [], []
    level_correct = defaultdict(list)
    for result in results:
        rid = str(result["record_id"])
        output = result.get("final_output", {})
        symptom = output.get("bug_symptom", {})
        root = output.get("root_cause", {})
        symptom_pred = extract_id(symptom.get("specific_type")) or extract_id(symptom.get("subcategory"))
        root_pred = extract_id(root.get("subcategory")) or extract_id(root.get("primary_category"))
        symptom_gt = str(gt_by_id[rid].ground_truth_symptom_id)
        root_gt = str(gt_by_id[rid].ground_truth_root_cause_id)
        symptom_preds.append(symptom_pred)
        symptom_gts.append(symptom_gt)
        root_preds.append(root_pred)
        root_gts.append(root_gt)
        for name, pred, gt in [("symptom", symptom_pred, symptom_gt), ("root_cause", root_pred, root_gt)]:
            for level in range(gt.count(".") + 1):
                gt_prefix = ".".join(gt.split(".")[: level + 1])
                pred_prefix = ".".join(pred.split(".")[: level + 1])
                level_correct[f"{name}_level_{level}"].append(1 if pred_prefix == gt_prefix else 0)
    return {
        "symptom_leaf_accuracy": accuracy(zip(symptom_preds, symptom_gts)),
        "root_cause_leaf_accuracy": accuracy(zip(root_preds, root_gts)),
        "symptom_macro_f1": macro_f1(symptom_preds, symptom_gts),
        "root_cause_macro_f1": macro_f1(root_preds, root_gts),
        "level_accuracy": {key: sum(values) / len(values) for key, values in level_correct.items()},
    }


def efficiency(results: List[Dict]) -> Dict:
    total_wall = sum(float(result.get("wall_time_seconds", 0)) for result in results)
    total_calls = sum(int(result.get("api_calls", 0)) for result in results)
    total_tokens = sum(int(result.get("total_tokens", 0)) for result in results)
    return {
        "records": len(results),
        "total_wall_time_seconds": total_wall,
        "avg_wall_time_seconds": total_wall / len(results) if results else 0.0,
        "api_calls": total_calls,
        "avg_api_calls": total_calls / len(results) if results else 0.0,
        "total_tokens": total_tokens,
        "avg_tokens": total_tokens / len(results) if results else 0.0,
        "samples_per_hour": (len(results) / total_wall * 3600) if total_wall else 0.0,
        "invalid_output_rate": sum(1 for result in results if result.get("invalid_output")) / len(results) if results else 0.0,
    }


def main() -> None:
    args = parse_args()
    results = load_jsonl(args.predictions)
    gt_by_id = {record.record_id: record for record in load_records(args.task, args.input)}
    metrics = evaluate_filtering(results, gt_by_id) if args.task == "filtering" else evaluate_classification(results, gt_by_id)
    metrics["efficiency"] = efficiency(results)
    print(json.dumps(metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
