# Runtime lab variant

This directory tracks the runtime redesign separately from the original `lab-ready-1` recovery baseline.

- [Outside-Skillable preparation](lab-rejig-own-sub-instructions.md): core allocation and one-time preparation before the learner activities.
- [Learner instructions](lab-rejig-learner-instructions.md): key-based access, generated/edited Python, filesystem/network boundaries and lifecycle.
- [Access and service identities](lab-rejig-identity-flow.md).
- [Deferred changes](lab-rejig-todo.md): includes separating the MCP backend from the learner-facing app; not implemented yet.
- [Design instructions](lab-rejig-instructions.md) and [stage-one design/history](lab-rejig-stage1.md).

Run commands from the repository root, not this documentation directory. The guides were originally authored alongside the checkout; references to `ignite26-LAB722\infra\README.md` mean this repository's `infra\README.md`.

The current implementation is in `src\runtime`; deployment guidance is in `infra\README.md` and `scripts\README.md`. It still co-hosts the UI/API and MCP endpoint. Fresh Skillable delivery and measured learner timing are not verified.

The version-controlled files here are the maintained copies. Earlier workspace-root copies are retained but are not automatically synchronized.
