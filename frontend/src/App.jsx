import React, { useEffect, useState, useMemo } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, Polygon, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import icon from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";
import iconRetina from "leaflet/dist/images/marker-icon-2x.png";
import DocumentsPage from "./DocumentsPage";
import ProjectAcquisitionMap, { isParcelAcquired, createSquareIcon } from "./ProjectAcquisitionMap";
import LandParcels from "./LandParcels";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetina,
  iconUrl: icon,
  shadowUrl: iconShadow,
});

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8001";
const AUTH_LOGIN_PATH = "/auth/login";
const AUTH_ME_PATH = "/auth/me";

// Simple global event bus to eliminate manual refreshes
const EventBus = {
  listeners: new Set(),
  dispatch() { this.listeners.forEach(l => l()); },
  subscribe(l) { this.listeners.add(l); return () => this.listeners.delete(l); }
};

// API Wrapper with automatic event bus dispatch on mutations
async function api(path, opt = {}) {
  if (!path) throw Error("API endpoint is not configured");
  const t = localStorage.getItem("survi_token");
  let headers = { ...(opt.headers || {}) };
  if (!(opt.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (t) headers.Authorization = "Bearer " + t;
  let r;
  try {
    r = await fetch(API + path, { ...opt, headers });
  } catch (error) {
    throw Error(error.message || "Unable to reach the backend API");
  }
  let j = {};
  try { j = await r.json(); } catch {}
  if (!r.ok) {
    const detail = j.detail || j.message;
    const message = typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : `Request failed (${r.status})`;
    const error = Error(message);
    error.status = r.status;
    throw error;
  }
  
  // If this was a mutation (POST, PUT, PATCH, DELETE), trigger a global refresh
  if (opt.method && opt.method !== "GET") {
    EventBus.dispatch();
  }
  return j;
}

const nav = [
  ["dashboard", "Command Center"], ["state_dashboard", "State Authority Dashboard"], 
  ["district_dashboard", "District Authority Dashboard"], ["projects", "Projects"], 
  ["parcels", "Land Parcels"], ["gis", "GIS Intelligence"], ["workflow", "Acquisition Workflow"], 
  ["sla", "SLA & Timeline"], ["bottlenecks", "Bottleneck Detection"], ["field", "Field Verification"], 
  ["documents", "Documents / OCR"], ["risk", "Risk Intelligence"], ["alerts", "Alerts"], 
  ["analytics", "Analytics"], ["intelligence", "Advanced Intelligence"], ["reports", "Reports / MIS"], ["grievances", "Grievances"], 
  ["ml", "ML Monitoring"], ["users", "Users"], ["audit", "Audit Trail"], ["citizen_dash", "Citizen View"]
];
const tamil = { "Command Center": "கட்டளை மையம்", "Projects": "திட்டங்கள்", "Land Parcels": "நிலப்பகுதிகள்", "GIS Intelligence": "GIS நுண்ணறிவு", "Acquisition Workflow": "கையகப்படுத்தல் பணிப்பாய்வு", "SLA & Timeline": "SLA மற்றும் காலவரிசை", "Bottleneck Detection": "தாமதங்களை கண்டறிதல்", "Field Verification": "கள சரிபார்ப்பு", "Documents / OCR": "ஆவணங்கள் / OCR", "Risk Intelligence": "இடர் நுண்ணறிவு", "Alerts": "எச்சரிக்கைகள்", "Analytics": "பகுப்பாய்வு", "Advanced Intelligence": "மேம்பட்ட நுண்ணறிவு", "Reports / MIS": "அறிக்கைகள்", "Grievances": "குறைகள்", "ML Monitoring": "ML கண்காணிப்பு", "Users": "பயனர்கள்", "Audit Trail": "தணிக்கை பதிவு", "Citizen View": "குடிமக்கள் பார்வை" };

function Login({ onLogin }) {
  let [e, setE] = useState("state@cbe.ac.in"), [p, setP] = useState("Tngov@CBE#2026"), [err, setErr] = useState(""), [loading, setLoading] = useState(false);
  return (
    <div className="login">
      <div className="login-card">
        <div className="brand-mark">L</div><h1>LANDNEXUS</h1><p>Parcel-centric land acquisition intelligence</p>
        <input value={e} onChange={x => setE(x.target.value)} placeholder="Official email" />
        <input type="password" value={p} onChange={x => setP(x.target.value)} placeholder="Password" />
        <button disabled={loading} onClick={async () => {
          setLoading(true); setErr("");
          try {
            let x = await api(AUTH_LOGIN_PATH, { method: "POST", body: JSON.stringify({ email: e, password: p }) });
            localStorage.setItem("survi_token", x.access_token);
            onLogin(x.user);
          } catch (x) { setErr(x.message || "Login failed. Please check your credentials and try again."); }
          finally { setLoading(false); }
        }}>
          {loading ? "Authenticating..." : "Secure Login"}
        </button>
        {err && <div className="error">{err}</div>}
        <div style={{ fontSize: "11px", color: "#666", marginTop: "10px" }}>
          Demo Accounts (Pass: Tngov@CBE#2026):<br />state@cbe.ac.in<br />district@cbe.ac.in<br />field@cbe.ac.in<br />citizen@cbe.ac.in
        </div>
      </div>
    </div>
  );
}

function Cards({ d }) {
  let cards = [
    ["Total Projects", d.total_projects], ["Active Projects", d.active_projects], 
    ["Completed Projects", d.completed_projects], ["Delayed Projects", d.delayed_projects], 
    ["Total Parcels", d.total_parcels], ["Affected Families", d.affected_families], 
    ["High Risk", d.high_risk_projects], ["Critical", d.critical_projects], 
    ["Pending Compensation", d.pending_compensation], ["Paid Compensation", d.paid_compensation], 
    ["Legal Disputes", d.legal_disputes], ["SLA Breaches", d.sla_breaches]
  ];
  return <div className="cards">{cards.map(c => <div className="metric" key={c[0]}><span>{c[0]}</span><b>{c[1] ?? 0}</b></div>)}</div>;
}

function CreateProjectForm({ onSuccess, onCancel }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    project_id: "PRJ-" + new Date().getFullYear() + "-DIST-" + Math.floor(Math.random()*1000).toString().padStart(3, '0'),
    project_name: "", project_type: "Rail", district: "Coimbatore", taluk: "", village: "",
    land_required: 0, priority: "High", project_start_date: "", planned_completion_date: "",
    description: "", department: "", estimated_project_cost: 0, remarks: ""
  });

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      await api("/projects/", { method: "POST", body: JSON.stringify(form) });
      onSuccess();
    } catch (err) {
      setError(err.message || "Failed to create project.");
    }
    setLoading(false);
  };

  return (
    <div style={{ background: "#fff", padding: "20px", border: "1px solid #ddd", marginBottom: "20px", borderRadius: "8px" }}>
      <h3>Create New Project</h3>
      <form onSubmit={submit} className="form" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px" }}>
        <label>Project ID <input value={form.project_id} readOnly style={{ background: "#f5f5f5" }} /></label>
        <label>Project Name* <input required value={form.project_name} onChange={e => setForm({...form, project_name: e.target.value})} /></label>
        <label>Project Type 
          <select value={form.project_type} onChange={e => setForm({...form, project_type: e.target.value})}>
            <option>Rail</option><option>Road</option><option>Airport</option><option>Irrigation</option><option>Industrial</option>
          </select>
        </label>
        <label>District* <input required value={form.district} onChange={e => setForm({...form, district: e.target.value})} /></label>
        <label>Taluk* <input required value={form.taluk} onChange={e => setForm({...form, taluk: e.target.value})} /></label>
        <label>Village <input value={form.village} onChange={e => setForm({...form, village: e.target.value})} /></label>
        <label>Est. Land Area (Acres) <input type="number" step="0.01" value={form.land_required} onChange={e => setForm({...form, land_required: parseFloat(e.target.value)})} /></label>
        <label>Priority
          <select value={form.priority} onChange={e => setForm({...form, priority: e.target.value})}>
             <option>High</option><option>Medium</option><option>Low</option>
          </select>
        </label>
        <label>Proposed Start Date <input type="date" value={form.project_start_date} onChange={e => setForm({...form, project_start_date: e.target.value})} /></label>
        <label>Target Completion Date <input type="date" value={form.planned_completion_date} onChange={e => setForm({...form, planned_completion_date: e.target.value})} /></label>
        <label>Department / Agency <input value={form.department} onChange={e => setForm({...form, department: e.target.value})} /></label>
        <label>Est. Project Cost (₹) <input type="number" value={form.estimated_project_cost} onChange={e => setForm({...form, estimated_project_cost: parseFloat(e.target.value)})} /></label>
        <label style={{ gridColumn: "1 / -1" }}>Description <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} /></label>
        
        <div style={{ gridColumn: "1 / -1", display: "flex", gap: "10px" }}>
          <button type="submit" disabled={loading}>{loading ? "Saving..." : "Create Project"}</button>
          <button type="button" onClick={onCancel} style={{ background: "#ccc", color: "#333" }}>Cancel</button>
        </div>
      </form>
      {error && <div className="error" style={{ marginTop: "10px" }}>{error}</div>}
    </div>
  );
}

function useData(path, refreshMs = 0) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    if (!path) {
      setData(null);
      setError(null);
      return undefined;
    }
    const fetcher = () => api(path).then(setData).catch(setError);
    fetcher();
    const unsubscribe = EventBus.subscribe(fetcher);
    const timer = refreshMs > 0 ? setInterval(fetcher, refreshMs) : null;
    return () => { unsubscribe(); if (timer) clearInterval(timer); };
  }, [path, refreshMs]);
  return { data, error };
}

function StateDashboard() {
  const { data: d } = useData("/dashboard/state", 5000);
  const [showCreate, setShowCreate] = useState(false);
  
  if (!d) return <Panel title="State Authority Dashboard">Loading…</Panel>;
  let cards = [["Total Projects", d.total_projects], ["Active Projects", d.active_projects], ["Completed Projects", d.completed_projects], ["Total Parcels", d.total_parcels], ["Affected Families", d.affected_families], ["High Risk", d.high_risk_projects], ["Critical", d.critical_projects], ["Pending Compensation", d.pending_compensation], ["Legal Disputes", d.legal_disputes], ["Delayed Projects", d.delayed_projects], ["SLA Breaches", d.sla_breaches], ["Escalated Cases", d.escalated_cases]];
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
        <h2 style={{ margin: 0 }}>State Authority Command Center</h2>
        {!showCreate && <button onClick={() => setShowCreate(true)} style={{ background: "#0056b3", color: "white", padding: "8px 16px" }}>+ Create Project</button>}
      </div>
      
      {showCreate && <CreateProjectForm onSuccess={() => setShowCreate(false)} onCancel={() => setShowCreate(false)} />}
      
      <Panel title="State Authority Dashboard"><div className="cards">{cards.map(c => <div className="metric" key={c[0]}><span>{c[0]}</span><b>{c[1] ?? 0}</b></div>)}</div></Panel>
      <div className="grid2">
        <Panel title="Risk Distribution"><Bars data={d.risk_distribution} label="category" /></Panel>
        <Panel title="Projects by Stage"><Bars data={d.projects_by_stage} label="stage" /></Panel>
      </div>
      <div className="grid2">
        <Panel title="District Performance (Coimbatore Scope)"><Table rows={d.district_performance || []} cols={["district", "projects", "avg_progress"]} /></Panel>
        <Panel title="Major Bottlenecks"><Table rows={d.bottlenecks || []} cols={["stage", "count"]} /></Panel>
      </div>
      <div className="grid2">
        <Panel title="R&R Progress"><Table rows={d.rr_progress || []} cols={["status", "count"]} /></Panel>
      </div>
    </>
  );
}

function DistrictDashboard({ go, user }) {
  const { data: d, error: dashboardError } = useData("/dashboard/district", 5000);
  const { data: alertsList, error: alertsError } = useData("/alerts/?status=Open", 5000);
  const { data: projectList, error: projectsError } = useData("/projects/?limit=500", 5000);

  const [parcelQuery, setParcelQuery] = useState("");
  const [debouncedParcelQ, setDebouncedParcelQ] = useState("");
  const [talukFilter, setTalukFilter] = useState("All");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedParcelQ(parcelQuery), 300);
    return () => clearTimeout(timer);
  }, [parcelQuery]);

  const parcelUrl = `/api/parcels?district=${encodeURIComponent(user?.district || "Coimbatore")}&limit=50` + 
    (debouncedParcelQ ? `&q=${encodeURIComponent(debouncedParcelQ)}` : "") +
    (talukFilter !== "All" ? `&taluk=${encodeURIComponent(talukFilter)}` : "");
  const { data: districtParcels } = useData(parcelUrl, 5000);
  
  if (dashboardError) return <Panel title="District Authority Dashboard"><div className="error">Unable to load district dashboard ({dashboardError.status || "network error"}): {dashboardError.message}</div></Panel>;
  if (!d) return <Panel title="District Authority Dashboard">Loading…</Panel>;
  let cards = [["Total Projects", d.total_projects], ["Active Projects", d.active_projects], ["Completed Projects", d.completed_projects], ["Total Parcels", d.total_parcels], ["Affected Families", d.affected_families], ["High/Critical Risk", d.high_risk_projects + d.critical_projects], ["Total Compensation", d.total_compensation], ["Paid Compensation", d.paid_compensation], ["Pending Compensation", d.pending_compensation], ["Legal Disputes", d.legal_disputes], ["Delayed Projects", d.delayed_projects], ["SLA Breaches", d.sla_breaches], ["Pending Field Verification", d.pending_verification], ["Escalated Cases", d.escalated_cases]];
  
  // Filter alerts for this district user
  const myAlerts = (alertsList || []).filter(a => a.assigned_to === user?.email);

  return (
    <>
      {myAlerts.length > 0 && (
        <Panel title={`Notifications (${myAlerts.length})`}>
          {myAlerts.map(a => (
            <div className="notice" key={a.alert_id} style={{ cursor: "pointer", borderLeft: "4px solid #0056b3" }} onClick={() => go({ project_id: a.project_id })}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <b>{a.title || a.type}</b>
                <small>{new Date(a.created_at).toLocaleString()}</small>
              </div>
              <p style={{ margin: "5px 0" }}>{a.message}</p>
              <small>Project: {a.project_id} | Priority: {a.severity}</small>
            </div>
          ))}
        </Panel>
      )}

      {/* District Parcel Search & Register Bar */}
      <Panel title="District Parcel Search & Register">
        <div className="toolbar" style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "14px", flexWrap: "wrap" }}>
          <div style={{ position: "relative", flex: "1 1 280px", minWidth: "220px" }}>
            <input
              placeholder="Search district parcels by Survey No, Parcel ID, Owner, Taluk..."
              value={parcelQuery}
              onChange={e => setParcelQuery(e.target.value)}
              style={{ width: "100%", margin: 0, padding: "8px 32px 8px 12px", boxSizing: "border-box" }}
            />
            {parcelQuery && (
              <button
                type="button"
                onClick={() => { setParcelQuery(""); setDebouncedParcelQ(""); }}
                style={{ position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "14px" }}
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>
          <select
            value={talukFilter}
            onChange={e => setTalukFilter(e.target.value)}
            style={{ margin: 0, padding: "8px 12px" }}
          >
            <option value="All">All Taluks</option>
            {["Sulur", "Kinathukadavu", "Annur", "Perur", "Mettupalayam", "Madukkarai"].map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <span className="project-count-badge">
            District: {user?.district || "Coimbatore"} 🔒
          </span>
          <span className="project-count-badge">
            Showing {districtParcels?.items?.length || 0} of {districtParcels?.total || 0} parcels
          </span>
        </div>
        {districtParcels?.items?.length ? (
          <Table
            rows={districtParcels.items.slice(0, 15)}
            cols={["id", "survey_no", "village", "taluk", "district", "owner_name", "area", "project_id", "acquisition_status"]}
            onClick={go}
          />
        ) : (
          <p>No district parcels found matching your search.</p>
        )}
      </Panel>

      <Panel title="District Project List">
        {projectsError && <div className="error">Unable to load projects ({projectsError.status || "network error"}): {projectsError.message}</div>}
        {!projectsError && !projectList && <p>Loading projects...</p>}
        {projectList && <Table rows={projectList.items || []} cols={["project_id", "project_name", "district", "taluk", "village", "current_stage", "project_status", "progress"]} onClick={go} />}
      </Panel>

      <Panel title="District Authority Dashboard">
        <div className="cards">{cards.map(c => <div className="metric" key={c[0]}><span>{c[0]}</span><b>{c[1] ?? 0}</b></div>)}</div>
        <div style={{ marginTop: 20 }}><b>Payment Completion:</b> <progress value={d.payment_completion || 0} max={100} style={{ width: "100%" }} /> {d.payment_completion || 0}%</div>
      </Panel>
      <div className="grid2">
        <Panel title="Taluk-wise Project Overview"><Table rows={d.taluk_overview || []} cols={["taluk", "projects", "avg_progress"]} /></Panel>
        <Panel title="Priority Actions">{d.priority_actions?.length ? d.priority_actions.map((p, i) => <div className="notice" key={i}><b>{p.task}</b> - Project: {p.project_id}</div>) : <p>No immediate priority actions.</p>}</Panel>
      </div>
      <div className="grid2">
        <Panel title="Compensation Paid Report"><Table rows={d.compensation_paid_report || []} cols={["project_id", "survey_no", "taluk", "owner_reference", "approved_amount", "paid_amount", "status"]} /></Panel>
        <Panel title="Pending Compensation Report"><Table rows={d.compensation_pending_report || []} cols={["project_id", "survey_no", "taluk", "owner_reference", "assessed_amount", "pending_amount", "status"]} /></Panel>
      </div>
      <Panel title="Officer Workload"><div className="cards">{d.officer_workload?.length ? d.officer_workload.map((w, i) => <div className="metric" key={i}><span>{w.assigned_to}</span><b>{w.count} pending</b></div>) : <p>No active assignments.</p>}</div></Panel>
    </>
  );
}

function Dashboard() {
  const { data: d } = useData("/dashboard/", 5000);
  if (!d) return <Panel title="Command Center">Loading…</Panel>;
  return (
    <>
      <Cards d={d} />
      <div className="grid2">
        <Panel title="Priority Actions (Today)">{d.priority_actions?.length ? d.priority_actions.map((p, i) => <div className="notice" key={i}><b>{p.task}</b> - Project: {p.project_id}</div>) : <p>No immediate priority actions.</p>}</Panel>
        <Panel title="Officer Workload">{d.officer_workload?.length ? d.officer_workload.map((w, i) => <div className="metric" key={i}><span>{w.assigned_to}</span><b>{w.count} pending</b></div>) : <p>No active assignments.</p>}</Panel>
      </div>
      <div className="grid2">
        <Panel title="Risk Distribution"><Bars data={d.risk_distribution} label="category" /></Panel>
        <Panel title="Projects by Stage"><Bars data={d.projects_by_stage} label="stage" /></Panel>
      </div>
      <Panel title="Platform posture">
        <div className="banner">DATA → PARCEL → PROJECT → WORKFLOW → EVIDENCE → GIS → RISK → EXPLAINABLE AI → ACTION → ALERT → OUTCOME → TRAINING → MODEL VERSION → AUDIT</div>
      </Panel>
    </>
  );
}

function Bars({ data, label }) {
  return <div>{data?.map(x => <div className="bar" key={x[label]}><span>{x[label]}</span><i style={{ width: `${Math.min(100, (x.count / (Math.max(...data.map(a => a.count), 1))) * 100)}%` }}></i><b>{x.count}</b></div>)}</div>;
}

function Panel({ title, children }) {
  return <section className="panel"><div className="panel-head"><h2>{title}</h2></div>{children}</section>;
}

function Table({ rows, cols, onClick, actions }) {
  if (!rows || rows.length === 0) return <p>No records found.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map(c => <th key={c}>{c.replaceAll("_", " ")}</th>)}{actions && <th>Actions</th>}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id || r.project_id || r.record_id || i} onClick={() => onClick && onClick(r)}>
              {cols.map(c => <td key={c}>{String(r[c] ?? "")}</td>)}
              {actions && <td>{actions(r)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ActionButton({ label, onClick, disabled }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  return (
    <div style={{display: 'inline-block', marginRight: '5px'}}>
      <button disabled={disabled || loading} onClick={async (e) => {
        e.stopPropagation();
        setLoading(true); setError("");
        try { await onClick(e); } catch(ex) { setError(String(ex?.message || ex || "Action failed")); }
        setLoading(false);
      }}>{loading ? "..." : label}</button>
      {error && <span style={{color: "red", fontSize: "10px", marginLeft: "4px"}}>{error}</span>}
    </div>
  );
}

function Projects({ go }) {
  const { data: d, error } = useData("/projects/?limit=500", 5000);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState("");
  const [selectedTaluk, setSelectedTaluk] = useState("");
  const [selectedStage, setSelectedStage] = useState("");

  // Unique taluks dynamically populated from project items
  const talukOptions = useMemo(() => {
    const set = new Set();
    (d?.items || []).forEach(p => {
      const t = String(p.taluk || "").trim();
      if (t) set.add(t);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [d?.items]);

  // Project type options: required types + any other types from data
  const projectTypeOptions = useMemo(() => {
    const requiredTypes = ["Rail", "Road", "Airport", "Industrial", "Urban Development"];
    const set = new Set(requiredTypes);
    (d?.items || []).forEach(p => {
      const t = String(p.project_type || "").trim();
      if (t) set.add(t);
    });
    return Array.from(set);
  }, [d?.items]);

  // Status / Stage filter options
  const stageOptions = [
    "Proposal",
    "SIA / Survey",
    "Approval",
    "Rehabilitation",
    "Closure / Completion"
  ];

  // Real-time filtering across search input and dropdowns
  const filteredProjects = useMemo(() => {
    if (!d?.items) return [];
    return d.items.filter(p => {
      // 1. Search Bar (case-insensitive across Project ID, Name, Taluk)
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const pId = String(p.project_id || "").toLowerCase();
        const pName = String(p.project_name || "").toLowerCase();
        const pTaluk = String(p.taluk || "").toLowerCase();
        if (!pId.includes(q) && !pName.includes(q) && !pTaluk.includes(q)) {
          return false;
        }
      }

      // 2. Project Type Filter
      if (selectedType) {
        const pType = String(p.project_type || "").trim().toLowerCase();
        const targetType = selectedType.trim().toLowerCase();
        if (targetType === "industrial") {
          if (!pType.includes("industrial")) return false;
        } else if (pType !== targetType) {
          return false;
        }
      }

      // 3. Taluk Filter
      if (selectedTaluk) {
        const pTaluk = String(p.taluk || "").trim().toLowerCase();
        if (pTaluk !== selectedTaluk.trim().toLowerCase()) return false;
      }

      // 4. Status / Stage Filter
      if (selectedStage) {
        const targetStage = selectedStage.trim().toLowerCase();
        const currentStage = String(p.current_stage || "").trim().toLowerCase();
        const status = String(p.project_status || "").trim().toLowerCase();

        let matches = false;
        if (targetStage === "sia / survey") {
          matches = currentStage === "sia / survey" || currentStage === "survey";
        } else if (targetStage === "rehabilitation") {
          matches = currentStage === "rehabilitation" || currentStage.includes("rehabilitation");
        } else if (targetStage === "closure / completion") {
          matches = currentStage === "closure / completion" || currentStage === "completed" || status === "completed";
        } else {
          matches = currentStage === targetStage || status === targetStage;
        }
        if (!matches) return false;
      }

      return true;
    });
  }, [d?.items, searchQuery, selectedType, selectedTaluk, selectedStage]);

  const handleResetFilters = () => {
    setSearchQuery("");
    setSelectedType("");
    setSelectedTaluk("");
    setSelectedStage("");
  };

  const isFiltered = Boolean(searchQuery.trim() || selectedType || selectedTaluk || selectedStage);
  const totalCount = d?.items?.length || 0;
  const filteredCount = filteredProjects.length;

  if (error) return <Panel title="Project Register"><div className="error">Unable to load projects ({error.status || "network error"}): {error.message}</div></Panel>;
  if (!d) return <Panel title="Project Register">Loading projects...</Panel>;

  return (
    <Panel title="Project Register">
      {/* Search and Filter Toolbar */}
      <div className="project-toolbar">
        <div className="project-toolbar-filters">
          {/* Search Bar with Clear (✕) Button */}
          <div className="search-input-wrapper">
            <input
              type="text"
              placeholder="Search by Project ID, Name, or Taluk..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              aria-label="Search by Project ID, Name, or Taluk"
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => setSearchQuery("")}
                aria-label="Clear search"
                title="Clear search"
              >
                ✕
              </button>
            )}
          </div>

          {/* Project Type Filter Dropdown */}
          <select
            className="project-filter-select"
            value={selectedType}
            onChange={e => setSelectedType(e.target.value)}
            aria-label="Filter by Project Type"
          >
            <option value="">All Types</option>
            {projectTypeOptions.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {/* Taluk Filter Dropdown (Dynamically Populated) */}
          <select
            className="project-filter-select"
            value={selectedTaluk}
            onChange={e => setSelectedTaluk(e.target.value)}
            aria-label="Filter by Taluk"
          >
            <option value="">All Taluks</option>
            {talukOptions.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          {/* Status / Stage Filter Dropdown */}
          <select
            className="project-filter-select"
            value={selectedStage}
            onChange={e => setSelectedStage(e.target.value)}
            aria-label="Filter by Stage or Status"
          >
            <option value="">All Stages</option>
            {stageOptions.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {/* Reset Filters button if any filter is active */}
          {isFiltered && (
            <button
              type="button"
              className="btn-reset-filters"
              onClick={handleResetFilters}
              title="Reset all filters"
            >
              Reset Filters
            </button>
          )}
        </div>

        {/* Live Count Badge */}
        <div className="project-count-badge" aria-live="polite">
          Showing {filteredCount} of {totalCount} projects
        </div>
      </div>

      {/* Results Table or Clean Empty State */}
      {filteredCount === 0 ? (
        <div className="project-empty-state">
          <div className="empty-title">
            No projects found matching your search.
          </div>
          <p className="empty-subtitle">
            Try adjusting keywords or filters.
          </p>
          <button
            type="button"
            className="btn-reset-filters primary"
            onClick={handleResetFilters}
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <Table
          rows={filteredProjects}
          cols={["project_id", "project_name", "project_type", "district", "taluk", "current_stage", "project_status", "progress"]}
          onClick={go}
        />
      )}
    </Panel>
  );
}

// ProjectAcquisitionMap is imported from ./ProjectAcquisitionMap

function Workflow({ selected, go, user }) {
  const { data: projectDetails, error } = useData(selected ? `/projects/${selected.project_id}` : null, 5000);
  const { data: compensation, error: compensationError } = useData(selected ? `/compensation/project/${selected.project_id}` : null, 5000);
  const canExecute = ["district_authority", "authority", "admin", "acquisition_officer"].includes(user?.role);
  const { data: officers } = useData(canExecute && selected ? "/field/officers" : null);
  const [survey, setSurvey] = useState("");
  const [subdivision, setSubdivision] = useState("");
  const [village, setVillage] = useState("");
  const [taluk, setTaluk] = useState("");
  const [district, setDistrict] = useState("");
  const [searchPath, setSearchPath] = useState(null);
  const [selectedParcel, setSelectedParcel] = useState(null);
  const [assigningParcel, setAssigningParcel] = useState(null);
  const [officer, setOfficer] = useState("");
  const { data: searchResults, error: searchError } = useData(searchPath);

  if (!selected) return <Placeholder title="Workflow" />;
  if (error) return <Panel title="Project Details"><p className="error">Unable to load project details ({error.status || "network error"}): {error.message}</p></Panel>;
  if (!projectDetails) return <Panel title="Project Details"><p>Loading project details...</p></Panel>;
  const lifecycle = [{ internal: "Proposal", label: "Proposal" }, { internal: "SIA / Survey", label: "SIA / Survey" }, { internal: "Notification", label: "Notification" }, { internal: "Legal Dispute / Resolution", label: "Objections" }, { internal: "Approval", label: "Approval" }, { internal: "Award", label: "Award" }, { internal: "Compensation", label: "Compensation" }, { internal: "Possession", label: "Possession" }, { internal: "Rehabilitation", label: "Rehabilitation" }, { internal: "Closure / Completion", label: "Completed" }];
  const normalizedStage = { Survey: "SIA / Survey", "Rehabilitation & Resettlement": "Rehabilitation" }[projectDetails.current_stage] || projectDetails.current_stage;
  const currentIndex = lifecycle.findIndex(s => s.internal === normalizedStage);
  const nextStage = currentIndex >= 0 ? lifecycle[currentIndex + 1] : null;
  const transition = async () => {
    if (!nextStage || !window.confirm(`Move ${projectDetails.project_id} to ${nextStage.label}?`)) return;
    await api(`/projects/${encodeURIComponent(projectDetails.project_id)}/workflow/transition`, { method: "POST", body: JSON.stringify({ next_stage: nextStage.internal }) });
  };
  const search = e => {
    e.preventDefault();
    const parts = survey.trim().split("/");
    const surveyNo = parts[0] || "";
    const subdivisionValue = parts.length > 1 ? parts.slice(1).join("/") : subdivision.trim();
    const params = new URLSearchParams({ limit: "100" });
    if (surveyNo) params.set("survey_no", surveyNo);
    if (subdivisionValue) params.set("subdivision", subdivisionValue);
    if (village.trim()) params.set("village", village.trim());
    if (taluk.trim()) params.set("taluk", taluk.trim());
    if (district.trim()) params.set("district", district.trim());
    setSearchPath(`/land-records/?${params.toString()}`);
  };
  const linkSelected = async () => {
    if (!selectedParcel) return;
    await api(`/projects/${encodeURIComponent(projectDetails.project_id)}/parcels/${selectedParcel.id}`, { method: "POST" });
    setSelectedParcel(null); setSearchPath(null);
  };
  const assign = async parcel => {
    if (!officer) throw Error("Select a field officer");
    await api("/field/assign", { method: "POST", body: JSON.stringify({ project_id: projectDetails.project_id, parcel_id: parcel.id, officer_email: officer }) });
    setAssigningParcel(null); setOfficer("");
  };
  const parcelActions = canExecute ? p => assigningParcel === p.id ? <><select value={officer} onChange={e => setOfficer(e.target.value)}><option value="">Select field officer</option>{(officers || []).map(o => <option key={o.email} value={o.email}>{o.email}</option>)}</select><ActionButton label="Assign" onClick={() => assign(p)} /></> : <><button type="button" onClick={() => go({ parcel_id: p.id, project_id: p.project_id })}>View Parcel</button><button type="button" onClick={() => setAssigningParcel(p.id)}>Assign Field Officer</button></> : undefined;
  return (
    <>
      <Panel title={`Project Details: ${projectDetails.project_id} - ${projectDetails.project_name}`}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "10px", marginBottom: "20px", padding: "15px", background: "#f8f9fa", borderRadius: "8px" }}>
          <div><b>Project ID:</b> {projectDetails.project_id}</div><div><b>Project Name:</b> {projectDetails.project_name}</div>
          <div><b>District:</b> {projectDetails.district || "N/A"}</div><div><b>Taluk:</b> {projectDetails.taluk || "N/A"}</div>
          <div><b>Village:</b> {projectDetails.village || "N/A"}</div><div><b>Stage:</b> {projectDetails.current_stage}</div>
          <div><b>Status:</b> {projectDetails.project_status || "N/A"}</div><div><b>Progress:</b> {projectDetails.progress ?? 0}%</div>
          <div><b>Linked Land Area:</b> {(projectDetails.linked_land_area ?? 0).toFixed(2)} acres</div><div><b>Target Date:</b> {projectDetails.planned_completion_date || "N/A"}</div>
          <div><b>Risk:</b> {projectDetails.project_risk || "N/A"}</div>
          <div><b>Linked Parcels:</b> {projectDetails.linked_parcel_count ?? 0}</div><div><b>Verified / Pending:</b> {projectDetails.verified_parcel_count ?? 0} / {projectDetails.pending_verification_count ?? 0}</div>
        </div>
        <h4>Acquisition Workflow</h4>
        <div className="timeline">{lifecycle.map((stage, index) => { const milestone=projectDetails.workflow?.find(m => m.stage===stage.internal); const status=index<currentIndex ? "Completed" : index===currentIndex ? "Current" : "Pending"; return <div className="stage" key={stage.internal}><b>{stage.label}</b><span>{status}</span><small>{milestone?.actual_date ? `Completed: ${milestone.actual_date}` : milestone?.planned_date ? `Started: ${milestone.planned_date}` : "No date recorded"}{milestone?.responsible_officer ? ` · ${milestone.responsible_officer}` : ""}</small></div>; })}</div>
        {projectDetails.pending_verification_count > 0 && <div className="notice">{projectDetails.pending_verification_count} linked parcel(s) are still pending field verification.</div>}
        {canExecute && nextStage && <ActionButton label={`Move to ${nextStage.label}`} onClick={transition} />}
      </Panel>
      <ProjectAcquisitionMap projectId={projectDetails.project_id} />
      {canExecute && <Panel title="Link Existing Parcel">
        <form className="toolbar" onSubmit={search}><input placeholder="Survey / Survey-Subdivision (e.g. 00029/4A)" value={survey} onChange={e => setSurvey(e.target.value)} /><input placeholder="Subdivision" value={subdivision} onChange={e => setSubdivision(e.target.value)} /><input placeholder="Village" value={village} onChange={e => setVillage(e.target.value)} /><input placeholder="Taluk" value={taluk} onChange={e => setTaluk(e.target.value)} /><input placeholder="District" value={district} onChange={e => setDistrict(e.target.value)} /><button type="submit">Search Parcels</button></form>
        {searchError && <div className="error">Unable to search parcels: {searchError.message}</div>}
        {searchResults && <><Table rows={searchResults.items || []} cols={["id", "survey_no", "subdivision", "village", "taluk", "district", "area", "acquisition_status", "risk_category", "risk_score"]} onClick={setSelectedParcel} /><div>{selectedParcel && <><span>Selected: Parcel {selectedParcel.id} · {selectedParcel.survey_no}</span> <button type="button" onClick={linkSelected}>Link Selected Parcel</button></>}</div></>}
        {searchResults && !(searchResults.items || []).length && <div className="empty">No parcels found for this search.</div>}
      </Panel>}
      <Panel title="Linked Parcels"><Table rows={projectDetails.parcels || []} cols={["id", "survey_no", "subdivision", "village", "taluk", "area", "risk_category", "acquisition_status", "assignment_status"]} onClick={p => go({ parcel_id: p.id, project_id: p.project_id })} actions={parcelActions} /></Panel>
      <Panel title="Pending Compensation">
        {compensationError && <div className="error">Unable to load compensation ({compensationError.status || "network error"}): {compensationError.message}</div>}
        {!compensationError && !compensation && <p>Loading compensation...</p>}
        {compensation && <Table rows={compensation} cols={["parcel_id", "survey_no", "village", "eligible_amount", "paid_amount", "pending_amount", "status"]} actions={r => <ActionButton label="Pay" onClick={() => api(`/compensation/project/${projectDetails.project_id}/parcel/${r.parcel_id}/pay`, { method: "POST" })} />} />}
        {compensation && !compensation.length && <div className="empty">No pending compensation records.</div>}
      </Panel>
    </>
  );
}

function Parcels({ go }) {
  const [q, setQ] = useState("");
  const { data: rows } = useData("/land-records/?limit=100&survey_no=" + encodeURIComponent(q));
  return (
    <Panel title="Parcel Register">
      <div className="toolbar"><input placeholder="Search survey number" value={q} onChange={e => setQ(e.target.value)} /></div>
      <Table rows={rows?.items || []} cols={["record_id", "survey_no", "village", "taluk", "district", "area", "classification", "project_id", "acquisition_status", "risk_category"]} onClick={go} />
    </Panel>
  );
}

function GIS() {
  const { data: g } = useData("/gis/parcels?limit=500");
  const [q, setQ] = useState("");
  let fs = g?.features || [], filtered = fs.filter(f => !q || String(f.properties?.survey_no || "").toLowerCase().includes(q.toLowerCase()));
  return (
    <Panel title="GIS Parcel Intelligence">
      <div className="notice">SYNTHETIC DEMO GEOMETRY — points only. Not official cadastral boundaries.</div>
      <input placeholder="Search Survey Number" value={q} onChange={e => setQ(e.target.value)} />
      <div className="map">
        <MapContainer center={[11.0168, 76.9558]} zoom={10} scrollWheelZoom>
          <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {filtered.map((f, i) => {
            let c = f.geometry?.coordinates || [76.9558, 11.0168];
            return (
              <Marker key={i} position={[c[1], c[0]]}>
                <Popup><b>Survey {f.properties?.survey_no}</b><br />{f.properties?.village}<br />Project: {f.properties?.project_id}</Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>
      <small>{filtered.length} demo GIS points</small>
    </Panel>
  );
}

function ML() {
  const { data: dashboardData } = useData("/ml/dashboard");
  const { data: v } = useData("/ml/versions");
  
  if (!dashboardData) return <Panel title="ML Monitoring">Loading...</Panel>;
  
  return (
    <>
      <Panel title="ML Model Overview">
        <div className="cards">
          <div className="metric"><span>Model Version</span><b>{dashboardData.model_version}</b></div>
          <div className="metric"><span>Status</span><b>{dashboardData.model_status}</b></div>
          <div className="metric"><span>Accuracy</span><b>{dashboardData.accuracy}%</b></div>
          <div className="metric"><span>Predictions Today</span><b>{dashboardData.predictions_today}</b></div>
          <div className="metric"><span>Avg Confidence</span><b>{dashboardData.average_confidence}%</b></div>
          <div className="metric"><span>Data Drift</span><b>{dashboardData.data_drift}</b></div>
        </div>
      </Panel>
      <div className="grid2">
        <Panel title="Recent Risk Predictions">
          <Table rows={dashboardData.recent_predictions || []} cols={["project_id", "survey_no", "risk", "confidence"]} />
        </Panel>
        <Panel title="AI Alerts">
          {dashboardData.alerts?.map((a, i) => <div className="notice" key={i}><b>{a.type}</b>: {a.message} <span style={{float:'right', color: 'red'}}>{a.severity}</span></div>)}
        </Panel>
      </div>
      <Panel title="Model Version History">
        <Table rows={v || []} cols={["version", "accuracy", "status", "created_at"]} />
      </Panel>
    </>
  );
}

function SLA({ selected }) {
  const { data: d } = useData("/sla/timeline/" + (selected?.project_id || "none"), 5000);
  if (!selected?.project_id) return <Placeholder title="SLA & Timeline" />;
  return (
    <Panel title={`SLA & Timeline · ${selected.project_id}`}>
      <div className="timeline">
        {(d || []).map(m => (
          <div className="stage" key={m.stage}>
            <b>{m.stage}</b><span>{m.status}</span>
            <small>Started: {m.planned_date || 'N/A'} · Actual: {m.actual_date || 'N/A'}<br />Delay: {m.delay_days || 0} days</small>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function AlertTable({ rows, columns, onOpen, emptyMessage, actionLabel = "View Details" }) {
  if (!rows.length) return <div className="empty">{emptyMessage}</div>;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}<th>Action</th></tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={row.parcel_id || row.project_id || index}>
            {columns.map(c => <td key={c.key}>{c.render ? c.render(row) : String(row[c.key] ?? "N/A")}</td>)}
            <td><button type="button" onClick={() => onOpen(row)}>{actionLabel}</button></td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function RefreshButton() {
  return <button type="button" onClick={() => EventBus.dispatch()}>Refresh</button>;
}

function DataPanel({ title, data, error, children, empty = false }) {
  if (error) return <Panel title={title}><div className="error">Unable to load {title} ({error.status || "network error"}): {error.message} <RefreshButton /></div></Panel>;
  if (!data) return <Panel title={title}><p>Loading {title.toLowerCase()}...</p></Panel>;
  if (empty) return <Panel title={title}><div className="empty">No {title.toLowerCase()} found.</div><RefreshButton /></Panel>;
  return children;
}

function RiskIntelligence({ go }) {
  const { data, error } = useData("/analytics/operations", 5000);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("ALL");
  const [explanationParcel, setExplanationParcel] = useState(null);
  const { data: explanation, error: explanationError } = useData(explanationParcel ? `/ml/parcels/${explanationParcel.parcel_id}/explanation` : null);
  if (error || !data) return <DataPanel title="Risk Intelligence" data={data} error={error} />;
  const risk = data.risk;
  const matches = row => `${row.parcel_id || ""} ${row.survey_no || ""} ${row.project_id || ""} ${row.project_name || ""} ${row.village || ""} ${row.taluk || ""} ${row.district || ""}`.toLowerCase().includes(query.toLowerCase());
  const rows = risk.top_parcels.filter(r => (category === "ALL" || r.risk_category === category) && matches(r));
  const open = row => go({ project_id: row.project_id, parcel_id: row.parcel_id, record_id: row.record_id, survey_no: row.survey_no });
  return (
    <>
      <Panel title="Risk Intelligence">
        <div className="toolbar"><input aria-label="Search risk records" placeholder="Search parcel, survey, project, village..." value={query} onChange={e => setQuery(e.target.value)} /><select value={category} onChange={e => setCategory(e.target.value)}><option value="ALL">All categories</option><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select><RefreshButton /></div>
        {risk.prediction_count === 0 && <div className="notice">No risk predictions available. Stored parcel risk classifications are marked as prototype data; SHAP is generated on demand from the active model.</div>}
        {risk.synthetic_note && <div className="notice">{risk.synthetic_note}</div>}
        <div className="cards">
          <div className="metric"><span>Total Risk Parcels</span><b>{risk.total}</b></div>
          {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(level => <div className="metric" key={level}><span>{level} RISK</span><b>{data.parcels.risk_distribution.find(x => x.category === level)?.count || 0}</b></div>)}
          <div className="metric"><span>Average Risk Score</span><b>{risk.average_score ?? "N/A"}</b></div>
        </div>
      </Panel>
      <div className="grid2">
        <Panel title="Risk Distribution">{risk.prediction_count ? <Table rows={risk.prediction_distribution} cols={["category", "count"]} /> : <div className="empty">No risk predictions available.</div>}</Panel>
        <Panel title="Project-wise Risk"><Table rows={risk.project_wise.slice(0, 20)} cols={["project_id", "project_name", "parcels", "high_risk", "average_risk_score"]} onClick={r => go({ project_id: r.project_id })} /></Panel>
      </div>
      <Panel title="Village-wise Risk"><Table rows={risk.village_wise.slice(0, 30)} cols={["village", "taluk", "district", "parcels", "high_risk", "average_risk_score"]} /></Panel>
      <Panel title="Top High-risk Parcels">
        <AlertTable rows={rows} columns={[{key:"parcel_id",label:"Parcel ID"},{key:"survey_no",label:"Survey Number"},{key:"project_id",label:"Project"},{key:"project_name",label:"Project Name"},{key:"village",label:"Village"},{key:"taluk",label:"Taluk"},{key:"district",label:"District"},{key:"risk_category",label:"Risk Category"},{key:"risk_score",label:"Risk Score",render:r=>r.risk_score ?? "N/A"},{key:"assessed_at",label:"Assessed"}]} onOpen={row => setExplanationParcel(row)} actionLabel="View Explanation" emptyMessage="No risk records available." />
      </Panel>
      {explanationParcel && <RiskExplanation parcel={explanationParcel} explanation={explanation} error={explanationError} onClose={() => setExplanationParcel(null)} />}
    </>
  );
}

function RiskExplanation({ parcel, explanation, error, onClose }) {
  return <Panel title="PARCEL RISK EXPLANATION">
    <button type="button" onClick={onClose}>Close Explanation</button>
    <div className="status-card"><p><b>Survey Number:</b> {parcel.survey_no}</p><p><b>Village / Taluk:</b> {parcel.village} / {parcel.taluk}</p><p><b>Project:</b> {parcel.project_name || parcel.project_id}</p>{error ? <div className="error">Unable to load risk explanation ({error.status || "network error"}): {error.message}</div> : !explanation ? <p>Loading risk explanation...</p> : <><p><b>Model Risk Score:</b> {explanation.risk_score}</p><p><b>Model Risk Category:</b> {explanation.risk_category}</p><p><b>Stored Parcel Classification:</b> {explanation.stored_risk_category || "N/A"}</p><p><b>Model Confidence:</b> {(explanation.confidence * 100).toFixed(2)}%</p><p><b>Explainer:</b> {explanation.explanation_method} ({explanation.output_space})</p><p><b>Base Prediction:</b> {explanation.base_value} <b>Final Prediction:</b> {explanation.final_value}</p><h3>WHY DOES THE MODEL CLASSIFY THIS PARCEL THIS WAY?</h3><div>{explanation.features.slice(0,8).map(f => <div key={f.name + f.display_name} style={{display:"grid",gridTemplateColumns:"2fr 1fr 2fr",gap:"8px",alignItems:"center",margin:"6px 0"}}><span>{f.display_name}</span><span>{String(f.value ?? "N/A")}</span><span style={{color:f.shap_value >= 0 ? "#b42318" : "#16704a"}}>{f.shap_value >= 0 ? "+" : ""}{f.shap_value}</span><i style={{height:"8px",width:`${Math.min(100,Math.abs(f.shap_value)*400)}%`,background:f.shap_value >= 0 ? "#d92d20" : "#12b76a",display:"block"}} /></div>)}</div><h3>Recommended operational action based on risk factors</h3><ul>{explanation.recommended_actions.map(action => <li key={action}>{action}</li>)}</ul></>}</div>
  </Panel>;
}

function AlertsPage({ go }) {
  const { data, error } = useData("/alerts/operations", 5000);
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  if (error || !data) return <DataPanel title="Alerts" data={data} error={error} />;
  const visible = data.filter(a => (filter === "All" || (filter === "Unread" ? a.read_status === "Unread" : a.category === filter)) && `${a.type} ${a.message} ${a.project_id || ""} ${a.survey_no || ""} ${a.district || ""}`.toLowerCase().includes(query.toLowerCase()));
  const open = row => { if (row.parcel_id) go({ project_id: row.project_id, parcel_id: row.parcel_id, record_id: row.record_id, survey_no: row.survey_no }); else if (row.project_id) go({ project_id: row.project_id }); };
  return <Panel title="Operational Alerts">
    <div className="toolbar"><input aria-label="Search alerts" placeholder="Search alert, project, parcel, district..." value={query} onChange={e => setQuery(e.target.value)} /><select value={filter} onChange={e => setFilter(e.target.value)}>{["All", "Unread", "Risk", "SLA", "Project", "Grievance", "Verification"].map(x => <option key={x}>{x}</option>)}</select><RefreshButton /></div>
    <AlertTable rows={visible} columns={[{key:"type",label:"Alert Type"},{key:"category",label:"Category"},{key:"message",label:"Message"},{key:"project_id",label:"Project"},{key:"survey_no",label:"Parcel / Survey",render:r=>r.parcel_id ? `${r.parcel_id} / ${r.survey_no || "N/A"}` : "N/A"},{key:"district",label:"District"},{key:"created_at",label:"Created"},{key:"severity",label:"Severity"},{key:"read_status",label:"Read Status"},{key:"assigned_to",label:"Relevant User / Role"}]} onOpen={open} emptyMessage="No alerts found." />
    {visible.filter(a => a.status === "Open").map(a => <ActionButton key={a.alert_id} label={`Acknowledge ${a.alert_id}`} onClick={() => api(`/alerts/${a.alert_id}`, { method: "PATCH", body: JSON.stringify({ status: "Acknowledged" }) }).then(() => EventBus.dispatch())} />)}
  </Panel>;
}

function AnalyticsPage({ go }) {
  const { data, error } = useData("/analytics/operations", 5000);
  if (error || !data) return <DataPanel title="Analytics" data={data} error={error} />;
  const kpis = [["Total Projects", data.projects.total], ["Active Projects", data.projects.active], ["Delayed Projects", data.projects.delayed], ["Completed Projects", data.projects.completed], ["Total Parcels", data.parcels.total], ["Affected Parcels", data.parcels.affected], ["Verified Parcels", data.parcels.verified], ["Pending Verification", data.parcels.pending_verification], ["SLA Due Soon", data.sla.due_soon], ["SLA Breached", data.sla.breached], ["Compensation Pending", data.acquisition.compensation_pending], ["Open Grievances", (data.grievances.by_status.find(x => x.status === "Open") || {}).count || 0]];
  return <>
    <Panel title="Operational Analytics"><div className="toolbar"><RefreshButton /></div><div className="cards">{kpis.map(k => <div className="metric" key={k[0]}><span>{k[0]}</span><b>{k[1]}</b></div>)}</div></Panel>
    <div className="grid2"><Panel title="Projects by Stage"><Table rows={data.projects.by_stage} cols={["stage", "count"]} /></Panel><Panel title="Projects by District"><Table rows={data.projects.by_district} cols={["district", "count"]} /></Panel></div>
    <Panel title="Project Risk Detail"><AlertTable rows={data.risk.project_wise.slice(0, 30)} columns={[{key:"project_id",label:"Project ID"},{key:"project_name",label:"Project Name"},{key:"parcels",label:"Parcels"},{key:"high_risk",label:"High / Critical"},{key:"average_risk_score",label:"Average Risk Score"}]} onOpen={r => go({ project_id: r.project_id })} emptyMessage="No project analytics available." /></Panel>
    <div className="grid2"><Panel title="Parcel Risk Distribution"><Table rows={data.parcels.risk_distribution} cols={["category", "count", "average_score"]} /></Panel><Panel title="Acquisition Stage Distribution"><Table rows={data.acquisition.by_stage} cols={["stage", "count"]} /></Panel></div>
    <div className="grid2"><Panel title="Compensation / Possession"><Table rows={[{status:"Pending",count:data.acquisition.compensation_pending},{status:"Paid",count:data.acquisition.compensation_completed},...(data.acquisition.possession || [])]} cols={["status", "count"]} /></Panel><Panel title="Rehabilitation / R&R"><Table rows={data.acquisition.rehabilitation} cols={["status", "count"]} /></Panel></div>
    <div className="grid2"><Panel title="SLA Analytics"><Table rows={[{status:"Due Soon",count:data.sla.due_soon},{status:"Breached",count:data.sla.breached},{status:"Average Delay",count:data.sla.average_delay},{status:"Bottlenecks",count:data.sla.bottlenecks}]} cols={["status", "count"]} /></Panel><Panel title="Grievances"><Table rows={data.grievances.by_status.length ? data.grievances.by_status : [{status:"Total",count:data.grievances.total}]} cols={["status", "count"]} /></Panel></div>
  </>;
}

function Bottlenecks({ go }) {
  const { data, error } = useData("/sla/operations", 5000);
  const [query, setQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState("ALL");

  if (error) return <Panel title="Operational Bottlenecks"><div className="error">Unable to load bottleneck operations ({error.status || "network error"}): {error.message}</div></Panel>;
  if (!data) return <Panel title="Operational Bottlenecks"><p>Loading operational records...</p></Panel>;

  const matches = row => {
    const text = `${row.project_id || ""} ${row.project_name || ""} ${row.district || ""} ${row.stage || row.current_stage || ""} ${row.survey_no || ""} ${row.village || ""}`.toLowerCase();
    return text.includes(query.toLowerCase());
  };
  const bottlenecks = data.process_bottlenecks.filter(matches);
  const dueSoon = data.sla_due_soon.filter(matches);
  const breached = data.sla_breached.filter(matches);
  const risks = data.risk_alerts.filter(r => (riskFilter === "ALL" || r.risk_category === riskFilter) && matches(r));
  const openProject = row => go({ project_id: row.project_id, parcel_id: row.parcel_id, record_id: row.record_id, survey_no: row.survey_no });
  const projectColumns = [
    { key: "project_id", label: "Project ID" }, { key: "project_name", label: "Project Name" },
    { key: "district", label: "District" }, { key: "current_stage", label: "Current Stage" },
    { key: "progress", label: "Progress", render: r => `${r.progress ?? 0}%` },
    { key: "days_at_stage", label: "Days at Stage" }, { key: "project_status", label: "Status" },
    { key: "responsible_officer", label: "Responsible Officer" }, { key: "reason", label: "Reason" },
  ];
  const slaColumns = [
    { key: "project_id", label: "Project ID" }, { key: "project_name", label: "Project Name" },
    { key: "current_stage", label: "Current Stage" }, { key: "due_date", label: "Due Date" },
    { key: "days_remaining", label: "Days Remaining", render: r => r.sla_status === "SLA Breached" ? "-" : r.days_remaining },
    { key: "days_overdue", label: "Days Overdue", render: r => r.sla_status === "SLA Breached" ? r.days_overdue || r.delay_days : "-" },
    { key: "responsible_officer", label: "Responsible Officer" }, { key: "reason", label: "Reason" },
  ];
  const riskColumns = [
    { key: "parcel_id", label: "Parcel ID" }, { key: "survey_no", label: "Survey Number" },
    { key: "village", label: "Village" }, { key: "project_id", label: "Project" },
    { key: "risk_category", label: "Risk Category" }, { key: "risk_score", label: "Risk Score", render: r => r.risk_score ?? "N/A" },
    { key: "current_stage", label: "Current Stage" }, { key: "responsible_officer", label: "Responsible Officer" },
  ];

  return (
    <>
      <Panel title="Bottleneck Operations">
        <div className="toolbar">
          <input aria-label="Filter operational alerts" placeholder="Filter project, district, stage, survey..." value={query} onChange={e => setQuery(e.target.value)} />
          <select aria-label="Filter risk alerts" value={riskFilter} onChange={e => setRiskFilter(e.target.value)}>
            <option value="ALL">All risk alerts</option><option value="HIGH">High risk</option><option value="CRITICAL">Critical risk</option>
          </select>
        </div>
        <div className="cards">
          <div className="metric"><span>EPO / PROCESS BOTTLENECKS</span><b>{bottlenecks.length}</b></div>
          <div className="metric"><span>SLA DUE SOON</span><b>{dueSoon.length}</b></div>
          <div className="metric"><span>SLA BREACHED</span><b>{breached.length}</b></div>
          <div className="metric"><span>HIGH RISK</span><b>{risks.filter(r => r.risk_category === "HIGH").length}</b></div>
          <div className="metric"><span>CRITICAL RISK</span><b>{risks.filter(r => r.risk_category === "CRITICAL").length}</b></div>
        </div>
      </Panel>
      <Panel title="EPO / PROCESS BOTTLENECKS">
        <AlertTable rows={bottlenecks} columns={projectColumns} onOpen={openProject} emptyMessage="No active process bottlenecks match the current filter." />
      </Panel>
      <Panel title="SLA DUE SOON">
        <AlertTable rows={dueSoon} columns={slaColumns} onOpen={openProject} emptyMessage="No active milestone is due within 7 days." />
      </Panel>
      <Panel title="SLA BREACHED">
        <AlertTable rows={breached} columns={slaColumns} onOpen={openProject} emptyMessage="No active milestone is past its due date or has a recorded delay." />
      </Panel>
      <Panel title="HIGH RISK / CRITICAL RISK">
        <div className="notice">{data.risk_data_note}</div>
        <AlertTable rows={risks} columns={riskColumns} onOpen={openProject} emptyMessage="No stored high or critical parcel risk alerts match the current filter." />
      </Panel>
    </>
  );
}

function Reports() {
  const { data: d } = useData("/reports/");
  if (!d) return <Panel title="MIS Reports">Loading...</Panel>;
  return (
    <>
      <Cards d={{ total_projects: d.summary.total_projects, active_projects: d.summary.active_projects, completed_projects: d.summary.completed_projects, delayed_projects: d.summary.delayed_cases, pending_compensation: d.summary.total_pending_compensation }} />
      <Panel title="Project Progress Report">
        <Table rows={d.project_wise || []} cols={["project_id", "project_name", "current_stage", "progress"]} />
      </Panel>
    </>
  );
}

function FieldVerification({ go }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(searchTerm), 300);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const queryUrl = `/api/field-verification?q=${encodeURIComponent(debouncedQ)}&status=${encodeURIComponent(statusFilter)}`;
  const { data: d, error } = useData(queryUrl, 5000);

  if (error) return <Panel title="Field Verification Worklist"><div className="error">Unable to load field assignments ({error.status || "network error"}): {error.message} <RefreshButton /></div></Panel>;
  if (!d) return <Panel title="Field Verification Worklist"><p>Loading field assignments...</p></Panel>;

  return (
    <Panel title="Field Verification Worklist">
      <div className="toolbar" style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "14px", flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: "1 1 280px", minWidth: "220px" }}>
          <input
            placeholder="Search assigned parcels by Survey No, Parcel ID, Village, Taluk..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{ width: "100%", margin: 0, padding: "8px 32px 8px 12px", boxSizing: "border-box" }}
          />
          {searchTerm && (
            <button
              type="button"
              onClick={() => { setSearchTerm(""); setDebouncedQ(""); }}
              style={{ position: "absolute", right: "8px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "14px" }}
              title="Clear search"
            >
              ✕
            </button>
          )}
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ margin: 0, padding: "8px 12px", minWidth: "150px" }}
        >
          <option value="All">All Statuses</option>
          <option value="Pending Verification">Pending Verification</option>
          <option value="Verified">Verified</option>
        </select>
        <span className="project-count-badge">
          Showing {d.length} parcels
        </span>
      </div>

      {d.length === 0 ? (
        <div style={{ padding: "30px 20px", textAlign: "center", background: "#f8fafc", borderRadius: "8px", border: "1px dashed #cbd5e1" }}>
          No field assignments found matching your search.
          <br />
          <button
            type="button"
            onClick={() => { setSearchTerm(""); setDebouncedQ(""); setStatusFilter("All"); }}
            style={{ marginTop: "10px", padding: "6px 14px", background: "#0f6c70", color: "#fff", border: "none", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600" }}
          >
            Reset Search
          </button>
        </div>
      ) : (
        <Table rows={d} cols={["assignment_id", "parcel_id", "survey_no", "subdivision", "village", "taluk", "project_id", "assignment_status", "assigned_at"]} actions={(r) => (
          <div style={{display: "flex", gap: "5px"}}>
            {r.assignment_status !== "Verified" ? 
              <ActionButton label="Mark Verified" onClick={async () => { await api(`/field/assignments/${r.assignment_id}/verify`, { method: "POST", body: JSON.stringify({ remarks: "Verified OK" }) }); }} /> 
            : <span style={{color: "green", marginRight: "10px"}}>Verified</span>}
            <button type="button" onClick={() => go({ project_id: r.project_id, parcel_id: r.parcel_id })}>Upload / OCR</button>
          </div>
        )}/>
      )}
    </Panel>
  );
}

function Grievances({ user }) {
  const { data: all_grievances } = useData("/grievances/all"); // We will create this endpoint
  const [form, setForm] = useState({ parcel_id: "", project_id: "", type: "Compensation", description: "" });
  
  return (
    <>
      {user.role === "citizen" && (
        <Panel title="Submit Grievance">
          <div className="form">
            <label>Parcel ID <input value={form.parcel_id} onChange={e => setForm({...form, parcel_id: e.target.value})} /></label>
            <label>Project ID <input value={form.project_id} onChange={e => setForm({...form, project_id: e.target.value})} /></label>
            <label>Type 
              <select value={form.type} onChange={e => setForm({...form, type: e.target.value})}>
                <option>Compensation</option><option>Ownership</option><option>Boundary</option><option>Survey</option>
              </select>
            </label>
            <label>Description <input value={form.description} onChange={e => setForm({...form, description: e.target.value})} /></label>
          </div>
          <ActionButton label="Submit Grievance" onClick={() => {
            if (!form.parcel_id || !form.project_id) throw Error("Fill required fields");
            return api("/grievances/", { method: "POST", body: JSON.stringify({...form, submitted_by: user.email}) })
          }} />
        </Panel>
      )}
      
      <Panel title="Grievance Management">
        <Table rows={all_grievances || []} cols={["id", "parcel_id", "project_id", "submitted_by", "type", "status", "created_at"]} actions={(r) => (
          (user.role === "district_authority" && r.status !== "Resolved") ? 
          <ActionButton label="Resolve" onClick={() => api(`/grievances/${r.id}/resolve`, { method: "POST", body: JSON.stringify({ resolution: "Resolved by officer" }) })} /> 
          : null
        )}/>
      </Panel>
    </>
  );
}

function CitizenDash({ lang, user }) {
  const [q, setQ] = useState("");
  const { data: searchResults, error } = useData(q ? "/land-records/?survey_no=" + encodeURIComponent(q) : null);
  const { data: compensation, error: compensationError } = useData("/compensation/mine", 5000);
  const [selectedParcel, setSelectedParcel] = useState(null);
  const t = (en, ta) => lang === "ta" ? ta : en;

  return (
    <>
    <Panel title={t("Citizen View", "குடிமக்கள் பார்வை")}>
      <p>{t("Public-safe lookup. Internal risk, audit and private owner details are excluded.", "பொது பாதுகாப்பான பார்வை. உள் இடர் மற்றும் தணிக்கை தகவல்கள் தவிர்க்கப்பட்டுள்ளன.")}</p>
      <div className="toolbar">
        <input placeholder={t("Search by Survey Number (e.g. 00001/1A)", "சர்வே எண்")} value={q} onChange={x => { setQ(x.target.value); setSelectedParcel(null); }} />
      </div>
      {error && <div className="error">{error.message}</div>}
      
      {!selectedParcel && searchResults?.items?.length > 0 && (
        <div style={{marginTop: 15}}>
          <p>Found {searchResults.items.length} parcel(s):</p>
          <Table rows={searchResults.items} cols={["survey_no", "village", "taluk", "district", "project_id"]} onClick={setSelectedParcel} />
        </div>
      )}
      
      {q && searchResults?.items?.length === 0 && <div className="error">{t("No parcel found for Survey Number: ", "காணவில்லை: ")} {q}</div>}

      {selectedParcel && (
        <div className="status-card" style={{marginTop: 20}}>
          <h3>{t("My Project", "என் திட்டம்")}: {selectedParcel.project_id}</h3>
          <p>{t("Survey Number", "சர்வே எண்")}: {selectedParcel.survey_no} · {selectedParcel.village}, {selectedParcel.district}</p>
          <p>{t("Total Land Area", "மொத்த நிலப்பரப்பு")}: {selectedParcel.area}</p>
          <p>{t("Acquisition Status", "கையகப்படுத்தல் நிலை")}: <b>{selectedParcel.acquisition_status}</b></p>
          
          <hr />
          <h3>{t("How My Land Is Affected", "என் நிலம் எப்படி பாதிக்கப்படுகிறது")}</h3>
          <div style={{ background: "#f5f5f5", padding: "10px", borderRadius: "8px", marginBottom: "10px" }}>
            <p>{t(`This project affects ${selectedParcel.area} acres of your land.`, `இந்தத் திட்டம் உங்கள் நிலத்தின் ${selectedParcel.area} ஏக்கர் பகுதியை பாதிக்கிறது.`)}</p>
            <p>Stage: <b>{selectedParcel.acquisition_status}</b></p>
          </div>
          <div className="map">
            <MapContainer center={[11.0168, 76.9558]} zoom={12} scrollWheelZoom={false}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Circle center={[11.0168, 76.9558]} radius={500} color="red" fillColor="#f03" fillOpacity={0.2}>
                <Popup><b>Project Alignment</b><br/>{selectedParcel.project_id}</Popup>
              </Circle>
              <Marker position={[11.0168, 76.9558]}><Popup><b>{t("Your Land", "உங்கள் நிலம்")}</b><br />{selectedParcel.survey_no}</Popup></Marker>
              <Marker position={[11.02, 76.96]} opacity={0.5}><Popup>Neighboring Affected Parcel</Popup></Marker>
            </MapContainer>
          </div>
          <div style={{marginTop: 15}}>
             <button onClick={() => setSelectedParcel(null)}>Close / Search Again</button>
          </div>
        </div>
      )}
    </Panel>
    <Panel title="My Compensation">
      {compensationError && <div className="error">Unable to load compensation ({compensationError.status || "network error"}): {compensationError.message}</div>}
      {!compensationError && !compensation && <p>Loading compensation...</p>}
      {compensation && <Table rows={compensation} cols={["project_id", "parcel_id", "survey_no", "eligible_amount", "paid_amount", "pending_amount", "status", "payment_date"]} />}
      {compensation && !compensation.length && <div className="empty">No compensation records available.</div>}
    </Panel>
    </>
  );
}

function ParcelDetails({ selected }) {
  const { data, error } = useData(selected?.parcel_id ? `/land-records/${selected.parcel_id}` : null);
  if (error) return <Panel title="Parcel Details"><div className="error">Unable to load parcel details ({error.status || "network error"}): {error.message}</div></Panel>;
  if (!data) return <Panel title="Parcel Details"><p>Loading parcel details...</p></Panel>;
  return <Panel title={`Parcel Details · ${data.survey_no}`}><div className="status-card"><p><b>Parcel ID:</b> {data.id}</p><p><b>Record ID:</b> {data.record_id}</p><p><b>Project:</b> {data.project_id}</p><p><b>Village / Taluk / District:</b> {data.village} / {data.taluk} / {data.district}</p><p><b>Risk:</b> {data.risk_category || "N/A"} · Score: {data.risk_score ?? "N/A"}</p><p><b>Acquisition Status:</b> {data.acquisition_status}</p></div></Panel>;
}

function Placeholder({ title }) { return <Panel title={title}><div className="empty">No operational records available.</div></Panel>; }

function Simulator() {
  const [out, setOut] = useState(null);
  return <section className="panel"><h2>Acquisition Flight Simulator</h2><p>Compare Route A/B/C before a decision.</p><button onClick={async() => setOut(await api('/intelligence/simulate', {method:'POST',body:JSON.stringify({})}))}>Run Simulation</button>{out && <div className="grid2" style={{marginTop: 15}}>{out.scenarios.map(s => <div className="notice" key={s.name}><h3>{s.name}{s.name === out.recommended.name ? ' ★ Recommended' : ''}</h3><div>Cost: {s.cost.toFixed(1)}</div><div>Affected parcels: {s.affected_parcels}</div><div>High-risk: {s.high_risk}</div><div>Delay: {s.delay_months} months</div><div>Decision score: <b>{s.decision_score}</b></div></div>)}</div>}</section>;
}

function Tools() {
  const [res, setRes] = useState(null);
  const [p, setP] = useState({before:0.2, after:0.5, threshold:0.15});
  return <section className="panel"><h2>Evidence Intelligence</h2><div className="toolbar" style={{display: 'flex', gap: '10px'}}><button onClick={async() => setRes(await api('/intelligence/satellite/change', {method:'POST',body:JSON.stringify(p)}))}>Check Satellite Change</button><button onClick={async() => setRes(await api('/intelligence/premortem', {method:'POST',body:JSON.stringify({legal_disputes:1,objections:1,compensation_deviation:18,satellite_change:1})}))}>Run Acquisition Pre-Mortem</button><button onClick={async() => setRes(await api('/intelligence/conflict-graph'))}>Build Conflict Graph</button></div><div className="toolbar" style={{display: 'flex', gap: '10px', marginTop: '10px'}}>{Object.keys(p).map(k => <label key={k}>{k} <input type="number" step="0.01" value={p[k]} onChange={e => setP({...p, [k]: parseFloat(e.target.value)})}/></label>)}</div>{res && <pre style={{background: '#f4f4f4', padding: '10px', marginTop: '10px', overflowX: 'auto'}}>{JSON.stringify(res,null,2)}</pre>}</section>;
}

function Evidence() {
  const [parcel, setParcel] = useState('');
  const [reason, setReason] = useState('');
  const [msg, setMsg] = useState('');
  return <section className="panel"><h2>Citizen Evidence & Field Verification</h2><div style={{display: 'grid', gap: '10px', marginBottom: '10px'}}><label>Parcel ID <input value={parcel} onChange={e => setParcel(e.target.value)}/></label><label>Objection / notes <textarea value={reason} onChange={e => setReason(e.target.value)}/></label></div><div className="toolbar" style={{display: 'flex', gap: '10px'}}><button onClick={async() => {try {const x = await api('/intelligence/objection', {method:'POST',body:JSON.stringify({parcel_id:parcel,reason})}); setMsg(x.message)} catch(e) {setMsg(e.message)}}}>Submit Citizen Objection</button><button onClick={async() => {try {const x = await api('/intelligence/verify', {method:'POST',body:JSON.stringify({parcel_id:parcel,outcome:'verified',notes:reason,latitude:11.0168,longitude:76.9558})}); setMsg(x.message)} catch(e) {setMsg(e.message)}}}>Field Verify</button><button onClick={async() => setMsg(JSON.stringify(await api('/intelligence/ledger'), null, 2))}>Check Evidence Ledger</button></div>{msg && <pre style={{background: '#f4f4f4', padding: '10px', marginTop: '10px', overflowX: 'auto'}}>{msg}</pre>}</section>;
}

function Report() {
  const [id, setId] = useState('');
  const [out, setOut] = useState(null);
  return <section className="panel"><h2>Factual Evidence Report</h2><div className="toolbar"><input placeholder="Parcel database ID" value={id} onChange={e => setId(e.target.value)}/><button onClick={async() => setOut(await api('/intelligence/report/'+id))}>Generate Report</button></div>{out && <pre style={{background: '#f4f4f4', padding: '10px', marginTop: '10px', overflowX: 'auto'}}>{JSON.stringify(out,null,2)}</pre>}</section>;
}

function Advanced() {
  const [fusion, setFusion] = useState(null);
  const [cluster, setCluster] = useState(null);
  const [active, setActive] = useState(null);
  const [fb, setFb] = useState('');
  const runFusion = async() => setFusion(await api('/intelligence/fusion', {method:'POST',body:JSON.stringify({features:{project_type:'Road',land_required:2,affected_parcels:10,affected_families:3,legal_disputes:1,compensation_pending:1,approval_pending:0,documentation_pending:1,rehabilitation_pending:0,notification_pending:0,award_pending:0,possession_pending:0,stakeholder_responsiveness:2,environmental_risk:1,weather_risk:1},evidence:{satellite_observation:true,satellite_confidence:.86,document_mismatch_count:2,objection_count:2,ownership_complexity:3,data_completeness:72}})}));
  const runActive = async() => setActive(await api('/intelligence/active-learning', {method:'POST',body:JSON.stringify({parcels:[{parcel_id:'P1048',risk:76,uncertainty:28,missing_evidence:2,connected_parcels:8},{parcel_id:'P102',risk:64,uncertainty:61,missing_evidence:4,connected_parcels:6},{parcel_id:'P103',risk:77,uncertainty:35,missing_evidence:1,connected_parcels:2}]})}));
  return <section className="panel"><h2>Advanced Intelligence • Closed Loop</h2><div className="toolbar" style={{display: 'flex', gap: '10px'}}><button onClick={runFusion}>Run Multimodal Fusion</button><button onClick={async() => setCluster(await api('/intelligence/clusters'))}>Detect Conflict Clusters</button><button onClick={runActive}>Prioritize Field Verification</button></div>{fusion && <div className="notice" style={{marginTop: '10px'}}><b>Fusion Risk {fusion.risk_score}/100 • {fusion.risk_category}</b><br/>Uncertainty: {fusion.uncertainty}% • Data quality: {fusion.data_quality}%<br/>{fusion.disclaimer}</div>}{cluster && <pre style={{background: '#f4f4f4', padding: '10px', marginTop: '10px', overflowX: 'auto'}}>{JSON.stringify(cluster,null,2)}</pre>}{active && <pre style={{background: '#f4f4f4', padding: '10px', marginTop: '10px', overflowX: 'auto'}}>{JSON.stringify(active,null,2)}</pre>}<div className="toolbar" style={{display: 'flex', gap: '10px', marginTop: '10px'}}><input placeholder="Predicted label" value={fb} onChange={e => setFb(e.target.value)}/><button onClick={async() => setFb(JSON.stringify(await api('/intelligence/feedback', {method:'POST',body:JSON.stringify({parcel_id:1,predicted:fb,ground_truth:'VERIFIED',notes:'Field outcome captured'})}), null, 2))}>Record Ground Truth</button><button onClick={async() => setFb(JSON.stringify(await api('/intelligence/model-health'), null, 2))}>Model Health</button></div>{fb && <pre style={{background: '#f4f4f4', padding: '10px', marginTop: '10px', overflowX: 'auto'}}>{fb}</pre>}</section>;
}


// ─── Cross-Department Conflict Engine ────────────────────────────────────────
const SEV_COLOR = { Critical: '#b42318', High: '#d97706', Medium: '#0056b3', Low: '#16704a' };
const STATUS_COLOR = { Resolved: '#16704a', 'Under Review': '#d97706', Escalated: '#b42318', Assigned: '#0056b3', Pending: '#888', Verified: '#16704a', 'Cannot Verify': '#b42318' };

function SeverityBadge({ s }) {
  return <span style={{ background: SEV_COLOR[s] || '#888', color: '#fff', borderRadius: '4px', padding: '2px 8px', fontSize: '11px', fontWeight: 700 }}>{s}</span>;
}
function StatusBadge({ s }) {
  return <span style={{ background: STATUS_COLOR[s] || '#888', color: '#fff', borderRadius: '4px', padding: '2px 8px', fontSize: '11px' }}>{s || 'Pending'}</span>;
}

function ConflictEngine({ user }) {
  const role = user?.role || '';
  const isState    = ['state_authority', 'authority', 'admin'].includes(role);
  const isDistrict = ['district_authority', 'authority', 'admin', 'acquisition_officer'].includes(role);
  const isField    = ['field_officer', 'officer', 'authority', 'admin'].includes(role);

  // ── shared conflict list state ────────────────────────────────────
  const [severity, setSeverity] = useState('ALL');
  const [status, setStatus]     = useState('ALL');
  const [search, setSearch]     = useState('');
  const [refresh, setRefresh]   = useState(0);
  const bump = () => setRefresh(r => r + 1);

  const params = new URLSearchParams({ severity, status, search });
  const { data, error } = useData(`/intelligence/conflict-engine?${params}`, 0);

  // ── assignment tracking (District view) ──────────────────────────
  const { data: allAssignments } = useData(isDistrict ? '/intelligence/conflict-engine/assignments/all' : null, 0);
  // ── my assignments (Field view) ──────────────────────────────────
  const { data: myData } = useData(isField && !isDistrict && !isState ? '/intelligence/conflict-engine/assignments/mine' : null, 0);

  // ── per-row UI state ─────────────────────────────────────────────
  const [expandedId, setExpandedId] = useState(null);
  const [assignForms, setAssignForms]     = useState({}); // {conflictId: {officer_email, priority, notes}}
  const [fieldForms, setFieldForms]       = useState({}); // {conflictId: {field_status, field_remarks, evidence_description}}
  const [resolveForms, setResolveForms]   = useState({}); // {conflictId: {resolution_status, resolution_note}}
  const [saving, setSaving]               = useState({});
  const [msgs, setMsgs]                   = useState({});

  const setMsg = (id, m) => setMsgs(p => ({ ...p, [id]: m }));
  const setSav = (id, v) => setSaving(p => ({ ...p, [id]: v }));

  // ── field officers for District assign dropdown ───────────────────
  const { data: officersData } = useData(isDistrict ? '/field/officers' : null);
  const officers = officersData || [];

  // ── summary cards ─────────────────────────────────────────────────
  const sum = data?.summary || {};

  // ── Field officer: merge my assignments with conflict list ────────
  const myAssignMap = {};
  if (myData?.assignments) {
    myData.assignments.forEach(a => { myAssignMap[a.conflict_id] = a; });
  }
  const allAssignMap = {};
  if (allAssignments?.assignments) {
    allAssignments.assignments.forEach(a => { allAssignMap[a.conflict_id] = a; });
  }

  // For field officers without District/State access, only show their assigned conflicts
  const conflicts = (() => {
    if (!data?.conflicts) return [];
    if (isField && !isDistrict && !isState) {
      // Only show conflicts that are assigned to this field officer
      return data.conflicts.filter(cf => myAssignMap[cf.conflict_id]);
    }
    return data.conflicts;
  })();

  const saveAssign = async (cf) => {
    const form = assignForms[cf.conflict_id] || {};
    if (!form.officer_email) { setMsg(cf.conflict_id, 'Select a field officer'); return; }
    setSav(cf.conflict_id, true);
    try {
      const r = await api(`/intelligence/conflict-engine/${cf.conflict_id}/assign`, {
        method: 'POST',
        body: JSON.stringify({ officer_email: form.officer_email, priority: form.priority || 'Normal', notes: form.notes || '' })
      });
      setMsg(cf.conflict_id, r.message);
      setAssignForms(p => ({ ...p, [cf.conflict_id]: {} }));
      bump();
    } catch(e) { setMsg(cf.conflict_id, e.message); }
    setSav(cf.conflict_id, false);
  };

  const saveFieldUpdate = async (cf) => {
    const form = fieldForms[cf.conflict_id] || {};
    if (!form.field_status) { setMsg(cf.conflict_id, 'Select a field status'); return; }
    setSav(cf.conflict_id, true);
    try {
      const r = await api(`/intelligence/conflict-engine/${cf.conflict_id}/field-update`, {
        method: 'PATCH',
        body: JSON.stringify({ field_status: form.field_status, field_remarks: form.field_remarks || '', evidence_description: form.evidence_description || '' })
      });
      setMsg(cf.conflict_id, r.message);
      bump();
    } catch(e) { setMsg(cf.conflict_id, e.message); }
    setSav(cf.conflict_id, false);
  };

  const saveResolve = async (cf) => {
    const form = resolveForms[cf.conflict_id] || {};
    setSav(cf.conflict_id, true);
    try {
      const r = await api(`/intelligence/conflict-engine/${cf.conflict_id}/resolve`, {
        method: 'PATCH',
        body: JSON.stringify({ resolution_status: form.resolution_status || 'Resolved', resolution_note: form.resolution_note || '' })
      });
      setMsg(cf.conflict_id, r.message);
      bump();
    } catch(e) { setMsg(cf.conflict_id, e.message); }
    setSav(cf.conflict_id, false);
  };

  if (error) return (
    <Panel title="Cross-Department Conflict Engine">
      <div className="error">Unable to load conflicts ({error.status || 'network error'}): {error.message} <RefreshButton /></div>
    </Panel>
  );
  if (!data) return <Panel title="Cross-Department Conflict Engine"><p>Loading conflict data…</p></Panel>;

  return (
    <>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>Cross-Department Conflict Engine</h2>
        <RefreshButton />
      </div>

      {sum.demo_rows > 0 && (
        <div className="notice" style={{ background: '#fffbe6', borderLeft: '4px solid #d97706', marginBottom: 12 }}>
          ⚠ <b>DEMO DATA:</b> {sum.demo_rows} synthetic conflict row(s) are included for demonstration. Real conflicts detected from live parcel-project overlaps are labelled LIVE.
        </div>
      )}

      {/* ── Summary Cards ──────────────────────────────────────────── */}
      <div className="cards" style={{ marginBottom: 16 }}>
        {[['Total Conflicts', sum.total, '#0056b3'],
          ['Critical', sum.critical, '#b42318'],
          ['High', sum.high, '#d97706'],
          ['Resolved', sum.resolved, '#16704a'],
          ['Pending', sum.pending, '#555']
        ].map(([label, val, col]) => (
          <div className="metric" key={label} style={{ borderTop: `3px solid ${col}` }}>
            <span>{label}</span><b style={{ color: col }}>{val ?? 0}</b>
          </div>
        ))}
      </div>

      {/* ── Filters ────────────────────────────────────────────────── */}
      <div className="toolbar" style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input placeholder="Search survey, village, type…" value={search}
          onChange={e => setSearch(e.target.value)} style={{ minWidth: 200 }} />
        <select value={severity} onChange={e => setSeverity(e.target.value)}>
          {['ALL','Critical','High','Medium','Low'].map(x => <option key={x}>{x}</option>)}
        </select>
        <select value={status} onChange={e => setStatus(e.target.value)}>
          {['ALL','Pending','Under Review','Escalated','Assigned','Verified','Resolved'].map(x => <option key={x}>{x}</option>)}
        </select>
      </div>

      {/* ── Field officer with no assignments ─────────────────────── */}
      {isField && !isDistrict && !isState && conflicts.length === 0 && (
        <div className="empty">No conflicts assigned to you yet. Your District Authority will assign conflicts for field verification.</div>
      )}

      {/* ── Conflict Cards ─────────────────────────────────────────── */}
      {conflicts.map(cf => {
        const expanded   = expandedId === cf.conflict_id;
        const assignment = allAssignMap[cf.conflict_id] || myAssignMap[cf.conflict_id] || null;
        const aForm  = assignForms[cf.conflict_id] || {};
        const fForm  = fieldForms[cf.conflict_id] || {};
        const rForm  = resolveForms[cf.conflict_id] || {};
        const isSaving = saving[cf.conflict_id];
        const msg    = msgs[cf.conflict_id];

        return (
          <div key={cf.conflict_id} style={{ background: '#fff', border: `2px solid ${SEV_COLOR[cf.severity] || '#ddd'}`, borderRadius: 8, marginBottom: 12, overflow: 'hidden' }}>

            {/* ── Card Header ────────────────────────────────────── */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', background: '#f8f9fa', cursor: 'pointer' }}
                 onClick={() => setExpandedId(expanded ? null : cf.conflict_id)}>
              <div>
                <b>Survey {cf.survey_no}</b> · {cf.village}
                {cf.data_source === 'DEMO' && <span style={{ marginLeft: 8, fontSize: 10, background: '#d97706', color: '#fff', borderRadius: 3, padding: '1px 6px' }}>DEMO</span>}
                <span style={{ margin: '0 8px', color: '#666', fontSize: 12 }}>{cf.conflict_type}</span>
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <SeverityBadge s={cf.severity} />
                <StatusBadge s={assignment?.field_status || cf.resolution_status} />
                <span style={{ fontSize: 18, color: '#666' }}>{expanded ? '▲' : '▼'}</span>
              </div>
            </div>

            {/* ── Expanded Body ───────────────────────────────────── */}
            {expanded && (
              <div style={{ padding: '14px 16px' }}>

                {/* Core info */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12, background: '#f8f9fa', padding: 10, borderRadius: 6 }}>
                  <div><b>Conflict ID:</b><br /><small>{cf.conflict_id}</small></div>
                  <div><b>Overlap Area:</b><br />{cf.overlap_area_acres} acres ({cf.overlap_pct}%)</div>
                  <div><b>Resolution Status:</b><br /><StatusBadge s={cf.resolution_status} /></div>
                </div>

                {/* Departments */}
                <div style={{ marginBottom: 10 }}>
                  <b>Conflicting Departments / Projects:</b>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
                    {cf.departments.map((d, i) => (
                      <div key={i} style={{ background: '#e8f0fe', borderRadius: 6, padding: '5px 10px', fontSize: 13 }}>
                        <b>{d.department}</b><br /><small>{d.project_name}</small><br /><small style={{ color: '#666' }}>{d.project_id}</small>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Suggested resolution */}
                <div style={{ background: '#f0fff4', border: '1px solid #16704a', borderRadius: 6, padding: 10, marginBottom: 12 }}>
                  <b>💡 Suggested Resolution:</b><br />{cf.suggested_resolution}
                </div>

                {/* Assignment status if any */}
                {assignment && (
                  <div style={{ background: '#e8f0fe', borderRadius: 6, padding: 10, marginBottom: 12 }}>
                    <b>Field Assignment:</b> {assignment.assigned_to} · Priority: {assignment.priority}
                    {assignment.notes && <> · Notes: {assignment.notes}</>}<br />
                    <b>Field Status:</b> <StatusBadge s={assignment.field_status} />
                    {assignment.field_remarks && <> · Remarks: {assignment.field_remarks}</>}
                    {assignment.evidence_file && <> · Evidence: {assignment.evidence_file}</>}
                  </div>
                )}

                {msg && <div className="notice" style={{ marginBottom: 10, color: msg.includes('failed') || msg.includes('error') ? 'red' : '#16704a' }}>{msg}</div>}

                {/* ── District Officer Actions ────────────────────── */}
                {isDistrict && (
                  <details style={{ marginBottom: 10 }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: 6 }}>
                      {assignment ? '↺ Re-assign Field Officer' : '+ Assign Field Officer'}
                    </summary>
                    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 2fr auto', gap: 8, alignItems: 'end', marginTop: 8 }}>
                      <label>Field Officer
                        <select value={aForm.officer_email || ''} onChange={e => setAssignForms(p => ({ ...p, [cf.conflict_id]: { ...aForm, officer_email: e.target.value } }))}>
                          <option value="">Select officer…</option>
                          {officers.map(o => <option key={o.email} value={o.email}>{o.email}</option>)}
                        </select>
                      </label>
                      <label>Priority
                        <select value={aForm.priority || 'Normal'} onChange={e => setAssignForms(p => ({ ...p, [cf.conflict_id]: { ...aForm, priority: e.target.value } }))}>
                          {['Normal','High','Urgent'].map(x => <option key={x}>{x}</option>)}
                        </select>
                      </label>
                      <label>Notes
                        <input placeholder="Instructions for officer…" value={aForm.notes || ''}
                          onChange={e => setAssignForms(p => ({ ...p, [cf.conflict_id]: { ...aForm, notes: e.target.value } }))} />
                      </label>
                      <button onClick={() => saveAssign(cf)} disabled={isSaving} style={{ background: '#0056b3', color: '#fff' }}>
                        {isSaving ? 'Saving…' : 'Assign'}
                      </button>
                    </div>
                  </details>
                )}

                {isDistrict && (
                  <details style={{ marginBottom: 10 }}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: 6 }}>Mark as Resolved / Escalated</summary>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 8, alignItems: 'end', marginTop: 8 }}>
                      <label>Status
                        <select value={rForm.resolution_status || 'Resolved'} onChange={e => setResolveForms(p => ({ ...p, [cf.conflict_id]: { ...rForm, resolution_status: e.target.value } }))}>
                          {['Resolved','Under Review','Escalated','Pending'].map(x => <option key={x}>{x}</option>)}
                        </select>
                      </label>
                      <label>Resolution Note
                        <input placeholder="Describe resolution…" value={rForm.resolution_note || ''}
                          onChange={e => setResolveForms(p => ({ ...p, [cf.conflict_id]: { ...rForm, resolution_note: e.target.value } }))} />
                      </label>
                      <button onClick={() => saveResolve(cf)} disabled={isSaving} style={{ background: '#16704a', color: '#fff' }}>
                        {isSaving ? 'Saving…' : 'Update'}
                      </button>
                    </div>
                  </details>
                )}

                {/* ── Field Officer Actions ───────────────────────── */}
                {isField && (
                  <details style={{ marginBottom: 10 }} open={isField && !isDistrict && !isState}>
                    <summary style={{ cursor: 'pointer', fontWeight: 600, marginBottom: 6 }}>📋 Submit Field Verification</summary>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 2fr auto', gap: 8, alignItems: 'end', marginTop: 8 }}>
                      <label>Field Status
                        <select value={fForm.field_status || ''} onChange={e => setFieldForms(p => ({ ...p, [cf.conflict_id]: { ...fForm, field_status: e.target.value } }))}>
                          <option value="">Select…</option>
                          {['Assigned','In Progress','Verified','Cannot Verify','Escalated'].map(x => <option key={x}>{x}</option>)}
                        </select>
                      </label>
                      <label>Field Remarks
                        <input placeholder="Ground observations…" value={fForm.field_remarks || ''}
                          onChange={e => setFieldForms(p => ({ ...p, [cf.conflict_id]: { ...fForm, field_remarks: e.target.value } }))} />
                      </label>
                      <label>Evidence Description
                        <input placeholder="Photo ref / doc ref / GPS note…" value={fForm.evidence_description || ''}
                          onChange={e => setFieldForms(p => ({ ...p, [cf.conflict_id]: { ...fForm, evidence_description: e.target.value } }))} />
                      </label>
                      <button onClick={() => saveFieldUpdate(cf)} disabled={isSaving} style={{ background: '#0056b3', color: '#fff' }}>
                        {isSaving ? 'Saving…' : 'Submit'}
                      </button>
                    </div>
                  </details>
                )}

              </div>
            )}
          </div>
        );
      })}

      {conflicts.length === 0 && data && (
        <div className="empty">No conflicts match the current filters.</div>
      )}

      {/* ── District: Assignment Tracker ───────────────────────────── */}
      {isDistrict && allAssignments?.assignments?.length > 0 && (
        <Panel title={`Field Assignment Tracker (${allAssignments.total})`}>
          <Table
            rows={allAssignments.assignments}
            cols={['conflict_id','assigned_to','assigned_by','priority','field_status','field_remarks','assigned_at','updated_at']}
          />
        </Panel>
      )}
    </>
  );
}

function IntelligenceDashboard({ user }) {
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
        <h2 style={{ margin: 0 }}>Advanced Intelligence</h2>
      </div>
      <ConflictEngine user={user} />
      <Simulator />
      <Tools />
      <Advanced />
      <Evidence />
      <Report />
    </>
  );
}

function App() {
  const [user, setUser] = useState(null), [page, setPage] = useState("dashboard"), [lang, setLang] = useState("en"), [selected, setSelected] = useState(null);

  useEffect(() => {
    if (localStorage.getItem("survi_token")) {
      api(AUTH_ME_PATH).then(u => {
        setUser(u);
        if (u.role === 'citizen') setPage('citizen_dash');
        else if (u.role === 'state_authority') setPage('state_dashboard');
        else if (u.role === 'district_authority') setPage('district_dashboard');
        else if (u.role === 'field_officer') setPage('field');
      }).catch(() => localStorage.removeItem("survi_token"));
    }
  }, []);

  if (!user) return <Login onLogin={u => {
    setUser(u);
    if (u.role === 'citizen') setPage('citizen_dash');
    else if (u.role === 'state_authority') setPage('state_dashboard');
    else if (u.role === 'district_authority') setPage('district_dashboard');
    else if (u.role === 'field_officer') setPage('field');
  }} />;

  let content = <Placeholder title={nav.find(x => x[0] === page)?.[1] || page} />;
  if (page === "dashboard") content = <Dashboard />;
  else if (page === "state_dashboard") content = <StateDashboard />;
  else if (page === "district_dashboard") content = <DistrictDashboard user={user} go={x => { setSelected(x); setPage("workflow"); }} />;
  else if (page === "projects") content = <Projects go={x => { setSelected(x); setPage("workflow"); }} />;
  else if (page === "parcels") content = <LandParcels user={user} go={x => { setSelected(x); setPage("workflow"); }} />;
  else if (page === "gis") content = <GIS />;
  else if (page === "ml") content = <ML />;
  else if (page === "citizen_dash") content = <CitizenDash lang={lang} user={user} />;
  else if (page === "workflow") content = <Workflow selected={selected} user={user} go={x => { setSelected(x); setPage(x.parcel_id ? "parcel_details" : "workflow"); }} />;
  else if (page === "parcel_details") content = <ParcelDetails selected={selected} />;
  else if (page === "sla") content = <SLA selected={selected} />;
  else if (page === "bottlenecks") content = <Bottlenecks go={x => { setSelected(x); setPage("workflow"); }} />;
  else if (page === "risk") content = <RiskIntelligence go={x => { setSelected(x); setPage(x.parcel_id ? "parcel_details" : "workflow"); }} />;
  else if (page === "alerts") content = <AlertsPage go={x => { setSelected(x); setPage(x.parcel_id ? "parcel_details" : "workflow"); }} />;
  else if (page === "analytics") content = <AnalyticsPage go={x => { setSelected(x); setPage("workflow"); }} />;
  else if (page === "reports") content = <Reports />;
  else if (page === "field") content = <FieldVerification go={x => { setSelected(x); setPage("documents"); }} />;
  else if (page === "grievances") content = <Grievances user={user} />;
  else if (page === "documents") content = <DocumentsPage user={user} selected={selected} />;
  else if (page === "intelligence") content = <IntelligenceDashboard />;

  const allowedNav = nav.filter(n => {
    if (user.role === "citizen") return ["citizen_dash", "grievances"].includes(n[0]);
    if (user.role === "state_authority") return !["district_dashboard", "citizen_dash", "users", "audit"].includes(n[0]);
    if (user.role === "district_authority") return !["state_dashboard", "citizen_dash", "users", "audit", "ml", "intelligence"].includes(n[0]);
    if (user.role === "field_officer") return ["field", "parcels", "gis", "documents"].includes(n[0]);
    return n[0] !== "citizen_dash";
  });

  return (
    <div className="shell">
      <aside className="sidebar flex flex-col h-screen max-h-screen">
        <div className="side-header shrink-0 flex-shrink-0">
          <div className="logo">LAND<span>NEXUS</span></div>
          <div className="tag">SIH 26016 CORE</div>
        </div>
        <div className="side-nav-scroll flex-1 min-h-0 overflow-y-auto overflow-x-hidden">
          {allowedNav.map(n => <button className={page === n[0] ? "nav active" : "nav"} key={n[0]} onClick={() => setPage(n[0])}>{lang === "ta" ? tamil[n[1]] || n[1] : n[1]}</button>)}
        </div>
        <div className="side-bottom shrink-0 flex-shrink-0">
          <button className="nav" onClick={() => setLang(lang === "en" ? "ta" : "en")}>English / தமிழ்</button>
          <button className="nav logout" onClick={() => { localStorage.removeItem("survi_token"); setUser(null); }}>Logout</button>
        </div>
      </aside>
      <main className="content">
        <header>
          <div>
            <div className="eyebrow">PROTOTYPE SCOPE: COIMBATORE DISTRICT · SYNTHETIC PROTOTYPE DATA</div>
            <h1>{lang === "ta" ? (tamil[nav.find(x => x[0] === page)?.[1]] || page) : (nav.find(x => x[0] === page)?.[1] || page)}</h1>
            <p>From land records to acquisition decisions — monitor, predict, explain and act.</p>
          </div>
          <div className="user-pill">{user.role.replaceAll("_", " ")}<br /><small>{user.email}</small></div>
        </header>
        {selected && <div className="context-strip">Selected Context: {selected.project_id || selected.record_id || selected.survey_no} <button onClick={() => setSelected(null)}>×</button></div>}
        {content}
      </main>
    </div>
  );
}

export default App;
export { api, useData, Panel, Table, ActionButton, EventBus, DataPanel, RefreshButton, AlertTable };
