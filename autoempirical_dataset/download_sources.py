from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

import pandas as pd


DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".tsv", ".txt", ".md", ".zip"}
DEFAULT_USER_AGENT = "AutoEmpirical-Dataset-Downloader/0.1 (+https://github.com/)"
ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class DownloadPlan:
    category: str
    reason: str
    mode: str
    target_url: str
    filename_hint: str


@dataclass
class DownloadResult:
    paper_id: str
    source_index: Any
    category: str
    status: str
    source_url: str
    target_url: str
    output_path: str = ""
    http_status: str = ""
    content_type: str = ""
    bytes_written: int = 0
    error: str = ""
    reason: str = ""


def sanitize_filename(value: str, fallback: str = "download") -> str:
    name = re.sub(r"[^\w.\-]+", "_", value.strip(), flags=re.UNICODE).strip("._")
    return name or fallback


def extension_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(urllib.parse.unquote(parsed.path)).suffix
    return suffix.lower()


def google_sheet_export_url(url: str) -> Optional[str]:
    match = re.search(r"/spreadsheets/d/([^/]+)", url)
    if not match:
        return None
    return f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=xlsx"


def github_url_parts(url: str) -> Optional[Dict[str, str]]:
    clean = url.strip()
    match = re.match(r"https://github.com/([^/]+)/([^/\s]+)(?:/(blob|tree)/([^/]+)/(.*))?$", clean)
    if not match:
        return None
    owner, repo, kind, ref, path = match.groups()
    return {
        "owner": owner,
        "repo": repo.rstrip(),
        "kind": kind or "",
        "ref": ref or "",
        "path": path or "",
    }


def github_blob_raw_url(url: str) -> Optional[str]:
    parts = github_url_parts(url)
    if not parts or parts["kind"] != "blob":
        return None
    return (
        f"https://raw.githubusercontent.com/{parts['owner']}/{parts['repo']}/"
        f"{parts['ref']}/{parts['path']}"
    )


def github_contents_api_url(url: str) -> Optional[str]:
    parts = github_url_parts(url)
    if not parts:
        return None
    api = f"https://api.github.com/repos/{parts['owner']}/{parts['repo']}/contents"
    if parts["kind"] == "tree" and parts["path"]:
        api += "/" + urllib.parse.quote(parts["path"])
    if parts["ref"]:
        api += f"?ref={urllib.parse.quote(parts['ref'])}"
    return api


def github_archive_url(url: str) -> Optional[str]:
    parts = github_url_parts(url)
    if not parts:
        return None
    ref = parts["ref"] or "HEAD"
    return f"https://github.com/{parts['owner']}/{parts['repo']}/archive/{ref}.zip"


def gitlab_archive_url(url: str) -> Optional[str]:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.netloc != "gitlab.com":
        return None
    project = parsed.path.strip("/")
    if not project:
        return None
    return f"https://gitlab.com/{project}/-/archive/main/{project.split('/')[-1]}-main.zip"


def gitlab_archive_fallback_urls(url: str) -> List[str]:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.netloc != "gitlab.com":
        return []
    project = parsed.path.strip("/")
    if not project:
        return []
    repo = project.split("/")[-1]
    return [
        f"https://gitlab.com/{project}/-/archive/main/{repo}-main.zip",
        f"https://gitlab.com/{project}/-/archive/master/{repo}-master.zip",
    ]


def zenodo_record_id(url: str) -> Optional[str]:
    direct = re.search(r"zenodo\.org/records/(\d+)", url)
    if direct:
        return direct.group(1)
    doi = re.search(r"10\.5281/zenodo\.(\d+)", url)
    if doi:
        return doi.group(1)
    return None


def zenodo_api_url(url: str) -> Optional[str]:
    record_id = zenodo_record_id(url)
    if not record_id:
        return None
    return f"https://zenodo.org/api/records/{record_id}"


def classify_source(row: pd.Series) -> DownloadPlan:
    source_url = str(row.get("supplementary_link", "")).strip()
    source_index = int(row.get("source_index", 0)) if str(row.get("source_index", "")).isdigit() else None

    if "archive.org/download/stackexchange" in source_url:
        return DownloadPlan(
            "deferred_large_secondary",
            "Archive.org StackExchange dump is very large and a secondary artifact.",
            "manual",
            source_url,
            "stackexchange_manual",
        )
    if "bugswarm.org" in source_url:
        return DownloadPlan(
            "deferred_secondary",
            "BugSwarm benchmark is not a primary bug-report source.",
            "manual",
            source_url,
            "bugswarm_manual",
        )
    if "anonymous.4open.science" in source_url or source_index in {9, 23, 38, 44}:
        return DownloadPlan(
            "manual_review",
            "Website or special host needs human confirmation of the actual dataset file.",
            "manual",
            source_url,
            "manual_review",
        )
    sheet_url = google_sheet_export_url(source_url)
    if sheet_url:
        return DownloadPlan(
            "auto_direct",
            "Google Sheets workbook can be exported as xlsx.",
            "direct_file",
            sheet_url,
            "google_sheet_export.xlsx",
        )
    raw_url = github_blob_raw_url(source_url)
    if raw_url:
        filename = sanitize_filename(Path(urllib.parse.unquote(urllib.parse.urlparse(raw_url).path)).name)
        return DownloadPlan(
            "auto_direct",
            "GitHub blob URL can be converted to raw URL.",
            "direct_file",
            raw_url,
            filename,
        )
    if github_contents_api_url(source_url):
        return DownloadPlan(
            "auto_repo_or_dir",
            "GitHub repository or directory can be enumerated through the contents API.",
            "github_contents",
            github_contents_api_url(source_url) or source_url,
            "github_contents",
        )
    if "gitlab.com/" in source_url:
        archive_url = gitlab_archive_url(source_url) or source_url
        return DownloadPlan(
            "auto_repo_or_dir",
            "GitLab repository can be downloaded as an archive.",
            "direct_file",
            archive_url,
            "gitlab_archive.zip",
        )
    zapi = zenodo_api_url(source_url)
    if zapi:
        return DownloadPlan(
            "try_auto_then_manual",
            "Zenodo/DOI is public, but may require manual fallback if API access is blocked.",
            "zenodo",
            zapi,
            "zenodo_record",
        )
    return DownloadPlan(
        "manual_review",
        "Website needs human confirmation of the actual dataset file.",
        "manual",
        source_url,
        "manual_review",
    )


def http_headers() -> Dict[str, str]:
    headers = {"User-Agent": DEFAULT_USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def http_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers=http_headers())


def read_json_url(url: str, timeout: int = 30) -> Any:
    with urllib.request.urlopen(http_request(url), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def content_length(url: str, timeout: int = 30) -> tuple[Optional[int], str, str]:
    request = urllib.request.Request(url, method="HEAD", headers=http_headers())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            size = response.headers.get("content-length")
            return int(size) if size else None, str(response.status), response.headers.get("content-type", "")
    except Exception:
        return None, "", ""


def download_file(url: str, output_path: Path, max_bytes: int, timeout: int = 60) -> DownloadResult:
    if output_path.exists():
        return DownloadResult("", "", "", "already_exists", url, url, str(output_path), bytes_written=output_path.stat().st_size)

    size, head_status, head_type = content_length(url, timeout=timeout)
    if size is not None and size > max_bytes:
        return DownloadResult(
            "",
            "",
            "",
            "manual_needed",
            url,
            url,
            "",
            http_status=head_status,
            content_type=head_type,
            error=f"File exceeds max_bytes ({size} > {max_bytes}).",
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = http_request(url)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        status = str(response.status)
        written = 0
        with output_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise RuntimeError(f"Download exceeded max_bytes ({written} > {max_bytes})")
                handle.write(chunk)
    return DownloadResult("", "", "", "downloaded", url, url, str(output_path), status, content_type, written)


def download_first_available(urls: Iterable[str], output_path: Path, max_bytes: int) -> DownloadResult:
    errors: List[str] = []
    for url in urls:
        try:
            result = download_file(url, output_path, max_bytes)
            result.target_url = url
            return result
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
    return DownloadResult("", "", "", "failed", "", "", error="; ".join(errors))


def candidate_files_from_github(
    api_url: str,
    max_files: int,
    timeout: int = 30,
    progress: Optional[ProgressCallback] = None,
) -> List[Dict[str, str]]:
    found: List[Dict[str, str]] = []
    visited = 0

    def visit(url: str) -> None:
        nonlocal visited
        if visited >= max_files:
            return
        if progress:
            progress(f"scan github api: {url}")
        payload = read_json_url(url, timeout=timeout)
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if visited >= max_files:
                return
            entry_type = entry.get("type")
            path = entry.get("path", "")
            if entry_type == "file":
                visited += 1
                if Path(path).suffix.lower() in DATA_EXTENSIONS and entry.get("download_url"):
                    found.append({"path": path, "download_url": entry["download_url"]})
                    if progress:
                        progress(f"candidate {len(found)}: {path}")
            elif entry_type == "dir" and entry.get("url"):
                visit(entry["url"])

    visit(api_url)
    return found


def zenodo_file_urls(api_url: str, timeout: int = 30) -> List[Dict[str, str]]:
    payload = read_json_url(api_url, timeout=timeout)
    files = payload.get("files", []) if isinstance(payload, dict) else []
    results: List[Dict[str, str]] = []
    for item in files:
        links = item.get("links", {})
        url = links.get("self") or links.get("download")
        key = item.get("key") or item.get("filename") or "zenodo_file"
        if url:
            results.append({"path": key, "download_url": url})
    return results


def enrich_result(base: DownloadResult, row: pd.Series, plan: DownloadPlan, source_url: str) -> DownloadResult:
    base.paper_id = str(row.get("paper_id", ""))
    base.source_index = row.get("source_index", "")
    base.category = plan.category
    base.source_url = source_url
    base.reason = plan.reason
    return base


def download_source(
    row: pd.Series,
    raw_dir: Path,
    dry_run: bool = False,
    max_bytes: int = 500 * 1024 * 1024,
    max_github_files: int = 250,
    progress: Optional[ProgressCallback] = None,
) -> List[DownloadResult]:
    source_url = str(row.get("supplementary_link", "")).strip()
    paper_id = str(row.get("paper_id", ""))
    plan = classify_source(row)
    source_dir = raw_dir / paper_id

    if plan.mode == "manual":
        return [
            DownloadResult(
                paper_id,
                row.get("source_index", ""),
                plan.category,
                "manual_needed",
                source_url,
                plan.target_url,
                reason=plan.reason,
            )
        ]

    if dry_run:
        return [
            DownloadResult(
                paper_id,
                row.get("source_index", ""),
                plan.category,
                "dry_run",
                source_url,
                plan.target_url,
                str(source_dir / plan.filename_hint),
                reason=plan.reason,
            )
        ]

    results: List[DownloadResult] = []
    try:
        if plan.mode == "direct_file":
            target = source_dir / sanitize_filename(plan.filename_hint)
            if progress:
                progress(f"download file: {target}")
            if "gitlab.com/" in source_url:
                result = download_first_available(gitlab_archive_fallback_urls(source_url), target, max_bytes)
            else:
                result = download_file(plan.target_url, target, max_bytes)
            results.append(enrich_result(result, row, plan, source_url))
        elif plan.mode == "github_contents":
            if progress:
                progress(f"enumerate github contents: {plan.target_url}")
            try:
                candidates = candidate_files_from_github(plan.target_url, max_github_files, progress=progress)
            except urllib.error.HTTPError as exc:
                if exc.code == 403:
                    archive_url = github_archive_url(source_url)
                    if archive_url:
                        if progress:
                            progress("github api rate-limited; fallback to repository archive zip")
                        target = source_dir / "github_archive.zip"
                        result = download_file(archive_url, target, max_bytes)
                        results.append(enrich_result(result, row, plan, source_url))
                        return results
                raise
            if not candidates:
                results.append(
                    DownloadResult(
                        paper_id,
                        row.get("source_index", ""),
                        plan.category,
                        "manual_needed",
                        source_url,
                        plan.target_url,
                        reason="No candidate data files found through GitHub contents API.",
                    )
                )
            else:
                total_candidates = len(candidates)
                for candidate_index, candidate in enumerate(candidates, start=1):
                    target = source_dir / sanitize_filename(candidate["path"].replace("/", "__"))
                    if progress:
                        progress(f"download candidate {candidate_index}/{total_candidates}: {candidate['path']}")
                    result = download_file(candidate["download_url"], target, max_bytes)
                    results.append(enrich_result(result, row, plan, source_url))
                    time.sleep(0.1)
        elif plan.mode == "zenodo":
            if progress:
                progress(f"enumerate zenodo record: {plan.target_url}")
            files = zenodo_file_urls(plan.target_url)
            if not files:
                results.append(
                    DownloadResult(
                        paper_id,
                        row.get("source_index", ""),
                        plan.category,
                        "manual_needed",
                        source_url,
                        plan.target_url,
                        reason="Zenodo record has no downloadable files in API response.",
                    )
                )
            total_files = len(files)
            for file_index, item in enumerate(files, start=1):
                target = source_dir / sanitize_filename(item["path"])
                if progress:
                    progress(f"download zenodo file {file_index}/{total_files}: {item['path']}")
                result = download_file(item["download_url"], target, max_bytes)
                results.append(enrich_result(result, row, plan, source_url))
                time.sleep(0.1)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
        results.append(
            DownloadResult(
                paper_id,
                row.get("source_index", ""),
                plan.category,
                "manual_needed" if plan.category in {"try_auto_then_manual", "manual_review"} else "failed",
                source_url,
                plan.target_url,
                error=f"{type(exc).__name__}: {exc}",
                reason=plan.reason,
            )
        )
    return results


def results_to_frame(results: Iterable[DownloadResult]) -> pd.DataFrame:
    return pd.DataFrame([result.__dict__ for result in results])


def manual_needed_frame(status: pd.DataFrame) -> pd.DataFrame:
    if status.empty:
        return status
    return status[status["status"].isin(["manual_needed", "failed"])].copy()
