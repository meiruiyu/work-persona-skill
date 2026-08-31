#!/usr/bin/env python3
"""Build report.json, fill the fixed HTML template, and screenshot it to PNG."""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import subprocess
import sys
from pathlib import Path


AXIS_COPY = {
    "EI": {"E": "外放协作型", "I": "深潜独立型"},
    "SN": {"S": "具体执行型", "N": "洞察创想型"},
    "TF": {"T": "逻辑结果型", "F": "体验表达型"},
    "JP": {"J": "规划归档型", "P": "灵活探索型"}
}

def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--types", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--display-name", help="Current Marvis account display name for the poster title.")
    return parser.parse_args()


def clean_display_name(value: str | None) -> str:
    candidate = (
        value
        or os.environ.get("MARVIS_ACCOUNT_NAME")
        or os.environ.get("MARVIS_DISPLAY_NAME")
        or os.environ.get("MARVIS_NICKNAME")
        or "小马同学"
    )
    cleaned = " ".join(str(candidate).replace("\n", " ").split()).strip()
    return cleaned[:24] or "小马同学"


def title_font_size(display_name: str) -> int:
    """Fit the account byline without competing with the personality headline."""
    title = f"{display_name}的工作版MBTI"
    width_units = sum(0.58 if ord(char) < 128 else 1.0 for char in title)
    return max(24, min(36, int(680 / max(width_units, 1))))


def feature_value(evidence: dict, key: str, default=0):
    return evidence.get("gray_features", {}).get(key, {}).get("value", default)


def metric_display(evidence: dict, key: str) -> dict:
    return evidence.get("white_metrics", {}).get(key, {}).get("display", {})


def plain_habits(evidence: dict) -> list[dict]:
    """Turn precise evidence into shareable copy without changing the numbers."""
    metadata = evidence.get("metadata", {})
    candidates = []
    recent = feature_value(evidence, "recent_180_file_count")
    if not recent:
        windows = metadata.get("time_windows", {})
        recent = windows.get("0_90", 0) + windows.get("91_180", 0)
    if recent:
        candidates.append((100, "电脑最近是真的忙", f"近 180 天有 {int(recent):,} 份文件更新过。努没努力，电脑比打卡机更诚实。", "G.recent_180_file_count"))

    project_total = metadata.get("project_count", 0)
    active_projects = feature_value(evidence, "parallel_project_count")
    if project_total:
        active_copy = f"，其中 {int(active_projects):,} 条近 90 天还在继续推进" if active_projects else ""
        candidates.append((92, "项目不是排队来，是一起上", f"电脑从文件和文件夹里找到了 {int(project_total):,} 条项目线索{active_copy}。你的待办不是列表，是一整个项目群。", "M.project_count"))

    periodic = metric_display(evidence, "J1").get("periodic_chain_count", 0)
    if periodic:
        candidates.append((90, "稳定交作业这件事，你是认真的", f"电脑记下了 {int(periodic)} 条固定交作业节奏。周报月报按时来，职场全勤证藏在文件里。", "W.J1"))

    late = feature_value(evidence, "late_night_activity_ratio")
    sessions = feature_value(evidence, "activity_session_count")
    if late and (not sessions or sessions >= 30):
        candidates.append((88 if late >= 0.1 else 74, "下班了，电脑还没下班", f"近 180 天约 {late * 100:.0f}% 的工作痕迹出现在 23:00–06:00。夜深了，你和文件还没散会。", "G.late_night_activity_ratio"))

    weekend = feature_value(evidence, "weekend_activity_ratio")
    if weekend and weekend >= 0.12 and (not sessions or sessions >= 30):
        candidates.append((82, "周末也给工作留了座位", f"近 180 天约 {weekend * 100:.0f}% 的工作痕迹落在周末。别人打开外卖，你还在打开文件。", "G.weekend_activity_ratio"))

    versions = feature_value(evidence, "unstructured_version_count_weighted")
    if versions:
        candidates.append((80, "Final 之后，还有 Final", f"近期约有 {versions:g} 处 final、最终版或副本痕迹。一稿过是传说，认真改才是日常。", "G.unstructured_version_count_weighted"))

    image_total = feature_value(evidence, "image_total")
    if image_total:
        candidates.append((62, "素材先收下，灵感以后会用到", f"电脑里有 {int(image_total):,} 张图片素材。不是舍不得删，是随时在给下一个需求备货。", "G.image_total"))

    convergent = metric_display(evidence, "S3").get("convergent_projects", 0)
    branching = metric_display(evidence, "S3").get("branching_projects", 0)
    if convergent or branching:
        candidates.append((76, "一边开脑洞，一边把活做完", f"电脑找到了 {int(convergent)} 个一路做到交付的项目，还有 {int(branching)} 个仍在试新方向。想法可以多，活也照样往前推。", "W.S3"))

    if not candidates:
        candidates.append((1, "电脑还在慢慢认识你", "这次只找到 0 条足够清楚的近期工作习惯。不是你没努力，是授权范围还不够让电脑看明白。", "M"))

    selected = []
    seen_sources = set()
    for _priority, title, text, source in sorted(candidates, reverse=True):
        lineage = source.split(".", 1)[0]
        if source in seen_sources:
            continue
        if len(selected) == 2 and lineage == "M" and any(item["source"].startswith("M.") for item in selected):
            continue
        selected.append({"title": title, "text": text, "source": source})
        seen_sources.add(source)
        if len(selected) == 3:
            break
    while len(selected) < 3:
        selected.append({"title": "忙碌证据还在加载", "text": "这一栏暂时找到 0 条说得准的工作习惯；多选一个近期工作文件夹，电脑就能讲得更具体。", "source": "M"})
    return selected


def confidence_copy(axis: dict) -> str:
    letter = axis["chosen_letter"]
    if axis["confidence"] == "high":
        return f"典型 {letter}"
    if axis["confidence"] == "medium":
        return f"明显偏 {letter}"
    return f"几乎对半，微偏 {letter}"


def confidence_label(value: str) -> str:
    return {"high": "高置信", "medium": "中置信", "low": "低置信"}.get(value, "低置信")


def report_stats(evidence: dict) -> list[dict]:
    metadata = evidence["metadata"]
    gray = evidence["gray_features"]
    peak_hour = gray.get("peak_activity_hour", {}).get("value")
    peak_confidence = gray.get("peak_activity_confidence", {}).get("value", "low")
    late_ratio = gray.get("late_night_activity_ratio", {}).get("value")
    activity_sessions = gray.get("activity_session_count", {}).get("value", 0)
    peak_value = f"{int(peak_hour):02d}:00" if peak_hour is not None and peak_confidence in {"high", "medium"} else "样本不足"
    late_value = f"{late_ratio * 100:.0f}%" if late_ratio is not None and activity_sessions >= 30 else "样本不足"
    return [
        {"value": f"{metadata.get('valid_file_count', 0):,}", "label": "份工作足迹", "source": "授权目录清洗后的文件计数"},
        {"value": f"{metadata.get('project_count', 0):,}", "label": "个项目线索", "source": "文件夹、命名和时间近邻聚类"},
        {"value": peak_value, "label": "你的高产时段", "source": "近180天去批量事件后的项目-小时活跃会话", "confidence": peak_confidence},
        {"value": late_value, "label": "深夜产出占比", "source": "近180天去批量事件后的项目-小时活跃会话", "session_count": activity_sessions},
    ]


def main():
    args = parse_args()
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    score = json.loads(Path(args.score).read_text(encoding="utf-8"))
    types = json.loads(Path(args.types).read_text(encoding="utf-8"))
    type_code = score["display_type"]
    profile = types["types"][type_code]
    camp = types["camps"][profile["camp"]]
    palette = types["palettes"][profile["palette"]]

    evidence_slots = plain_habits(evidence)

    axes = []
    for axis_id in ("EI", "SN", "TF", "JP"):
        axis = score["axes"][axis_id]
        letter = axis["chosen_letter"]
        axes.append({
            "id": axis_id,
            "letter": letter,
            "label": AXIS_COPY[axis_id][letter],
            "score": axis["chosen_score"],
            "confidence": axis["confidence"],
            "confidence_copy": confidence_copy(axis),
            "coverage": axis["coverage"]
        })

    display_name = clean_display_name(args.display_name)
    report = {
        "schema_version": "2.0.0",
        "report_version": "2.0.0-beta",
        "display_name": display_name,
        "type": type_code,
        "name": profile["name"],
        "camp": f"{profile['camp']}｜{camp['name']}",
        "tagline": profile["tagline"],
        "habits": evidence_slots[:3],
        "evidence": evidence_slots[:3],
        "axes": axes,
        "stats": report_stats(evidence),
        "palette": profile["palette"],
        "scarf_group": palette["name"],
        "colors": {key: palette[key] for key in ("bg", "accent", "text", "soft", "track")},
        "personality_image": f"assets/personalities/{profile.get('image', f'{type_code}.png')}",
        "privacy_title": "Marvis本地知识库 · 你的文件管家",
        "privacy_copy": "只读不改 · 敏感内容自动跳过 · 端侧模型生成不上传"
    }

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    skill_root = Path(__file__).resolve().parent.parent
    personality_filename = Path(report["personality_image"]).name
    personality_source = skill_root / "assets" / "personalities" / personality_filename
    if not personality_source.exists():
        raise SystemExit(f"Missing personality image: {personality_source}")
    report_json = output_dir / "report.json"
    report_html = output_dir / "report.html"
    report_png = output_dir / "report.png"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    template_dir = skill_root / "assets" / "report-template"
    template = (template_dir / "template.html").read_text(encoding="utf-8")
    style = (template_dir / "style.css").read_text(encoding="utf-8")
    personality_data = base64.b64encode(personality_source.read_bytes()).decode("ascii")
    evidence_html = "".join(
        '<li><span class="dot"></span><p>'
        f'<strong>{html.escape(item["title"])}</strong>'
        f'<span>：{html.escape(item["text"])}</span></p></li>'
        for item in report["habits"]
    )
    axes_html = "".join(
        '<div class="axis-row">'
        f'<div class="axis-letter">{html.escape(axis["letter"])}</div>'
        f'<div class="axis-label">{html.escape(axis["label"])}</div>'
        '<div class="axis-track">'
        f'<div class="axis-fill" style="width:{axis["score"]}%"></div></div>'
        f'<div class="axis-score">{axis["score"]}</div>'
        f'<div class="axis-confidence">{confidence_label(axis["confidence"])}</div>'
        '</div>'
        for axis in report["axes"]
    )
    stats_html = "".join(
        '<div class="stat">'
        f'<strong>{html.escape(stat["value"])}</strong>'
        f'<span>{html.escape(stat["label"])}</span></div>'
        for stat in report["stats"]
    )
    replacements = {
        "{{STYLE}}": style,
        "{{BG}}": palette["bg"],
        "{{ACCENT}}": palette["accent"],
        "{{TEXT}}": palette["text"],
        "{{SOFT}}": palette["soft"],
        "{{TRACK}}": palette["track"],
        "{{DISPLAY_NAME}}": html.escape(report["display_name"]),
        "{{TITLE_FONT_SIZE}}": str(title_font_size(display_name)),
        "{{TYPE}}": html.escape(type_code),
        "{{NAME}}": html.escape(profile["name"]),
        "{{TAGLINE}}": html.escape(profile["tagline"]),
        "{{EVIDENCE}}": evidence_html,
        "{{AXES}}": axes_html,
        "{{STATS}}": stats_html,
        "{{PERSONALITY_DATA}}": personality_data,
        "{{PRIVACY_TITLE}}": html.escape(report["privacy_title"]),
        "{{PRIVACY}}": html.escape(report["privacy_copy"]),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    report_html.write_text(template, encoding="utf-8")

    subprocess.run([
        sys.executable,
        str(skill_root / "scripts" / "render_report_png.py"),
        "--html", str(report_html),
        "--output", str(report_png),
    ], check=True)
    print(json.dumps({
        "output_dir": str(output_dir),
        "type": type_code,
        "palette": profile["palette"],
        "report_html": str(report_html),
        "report_png": str(report_png),
        "personality_asset": str(personality_source),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
