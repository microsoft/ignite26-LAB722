"use strict";
const byId = (id) => document.getElementById(id);
let key = "";
let connected = false;
let busy = false;

function buttons() {
  for (const id of ["analyze", "execute"]) byId(id).disabled = !connected || busy;
  byId("connect").disabled = busy;
}

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Lab722-Proof-Key": key, ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const value = await response.json();
  if (!response.ok) {
    const error = new Error(value.error || `HTTP ${response.status}`);
    error.details = value;
    throw error;
  }
  return value;
}

byId("connect").addEventListener("click", async () => {
  key = byId("key").value;
  byId("key").value = "";
  connected = false;
  busy = true;
  buttons();
  try {
    const configuration = await api("/api/config");
    byId("configuration").textContent = JSON.stringify(configuration, null, 2);
    connected = true;
  } catch (error) {
    byId("configuration").textContent = error.message;
    key = "";
  } finally {
    busy = false;
    buttons();
  }
});

function render(value) {
  const receipt = value.receipt;
  byId("status").textContent = `${value.status} | run ${value.run_id}`;
  byId("evidence").textContent = JSON.stringify({
    route: value.route, tool: value.tool, agent: value.agent || "not invoked",
    agent_version: value.agent_version, conversation_id: value.conversation_id,
    sandbox_id: receipt.sandbox_id, execution_marker: receipt.execution_marker,
    exit_code: receipt.exit_code, execution_uid: receipt.execution_uid,
    environment_cleared: receipt.environment_cleared, no_new_privileges: receipt.no_new_privileges,
    identity_endpoint_status: receipt.identity_endpoint_status,
    dataset_version: receipt.dataset_version, elapsed_seconds: value.elapsed_seconds,
    remote_elapsed_seconds: receipt.elapsed_seconds, captured_bytes: receipt.captured_bytes,
    result_format: receipt.result_format, output_types: value.output_types,
  }, null, 2);
  byId("code").value = value.code;
  byId("result").textContent = receipt.stdout;
  byId("stderr").textContent = receipt.stderr || "(none)";
  byId("answer").textContent = value.answer || "(edited code: no agent summary)";
  byId("chart").replaceChildren();
  const rows = receipt.result?.chart;
  if (receipt.status !== "completed" || !Array.isArray(rows) || !rows.length) return;
  if (!rows.every((row) => typeof row.label === "string" && Number.isFinite(row.value) && row.value >= 0)) {
    byId("chart").textContent = "Chart not rendered: expected non-negative numeric label/value rows. See actual JSON above.";
    return;
  }
  const maximum = Math.max(1, ...rows.map((row) => row.value));
  for (const row of rows.slice(0, 50)) {
    const container = document.createElement("div");
    container.className = "bar-row";
    const label = document.createElement("span");
    label.textContent = row.label;
    const track = document.createElement("div");
    track.className = "bar-track";
    const bar = document.createElement("div");
    bar.className = "bar";
    bar.style.width = `${100 * row.value / maximum}%`;
    track.append(bar);
    const count = document.createElement("span");
    count.textContent = String(row.value);
    container.append(label, track, count);
    byId("chart").append(container);
  }
}

async function submit(path, body) {
  busy = true;
  buttons();
  byId("status").textContent = "Running. The actual remote execution is bounded to 30 seconds.";
  for (const id of ["evidence", "result", "stderr", "answer"]) byId(id).textContent = "";
  byId("chart").replaceChildren();
  try {
    render(await api(path, body));
  } catch (error) {
    byId("status").textContent = `Request failed: ${error.message}`;
    byId("evidence").textContent = JSON.stringify(error.details || { error: error.message }, null, 2);
  } finally {
    busy = false;
    buttons();
  }
}

byId("analyze").addEventListener("click", () => submit("/api/analyze", { prompt: byId("prompt").value }));
byId("execute").addEventListener("click", () => submit("/api/execute", { code: byId("code").value }));
