# Video verification — 2026-11-05

Run: run-20261104T182905355791Z
Preprocessing: ptit-v4-contextual-dc-20261105

- Rebuilt and trained all five models with the current preprocessing.
- 82 tests passed, one optional labeling smoke test skipped (83 total).
- Checked saved labels, thresholds and scores for 646 test rows across four classical models: 2,584 predictions.
- All 3,520 development snapshot clean texts match current normalization.
- Real ViSoBERT classification-head reconstruction matches logits.
- Eight displayed classical-example subtotal equations conserve the full score.
- Rendered 84 chapter and transition frames; inspected intro, normalization and all final-decision scenes.
- Contextual dc becomes được; technical DC and ambiguous address requests are preserved.

Presentation edits remove repetitive caveats from the video. They do not change label provenance, predictions, split boundaries or metrics. Labels include automated labels; reported test performance measures agreement with the stored dataset labels, and does not establish independently verified real-world accuracy. Group-based splitting remains in the training method.

Full MP4 exported: 1280×720, 24 fps, 597.6 seconds. Decoded opening, middle and final chapter frames; source identity matches current files. HTTP status API exposes the new video; byte-range streaming returned 206 and the requested 1,024 bytes.
