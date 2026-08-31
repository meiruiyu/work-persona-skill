#!/usr/bin/env python3
"""Run the complete Marvis work-MBTI pipeline and verify every required product."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", default=[], help="Explicitly authorized work root; repeat for custom scope.")
    parser.add_argument(
        "--scope-preset",
        choices=("desktop", "documents", "downloads", "work-core", "work-triad", "custom"),
        default="custom",
        help="Authorized scope selected by the user. work-core means Desktop + Documents; work-triad also includes Downloads.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        choices=(90, 180, 365),
        default=365,
        help="Fixed recent-file window for scoring. User-facing flow must keep this at 365.",
    )
    parser.add_argument("--exclude", action="append", default=[], help="Excluded path; repeat as needed.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--research-consent", choices=("yes", "no"), required=True)
    parser.add_argument("--display-name", help="Current Marvis account display name; used only in the local poster.")
    parser.add_argument("--participant-id", help="Optional anonymous campaign ID, never a real name or contact detail.")
    parser.add_argument("--app-inventory-json", help="Optional Marvis local app inventory aggregate; stored for research only, not scoring.")
    parser.add_argument("--image-summary-json", help="Optional Marvis local image category aggregate for the authorized file scope.")
    parser.add_argument("--max-docs", type=int, default=300)
    parser.add_argument("--mode", choices=("beta_blind", "campaign_compare"), default="beta_blind")
    parser.add_argument("--psychological-type")
    return parser.parse_args()


def authorized_roots(args) -> list[str]:
    home = Path.home()
    presets = {
        "desktop": [home / "Desktop"],
        "documents": [home / "Documents"],
        "downloads": [home / "Downloads"],
        "work-core": [home / "Desktop", home / "Documents"],
        "work-triad": [home / "Desktop", home / "Documents", home / "Downloads"],
    }
    roots = [Path(item).expanduser() for item in args.root]
    if args.scope_preset != "custom":
        roots = presets[args.scope_preset]
    roots = [path.resolve() for path in roots if path.exists() and path.is_dir()]
    if not roots:
        raise SystemExit("No authorized scan directory is available. Choose a scope option or provide --root for custom scope.")
    return [str(path) for path in roots]


def display_name(args) -> str:
    candidate = (
        args.display_name
        or os.environ.get("MARVIS_ACCOUNT_NAME")
        or os.environ.get("MARVIS_DISPLAY_NAME")
        or os.environ.get("MARVIS_NICKNAME")
        or "小马同学"
    )
    cleaned = " ".join(str(candidate).replace("\n", " ").split()).strip()
    return cleaned[:24] or "小马同学"


def run(command: list[str]):
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        stage = Path(command[1]).stem if len(command) > 1 else command[0]
        raise SystemExit(f"Pipeline stopped at {stage}. Review the message above and retry with a broader authorized scope if evidence was insufficient.") from exc


def main():
    args = parse_args()
    skill_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output_dir).expanduser().resolve()
    temp_dir = output_dir / "internal"
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    evidence = temp_dir / "evidence.json"
    score = temp_dir / "score.json"
    roots = authorized_roots(args)

    collect = [
        sys.executable, str(skill_root / "scripts" / "collect_evidence.py"),
        "--output", str(evidence), "--max-docs", str(args.max_docs),
        "--scope-label", args.scope_preset,
        "--lookback-days", str(args.lookback_days),
    ]
    for root in roots:
        collect.extend(["--root", root])
    excluded = list(args.exclude) + [str(output_dir)]
    for path in excluded:
        collect.extend(["--exclude", path])
    if args.app_inventory_json:
        collect.extend(["--app-inventory-json", args.app_inventory_json])
    if args.image_summary_json:
        collect.extend(["--image-summary-json", args.image_summary_json])
    run(collect)

    scoring = [
        sys.executable, str(skill_root / "scripts" / "score_profile.py"),
        "--mode", args.mode,
        "--evidence", str(evidence),
        "--config", str(skill_root / "references" / "scoring-v1.json"),
        "--output", str(score),
    ]
    if args.psychological_type:
        scoring.extend(["--psychological-type", args.psychological_type])
    run(scoring)

    run([
        sys.executable, str(skill_root / "scripts" / "build_report.py"),
        "--evidence", str(evidence), "--score", str(score),
        "--types", str(skill_root / "references" / "personality-types.json"),
        "--output-dir", str(output_dir),
        "--display-name", display_name(args),
    ])

    dataset = [
        sys.executable, str(skill_root / "scripts" / "export_dataset.py"),
        "--evidence", str(evidence), "--score", str(score),
        "--config", str(skill_root / "references" / "scoring-v1.json"),
        "--output-dir", str(output_dir), "--research-consent", args.research_consent,
    ]
    if args.participant_id:
        dataset.extend(["--participant-id", args.participant_id])
    run(dataset)

    required = [
        output_dir / "report.png",
        output_dir / "report.html",
        output_dir / "report.json",
        output_dir / "data_collection.csv",
        output_dir / "evidence_table.csv",
        output_dir / "data_manifest.json",
        output_dir / "work_mbti_return_bundle.zip",
        evidence,
        score,
    ]
    missing = [str(path) for path in required if not path.exists() or path.stat().st_size == 0]
    if missing:
        raise SystemExit("Pipeline incomplete; missing products: " + ", ".join(missing))
    run([
        sys.executable, str(skill_root / "scripts" / "validate_products.py"),
        "--output-dir", str(output_dir),
    ])
    result = json.loads(score.read_text(encoding="utf-8"))
    print(json.dumps({
        "status": "awaiting_feedback" if args.mode == "beta_blind" else "complete",
        "raw_work_type": result["raw_work_type"],
        "display_type": result["display_type"],
        "primary_product": str(output_dir / "report.png"),
        "research_products": [
            str(output_dir / "work_mbti_return_bundle.zip"),
            str(output_dir / "data_collection.csv"),
            str(output_dir / "evidence_table.csv"),
            str(output_dir / "data_manifest.json"),
        ],
        "return_bundle": str(output_dir / "work_mbti_return_bundle.zip"),
        "internal_products": [str(evidence), str(score)],
        "next_required_action": "collect_beta_feedback" if args.mode == "beta_blind" else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
