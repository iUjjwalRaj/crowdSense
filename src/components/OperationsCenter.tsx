import { useEffect, useState } from "react";
import { getOperationsSnapshot, getRecommendations, reviewRecommendation } from "../api";
import { syntheticAdvisories, syntheticOperationsSnapshot } from "../operationsFixtures";
import type { Advisory, OperationsSnapshot } from "../types";
import MapView from "./MapView";

const AUDIT_KEY = "crowdsense.operations.audit";

type AuditEntry = {
  timestamp: string;
  advisoryId: string;
  action: "approve" | "reject" | "defer";
  authorizedBy: string;
};

export default function OperationsCenter() {
  const [snapshot, setSnapshot] = useState<OperationsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedAdvisory, setSelectedAdvisory] = useState<Advisory | null>(null);
  const [authorized, setAuthorized] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [reviewAction, setReviewAction] = useState<"approve" | "reject" | "defer">("approve");
  const [audits, setAudits] = useState<AuditEntry[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(AUDIT_KEY) || "[]") as AuditEntry[];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    let active = true;
    getOperationsSnapshot()
      .then((data) => { if (active) setSnapshot(data); })
      .catch((caught) => {
        if (!active) return;
        setError(caught instanceof Error ? caught.message : "Operations snapshot unavailable");
        if (import.meta.env.DEV) setSnapshot(syntheticOperationsSnapshot);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    getRecommendations().catch(() => undefined);
  }, []);

  function closeDialog() {
    setSelectedAdvisory(null);
    setAuthorized("");
    setConfirmed(false);
    setReviewAction("approve");
  }

  function recordDraft() {
    if (!selectedAdvisory || !authorized.trim() || !confirmed) return;
    const entry: AuditEntry = {
      timestamp: new Date().toISOString(),
      advisoryId: selectedAdvisory.id,
      action: reviewAction,
      authorizedBy: authorized.trim(),
    };
    const next = [entry, ...audits].slice(0, 20);
    setAudits(next);
    localStorage.setItem(AUDIT_KEY, JSON.stringify(next));
    void reviewRecommendation(selectedAdvisory.id, reviewAction, authorized.trim())
      .catch(() => undefined);
    closeDialog();
  }

  const advisories = snapshot?.source === "estimated"
    ? syntheticAdvisories
    : [];

  return (
    <main className="operations-app">
      <header className="operations-header">
        <div><p className="eyebrow">Transit operations</p><h1>Command Center</h1></div>
        <span className={`data-state ${snapshot?.source === "live" ? "live" : ""}`}>
          {snapshot?.source === "live" ? "API live" : snapshot ? "Estimated / fixture" : "Data unavailable"}
        </span>
      </header>

      {loading && <p className="ops-status" role="status">Loading operations snapshot…</p>}
      {error && <p className="ops-status" role="alert">{error}{snapshot ? " Showing development fixture." : ""}</p>}

      <section className="metrics-grid" aria-label="Network overview">
        <article><p>Active routes</p><strong>{snapshot?.active_routes ?? "Unavailable"}</strong><span>{snapshot?.source === "estimated" ? "Estimated" : snapshot?.source === "live" ? "API" : "No source"}</span></article>
        <article><p>Active vehicles</p><strong>{snapshot?.active_vehicles ?? "Unavailable"}</strong><span>{snapshot?.source === "estimated" ? "Estimated" : snapshot?.source === "live" ? "API" : "No source"}</span></article>
        <article><p>On-time</p><strong>{snapshot?.on_time_percentage != null ? `${snapshot.on_time_percentage}%` : "Unavailable"}</strong><span>{snapshot?.source === "estimated" ? "Estimated" : snapshot?.source === "live" ? "API" : "No source"}</span></article>
      </section>

      <section className="ops-grid">
        <article className="ops-panel network-panel">
          <div className="panel-heading"><div><p className="eyebrow">Network</p><h2>Route & segment overlay</h2></div></div>
          <MapView />
        </article>

        <article className="ops-panel">
          <div className="panel-heading"><div><p className="eyebrow">Intelligence</p><h2>Route status</h2></div></div>
          {snapshot?.corridors?.length ? snapshot.corridors.map((corridor) => (
            <div className="corridor-row" key={corridor.id}>
              <span className={`crowd-dot ${corridor.crowd}`} />
              <div><strong>{corridor.name}</strong><small>{corridor.id} · {corridor.occupancy != null ? `${corridor.occupancy}% occupancy` : "Occupancy unavailable"}</small></div>
            </div>
          )) : <p className="ops-status">Corridor intelligence unavailable.</p>}
        </article>

        <article className="ops-panel">
          <div className="panel-heading"><div><p className="eyebrow">Radar</p><h2>Bottlenecks</h2></div></div>
          {snapshot?.corridors?.filter((item) => item.crowd === "full" || item.crowd === "crowded").map((item) => (
            <div className="bottleneck" key={item.id}><strong>{item.name}</strong><span>{item.crowd} · {item.occupancy != null ? `${item.occupancy}% predicted` : "Data unavailable"}</span></div>
          )) || <p className="ops-status">No bottleneck data source.</p>}
        </article>

        <article className="ops-panel">
          <div className="panel-heading"><div><p className="eyebrow">Advisory center</p><h2>Recommendations</h2></div></div>
          {advisories.length ? advisories.map((advisory) => (
            <div className="advisory" key={advisory.id}>
              <div><strong>{advisory.title}</strong><p>{advisory.description}</p><small>{advisory.dataSource} · {advisory.severity} severity</small></div>
              <button type="button" onClick={() => setSelectedAdvisory(advisory)}>Draft advisory</button>
            </div>
          )) : <p className="ops-status">No recommendations available from the current API data.</p>}
        </article>

        <article className="ops-panel analytics-panel">
          <div className="panel-heading"><div><p className="eyebrow">Analytics</p><h2>Historical occupancy</h2></div></div>
          {snapshot?.source === "estimated"
            ? <div className="spark-bars" aria-label="Synthetic historical occupancy fixture">{[54, 61, 58, 72, 68, 82, 76].map((value, index) => <i key={index} style={{ height: `${value}%` }} title={`Fixture: ${value}%`} />)}</div>
            : <p className="ops-status">Historical data unavailable.</p>}
        </article>
      </section>

      {audits.length > 0 && (
        <section className="audit-log" aria-labelledby="audit-heading">
          <h2 id="audit-heading">Local audit trail</h2>
          {audits.map((entry) => <p key={`${entry.timestamp}-${entry.advisoryId}`}><strong>{entry.timestamp}</strong> · {entry.authorizedBy} · {entry.action} {entry.advisoryId}</p>)}
        </section>
      )}

      {selectedAdvisory && (
        <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}>
          <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-heading">
            <p className="eyebrow">Authorization required</p>
            <h2 id="confirm-heading">Draft advisory</h2>
            <p>This creates an audit record only. It does not publish or change operations.</p>
            <label>Authorized identity<input value={authorized} onChange={(event) => setAuthorized(event.target.value)} placeholder="Operator name or role" /></label>
            <label className="confirm-check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I confirm this advisory draft action</label>
            <label>Review action
              <select value={reviewAction} onChange={(event) => setReviewAction(event.target.value as "approve" | "reject" | "defer")}>
                <option value="approve">Approve</option>
                <option value="reject">Reject</option>
                <option value="defer">Defer</option>
              </select>
            </label>
            <div className="dialog-actions"><button type="button" onClick={closeDialog}>Cancel</button><button type="button" disabled={!authorized.trim() || !confirmed} onClick={recordDraft}>Confirm & audit</button></div>
          </section>
        </div>
      )}
    </main>
  );
}
