import sqlite3, json, uuid
from datetime import datetime, timezone
from .config import DATABASE_PATH

def connect():
    con = sqlite3.connect(DATABASE_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS traces (trace_id TEXT PRIMARY KEY, created_at TEXT, query TEXT, employee_id TEXT, status TEXT, answer TEXT, steps INTEGER, latency_ms REAL, failure_category TEXT, trace_json TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS travel_requests (request_id TEXT PRIMARY KEY, created_at TEXT, payload TEXT, status TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS approvals (approval_id TEXT PRIMARY KEY, created_at TEXT, payload TEXT, status TEXT)")

def save_trace(d):
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO traces VALUES (?,?,?,?,?,?,?,?,?,?)",
          (d["trace_id"],d["created_at"],d["query"],d["employee_id"],d["status"],d["answer"],d["steps"],d["latency_ms"],d.get("failure_category"),json.dumps(d,ensure_ascii=False)))

def list_traces(limit=100):
    with connect() as con:
        rows=con.execute("SELECT * FROM traces ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    return [dict(r) for r in rows]

def get_trace(tid):
    with connect() as con:
        row=con.execute("SELECT * FROM traces WHERE trace_id=?",(tid,)).fetchone()
    return dict(row) if row else None

def save_travel(payload):
    rid="TRV-"+uuid.uuid4().hex[:10].upper()
    with connect() as con:
        con.execute("INSERT INTO travel_requests VALUES (?,?,?,?)",(rid,datetime.now(timezone.utc).isoformat(),json.dumps(payload),"submitted"))
    return rid

def save_approval(payload):
    aid="APR-"+uuid.uuid4().hex[:10].upper()
    with connect() as con:
        con.execute("INSERT INTO approvals VALUES (?,?,?,?)",(aid,datetime.now(timezone.utc).isoformat(),json.dumps(payload),"pending_human_review"))
    return aid
