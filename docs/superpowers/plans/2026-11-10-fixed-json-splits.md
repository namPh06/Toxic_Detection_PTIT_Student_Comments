# Fixed JSON splits

Goal: preserve the current 4,837/833/904 memberships and labels in three readable JSON files.

Architecture: data/train.json, validation.json and test.json store complete rows. The workspace remains the annotation source; export refreshes existing members only, never adds crawl rows implicitly. Training reads these files and rejects stale contents or partial sets. Existing group leakage checks remain active.

- [x] Export exact current membership and retain a compressed backup of the replaced membership map.
- [x] Replace the membership-map reader with a validated three-file reader; synchronize existing members during shared export.
- [x] Verify membership, labels, group separation and regression tests; remove only the replaced map. Keep cleaning exports, raw/context data, label history, model artifacts and manual Excel because they have separate uses.

Validation: all 6,574 memberships and labels match the previous map; split_dataset confirms group isolation. Shared dataset check passes. The 27 dataset/lab/bulk tests pass using a workspace temporary directory (temporary fixtures removed). Focused checks reject partial split sets and duplicate IDs and verify label synchronization. The broader project suite cannot complete here: local socket access is denied, and its legacy pickle test cannot resolve the synthetic __main__ module when invoked through stdin. No live training was rerun.
