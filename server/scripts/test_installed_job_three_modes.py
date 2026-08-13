from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from scripts.run_sample import _word_error_rate


MODES = ("visual_only", "context_select", "llm_assist")
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def _run_job(
    client: httpx.Client,
    base_url: str,
    video_path: Path,
    mode: str,
    context: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    started = time.perf_counter()
    with video_path.open("rb") as handle:
        response = client.post(
            f"{base_url}/v1/jobs",
            files={"video": (video_path.name, handle, "video/mp4")},
            data={
                "input_kind": "raw_face",
                "mode": mode,
                "context_hint": context if mode != "visual_only" else "",
                "accept_llm_risk": str(mode != "visual_only").lower(),
            },
        )
    response.raise_for_status()
    accepted = response.json()
    job_id = accepted["job_id"]
    timeline = [{"at_seconds": 0.0, **accepted}]
    poll_delay = max(float(accepted.get("poll_after_ms", 800)) / 1000.0, 0.25)

    while True:
        time.sleep(poll_delay)
        job_response = client.get(f"{base_url}/v1/jobs/{job_id}")
        job_response.raise_for_status()
        status = job_response.json()
        timeline.append(
            {
                "at_seconds": round(time.perf_counter() - started, 3),
                "status": status["status"],
                "queue_position": status.get("queue_position"),
            }
        )
        if status["status"] in TERMINAL_STATUSES:
            status["http_elapsed_seconds"] = round(
                time.perf_counter() - started, 3
            )
            return status, timeline


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Clean-installed validation: two clips, three modes",
        "",
        f"Server: `{report['base_url']}`",
        "",
        "| Video | Mode | Status | Visual transcript | Assisted transcript | Visual WER | Assisted WER | Seconds |",
        "|---|---|---:|---|---|---:|---:|---:|",
    ]
    for item in report["results"]:
        def cell(value: Any) -> str:
            if value is None:
                return "—"
            return str(value).replace("|", "\\|").replace("\n", " ")

        lines.append(
            "| "
            + " | ".join(
                [
                    cell(item["video"]),
                    cell(item["mode"]),
                    cell(item["status"]),
                    cell(item.get("transcript")),
                    cell(item.get("assisted_transcript")),
                    cell(item.get("visual_wer")),
                    cell(item.get("assisted_wer")),
                    cell(item.get("http_elapsed_seconds")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "Ghi chú: transcript thị giác luôn được giữ riêng; assisted transcript chỉ xuất hiện ở luồng LLM và cần người dùng rà soát.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:7100")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    samples = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(samples, list) or not samples:
        parser.error("Manifest must be a non-empty JSON list.")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=httpx.Timeout(1800.0, connect=10.0)) as client:
        health_before = client.get(f"{args.base_url}/healthz").raise_for_status().json()
        for sample in samples:
            video_path = Path(sample["path"]).resolve()
            if not video_path.is_file():
                raise FileNotFoundError(video_path)
            reference = str(sample["reference"]).strip()
            context = str(sample["context"]).strip()
            for mode in MODES:
                print(f"START {video_path.name} | {mode}", flush=True)
                try:
                    status, timeline = _run_job(
                        client, args.base_url, video_path, mode, context
                    )
                    record: dict[str, Any] = {
                        "video": video_path.name,
                        "video_path": str(video_path),
                        "mode": mode,
                        "reference": reference,
                        "context_hint": context if mode != "visual_only" else None,
                        "job_id": status.get("job_id"),
                        "request_id": status.get("request_id"),
                        "status": status["status"],
                        "http_elapsed_seconds": status["http_elapsed_seconds"],
                        "timeline": timeline,
                        "error": status.get("error"),
                    }
                    payload = status.get("result") or {}
                    transcript = payload.get("transcript") or ""
                    assisted = payload.get("assisted_transcript")
                    record.update(
                        {
                            "transcript": transcript,
                            "assisted_transcript": assisted,
                            "consensus_transcript": payload.get("consensus_transcript"),
                            "api_elapsed_ms": payload.get("elapsed_ms"),
                            "num_frames": payload.get("num_frames"),
                            "alternatives": payload.get("alternatives"),
                            "risk_notice": payload.get("risk_notice"),
                            "diagnostics": payload.get("diagnostics"),
                        }
                    )
                    if transcript:
                        wer, edits = _word_error_rate(reference, transcript)
                        record["visual_wer"] = round(wer, 6)
                        record["visual_word_edits"] = edits
                    if assisted:
                        wer, edits = _word_error_rate(reference, assisted)
                        record["assisted_wer"] = round(wer, 6)
                        record["assisted_word_edits"] = edits
                except Exception as exc:
                    record = {
                        "video": video_path.name,
                        "video_path": str(video_path),
                        "mode": mode,
                        "reference": reference,
                        "context_hint": context if mode != "visual_only" else None,
                        "status": "client_error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                results.append(record)
                print(
                    f"DONE  {video_path.name} | {mode} | {record['status']} | "
                    f"{record.get('http_elapsed_seconds', 'n/a')}s",
                    flush=True,
                )
        health_after = client.get(f"{args.base_url}/healthz").raise_for_status().json()

    report = {
        "manifest": str(args.manifest.resolve()),
        "base_url": args.base_url,
        "health_before": health_before,
        "health_after": health_after,
        "results": results,
    }
    json_path = args.output_dir / "installed_job_three_mode_results.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = [
        "video",
        "mode",
        "status",
        "http_elapsed_seconds",
        "num_frames",
        "transcript",
        "assisted_transcript",
        "consensus_transcript",
        "visual_wer",
        "assisted_wer",
        "job_id",
        "request_id",
        "error",
    ]
    with (args.output_dir / "installed_job_three_mode_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    (args.output_dir / "README.md").write_text(
        _markdown(report), encoding="utf-8"
    )
    print(json_path.resolve())
    return 0 if all(item["status"] == "completed" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
