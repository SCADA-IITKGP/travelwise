from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException,Query,UploadFile,File,Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from .schemas import ChatRequest,TravelRequest,ExpenseValidationRequest,ReceiptTextRequest,ApprovalRequest,ModelSelectionRequest,EmbeddingConfigRequest,PipelineDiagnosticRequest
from . import store,tools,market_data,rate_limit,embeddings,evidently_monitor
from .agents import run_agent
from .llm import status as llm_status, select_model as llm_select_model
from .config import INGESTION_DIR,MAX_AGENT_STEPS
from .rag import SUPPORTED_EXTENSIONS,cache_status,extract_text,normalize_organization
import json
import re
from pathlib import Path

@asynccontextmanager
async def lifespan(_app:FastAPI):
    store.init_db()
    yield

app=FastAPI(title="Travel & Expense Policy Agent",version="1.1.0",
 description="Travel and expense workflows with published FX reference data, policy retrieval and monitoring.",
 lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
app.add_middleware(rate_limit.InMemoryRateLimitMiddleware)
@app.get("/health")
def health():
    hosted=llm_status()
    return {"status":"ok","llm_mode":hosted["mode"],"max_agent_steps":MAX_AGENT_STEPS,
        "market_data":market_data.status(),"rate_limit":rate_limit.status(),
        "hosted_model":hosted,"embeddings":embeddings.status(),"rag_cache":cache_status()}

@app.get("/api/v1/llm/status")
def hosted_model_status(): return llm_status()

@app.get("/api/v1/llm/models")
def hosted_models():
    st=llm_status()
    return {"active_selection":st["active_selection"],"models":st["available_models"],"status":st}

@app.post("/api/v1/llm/select")
def select_llm(req:ModelSelectionRequest):
    try:
        return llm_select_model(
            selection=req.selection,
            mode=req.mode,
            model=req.model,
            base_url=req.base_url,
            api_key=req.api_key,
            ca_cert_file=req.ca_cert_file,
        )
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.get("/api/v1/embeddings/status")
def embedding_status(): return embeddings.status()

@app.post("/api/v1/embeddings/config")
def configure_embeddings(req:EmbeddingConfigRequest):
    try:
        return embeddings.configure(
            mode=req.mode,
            base_url=req.base_url,
            api_key=req.api_key,
            model=req.model,
            ca_cert_file=req.ca_cert_file,
        )
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.post("/api/v1/ai/chat")
async def chat(req:ChatRequest):
    travel_context=req.travel_context.model_dump(exclude_none=True) if req.travel_context else None
    trace=await run_agent(
        req.query,
        req.employee_id,
        req.grade,
        req.organization_id,
        travel_context=travel_context,
        model_override=req.model,
        session_id=req.session_id,
        prompt_strategy=req.prompt_strategy,
    )
    store.save_trace(trace)
    return trace
@app.post("/api/v1/travel/requests")
def travel(req:TravelRequest):
    rid=store.save_travel(req.model_dump()); return {"request_id":rid,"status":"submitted"}
@app.post("/api/v1/expenses/validate")
async def validate(req:ExpenseValidationRequest):
    try:
        fx=await market_data.get_rate(req.currency,"INR")
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except market_data.MarketDataUnavailable as exc:
        raise HTTPException(503,detail=str(exc),headers={"Retry-After":str(exc.retry_after_seconds)}) from exc
    amount_inr=round(req.amount*fx["rate"],2)
    try:
        organization_id=normalize_organization(req.organization_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    return {"employee_id":req.employee_id,"organization_id":organization_id,"source_amount":req.amount,"source_currency":req.currency.upper(),
      "exchange_rate":fx["rate"],"amount_inr":amount_inr,"fx":fx,
      **tools.expense_validate(req.category,amount_inr,req.grade,req.nights,organization_id),
      "final_decision":"approved_policy_required"}

@app.get("/api/v1/market/fx")
async def fx_rate(base:str=Query(default="USD"),quote:str=Query(default="INR"),amount:float=Query(default=1,gt=0)):
    try:
        result=await market_data.get_rate(base,quote)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except market_data.MarketDataUnavailable as exc:
        raise HTTPException(503,detail=str(exc),headers={"Retry-After":str(exc.retry_after_seconds)}) from exc
    return {**result,"amount":amount,"converted_amount":round(amount*result["rate"],2)}

@app.get("/api/v1/market/status")
def market_status(): return market_data.status()

@app.get("/api/v1/policies/status")
def policy_status(organization_id:str="default"):
    from .rag import load_docs
    try:
        org=normalize_organization(organization_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    docs=load_docs(org)
    clause_count=len(docs)
    documents={d["document_id"]:d for d in docs}
    corpus_batches=sorted({d["batch"] for d in docs if d.get("batch")})
    return {"organization_id":org,"configured":bool(docs),"document_count":len(documents),
      "clause_count":clause_count,"minimum_clause_target":500,"minimum_clause_target_met":clause_count>=500,
      "source":f"data/policies/{org}","synthetic_document_count":sum(1 for d in documents.values() if d.get("synthetic")),
      "batches":corpus_batches,"full_corpus_expected_documents":500 if org=="globaltech" else None,
      "corpus_complete":len(documents)>=500 if org=="globaltech" else None,
      "status":"ready" if docs else "no_approved_policy_documents"}
@app.get("/api/v1/policies/organizations")
def policy_organizations():
    from .rag import organizations
    return {"organizations":organizations()}
@app.post("/api/v1/policies/ingest")
async def ingest_policy(file:UploadFile=File(...),organization_id:str=Form("default")):
    """Store an approved source document for offline indexing and online retrieval."""
    try:
        org=normalize_organization(organization_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    filename=(file.filename or "").replace("\\","/").split("/")[-1].strip()
    if not filename or filename in {".",".."} or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,159}",filename):
        raise HTTPException(422,"Use a filename with letters, numbers, spaces, dots, underscores or hyphens.")
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415,"Supported files: TXT, Markdown, HTML, PDF and DOCX.")
    data=await file.read(20*1024*1024+1)
    if len(data)>20*1024*1024:
        raise HTTPException(413,"Document size exceeds the 20 MB limit.")
    if not data:
        raise HTTPException(422,"The uploaded document is empty.")
    directory=INGESTION_DIR/org
    directory.mkdir(parents=True,exist_ok=True)
    destination=directory/filename
    if destination.exists():
        raise HTTPException(409,"A document with this name already exists for this organization.")
    destination.write_bytes(data)
    try:
        text=extract_text(destination)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(422,f"Could not extract text from this document: {exc}") from exc
    if not text.strip():
        destination.unlink(missing_ok=True)
        raise HTTPException(422,"No readable text was found in the document.")
    from .rag import load_docs
    clauses=[d for d in load_docs(org) if d["document_id"]==f"{org}/{destination.stem}"]
    return {"organization_id":org,"document_id":f"{org}/{destination.stem}","filename":filename,
            "characters":len(text),"indexed_clauses":len(clauses),"status":"ingested"}
@app.post("/api/v1/receipts/extract")
def receipt(req:ReceiptTextRequest): return tools.receipt_extract(req.text)
@app.post("/api/v1/ai/policy-search")
def policy_search(query:str,grade:str="ALL",organization_id:str="default"):
    try:
        return tools.policy_search(query,grade,organization_id)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
@app.post("/api/v1/approvals/submit")
def approval(req:ApprovalRequest):
    aid=store.save_approval(req.model_dump())
    return {"approval_id":aid,"status":"pending_human_review","message":"Recommendation sent for human review; no payment initiated."}
@app.get("/api/v1/traces")
def traces(limit:int=100): return store.list_traces(min(max(limit,1),500))
@app.get("/api/v1/traces/{trace_id}")
def trace_detail(trace_id:str):
    r=store.get_trace(trace_id)
    if not r: raise HTTPException(404,"Trace not found")
    r["trace"]=json.loads(r.pop("trace_json")); return r
@app.get("/api/v1/dashboard/analytics")
def analytics():
    rows=store.list_traces(500); n=len(rows); failures={}
    for r in rows:
        if r.get("failure_category"): failures[r["failure_category"]]=failures.get(r["failure_category"],0)+1
    ok=sum(1 for r in rows if r["status"]=="success")
    return {"total_queries":n,"successful":ok,"failed":n-ok,"success_rate":round(ok/n,3) if n else 0,
      "average_latency_ms":round(sum(r["latency_ms"] for r in rows)/n,2) if n else 0,
      "failure_taxonomy":failures,"market_data":market_data.status(),
      "rate_limit":rate_limit.status()}

@app.get("/api/v1/observability/pipeline")
def observability_pipeline():
    return evidently_monitor.pipeline_overview()

@app.post("/api/v1/observability/pipeline/test")
async def observability_pipeline_test(req:PipelineDiagnosticRequest):
    ctx=req.travel_context.model_dump(exclude_none=True) if req.travel_context else None
    return await evidently_monitor.run_pipeline_diagnostic(req.query,req.organization_id,ctx)

@app.get("/api/v1/observability/evidently/summary")
def evidently_summary(source:str=Query(default="evaluation")):
    try:
        return evidently_monitor.get_summary(source)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.post("/api/v1/observability/evidently/run")
def evidently_run(source:str=Query(default="evaluation")):
    try:
        return evidently_monitor.generate_report(source)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc

@app.get("/api/v1/observability/evidently/report",response_class=HTMLResponse)
def evidently_report_html(source:str=Query(default="evaluation")):
    try:
        return HTMLResponse(evidently_monitor.get_html_report(source))
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
