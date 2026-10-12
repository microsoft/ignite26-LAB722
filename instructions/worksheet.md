# Participant checkpoint worksheet

Use this worksheet for either path. Write **recorded** or **new live run** beside every observation; never combine two runs to fill a missing check.

| Segment | Record | Checkpoint question |
|---|---|---|
| 0 | Execution path, run ID, dataset version, manifest and logical SHA-256 | Which facts were checked now, and which are recorded? |
| 1 | Application URL, image digest, starter/reference state and observation time | Does unavailable mean missing worker source, or only the visible portal state? |
| 2 | Three roles, bounded tasks, allowed feature paths and plan identity | What prevents an agent from approving its own release? |
| 3 | Source revision, primary ID, snapshot ID, three clone IDs and frozen identity | Is this an untouched prepared baseline or code-preserving reuse? |
| 4 | Worker blockers, 11 checks, primary vs worker check locations, egress evidence hashes | Why is a timeout insufficient proof of denied egress? |
| 5 | Result/source hashes, published digest, ACR run, separate human approval | Which exact run/dataset/image was approved, and for what scope? |
| 6 | Cross-receipt pins, timestamped app observation and missing telemetry | Does a recorded receipt prove the application is healthy now? |

## Explain the release boundary

Write one sentence for each distinction: source-use authorization vs expert audit; build validation vs publication; publication vs exact-image deployment approval; development preview vs attendee release; recorded observation vs a fresh live check.

## Reflection

How would you investigate a different image, another worker's Sandbox ID, a narrowed shared-record array, an invalid source-record ID or a mismatched run ID? The intended answer preserves the failed evidence and stops the affected operation. It does not reset retained resources, broaden permissions, rewrite tests or substitute a new trust anchor.
