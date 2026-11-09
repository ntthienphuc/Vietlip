"""Score complete causal windows using isolated PAZ VVAD candidate dependencies."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
import numpy as np
import tensorflow as tf


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.input / "SCORES.json"
    if output.exists():
        raise FileExistsError(output)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    sys.path.insert(0, str(args.candidate_root / "upstream"))
    from cnn2Plus1 import CNN2Plus1D
    from vvad_lrs3 import VVAD_LRS3_LSTM

    info = json.loads((args.input / "INPUT.json").read_text(encoding="utf8"))
    crops = np.load(args.input / "face_rgb.npy", mmap_mode="r")
    assert len(crops) == len(info["frames"])
    results = []
    for name, filename, factory in [
        (
            "CNN2Plus1D_Light",
            "cnn-2plus1d-light_weights-35.hdf5",
            lambda: CNN2Plus1D(architecture="CNN2Plus1D_Light"),
        ),
        ("VVAD_LRS3_LSTM", "vvad_lrs3-weights-23.hdf5", VVAD_LRS3_LSTM),
    ]:
        model = factory()
        weights = args.candidate_root / "models" / filename
        model.load_weights(weights)
        infer = tf.function(lambda x: model(x, training=False))
        infer(np.zeros((1, 38, 96, 96, 3), np.float32)).numpy()
        events = []
        for i in range(0, len(crops), 3):
            event = dict(index=i, time=info["frames"][i]["time"])
            if i < 37:
                event.update(score=None, quality="buffering")
            elif any(r["crop_quality"] != "visible" for r in info["frames"][i - 37 : i + 1]):
                event.update(score=None, quality="face_unavailable")
            else:
                clip = np.asarray(crops[i - 37 : i + 1], dtype=np.float32)[None]
                tick = time.perf_counter()
                value = float(infer(clip).numpy()[0, 0])
                elapsed = (time.perf_counter() - tick) * 1000
                event.update(
                    score=value,
                    quality="visible",
                    processing_ms=elapsed,
                    window_start=info["frames"][i - 37]["time"],
                )
            events.append(event)
        result = dict(
            model=name,
            weights_sha256=hashlib.sha256(weights.read_bytes()).hexdigest(),
            events=events,
        )
        results.append(result)
        print(
            json.dumps(
                dict(
                    model=name,
                    windows=sum(e["score"] is not None for e in events),
                    median_ms=float(
                        np.median([e["processing_ms"] for e in events if e["score"] is not None])
                    ),
                )
            ),
            flush=True,
        )
    output.write_text(
        json.dumps(
            dict(
                video_sha256=info["video_sha256"],
                input_sha256=hashlib.sha256((args.input / "INPUT.json").read_bytes()).hexdigest(),
                normalization="RGB float32 0..255; zero mean, as upstream ClassifyVVAD",
                smoothing="none",
                threshold_predeclared=0.5,
                cpu_threads=2,
                models=results,
            ),
            indent=2,
        ),
        encoding="utf8",
    )


if __name__ == "__main__":
    main()
