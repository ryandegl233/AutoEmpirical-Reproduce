"""
Enrich stage1_unified_labels.csv with GitHub issue body and comments.

For records where body/comments are missing but issue_url points to a
valid GitHub issue or PR, this script fetches the content via the GitHub
REST API and writes a new enriched CSV.

Output: data/processed/stage1_enriched.csv  (original file untouched)

Usage:
    python scripts/enrich_stage1_with_github.py
    python scripts/enrich_stage1_with_github.py --token ghp_xxxx
    python scripts/enrich_stage1_with_github.py --dry-run --limit 10
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# GitHub issue/PR URL pattern
_GH_ISSUE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)"
)


def _build_headers(token: Optional[str]) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AutoEmpirical-Enrich/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _gh_get(url: str, headers: dict, retries: int = 3) -> Optional[dict]:
    """GET a GitHub API URL, return parsed JSON or None on permanent failure."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None  # issue deleted or private
            if exc.code in (403, 429):
                # rate limited – read Retry-After or back off exponentially
                retry_after = int(exc.headers.get("Retry-After", 60))
                wait = max(retry_after, 2 ** (attempt + 2))
                print(f"    Rate limited. Waiting {wait}s …")
                time.sleep(wait)
            elif exc.code >= 500:
                time.sleep(2 ** attempt)
            else:
                print(f"    HTTP {exc.code} for {url}")
                return None
        except Exception as exc:  # noqa: BLE001
            print(f"    Error fetching {url}: {exc}")
            time.sleep(2 ** attempt)
    return None


def fetch_issue(owner: str, repo: str, number: str, headers: dict) -> dict:
    """Return {'body': str, 'comments': str, 'title': str} from GitHub API."""
    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    # Issue/PR metadata (body + title)
    issue_data = _gh_get(f"{api_base}/issues/{number}", headers)
    if issue_data is None:
        return {"body": None, "comments": None, "title": None}

    body = issue_data.get("body") or ""
    title = issue_data.get("title") or ""

    # Comments
    comments_data = _gh_get(
        f"{api_base}/issues/{number}/comments?per_page=100", headers
    )
    if comments_data:
        # Concatenate all comment bodies, separated by a marker
        parts = []
        for c in comments_data:
            user = (c.get("user") or {}).get("login", "unknown")
            body_c = (c.get("body") or "").strip()
            if body_c:
                parts.append(f"[{user}]: {body_c}")
        comments_str = "\n\n---\n\n".join(parts) if parts else None
    else:
        comments_str = None

    return {
        "title": title,
        "body": body if body.strip() else None,
        "comments": comments_str,
    }


def enrich(
    input_path: Path,
    output_path: Path,
    token: Optional[str],
    dry_run: bool,
    limit: Optional[int],
    delay: float,
) -> None:
    df = pd.read_csv(input_path, low_memory=False)
    original_len = len(df)

    # Identify rows that need enrichment: missing body AND have a GitHub URL
    needs_body = df["body"].isna()
    has_gh_url = df["issue_url"].str.contains(
        r"https://github\.com/", na=False, regex=True
    )
    mask = needs_body & has_gh_url
    targets = df[mask].copy()

    print(f"Total records : {original_len}")
    print(f"Need enrichment: {mask.sum()} (missing body + valid GitHub URL)")

    if limit:
        targets = targets.head(limit)
        print(f"Limiting to first {limit} rows (--limit flag)")

    if dry_run:
        print("\n[dry-run] Showing first 5 URLs that would be fetched:")
        print(targets["issue_url"].head().to_string())
        return

    headers = _build_headers(token)
    fetched = skipped = failed = 0

    for idx, row in targets.iterrows():
        url = row["issue_url"]
        m = _GH_ISSUE_RE.match(str(url))
        if not m:
            skipped += 1
            continue

        owner, repo, _kind, number = m.groups()
        print(f"  [{fetched + skipped + failed + 1}/{len(targets)}] {owner}/{repo}#{number} … ", end="", flush=True)

        result = fetch_issue(owner, repo, number, headers)

        if result["body"] is None and result["title"] is None:
            print("FAILED (404 or network error)")
            failed += 1
        else:
            # Only overwrite fields that were originally empty
            if pd.isna(df.at[idx, "body"]) and result["body"]:
                df.at[idx, "body"] = result["body"]
            if pd.isna(df.at[idx, "comments"]) and result["comments"]:
                df.at[idx, "comments"] = result["comments"]
            # Overwrite title only if original looks like a raw URL
            orig_title = str(df.at[idx, "title"] or "")
            if orig_title.startswith("http") and result["title"]:
                df.at[idx, "title"] = result["title"]
            fetched += 1
            body_preview = (result["body"] or "")[:60].replace("\n", " ")
            print(f"OK  body={bool(result['body'])} comments={bool(result['comments'])}  \"{body_preview}...\"")

        time.sleep(delay)

    # Summary
    still_missing = df["body"].isna().sum()
    print(f"\n=== Done ===")
    print(f"  Fetched      : {fetched}")
    print(f"  Skipped (no GitHub URL match): {skipped}")
    print(f"  Failed       : {failed}")
    print(f"  Still missing body after enrichment: {still_missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\nSaved enriched dataset → {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich stage1 CSV with GitHub issue body/comments.")
    parser.add_argument(
        "--input",
        default="data/processed/stage1_unified_labels.csv",
        help="Source CSV (not modified).",
    )
    parser.add_argument(
        "--output",
        default="data/processed/stage1_enriched.csv",
        help="Output path for enriched CSV.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token. Falls back to $GITHUB_TOKEN env var.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Seconds to wait between API calls (default 0.8). Lower only with auth token.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched without making any API calls.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N rows (for testing).",
    )
    args = parser.parse_args()

    enrich(
        input_path=ROOT / args.input,
        output_path=ROOT / args.output,
        token=args.token,
        dry_run=args.dry_run,
        limit=args.limit,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
