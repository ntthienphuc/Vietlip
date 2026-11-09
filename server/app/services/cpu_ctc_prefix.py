"""Small-beam CTC recurrence on CPU to avoid thousands of tiny CUDA launches.

Reuses ESPnet's original NumPy recurrence. The neural CTC head and Transformer
remain on the selected model device. No score pruning or reference text is added.
"""

import numpy as np
import torch
from espnet.nets.ctc_prefix_score import CTCPrefixScore
from espnet.nets.scorer_interface import BatchPartialScorerInterface


class CpuCTCPrefixScorer(BatchPartialScorerInterface):
    def __init__(self, ctc, eos):
        self.ctc, self.eos = ctc, eos
        self.impl = None

    def batch_init_state(self, x):
        logp = self.ctc.log_softmax(x[None]).detach()[0].cpu().numpy()
        self.impl = CTCPrefixScore(logp, 0, self.eos, np)
        self.odim = logp.shape[1]
        return 0.0, self.impl.initial_state()

    def batch_score_partial(self, y, ids, states, x):
        prefixes = y.detach().cpu().numpy()
        choices = ids.detach().cpu().numpy() if ids is not None else None
        scores = np.full((len(prefixes), self.odim), -1e10, dtype=np.float32)
        next_states = []
        for i, prefix in enumerate(prefixes):
            candidates = choices[i] if choices is not None else np.arange(self.odim)
            # ESPnet's vectorized scorer always supplies EOS, even outside prebeam.
            if self.eos not in candidates:
                candidates = np.r_[candidates, self.eos]
            previous_score, previous_state = states[i]
            totals, cache = self.impl(prefix, candidates, previous_state)
            # Upstream NumPy recurrence allocates impossible early states with
            # empty(); they never affect scores, but clear them before reuse so
            # logaddexp cannot read uninitialized NaNs on later tokens.
            cache[:, : max(0, len(prefix) - 2), :] = -1e10
            scores[i, candidates] = totals - previous_score
            scores[i, 0] = -1e10
            next_states.append((candidates, totals, cache))
        return torch.as_tensor(scores, device=x.device, dtype=x.dtype), next_states

    def select_state(self, state, i, new_id=None):
        selected = state[int(i)]
        if new_id is None:
            return selected
        candidates, totals, cache = selected
        where = np.flatnonzero(candidates == int(new_id))
        if not len(where):
            raise ValueError("Beam selected an unscored CTC candidate")
        index = int(where[0])
        return totals[index], cache[index]

    def score_partial(self, y, ids, state, x):
        raise NotImplementedError("Use this adapter with BatchBeamSearch")
