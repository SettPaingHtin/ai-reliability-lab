"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import { api, ApiError, postJson, type Dataset, type Page, type Project, type Run } from "@/lib/api";
import { formatMs, formatPercent } from "@/lib/format";

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lineErrors, setLineErrors] = useState<{ line: number; message: string }[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [dsName, setDsName] = useState("");
  const [target, setTarget] = useState("");
  const [jsonl, setJsonl] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, d, r] = await Promise.all([
        api<Project>(`/projects/${id}`),
        api<Page<Dataset>>(`/projects/${id}/datasets?limit=100`),
        api<Page<Run>>(`/projects/${id}/runs?limit=50`),
      ]);
      setProject(p);
      setDatasets(d.items);
      setRuns(r.items);
      setTarget((t) => t || d.items[0]?.id || "");
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load project");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function guarded(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setLineErrors([]);
    setNotice(null);
    try {
      await fn();
    } catch (e) {
      if (e instanceof ApiError) {
        setError(e.message);
        setLineErrors(e.lineErrors);
      } else setError("Unexpected error");
    } finally {
      setBusy(false);
    }
  }

  const createDataset = (e: React.FormEvent) => {
    e.preventDefault();
    void guarded(async () => {
      const d = await postJson<Dataset>(`/projects/${id}/datasets`, { name: dsName });
      setDsName("");
      setTarget(d.id);
      await load();
    });
  };

  const importJsonl = () =>
    void guarded(async () => {
      const res = await api<{ imported: number }>(`/datasets/${target}/import`, {
        method: "POST",
        headers: { "content-type": "text/plain" },
        body: jsonl,
      });
      setNotice(`Imported ${res.imported} test case(s).`);
      setJsonl("");
      await load();
    });

  const startRun = (datasetId: string) =>
    void guarded(async () => {
      const run = await postJson<Run>(`/datasets/${datasetId}/runs`, {});
      window.location.href = `/runs/${run.id}`;
    });

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setJsonl(await file.text());
  }

  if (error && !project) return <div role="alert" className="alert">{error}</div>;
  if (!project) return <p className="muted">Loading…</p>;

  return (
    <>
      <p><Link href="/">← Projects</Link></p>
      <h1>{project.name}</h1>
      <p className="muted">{project.description ?? ""}</p>
      {error && <div role="alert" className="alert">{error}
        {lineErrors.length > 0 && (
          <ul>{lineErrors.map((l) => <li key={`${l.line}-${l.message}`}>Line {l.line}: {l.message}</li>)}</ul>
        )}
      </div>}
      {notice && <div role="status" className="card" style={{ borderColor: "var(--ok)" }}>{notice}</div>}

      <h2>Datasets</h2>
      <form onSubmit={createDataset} className="row" aria-label="Create dataset">
        <label htmlFor="dname" className="muted">Name</label>
        <input id="dname" value={dsName} onChange={(e) => setDsName(e.target.value)} required maxLength={100} />
        <button className="primary" disabled={busy || !dsName.trim()}>Create dataset</button>
      </form>
      {datasets === null ? <p className="muted">Loading…</p> : datasets.length === 0 ? (
        <div className="empty" style={{ marginTop: 12 }}>No datasets yet.</div>
      ) : (
        <div className="table-wrap"><table>
          <thead><tr><th>Name</th><th>Cases</th><th></th></tr></thead>
          <tbody>{datasets.map((d) => (
            <tr key={d.id}>
              <td>{d.name}</td><td>{d.case_count}</td>
              <td><button disabled={busy || d.case_count === 0} onClick={() => startRun(d.id)}>Run evaluation (mock)</button>{" "}
                <a href={`/api/datasets/${d.id}/export`}>Export JSONL</a></td>
            </tr>))}
          </tbody>
        </table></div>
      )}

      {datasets && datasets.length > 0 && (
        <>
          <h2>Import JSONL</h2>
          <p className="muted">One JSON object per line: <code>input</code>, plus <code>expected</code> or <code>rules</code>. See datasets/sample.jsonl.</p>
          <div className="row">
            <label htmlFor="target" className="muted">Into dataset</label>
            <select id="target" value={target} onChange={(e) => setTarget(e.target.value)}>
              {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <input type="file" accept=".jsonl,.ndjson,.txt" onChange={onFile} aria-label="Choose JSONL file" />
          </div>
          <textarea aria-label="JSONL content" value={jsonl} onChange={(e) => setJsonl(e.target.value)} placeholder='{"input": "2+2?", "expected": "4"}' />
          <button className="primary" disabled={busy || !jsonl.trim() || !target} onClick={importJsonl}>Import</button>
        </>
      )}

      <h2>Run history</h2>
      {runs === null ? <p className="muted">Loading…</p> : runs.length === 0 ? (
        <div className="empty">No runs yet. Import cases and run an evaluation.</div>
      ) : (
        <div className="table-wrap"><table>
          <thead><tr><th>Started</th><th>Status</th><th>Model</th><th>Pass rate</th><th>Avg latency</th></tr></thead>
          <tbody>{runs.map((r) => (
            <tr key={r.id}>
              <td><Link href={`/runs/${r.id}`}>{new Date(r.created_at).toLocaleString()}</Link></td>
              <td><span className={`badge ${r.status}`}>{r.status}</span></td>
              <td>{r.provider}/{r.model}</td>
              <td>{formatPercent(r.pass_rate)}</td><td>{formatMs(r.avg_latency_ms)}</td>
            </tr>))}
          </tbody>
        </table></div>
      )}
    </>
  );
}
