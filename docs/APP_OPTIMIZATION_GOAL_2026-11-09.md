# Application optimization goal — updated by the user

Current Wi-Fi iteration: see
[`VISUAL_CONFIRMATION_AND_SCENE04_2026-11-10.md`](VISUAL_CONFIRMATION_AND_SCENE04_2026-11-10.md)
for the four real scenes, frozen comparisons, conservative speech confirmation,
and the fresh short-sentence session. SO17 remains selected; confirmation is
opt-in. The release is synchronized to 1.6.3, including the verified
Android export/version and final-caption receipt fixes. The earlier closing
decision below refers to the November 9 checkpoint-selection iteration only.
See `RELEASE_1_6_3_2026-11-10.md` for installed-package/LAN evidence. The overall
optimization goal remains active: free-speech accuracy and broad live silence
rejection have not been established at the user's desired level.

The user expanded the active goal on 2026-11-09: optimize the application as far
as practical, explore the parent Lip project and relevant work, use Vast if useful,
and choose the best supported configuration when further trials stop producing
reliable gains. The phoneme branch is one tested option and is not a requirement
for the final application.

The goal tracker currently exposes status updates only. This project-local note
records the user's revised scope without falsely marking the ongoing goal complete
in order to replace its tracker description.

## Decision requirements

- Prioritize accurate, stable captions from visual input and practical automatic live use.
- Aim for words within 2–3 seconds after speaking; distinguish server endpoint
  latency, client rendering and acoustic speech-end timing.
- Work primarily in this app project, preserve original research weights/data and
  previous experiments. The user has now explicitly requested a new Git repository
  and source synchronization; use a private repository and exclude local media,
  credentials, large checkpoints and generated artifacts.
- Compare alternatives using identical inputs and window boundaries where
  possible. Choose settings using development data, then evaluate other clips.
- Use confirmed references only for labels/scoring, not as prompts/candidate lists
  during visual inference. Disclose data/model independence limits.
- Retain the best supported accuracy/latency/stability compromise. Improvements
  on only one previously used phone clip are insufficient for broad promotion.
- A practical stopping decision requires measured alternatives, a stable usable
  configuration, device/runtime verification and an explicit account of remaining
  recognition limits. It does not require continuing phoneme experiments after
  they cease to help.

## Current evidence and next comparisons

The direct-phoneme experiment in `DIRECT_PHONEME_2026-11-09.md` is complete and is
not promoted: four replay captions total 531/759 errors versus SO17's 496/759.
The new startup preparation and early-empty-window warning correction are applied.
The default app server remains SO17 beam3/CTC .1 with automatic visual endpoints.

Next compare context at boundaries, the supported checkpoint/search alternatives,
and usable pretrained/adaptation approaches identified in the parent project or
primary research sources. Add client timing evidence where it can resolve the
user-visible latency question. Any training must use isolated app-local outputs
and a specified train/development/evaluation protocol.

## UI and delivery scope added by the user

Finish with a minimal, clear interface: large portrait preview at its correct
aspect ratio, large readable captions, understandable connection/activity states,
and unobtrusive secondary options. Clean the application and server code, verify
on the connected Android device, then synchronize a new private Git repository.
Preserve the existing remote and local recordings. Source synchronization does
not mean the app is production-ready or that unseen-speech accuracy is solved.

## Final checkpoint decision

Seven source checkpoints, three averages and three anchored interpolations have
been evaluated. Both dev-selected averages regress at least one phone clip. Keep
SO17 for the application; see `CHECKPOINT_SELECTION_2026-11-09.md`. No additional
phoneme training or Vast rental is needed in this iteration. UI and code maintenance are complete. Device delivery evidence is recorded in
`RELEASE_1_5_0_2026-11-09.md`. The repository was private during this
iteration and is now available at [Vietlip](https://github.com/ntthienphuc/Vietlip). This closes the bounded optimization
iteration while explicitly retaining the documented free-speech accuracy limit.
