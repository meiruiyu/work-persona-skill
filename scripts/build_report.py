#!/usr/bin/env python3
"""Build report.json, fill the fixed HTML template, and screenshot it to PNG."""

from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess
import sys
from pathlib import Path


AXIS_COPY = {
    "EI": {"E": "外放协作型", "I": "深潜独立型"},
    "SN": {"S": "具体执行型", "N": "洞察创想型"},
    "TF": {"T": "逻辑结果型", "F": "体验表达型"},
    "JP": {"J": "规划归档型", "P": "灵活探索型"}
}

METRIC_COPY = {
    "E1": lambda d: f"近期样本中识别到 {int(d.get('external_signals', 0))} 条团队/对外交付信号",
    "E2": lambda d: f"协作角色信号 {int(d.get('collaborative_signals', 0))} 条，独立角色信号 {int(d.get('independent_signals', 0))} 条",
    "E3": lambda d: f"协作命名痕迹 {int(d.get('collaboration_named_documents', 0))}，独立命名痕迹 {int(d.get('independent_named_documents', 0))}",
    "S1": lambda d: f"具体任务信号 {int(d.get('specific_signals', 0))} 条，概念探索信号 {int(d.get('novel_signals', 0))} 条",
    "S2": lambda d: f"交付型痕迹 {d.get('delivery_weighted', 0)}，探索型痕迹 {d.get('exploration_weighted', 0)}",
    "S3": lambda d: f"识别到 {int(d.get('convergent_projects', 0))} 个收敛项目与 {int(d.get('branching_projects', 0))} 个分支项目",
    "S4": lambda d: f"有 {int(d.get('high_mix_projects', 0))} 个项目出现跨主题混搭",
    "T1": lambda d: f"逻辑验证信号 {int(d.get('logic_signals', 0))} 条，体验表达信号 {int(d.get('expression_signals', 0))} 条",
    "T2": lambda d: f"计算验证型项目 {int(d.get('compute_projects', 0))} 个，沟通表达型项目 {int(d.get('expression_projects', 0))} 个",
    "T3": lambda d: f"数据验证迭代项目 {int(d.get('data_iteration_projects', 0))} 个，视觉表达迭代项目 {int(d.get('visual_iteration_projects', 0))} 个",
    "J1": lambda d: f"发现 {int(d.get('periodic_chain_count', 0))} 条周期性交付链",
    "J2": lambda d: f"结构化版本痕迹 {d.get('structured_weighted', 0)}，随手版本痕迹 {d.get('unstructured_weighted', 0)}",
    "J3": lambda d: f"明确终态项目 {int(d.get('terminal_projects', 0))} 个，明确开放态项目 {int(d.get('open_projects', 0))} 个",
    "J4": lambda d: f"{int(d.get('consistent_roots', 0))} 个授权工作区具有一致分类体系",
    "J5": lambda d: f"近 180 天整理痕迹 {d.get('organized_weighted', 0)}，散落痕迹 {d.get('scattered_weighted', 0)}",
    "J6": lambda d: f"周期节点修改痕迹 {d.get('deadline_weighted', 0)}"
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--types", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def metric_sentence(metric: dict) -> str:
    builder = METRIC_COPY.get(metric["id"])
    return builder(metric.get("display", {})) if builder else metric["name"]


def gray_quirk(evidence: dict) -> dict:
    gray = evidence["gray_features"]
    candidates = []
    total = gray.get("file_total", {}).get("value", 0)
    if total:
        candidates.append((min(total / 1000, 10), "文件仓库体质", f"授权范围里识别到 {total:,} 个工作相关文件，电脑记得比人牢。"))
    versions = gray.get("unstructured_version_count_weighted", {}).get("value", 0)
    if versions:
        candidates.append((min(versions / 10, 10), "Final 之后还有 Final", f"近期加权后仍有 {versions:g} 个随手版本痕迹，收口常常晚于灵感。"))
    image_total = gray.get("image_total", {}).get("value", 0)
    if image_total:
        candidates.append((min(image_total / 200, 8), "视觉素材囤积区", f"授权范围里有 {image_total:,} 张图片，灵感和截图都舍不得扔。"))
    late = gray.get("late_night_activity_ratio", {}).get("value", 0)
    if late:
        candidates.append((late * 20, "午夜还有尾巴", f"约 {late * 100:.0f}% 的近期修改发生在深夜时段。"))
    if not candidates:
        return {"title": "电脑暂时守口如瓶", "text": "灰名单里还没有足够有趣、又不影响字母的怪癖。", "source": "G"}
    _, title, text = max(candidates, key=lambda item: item[0])
    return {"title": title, "text": text, "source": "G"}


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
    late_ratio = gray.get("late_night_activity_ratio", {}).get("value")
    return [
        {"value": f"{metadata.get('valid_file_count', 0):,}", "label": "有效文件"},
        {"value": f"{metadata.get('project_count', 0):,}", "label": "识别出的项目"},
        {"value": f"{int(peak_hour):02d}:00" if peak_hour is not None else "--", "label": "最高产时段"},
        {"value": f"{late_ratio * 100:.0f}%" if late_ratio is not None else "--", "label": "深夜产出占比"},
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

    all_metrics = []
    for axis_id, axis in score["axes"].items():
        for metric in axis["metrics"]:
            enriched = dict(metric)
            enriched["axis"] = axis_id
            enriched["axis_confidence"] = axis["confidence"]
            supports_chosen = metric["contribution"] >= 0 if axis["chosen_letter"] == axis["left_letter"] else metric["contribution"] <= 0
            if supports_chosen and abs(metric["contribution"]) > 0:
                all_metrics.append(enriched)
    ranked = sorted(all_metrics, key=lambda item: (item["axis_confidence"] == "high", abs(item["contribution"]), item["coverage"]), reverse=True)
    evidence_one = ranked[0] if ranked else None
    workflow_priority = ["J1", "S3", "T2", "J2", "T1"]
    evidence_two = None
    for metric_id in workflow_priority:
        evidence_two = next((item for item in ranked if item["id"] == metric_id and item is not evidence_one), None)
        if evidence_two:
            break
    if not evidence_two:
        evidence_two = next((item for item in ranked if item is not evidence_one), evidence_one)
    quirk = gray_quirk(evidence)

    evidence_slots = []
    if evidence_one:
        evidence_slots.append({"title": evidence_one["name"], "text": metric_sentence(evidence_one), "source": evidence_one["id"]})
    if evidence_two:
        evidence_slots.append({"title": evidence_two["name"], "text": metric_sentence(evidence_two), "source": evidence_two["id"]})
    evidence_slots.append(quirk)
    while len(evidence_slots) < 3:
        evidence_slots.append({"title": "证据还在长大", "text": "当前授权范围较小，更多近期工作资料会让画像更稳定。", "source": "M"})

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

    report = {
        "schema_version": "1.2.0",
        "report_version": "1.2.0-beta",
        "type": type_code,
        "name": profile["name"],
        "camp": f"{profile['camp']}｜{camp['name']}",
        "tagline": profile["tagline"],
        "evidence": evidence_slots[:3],
        "axes": axes,
        "stats": report_stats(evidence),
        "palette": profile["palette"],
        "scarf_group": palette["name"],
        "colors": {key: palette[key] for key in ("bg", "accent", "text", "soft", "track")},
        "personality_image": f"assets/personalities/{profile.get('image', f'{type_code}.png')}",
        "privacy_copy": "只读不改 · 不上传 · 敏感内容自动跳过",
        "campaign_tag": "#生成我的数字分身报告"
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
        for item in report["evidence"]
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
        "{{TYPE}}": html.escape(type_code),
        "{{NAME}}": html.escape(profile["name"]),
        "{{TAGLINE}}": html.escape(profile["tagline"]),
        "{{EVIDENCE}}": evidence_html,
        "{{AXES}}": axes_html,
        "{{STATS}}": stats_html,
        "{{PERSONALITY_DATA}}": personality_data,
        "{{PRIVACY}}": html.escape(report["privacy_copy"]),
        "{{TAG}}": html.escape(report["campaign_tag"]),
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
