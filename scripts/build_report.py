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


def format_number(value) -> str:
    number = float(value or 0)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.1f}".rstrip("0").rstrip(".")


def score_metrics(score: dict) -> tuple[dict, dict]:
    metrics = {}
    metric_axes = {}
    for axis_id, axis in score.get("axes", {}).items():
        for metric in axis.get("metrics", []):
            metrics[metric["id"]] = metric
            metric_axes[metric["id"]] = axis_id
    return metrics, metric_axes


def metric_supports_letter(metric: dict, axis: dict) -> bool:
    tendency = float(metric.get("tendency", 0))
    if abs(tendency) < 0.02:
        return False
    chosen = axis.get("chosen_letter")
    return (tendency > 0 and chosen == axis.get("left_letter")) or (
        tendency < 0 and chosen == axis.get("right_letter")
    )


def metric_habit(metric_id: str, display: dict, letter: str) -> dict | None:
    """Explain one scoring metric in plain language while keeping exact counts."""
    copy = {
        ("E1", "E"): ("做出来，就是要给人看", "近期文件里有 {external_signals} 处汇报、提案或发布线索，个人笔记类 {personal_signals} 处。内容不是锁在电脑里，而是准备拿去沟通、交付、见人。"),
        ("E1", "I"): ("先想透，再把活交出去", "近期文件里有 {personal_signals} 处个人笔记或研究线索，对外内容 {external_signals} 处。你习惯先在自己的工作区把事情想明白，再拿出手。"),
        ("E2", "E"): ("会议散了，活还在往前走", "电脑认出 {collaborative_signals} 处纪要、汇报或评审线索，个人研究类 {independent_signals} 处。你做的工作，天然带着和人一起推进的属性。"),
        ("E2", "I"): ("独立深挖，是你的工作主场", "电脑认出 {independent_signals} 处研究、草稿或实验线索，协作类 {collaborative_signals} 处。安静做深做透，是你把活做好的方式。"),
        ("E3", "E"): ("文件名里都站着队友", "有 {collaboration_named_documents} 份文件带协作、人名或组织线索，个人向文件 {independent_named_documents} 份。你的工作不是单机游戏，交付对象一直在线。"),
        ("E3", "I"): ("自己的工作台，自己先打磨", "个人向命名线索有 {independent_named_documents} 处，协作命名线索 {collaboration_named_documents} 处。你更习惯先独立把文件磨到能交付。"),
        ("S1", "S"): ("需求一来，先把具体活做掉", "电脑认出 {specific_signals} 处排期、清单或执行线索，创想类 {novel_signals} 处。你擅长把工作落到今天能做的下一步。"),
        ("S1", "N"): ("一个需求，能长出好几个方向", "电脑认出 {novel_signals} 处想法、选题或探索线索，具体执行类 {specific_signals} 处。工作交到你手里，常常会多出新解法。"),
        ("S2", "S"): ("想法最后都得变成交付", "近期有 {delivery_weighted} 份清单、排期或成品线索，探索类 {exploration_weighted} 份。你不是只想想，工作最后要落到能交出去。"),
        ("S2", "N"): ("灵感先别关，工作还有新可能", "近期有 {exploration_weighted} 份研究、参考或脑暴线索，交付类 {delivery_weighted} 份。你会给需求多留几个值得试的方向。"),
        ("S3", "S"): ("一条路做到底，直到能交作业", "电脑找到 {convergent_projects} 个一路收口的项目，分支探索项目 {branching_projects} 个。你的工作习惯是选定路线后认真做完。"),
        ("S3", "N"): ("方案不止一套，工作多试几条路", "电脑找到 {branching_projects} 个多方向探索项目，单线收口项目 {convergent_projects} 个。你习惯边做边比较，不轻易错过新解法。"),
        ("S4", "S"): ("每个项目各干各的，做事很具体", "有 {low_mix_projects} 个项目主题集中，跨主题项目 {high_mix_projects} 个。工作装进清楚的格子里，推进起来不绕路。"),
        ("S4", "N"): ("跨界拼一拼，需求会长出新东西", "有 {high_mix_projects} 个项目混合了多类内容，单一主题项目 {low_mix_projects} 个。你擅长把不同素材接起来做成新方案。"),
        ("T1", "T"): ("先看数据，再决定怎么做", "近期出现 {logic_signals} 处规则、测试或验证表达，体验表达类 {expression_signals} 处。工作结论要站得住，你才放心交付。"),
        ("T1", "F"): ("做对还不够，还得让人有感觉", "近期出现 {expression_signals} 处用户、体验或故事表达，逻辑验证类 {logic_signals} 处。你做工作时，也一直在想别人会怎么看、怎么感受。"),
        ("T2", "T"): ("结果要算得清，工作才算落地", "电脑认出 {compute_projects} 个数据、代码或验证类项目，表达类 {expression_projects} 个。你习惯用结果和逻辑把活做实。"),
        ("T2", "F"): ("内容活儿，是你的工作主场", "电脑认出 {expression_projects} 个文案、传播或设计类项目，数据代码类 {compute_projects} 个。你不只把需求做完，还要让人看懂、愿意看。"),
        ("T3", "T"): ("每改一版，都要有验证依据", "有 {data_iteration_projects} 个项目留下数据或测试改版，视觉改版项目 {visual_iteration_projects} 个。你认真改工作，不靠感觉拍板。"),
        ("T3", "F"): ("一张图，也值得认真磨", "有 {visual_iteration_projects} 个项目留下视觉改版痕迹，数据验证类 {data_iteration_projects} 个。发布前再调一版，是你对内容交付的基本礼貌。"),
        ("J1", "J"): ("稳定交作业这件事，你是认真的", "电脑记下 {periodic_chain_count} 条固定交付节奏，不定期链条 {irregular_chain_count} 条。周报月报按时来，职场全勤证藏在文件里。"),
        ("J1", "P"): ("节奏可以变，工作照样往前赶", "电脑记下 {irregular_chain_count} 条灵活交付节奏，固定周期 {periodic_chain_count} 条。需求什么时候来，你就什么时候把活接住。"),
        ("J2", "J"): ("版本有编号，认真改也不迷路", "近期结构化版本痕迹约 {structured_weighted} 处，随手版本约 {unstructured_weighted} 处。工作改了几轮，电脑都能顺着编号找到。"),
        ("J2", "P"): ("Final 之后，还有 Final", "近期随手版本痕迹约 {unstructured_weighted} 处，结构化版本约 {structured_weighted} 处。一稿过是传说，认真改才是日常。"),
        ("J3", "J"): ("开了工，也负责把它收回来", "电脑找到 {terminal_projects} 个有明确交付结果的项目，仍开放的项目 {open_projects} 个。工作到你这里，不容易烂尾。"),
        ("J3", "P"): ("项目先别封箱，工作还能继续长", "电脑找到 {open_projects} 个仍在继续的项目，已明确收口的项目 {terminal_projects} 个。你会给需求留下继续改进的空间。"),
        ("J4", "J"): ("文件夹有章法，找活不用考古", "授权范围里有 {consistent_roots} 个目录保持同一套整理方式，混合目录 {mixed_roots} 个。认真归类，是你给未来工作省时间。"),
        ("J4", "P"): ("项目怎么长，文件夹就怎么装", "授权范围里有 {mixed_roots} 个混合整理目录，规则一致目录 {consistent_roots} 个。工作变化快，你的整理方式也跟着变。"),
        ("J5", "J"): ("手头再忙，工作区也尽量收好", "近期整理归位痕迹约 {organized_weighted} 份，散落痕迹约 {scattered_weighted} 份。忙归忙，文件该回哪儿还是尽量回哪儿。"),
        ("J5", "P"): ("桌面是工作现场，不是样板间", "近期散落痕迹约 {scattered_weighted} 份，整理归位约 {organized_weighted} 份。文件摊开不是摆烂，是需求正在同时开工。"),
        ("J6", "J"): ("截止点一到，你的文件会准时出现", "近期约有 {deadline_weighted} 份工作痕迹靠近固定节点，其他时段 {other_weighted} 份。你对交付时间有自己的节拍器。"),
        ("J6", "P"): ("不等整点，想到就把工作往前推", "近期约有 {other_weighted} 份工作痕迹落在灵活时段，节点附近 {deadline_weighted} 份。你的推进节奏不被日历格子绑住。"),
    }.get((metric_id, letter))
    if not copy:
        return None
    title, template = copy
    values = {key: format_number(value) for key, value in display.items()}
    try:
        text = template.format(**values)
    except KeyError:
        return None
    return {"title": title, "text": text, "source": f"W.{metric_id}"}


def fallback_habits(evidence: dict) -> list[dict]:
    """Effort-oriented fallback facts used only when type evidence is too sparse."""
    metadata = evidence.get("metadata", {})
    candidates = []
    recent = feature_value(evidence, "recent_180_file_count")
    if not recent:
        windows = metadata.get("time_windows", {})
        recent = windows.get("0_90", 0) + windows.get("91_180", 0)
    if recent:
        if recent >= 30:
            candidates.append((94, "电脑最近是真的忙", f"近 180 天有 {int(recent):,} 份文件更新过。努没努力，电脑比打卡机更诚实。", "G.recent_180_file_count"))
        else:
            candidates.append((45, "这个工作区，小而专注", f"近 180 天有 {int(recent):,} 份文件更新过。数量不铺张，但每一份都留下了工作痕迹。", "G.recent_180_file_count"))

    project_total = metadata.get("project_count", 0)
    active_projects = feature_value(evidence, "parallel_project_count")
    if project_total:
        active_copy = f"，其中 {int(active_projects):,} 条近 90 天还在继续推进" if active_projects else ""
        candidates.append((100, "项目不是排队来，是一起上", f"电脑从文件和文件夹里找到了 {int(project_total):,} 条项目线索{active_copy}。你的待办不是列表，是一整个项目群。", "M.project_count"))

    periodic = metric_display(evidence, "J1").get("periodic_chain_count", 0)
    if periodic:
        candidates.append((98, "稳定交作业这件事，你是认真的", f"电脑记下了 {int(periodic)} 条固定交作业节奏。周报月报按时来，职场全勤证藏在文件里。", "W.J1"))

    late = feature_value(evidence, "late_night_activity_ratio")
    sessions = feature_value(evidence, "activity_session_count")
    if late and (not sessions or sessions >= 30):
        candidates.append((108 if late >= 0.1 else 76, "下班了，电脑还没下班", f"近 180 天约 {late * 100:.0f}% 的工作痕迹出现在 23:00–06:00。夜深了，你和文件还没散会。", "G.late_night_activity_ratio"))

    weekend = feature_value(evidence, "weekend_activity_ratio")
    if weekend and weekend >= 0.12 and (not sessions or sessions >= 30):
        candidates.append((106, "周末也给工作留了座位", f"近 180 天约 {weekend * 100:.0f}% 的工作痕迹落在周末。别人打开外卖，你还在打开文件。", "G.weekend_activity_ratio"))

    versions = feature_value(evidence, "unstructured_version_count_weighted")
    if versions:
        candidates.append((110, "Final 之后，还有 Final", f"近期约有 {versions:g} 处 final、最终版或副本痕迹。一稿过是传说，认真改才是日常。", "G.unstructured_version_count_weighted"))

    image_total = feature_value(evidence, "image_total")
    if image_total:
        candidates.append((62, "素材先收下，灵感以后会用到", f"电脑里有 {int(image_total):,} 张图片素材。不是舍不得删，是随时在给下一个需求备货。", "G.image_total"))

    convergent = metric_display(evidence, "S3").get("convergent_projects", 0)
    branching = metric_display(evidence, "S3").get("branching_projects", 0)
    if convergent or branching:
        candidates.append((76, "一边开脑洞，一边把活做完", f"电脑找到了 {int(convergent)} 个一路做到交付的项目，还有 {int(branching)} 个仍在试新方向。想法可以多，活也照样往前推。", "W.S3"))

    if not candidates:
        candidates.append((1, "电脑还在慢慢认识你", "这次只找到 0 条足够清楚的近期工作习惯。不是你没努力，是授权范围还不够让电脑看明白。", "M"))

    return [
        {"title": title, "text": text, "source": source}
        for _priority, title, text, source in sorted(candidates, reverse=True)
    ]


def plain_habits(evidence: dict, score: dict, profile: dict) -> list[dict]:
    """Use one type proof, then prioritize two fun and effort-oriented facts."""
    metrics, metric_axes = score_metrics(score)
    selected = []
    seen = set()

    preferred = list(profile.get("evidence_slots", []))
    supportive = []
    for metric_id, metric in metrics.items():
        axis_id = metric_axes[metric_id]
        axis = score["axes"][axis_id]
        if metric_supports_letter(metric, axis):
            supportive.append((abs(float(metric.get("contribution", 0))), metric_id))
    ordered_ids = preferred + [metric_id for _strength, metric_id in sorted(supportive, reverse=True)]

    remaining_supportive = []
    for metric_id in ordered_ids:
        if metric_id in seen or metric_id not in metrics:
            continue
        axis = score["axes"][metric_axes[metric_id]]
        metric = metrics[metric_id]
        if not metric_supports_letter(metric, axis):
            continue
        habit = metric_habit(metric_id, metric.get("display", {}), axis["chosen_letter"])
        if not habit:
            continue
        if not selected:
            selected.append(habit)
            seen.add(metric_id)
        else:
            remaining_supportive.append((metric_id, habit))

    for habit in fallback_habits(evidence):
        if habit["source"] in seen:
            continue
        selected.append(habit)
        seen.add(habit["source"])
        if len(selected) == 3:
            return selected

    for metric_id, habit in remaining_supportive:
        if metric_id in seen:
            continue
        selected.append(habit)
        seen.add(metric_id)
        if len(selected) == 3:
            return selected

    while len(selected) < 3:
        selected.append({
            "title": "这次工作区很精简",
            "text": "本次授权范围里只找到 0 条额外工作习惯，但已有文件仍完成了人格判断。",
            "source": "M",
        })
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
    observation_level = gray.get("activity_observation_level", {}).get("value")
    late_ratio = gray.get("late_night_activity_ratio", {}).get("value")
    activity_sessions = gray.get("activity_session_count", {}).get("value", 0)
    hourly = gray.get("hourly_activity_distribution", {}).get("value") or {}
    if peak_hour is None and hourly:
        observed = {int(hour): float(share or 0) for hour, share in hourly.items()}
        if any(observed.values()):
            peak_hour = max(observed, key=observed.get)
    if late_ratio is None and hourly:
        late_ratio = sum(float(hourly.get(str(hour), hourly.get(hour, 0)) or 0) for hour in (0, 1, 2, 3, 4, 5, 23))
    if observation_level is None:
        active_days = gray.get("activity_active_day_count", {}).get("value", 0)
        observation_level = "stable" if activity_sessions >= 30 and active_days >= 5 else "limited" if activity_sessions else "none"
    peak_value = f"{int(peak_hour):02d}:00前后" if peak_hour is not None else "暂无记录"
    late_value = f"{float(late_ratio or 0) * 100:.0f}%"
    return [
        {"value": f"{metadata.get('valid_file_count', 0):,}", "label": "份工作足迹", "source": "授权目录清洗后的文件计数"},
        {"value": f"{metadata.get('project_count', 0):,}", "label": "个项目线索", "source": "文件夹、命名和时间近邻聚类"},
        {"value": peak_value, "label": "你的高产时段", "source": "近180天去批量事件后的三小时活跃区间", "confidence": peak_confidence, "observation_level": observation_level},
        {"value": late_value, "label": "深夜产出占比", "source": "近180天去批量事件后的项目-小时活动", "session_count": activity_sessions, "observation_level": observation_level},
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

    evidence_slots = plain_habits(evidence, score, profile)

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
