# LAB722 presenter presentation

**Operate secure, multi-tenant agentic apps on Azure Container Apps**

Simon Jakesch · Microsoft Ignite 2026

Scenario: Caldova Research Preview Factory, a fictional pharmaceutical company.

This is facilitator-guided/rehearsal material with prepared resources and real development evidence. **Recorded Evidence is the default participant path**; optional Live Exercise requires explicit facilitator authorization. The [shared participant guide](..\instructions\README.md) supports guided and self-paced reading. Skillable-specific integration is excluded from this material milestone, not a reason to block it.

**October 14 delivery update:** the participant guide now covers portable builds in the allocated ACR, the bundled v2 dataset and [ready-made-image recovery](../instructions/05-build-and-publish.md#recovery---use-the-ready-made-reference-image). This deck, its embedded/generated notes and its exports remain the earlier recorded-evidence snapshot, including its original maintainer-only publication description; they were not regenerated for the new flow. Use the current guide for live commands. Reference images are not available merely because recovery commands exist: publication, exact digests and actual attendee pull access still need verification.

## Deliverables

- [RevealJS source](index.html): 24 slides; seven segment openers each state goal, why, services, outcome, and target timing.
- [PDF](outputs\lab722-caldova.pdf): 24 pages, 16:9, without speaker notes.
- `outputs\slide-01.png` through `outputs\slide-24.png`: individual 1280 × 720 slides.
- [Speaker notes](speaker-notes.md): planned slide/segment timing, transitions, checkpoints, and safe recorded-evidence fallbacks.
- [Export validation receipt](outputs\export-validation.json): source/artifact SHA-256 values, page counts, browser/version, links, layout, navigation, notes, and console checks.
- [Real reduced evidence bundle](..\instructions\assets\development-evidence.html): accepted-run/worker/check/image/approval/timestamped-observation teaching extract. This presentation does not generate or alter that bundle.

PowerPoint is not required. The PDF/PNGs are portable, static deliverables; the interactive deck needs the locally installed assets described below.

## View locally on Windows

From the repository root:

```powershell
Set-Location .\presentations
npm run present
```

Open the loopback URL printed by the command in Microsoft Edge. The server binds only to `127.0.0.1`; it serves presentation assets and selected participant Markdown/evidence files, not arbitrary repository files. Press `Ctrl+C` when finished.

- Arrow keys / Page Up / Page Down: previous or next slide.
- `Home` / `End`: first or last slide.
- `S`: speaker view with embedded notes; allow the local popup.
- `Esc`: slide overview.
- Slide numbers and a progress bar remain visible.

The source uses system fonts, black text on white, underlined links, named navigation controls, and reduced-motion styling. Architecture is readable HTML with an accessible description, not a decorative image. Markdown guide links are served as readable source; use an editor or repository viewer for rendered Markdown navigation. Do not use `file://` for speaker view.

If dependencies are missing, install only this folder’s locked packages. No global tool or browser installation is needed:

```powershell
Set-Location .\presentations
New-Item -ItemType Directory -Force .\.npm-runtime | Out-Null
$env:TEMP = Join-Path $PWD '.npm-runtime'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
npm ci --ignore-scripts --no-audit --no-fund --cache .\.npm-cache
```

The manifest pins RevealJS 4.5.0, Playwright Core 1.58.2, and PDF-lib 1.17.1. Existing Edge is used; **no additional browser is downloaded**. These are presentation-local dependencies, not application-tooling upgrades.

## Reproduce and verify exports

```powershell
# Run inside presentations.
npm run export
npm run verify
```

Default Edge path: `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`. If Edge is installed elsewhere, set `$env:LAB722_EDGE_PATH` to its executable.

The exporter starts its own isolated headless Edge process/profile and loopback server. Runtime/profile scratch stays in this folder’s uniquely named `.renderer-workspaces` child and is removed only for that run. It does not attach to or kill an existing browser. It blocks non-loopback page requests and does not upload repository data to any renderer. No Azure, credentials, candidate execution, publication, or deployment is involved.

Exports are published only after all 24 slide bounds/notes, seven opener contracts, relative links, keyboard navigation, local speaker popup, console/network results, PDF slide order/page count, and PNG dimensions pass. The receipt binds the final `index.html`, renderer, manifest/lockfile, template attribution, and exported files. `npm run verify` checks persistent files and fails if source or artifacts changed. It does not recertify live application health.

Edit **`index.html`**, including its embedded `<aside class="notes">` content, then rerun export. `speaker-notes.md` is generated from those same notes to avoid divergent versions. PDF printing uses Reveal’s print layout; notes are exported separately, not appended as extra PDF pages.

## House-template provenance

The starting HTML was copied from [pamelafox/presentation-skills](https://github.com/pamelafox/presentation-skills/tree/2b809b3a8d2ffdd2a5fb30da890d0e7ce6aeb53c), revision `2b809b3a8d2ffdd2a5fb30da890d0e7ce6aeb53c`, asset `.agents/skills/make-revealjs-presentation/assets/index.html`; its `SKILL.md` was read at the same revision. Upstream hashes are in [template-provenance.json](template-provenance.json). Copyright (c) 2024 Pamela Fox; the full [MIT license](licenses\presentation-skills-MIT.txt) is preserved.

The simple system-font, black-on-white sections, `heading-only` dividers, code blocks, and 1280 × 720 Reveal initialization are retained. Deliberate adaptations:

- Replace mixed-version/unversioned CDN assets with **coherent local Reveal 4.5.0** core/reset/simple theme and Notes. This makes exports reproducible and prevents external asset/network dependencies.
- Generate `theme-simple.css` from that pinned simple theme, removing its two Google Fonts imports and selecting system fonts. The theme’s original copyright header and Reveal MIT license remain intact.
- Omit Menu (the workflow documents an unnamed-trigger accessibility concern) and unused syntax highlighting. Native code blocks remain legible; named core controls and keyboard navigation provide access.
- Add the local Notes plugin for presenter view, disable visual transitions, and respect reduced-motion preferences.
- Apply template flex styling only to the active divider (or print layout), so hidden section dividers cannot overlap the current slide.
- Preserve authored print padding, use exact 720-pixel PDF frames, and override the last frame’s forced page break to avoid a trailing blank page. Non-slide pause controls remain excluded from print.

## Timing and readiness boundary

| Segment | Target | Planned window |
| --- | ---: | --- |
| 0 · Welcome/readiness | 5 min | 00:00–05:00 |
| 1 · Research portal | 4 min | 05:00–09:00 |
| 2 · Foundry orchestrator | 15 min | 09:00–24:00 |
| 3 · Sandbox baseline | 15 min | 24:00–39:00 |
| 4 · Agent team | 23 min | 39:00–62:00 |
| 5 · Build/publish receipts | 6 min | 62:00–68:00 |
| 6 · Trace evidence | 7 min | 68:00–75:00 |

These are **targets, not measured timing**. Segment 5 walks recorded builds. The current build helper supports explicit participant subscription/resource-group/registry scope; omitting the group retains the original maintainer-only guard. Publication/deployment mutate resources, and deployment helpers may refresh pull credentials. Do not invoke them as a read-only exercise.

The v2 bundle now has committed-source provenance and exact-slice distribution confirmation, not a completed live release. Full event authorization/startup, actual v2 starter/reference image distribution, clean VM capture and a fresh dry run remain unfinished. Videos have not been created; event release and final recording readiness are not claimed. Prepared Foundry/Sandbox scopes are deliberately mixed, retained Sandbox capacity is full, and implemented Reuse is not an untouched starter.

The offline evidence inspector verifies checksums/identity joins; it never authenticates approvers, reruns application tests, evaluates release gates, or claims current live health/attendee readiness. No telemetry workbook or invented issue/session/token details are presented. “reviewed-public” names owner-selected lab-source use, not an expert clinical audit. No clinical causation, incidence, comparative safety, treatment recommendation, or medical advice is implied.
