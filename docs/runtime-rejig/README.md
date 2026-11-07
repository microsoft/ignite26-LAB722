# LAB722 reactor

The maintained November 7 redesign is on **`lab-reactor`**. It supersedes the November 6 shared-key/fixed-Sandbox variant; that variant remains in Git at `35f5ee8`. The `lab-ready-1` recovery tag is unchanged.

- [Learner entry point](lab-rejig-learner-instructions.md).
- [Facilitator setup and recovery](lab-rejig-instructions.md).
- [One-page owner explanation](lab-rejig-identity-flow.md).
- [Walkthrough and objective verdicts](reactor-walkthrough-report.md).
- Root implementation brief: `lab-pamela-adopt-instructions.md`. Its companion `lab-learner-walkthrough.md` remains unchanged.

Current source: `src\reactor`; two-app ARM: `infra\reactor.bicep`.

**Live prerequisite blocked:** no dedicated execution API audience has been supplied, and the owner declined tenant resource creation. No new service API registration, first-party-audience substitution, shared-key fallback or self-hosted-orchestrator substitution is implemented. The new end-to-end path has not been run. Local checks and image builds are not a live architecture pass.

The other documents in this directory (`lab-rejig-stage1.md`, `lab-rejig-own-sub-instructions.md`, `lab-rejig-todo.md`) are historical November 6 material, not instructions for this reactor. Do not reuse their access key, fixed A workspace or deployment helper.
