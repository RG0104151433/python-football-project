# Adopted V5 — presentation base

[中文](README.md) | **English**


Open index.html and go to screen 9. Keep repository_architecture.html beside it. This version is based on frozen V4; V4 remains frozen; the main presentation/index.html now uses this adopted V5.

Hover or keyboard-focus any of the 52 fixture tiles. The panel appears above the grid, showing the two teams, home/away roles, fixture date and the current model's probabilities. In three-way mode, pointing at one of the three colored segments also emphasizes that outcome. In binary/range mode, the panel magnifies the home-win probability and the latent-strength 90% range. Withheld predictions stay withheld.

Move the pointer out of the grid, press Escape or leave the screen to hide the panel. The panel does not capture clicks or obscure access to the underlying controls. Predictions and result-import data are unchanged. The record supplies a match date, not an exact kick-off time; no time is invented.

Rebuild from the full repository with python presentation/build_v5.py. This reads the frozen V4 HTML and appends forecast_hover_v5.js; it publishes V5 to the main entry and does not rebuild or overwrite V4. Browser QA: node presentation/verify_v5.cjs. Verification: ../../v5_verification.json.

The owner adopted V5 as the base on 10 November. The earlier V4 remains a separate backup.

Speaking script: PRESENTATION_SCRIPT_EN.md. Matchday result handoff: RESULTS_DAY_CHECKLIST.md. All actual results are still pending.

Current script revision (11 November): 552–556 spoken words, with separate Chinese action cues. Planned speaking and operation time is 8:25; no timed rehearsal has been completed. The V5 HTML is unchanged.
