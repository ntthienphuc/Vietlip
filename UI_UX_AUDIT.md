# VietLip 1.8.0 — audit UI/UX, 15/11/2026

## Product and observed baseline

Android camera utility for Vietnamese visual speech, Flutter/Material 3.
Camera → local Windows SO17 server over Wi-Fi → live captions → local history,
copy and video export. Three tabs: Đọc môi, Lịch sử, Cài đặt. Preserve automatic
endpointing, one visual recognition profile, portrait orientation, saved data
and existing routes/API.

User rejected the 1.7.0 appearance as dull. The actual baseline was inspected
on connected Samsung SM-G965F / Android 10, not inferred only from code.
Screenshot: `artifacts/ui_refresh_20261115/before/phone.png`. Version 1.7.0
audit/report preserved under that same `before/` folder and in Git history.

## Findings and priorities

| Priority | Evidence | Effect | Applied direction |
| --- | --- | --- | --- |
| P1 | Actual home screenshot: full-width camera card contains a narrow portrait image and large black bands | Small apparent face; much of the main surface is unused | Fill card with uniform scaling; trim outer edges and keep original inference frames |
| P1 | User explicitly wants a clear main transcript frame; white preview surround and white caption panel have weak separation | Caption destination lacks emphasis | Permanent deep blue caption surface, large white type, mint state cue |
| P1 | Large status strip, repeated helper text, nested white cards share similar weight | Many elements compete with camera/text | Compact real readiness row; single line state inside captions; primary action stays pinned |
| P2 | Prior mark is a generic subtitle icon, Nunito/teal treatment feels generic to this product | Weak visual identity | Lip contour mark, cobalt, Vietnamese Be Vietnam Pro typography |
| P2 | History is a repeated list with no overview; result surface resembles other cards | Scanning hierarchy is weak | Saved-session count, restrained rows, transcript-first dark review surface |
| P2 | Settings explains PC connection only in prose | Users must infer which two devices connect | Static phone–Wi-Fi–PC diagram plus real status below the actual check |
| P2 | Empty completed session remains in a warning state after removing its selected video | Idle screen looks like an ongoing failure | Reset empty-session state when discarding the selection; retain nonempty captions |
| P1 during verification | Connection diagram initially overflowed at 360 px / 2× text | Enlarged text makes the page fail | Flexible device labels with wrapping; rerun small-screen checks |

## Design direction

A camera and caption tool with an identifiable, quiet visual system.
Cobalt `#3857D6` for actions; dark ink `#202C45`; canvas `#F4F6FB`;
caption surface `#1C2B49`; mint `#90DCCA` for readable caption state.
One bundled font family for current UI: Be Vietnam Pro, weights 400–700,
with its OFL license. Large actual caption text; compact labels and secondary
metadata. Radii follow roles: 14–16 for small controls, 22–26 for main surfaces.

Camera cover uses equal scale on both axes. It crops edges, never squeezes a
face; recognition still uses the original frames. The face guide keeps portrait
proportions in the visible card. No decorative animation or network font load.

Keep the permanent caption frame, Vietnamese action labels, refreshable real
server state, stable-caption policy, local history/export and 48 px touch targets.
Do not imply improved recognition through styling. LLM is evaluated in a separate
research runner; app/server runtime still has one visual-only mechanism.

## Interaction/accessibility checks

Inspect actual home, live, history, result, settings, error/recovery and copy
feedback on the phone. Exercise long content, narrow phone/tablet widths and
text scale through 2 with existing widget tests. Keep scroll fallback with
controls reachable. Status uses wording/icons as well as color. New layout
introduces no motion; existing reduced-motion behavior remains applicable.

The prior pass read the user-specified Impeccable, Vercel, Anthropic frontend
design, UI UX Pro Max, UX writing and evidence-based critique references.
This pass also reread the Anthropic design guidance and obtained the font from
the official Google Fonts source. No third-party design skills were installed.
These references support decisions; they are not automated audit results.
No full WCAG/TalkBack certification is claimed.
