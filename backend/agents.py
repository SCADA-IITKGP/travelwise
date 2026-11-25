import time, uuid, re
from datetime import datetime,timezone
from . import tools
from .llm import generate,LLMError
from .safety import inspect_query,redact_pii
from .config import MAX_AGENT_STEPS

SYSTEM_PROMPT="""You are an enterprise travel and expense assistant. Use only supplied policy evidence.
If evidence is insufficient, say so. Do not invent policy limits. Distinguish recommendations from approvals.
Never approve or initiate payment. Be concise and cite policy identifiers."""

async def run_agent(query,employee_id,grade,organization_id="default"):
    start=time.perf_counter(); tid="TRC-"+uuid.uuid4().hex[:12]
    trace={"trace_id":tid,"created_at":datetime.now(timezone.utc).isoformat(),
      "query":redact_pii(query),"employee_id":employee_id,"organization_id":organization_id,"steps_log":[]}
    blocked=inspect_query(query)
    if blocked:
        trace.update(status="blocked",answer="I cannot follow instructions that attempt to override system safeguards.",
          steps=0,latency_ms=round((time.perf_counter()-start)*1000,2),failure_category=blocked)
        return trace
    try:
        low=query.lower(); plan=[]
        if any(w in low for w in ["receipt","invoice","bill","upload"]): plan.append("receipt_extract")
        if any(w in low for w in ["hotel","meal","flight","expense","claim","reimburse","policy","travel"]): plan.append("policy_search")
        if any(w in low for w in ["hotel","expense","claim","reimburse","amount","bill","invoice"]): plan.append("expense_validate")
        if not plan: plan=["policy_search"]
        plan=plan[:MAX_AGENT_STEPS]; trace["plan"]=plan; results={}
        for name in plan:
            if len(trace["steps_log"])>=MAX_AGENT_STEPS: break
            t=time.perf_counter()
            if name=="policy_search": results[name]=tools.policy_search(query,grade,organization_id)
            elif name=="receipt_extract":
                results[name]={"note":"Use /api/v1/receipts/extract with OCR text to extract receipt fields."}
            elif name=="expense_validate":
                m=re.search(r"(?:₹|INR|Rs\.?)\s*([0-9,]+(?:\.\d{1,2})?)",query,re.I)
                if m and "hotel" in low: results[name]=tools.expense_validate("hotel",float(m.group(1).replace(",","")),grade,organization_id=organization_id)
                else: results[name]={"status":"not_executed","reason":"Numeric amount and supported category required."}
            trace["steps_log"].append({"step":len(trace["steps_log"])+1,"tool":name,
              "duration_ms":round((time.perf_counter()-t)*1000,2),"status":"success"})
        docs=results.get("policy_search",{}).get("documents",[])
        failure="retrieval_failure" if "policy_search" in plan and not docs else None
        context="\n".join(f"[{d['id']}] {d['text']}" for d in docs)
        v=results.get("expense_validate",{})
        if failure:
            answer="I could not retrieve supporting policy evidence. No eligibility decision has been made; please escalate to Finance."
        else:
            answer=await generate(SYSTEM_PROMPT,f"Question: {redact_pii(query)}\nEvidence:\n{context}\nTool results: {results}")
        trace.update(status="degraded" if failure else "success",answer=answer,tool_results=results,citations=[d["id"] for d in docs],
          steps=len(trace["steps_log"]),latency_ms=round((time.perf_counter()-start)*1000,2),failure_category=failure)
    except LLMError as e:
        trace.update(status="failed",answer="Hosted model endpoint unavailable. Retry or escalate.",
          steps=len(trace["steps_log"]),latency_ms=round((time.perf_counter()-start)*1000,2),
          failure_category="tool_failure",error=str(e))
    except Exception as e:
        trace.update(status="failed",answer="The request could not be completed safely.",
          steps=len(trace["steps_log"]),latency_ms=round((time.perf_counter()-start)*1000,2),
          failure_category="orchestration_failure",error=f"{type(e).__name__}: {e}")
    return trace
