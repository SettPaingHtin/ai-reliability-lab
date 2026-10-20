"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import { RunsTable } from "@/components/run-view";
import { EmptyState, SkeletonRows } from "@/components/ui";
import { api, ApiError, postJson, type Dataset, type Page, type Project, type Run } from "@/lib/api";

const MODELS = [
  { value: "mock-1", label: "mock-1 (baseline)" },
  { value: "mock-2", label: "mock-2 (candidate)" },
];

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [datasets, setDatasets] = useState<Dataset[] | null>(null);
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lineErrors, setLineErrors] = useState<{ line: number; message: string }[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [dsName, setDsName] = useState("");
  const [target, setTarget] = useState("");
  const [model, setModel] = useState(MODELS[0]!.value);
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
      setNotice(`Imported ${res.imported} test case${res.imported === 1 ? "" : "s"}.`);
      setJsonl("");
      await load();
    });

  const startRun = (datasetId: string) =>
    void guarded(async () => {
      const run = await postJson<Run>(`/datasets/${datasetId}/runs`, { provider: "mock", model });
      router.push(`/runs/${run.id}`);
    });

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) setJsonl(await file.text());
  }

  if (error && !project) return <div role="alert" className="alert">{error}</div>;
  if (!project) return <SkeletonRows rows={4} />;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumbs"><Link href="/">Projects</Link> / {project.name}</div>
          <h1>{project.name}</h1>
          {project.description && <p className="sub">{project.description}</p>}
        </div>
      </div>

      {error && (
        <div role="alert" className="alert">
          {error}
          {lineErrors.length > 0 && (
            <ul>{lineErrors.map((l) => <li key={`${l.line}-${l.message}`}>Line {l.line}: {l.message}</li>)}</ul>
          )}
        </div>
      )}
      {notice && <div role="status" className="notice">{notice}</div>}

      <div className="section">
        <div className="section-head">
          <h2>Datasets</h2>
          <div className="row">
            <label htmlFor="model" className="hint">Run with model</label>
            <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
              {MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
        </div>
        <form onSubmit={createDataset} className="card card-pad row" aria-label="Create dataset" style={{ alignItems: "flex-end", marginBottom: 12 }}>
          <div className="field" style={{ flex: 1, minWidth: 200 }}>
            <label htmlFor="dname">New dataset name</label>
            <input id="dname" type="text" value={dsName} onChange={(e) => setDsName(e.target.value)} required maxLength={100} placeholder="e.g. qa-suite" />
          </div>
          <button className="btn" disabled={busy || !dsName.trim()}>Create dataset</button>
        </form>
        {datasets === null ? <SkeletonRows rows={2} /> : datasets.length === 0 ? (
          <EmptyState title="No datasets yet">Create one above, then import test cases.</EmptyState>
        ) : (
          <div className="card table-wrap">
            <table>
              <thead><tr><th>Name</th><th className="num">Cases</th><th className="num">Actions</th></tr></thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id}>
                    <td><strong>{d.name}</strong></td>
                    <td className="num">{d.case_count}</td>
                    <td className="num">
                      <div className="row" style={{ justifyContent: "flex-end" }}>
                        <a className="btn btn-sm" href={`/api/datasets/${d.id}/export`}>Export JSONL</a>
                        <button className="btn btn-sm btn-primary" disabled={busy || d.case_count === 0} onClick={() => startRun(d.id)}>Run evaluation</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {datasets && datasets.length > 0 && (
        <div className="section">
          <div className="section-head">
            <h2>Import test cases</h2>
            <span className="hint">JSONL, one case per line · try <code>datasets/mock-qa-suite.jsonl</code></span>
          </div>
          <div className="card card-pad">
            <div className="row" style={{ marginBottom: 12, alignItems: "flex-end" }}>
              <div className="field">
                <label htmlFor="target">Into dataset</label>
                <select id="target" value={target} onChange={(e) => setTarget(e.target.value)}>
                  {datasets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
              <div className="field">
                <label htmlFor="file">Or choose a file</label>
                <input id="file" type="file" accept=".jsonl,.ndjson,.txt" onChange={onFile} />
              </div>
            </div>
            <textarea aria-label="JSONL content" value={jsonl} onChange={(e) => setJsonl(e.target.value)} placeholder={'{"input": "What is 2 + 2?", "expected": "4"}'} />
            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" disabled={busy || !jsonl.trim() || !target} onClick={importJsonl}>Import</button>
              {jsonl && <span className="hint">{jsonl.split("\n").filter((l) => l.trim()).length} line(s) ready</span>}
            </div>
          </div>
        </div>
      )}

      <div className="section">
        <div className="section-head"><h2>Run history</h2></div>
        {runs === null ? <SkeletonRows rows={3} /> : <RunsTable runs={runs} />}
      </div>
    </>
  );
}
