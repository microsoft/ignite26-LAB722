import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFile, writeFile, mkdir, stat, copyFile, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { inflateSync } from "node:zlib";
import { chromium } from "playwright-core";
import { PDFDocument } from "pdf-lib";

const root = path.dirname(fileURLToPath(import.meta.url));
const repository = path.dirname(root);
const outputs = path.join(root, "outputs");
const width = 1280;
const height = 720;
const expectedSlides = 24;
const segmentTargets = [5, 4, 15, 15, 23, 6, 7];
const sourceNames = ["index.html", "theme-simple.css", "export.mjs", "package.json", "package-lock.json", "template-provenance.json",
  "licenses/presentation-skills-MIT.txt", "licenses/reveal.js-MIT.txt", "node_modules/reveal.js/dist/reset.css",
  "node_modules/reveal.js/dist/reveal.css", "node_modules/reveal.js/dist/reveal.js", "node_modules/reveal.js/plugin/notes/notes.js"];
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const clock = minutes => `${Math.floor(minutes)}:${String(Math.round((minutes % 1) * 60)).padStart(2, "0")}`;

async function sourceHashes() {
  return Object.fromEntries(await Promise.all(sourceNames.map(async name =>
    [name, hash(await readFile(path.join(root, ...name.split("/"))))]
  )));
}

async function prepareTheme() {
  const original = await readFile(path.join(root, "node_modules", "reveal.js", "dist", "theme", "simple.css"), "utf8");
  const local = original
    .replace(/^@import url\(https:\/\/fonts\.googleapis\.com\/[^;]+;\r?\n/gm, "")
    .replace("--r-main-font: Lato, sans-serif;", '--r-main-font: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;')
    .replace("--r-heading-font: News Cycle, Impact, sans-serif;", "--r-heading-font: inherit;");
  assert(!/@import|fonts\.googleapis/.test(local), "Unexpected remote import in the pinned simple theme");
  await writeFile(path.join(root, "theme-simple.css"), local, "utf8");
  await mkdir(path.join(root, "licenses"), { recursive: true });
  await copyFile(path.join(root, "node_modules", "reveal.js", "LICENSE"), path.join(root, "licenses", "reveal.js-MIT.txt"));
}

function pngSize(bytes) {
  assert.equal(bytes.subarray(0, 8).toString("hex"), "89504e470d0a1a0a", "PNG signature");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
}

async function serve() {
  const mime = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json", ".md": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".png": "image/png", ".pdf": "application/pdf", ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf" };
  const server = createServer(async (request, response) => {
    try {
      let name = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
      if (name === "/favicon.ico") { response.writeHead(204); response.end(); return; }
      if (name === "/") name = "/presentations/index.html";
      const parts = name.split("/").filter(Boolean);
      if (parts.some(part => part === ".." || part.includes("\\") || part.startsWith("."))) throw new Error("Path not served");
      const presentationPath = parts[0] === "presentations" && (
        parts.length === 2 && ["index.html", "theme-simple.css", "README.md", "speaker-notes.md", "template-provenance.json"].includes(parts[1]) ||
        parts[1] === "outputs" && parts.length === 3 ||
        parts[1] === "node_modules" && parts[2] === "reveal.js" && ["dist", "plugin"].includes(parts[3])
      );
      const guidePath = parts[0] === "instructions" && (
        parts.length === 2 && path.extname(parts[1]) === ".md" ||
        parts[1] === "assets" && parts.length === 3 && /^development-evidence(?:-manifest)?\.(html|json)$/.test(parts[2])
      );
      if (!presentationPath && !guidePath) throw new Error("Path not served");
      const target = path.join(repository, ...parts);
      const bytes = await readFile(target);
      response.writeHead(200, { "Content-Type": mime[path.extname(target)] ?? "application/octet-stream", "Cache-Control": "no-store" });
      response.end(bytes);
    } catch {
      response.writeHead(404, { "Content-Type": "text/plain" });
      response.end("Not served by the local presentation server.");
    }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  return { server, origin: `http://127.0.0.1:${server.address().port}` };
}

function markdownNotes(slides, sourceHash) {
  let cumulative = 0;
  const lines = [
    "# LAB722 presenter notes", "",
    "Operate secure, multi-tenant agentic apps on Azure Container Apps",
    "", "Simon Jakesch · Microsoft Ignite 2026", "",
    "Generated from the embedded notes in `index.html`; edit that source and rerun `npm run export`.",
    `Deck SHA-256: \`${sourceHash}\``, "",
    "## Delivery boundary", "",
    "Facilitator-guided rehearsal with prepared resources. **Recorded Evidence is the default**; optional Live Exercise requires explicit facilitator authorization. No event release, measured 75-minute runtime, or final recording readiness is claimed. Videos do not yet exist. Skillable-specific integration is excluded from this material milestone.",
    "", "## Target schedule", "",
    "| Segment | Target | Planned window |",
    "| --- | ---: | --- |"
  ];
  const names = ["Welcome/readiness", "Research portal", "Foundry orchestrator", "Sandbox baseline", "Agent team", "Build/publish receipts", "Trace evidence"];
  for (let i = 0, start = 0; i < segmentTargets.length; i++) {
    lines.push(`| ${i} · ${names[i]} | ${segmentTargets[i]} min | ${clock(start)}–${clock(start + segmentTargets[i])} |`);
    start += segmentTargets[i];
  }
  lines.push("", "These are activity allocations, not measurements. Segment 5 is a recorded-build walkthrough, not a six-minute full-build promise.", "");
  for (const [index, slide] of slides.entries()) {
    lines.push(`## Slide ${String(index + 1).padStart(2, "0")} · ${slide.title}`, "");
    lines.push(`Segment ${slide.segment} · Slide target ${clock(slide.minutes)} · Planned window ${clock(cumulative)}–${clock(cumulative + slide.minutes)}`, "");
    for (const paragraph of slide.notes) lines.push(paragraph, "");
    cumulative += slide.minutes;
  }
  lines.push("## Presenter controls", "", "Serve with `npm run present`; open the printed loopback URL. Arrow keys/Page Up/Page Down navigate; Home/End jump; `S` opens the local speaker view. Allow the local popup. `Esc` opens overview. The PDF and slide images intentionally omit speaker notes. Relative guide links are served as readable source files; open the Markdown guide in your editor or repository viewer for rendered navigation.", "");
  return lines.join("\n");
}

async function verify() {
  const receipt = JSON.parse(await readFile(path.join(outputs, "export-validation.json"), "utf8"));
  assert.deepEqual(receipt.source_sha256, await sourceHashes(), "Exports do not match current source; run npm run export");
  assert.equal(receipt.slides, expectedSlides);
  assert.equal(receipt.pdf_pages, expectedSlides);
  assert.deepEqual(receipt.segment_minutes, segmentTargets);
  for (const item of receipt.artifacts) {
    const file = path.join(root, ...item.path.split("/"));
    const bytes = await readFile(file);
    assert.equal(hash(bytes), item.sha256, `Changed/missing artifact: ${item.path}`);
    assert.equal(bytes.length, item.bytes);
    if (item.path.endsWith(".png")) assert.deepEqual(pngSize(bytes), { width, height });
    if (item.path.endsWith(".pdf")) assert.equal((await PDFDocument.load(bytes)).getPageCount(), expectedSlides);
  }
  assert.equal(receipt.artifacts.filter(item => item.path.endsWith(".png")).length, expectedSlides);
  console.log(`Verified persistent exports: ${expectedSlides} slides, ${expectedSlides} PDF pages, ${expectedSlides} PNGs; source and artifact SHA-256 values match.`);
}

async function render() {
  await prepareTheme();
  const before = await sourceHashes();
  const html = await readFile(path.join(root, "index.html"), "utf8");
  assert(!/Talk Title|Conference Name|Your Name|website\.example|example\.com|filename\.html|TODO|TBD|Lorem ipsum/i.test(html), "Stock placeholder in deck");
  assert.equal((html.match(/<section\b/g) ?? []).length, expectedSlides, "Source section count");
  assert.equal((html.match(/<\/section>/g) ?? []).length, expectedSlides, "Unbalanced section count");
  assert.equal((html.match(/<aside class="notes">/g) ?? []).length, expectedSlides, "Source notes count");
  const workspace = path.join(root, ".renderer-workspaces", `export-${randomUUID()}`);
  const profile = path.join(workspace, "edge-profile");
  const staging = path.join(workspace, "rendered");
  const runtime = path.join(workspace, "runtime");
  await Promise.all([mkdir(profile, { recursive: true }), mkdir(staging, { recursive: true }), mkdir(runtime, { recursive: true })]);
  const { server, origin } = await serve();
  const edge = process.env.LAB722_EDGE_PATH ?? "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
  await stat(edge);
  let child, browser, context, session;
  const consoleErrors = [];
  const failedRequests = [];
  const externalRequests = [];
  try {
    // Spawn Edge directly so its isolated profile/runtime remain inside this owned directory.
    // Playwright attaches over CDP; no browser download or default OS-temp launch profile is used.
    child = spawn(edge, ["--headless=new", "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking", "--disable-component-update", "--disable-sync", "--hide-scrollbars", "about:blank"], {
      cwd: root, windowsHide: true, stdio: "ignore",
      env: { ...process.env, TEMP: runtime, TMP: runtime, TMPDIR: runtime }
    });
    let spawnError;
    child.on("error", error => { spawnError = error; });
    let port;
    for (let attempt = 0; attempt < 120; attempt++) {
      if (spawnError) throw spawnError;
      if (child.exitCode !== null) throw new Error(`Isolated Edge exited ${child.exitCode}`);
      try {
        port = (await readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split(/\r?\n/)[0];
        if (/^\d+$/.test(port)) break;
      } catch {}
      await pause(250);
    }
    assert(port, "Edge CDP did not become responsive");
    browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
    context = browser.contexts()[0];
    await context.route("**/*", route => {
      const url = route.request().url();
      if (url.startsWith(`${origin}/`) || url.startsWith("data:") || url.startsWith("about:")) return route.continue();
      externalRequests.push(url);
      return route.abort("blockedbyclient");
    });
    context.on("page", page => {
      page.on("console", message => { if (message.type() === "error") consoleErrors.push(message.text()); });
      page.on("pageerror", error => consoleErrors.push(error.message));
      page.on("requestfailed", request => failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
      page.on("response", response => { if (response.status() >= 400) failedRequests.push({ url: response.url(), status: response.status() }); });
    });
    const page = await context.newPage();
    session = await context.newCDPSession(page);
    await page.setViewportSize({ width, height });
    const deckUrl = `${origin}/presentations/index.html`;
    await page.goto(deckUrl, { waitUntil: "networkidle" });
    await page.waitForFunction(() => window.Reveal?.isReady());
    await page.evaluate(() => document.fonts.ready);
    const slides = await page.evaluate(() => {
      const sections = [...document.querySelectorAll(".slides > section")];
      return sections.map(section => ({
        id: section.id, title: section.dataset.title, segment: Number(section.dataset.segment),
        minutes: Number(section.dataset.minutes), heading: section.querySelector("h1,h2,h3")?.textContent.trim(),
        notes: [...section.querySelectorAll("aside.notes > p")].map(p => p.textContent.trim()),
        opener: section.dataset.opener === "true",
        fields: [...section.querySelectorAll(".opener dt")].map(dt => dt.textContent.trim()),
        body: [...section.children].filter(child => !child.matches("aside.notes")).map(child => child.textContent).join("\n")
      }));
    });
    assert.equal(slides.length, expectedSlides);
    assert.equal(new Set(slides.map(slide => slide.id)).size, expectedSlides, "Duplicate slide ids");
    for (const slide of slides) {
      assert(slide.heading && slide.title && slide.id, "Missing slide heading/title/id");
      assert(slide.notes.length >= 3, `Missing notes: ${slide.id}`);
      assert(slide.notes.some(note => note.includes("Checkpoint:") && note.includes("Transition:")), `Missing checkpoint/transition: ${slide.id}`);
      assert(slide.notes[0].includes(`Target: ${clock(slide.minutes)}`), `Timing disagreement: ${slide.id}`);
      assert(Number.isFinite(slide.minutes) && slide.minutes > 0);
    }
    const openers = slides.filter(slide => slide.opener);
    assert.deepEqual(openers.map(slide => slide.segment), [0, 1, 2, 3, 4, 5, 6]);
    for (const slide of openers) assert.deepEqual(slide.fields, ["Goal", "Why", "Services", "Outcome"]);
    const minutes = segmentTargets.map((_, segment) => slides.filter(slide => slide.segment === segment).reduce((total, slide) => total + slide.minutes, 0));
    assert.deepEqual(minutes, segmentTargets);
    assert.equal(minutes.reduce((a, b) => a + b, 0), 75);
    const structure = await page.evaluate(() => ({
      lang: document.documentElement.lang,
      mains: document.querySelectorAll("main").length,
      duplicateIds: [...document.querySelectorAll("[id]")].map(el => el.id).filter((id, i, all) => all.indexOf(id) !== i),
      unnamedLinks: [...document.querySelectorAll("a")].filter(a => !a.textContent.trim() && !a.getAttribute("aria-label")).length,
      unnamedControls: [...document.querySelectorAll(".controls button")].filter(b => !b.getAttribute("aria-label") && !b.textContent.trim()).length,
      imagesMissingAlt: document.querySelectorAll("img:not([alt])").length,
      remoteAssets: [...document.querySelectorAll("script[src],link[rel=stylesheet],img[src],iframe[src]")].filter(el => /^https?:/.test(el.getAttribute("src") ?? el.getAttribute("href"))).length,
      revealVersion: Reveal.VERSION
    }));
    assert.equal(structure.lang, "en");
    assert.equal(structure.mains, 1);
    assert.deepEqual(structure.duplicateIds, []);
    assert.equal(structure.unnamedLinks, 0);
    assert.equal(structure.unnamedControls, 0);
    assert.equal(structure.imagesMissingAlt, 0);
    assert.equal(structure.remoteAssets, 0);
    assert.equal(structure.revealVersion, "4.5.0");
    const hrefs = await page.locator("a[href]").evaluateAll(anchors => [...new Set(anchors.map(a => a.getAttribute("href")).filter(href => !/^[a-z]+:/i.test(href) && !href.startsWith("#")))]);
    const relativeLinks = [];
    for (const href of hrefs) {
      const url = new URL(href, deckUrl);
      assert.equal(url.origin, origin);
      const response = await context.request.get(url.href);
      assert.equal(response.status(), 200, `Broken relative link: ${href}`);
      const body = await response.body();
      assert(body.length > 80, `Empty guide/evidence link: ${href}`);
      relativeLinks.push({ href, bytes: body.length, sha256_at_export: hash(body) });
    }
    const navigation = [];
    await page.keyboard.press("Home");
    assert.equal(await page.evaluate(() => Reveal.getIndices().h), 0);
    await page.keyboard.press("ArrowRight");
    assert.equal(await page.evaluate(() => Reveal.getIndices().h), 1);
    navigation.push("Home", "ArrowRight");
    await page.keyboard.press("ArrowLeft");
    assert.equal(await page.evaluate(() => Reveal.getIndices().h), 0);
    await page.keyboard.press("End");
    assert.equal(await page.evaluate(() => Reveal.getIndices().h), expectedSlides - 1);
    navigation.push("ArrowLeft", "End");
    await page.keyboard.press("Home");
    const popupPromise = context.waitForEvent("page");
    await page.keyboard.press("s");
    const popup = await popupPromise;
    await popup.waitForLoadState("domcontentloaded");
    await popup.waitForFunction(() => document.body.innerText.includes("Target:") && document.body.innerText.includes("Checkpoint:"), { timeout: 15000 });
    const speakerView = { shortcut: "S", opened: true, notes_visible: true };
    await popup.close();
    await page.bringToFront();
    const layout = [];
    for (let index = 0; index < slides.length; index++) {
      await page.evaluate(i => Reveal.slide(i), index);
      await page.waitForFunction(i => Reveal.getIndices().h === i && document.querySelectorAll(".slides > section.present").length === 1, index);
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(() => {
        const slide = Reveal.getCurrentSlide();
        const bounds = slide.getBoundingClientRect();
        const footer = slide.querySelector(".slide-link")?.getBoundingClientRect();
        const failures = [];
        const visible = [...slide.querySelectorAll("h1,h2,h3,p,li,td,th,dt,dd,pre,.node")].filter(el => !el.closest(".notes"));
        for (const element of visible) {
          const rect = element.getBoundingClientRect();
          const text = element.textContent.trim().slice(0, 100);
          if (rect.left < bounds.left - 1 || rect.right > bounds.right + 1 || rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1) failures.push({ text, reason: "outside slide", rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } });
          if (element.clientWidth > 0 && element.scrollWidth > element.clientWidth + 2) failures.push({ text, reason: "horizontal clipping" });
          if (footer && !element.closest(".slide-link") && rect.bottom > footer.top - 8) failures.push({ text, reason: "overlaps guide footer" });
        }
        return { slide: slide.id, width: Math.round(bounds.width), height: Math.round(bounds.height), checked_elements: visible.length, failures };
      });
      assert.deepEqual(result.failures, [], `Overflow on ${slides[index].id}: ${JSON.stringify(result.failures)}`);
      assert.equal(result.width, width);
      assert.equal(result.height, height);
      layout.push(result);
      await page.screenshot({ path: path.join(staging, `slide-${String(index + 1).padStart(2, "0")}.png`), fullPage: false });
    }
    await page.setViewportSize({ width: 960, height: 540 });
    await page.evaluate(() => Reveal.slide(0));
    const scaled = await page.evaluate(() => {
      const rect = Reveal.getCurrentSlide().getBoundingClientRect();
      return { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, viewport_width: innerWidth, viewport_height: innerHeight };
    });
    assert(scaled.left >= -1 && scaled.top >= -1 && scaled.right <= 961 && scaled.bottom <= 541, "Scaled slide exceeds viewport");
    await page.setViewportSize({ width, height });
    await page.goto(`${deckUrl}?print-pdf`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => window.Reveal?.isReady() && document.querySelectorAll(".pdf-page").length === 24);
    await page.emulateMedia({ media: "print" });
    await page.evaluate(() => document.fonts.ready);
    const printNotes = await page.locator(".pdf-page .speaker-notes").count();
    assert.equal(printNotes, 0, "Speaker notes must not add PDF pages");
    const visibleNotes = await page.locator(".pdf-page aside.notes").evaluateAll(notes =>
      notes.filter(note => getComputedStyle(note).display !== "none").length
    );
    assert.equal(visibleNotes, 0, "Embedded notes must remain hidden in the PDF");
    const printPages = await page.evaluate(() => [...document.querySelectorAll(".pdf-page")].map(page => {
      const section = page.querySelector("section");
      return { id: section?.id, height: page.getBoundingClientRect().height, text: section?.innerText };
    }));
    assert.equal(printPages.length, expectedSlides);
    assert.deepEqual(printPages.map(page => page.id), slides.map(slide => slide.id), "PDF slide order");
    const printOverflow = await page.evaluate(() => [...document.querySelectorAll(".pdf-page")].flatMap(page => {
      const bounds = page.getBoundingClientRect();
      const section = page.querySelector("section");
      const footer = section.querySelector(".slide-link")?.getBoundingClientRect();
      return [...section.querySelectorAll("h1,h2,h3,p,li,td,th,dt,dd,pre,.node")]
        .filter(el => !el.closest(".notes"))
        .flatMap(el => {
          const rect = el.getBoundingClientRect();
          const outside = rect.left < bounds.left - 1 || rect.right > bounds.right + 1 || rect.top < bounds.top - 1 || rect.bottom > bounds.bottom + 1;
          const overlaps = footer && !el.closest(".slide-link") && rect.bottom > footer.top - 8;
          return outside || overlaps ? [{ slide: section.id, text: el.textContent.trim().slice(0, 80), outside, overlaps: Boolean(overlaps) }] : [];
        });
    }));
    assert.deepEqual(printOverflow, [], "Overflow in PDF print layout");
    await page.pdf({ path: path.join(staging, "lab722-caldova.pdf"), preferCSSPageSize: true, printBackground: true, tagged: true, margin: { top: "0", right: "0", bottom: "0", left: "0" } });
    const pdfBytes = await readFile(path.join(staging, "lab722-caldova.pdf"));
    const pdf = await PDFDocument.load(pdfBytes);
    assert.equal(pdf.getPageCount(), expectedSlides, "PDF page count");
    for (const pdfPage of pdf.getPages()) {
      assert(Math.abs(pdfPage.getWidth() / pdfPage.getHeight() - width / height) < 0.001, "PDF aspect ratio");
      const contents = pdfPage.node.Contents();
      const entries = contents?.asArray ? contents.asArray() : contents ? [contents] : [];
      const drawing = entries.map(entry => inflateSync(pdf.context.lookup(entry).getContents()).toString()).join("");
      assert(/\bBT\b/.test(drawing), "Blank PDF page");
    }
    assert.deepEqual(await sourceHashes(), before, "Source changed during rendering");
    assert.deepEqual(externalRequests, [], "Deck attempted external asset/network requests");
    assert.deepEqual(failedRequests, [], "Browser network/HTTP failure");
    assert.deepEqual(consoleErrors, [], "Browser console error");
    const notes = markdownNotes(slides, before["index.html"]);
    await writeFile(path.join(staging, "speaker-notes.md"), notes, "utf8");
    await mkdir(outputs, { recursive: true });
    const artifacts = [];
    const names = ["lab722-caldova.pdf", ...slides.map((_, i) => `slide-${String(i + 1).padStart(2, "0")}.png`)];
    for (const name of names) {
      const bytes = await readFile(path.join(staging, name));
      if (name.endsWith(".png")) assert.deepEqual(pngSize(bytes), { width, height });
      await copyFile(path.join(staging, name), path.join(outputs, name));
      artifacts.push({ path: `outputs/${name}`, bytes: bytes.length, sha256: hash(bytes) });
    }
    await copyFile(path.join(staging, "speaker-notes.md"), path.join(root, "speaker-notes.md"));
    artifacts.push({ path: "speaker-notes.md", bytes: Buffer.byteLength(notes), sha256: hash(notes) });
    const receipt = {
      schema: "lab722-presentation-export-v1", exported_at: new Date().toISOString(),
      purpose: "facilitator-guided rehearsal; Recorded Evidence default; no event-release/readiness claim",
      source_sha256: before, browser: { executable: edge, version: browser.version(), isolated_profile: true, third_party_renderer: false },
      dependencies: { reveal_js: "4.5.0", playwright_core: "1.58.2", pdf_lib: "1.17.1" },
      slides: slides.length, pdf_pages: pdf.getPageCount(), png_dimensions: { width, height },
      segment_minutes: minutes, target_total_minutes: 75, measured_lab_duration: false,
      checks: { structure, all_slides_have_notes: true, all_segment_openers_complete: true, stock_placeholders: 0,
        keyboard_navigation: navigation, speaker_view: speakerView, scaled_viewport: scaled, overflow: layout,
        relative_links: relativeLinks, external_requests: externalRequests, failed_requests: failedRequests, console_errors: consoleErrors,
        pdf_order_matches_slides: true, pdf_notes_omitted: true, pdf_blank_pages: 0, pdf_print_overflow: printOverflow },
      slide_index: slides.map((slide, i) => ({ number: i + 1, id: slide.id, title: slide.title, segment: slide.segment, target_minutes: slide.minutes })),
      artifacts,
      limitations: ["Target schedule is not measured lab timing.", "Recorded evidence does not certify current live health or attendee readiness.", "Event authorization/startup, starter distribution, committed provenance and a fresh dry run remain external.", "Videos/final recording readiness and Skillable-specific integration are outside this milestone.", "Checks cover DOM structure, bounds, named controls and navigation; no comprehensive WCAG audit is claimed."]
    };
    await writeFile(path.join(outputs, "export-validation.json"), `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
    await verify();
  } finally {
    if (session) {
      try { await session.send("Browser.close"); } catch {}
    }
    if (browser) { try { await browser.close(); } catch {} }
    if (child && child.exitCode === null) {
      await Promise.race([new Promise(resolve => child.once("exit", resolve)), pause(5000)]);
      if (child.exitCode === null) child.kill();
    }
    await new Promise(resolve => server.close(resolve));
    // Delete only this run's uniquely created browser scratch, never retained resources or other runs.
    await rm(workspace, { recursive: true, force: true, maxRetries: 5, retryDelay: 500 });
  }
}

if (process.argv.includes("--serve")) {
  await prepareTheme();
  const { server, origin } = await serve();
  console.log(`LAB722 local presenter: ${origin}/presentations/index.html`);
  console.log("Arrow keys navigate; S opens speaker notes. Ctrl+C stops this server. Only deck assets and selected participant materials are served.");
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.close(() => process.exit(0)));
} else if (process.argv.includes("--verify")) {
  await verify();
} else {
  await render();
}
