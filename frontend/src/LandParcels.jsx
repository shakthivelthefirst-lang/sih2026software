import React, { useState, useEffect, useMemo } from "react";
import { useData, Panel, Table, ActionButton, RefreshButton } from "./App";

export default function LandParcels({ user, go }) {
  const role = user?.role || "state_authority";
  const userDistrict = user?.district || (role !== "state_authority" ? "Coimbatore" : "");
  const userTaluk = user?.taluk || (role === "field_officer" ? "Sulur" : "");

  // Search input state
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");

  // Role-adaptive filter states
  const [selectedDistrict, setSelectedDistrict] = useState(userDistrict || "All");
  const [selectedTaluk, setSelectedTaluk] = useState(userTaluk || "All");
  const [selectedVillage, setSelectedVillage] = useState("All");
  const [selectedProject, setSelectedProject] = useState("All");
  const [selectedAcqStatus, setSelectedAcqStatus] = useState("All");
  const [selectedSlaRisk, setSelectedSlaRisk] = useState("All");
  const [selectedInspectionStatus, setSelectedInspectionStatus] = useState("All");
  const [assignedToMe, setAssignedToMe] = useState(role === "field_officer");
  const [activeChip, setActiveChip] = useState("ALL");

  // Debounce search input by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQ(searchTerm);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  // Load project list for project dropdown
  const { data: projectsData } = useData("/projects/?limit=200", 10000);
  const projectList = useMemo(() => {
    return (projectsData?.items || []).map(p => p.project_id).filter(Boolean);
  }, [projectsData]);

  // Build query string for API
  const queryParams = useMemo(() => {
    const p = new URLSearchParams({ limit: "150" });
    if (debouncedQ.trim()) p.set("q", debouncedQ.trim());

    // State Authority filters
    if (role === "state_authority" || role === "authority" || role === "admin") {
      if (selectedDistrict && selectedDistrict !== "All") p.set("district", selectedDistrict);
      if (selectedProject && selectedProject !== "All") p.set("project_id", selectedProject);
    } else if (role === "district_authority") {
      p.set("district", userDistrict || "Coimbatore");
    } else if (role === "field_officer") {
      p.set("taluk", userTaluk || "Sulur");
    }

    // Taluk filter for non-field officers
    if (role !== "field_officer" && selectedTaluk && selectedTaluk !== "All") {
      p.set("taluk", selectedTaluk);
    }

    // Village filter
    if (selectedVillage && selectedVillage !== "All") {
      p.set("village", selectedVillage);
    }

    // Chip filter takes precedence or combines
    if (activeChip === "ACQUIRED") {
      p.set("acquisition_status", "ACQUIRED");
    } else if (activeChip === "PENDING") {
      p.set("acquisition_status", "PENDING");
    } else if (activeChip === "DISPUTED") {
      p.set("acquisition_status", "DISPUTED");
    } else if (activeChip === "VERIFICATION_PENDING") {
      p.set("verification_status", "PENDING INSPECTION");
    } else {
      if (selectedAcqStatus && selectedAcqStatus !== "All") p.set("acquisition_status", selectedAcqStatus);
      if (selectedInspectionStatus && selectedInspectionStatus !== "All") p.set("verification_status", selectedInspectionStatus);
    }

    // SLA risk
    if (selectedSlaRisk && selectedSlaRisk !== "All") {
      p.set("risk_level", selectedSlaRisk);
    }

    // Assigned to me
    if (assignedToMe) {
      p.set("assigned_to_me", "true");
    }

    return p.toString();
  }, [
    debouncedQ,
    role,
    userDistrict,
    userTaluk,
    selectedDistrict,
    selectedTaluk,
    selectedVillage,
    selectedProject,
    selectedAcqStatus,
    selectedSlaRisk,
    selectedInspectionStatus,
    assignedToMe,
    activeChip
  ]);

  // Fetch parcels data from backend
  const { data: parcelsData, error: parcelsError, reload } = useData(`/api/parcels?${queryParams}`, 5000);

  const resetFilters = () => {
    setSearchTerm("");
    setDebouncedQ("");
    setSelectedDistrict(userDistrict || "All");
    setSelectedTaluk(userTaluk || "All");
    setSelectedVillage("All");
    setSelectedProject("All");
    setSelectedAcqStatus("All");
    setSelectedSlaRisk("All");
    setSelectedInspectionStatus("All");
    setAssignedToMe(false);
    setActiveChip("ALL");
  };

  const parcels = parcelsData?.items || [];

  // Decoupled global stats object from API response
  const stats = useMemo(() => {
    return parcelsData?.stats || {
      all: 0,
      acquired: 0,
      pending: 0,
      disputed: 0,
      verification_pending: 0
    };
  }, [parcelsData?.stats]);

  // Standard dropdown options
  const districtOptions = ["All", "Coimbatore", "Tiruppur", "Erode", "Salem"];
  const talukOptions = ["All", "Sulur", "Kinathukadavu", "Annur", "Perur", "Mettupalayam", "Madukkarai"];
  const villageOptions = ["All", "Sulur", "Karamadai", "Madukkarai", "Perur", "Annur", "Kinathukadavu", "Vadavalli", "Singanallur", "Kalapatti"];

  return (
    <div className="parcels-module">
      <Panel title="Land Parcels Register">
        {/* A. Global Search Bar */}
        <div className="parcel-search-container" style={{ marginBottom: "16px" }}>
          <div className="search-input-wrapper" style={{ position: "relative", width: "100%", maxWidth: "100%" }}>
            <span style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "#64748b", fontSize: "15px" }}>
              🔍
            </span>
            <input
              type="text"
              className="parcel-search-input"
              style={{
                width: "100%",
                padding: "10px 36px 10px 36px",
                borderRadius: "10px",
                border: "1px solid #cbd5e1",
                backgroundColor: "#f8fafc",
                fontSize: "14px",
                color: "#1e293b",
                outline: "none",
                boxSizing: "border-box"
              }}
              placeholder="Search by Survey No, Parcel ID, Landowner, or Project ID..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              aria-label="Search Land Parcels"
            />
            {searchTerm && (
              <button
                type="button"
                className="search-clear-btn"
                style={{
                  position: "absolute",
                  right: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: "16px",
                  cursor: "pointer",
                  padding: "4px"
                }}
                onClick={() => { setSearchTerm(""); setDebouncedQ(""); }}
                title="Clear Search"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* B. Role-Adaptive Filter Bar */}
        <div className="role-adaptive-toolbar" style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: "10px",
          padding: "12px 14px",
          backgroundColor: "#f8fafc",
          border: "1px solid #e2e8f0",
          borderRadius: "10px",
          marginBottom: "16px"
        }}>
          {/* Role 1: State Authority Controls */}
          {(role === "state_authority" || role === "authority" || role === "admin") && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>District:</label>
                <select
                  value={selectedDistrict}
                  onChange={e => setSelectedDistrict(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  {districtOptions.map(d => <option key={d} value={d}>{d === "All" ? "All Districts" : d}</option>)}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Project:</label>
                <select
                  value={selectedProject}
                  onChange={e => setSelectedProject(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff", maxWidth: "160px" }}
                >
                  <option value="All">All Projects</option>
                  {projectList.slice(0, 30).map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Status:</label>
                <select
                  value={selectedAcqStatus}
                  onChange={e => setSelectedAcqStatus(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  <option value="All">All Statuses</option>
                  <option value="ACQUIRED">Acquired</option>
                  <option value="PENDING">Pending</option>
                  <option value="DISPUTED">Disputed</option>
                </select>
              </div>
            </>
          )}

          {/* Role 2: District Officer Controls */}
          {role === "district_authority" && (
            <>
              {/* District locked badge */}
              <div style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                background: "#e0f2fe",
                color: "#0369a1",
                border: "1px solid #bae6fd",
                padding: "5px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600"
              }}>
                <span>🔒 District: {userDistrict || "Coimbatore"}</span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Taluk:</label>
                <select
                  value={selectedTaluk}
                  onChange={e => setSelectedTaluk(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  {talukOptions.map(t => <option key={t} value={t}>{t === "All" ? "All Taluks" : t}</option>)}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Village:</label>
                <select
                  value={selectedVillage}
                  onChange={e => setSelectedVillage(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  {villageOptions.map(v => <option key={v} value={v}>{v === "All" ? "All Villages" : v}</option>)}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>SLA Risk:</label>
                <select
                  value={selectedSlaRisk}
                  onChange={e => setSelectedSlaRisk(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  <option value="All">All Risks</option>
                  <option value="NORMAL">Normal</option>
                  <option value="AT_RISK">At Risk</option>
                  <option value="SLA_BREACH">Breached</option>
                </select>
              </div>
            </>
          )}

          {/* Role 3: Field Officer Controls */}
          {role === "field_officer" && (
            <>
              {/* District & Taluk locked badges */}
              <div style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                background: "#e0f2fe",
                color: "#0369a1",
                border: "1px solid #bae6fd",
                padding: "5px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600"
              }}>
                <span>🔒 District: {userDistrict || "Coimbatore"}</span>
              </div>

              <div style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "5px",
                background: "#f1f5f9",
                color: "#334155",
                border: "1px solid #cbd5e1",
                padding: "5px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "600"
              }}>
                <span>🔒 Taluk: {userTaluk || "Sulur"}</span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Village:</label>
                <select
                  value={selectedVillage}
                  onChange={e => setSelectedVillage(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  {villageOptions.map(v => <option key={v} value={v}>{v === "All" ? "All Villages" : v}</option>)}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <label style={{ fontSize: "12px", fontWeight: "600", color: "#475569" }}>Inspection:</label>
                <select
                  value={selectedInspectionStatus}
                  onChange={e => setSelectedInspectionStatus(e.target.value)}
                  style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #cbd5e1", fontSize: "12px", background: "#fff" }}
                >
                  <option value="All">All</option>
                  <option value="PENDING INSPECTION">Pending Inspection</option>
                  <option value="VERIFIED">Verified</option>
                  <option value="DISPUTED">Disputed</option>
                </select>
              </div>

              {/* Quick toggle: Assigned to Me */}
              <label style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "12px",
                fontWeight: "600",
                color: "#0f6c70",
                cursor: "pointer",
                userSelect: "none"
              }}>
                <input
                  type="checkbox"
                  checked={assignedToMe}
                  onChange={e => setAssignedToMe(e.target.checked)}
                  style={{ width: "auto", margin: 0 }}
                />
                Assigned to Me
              </label>
            </>
          )}

          {/* Reset Filters button */}
          <button
            type="button"
            onClick={resetFilters}
            style={{
              marginLeft: "auto",
              padding: "5px 12px",
              borderRadius: "6px",
              background: "#f1f5f9",
              color: "#475569",
              border: "1px solid #cbd5e1",
              fontSize: "12px",
              fontWeight: "600",
              cursor: "pointer"
            }}
          >
            Reset Filters
          </button>
        </div>

        {/* C. Quick Status Metric Badges (Clickable Filter Chips) */}
        <div className="metric-chips-bar" style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "8px",
          marginBottom: "16px"
        }}>
          {[
            { id: "ALL", label: `All: ${(stats.all || 0).toLocaleString()}` },
            { id: "ACQUIRED", label: `Acquired: ${(stats.acquired || 0).toLocaleString()}`, color: "#16a34a", bg: "#dcfce7" },
            { id: "PENDING", label: `Pending: ${(stats.pending || 0).toLocaleString()}`, color: "#d97706", bg: "#fef3c7" },
            { id: "DISPUTED", label: `Disputed: ${(stats.disputed || 0).toLocaleString()}`, color: "#dc2626", bg: "#fee2e2" },
            { id: "VERIFICATION_PENDING", label: `Verification Pending: ${(stats.verification_pending || 0).toLocaleString()}`, color: "#2563eb", bg: "#dbeafe" }
          ].map(chip => {
            const isActive = activeChip === chip.id;
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => setActiveChip(isActive && chip.id !== "ALL" ? "ALL" : chip.id)}
                style={{
                  padding: "5px 12px",
                  borderRadius: "9999px",
                  fontSize: "12px",
                  fontWeight: "600",
                  cursor: "pointer",
                  border: isActive ? `2px solid ${chip.color || "#0f6c70"}` : "1px solid #cbd5e1",
                  backgroundColor: isActive ? (chip.bg || "#f1f5f9") : "#ffffff",
                  color: isActive ? (chip.color || "#0f6c70") : "#475569",
                  transition: "all .15s ease"
                }}
              >
                {chip.label}
              </button>
            );
          })}
        </div>

        {/* Parcel Results Table or Empty State */}
        {parcelsError && (
          <div className="error">
            Unable to load parcels: {parcelsError.message}
          </div>
        )}

        {!parcelsError && parcels.length === 0 ? (
          <div style={{
            padding: "40px 20px",
            textAlign: "center",
            background: "#f8fafc",
            border: "1px dashed #cbd5e1",
            borderRadius: "10px",
            margin: "12px 0"
          }}>
            <div style={{ fontSize: "15px", fontWeight: "600", color: "#334155", marginBottom: "6px" }}>
              No parcels found matching your criteria.
            </div>
            <p style={{ fontSize: "13px", color: "#64748b", margin: "0 0 14px 0" }}>
              Try adjusting your search query, district/taluk filters, or active status chips.
            </p>
            <button
              type="button"
              onClick={resetFilters}
              style={{
                background: "#0f6c70",
                color: "#ffffff",
                border: "none",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer"
              }}
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <Table
            rows={parcels}
            cols={[
              "id",
              "survey_no",
              "village",
              "taluk",
              "district",
              "area",
              "owner_name",
              "project_id",
              "acquisition_status",
              "verification_status"
            ]}
            onClick={go}
          />
        )}
      </Panel>
    </div>
  );
}
