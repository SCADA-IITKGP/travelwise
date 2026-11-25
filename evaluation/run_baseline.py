"""Week 1 retrieval-only baseline. Freeze dataset and save baseline before agent coding."""
import json,pathlib,subprocess,time
from backend.rag import retrieve
from backend.safety import inspect_query
ROOT=pathlib.Path(__file__).resolve().parents[1]
cases=json.loads((ROOT/"evaluation/gold_cases.json").read_text()); out=[]
for c in cases:
 t=time.perf_counter(); blocked=inspect_query(c["query"]); org=c.get("organization_id","default"); docs=[] if blocked else retrieve(c["query"],c.get("grade","M6"),organization_id=org)
 out.append({"id":c["id"],"organization_id":org,"retrieved_ids":[d["id"] for d in docs],"blocked":bool(blocked),"latency_ms":round((time.perf_counter()-t)*1000,2)})
try: commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
except Exception: commit="not-in-git-yet"
result={"dataset_version":"v1-starter-freeze-me-after-review","git_commit":commit,"mode":"retrieval_only_baseline","results":out}
dest=ROOT/"evaluation/results"; dest.mkdir(exist_ok=True); (dest/"baseline.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
