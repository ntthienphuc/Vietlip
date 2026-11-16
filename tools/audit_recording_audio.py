"""Audit a consented local recording; audio never enters visual inference or LLMs.

Run with a Python environment containing PyAV and faster-whisper. Use a local
model directory. Original media is preserved; outputs must use a new directory.
ASR is an audit candidate, not an automatically verified reference transcript.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import wave


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.video.is_file() or not args.model_path.is_dir():
        raise FileNotFoundError("A recording and a local Whisper model are required")
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import av
    from faster_whisper import WhisperModel

    wav_path = args.output / "speech.wav"
    with av.open(str(args.video)) as media:
        audio = next(iter(media.streams.audio), None)
        if audio is None:
            raise ValueError("Recording has no audio track")
        metadata = {
            "codec": audio.codec_context.name,
            "sample_rate": audio.codec_context.sample_rate,
            "duration_s": float(audio.duration * audio.time_base) if audio.duration else None,
            "start_s": float(audio.start_time * audio.time_base) if audio.start_time else 0,
        }
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        with wave.open(str(wav_path), "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(16000)
            for frame in media.decode(audio):
                for output in resampler.resample(frame):
                    target.writeframes(output.to_ndarray().tobytes())
            for output in resampler.resample(None):
                target.writeframes(output.to_ndarray().tobytes())
    print("Audio extracted. Auditing locally on CPU, without a reference prompt.", flush=True)
    model = WhisperModel(
        str(args.model_path),
        device="cpu",
        compute_type="int8",
        cpu_threads=2,
        local_files_only=True,
    )
    segments, info = model.transcribe(
        str(wav_path),
        language="vi",
        beam_size=5,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    rows = []
    for segment in segments:
        rows.append(
            {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "avg_logprob": segment.avg_logprob,
                "no_speech_prob": segment.no_speech_prob,
                "words": [
                    {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                    for w in segment.words or []
                ],
            }
        )
        print(f"Audited speech through {segment.end:.1f} seconds", flush=True)
    result = {
        "source": str(args.video.resolve()),
        "source_sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
        "audio": metadata,
        "wav": str(wav_path.resolve()),
        "model": str(args.model_path),
        "device": "cpu/int8",
        "language_probability": info.language_probability,
        "candidate_text": " ".join(row["text"].strip() for row in rows),
        "segments": rows,
        "verified_reference": False,
        "scope": "Local acoustic audit only; ASR candidates need review where unclear.",
        "audio_sent_to_vsr_or_llm": False,
        "reference_prompt_used": False,
    }
    (args.output / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output / "candidate.txt").write_text(result["candidate_text"], encoding="utf-8")
    print(f"Saved {len(rows)} acoustic segments to {args.output}")


if __name__ == "__main__":
    main()
