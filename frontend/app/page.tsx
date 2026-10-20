"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, postJson, type Page, type Project } from "@/lib/api";

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setProjects((await api<Page<Project>>("/projects?limit=100")).items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load projects");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await postJson<Project>("/projects", { name });
      setName("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create project");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Projects</h1>
      <p className="muted">Each project holds datasets and evaluation runs.</p>
      <form onSubmit={create} className="row" aria-label="Create project">
        <label htmlFor="pname" className="muted">Name</label>
        <input id="pname" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
        <button className="primary" disabled={busy || !name.trim()}>Create project</button>
      </form>
      {error && <div role="alert" className="alert">{error}</div>}
      <h2>All projects</h2>
      {projects === null && !error && <p className="muted">Loading…</p>}
      {projects?.length === 0 && <div className="empty">No projects yet. Create one above to get started.</div>}
      {projects && projects.length > 0 && (
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))" }}>
          {projects.map((p) => (
            <Link key={p.id} href={`/projects/${p.id}`} className="card" style={{ textDecoration: "none", color: "inherit" }}>
              <strong>{p.name}</strong>
              <div className="muted">{p.description ?? "No description"}</div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
