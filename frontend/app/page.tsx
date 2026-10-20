"use client";

import { useCallback, useEffect, useState } from "react";
import { ProjectGrid } from "@/components/run-view";
import { EmptyState, SkeletonRows } from "@/components/ui";
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
      <div className="page-head">
        <div>
          <h1>Projects</h1>
          <p className="sub">Each project holds datasets and the evaluation runs made against them.</p>
        </div>
      </div>

      <form onSubmit={create} className="card card-pad row" aria-label="Create project" style={{ alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1, minWidth: 220 }}>
          <label htmlFor="pname">New project name</label>
          <input id="pname" type="text" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} placeholder="e.g. support-bot" />
        </div>
        <button className="btn btn-primary" disabled={busy || !name.trim()}>Create project</button>
      </form>

      {error && <div role="alert" className="alert">{error}</div>}

      <div className="section">
        <div className="section-head">
          <h2>All projects{projects ? ` (${projects.length})` : ""}</h2>
        </div>
        {projects === null && !error && <SkeletonRows />}
        {projects?.length === 0 && (
          <EmptyState title="No projects yet">Create your first project above to get started.</EmptyState>
        )}
        {projects && projects.length > 0 && <ProjectGrid projects={projects} />}
      </div>
    </>
  );
}
