#!/usr/bin/env python3
"""Export one privacy-safe research row and a readable evidence table."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--feedback")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--participant-id", help="Optional anonymous campaign ID; never use a real name or contact detail.")
    parser.add_argument("--research-consent", choices=("yes", "no"), required=True)
    return parser.parse_args()


def scalar(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def flatten(prefix: str, value, output: dict):
    if isinstance(value, dict):
        for key in sorted(value):
            flatten(f"{prefix}.{key}" if prefix else key, value[key], output)
    elif isinstance(value, list):
        output[prefix] = scalar(value)
    else:
        output[prefix] = value


def anonymous_run_id(evidence: dict) -> str:
    metadata = evidence["metadata"]
    seed = "|".join([
        metadata.get("collector_version", ""),
        metadata.get("scan_started_at", ""),
        *metadata.get("authorized_root_ids", []),
    ])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def write_return_bundle(output_dir: Path, include_feedback: bool) -> Path:
    bundle_path = output_dir / "work_mbti_return_bundle.zip"
    include_names = [
        "report.png",
        "data_collection.csv",
        "evidence_table.csv",
        "data_manifest.json",
    ]
    if include_feedback:
        include_names.append("feedback.json")
    note = (
        "工作版 MBTI 内测回传包\n"
        "\n"
        "请回传“work_mbti_return_bundle.zip”这个文件夹给Angeline。\n"
        "它是一个 zip 回传包，整体发送即可。\n"
        "里面包含：报告图片、脱敏数据表、证据明细、隐私授权记录"
        + ("、用户反馈。\n" if include_feedback else "。\n")
        + "不需要单独回传 report.html、report.json 或 internal 文件夹。\n"
        + "本包不包含原文、文件名、完整路径、姓名、联系方式或账号信息。\n"
    )
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in include_names:
            path = output_dir / name
            if path.exists() and path.stat().st_size > 0:
                bundle.write(path, arcname=name)
        bundle.writestr("README_请回传这个zip.txt", note)
    return bundle_path


def main():
    args = parse_args()
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    score = json.loads(Path(args.score).read_text(encoding="utf-8"))
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    feedback = json.loads(Path(args.feedback).read_text(encoding="utf-8")) if args.feedback else {}
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = anonymous_run_id(evidence)
    participant_id = args.participant_id or f"anon-{run_id}"
    row = {
        "dataset_schema_version": "1.0.0-beta",
        "anonymous_run_id": run_id,
        "participant_id": participant_id,
        "research_consent": args.research_consent,
        "raw_work_type": score["raw_work_type"],
        "display_type": score["display_type"],
        "scoring_version": score["scoring_version"],
        "scoring_mode": score["mode"],
    }
    flatten("metadata", evidence["metadata"], row)
    flatten("privacy", evidence["privacy_audit"], row)
    flatten("gray", evidence["gray_features"], row)
    for metric_id, metric in sorted(evidence["white_metrics"].items()):
        flatten(f"metric.{metric_id}", metric, row)
    for axis_id, axis in sorted(score["axes"].items()):
        axis_summary = {key: value for key, value in axis.items() if key != "metrics"}
        flatten(f"axis.{axis_id}", axis_summary, row)
        for metric in axis["metrics"]:
            flatten(f"score_metric.{metric['id']}", metric, row)
    if feedback:
        flatten("feedback", feedback, row)
    else:
        row["feedback.status"] = "not_collected"

    collection_path = output_dir / "data_collection.csv"
    with collection_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow({key: scalar(value) for key, value in row.items()})

    table_path = output_dir / "evidence_table.csv"
    table_fields = [
        "anonymous_run_id", "group", "field_id", "status", "left", "right",
        "value", "unit", "reliability", "coverage", "scoring_weight", "source_lineage",
    ]
    nominal_weights = {
        metric["id"]: metric["weight"]
        for axis in config["axes"].values()
        for metric in axis["metrics"]
    }
    with table_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=table_fields)
        writer.writeheader()
        for metric_id, metric in sorted(evidence["white_metrics"].items()):
            writer.writerow({
                "anonymous_run_id": run_id,
                "group": "W_scoring_metric",
                "field_id": metric_id,
                "status": metric["status"],
                "left": metric["left"],
                "right": metric["right"],
                "reliability": metric["reliability"],
                "coverage": metric["coverage"],
                "scoring_weight": nominal_weights[metric_id],
                "source_lineage": scalar(metric["source_lineage"]),
            })
        for field_id, feature in sorted(evidence["gray_features"].items()):
            writer.writerow({
                "anonymous_run_id": run_id,
                "group": "G_research_candidate",
                "field_id": field_id,
                "value": scalar(feature["value"]),
                "unit": feature["unit"],
                "scoring_weight": 0,
                "source_lineage": scalar(feature["source_lineage"]),
            })

    manifest = {
        "schema_version": "1.1.0",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "anonymous_run_id": run_id,
        "participant_id": participant_id,
        "research_consent": args.research_consent,
        "authorization": {
            "authorized_root_count": evidence["metadata"].get("authorized_root_count", 0),
            "authorized_root_ids": evidence["metadata"].get("authorized_root_ids", []),
            "scan_scope_preset": evidence["metadata"].get("scan_scope_preset"),
            "lookback_days": evidence["metadata"].get("lookback_days"),
            "scan_started_at": evidence["metadata"].get("scan_started_at"),
            "scan_finished_at": evidence["metadata"].get("scan_finished_at"),
        },
        "privacy": {
            "contains_raw_text": False,
            "contains_filenames": False,
            "contains_full_paths": False,
            "contains_personal_entities": False,
            "local_only_until_explicit_submission": True,
        },
        "feedback_status": "collected" if feedback else "pending_user_response",
        "feedback_included": bool(feedback),
        "files": [
            "report.png",
            collection_path.name,
            table_path.name,
        ] + (["feedback.json"] if feedback else []),
        "participant_return": {
            "preferred_file": "work_mbti_return_bundle.zip",
            "note": "请回传“work_mbti_return_bundle.zip”这个文件夹给Angeline；report.html、report.json、internal/ 默认不用回传。",
        },
    }
    manifest_path = output_dir / "data_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    bundle_path = write_return_bundle(output_dir, bool(feedback))
    print(json.dumps({
        "data_collection": str(collection_path),
        "evidence_table": str(table_path),
        "manifest": str(manifest_path),
        "return_bundle": str(bundle_path),
        "feedback_included": bool(feedback),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
