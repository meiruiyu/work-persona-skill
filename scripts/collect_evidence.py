#!/usr/bin/env python3
"""Collect privacy-safe work evidence from explicitly authorized roots."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import math
import os
import re
import statistics
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


VERSION = "1.4.0-beta"
NOW = dt.datetime.now(dt.timezone.utc)

EXCLUDED_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".cache", "caches",
    "cache", "tmp", "temp", "trash", ".trash", "packages", "pkgs", "venv",
    ".venv", "site-packages", "deriveddata", "backups.backupdb"
}
SENSITIVE_TERMS = {
    "身份证", "护照", "银行卡", "病历", "病例", "合同", "劳动合同", "密码", "账号",
    "聊天记录", "私密", "证件", "medical", "passport", "bank", "password", "credential",
    "contract", "wechat", "messages", "mail"
}
WORK_EXTENSIONS = {
    ".doc", ".docx", ".pdf", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".tsv",
    ".md", ".txt", ".rtf", ".pages", ".key", ".numbers", ".py", ".ipynb", ".js",
    ".ts", ".tsx", ".html", ".css", ".sql", ".r", ".swift", ".java", ".mov", ".mp4",
    ".psd", ".ai", ".fig", ".sketch", ".jpg", ".jpeg", ".png", ".webp"
}
TEXT_EXTENSIONS = {".md", ".txt", ".html", ".htm", ".css", ".js", ".ts", ".tsx", ".py", ".sql", ".r", ".swift", ".java", ".json", ".csv"}
DOC_EXTENSIONS = {".doc", ".docx", ".pdf", ".ppt", ".pptx", ".md", ".txt", ".rtf", ".pages", ".key", ".html"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".tif", ".tiff"}
ACTIVE_AREA_NAMES = {"desktop", "桌面", "downloads", "download", "下载"}

KEYWORDS = {
    "external": ["汇报", "提案", "brief", "对齐", "评审", "会前", "培训", "分享", "纪要", "新闻稿", "发布", "宣讲", "presentation", "proposal", "review", "meeting"],
    "personal": ["笔记", "草稿", "研究", "实验", "学习", "想法", "todo", "draft", "note", "research", "temp", "test"],
    "collaborative": ["会议", "纪要", "汇报", "提案", "培训", "评审", "对齐", "共享", "review", "meeting", "team", "share"],
    "independent": ["笔记", "研究", "草稿", "实验", "学习", "代码", "模型", "note", "research", "draft", "experiment"],
    "specific": ["排期", "预算", "清单", "提测", "日报", "周报", "月报", "sop", "tracker", "流程", "进度", "schedule", "budget", "checklist"],
    "novel": ["想法", "脑洞", "方向", "选题", "探索", "灵感", "参考", "研究", "moodboard", "idea", "brainstorm", "inspiration", "concept"],
    "delivery": ["sop", "排期", "清单", "tracker", "预算", "流程", "交付", "定稿", "终版", "验收", "schedule", "deliver"],
    "exploration": ["脑暴", "研究", "参考", "moodboard", "灵感", "选题", "草稿", "实验", "brainstorm", "research", "reference", "draft"],
    "logic": ["指标", "模型", "测试", "roi", "dashboard", "forecast", "效率", "规则", "验证", "数据", "分析", "优化", "metric", "model", "test", "analysis", "sql"],
    "expression": ["文案", "传播", "品牌", "调性", "脚本", "故事", "用户", "体验", "共鸣", "设计", "视觉", "内容", "copywriting", "brand", "story", "user", "experience"],
    "terminal": ["定稿", "终版", "交付", "发布", "归档", "复盘", "验收", "final", "approved", "archive", "released"],
    "visual": ["设计", "海报", "视觉", "调色", "排版", "poster", "design", "visual", "layout", "color"],
    "data": ["数据", "模型", "测试", "分析", "验证", "指标", "代码", "脚本", "data", "model", "test", "analysis", "code", "script"]
}

STRUCTURED_VERSION = re.compile(r"(?:^|[_\-\s])(v(?:er)?\s*\d+(?:\.\d+)*|20\d{6}|20\d{2}[-_.]?\d{2}[-_.]?\d{2})(?:$|[_\-\s])", re.I)
UNSTRUCTURED_VERSION = re.compile(r"final|最终|终版|真final|copy|副本|新建文件夹|untitled", re.I)
DATE_TOKEN = re.compile(r"20\d{2}[-_.年]?(?:0?[1-9]|1[0-2])(?:[-_.月]?(?:0?[1-9]|[12]\d|3[01]))?", re.I)
VERSION_TOKEN = re.compile(r"(?:^|[_\-\s])v(?:er)?\s*\d+(?:\.\d+)*(?:$|[_\-\s])", re.I)
ENTITY_HINT = re.compile(r"(?:公司|集团|部门|团队|team|腾讯|字节|阿里|客户|用户|给.{1,8}看)", re.I)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", required=True, help="Explicitly authorized root. Repeat for multiple roots.")
    parser.add_argument("--exclude", action="append", default=[], help="Explicit subpath to exclude. Repeat as needed.")
    parser.add_argument("--output", required=True, help="Output evidence JSON path.")
    parser.add_argument("--max-docs", type=int, default=300, help="Maximum recent documents sampled for transient local classification.")
    parser.add_argument("--sample-chars", type=int, default=200, help="Maximum transient text characters per sampled document.")
    parser.add_argument("--lookback-days", type=int, choices=(90, 180, 365), default=365, help="Include only files modified inside this user-authorized window.")
    parser.add_argument("--scope-label", choices=("desktop", "documents", "downloads", "work-core", "work-triad", "custom"), default="custom", help="Privacy-safe label for the selected directory option.")
    parser.add_argument("--app-inventory-json", help="Optional Marvis local app inventory aggregate. Stored as gray research data only; never scores letters.")
    parser.add_argument("--image-summary-json", help="Optional Marvis local image category aggregate for the authorized scope. Uses counts only, never raw images or OCR text.")
    return parser.parse_args()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def keyword_score(text: str, group: str) -> int:
    lowered = normalize(text)
    return sum(1 for word in KEYWORDS[group] if word in lowered)


def safe_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]


def recency_bucket(mtime: float) -> tuple[str, float, int]:
    when = dt.datetime.fromtimestamp(mtime, dt.timezone.utc)
    age = max(0, (NOW - when).days)
    if age <= 90:
        return "0_90", 1.0, age
    if age <= 180:
        return "91_180", 0.6, age
    if age <= 365:
        return "181_365", 0.3, age
    return "over_365", 0.0, age


def is_sensitive(parts: tuple[str, ...], name: str) -> bool:
    text = normalize(" ".join(parts) + " " + name)
    return any(term in text for term in SENSITIVE_TERMS)


def extract_docx_prefix(path: Path, limit: int) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            data = archive.read("word/document.xml")
        root = ElementTree.fromstring(data)
        text = " ".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
        return text[:limit]
    except Exception:
        return ""


def extract_text_prefix(path: Path, limit: int) -> str:
    if path.suffix.lower() == ".docx":
        return extract_docx_prefix(path, limit)
    if path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return handle.read(limit)
        except OSError:
            return ""
    return ""


def project_key(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    if len(relative.parts) > 1:
        raw = relative.parts[0]
    else:
        stem = re.sub(r"[_\-\s]+", " ", path.stem.lower())
        stem = DATE_TOKEN.sub("", stem)
        stem = VERSION_TOKEN.sub("", stem)
        raw = " ".join(stem.split()[:3]) or "root-files"
    return safe_hash(raw)


def classify_theme(text: str, ext: str) -> str:
    if ext in {".py", ".ipynb", ".js", ".ts", ".tsx", ".sql", ".r", ".swift", ".java", ".csv", ".xlsx", ".parquet"}:
        return "compute"
    if ext in {".mov", ".mp4", ".psd", ".ai", ".fig", ".sketch", ".jpg", ".jpeg", ".png", ".webp"}:
        return "visual"
    if keyword_score(text, "logic") > keyword_score(text, "expression"):
        return "compute"
    if keyword_score(text, "expression"):
        return "expression"
    if keyword_score(text, "novel"):
        return "exploration"
    if keyword_score(text, "specific"):
        return "delivery"
    return "general"


def metric(left: float, right: float, reliability: float, coverage: float, lineage: str, display: dict | None = None, status: str = "available") -> dict:
    if left + right <= 0 or coverage <= 0:
        status = "missing"
        reliability = 0.0
        coverage = 0.0
    return {
        "status": status,
        "left": round(float(left), 4),
        "right": round(float(right), 4),
        "reliability": round(float(reliability), 4),
        "coverage": round(float(min(1, max(0, coverage))), 4),
        "source_lineage": [lineage],
        "display": display or {}
    }


def gray(value, unit: str, lineage: str) -> dict:
    return {"value": value, "unit": unit, "scoring_weight": 0, "source_lineage": [lineage]}


def load_optional_json(path_text: str | None) -> dict:
    if not path_text:
        return {}
    path = Path(path_text).expanduser()
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def numeric_counts(value) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    counts = {}
    for key, raw in value.items():
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if number > 0:
            counts[normalize(str(key))] = number
    return counts


def app_inventory(data: dict) -> tuple[int, dict[str, float], list[str]]:
    """Keep app inventory as optimization data, not scoring evidence."""
    category_counts = numeric_counts(data.get("categories") or data.get("category_counts"))
    names = []
    apps = data.get("apps")
    if isinstance(apps, list):
        for item in apps:
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("display_name") or "").strip()
                category = normalize(str(item.get("category") or item.get("type") or "uncategorized"))
                if category:
                    category_counts[category] = category_counts.get(category, 0) + 1
            else:
                name = str(item).strip()
            if name:
                names.append(name[:80])
    total = int(data.get("total") or data.get("installed_app_count") or len(names) or sum(category_counts.values()) or 0)
    return total, category_counts, sorted(set(names))[:120]


def category_sum(counts: dict[str, float], labels: set[str]) -> float:
    return sum(value for key, value in counts.items() if key in labels)


def project_capped_pair(records: list[dict], left_value, right_value) -> tuple[float, float, int]:
    """Aggregate one normalized vote per project so a project cannot dominate."""
    grouped: dict[str, list[float]] = collections.defaultdict(lambda: [0.0, 0.0])
    for record in records:
        grouped[record["project"]][0] += float(left_value(record))
        grouped[record["project"]][1] += float(right_value(record))
    left = right = 0.0
    eligible = 0
    for project_left, project_right in grouped.values():
        total = project_left + project_right
        if total <= 0:
            continue
        eligible += 1
        left += project_left / total
        right += project_right / total
    return left, right, eligible


def project_coverage(project_count: int) -> float:
    # Seven equally weighted projects keep any one project below 15%.
    return min(1.0, project_count / 7.0)


def main() -> int:
    args = parse_args()
    roots = [Path(value).expanduser().resolve() for value in args.root]
    excluded_paths = [Path(value).expanduser().resolve() for value in args.exclude]
    image_summary = load_optional_json(args.image_summary_json)
    app_summary = load_optional_json(args.app_inventory_json)
    app_total, app_categories, app_names = app_inventory(app_summary)
    missing = [str(root) for root in roots if not root.exists() or not root.is_dir()]
    if missing:
        print(f"Invalid authorized roots: {', '.join(missing)}", file=sys.stderr)
        return 2

    started = dt.datetime.now(dt.timezone.utc)
    excluded = collections.Counter()
    records: list[dict] = []
    batch_times = collections.Counter()
    extension_counts = collections.Counter()
    time_windows = collections.Counter()
    total_bytes = 0
    maximum_file_size = 0

    for root_index, root in enumerate(roots):
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            kept_dirs = []
            for directory in dirs:
                candidate = (current_path / directory).resolve()
                explicitly_excluded = any(candidate == blocked or blocked in candidate.parents for blocked in excluded_paths)
                if explicitly_excluded:
                    excluded["explicit_scope"] += 1
                elif directory.lower() in EXCLUDED_DIRS or directory.startswith(".") or directory.endswith(".app"):
                    excluded["system_cache_package"] += 1
                else:
                    kept_dirs.append(directory)
            dirs[:] = kept_dirs
            for filename in files:
                path = current_path / filename
                try:
                    relative = path.relative_to(root)
                    stat = path.stat()
                except (OSError, ValueError):
                    excluded["unreadable"] += 1
                    continue
                if filename.startswith("."):
                    excluded["hidden"] += 1
                    continue
                if is_sensitive(relative.parts[:-1], filename):
                    excluded["sensitive"] += 1
                    continue
                ext = path.suffix.lower()
                if ext not in WORK_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                    excluded["unsupported"] += 1
                    continue
                bucket, recency, age_days = recency_bucket(stat.st_mtime)
                if age_days > args.lookback_days:
                    excluded["outside_time_window"] += 1
                    continue
                time_windows[bucket] += 1
                extension_counts[ext or "none"] += 1
                total_bytes += stat.st_size
                maximum_file_size = max(maximum_file_size, stat.st_size)
                batch_times[int(stat.st_mtime)] += 1
                name = normalize(path.stem)
                active_area = root.name.lower() in ACTIVE_AREA_NAMES or (
                    bool(relative.parts) and relative.parts[0].lower() in ACTIVE_AREA_NAMES
                )
                records.append({
                    "path": path,
                    "root_index": root_index,
                    "project": project_key(root, path),
                    "name": name,
                    "ext": ext,
                    "mtime": stat.st_mtime,
                    "ctime": stat.st_ctime,
                    "size": stat.st_size,
                    "bucket": bucket,
                    "recency": recency,
                    "age_days": age_days,
                    "depth": max(0, len(relative.parts) - 1),
                    "active_area": active_area,
                    "theme": classify_theme(name, ext)
                })

    duplicate_signatures = collections.Counter((r["size"], r["ext"], r["name"]) for r in records)
    duplicate_count = sum(count - 1 for count in duplicate_signatures.values() if count > 1)
    for record in records:
        record["batch_event"] = batch_times[int(record["mtime"])] > 50

    projects: dict[str, list[dict]] = collections.defaultdict(list)
    for record in records:
        projects[record["project"]].append(record)

    recent_docs = [r for r in records if r["age_days"] <= 90 and r["ext"] in DOC_EXTENSIONS]
    by_project: dict[str, list[dict]] = collections.defaultdict(list)
    for record in sorted(recent_docs, key=lambda item: item["mtime"], reverse=True):
        if len(by_project[record["project"]]) < 20:
            by_project[record["project"]].append(record)
    sampled: list[dict] = []
    queues = [list(items) for items in by_project.values()]
    while queues and len(sampled) < args.max_docs:
        next_queues = []
        for queue in queues:
            if queue and len(sampled) < args.max_docs:
                sampled.append(queue.pop(0))
            if queue:
                next_queues.append(queue)
        queues = next_queues

    semantic = collections.Counter()
    sampled_success = 0
    for record in sampled:
        prefix = extract_text_prefix(record["path"], args.sample_chars)
        if prefix:
            sampled_success += 1
        text = f"{record['name']} {prefix}"
        weight = record["recency"]
        record["semantic_scores"] = {}
        for group in ("external", "personal", "collaborative", "independent", "specific", "novel", "delivery", "exploration", "logic", "expression"):
            value = keyword_score(text, group) * weight
            semantic[group] += value
            record["semantic_scores"][group] = value
        record["sample_theme"] = classify_theme(text, record["ext"])
        prefix = ""

    semantic_success_rate = sampled_success / len(sampled) if sampled else 0.0
    semantic_volume_coverage = semantic_success_rate * min(1.0, len(sampled) / 30.0)

    semantic_pairs = {}
    for key, left_group, right_group in (
        ("E1", "external", "personal"),
        ("E2", "collaborative", "independent"),
        ("S1", "specific", "novel"),
        ("T1", "logic", "expression"),
    ):
        left, right, project_count = project_capped_pair(
            sampled,
            lambda record, group=left_group: record["semantic_scores"].get(group, 0),
            lambda record, group=right_group: record["semantic_scores"].get(group, 0),
        )
        coverage = semantic_volume_coverage * project_coverage(project_count)
        semantic_pairs[key] = (left, right, project_count, coverage)

    eligible_docs = [r for r in records if r["age_days"] <= 365 and r["ext"] in DOC_EXTENSIONS]
    collab_name = sum(r["recency"] for r in eligible_docs if keyword_score(r["name"], "collaborative") or ENTITY_HINT.search(r["name"]))
    independent_name = sum(r["recency"] for r in eligible_docs if keyword_score(r["name"], "independent"))
    e3_left, e3_right, e3_projects = project_capped_pair(
        eligible_docs,
        lambda record: record["recency"] if keyword_score(record["name"], "collaborative") or ENTITY_HINT.search(record["name"]) else 0,
        lambda record: record["recency"] if keyword_score(record["name"], "independent") else 0,
    )

    delivery_count = sum(r["recency"] * max(1, keyword_score(r["name"], "delivery")) for r in records if keyword_score(r["name"], "delivery"))
    exploration_count = sum(r["recency"] * max(1, keyword_score(r["name"], "exploration")) for r in records if keyword_score(r["name"], "exploration"))
    s2_left, s2_right, s2_projects = project_capped_pair(
        records,
        lambda record: record["recency"] * keyword_score(record["name"], "delivery"),
        lambda record: record["recency"] * keyword_score(record["name"], "exploration"),
    )

    structured = sum(r["recency"] for r in records if STRUCTURED_VERSION.search(r["name"]))
    unstructured = sum(r["recency"] for r in records if UNSTRUCTURED_VERSION.search(r["name"]))
    j2_left, j2_right, j2_projects = project_capped_pair(
        records,
        lambda record: record["recency"] if STRUCTURED_VERSION.search(record["name"]) else 0,
        lambda record: record["recency"] if UNSTRUCTURED_VERSION.search(record["name"]) else 0,
    )

    terminal_projects = 0
    open_projects = 0
    convergence_projects = 0
    branching_projects = 0
    low_mix_projects = 0
    high_mix_projects = 0
    compute_projects = 0
    expression_projects = 0
    data_iteration_projects = 0
    visual_iteration_projects = 0
    periodic_groups = collections.defaultdict(list)

    for project_records in projects.values():
        active = [r for r in project_records if r["age_days"] <= 365]
        if not active:
            continue
        # A missing terminal filename is not proof that a project is open. Only
        # mature projects with an explicit terminal or draft/temp signal count.
        if len(active) >= 2:
            if any(keyword_score(r["name"], "terminal") for r in active):
                terminal_projects += 1
            elif any(UNSTRUCTURED_VERSION.search(r["name"]) or keyword_score(r["name"], "independent") for r in active):
                open_projects += 1
        structured_here = sum(bool(STRUCTURED_VERSION.search(r["name"])) for r in active)
        unstructured_here = sum(bool(UNSTRUCTURED_VERSION.search(r["name"])) for r in active)
        if len(active) >= 3:
            if structured_here > unstructured_here and structured_here >= 2:
                convergence_projects += 1
            elif unstructured_here >= 2 or len({r["theme"] for r in active}) >= 3:
                branching_projects += 1
        themes = {r["theme"] for r in active if r["theme"] != "general"}
        if len(active) >= 3:
            if len(themes) <= 1:
                low_mix_projects += 1
            elif len(themes) >= 3:
                high_mix_projects += 1
        compute = sum(r["recency"] for r in active if r["theme"] == "compute")
        expressive = sum(r["recency"] for r in active if r["theme"] in {"visual", "expression"})
        if len(active) >= 2:
            if compute > expressive:
                compute_projects += 1
            elif expressive > compute:
                expression_projects += 1
        data_versions = sum(bool(STRUCTURED_VERSION.search(r["name"])) and r["theme"] == "compute" for r in active)
        visual_versions = sum((bool(STRUCTURED_VERSION.search(r["name"])) or bool(UNSTRUCTURED_VERSION.search(r["name"]))) and r["theme"] == "visual" for r in active)
        if data_versions >= 2:
            data_iteration_projects += 1
        if visual_versions >= 2:
            visual_iteration_projects += 1
        for record in active:
            base = DATE_TOKEN.sub("{date}", record["name"])
            base = VERSION_TOKEN.sub("{version}", base)
            base = re.sub(r"\d+", "{n}", base)
            if "{date}" in base and len(base) >= 6:
                periodic_groups[(record["project"], base)].append(record["mtime"])

    periodic_chain_count = 0
    irregular_chain_count = 0
    periodic_project_votes: dict[str, list[float]] = collections.defaultdict(lambda: [0.0, 0.0])
    for (project_id, _), times in periodic_groups.items():
        if len(times) < 3:
            continue
        days = sorted(dt.datetime.fromtimestamp(value, dt.timezone.utc).date() for value in times)
        intervals = [(b - a).days for a, b in zip(days, days[1:]) if (b - a).days > 0]
        if intervals and (statistics.median(intervals) in range(5, 10) or statistics.median(intervals) in range(25, 36)):
            periodic_chain_count += 1
            periodic_project_votes[project_id][0] += 1
        elif intervals:
            irregular_chain_count += 1
            periodic_project_votes[project_id][1] += 1
    periodic_left = periodic_right = 0.0
    for left, right in periodic_project_votes.values():
        total = left + right
        periodic_left += left / total
        periodic_right += right / total
    eligible_project_count = terminal_projects + open_projects

    top_level_groups: dict[tuple[int, str], set[str]] = collections.defaultdict(set)
    for record in records:
        try:
            relative = record["path"].relative_to(roots[record["root_index"]])
        except (OSError, ValueError):
            continue
        if len(relative.parts) < 2:
            continue
        name = normalize(relative.parts[0])
        if DATE_TOKEN.search(name):
            kind = "date"
        elif any(word in name for word in KEYWORDS["specific"]):
            kind = "stage"
        else:
            kind = "project"
        top_level_groups[(record["root_index"], kind)].add(name)
    folder_kinds = collections.Counter()
    for (root_index, kind), names in top_level_groups.items():
        folder_kinds[(root_index, kind)] += len(names)
    consistent_roots = 0
    mixed_roots = 0
    for root_index in range(len(roots)):
        counts = [count for (idx, _), count in folder_kinds.items() if idx == root_index]
        total = sum(counts)
        if total < 3:
            continue
        if max(counts) / total >= 0.7:
            consistent_roots += 1
        else:
            mixed_roots += 1

    active = [r for r in records if r["age_days"] <= 180 and r["active_area"]]
    organized_active = sum(r["recency"] for r in active if r["depth"] >= 1 and not UNSTRUCTURED_VERSION.search(r["name"]))
    scattered_active = sum(r["recency"] for r in active if r["depth"] == 0 or UNSTRUCTURED_VERSION.search(r["name"]))
    j5_left, j5_right, j5_projects = project_capped_pair(
        active,
        lambda record: record["recency"] if record["depth"] >= 1 and not UNSTRUCTURED_VERSION.search(record["name"]) else 0,
        lambda record: record["recency"] if record["depth"] == 0 or UNSTRUCTURED_VERSION.search(record["name"]) else 0,
    )

    regular_timestamps = 0
    irregular_timestamps = 0
    for record in records:
        if record["age_days"] > 365 or record["batch_event"]:
            continue
        when = dt.datetime.fromtimestamp(record["mtime"])
        is_deadline = when.weekday() == 4 or when.day >= 27 or when.minute <= 5 or when.minute >= 55
        if is_deadline:
            regular_timestamps += record["recency"]
        else:
            irregular_timestamps += record["recency"]
    timestamp_records = [r for r in records if r["age_days"] <= 365 and not r["batch_event"]]
    j6_left, j6_right, j6_projects = project_capped_pair(
        timestamp_records,
        lambda record: record["recency"] if (dt.datetime.fromtimestamp(record["mtime"]).weekday() == 4 or dt.datetime.fromtimestamp(record["mtime"]).day >= 27 or dt.datetime.fromtimestamp(record["mtime"]).minute <= 5 or dt.datetime.fromtimestamp(record["mtime"]).minute >= 55) else 0,
        lambda record: record["recency"] if not (dt.datetime.fromtimestamp(record["mtime"]).weekday() == 4 or dt.datetime.fromtimestamp(record["mtime"]).day >= 27 or dt.datetime.fromtimestamp(record["mtime"]).minute <= 5 or dt.datetime.fromtimestamp(record["mtime"]).minute >= 55) else 0,
    )

    image_records = [r for r in records if r["ext"] in IMAGE_EXTENSIONS]
    screenshot_count = sum(1 for r in image_records if "screenshot" in r["name"] or "截屏" in r["name"] or "截图" in r["name"])
    selfie_count = sum(1 for r in image_records if "photo booth" in normalize(str(r["path"].parent.name)) or "自拍" in r["name"])
    image_categories = numeric_counts(image_summary.get("categories") or image_summary.get("category_counts"))
    recognized_images = int(image_summary.get("recognized_image_count") or image_summary.get("total") or sum(image_categories.values()) or 0)
    image_coverage = min(1.0, recognized_images / max(1, len(image_records))) if image_categories else 0.0
    image_specific = category_sum(image_categories, {
        "chart", "charts", "graph", "graphs", "table", "spreadsheet", "dashboard",
        "document_scan", "document", "receipt", "ticket", "screenshot", "code_screenshot",
        "图表", "表格", "数据图", "仪表盘", "文档扫描", "票据", "截图", "代码截图"
    })
    image_exploratory = category_sum(image_categories, {
        "whiteboard", "brainstorm", "moodboard", "design_reference", "inspiration",
        "concept", "reference", "sketch", "白板", "脑暴", "灵感", "参考", "草图", "概念"
    })
    image_logic = category_sum(image_categories, {
        "chart", "charts", "graph", "graphs", "table", "spreadsheet", "dashboard",
        "code_screenshot", "data_visualization", "数据图", "图表", "表格", "仪表盘", "代码截图"
    })
    image_expression = category_sum(image_categories, {
        "poster", "design", "video_cover", "cover", "brand_visual", "moodboard",
        "illustration", "海报", "设计稿", "封面", "品牌视觉", "插画", "素材"
    })
    # One project can export hundreds of files at once. Treat one project-hour as
    # one activity session so bulk exports and folder migrations cannot invent a
    # fake "most productive hour" for the poster.
    activity_sessions = {}
    active_days = set()
    activity_source_level = "strict_project_hour"
    activity_window_days = 180
    for record in records:
        if record["age_days"] > 180 or record["batch_event"]:
            continue
        when = dt.datetime.fromtimestamp(record["mtime"])
        session_key = (when.date().isoformat(), when.hour, record["project"])
        activity_sessions[session_key] = max(activity_sessions.get(session_key, 0), record["recency"])
        active_days.add(when.date().isoformat())

    # A narrow folder or a bulk export can leave the strict trace empty even
    # when usable modification times exist. Collapse those events to one vote
    # per day-hour so the poster can stay truthful without showing a blank card.
    if not activity_sessions:
        fallback_records = [record for record in records if record["age_days"] <= 180]
        activity_source_level = "collapsed_day_hour_180d"
        if not fallback_records:
            fallback_records = [record for record in records if record["age_days"] <= 365]
            activity_source_level = "collapsed_day_hour_365d"
            activity_window_days = 365
        for record in fallback_records:
            when = dt.datetime.fromtimestamp(record["mtime"])
            session_key = (when.date().isoformat(), when.hour, "collapsed")
            activity_sessions[session_key] = max(activity_sessions.get(session_key, 0), record["recency"])
            active_days.add(when.date().isoformat())

    late_night = 0.0
    weekend = 0.0
    activity_total = 0.0
    hourly_activity = collections.defaultdict(float)
    weekday_activity = collections.defaultdict(float)
    for (day_text, hour, _project), session_weight in activity_sessions.items():
        weekday = dt.date.fromisoformat(day_text).weekday()
        activity_total += session_weight
        hourly_activity[hour] += session_weight
        weekday_activity[weekday] += session_weight
        if hour < 6 or hour >= 23:
            late_night += session_weight
        if weekday >= 5:
            weekend += session_weight

    peak_activity_hour = max(hourly_activity, key=hourly_activity.get) if hourly_activity else None
    ranked_hours = sorted(hourly_activity.values(), reverse=True)
    peak_share = ranked_hours[0] / activity_total if activity_total and ranked_hours else 0
    peak_gap = (ranked_hours[0] - ranked_hours[1]) / activity_total if activity_total and len(ranked_hours) > 1 else peak_share
    session_count = len(activity_sessions)
    active_day_count = len(active_days)
    if session_count >= 80 and active_day_count >= 14 and peak_share >= 0.08 and peak_gap >= 0.01:
        peak_confidence = "high"
    elif session_count >= 30 and active_day_count >= 5 and peak_share >= 0.06 and peak_gap >= 0.005:
        peak_confidence = "medium"
    else:
        peak_confidence = "low"
    if session_count >= 30 and active_day_count >= 5:
        activity_observation_level = "stable"
    elif session_count > 0:
        activity_observation_level = "limited"
    else:
        activity_observation_level = "none"
    peak_activity_period = None
    if peak_activity_hour is not None:
        peak_activity_period = {
            "center_hour": peak_activity_hour,
            "start_hour": (peak_activity_hour - 1) % 24,
            "end_hour": (peak_activity_hour + 1) % 24,
        }
    hourly_distribution = {
        str(hour): round(hourly_activity.get(hour, 0) / activity_total, 4) if activity_total else 0
        for hour in range(24)
    }
    weekday_distribution = {
        str(day): round(weekday_activity.get(day, 0) / activity_total, 4) if activity_total else 0
        for day in range(7)
    }
    extension_distribution = {
        (extension or "no_extension"): count
        for extension, count in sorted(extension_counts.items())
    }

    semantic_reliability = 0.8 if semantic_volume_coverage >= 0.6 else 0.5
    white_metrics = {
        "E1": metric(semantic_pairs["E1"][0], semantic_pairs["E1"][1], semantic_reliability, semantic_pairs["E1"][3], "sample.semantic.audience", {"external_signals": semantic["external"], "personal_signals": semantic["personal"]}, "available" if semantic_pairs["E1"][3] >= 0.6 else "degraded"),
        "E2": metric(semantic_pairs["E2"][0], semantic_pairs["E2"][1], semantic_reliability, semantic_pairs["E2"][3], "sample.semantic.role", {"collaborative_signals": semantic["collaborative"], "independent_signals": semantic["independent"]}, "available" if semantic_pairs["E2"][3] >= 0.6 else "degraded"),
        "E3": metric(e3_left, e3_right, 0.5, project_coverage(e3_projects), "filename.collaboration_entities", {"collaboration_named_documents": round(collab_name, 1), "independent_named_documents": round(independent_name, 1), "eligible_documents": len(eligible_docs)}, "degraded"),
        "E4": metric(0, 0, 0, 0, "app.activity_proxy.collaboration", {"reason": "No separately authorized application activity roots"}, "missing"),
        "S1": metric(semantic_pairs["S1"][0], semantic_pairs["S1"][1], semantic_reliability, semantic_pairs["S1"][3], "sample.semantic.information_style", {"specific_signals": semantic["specific"], "novel_signals": semantic["novel"]}, "available" if semantic_pairs["S1"][3] >= 0.6 else "degraded"),
        "S2": metric(s2_left, s2_right, 1.0, project_coverage(s2_projects), "artifact.role.delivery_exploration", {"delivery_weighted": round(delivery_count, 1), "exploration_weighted": round(exploration_count, 1)}),
        "S3": metric(convergence_projects, branching_projects, 0.5, min(1, (convergence_projects + branching_projects) / 10), "project.version_topology", {"convergent_projects": convergence_projects, "branching_projects": branching_projects}, "degraded"),
        "S4": metric(low_mix_projects, high_mix_projects, 1.0, min(1, (low_mix_projects + high_mix_projects) / 10), "project.topic_mix", {"low_mix_projects": low_mix_projects, "high_mix_projects": high_mix_projects}),
        "S5": metric(image_specific, image_exploratory, 0.6, image_coverage, "marvis.image_category.information_style", {"specific_work_images": image_specific, "exploratory_work_images": image_exploratory, "recognized_images": recognized_images}, "degraded"),
        "T1": metric(semantic_pairs["T1"][0], semantic_pairs["T1"][1], semantic_reliability, semantic_pairs["T1"][3], "sample.semantic.decision_language", {"logic_signals": semantic["logic"], "expression_signals": semantic["expression"]}, "available" if semantic_pairs["T1"][3] >= 0.6 else "degraded"),
        "T2": metric(compute_projects, expression_projects, 0.6, min(1, (compute_projects + expression_projects) / 10), "project.purpose", {"compute_projects": compute_projects, "expression_projects": expression_projects}, "degraded"),
        "T3": metric(data_iteration_projects, visual_iteration_projects, 1.0, min(1, (data_iteration_projects + visual_iteration_projects) / 8), "project.iteration_mode", {"data_iteration_projects": data_iteration_projects, "visual_iteration_projects": visual_iteration_projects}),
        "T4": metric(0, 0, 0, 0, "app.activity_proxy.work_mode", {"reason": "No separately authorized application activity roots"}, "missing"),
        "T5": metric(image_logic, image_expression, 0.6, image_coverage, "marvis.image_category.decision_style", {"logic_work_images": image_logic, "expression_work_images": image_expression, "recognized_images": recognized_images}, "degraded"),
        "J1": metric(periodic_left, periodic_right, 1.0, project_coverage(len(periodic_project_votes)), "filename.periodic_chain", {"periodic_chain_count": periodic_chain_count, "irregular_chain_count": irregular_chain_count, "eligible_chain_templates": periodic_chain_count + irregular_chain_count}),
        "J2": metric(j2_left, j2_right, 1.0, project_coverage(j2_projects), "filename.version_structure", {"structured_weighted": round(structured, 1), "unstructured_weighted": round(unstructured, 1)}),
        "J3": metric(terminal_projects, open_projects, 0.6, min(1, eligible_project_count / 10) if eligible_project_count else 0, "project.terminal_state", {"terminal_projects": terminal_projects, "open_projects": open_projects}, "degraded"),
        "J4": metric(consistent_roots, mixed_roots, 1.0, min(1, sum(folder_kinds.values()) / 7), "folder.taxonomy_consistency", {"consistent_roots": consistent_roots, "mixed_roots": mixed_roots}),
        "J5": metric(j5_left, j5_right, 1.0, project_coverage(j5_projects), "active_area.organization", {"organized_weighted": round(organized_active, 1), "scattered_weighted": round(scattered_active, 1), "window_days": 180}),
        "J6": metric(j6_left, j6_right, 1.0, project_coverage(j6_projects), "timestamp.deadline_regularity", {"deadline_weighted": round(regular_timestamps, 1), "other_weighted": round(irregular_timestamps, 1)})
    }

    gray_features = {
        "file_total": gray(len(records), "files", "filesystem.inventory"),
        "total_size_bytes": gray(total_bytes, "bytes", "filesystem.inventory"),
        "maximum_file_size_bytes": gray(maximum_file_size, "bytes", "filesystem.inventory"),
        "extension_type_count": gray(len(extension_counts), "types", "filesystem.extensions"),
        "duplicate_file_estimate": gray(duplicate_count, "files", "filesystem.duplicate_signature"),
        "installed_app_count": gray(sum(1 for r in records if r["ext"] == ".app"), "apps", "app.installation"),
        "marvis_app_inventory_count": gray(app_total, "apps", "marvis.local_app_inventory"),
        "marvis_app_category_distribution": gray(app_categories, "apps_by_category", "marvis.local_app_inventory"),
        "marvis_app_names": gray(app_names, "app_names", "marvis.local_app_inventory"),
        "image_total": gray(len(image_records), "images", "image.inventory"),
        "marvis_image_recognized_count": gray(recognized_images, "images", "marvis.image_category"),
        "marvis_image_category_distribution": gray(image_categories, "images_by_category", "marvis.image_category"),
        "selfie_ratio": gray(round(selfie_count / len(image_records), 4) if image_records else 0, "ratio", "image.directory_proxy"),
        "screenshot_ratio": gray(round(screenshot_count / len(image_records), 4) if image_records else 0, "ratio", "image.filename_proxy"),
        "late_night_activity_ratio": gray(round(late_night / activity_total, 4) if activity_total else 0, "ratio", "timestamp.project_hour_sessions.180d"),
        "weekend_activity_ratio": gray(round(weekend / activity_total, 4) if activity_total else 0, "ratio", "timestamp.project_hour_sessions.180d"),
        "peak_activity_hour": gray(peak_activity_hour, "hour_0_23", "timestamp.project_hour_sessions.180d"),
        "peak_activity_confidence": gray(peak_confidence, "level", "timestamp.project_hour_sessions.180d"),
        "peak_activity_share": gray(round(peak_share, 4), "ratio", "timestamp.project_hour_sessions.180d"),
        "peak_activity_gap": gray(round(peak_gap, 4), "ratio", "timestamp.project_hour_sessions.180d"),
        "peak_activity_period": gray(peak_activity_period, "three_hour_period", "timestamp.project_hour_sessions.180d"),
        "activity_observation_level": gray(activity_observation_level, "level", "timestamp.project_hour_sessions.180d"),
        "activity_session_count": gray(session_count, "project_hour_sessions", "timestamp.project_hour_sessions.180d"),
        "activity_active_day_count": gray(active_day_count, "days", "timestamp.project_hour_sessions.180d"),
        "activity_source_level": gray(activity_source_level, "level", "timestamp.activity_fallback"),
        "activity_window_days": gray(activity_window_days, "days", "timestamp.activity_fallback"),
        "recent_180_file_count": gray(sum(time_windows.get(key, 0) for key in ("0_90", "91_180")), "files", "filesystem.recency"),
        "hourly_activity_distribution": gray(hourly_distribution, "ratio_by_hour", "timestamp.project_hour_sessions.180d"),
        "weekday_activity_distribution": gray(weekday_distribution, "ratio_by_weekday", "timestamp.project_hour_sessions.180d"),
        "extension_distribution": gray(extension_distribution, "files_by_extension", "filesystem.extensions"),
        "oldest_file_age_days": gray(max((r["age_days"] for r in records), default=0), "days", "filesystem.history"),
        "parallel_project_count": gray(sum(1 for items in projects.values() if any(r["age_days"] <= 90 for r in items)), "projects", "project.activity"),
        "structured_version_count_weighted": gray(round(structured, 1), "weighted_files", "filename.version_structure"),
        "unstructured_version_count_weighted": gray(round(unstructured, 1), "weighted_files", "filename.version_structure")
    }

    finished = dt.datetime.now(dt.timezone.utc)
    output = {
        "schema_version": "1.0.0",
        "metadata": {
            "collector_version": VERSION,
            "scan_started_at": started.isoformat(),
            "scan_finished_at": finished.isoformat(),
            "authorized_root_count": len(roots),
            "authorized_root_ids": [safe_hash(str(root)) for root in roots],
            "scan_scope_preset": args.scope_label,
            "lookback_days": args.lookback_days,
            "time_windows": dict(time_windows),
            "valid_file_count": len(records),
            "project_count": len(projects),
            "unclustered_ratio": round(sum(1 for r in records if r["project"] == safe_hash("root-files")) / len(records), 4) if records else 0,
            "sampled_document_count": len(sampled),
            "sampled_document_success_count": sampled_success,
            "semantic_classification_success_rate": round(semantic_success_rate, 4),
            "semantic_classification_coverage": round(semantic_volume_coverage, 4),
            "image_category_coverage": round(image_coverage, 4),
            "app_inventory_available": bool(app_summary),
            "app_activity_proxy_coverage": 0.0,
            "batch_timestamp_event_count": sum(1 for count in batch_times.values() if count > 50),
            "rules_version": "scoring-v1-compatible",
            "local_model_version": "filename-rules+transient-prefix-v1"
        },
        "white_metrics": white_metrics,
        "gray_features": gray_features,
        "privacy_audit": {
            "raw_text_retained": False,
            "filenames_retained": False,
            "full_paths_retained": False,
            "project_ids_hashed": True,
            "excluded_counts": dict(excluded)
        }
    }
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "files": len(records), "projects": len(projects), "sampled_documents": len(sampled)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
