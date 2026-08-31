#!/usr/bin/env python3
"""Collect beta feedback after raw scoring; never alter the current score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_TYPES = {a + b + c + d for a in "EI" for b in "SN" for c in "TF" for d in "JP"}
UNKNOWN_TYPE_ALIASES = {"UNKNOWN", "UNSURE", "NOT_SURE", "NA", "N/A", "NONE", "没测过", "不确定", "没测过/不确定"}
AXIS_CHOICE_SCORES = {"accurate": 7, "mixed": 4, "wrong": 1}
THREE_CHOICE_SCORES = {"yes": 6, "mixed": 4, "no": 2}


def ask_rating(prompt: str, optional: bool = False):
    while True:
        value = input(f"{prompt}（1-7{'，回车跳过' if optional else ''}）: ").strip()
        if optional and not value:
            return None
        if value.isdigit() and 1 <= int(value) <= 7:
            return int(value)
        print("请输入 1 到 7。")


def rating(value, prompt: str):
    if value is None:
        return ask_rating(prompt)
    if 1 <= value <= 7:
        return value
    raise SystemExit(f"{prompt} must be from 1 to 7.")


def choice_rating(value, choice, prompt: str, mapping: dict[str, int]):
    if value is not None:
        return rating(value, prompt)
    if choice:
        if choice not in mapping:
            raise SystemExit(f"{prompt} choice must be one of: {', '.join(mapping)}.")
        return mapping[choice]
    return ask_rating(prompt)


def normalize_psychological_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized in UNKNOWN_TYPE_ALIASES:
        return "UNKNOWN"
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--psychological-type")
    parser.add_argument("--psychological-type-source", choices=("self_selected", "unknown", "known", "formal_test", "micro_questions"))
    for field in ("ei-fit", "sn-fit", "tf-fit", "jp-fit", "overall-fit", "evidence-accuracy", "quirk-fun", "privacy-comfort", "share-intent"):
        parser.add_argument(f"--{field}", type=int)
    for field in ("ei-choice", "sn-choice", "tf-choice", "jp-choice"):
        parser.add_argument(f"--{field}", choices=tuple(AXIS_CHOICE_SCORES))
    for field in ("overall-choice", "evidence-choice", "quirk-choice", "privacy-choice", "share-choice"):
        parser.add_argument(f"--{field}", choices=tuple(THREE_CHOICE_SCORES))
    parser.add_argument("--improvement-suggestion", default="")
    parser.add_argument("--most-accurate-metric", default="")
    parser.add_argument("--least-accurate-metric", default="")
    parser.add_argument("--occupation-group", default="")
    parser.add_argument("--experience-band", default="")
    args = parser.parse_args()
    command_mode = args.psychological_type is not None
    score = json.loads(Path(args.score).read_text(encoding="utf-8"))
    raw = score["raw_work_type"]
    psychological = normalize_psychological_type(args.psychological_type) if args.psychological_type else ""
    while psychological not in VALID_TYPES and psychological != "UNKNOWN":
        psychological = normalize_psychological_type(input("你的心理版 MBTI（例如 ENFJ；没测过/不确定可填 UNKNOWN）: "))
        if psychological not in VALID_TYPES and psychological != "UNKNOWN":
            print("请输入有效的 4 字母 MBTI，或输入 UNKNOWN。")
    source = args.psychological_type_source
    if source is None:
        source = "unknown" if psychological == "UNKNOWN" else "self_selected"
    legacy_source_map = {"known": "self_selected", "formal_test": "self_selected", "micro_questions": "self_selected"}
    source = legacy_source_map.get(source, source)
    matched_letters = None if psychological == "UNKNOWN" else sum(a == b for a, b in zip(raw, psychological))
    axis_fit = {
        "EI": choice_rating(args.ei_fit, args.ei_choice, "EI 这一维像不像你的工作方式", AXIS_CHOICE_SCORES),
        "SN": choice_rating(args.sn_fit, args.sn_choice, "SN 这一维像不像你的工作方式", AXIS_CHOICE_SCORES),
        "TF": choice_rating(args.tf_fit, args.tf_choice, "TF 这一维像不像你的工作方式", AXIS_CHOICE_SCORES),
        "JP": choice_rating(args.jp_fit, args.jp_choice, "JP 这一维像不像你的工作方式", AXIS_CHOICE_SCORES),
    }
    output = {
        "schema_version": "1.0.0",
        "raw_work_type": raw,
        "psychological_type": psychological,
        "psychological_type_source": source,
        "matched_letters": matched_letters,
        "axis_fit": axis_fit,
        "overall_fit": choice_rating(args.overall_fit, args.overall_choice, "整体结果像不像你的工作方式", THREE_CHOICE_SCORES),
        "evidence_accuracy": choice_rating(args.evidence_accuracy, args.evidence_choice, "电脑证据准确吗", THREE_CHOICE_SCORES),
        "quirk_fun": choice_rating(args.quirk_fun, args.quirk_choice, "怪癖有趣吗", THREE_CHOICE_SCORES),
        "privacy_comfort": choice_rating(args.privacy_comfort, args.privacy_choice, "隐私体验是否舒适", THREE_CHOICE_SCORES),
        "share_intent": choice_rating(args.share_intent, args.share_choice, "你愿意分享这张报告吗", THREE_CHOICE_SCORES),
        "ui_choices": {
            "EI": args.ei_choice or "",
            "SN": args.sn_choice or "",
            "TF": args.tf_choice or "",
            "JP": args.jp_choice or "",
            "overall": args.overall_choice or "",
            "evidence": args.evidence_choice or "",
            "quirk": args.quirk_choice or "",
            "privacy": args.privacy_choice or "",
            "share": args.share_choice or "",
        },
        "improvement_suggestion": (
            args.improvement_suggestion[:300]
            if command_mode
            else input("你有什么具体改进建议？可留空: ").strip()[:300]
        ),
        "most_accurate_metric": args.most_accurate_metric if command_mode else input("最准的证据指标 ID（可留空）: ").strip(),
        "least_accurate_metric": args.least_accurate_metric if command_mode else input("最离谱的证据指标 ID（可留空）: ").strip(),
        "occupation_group": args.occupation_group if command_mode else input("职业大类（可留空）: ").strip(),
        "experience_band": args.experience_band if command_mode else input("工作年限区间（可留空）: ").strip()
    }
    target = Path(args.output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(target), "matched_letters": output["matched_letters"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
