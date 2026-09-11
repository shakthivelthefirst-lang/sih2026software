import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Header, HTTPException

from backend.core import audit, conn, current_user

router = APIRouter()
EDITOR_ROLES = {"authority", "admin", "district_authority", "state_authority", "acquisition_officer", "field_officer"}
VIEW_ROLES = EDITOR_ROLES | {"citizen"}
COMPENSATION_STATUSES = {"NOT_ASSESSED", "ASSESSED", "APPROVED", "PARTIALLY_PAID", "FULLY_PAID", "DISPUTED", "ON_HOLD"}
FAMILY_STATUSES = {"Pending", "Verified", "Rejected"}
SATELLITE_CHANGES = {"NO_SIGNIFICANT_CHANGE", "NEW_CONSTRUCTION", "LAND_USE_CHANGE", "POSSIBLE_ENCROACHMENT", "VEGETATION_CHANGE", "SURFACE_CHANGE", "INFRASTRUCTURE_PROGRESS"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _require_user(authorization, roles=VIEW_ROLES):
    user = current_user(authorization)
    if not user:
        raise HTTPException(401, "Authentication required")
    if user["role"] not in roles:
        raise HTTPException(403, "Insufficient permissions")
    return user


def _ensure_schema():
    c = conn()
    compensation_columns = {
        "case_id": "TEXT", "family_id": "TEXT", "land_compensation": "REAL DEFAULT 0",
        "structure_compensation": "REAL DEFAULT 0", "crop_tree_compensation": "REAL DEFAULT 0",
        "livelihood_compensation": "REAL DEFAULT 0", "rr_compensation": "REAL DEFAULT 0",
        "other_compensation": "REAL DEFAULT 0", "total_assessed": "REAL DEFAULT 0",
        "award_reference": "TEXT", "approval_status": "TEXT DEFAULT 'NOT_ASSESSED'",
        "remarks": "TEXT", "updated_at": "TEXT"
    }
    existing = {row[1] for row in c.execute("PRAGMA table_info(compensation)").fetchall()}
    for name, definition in compensation_columns.items():
        if name not in existing:
            c.execute(f"ALTER TABLE compensation ADD COLUMN {name} {definition}")
    c.execute("""
        CREATE TABLE IF NOT EXISTS family_impacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL,
            parcel_id INTEGER NOT NULL,
            case_id TEXT,
            family_reference TEXT NOT NULL,
            members_count INTEGER DEFAULT 0,
            affected INTEGER DEFAULT 0,
            displaced INTEGER DEFAULT 0,
            vulnerable INTEGER DEFAULT 0,
            livelihood_affected INTEGER DEFAULT 0,
            housing_affected INTEGER DEFAULT 0,
            agricultural_affected INTEGER DEFAULT 0,
            employment_affected INTEGER DEFAULT 0,
            rr_required INTEGER DEFAULT 0,
            rr_status TEXT DEFAULT 'Not Required',
            resettlement_status TEXT DEFAULT 'Not Started',
            compensation_status TEXT DEFAULT 'NOT_ASSESSED',
            verification_status TEXT DEFAULT 'Pending',
            remarks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS satellite_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evidence_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL,
            parcel_id INTEGER NOT NULL,
            baseline_date TEXT,
            current_date TEXT,
            before_image_url TEXT,
            after_image_url TEXT,
            source TEXT,
            change_status TEXT NOT NULL,
            confidence REAL,
            observation_date TEXT,
            verification_status TEXT DEFAULT 'Pending',
            field_verification_status TEXT DEFAULT 'Pending',
            notes TEXT,
            synthetic_flag INTEGER DEFAULT 1,
            created_by TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_family_project ON family_impacts(project_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_family_parcel ON family_impacts(parcel_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_satellite_project ON satellite_evidence(project_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_satellite_parcel ON satellite_evidence(parcel_id)")
    c.commit()
    c.close()


_ensure_schema()


def _parcel_context(c, parcel_id: int, project_id: Optional[str] = None):
    parcel = c.execute("SELECT id, project_id FROM parcels WHERE id=?", (parcel_id,)).fetchone()
    if not parcel:
        raise HTTPException(404, "PARCEL_NOT_FOUND")
    if project_id and str(parcel["project_id"]) != str(project_id):
        raise HTTPException(400, "Parcel does not belong to project")
    project = c.execute("SELECT project_id FROM projects WHERE project_id=?", (parcel["project_id"],)).fetchone()
    if not project:
        raise HTTPException(400, "PROJECT_NOT_FOUND")
    return parcel


def _project_filter(payload, c):
    project_id = payload.get("project_id")
    if project_id and not c.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
        raise HTTPException(404, "PROJECT_NOT_FOUND")
    return project_id


def _amount(value, name):
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{name} must be numeric")
    if amount < 0:
        raise HTTPException(400, f"{name} cannot be negative")
    return amount


@router.get("/dashboard")
def intelligence_dashboard(authorization: str = Header(None), project_id: Optional[str] = None,
                          district: Optional[str] = None, taluk: Optional[str] = None):
    _require_user(authorization)
    c = conn()
    clauses, args = ["1=1"], []
    for column, value in (("p.project_id", project_id), ("p.district", district), ("p.taluk", taluk)):
        if value:
            clauses.append(f"{column}=?"); args.append(value)
    where = " AND ".join(clauses)
    compensation = c.execute(f"""
        SELECT COALESCE(SUM(CASE WHEN c.total_assessed > 0 THEN c.total_assessed ELSE c.assessed_amount END), 0) total_assessed,
               COALESCE(SUM(c.paid_amount),0) amount_paid,
               COALESCE(SUM(c.pending_amount),0) amount_pending,
               COUNT(*) records
        FROM compensation c JOIN parcels p ON p.id=c.parcel_id WHERE {where}
    """, args).fetchone()
    family = c.execute(f"""
        SELECT COUNT(*) total, COALESCE(SUM(f.affected),0) affected,
               COALESCE(SUM(f.displaced),0) displaced, COALESCE(SUM(f.vulnerable),0) vulnerable,
               COALESCE(SUM(f.rr_required),0) rr_required,
               COALESCE(SUM(CASE WHEN f.rr_status IN ('Completed','COMPLETED') THEN 1 ELSE 0 END),0) rr_completed
        FROM family_impacts f JOIN parcels p ON p.id=f.parcel_id WHERE {where}
    """, args).fetchone()
    satellites = c.execute(f"""
        SELECT COUNT(*) total, COALESCE(SUM(CASE WHEN s.change_status != 'NO_SIGNIFICANT_CHANGE' THEN 1 ELSE 0 END),0) changes
        FROM satellite_evidence s JOIN parcels p ON p.id=s.parcel_id WHERE {where}
    """, args).fetchone()
    risk = c.execute(f"SELECT risk_category category, COUNT(*) count FROM parcels p WHERE {where} GROUP BY risk_category", args).fetchall()
    c.close()
    assessed = float(compensation["total_assessed"] or 0)
    paid = float(compensation["amount_paid"] or 0)
    return {
        "compensation": {"total_assessed": assessed, "amount_paid": paid, "amount_pending": float(compensation["amount_pending"] or 0), "records": compensation["records"]},
        "families": {"total": family["total"], "affected": family["affected"], "displaced": family["displaced"], "vulnerable": family["vulnerable"], "rr_required": family["rr_required"], "rr_completed": family["rr_completed"], "rr_pending": max(0, family["rr_required"] - family["rr_completed"])},
        "satellite": {"total": satellites["total"], "changes": satellites["changes"]},
        "payment_completion": round(paid / assessed * 100, 1) if assessed else 0,
        "risk_distribution": [dict(row) for row in risk],
        "data_note": "Values are calculated from linked application records. Satellite imagery is not fabricated; absent imagery remains unavailable.",
    }


@router.get("/compensation/project/{project_id}")
@router.get("/projects/{project_id}/compensation")
def compensation_by_project(project_id: str, authorization: str = Header(None)):
    _require_user(authorization, EDITOR_ROLES)
    c = conn()
    if not c.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone():
        c.close(); raise HTTPException(404, "PROJECT_NOT_FOUND")
    rows = [dict(row) for row in c.execute("""
        SELECT c.*, p.survey_no, p.village, p.taluk, p.district
        FROM compensation c JOIN parcels p ON p.id=c.parcel_id
        WHERE c.project_id=? ORDER BY c.id DESC
    """, (project_id,)).fetchall()]
    c.close(); return rows


@router.get("/compensation/parcel/{parcel_id}")
@router.get("/parcels/{parcel_id}/compensation")
def compensation_by_parcel(parcel_id: int, authorization: str = Header(None)):
    _require_user(authorization, EDITOR_ROLES)
    c = conn(); _parcel_context(c, parcel_id)
    row = c.execute("SELECT * FROM compensation WHERE parcel_id=? ORDER BY id DESC LIMIT 1", (parcel_id,)).fetchone()
    c.close()
    if not row: raise HTTPException(404, "COMPENSATION_NOT_FOUND")
    return dict(row)


@router.post("/compensation")
def create_compensation(payload: dict = Body(...), authorization: str = Header(None)):
    user = _require_user(authorization, EDITOR_ROLES)
    c = conn(); parcel = _parcel_context(c, int(payload.get("parcel_id")), payload.get("project_id"))
    project_id = str(parcel["project_id"])
    values = {name: _amount(payload.get(name), name) for name in ("land_compensation", "structure_compensation", "crop_tree_compensation", "livelihood_compensation", "rr_compensation", "other_compensation")}
    total = sum(values.values()); paid = _amount(payload.get("amount_paid", payload.get("paid_amount", 0)), "amount_paid")
    if paid > total: raise HTTPException(400, "amount_paid cannot exceed total assessed")
    status = payload.get("approval_status", "ASSESSED").upper()
    if status not in COMPENSATION_STATUSES: raise HTTPException(400, "Invalid compensation status")
    pending = total - paid
    if paid == total and total > 0: status = "FULLY_PAID"
    elif paid > 0: status = "PARTIALLY_PAID"
    c.execute("""INSERT INTO compensation
        (parcel_id,project_id,case_id,family_id,assessed_amount,approved_amount,paid_amount,pending_amount,status,
         land_compensation,structure_compensation,crop_tree_compensation,livelihood_compensation,rr_compensation,other_compensation,
         total_assessed,approval_status,award_reference,remarks,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (parcel["id"], project_id, payload.get("case_id"), payload.get("family_id"), total, total, paid, pending, status, values["land_compensation"], values["structure_compensation"], values["crop_tree_compensation"], values["livelihood_compensation"], values["rr_compensation"], values["other_compensation"], total, status, payload.get("award_reference"), payload.get("remarks"), _now()))
    record_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit(); c.close(); audit(user["email"], "COMPENSATION_CREATED", "compensation", json.dumps({"id": record_id, "parcel_id": parcel["id"], "total_assessed": total}))
    return {"compensation_id": record_id, "project_id": project_id, "parcel_id": parcel["id"], "total_assessed": total, "amount_paid": paid, "amount_pending": pending, "status": status}


@router.put("/compensation/{compensation_id}")
def update_compensation(compensation_id: int, payload: dict = Body(...), authorization: str = Header(None)):
    user = _require_user(authorization, EDITOR_ROLES)
    c = conn(); old = c.execute("SELECT * FROM compensation WHERE id=?", (compensation_id,)).fetchone()
    if not old: c.close(); raise HTTPException(404, "COMPENSATION_NOT_FOUND")
    component_names = ("land_compensation", "structure_compensation", "crop_tree_compensation", "livelihood_compensation", "rr_compensation", "other_compensation")
    values = {name: _amount(payload[name], name) if name in payload else float(old[name] or 0) for name in component_names}
    total = sum(values.values()); paid = _amount(payload.get("amount_paid", old["paid_amount"]), "amount_paid")
    if paid > total: raise HTTPException(400, "amount_paid cannot exceed total assessed")
    status = "FULLY_PAID" if paid == total and total > 0 else "PARTIALLY_PAID" if paid > 0 else str(payload.get("approval_status", old["approval_status"] or "ASSESSED")).upper()
    if status not in COMPENSATION_STATUSES: raise HTTPException(400, "Invalid compensation status")
    sets = ",".join(f"{name}=?" for name in component_names)
    c.execute(f"UPDATE compensation SET {sets}, assessed_amount=?, approved_amount=?, total_assessed=?, paid_amount=?, pending_amount=?, status=?, approval_status=?, award_reference=?, remarks=?, updated_at=? WHERE id=?", tuple(values.values()) + (total, total, total, paid, total-paid, status, status, payload.get("award_reference", old["award_reference"]), payload.get("remarks", old["remarks"]), _now(), compensation_id))
    c.commit(); c.close(); audit(user["email"], "COMPENSATION_UPDATED", "compensation", json.dumps({"id": compensation_id, "total_assessed": total, "amount_paid": paid}))
    return {"compensation_id": compensation_id, "total_assessed": total, "amount_paid": paid, "amount_pending": total-paid, "status": status}


@router.get("/families/project/{project_id}")
@router.get("/projects/{project_id}/families")
def families_by_project(project_id: str, authorization: str = Header(None)):
    _require_user(authorization, EDITOR_ROLES)
    c = conn()
    if not c.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone(): c.close(); raise HTTPException(404, "PROJECT_NOT_FOUND")
    rows = [dict(row) for row in c.execute("SELECT f.*, p.survey_no, p.village, p.taluk FROM family_impacts f JOIN parcels p ON p.id=f.parcel_id WHERE f.project_id=? ORDER BY f.id DESC", (project_id,)).fetchall()]
    c.close(); return rows


@router.get("/families/parcel/{parcel_id}")
@router.get("/parcels/{parcel_id}/families")
def families_by_parcel(parcel_id: int, authorization: str = Header(None)):
    _require_user(authorization, EDITOR_ROLES)
    c = conn(); _parcel_context(c, parcel_id)
    rows = [dict(row) for row in c.execute("SELECT * FROM family_impacts WHERE parcel_id=? ORDER BY id DESC", (parcel_id,)).fetchall()]
    c.close(); return rows


@router.post("/families")
def create_family(payload: dict = Body(...), authorization: str = Header(None)):
    user = _require_user(authorization, EDITOR_ROLES)
    if not payload.get("family_reference"): raise HTTPException(400, "family_reference is required")
    c = conn(); parcel = _parcel_context(c, int(payload.get("parcel_id")), payload.get("project_id")); project_id = str(parcel["project_id"])
    family_id = payload.get("family_id") or "FAM-" + uuid.uuid4().hex[:8].upper()
    verification = payload.get("verification_status", "Pending")
    if verification not in FAMILY_STATUSES: raise HTTPException(400, "Invalid verification_status")
    c.execute("""INSERT INTO family_impacts
      (family_id,project_id,parcel_id,case_id,family_reference,members_count,affected,displaced,vulnerable,livelihood_affected,housing_affected,agricultural_affected,employment_affected,rr_required,rr_status,resettlement_status,compensation_status,verification_status,remarks,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (family_id, project_id, parcel["id"], payload.get("case_id"), payload["family_reference"], int(payload.get("members_count", 0)), int(bool(payload.get("affected", False))), int(bool(payload.get("displaced", False))), int(bool(payload.get("vulnerable", False))), int(bool(payload.get("livelihood_affected", False))), int(bool(payload.get("housing_affected", False))), int(bool(payload.get("agricultural_affected", False))), int(bool(payload.get("employment_affected", False))), int(bool(payload.get("rr_required", False))), payload.get("rr_status", "Not Required"), payload.get("resettlement_status", "Not Started"), payload.get("compensation_status", "NOT_ASSESSED"), verification, payload.get("remarks"), _now()))
    c.commit(); c.close(); audit(user["email"], "FAMILY_CREATED", "family", json.dumps({"family_id": family_id, "project_id": project_id, "parcel_id": parcel["id"]}))
    return {"family_id": family_id, "project_id": project_id, "parcel_id": parcel["id"], "verification_status": verification}


@router.put("/families/{family_id}")
def update_family(family_id: str, payload: dict = Body(...), authorization: str = Header(None)):
    user = _require_user(authorization, EDITOR_ROLES)
    c = conn(); old = c.execute("SELECT * FROM family_impacts WHERE family_id=?", (family_id,)).fetchone()
    if not old: c.close(); raise HTTPException(404, "FAMILY_NOT_FOUND")
    allowed = {"members_count", "affected", "displaced", "vulnerable", "livelihood_affected", "housing_affected", "agricultural_affected", "employment_affected", "rr_required", "rr_status", "resettlement_status", "compensation_status", "verification_status", "remarks"}
    changes = {key: payload[key] for key in allowed if key in payload}
    if "verification_status" in changes and changes["verification_status"] not in FAMILY_STATUSES: raise HTTPException(400, "Invalid verification_status")
    if "compensation_status" in changes and str(changes["compensation_status"]).upper() not in COMPENSATION_STATUSES: raise HTTPException(400, "Invalid compensation_status")
    if not changes: raise HTTPException(400, "No supported fields to update")
    sets = ",".join(f"{key}=?" for key in changes); c.execute(f"UPDATE family_impacts SET {sets},updated_at=? WHERE family_id=?", tuple(changes.values()) + (_now(), family_id)); c.commit(); c.close()
    audit(user["email"], "FAMILY_UPDATED", "family", json.dumps({"family_id": family_id, "changes": changes}, default=str)); return {"family_id": family_id, "updated": list(changes)}


@router.get("/satellite/project/{project_id}")
@router.get("/projects/{project_id}/satellite")
def satellite_by_project(project_id: str, authorization: str = Header(None)):
    _require_user(authorization, EDITOR_ROLES)
    c = conn()
    if not c.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone(): c.close(); raise HTTPException(404, "PROJECT_NOT_FOUND")
    rows = [dict(row) for row in c.execute("SELECT s.*, p.survey_no, p.village FROM satellite_evidence s JOIN parcels p ON p.id=s.parcel_id WHERE s.project_id=? ORDER BY s.observation_date DESC, s.id DESC", (project_id,)).fetchall()]
    c.close(); return rows


@router.get("/satellite/parcel/{parcel_id}")
@router.get("/parcels/{parcel_id}/satellite")
def satellite_by_parcel(parcel_id: int, authorization: str = Header(None)):
    _require_user(authorization, EDITOR_ROLES)
    c = conn(); _parcel_context(c, parcel_id)
    rows = [dict(row) for row in c.execute("SELECT * FROM satellite_evidence WHERE parcel_id=? ORDER BY observation_date DESC, id DESC", (parcel_id,)).fetchall()]
    c.close(); return rows


@router.post("/satellite")
def create_satellite(payload: dict = Body(...), authorization: str = Header(None)):
    user = _require_user(authorization, EDITOR_ROLES)
    change_status = payload.get("change_status", "NO_SIGNIFICANT_CHANGE")
    if change_status not in SATELLITE_CHANGES: raise HTTPException(400, "Invalid change_status")
    confidence = payload.get("confidence")
    if confidence is not None and not 0 <= float(confidence) <= 1: raise HTTPException(400, "confidence must be between 0 and 1")
    c = conn(); parcel = _parcel_context(c, int(payload.get("parcel_id")), payload.get("project_id")); project_id = str(parcel["project_id"])
    evidence_id = "SAT-" + uuid.uuid4().hex[:10].upper()
    c.execute("""INSERT INTO satellite_evidence
      (evidence_id,project_id,parcel_id,baseline_date,current_date,before_image_url,after_image_url,source,change_status,confidence,observation_date,verification_status,field_verification_status,notes,synthetic_flag,created_by,updated_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (evidence_id, project_id, parcel["id"], payload.get("baseline_date"), payload.get("current_date"), payload.get("before_image_url"), payload.get("after_image_url"), payload.get("source"), change_status, confidence, payload.get("observation_date"), payload.get("verification_status", "Pending"), payload.get("field_verification_status", "Pending"), payload.get("notes"), int(bool(payload.get("synthetic_flag", True))), user["email"], _now()))
    c.commit(); c.close(); audit(user["email"], "SATELLITE_EVIDENCE_CREATED", "satellite", json.dumps({"evidence_id": evidence_id, "parcel_id": parcel["id"], "change_status": change_status}))
    return {"evidence_id": evidence_id, "project_id": project_id, "parcel_id": parcel["id"], "change_status": change_status, "verification_status": payload.get("verification_status", "Pending")}


@router.put("/satellite/{evidence_id}")
def update_satellite(evidence_id: str, payload: dict = Body(...), authorization: str = Header(None)):
    user = _require_user(authorization, EDITOR_ROLES)
    c = conn(); old = c.execute("SELECT * FROM satellite_evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
    if not old: c.close(); raise HTTPException(404, "SATELLITE_EVIDENCE_NOT_FOUND")
    changes = {key: payload[key] for key in ("change_status", "verification_status", "field_verification_status", "notes", "confidence") if key in payload}
    if "change_status" in changes and changes["change_status"] not in SATELLITE_CHANGES: raise HTTPException(400, "Invalid change_status")
    if "confidence" in changes and not 0 <= float(changes["confidence"]) <= 1: raise HTTPException(400, "confidence must be between 0 and 1")
    if not changes: raise HTTPException(400, "No supported fields to update")
    sets = ",".join(f"{key}=?" for key in changes); c.execute(f"UPDATE satellite_evidence SET {sets},updated_at=? WHERE evidence_id=?", tuple(changes.values()) + (_now(), evidence_id)); c.commit(); c.close()
    audit(user["email"], "SATELLITE_EVIDENCE_UPDATED", "satellite", json.dumps({"evidence_id": evidence_id, "changes": changes}, default=str)); return {"evidence_id": evidence_id, "updated": list(changes)}
