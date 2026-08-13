# Runtime assets

`20words_mean_face.npy` is the canonical 68-point reference face used by the
upstream Auto-AVSR mouth-alignment pipeline. It is downloaded by
`setup_server.ps1` from:

https://github.com/mpc001/Lipreading_using_Temporal_Convolutional_Networks/blob/master/preprocessing/20words_mean_face.npy

SHA-256 of the copy tested on 2026-07-24:
`DBF68B2044171E1160716DF7C53E8BBFAA0EE8C61FB41171D04CB6092BB81422`.

Important: the upstream repository's LICENSE starts with BSD-style terms but
also contains extra research/prototype and BBC-content commercial restrictions.
Treat this downloaded asset as research-only until legal review. Before a
commercial release, regenerate an equivalent canonical reference from
consented, internally owned landmark data (then rerun output-parity/WER tests),
or obtain explicit permission. The separate Auto-AVSR code repository is
Apache-2.0 licensed upstream.
