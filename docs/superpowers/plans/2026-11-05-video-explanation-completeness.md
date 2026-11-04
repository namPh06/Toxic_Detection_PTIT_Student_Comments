# Complete model explanation video

**Goal:** Show conserved arithmetic, actual thresholds and model-specific input paths for all five models.
**Architecture:** Artifact evidence supplies exact displayed subtotals and all remaining contributions. Separate timed pages explain calculation and decision without squeezing text.
**Spec:** 2026-11-04-system-report-video-design.md and the user's approved clarification.

- [x] Normalize contextual dc, preserve technical DC; bump preprocessing version.
- [x] Rebuild features and train models using current preprocessing; preserve original runs.
- [x] Verify NB/SVM arithmetic, class order, thresholds, and ViSoBERT logits against artifacts.
- [x] Render calculation pages and decision pages, with all omitted rows aggregated explicitly.
- [x] Inspect previews, export full MP4 and verify final video metadata and serving.

Constraints: no invented attention explanation, no test-based model selection, no claim of perfect labels. Tests run from stdin; no temporary test files remain.
