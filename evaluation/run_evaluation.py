import asyncio,json,pathlib
from backend.agents import run_agent
ROOT=pathlib.Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/"evaluation/gold_cases.json").read_text())
async def main():
 out=[]
 for c in cases:
  t=await run_agent(c["query"],"EVAL",c.get("grade","M6"),c.get("organization_id","default")); exp=c.get("expected_citations",[c.get("expected_citation")] if c.get("expected_citation") else [])
  out.append({"id":c["id"],"organization_id":c.get("organization_id","default"),"status":t["status"],"citation_ok":all(item in t.get("citations",[]) for item in exp),
    "security_ok":t["status"]=="blocked" if c.get("expected_category")=="security_block" else True,
    "latency_ms":t.get("latency_ms"),"failure_category":t.get("failure_category")})
 n=len(out); result={"dataset_version":"v1-starter","cases":n,
   "citation_pass_rate":sum(x["citation_ok"] for x in out)/n,
   "security_pass_rate":sum(x["security_ok"] for x in out)/n,"results":out}
 dest=ROOT/"evaluation/results"; dest.mkdir(exist_ok=True); (dest/"evaluation.json").write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
asyncio.run(main())
