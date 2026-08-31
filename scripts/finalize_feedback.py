#!/usr/bin/env python3
"""Save beta feedback and atomically refresh all research exports."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


RATING_FIELDS = (
    "ei-fit", "sn-fit", "tf-fit", "jp-fit", "overall-fit",
    "evidence-accuracy", "quirk-fun", "privacy-comfort", "share-intent",
)
AXIS_CHOICE_FIELDS = ("ei-choice", "sn-choice", "tf-choice", "jp-choice")
THREE_CHOICE_FIELDS = ("overall-choice", "evidence-choice", "quirk-choice", "privacy-choice", "share-choice")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--research-consent", choices=("yes", "no"), required=True)
    parser.add_argument("--participant-id")
    parser.add_argument("--psychological-type", required=True)
    parser.add_argument("--psychological-type-source", choices=("self_selected", "unknown", "known", "formal_test", "micro_questions"))
    for field in RATING_FIELDS:
        parser.add_argument(f"--{field}", type=int)
    for field in AXIS_CHOICE_FIELDS:
        parser.add_argument(f"--{field}", choices=("accurate", "mixed", "wrong"))
    for field in THREE_CHOICE_FIELDS:
        parser.add_argument(f"--{field}", choices=("yes", "mixed", "no"))
    parser.add_argument("--improvement-suggestion", default="")
    parser.add_argument("--most-accurate-metric", default="")
    parser.add_argument("--least-accurate-metric", default="")
    parser.add_argument("--occupation-group", default="")
    parser.add_argument("--experience-band", default="")
    args = parser.parse_args()

    skill_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output_dir).expanduser().resolve()
    feedback = output_dir / "feedback.json"
    feedback_command = [
        sys.executable, str(skill_root / "scripts" / "collect_feedback.py"),
        "--score", args.score,
        "--output", str(feedback),
        "--psychological-type", args.psychological_type,
    ]
    if args.psychological_type_source:
        feedback_command.extend(["--psychological-type-source", args.psychological_type_source])
    for field in RATING_FIELDS:
        value = getattr(args, field.replace("-", "_"))
        if value is not None:
            feedback_command.extend([f"--{field}", str(value)])
    for field in AXIS_CHOICE_FIELDS + THREE_CHOICE_FIELDS:
        value = getattr(args, field.replace("-", "_"))
        if value:
            feedback_command.extend([f"--{field}", value])
    if args.improvement_suggestion:
        feedback_command.extend(["--improvement-suggestion", args.improvement_suggestion])
    for field in ("most-accurate-metric", "least-accurate-metric", "occupation-group", "experience-band"):
        value = getattr(args, field.replace("-", "_"))
        if value:
            feedback_command.extend([f"--{field}", value])
    subprocess.run(feedback_command, check=True)

    export_command = [
        sys.executable, str(skill_root / "scripts" / "export_dataset.py"),
        "--evidence", args.evidence,
        "--score", args.score,
        "--config", args.config,
        "--feedback", str(feedback),
        "--output-dir", str(output_dir),
        "--research-consent", args.research_consent,
    ]
    if args.participant_id:
        export_command.extend(["--participant-id", args.participant_id])
    subprocess.run(export_command, check=True)

    return_bundle = output_dir / "work_mbti_return_bundle.zip"
    required = [feedback, output_dir / "data_collection.csv", output_dir / "evidence_table.csv", output_dir / "data_manifest.json", return_bundle]
    missing = [str(path) for path in required if not path.exists() or path.stat().st_size == 0]
    if missing:
        raise SystemExit("Feedback finalization incomplete: " + ", ".join(missing))
    subprocess.run([
        sys.executable, str(skill_root / "scripts" / "validate_products.py"),
        "--output-dir", str(output_dir), "--require-feedback",
    ], check=True)
    print(json.dumps({
        "status": "complete",
        "feedback": str(feedback),
        "data_collection": str(output_dir / "data_collection.csv"),
        "evidence_table": str(output_dir / "evidence_table.csv"),
        "data_manifest": str(output_dir / "data_manifest.json"),
        "return_bundle": str(return_bundle),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
