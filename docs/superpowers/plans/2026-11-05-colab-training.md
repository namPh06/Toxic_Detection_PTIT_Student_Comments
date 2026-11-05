# Colab training implementation plan

**Goal:** Export the current web experiment to Colab, train ViSoBERT on its GPU, and import the model for comparison and prediction locally.

**Approved approach:** The user selected ZIP export → Colab notebook → ZIP import. Implement inline in this workspace. No tunnel, credentials or browser profile are exported. NB/SVM remain local and compatible results are retained by the existing publication mechanism.

**Architecture:** A JSON snapshot records the exact prepared rows, feature settings and split. The package contains only the training modules and notebook. Colab reconstructs and verifies the split, runs the existing ViSoBERT routine, and returns safetensors plus JSON artifacts. Import validates the job, current dataset, feature settings, split and predictions before publishing.

## Tasks
- [x] Backend: export package, generate notebook, run snapshot and import validated results; reject stale jobs, path traversal, pickle and malformed artifacts. Store exported jobs locally.
- [x] Web: export and notebook download controls, large binary result upload, clear step instructions and progress/error feedback.
- [x] Verify: synthetic export/import round trip, mismatched and unsafe archives, existing Python suite, JavaScript syntax and local HTTP smoke checks. Delete temporary test files after each run.

## Constraints and review
- Preserve labels and test split. Select thresholds using validation only.
- ViSoBERT is the remote model; retain compatible local NB/SVM without copying executable pickle from Colab.
- Upload uses a bounded binary stream to a temporary file, not base64 JSON.
- A100 availability and actual GPU training require the user's Colab session; report local validation separately.
- Generated notebook can be retried; downloading an already completed result does not retrain.

## Verification results
- Export/notebook structure, exact snapshot and split, stale/unsafe/corrupt result rejection, and failed-import rollback passed.
- A real tiny XLM-RoBERTa safetensors model was imported, loaded and used for prediction; metrics/report and compatible local NB retention passed. This validates the transfer path, not real GPU training quality.
- HTTP notebook download, input ZIP export and binary result import passed. The live Colab panel was verified in the browser.
- Existing suite: 95 tests, 4 failures, 2 errors, 1 skipped. The same failing methods reproduced against unchanged HEAD app code; see `docs/reviews/COLAB_20261105.md`.
- No actual Colab/A100 session was executed. The user selects the runtime and runs the notebook in their own account.
