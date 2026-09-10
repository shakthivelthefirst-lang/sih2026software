import React, { useState, useEffect } from "react";
import { api, useData, Panel, Table, ActionButton, EventBus, RefreshButton } from "./App";

export default function DocumentsPage({ user, selected }) {
  const [projectId, setProjectId] = useState(selected?.project_id || "");
  const [parcelId, setParcelId] = useState(selected?.parcel_id || "");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [docId, setDocId] = useState(null);

  // Fetch documents for the project or all documents if district authority
  const query = parcelId ? `?parcel_id=${parcelId}` : (projectId ? `?project_id=${projectId}` : "");
  const { data: documents, error: fetchError } = useData(`/documents/${query}`, 5000);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    if (projectId) formData.append("project_id", projectId);
    if (parcelId) formData.append("parcel_id", parcelId);

    try {
      const res = await api("/documents/", { method: "POST", body: formData });
      setFile(null);
      setDocId(res.document_id);
      EventBus.dispatch();
    } catch (err) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const startOCR = async (document_id) => {
    try {
      await api(`/ocr/${document_id}/process`, { method: "POST" });
      setDocId(document_id);
    } catch (err) {
      alert("OCR failed: " + err.message);
    }
  };

  return (
    <>
      <Panel title="OCR Document Intelligence">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px" }}>
          <div>
            <h3>Upload Land Document</h3>
            <form onSubmit={handleUpload} className="form">
              <label>Project ID (Optional) <input value={projectId} onChange={e => setProjectId(e.target.value)} /></label>
              <label>Parcel ID (Optional) <input value={parcelId} onChange={e => setParcelId(e.target.value)} /></label>
              <label>
                Document (PDF/JPG/PNG)
                <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={e => setFile(e.target.files[0])} />
              </label>
              {file && <small>Selected: {file.name} ({Math.round(file.size/1024)} KB)</small>}
              <button type="submit" disabled={!file || uploading}>{uploading ? "Uploading..." : "Upload Document"}</button>
            </form>
            {error && <div className="error">{error}</div>}
          </div>

          <div>
            {docId && <OCRVerificationPanel documentId={docId} onClose={() => setDocId(null)} user={user} />}
          </div>
        </div>
      </Panel>

      <Panel title="Document History">
        <div className="toolbar"><RefreshButton /></div>
        {fetchError && <div className="error">{fetchError.message}</div>}
        <Table rows={documents || []} cols={["document_id", "document_name", "project_id", "parcel_id", "upload_date", "ocr_status", "verification_status"]} actions={(r) => (
          <div style={{ display: "flex", gap: "5px" }}>
            <button onClick={() => setDocId(r.document_id)}>View OCR</button>
            {(r.ocr_status === "Not Started" || r.ocr_status === "Failed") && <ActionButton label="Run OCR" onClick={() => startOCR(r.document_id)} />}
          </div>
        )} />
      </Panel>
    </>
  );
}

function OCRVerificationPanel({ documentId, onClose, user }) {
  const { data: ocrData, error } = useData(`/ocr/${documentId}`, 5000);
  const [fields, setFields] = useState({});
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (ocrData?.extractions) {
      const obj = {};
      ocrData.extractions.forEach(e => {
        obj[e.field_name] = e.value;
      });
      setFields(obj);
    }
  }, [ocrData]);

  if (error) return <div className="error">Error loading OCR details: {error.message}</div>;
  if (!ocrData) return <div>Loading OCR details...</div>;

  const handleVerify = async () => {
    try {
      await api(`/ocr/${documentId}/verify`, { method: "POST", body: JSON.stringify({ fields }) });
      setEditing(false);
    } catch (err) {
      alert("Verification failed: " + err.message);
    }
  };

  const canVerify = ["authority", "admin", "acquisition_officer", "district_authority", "state_authority", "field_officer"].includes(user?.role);
  const isVerified = ocrData.ocr_status === "Verified";

  return (
    <div style={{ background: "#f8f9fa", padding: "15px", borderRadius: "8px", border: "1px solid #ddd" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3>OCR Extraction</h3>
        <button type="button" onClick={onClose}>Close</button>
      </div>
      
      <p><b>Status:</b> {ocrData.ocr_status} {ocrData.ocr_confidence ? `(Confidence: ${Math.round(ocrData.ocr_confidence * 100)}%)` : ""}</p>
      
      {ocrData.extractions?.length === 0 ? (
        <p>No data extracted yet or processing...</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginTop: "10px" }}>
          {Object.entries(fields).map(([key, val]) => (
            <div key={key}>
              <label style={{ display: "block", fontSize: "12px", color: "#666" }}>{key.replace("_", " ").toUpperCase()}</label>
              {editing ? (
                <input style={{ width: "100%", padding: "4px" }} value={val || ""} onChange={e => setFields({...fields, [key]: e.target.value})} />
              ) : (
                <div style={{ background: "#fff", padding: "6px", border: "1px solid #ccc" }}>{val || "-"}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {canVerify && !isVerified && ocrData.extractions?.length > 0 && (
        <div style={{ marginTop: "15px", display: "flex", gap: "10px" }}>
          {editing ? (
            <>
              <ActionButton label="Save & Verify" onClick={handleVerify} />
              <button type="button" onClick={() => setEditing(false)}>Cancel</button>
            </>
          ) : (
            <>
              <button type="button" onClick={() => setEditing(true)}>Edit Extraction</button>
              <ActionButton label="Verify & Confirm" onClick={handleVerify} />
            </>
          )}
        </div>
      )}
      
      {isVerified && <div className="notice" style={{ marginTop: "10px" }}>This document has been verified by an authorized officer.</div>}
    </div>
  );
}
