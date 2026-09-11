import React, { useState } from "react";
import { api, useData, Panel, Table, ActionButton, RefreshButton } from "./App";

const editorRoles = ["authority", "admin", "district_authority", "state_authority", "acquisition_officer", "field_officer"];
const money = value => `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

function ProjectSelector({ projects, value, onChange }) {
  return <select value={value} onChange={e => onChange(e.target.value)}>
    <option value="">Select project</option>
    {(projects?.items || []).map(project => <option key={project.project_id} value={project.project_id}>{project.project_id} - {project.project_name}</option>)}
  </select>;
}

function MetricCards({ items }) {
  return <div className="cards">{items.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><b>{value}</b></div>)}</div>;
}

export function IntelligenceOverview() {
  const { data, error } = useData("/intelligence-data/dashboard", 5000);
  if (error) return <Panel title="Intelligence Dashboard"><div className="error">{error.message}</div></Panel>;
  if (!data) return <Panel title="Intelligence Dashboard">Loading...</Panel>;
  return <>
    <Panel title="Parcel-Centric Intelligence Dashboard">
      <MetricCards items={[
        ["Total Assessed", money(data.compensation.total_assessed)], ["Paid", money(data.compensation.amount_paid)],
        ["Pending", money(data.compensation.amount_pending)], ["Payment Completion", `${data.payment_completion}%`],
        ["Affected Families", data.families.affected], ["Displaced Families", data.families.displaced],
        ["R&R Pending", data.families.rr_pending], ["Satellite Changes", data.satellite.changes]
      ]} />
      <p className="notice">{data.data_note}</p>
    </Panel>
    <div className="grid2">
      <Panel title="Risk Distribution"><Table rows={data.risk_distribution || []} cols={["category", "count"]} /></Panel>
      <Panel title="Family Impact"><Table rows={[
        { status: "Affected", count: data.families.affected }, { status: "Displaced", count: data.families.displaced },
        { status: "Vulnerable", count: data.families.vulnerable }, { status: "R&R Completed", count: data.families.rr_completed }
      ]} cols={["status", "count"]} /></Panel>
    </div>
  </>;
}

export function CompensationIntelligence({ user }) {
  const { data: projects } = useData("/projects/?limit=500", 10000);
  const [projectId, setProjectId] = useState("");
  const { data: rows, error } = useData(projectId ? `/intelligence-data/compensation/project/${encodeURIComponent(projectId)}` : null, 5000);
  const [form, setForm] = useState({ parcel_id: "", land_compensation: "", structure_compensation: "", livelihood_compensation: "", rr_compensation: "", other_compensation: "", amount_paid: "", remarks: "" });
  const [message, setMessage] = useState("");
  const canEdit = editorRoles.includes(user?.role);
  const update = key => e => setForm({ ...form, [key]: e.target.value });
  const create = async e => {
    e.preventDefault(); setMessage("");
    try {
      const result = await api("/intelligence-data/compensation", { method: "POST", body: JSON.stringify({ ...form, project_id: projectId }) });
      setMessage(`Compensation ${result.compensation_id} saved. Pending: ${money(result.amount_pending)}`);
    } catch (err) { setMessage(err.message); }
  };
  return <>
    <Panel title="Compensation Intelligence">
      <div className="toolbar"><ProjectSelector projects={projects} value={projectId} onChange={setProjectId} /><RefreshButton /></div>
      {error && <div className="error">{error.message}</div>}
      {projectId && <Table rows={rows || []} cols={["compensation_id", "parcel_id", "survey_no", "land_compensation", "structure_compensation", "livelihood_compensation", "rr_compensation", "total_assessed", "paid_amount", "pending_amount", "approval_status"]} />}
    </Panel>
    {canEdit && projectId && <Panel title="Record Assessed Compensation">
      <form className="form" onSubmit={create}>
        <label>Parcel ID <input required value={form.parcel_id} onChange={update("parcel_id")} /></label>
        {[['land_compensation', 'Land'], ['structure_compensation', 'Structure'], ['livelihood_compensation', 'Livelihood'], ['rr_compensation', 'R&R'], ['other_compensation', 'Other'], ['amount_paid', 'Amount paid']].map(([key, label]) => <label key={key}>{label} <input type="number" min="0" step="0.01" value={form[key]} onChange={update(key)} /></label>)}
        <label>Remarks <textarea value={form.remarks} onChange={update("remarks")} /></label>
        <button type="submit">Save Compensation</button>
      </form>
      {message && <div className="notice">{message}</div>}
    </Panel>}
  </>;
}

export function FamilyImpact({ user }) {
  const { data: projects } = useData("/projects/?limit=500", 10000);
  const [projectId, setProjectId] = useState("");
  const { data: rows, error } = useData(projectId ? `/intelligence-data/families/project/${encodeURIComponent(projectId)}` : null, 5000);
  const [form, setForm] = useState({ parcel_id: "", family_reference: "", members_count: "", affected: true, displaced: false, vulnerable: false, rr_required: false, remarks: "" });
  const [message, setMessage] = useState("");
  const canEdit = editorRoles.includes(user?.role);
  const update = key => e => setForm({ ...form, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const create = async e => {
    e.preventDefault(); setMessage("");
    try { const result = await api("/intelligence-data/families", { method: "POST", body: JSON.stringify({ ...form, project_id: projectId }) }); setMessage(`${result.family_id} saved.`); }
    catch (err) { setMessage(err.message); }
  };
  return <>
    <Panel title="Affected & Displaced Family Intelligence">
      <div className="toolbar"><ProjectSelector projects={projects} value={projectId} onChange={setProjectId} /><RefreshButton /></div>
      {error && <div className="error">{error.message}</div>}
      {projectId && <Table rows={rows || []} cols={["family_id", "family_reference", "parcel_id", "survey_no", "members_count", "affected", "displaced", "vulnerable", "rr_required", "rr_status", "compensation_status", "verification_status"]} />}
    </Panel>
    {canEdit && projectId && <Panel title="Add Verified Family Impact Record">
      <form className="form" onSubmit={create}>
        <label>Parcel ID <input required value={form.parcel_id} onChange={update("parcel_id")} /></label>
        <label>Anonymous Family Reference <input required placeholder="FAM-000124" value={form.family_reference} onChange={update("family_reference")} /></label>
        <label>Members <input type="number" min="0" value={form.members_count} onChange={update("members_count")} /></label>
        {[['affected', 'Affected'], ['displaced', 'Displaced'], ['vulnerable', 'Vulnerable'], ['rr_required', 'R&R Required']].map(([key, label]) => <label key={key}><input type="checkbox" checked={form[key]} onChange={update(key)} /> {label}</label>)}
        <label>Remarks <textarea value={form.remarks} onChange={update("remarks")} /></label>
        <button type="submit">Save Family Record</button>
      </form>
      {message && <div className="notice">{message}</div>}
    </Panel>}
  </>;
}

export function SatelliteIntelligence({ user }) {
  const { data: projects } = useData("/projects/?limit=500", 10000);
  const [projectId, setProjectId] = useState("");
  const { data: rows, error } = useData(projectId ? `/intelligence-data/satellite/project/${encodeURIComponent(projectId)}` : null, 5000);
  const [form, setForm] = useState({ parcel_id: "", baseline_date: "", current_date: "", observation_date: "", change_status: "NO_SIGNIFICANT_CHANGE", confidence: "", source: "", before_image_url: "", after_image_url: "", notes: "" });
  const [message, setMessage] = useState("");
  const canEdit = editorRoles.includes(user?.role);
  const update = key => e => setForm({ ...form, [key]: e.target.value });
  const create = async e => {
    e.preventDefault(); setMessage("");
    try { const result = await api("/intelligence-data/satellite", { method: "POST", body: JSON.stringify({ ...form, project_id: projectId, synthetic_flag: true }) }); setMessage(`${result.evidence_id} saved for field verification.`); }
    catch (err) { setMessage(err.message); }
  };
  return <>
    <Panel title="Satellite Intelligence">
      <div className="toolbar"><ProjectSelector projects={projects} value={projectId} onChange={setProjectId} /><RefreshButton /></div>
      <p className="notice">Only supplied imagery references are displayed. No satellite imagery or coordinates are fabricated.</p>
      {error && <div className="error">{error.message}</div>}
      {projectId && <Table rows={rows || []} cols={["evidence_id", "parcel_id", "survey_no", "baseline_date", "current_date", "change_status", "confidence", "observation_date", "verification_status", "field_verification_status"]} />}
    </Panel>
    {canEdit && projectId && <Panel title="Add Satellite Observation">
      <form className="form" onSubmit={create}>
        <label>Parcel ID <input required value={form.parcel_id} onChange={update("parcel_id")} /></label>
        <label>Baseline date <input type="date" value={form.baseline_date} onChange={update("baseline_date")} /></label>
        <label>Current date <input type="date" value={form.current_date} onChange={update("current_date")} /></label>
        <label>Observation date <input type="date" value={form.observation_date} onChange={update("observation_date")} /></label>
        <label>Change status <select value={form.change_status} onChange={update("change_status")}><option>NO_SIGNIFICANT_CHANGE</option><option>NEW_CONSTRUCTION</option><option>LAND_USE_CHANGE</option><option>POSSIBLE_ENCROACHMENT</option><option>VEGETATION_CHANGE</option><option>SURFACE_CHANGE</option><option>INFRASTRUCTURE_PROGRESS</option></select></label>
        <label>Confidence (0-1) <input type="number" min="0" max="1" step="0.01" value={form.confidence} onChange={update("confidence")} /></label>
        <label>Source <input placeholder="Provider or field source" value={form.source} onChange={update("source")} /></label>
        <label>Before image URL (optional) <input value={form.before_image_url} onChange={update("before_image_url")} /></label>
        <label>After image URL (optional) <input value={form.after_image_url} onChange={update("after_image_url")} /></label>
        <label>Notes <textarea value={form.notes} onChange={update("notes")} /></label>
        <button type="submit">Save Satellite Evidence</button>
      </form>
      {message && <div className="notice">{message}</div>}
    </Panel>}
  </>;
}

export function ParcelIntelligence({ parcelId }) {
  const { data: families } = useData(parcelId ? `/intelligence-data/families/parcel/${parcelId}` : null, 5000);
  const { data: compensation } = useData(parcelId ? `/intelligence-data/compensation/parcel/${parcelId}` : null, 5000);
  const { data: satellite } = useData(parcelId ? `/intelligence-data/satellite/parcel/${parcelId}` : null, 5000);
  return <div className="grid2">
    <Panel title="Family Impact"><Table rows={families || []} cols={["family_id", "family_reference", "members_count", "affected", "displaced", "rr_status", "verification_status"]} /></Panel>
    <Panel title="Compensation"><Table rows={compensation ? [compensation] : []} cols={["total_assessed", "paid_amount", "pending_amount", "approval_status", "award_reference"]} /></Panel>
    <Panel title="Satellite Evidence"><Table rows={satellite || []} cols={["evidence_id", "change_status", "confidence", "observation_date", "field_verification_status"]} /></Panel>
  </div>;
}
