# Learner walkthrough: agent execution guide

The learning objectives are supplied before the review; preserve their meaning and identifiers. The coordinator supplies the objective extract and learner materials, keeping implementation instructions and answer keys out of the learner review.

Assess what the lab enables a learner to do, observe, and explain. Agent completion does not establish human comprehension, engagement, or completion time. The parent task's question allowance applies across all reviewers: **at most five questions total**, not five each.

## Set the boundary

Record the commit, intended environment, audience/prerequisites, learner entry point, supplied resources, and objectives. Separate current instructions from historical or facilitator-only material. Use the learner's actual permissions and supported interfaces; do not broaden access to obtain a pass.

Use two independent review contexts where possible:

- **Implementation reviewer:** source, configuration, tests, and execution evidence.
- **Learner reviewer:** objectives, declared prerequisites, delivered instructions, and learner-visible interfaces only. Supply no implementation answer key or maintainer history.

Assign check A below to the implementation reviewer and B–D to the learner reviewer. Reconcile findings afterward. With one context, inspect the learner path first. Disclose prior implementation knowledge as an informed review; an agent cannot forget it. Browser/devtools access must not supply knowledge unavailable to learners.

## Perform five checks

| Check | Required work |
| --- | --- |
| **A. Implementation accuracy** | Trace one request, identities, state, execution target, controls, and cleanup. Check each learning claim against implementation. For helpers, identify inputs, changes, outputs, and independent verification. Flag unsupported objectives. |
| **B. Observable evidence** | For every required “inspect,” “confirm,” or “compare,” locate the exact visible field/output. Check controls, links, variables, preparation, feedback, and restoration steps. Finding a missing value in source does not fix the learner instruction. |
| **C. Learning sequence** | At meaningful transitions check **goal → prediction → action → feedback → explanation**. Record missing prerequisites or unexplained terms. Use one small transfer question per objective; avoid invented novice emotions or clarity scores. |
| **D. Literal execution** | Follow the delivered sequence with the supplied permissions and environment. Capture starting state, expected/actual result, deviations, recovery, and final state. No silent command fixes, credential switches, undocumented setup, or skipped failures. |
| **E. Review calibration** | In offline copies/fixtures, seed a few relevant defects and matching correct controls. Use a blind reviewer when possible. Check detection of a missing prerequisite, nonexistent observation, incorrect explanation, and successful-but-wrong result. Record misses and false alarms; never alter the live lesson for calibration. |

## Handle failures honestly

Record the first failing step before diagnosis or repair. Continue independent checks where possible. A later checkpoint does not establish an uninterrupted pass. Fix authorized defects separately, then rerun the affected path on the corrected version.

Classify execution as **passed as documented / documented recovery / undocumented repair / blocked / not run**. Keep automated elapsed time, service waits, and debugging time separate; do not present them as measured learner duration.

Use independent acceptance evidence. A successful process, plausible summary, or configured policy alone does not prove answer correctness, tenant authorization, or enforcement. Include allowed cases alongside denied cases.

## Produce a compact report

1. **Scope and verdict:** version, environment, review mode, execution classification, and material limitations.
2. **Objective coverage:** one row per supplied objective with activity, observed evidence, explanation/transfer check, and **supported / partial / missing / not evaluated**.
3. **Findings:** location, objective, expected/actual evidence, consequence, severity (**blocker / major / minor**), smallest fix, and verification. Distinguish execution defects from instructional gaps.
4. **Calibration:** defects detected, misses, false alarms, and whether the review was blind; otherwise mark not run.
5. **Next step:** the smallest remaining check; avoid repeating full runs without a specific unresolved risk.

Label evidence **observed**, **source-supported**, **historical**, or **not verified**. Include concise source/output references and redact credentials. Long transcripts and screenshots are optional evidence, not substitutes for findings.

## Final gate

Recommend one representative human confirmation after required observations and explanations agree with implementation, objective gaps are resolved or explicitly accepted, and the delivered path has run without undocumented repairs in the intended environment. Verify ending and restoration states.

Use that human check for comprehension, discoverability, and pacing. If it does not occur, report technical and instructional review accurately without claiming human validation. One planned run is a target; a serious redesign can require focused revalidation.
