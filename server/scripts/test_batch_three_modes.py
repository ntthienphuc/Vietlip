from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import httpx

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from scripts.run_sample import _reference_from_csv, _tokens, _word_error_rate


CONTEXTS = {
    "BAI1439_2": "Một câu trong bài giảng tiếng Việt ở lớp học.",
    "BAITH53_3": "Cô giáo đang hướng dẫn một bài học tiếng Việt.",
    "NHUNG80_2": "Người nói đang kêu gọi người xem theo dõi một kênh nội dung.",
    "ONVAN174_3": "Một câu giải thích trong bài học tiếng Việt.",
}


def safe_reference(path: Path) -> tuple[str | None, str | None]:
    try:
        reference = _reference_from_csv(path).strip()
    except (KeyError, UnicodeError, csv.Error, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not reference or not _tokens(reference):
        return None, "CSV không chứa cột Word hoặc nội dung tham chiếu hợp lệ."
    return reference, None


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:7100")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        help=(
            "Optional JSON mapping video filename/stem to "
            "{reference, context}."
        ),
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("visual_only", "context_select", "llm_assist"),
        default=("visual_only", "context_select", "llm_assist"),
    )
    args = parser.parse_args()

    videos = sorted(args.input_dir.glob("*.mp4"))
    if not videos:
        parser.error("No MP4 files were found.")
    manifest = {}
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary: list[dict] = []
    with httpx.Client(timeout=httpx.Timeout(1200.0, connect=10.0)) as client:
        health_before = (
            client.get(f"{args.base_url}/healthz").raise_for_status().json()
        )
        for video in videos:
            sample = manifest.get(video.name, manifest.get(video.stem, {}))
            if sample.get("reference"):
                reference = str(sample["reference"]).strip()
                reference_error = None
            else:
                csv_path = video.with_suffix(".csv")
                reference, reference_error = safe_reference(csv_path)
            context = str(
                sample.get(
                    "context",
                    CONTEXTS.get(
                        video.stem,
                        "Một câu tiếng Việt trong nội dung giáo dục.",
                    ),
                )
            )
            for mode in args.modes:
                started = time.perf_counter()
                with video.open("rb") as handle:
                    response = client.post(
                        f"{args.base_url}/v1/transcriptions",
                        files={"video": (video.name, handle, "video/mp4")},
                        data={
                            "input_kind": "raw_face",
                            "mode": mode,
                            "context_hint": context if mode != "visual_only" else "",
                            "accept_llm_risk": str(mode != "visual_only").lower(),
                        },
                    )
                elapsed = round(time.perf_counter() - started, 3)
                record = {
                    "video": video.name,
                    "mode": mode,
                    "http_status": response.status_code,
                    "http_elapsed_seconds": elapsed,
                    "context_hint": context if mode != "visual_only" else None,
                    "reference": reference,
                    "reference_error": reference_error,
                }
                if response.is_success:
                    payload = response.json()
                    transcript = payload.get("transcript") or ""
                    assisted = payload.get("assisted_transcript")
                    record.update(
                        {
                            "request_id": payload.get("request_id"),
                            "transcript": transcript,
                            "assisted_transcript": assisted,
                            "api_elapsed_ms": payload.get("elapsed_ms"),
                            "num_frames": payload.get("num_frames"),
                            "alternatives": payload.get("alternatives"),
                            "risk_notice": payload.get("risk_notice"),
                            "diagnostics": payload.get("diagnostics"),
                        }
                    )
                    if reference:
                        visual_wer, visual_edits = _word_error_rate(
                            reference, transcript
                        )
                        record["visual_wer"] = round(visual_wer, 6)
                        record["visual_word_edits"] = visual_edits
                        if assisted:
                            assisted_wer, assisted_edits = _word_error_rate(
                                reference, assisted
                            )
                            record["assisted_wer"] = round(assisted_wer, 6)
                            record["assisted_word_edits"] = assisted_edits
                else:
                    record["error"] = response.text
                summary.append(record)
                print(
                    f"{video.name} | {mode} | HTTP {response.status_code} | "
                    f"{elapsed:.3f}s",
                    flush=True,
                )
        health_after = (
            client.get(f"{args.base_url}/healthz").raise_for_status().json()
        )

    report = {
        "input_dir": str(args.input_dir.resolve()),
        "base_url": args.base_url,
        "health_before": health_before,
        "health_after": health_after,
        "results": summary,
    }
    json_path = args.output_dir / "three_mode_results.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_path = args.output_dir / "three_mode_summary.csv"
    fields = [
        "video",
        "mode",
        "http_status",
        "http_elapsed_seconds",
        "num_frames",
        "transcript",
        "assisted_transcript",
        "visual_wer",
        "assisted_wer",
        "reference_error",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary)
    print(json_path.resolve())
    print(csv_path.resolve())
    return 0 if all(item["http_status"] == 200 for item in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
