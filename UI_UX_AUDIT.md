# VietLip — UI/UX audit, 15/11/2026

## Product and flows

Flutter/Material 3 Android client, Vietnamese, Nunito, teal identity. CameraX
captures portrait video; Python/FastAPI on a Windows PC reads visual speech over
local Wi-Fi. Primary path: configure PC address → start camera session → read
captions → finish → review/copy/export from local history. Existing `/read`,
`/history`, `/settings`, `/result` routes and history schema must remain usable.
Video import is another input to the same visual recognition engine.

Baseline: clean Git `177693f`, app 1.6.3, connected SM-G965F (Android 10).
Observed capture, settings, history and a real saved result using ADB screenshots
and accessibility dumps. Baselines: `artifacts/ui_polish_20261115/before/`.
Source alone was not used to judge the rendered UI.

## Priorities and evidence

| Priority | Screen/evidence | User impact | Correction |
| --- | --- | --- | --- |
| P1 | Main screen has no caption destination before live; user explicitly requested a permanent frame | Users cannot predict where words will appear | Keep preview and caption frame visible together from launch; explicit idle prompt |
| P1 | Capture has no visible connection status; stale saved IP only appears in settings | Users start without knowing whether PC is reachable | Show real, refreshable server state with a direct settings action |
| P1 | Capture source contains 3 processing modes, context form and LLM consent; result has LLM and N-best sections | Multiple competing explanations for one task; conflicts with requested visual-only product | Remove LLM UI and runtime; one supported visual mode; retain legacy history fields solely for readback |
| P1 | Start/import buttons share the row equally; controls are within scrolling content | Core action can leave the viewport; import competes with live use | Persistent full-size primary control plus a compact, named import action |
| P1 | Settings reports success until the next explicit check, even after editing the address | A ready state can describe a different address | Clear stale results on edit, validate next to field, disable duplicate checks, add return-to-capture action |
| P1 | History FutureBuilder has loading and success only | Read failure looks like endless loading | Explicit retry state; await refresh; preserve delete semantics |
| P2 | Result leads with warning, large technical chips, mode/model/request identifiers | Transcript is harder to scan; live duration is presented as processing time | Transcript first, concise review note, technical disclosure with correct duration labels |
| P2 | Many 800 font weights (font assets end at 700), card borders and repeated icon tiles | Weak visual hierarchy and excess density | Role-based 400/500/600/700 typography, restrained surfaces, consistent spacing/radii |
| P2 | Some copy mixes “live”, “server”, “full-clip”, “N-best” | Adds technical knowledge to routine tasks | Use “đọc môi”, “máy chủ”, “phụ đề”, “đọc video”; reserve internal details for disclosure |
| P2 | Live layout includes stop inside scroll; diagnostics sheets do not all handle enlarged text | Ending a session or reading details needs extra scrolling | Pin session control; scroll content/sheets; test 360–800 widths and text scale up to 2 |

## Design direction

Calm camera utility: large undistorted portrait image, independent readable
caption surface, one primary action per state. Preserve teal identity, Nunito,
Material feedback, three-tab navigation, automatic visual endpointing and local
history/export. Use 4/8/12/16/24 spacing; 16/20/24 radii by component role;
dark ink, AA-targeted muted text, semantic warning/error colors. Touch targets
at least 48 logical pixels. No decorative animation; honor disabled animations.
State is conveyed with text and icon, never color alone. No accuracy or latency
claims are implied by visual polish.

## Reference reading

Reviewed applicable source guidance, without installing or running third-party
skills/tools: [Impeccable](https://github.com/pbakaus/impeccable) (critique/audit,
polish/clarify/harden/onboard/adapt/distill/typeset/layout/animate/delight),
[Vercel agent guidelines](https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines),
[Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines),
[Anthropic frontend design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md),
[UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill),
[UX writing](https://github.com/plugin87/ux-ui-agent-skills/blob/main/.claude/skills/ux-writing/SKILL.md),
[evidence-based critique](https://github.com/luisoos/ui-skills/blob/main/skills/design-critique/SKILL.md).
Applied principles: hierarchy from the actual task, remove redundant choices,
specific action labels, error recovery, progressive disclosure, real device
inspection, text scaling and touch targets. Web/React-only advice is not treated
as an Android requirement. This is a product audit, not an execution of those
skills' automated audits or a claim of full WCAG compliance.
