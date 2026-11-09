"""Export the pinned PAZ Light weights; run in the isolated TensorFlow environment."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
import numpy as np
import tensorflow as tf


def main(args):
    args.output.mkdir(parents=True, exist_ok=False)
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    sys.path.insert(0, str(args.candidate_root / "upstream"))
    from cnn2Plus1 import CNN2Plus1D

    source = args.candidate_root / "upstream/cnn2Plus1.py"
    weights = args.candidate_root / "models/cnn-2plus1d-light_weights-35.hdf5"

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if sha(source) != "78399482fede72e552a609e222966b7aaac2cd0c46aa27bd79fcd7a9fc55181a":
        raise ValueError("Unrecognized upstream source")
    if sha(weights) != "8552ad1e7a894a94d2f1496a325c592a2c3df4a6bce85efe24d549f7351e4735":
        raise ValueError("Unrecognized upstream weights")
    model = CNN2Plus1D(architecture="CNN2Plus1D_Light")
    model.load_weights(weights)
    converted = {}

    def pair(prefix, arrays, dense=False):
        kernel, bias = arrays
        converted[prefix + ".weight"] = kernel.T if dense else kernel.transpose(4, 3, 0, 1, 2)
        converted[prefix + ".bias"] = bias

    def conv(prefix, arrays):
        pair(prefix + ".spatial", arrays[:2])
        pair(prefix + ".temporal", arrays[2:])

    def norm(prefix, arrays):
        converted[prefix + ".norm.weight"], converted[prefix + ".norm.bias"] = arrays

    conv("stem", model.layers[1].get_weights())
    for key, value in zip(
        ("weight", "bias", "running_mean", "running_var"), model.layers[2].get_weights()
    ):
        converted["batch_norm." + key] = value
    converted["batch_norm.num_batches_tracked"] = np.array(0, dtype=np.int64)
    for i, layer in enumerate((5, 9, 13)):
        arrays = model.layers[layer].get_weights()
        conv(f"blocks.{i}.first", arrays[:4])
        norm(f"blocks.{i}.first_norm", arrays[4:6])
        conv(f"blocks.{i}.second", arrays[6:10])
        norm(f"blocks.{i}.second_norm", arrays[10:12])
    for i, layer in ((1, 8), (2, 12)):
        arrays = model.layers[layer].get_weights()
        converted[f"blocks.{i}.project.0.weight"] = arrays[0].T[:, :, None, None, None]
        converted[f"blocks.{i}.project.0.bias"] = arrays[1]
        norm(f"blocks.{i}.project.1", arrays[2:])
    pair("output", model.layers[-1].get_weights(), dense=True)
    filename = args.output / "cnn2plus1d_light.npz"
    np.savez_compressed(filename, **converted)
    (args.output / "EXPORT.json").write_text(
        json.dumps(
            dict(
                upstream_source_sha256=sha(source),
                upstream_weights_sha256=sha(weights),
                exported_sha256=sha(filename),
                exported_bytes=filename.stat().st_size,
                tensors=len(converted),
                tensorflow_version=tf.__version__,
                action="Layout conversion only; no training, quantization or pruning",
            ),
            indent=2,
        ),
        encoding="utf8",
    )
    print(filename, filename.stat().st_size, sha(filename), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidate-root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
