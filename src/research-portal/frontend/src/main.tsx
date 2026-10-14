import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import { filterTrials, summarizeTrials } from "./trial-view";

type Condition = "" | "obesity" | "type-2-diabetes";
interface Candidate { candidate_id: string; name: string; research_area: string }
interface Source { source_id: string; name: string; attribution: string; license_notes: string; url: string | null; release: string; retrieved_at: string | null }
interface AuxiliaryArtifact { path: string; sha256: string; bytes: number }
interface SourceUse {
  scope: string; approved_by: string; approved_at: string; expert_audit_performed: false;
}
interface Metadata {
  preview_state: "starter" | "reference";
  fixture_warning: string | null;
  candidates: Candidate[];
  manifest: {
    dataset_version: string;
    dataset_kind: "synthetic-development" | "reviewed-public";
    pipeline_commit: string;
    built_at: string;
    database: { sha256: string; bytes: number };
    source_records?: AuxiliaryArtifact | null;
    pipeline_source?: AuxiliaryArtifact | null;
    public_extract?: {
      source_use: SourceUse;
      coverage_notes: string[];
      source_quality_counts: Record<string, number>;
    } | null;
    record_counts: Record<string, number>;
    sources: Source[];
    limitations: string;
  };
}
interface Evidence { source_id: string; source_record_id: string; source_url: string | null }
interface Trial extends Evidence {
  trial_id: string; title: string; phase: string; status: string; conditions: string[];
  source_conditions?: string[];
  source_interventions?: { intervention_id: number; candidate_id: string; name: string; intervention_type: string }[];
}
interface SafetyReport extends Evidence {
  report_id: string; version: number; candidate_ids: string[]; reaction_terms: string[];
  original_reaction_terms?: string[];
  source_drugs?: {
    candidate_ids: string[]; medicinalproduct: string | null;
    generic_names: string[]; brand_names: string[]; substance_names: string[];
  }[];
}
interface Research {
  status: "ready" | "unavailable";
  candidate: Candidate;
  dataset_version: string;
  trials: Trial[];
  safety_reports: SafetyReport[];
  limitations: string;
  fixture_warning: string | null;
}

async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`The research service returned HTTP ${response.status}.`);
  return response.json();
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "The research request failed.";
}

function Citation({ evidence, sources }: { evidence: Evidence; sources: Source[] }) {
  const source = sources.find(item => item.source_id === evidence.source_id);
  return <div className="citation">
    <span>{source?.name ?? evidence.source_id}</span>
    {evidence.source_url
      ? <a href={evidence.source_url} target="_blank" rel="noreferrer">{evidence.source_record_id}</a>
      : <code>{evidence.source_record_id}</code>}
  </div>;
}

function App() {
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [candidate, setCandidate] = useState("");
  const [condition, setCondition] = useState<Condition>("");
  const [research, setResearch] = useState<Research | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [phase, setPhase] = useState("");
  const [trialStatus, setTrialStatus] = useState("");
  const [trialLimit, setTrialLimit] = useState(10);

  useEffect(() => {
    const controller = new AbortController();
    setError(null);
    setLoading(true);
    getJson<Metadata>("/api/metadata", controller.signal).then(result => {
      if (result.candidates.length === 0) throw new Error("The dataset contains no research candidates.");
      setMetadata(result);
      setCandidate(previous => result.candidates.some(item => item.candidate_id === previous)
        ? previous : result.candidates[0].candidate_id);
    }).catch(error => {
      if (!controller.signal.aborted) { setError(errorMessage(error)); setLoading(false); }
    });
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    if (!metadata || !candidate) return;
    const controller = new AbortController();
    const parameters = new URLSearchParams({ candidate });
    if (condition) parameters.set("condition", condition);
    setLoading(true);
    setResearch(null);
    setError(null);
    getJson<Research>(`/api/research?${parameters}`, controller.signal).then(result => {
      setResearch(result);
      setPhase("");
      setTrialStatus("");
      setTrialLimit(10);
    }).catch(error => {
      if (!controller.signal.aborted) setError(errorMessage(error));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });
    return () => controller.abort();
  }, [metadata, candidate, condition, retry]);

  const sources = metadata?.manifest.sources ?? [];
  const trialSummary = summarizeTrials(research?.trials ?? []);
  const matchingTrials = filterTrials(research?.trials ?? [], phase, trialStatus);
  return <>
    <a className="skip-link" href="#workspace">Skip to research workspace</a>
    <header className="topbar">
      <a className="brand" href="#workspace"><span className="brand-mark" aria-hidden="true">C</span>Caldova<span className="brand-subtitle">Research</span></a>
      <nav aria-label="Workspace navigation"><a href="#workspace">Research workspace</a><a href="#provenance">Data provenance</a></nav>
      <span className="lab-label">LAB722 / development preview</span>
    </header>
    <main id="workspace">
      <div className="page-heading">
        <div><p className="eyebrow">Evidence-backed research</p><h1>Research workspace</h1>
          <p className="intro">Inspect trial records and report mentions. Keep the source and its limitations beside the evidence.</p></div>
        {metadata && <span className="state-label">{metadata.preview_state === "starter" ? "Starter preview" : "Reference preview"}</span>}
      </div>
      {metadata?.fixture_warning && <aside className="fixture-warning" aria-label="Development data warning">
        <strong>Synthetic development data</strong><p>{metadata.fixture_warning}</p>
      </aside>}
      {metadata?.manifest.dataset_kind === "reviewed-public" && <aside className="fixture-warning" aria-label="Public-data coverage">
        <strong>Bounded public-data demonstration</strong>
        <p>Frozen trial records and one cached report shard. This extract is not complete or representative; report versions are current only within the acquired input.</p>
      </aside>}
      <section className="filter-bar" aria-label="Research filters">
        <label>Research candidate<select id="research-candidate" name="candidate" value={candidate} disabled={!metadata} onChange={event => setCandidate(event.target.value)}>
          {!metadata && <option value="">Loading candidates...</option>}
          {metadata?.candidates.map(item => <option key={item.candidate_id} value={item.candidate_id}>{item.name}</option>)}
        </select></label>
        <label>Trial condition<select id="trial-condition" name="condition" value={condition} disabled={!metadata} onChange={event => {
          const value = event.target.value;
          if (value === "" || value === "obesity" || value === "type-2-diabetes") setCondition(value);
        }}>
          <option value="">All conditions</option><option value="obesity">Obesity</option><option value="type-2-diabetes">Type 2 diabetes</option>
        </select></label>
        <div className="data-status"><span className="status-dot" aria-hidden="true"></span>
          {metadata ? "Local artifact verified at startup" : "Checking the data artifact"}</div>
      </section>
      {error && <section className="error-panel" role="alert"><h2>Research could not load</h2><p>{error}</p>
        <button onClick={() => setRetry(value => value + 1)}>Try again</button></section>}
      {loading && !error && <p className="loading" role="status">Loading the verified research records...</p>}
      {research?.status === "unavailable" && <section className="starter-panel">
        <p className="eyebrow">Feature request / CALDOVA-001</p><h2>The research panel is not available in this preview.</h2>
        <p>The requested capability joins curated trial records with normalized safety-report mentions and shows their source identifiers.</p>
        <p>Use this starter preview to capture the baseline. The agent implementation exercise and release gate are still being prepared.</p>
      </section>}
      {research?.status === "ready" && <>
        <section className="metrics" aria-label="Evidence summary">
          <div><span>Trials matching the filters</span><strong>{matchingTrials.length}</strong><small>Source records, not an efficacy comparison</small></div>
          <div><span>Reports mentioning this candidate</span><strong>{research.safety_reports.length}</strong><small>Deduplicated reports, not an incidence rate</small></div>
          <div><span>Evidence mode</span><strong className="text-metric">{metadata?.manifest.dataset_kind === "synthetic-development" ? "Training fixture" : "Public lab extract"}</strong><small>No live clinical inference</small></div>
        </section>
        <div className="evidence-grid">
          <section className="evidence-panel" aria-labelledby="trials-heading">
            <div className="panel-heading"><div><p className="eyebrow">Clinical-trial records</p><h2 id="trials-heading">Trial evidence</h2></div><span className="count-label">{matchingTrials.length} of {research.trials.length} records</span></div>
            <div className="trial-summary" aria-label="Trial source coverage">
              <div><h3>By phase</h3><dl>{trialSummary.phases.map(([label, count]) =>
                <div key={label}><dt>{label.replaceAll("PHASE", "Phase ")}</dt><dd>{count}</dd></div>)}</dl></div>
              <div><h3>By status</h3><dl>{trialSummary.statuses.map(([label, count]) =>
                <div key={label}><dt>{label.replaceAll("_", " ").toLowerCase()}</dt><dd>{count}</dd></div>)}</dl></div>
            </div>
            <p className="panel-note">Counts describe this candidate/condition extract, not efficacy or safety. Phase and status filters affect trials only.</p>
            <div className="trial-filters">
              <label>Trial phase<select value={phase} onChange={event => { setPhase(event.target.value); setTrialLimit(10); }}>
                <option value="">All phases</option>{trialSummary.phases.map(([label]) =>
                  <option key={label} value={label}>{label.replaceAll("PHASE", "Phase ")}</option>)}
              </select></label>
              <label>Trial status<select value={trialStatus} onChange={event => { setTrialStatus(event.target.value); setTrialLimit(10); }}>
                <option value="">All statuses</option>{trialSummary.statuses.map(([label]) =>
                  <option key={label} value={label}>{label.replaceAll("_", " ").toLowerCase()}</option>)}
              </select></label>
            </div>
            {matchingTrials.length === 0 && <p className="empty-state">No trial records match the selected filters.</p>}
            {matchingTrials.slice(0, trialLimit).map(trial => <article className="trial-card" key={trial.trial_id}>
              <div className="record-tags"><span>{trial.phase.replace("PHASE", "Phase ")}</span><span>{trial.status.replaceAll("_", " ").toLowerCase()}</span></div>
              <h3>{trial.title}</h3><p>Matched research topics: {trial.conditions.map(item => item === "type-2-diabetes" ? "Type 2 diabetes" : "Obesity").join(", ")}</p>
              {trial.source_conditions && <details><summary>Original source labels</summary>
                <pre className="source-projection">{JSON.stringify({
                  conditions: trial.source_conditions, matched_interventions: trial.source_interventions,
                }, null, 2)}</pre>
              </details>}
              <Citation evidence={trial} sources={sources} />
            </article>)}
            {matchingTrials.length > trialLimit && <button onClick={() => setTrialLimit(previous => previous + 10)}>
              Show 10 more trials ({trialLimit} of {matchingTrials.length} shown)
            </button>}
          </section>
          <section className="evidence-panel" aria-labelledby="safety-heading">
            <div className="panel-heading"><div><p className="eyebrow">Report mentions</p><h2 id="safety-heading">Safety-report records</h2></div><span className="count-label">{research.safety_reports.length} reports</span></div>
            <p className="panel-note">Reports mention the selected candidate. They are not filtered to the trial condition and may mention more than one candidate.</p>
            {research.safety_reports.length === 0 && <p className="empty-state">No cached report records mention this candidate.</p>}
            {research.safety_reports.map(report => <article className="report-card" key={report.report_id}>
              <div className="report-title"><h3>{report.report_id}</h3><span>Version {report.version}</span></div>
              <p className="reaction-label">Reported terms</p><div className="reaction-terms">{report.reaction_terms.map(term => <span key={term}>{term.toLowerCase()}</span>)}</div>
              <p className="report-context">Candidate mentions: {report.candidate_ids.map(id => metadata?.candidates.find(item => item.candidate_id === id)?.name ?? id).join(", ")}</p>
              {report.source_drugs && <details><summary>Original report fields</summary>
                <p className="panel-note">Harmonized brand arrays are metadata, not proof of products taken.</p>
                <pre className="source-projection">{JSON.stringify({
                  matched_drugs: report.source_drugs, original_reaction_terms: report.original_reaction_terms,
                }, null, 2)}</pre>
              </details>}
              <Citation evidence={report} sources={sources} />
            </article>)}
          </section>
        </div>
      </>}
      {metadata && <section id="provenance" className="provenance" aria-labelledby="provenance-heading">
        <div><p className="eyebrow">Trace the input</p><h2 id="provenance-heading">Data provenance</h2>
          <p className="dataset-version">{metadata.manifest.dataset_version}</p>
          <p>{metadata.manifest.record_counts.raw_safety_reports} selected report versions normalize to {metadata.manifest.record_counts.safety_reports} distinct reports across the frozen lab extract.</p>
          {metadata.manifest.source_records && <a href="/api/source-records" target="_blank" rel="noreferrer">Inspect frozen original source fields</a>}
        </div>
        <details><summary>Artifact identity and source notes</summary>
          <dl><dt>SHA-256</dt><dd><code>{metadata.manifest.database.sha256}</code></dd><dt>Pipeline version</dt><dd>{metadata.manifest.pipeline_commit}</dd></dl>
          {metadata.manifest.pipeline_source && <p>Frozen pipeline-source ZIP SHA-256: <code>{metadata.manifest.pipeline_source.sha256}</code>. {/^[0-9a-f]{40}$/.test(metadata.manifest.pipeline_commit)
            ? "Source bytes are bound to the recorded Git commit; attendee readiness is a separate check."
            : "This working-tree snapshot is not a committed attendee release."}</p>}
          {metadata.manifest.public_extract && <div>
            <p>Selected lab-source use approved by {metadata.manifest.public_extract.source_use.approved_by} at {metadata.manifest.public_extract.source_use.approved_at}; no independent expert audit is claimed.</p>
            {metadata.manifest.public_extract.coverage_notes.map(note => <p key={note}>{note}</p>)}
          </div>}
          {sources.map(source => <div key={source.source_id}><h3>{source.name}</h3><p>{source.attribution}</p><p>{source.license_notes}</p>
            <p>Snapshot/export: {source.release}{source.retrieved_at && `; acquired ${source.retrieved_at}`}</p>
            {source.url && <a href={source.url} target="_blank" rel="noreferrer">Open source</a>}</div>)}
        </details>
      </section>}
      {metadata && <aside className="limitations" aria-label="Responsible-use limitations"><h2>Read the evidence within its limits</h2><p>{metadata.manifest.limitations}</p></aside>}
    </main>
    <footer>Caldova Research Preview Factory<span>Microsoft Ignite 2026 / LAB722</span></footer>
  </>;
}

const root = document.getElementById("root");
if (!root) throw new Error("The portal root element is missing.");
createRoot(root).render(<StrictMode><App /></StrictMode>);
