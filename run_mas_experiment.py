from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoempirical_mas.datasets import load_records
from autoempirical_mas.llm import ModelConfig, build_llm_client, load_env_file
from autoempirical_mas.pipeline import MASPipeline
from autoempirical_mas.prompts import load_base_prompts


VARIANTS = [
    "single_agent",
    "self_consistency",
    "majority_vote",
    "mas_without_evidence",
    "mas_without_critic",
    "mas_without_arbitrator",
    "mas_without_confidence",
    "full_mas",
    "stage2_verify_v2",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AutoEmpirical MAS experiments.")
    parser.add_argument("--task", choices=["filtering", "classification"], required=True)
    parser.add_argument("--variant", choices=VARIANTS, default="full_mas")
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--backend", choices=["openai", "camel", "mock"], default="openai")
    parser.add_argument("--input", default=None, help="Optional CSV override.")
    parser.add_argument("--output", default=None, help="JSONL output path.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--max-tokens", type=int, default=None, help="Optional max completion tokens per API call.")
    parser.add_argument("--quiet", action="store_true", help="Disable per-record progress output.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)
    prompts = load_base_prompts()
    llm = build_llm_client(ModelConfig(model=args.model, backend=args.backend, max_tokens=args.max_tokens))
    pipeline = MASPipeline(llm=llm, base_prompts=prompts, variant=args.variant)

    output = Path(args.output or f"res/mas_{args.task}_{args.variant}_{args.model}.jsonl")
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as handle:
        for index, record in enumerate(load_records(args.task, args.input, args.limit), start=1):
            result = pipeline.run(record)
            handle.write(json.dumps(result.to_jsonable(), ensure_ascii=False) + "\n")
            handle.flush()
            if not args.quiet:
                print(
                    f"[{index}] record_id={result.record_id} "
                    f"calls={result.api_calls} tokens={result.total_tokens} "
                    f"time={result.wall_time_seconds:.1f}s invalid={result.invalid_output}",
                    flush=True,
                )

    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
