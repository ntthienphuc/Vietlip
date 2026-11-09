# PAZ visual speech model attribution

`app/services/vvad_model.py` adapts CNN2Plus1D_Light from
[Octavio Arriaga's PAZ](https://github.com/oarriaga/paz). The upstream code is
MIT licensed; its copyright and license are preserved in this directory.

Local upstream source SHA-256:
`78399482fede72e552a609e222966b7aaac2cd0c46aa27bd79fcd7a9fc55181a`.

The pretrained `cnn-2plus1d-light_weights-35.hdf5` comes from the author's
[VVAD v0.19 release](https://github.com/oarriaga/altamira-data/releases/tag/v0.19).
Original SHA-256:
`8552ad1e7a894a94d2f1496a325c592a2c3df4a6bce85efe24d549f7351e4735`.

The local NumPy export only transposes weight layouts and adds a zero batch
counter for PyTorch. No fitting or quantization is performed. Export SHA-256:
`b32f26769b92dd1043bce2f7836787dbdb8489b92727f741b36fec1fe4187bb3`.
Reproduction script: `experiments/visual_activity_probe/export_torch.py`.

The inspected release describes pretrained models, but does not provide a
separate explicit commercial-data clearance. Code's MIT license is not treated
as proof of rights to all upstream training videos. VietLip remains an internal
application evaluation; this module makes no broader rights or accuracy claim.
