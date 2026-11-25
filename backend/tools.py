import re, hashlib
from .rag import retrieve, normalize_organization
def policy_search(query,grade,organization_id="default"):
    org=normalize_organization(organization_id)
    docs=retrieve(query,grade,organization_id=org)
    return {"documents":docs,"citations":[d["id"] for d in docs]}
def receipt_extract(text):
    m=re.search(r"(?:INR|Rs\.?|₹)\s*([0-9,]+(?:\.\d{1,2})?)",text,re.I)
    date=re.search(r"\b(20\d{2}[-/]\d{2}[-/]\d{2})\b",text)
    amount=float(m.group(1).replace(",","")) if m else None
    return {"merchant":text.strip().splitlines()[0][:100] if text.strip() else "Unknown",
      "amount":amount,"date":date.group(1) if date else None,"currency":"INR",
      "fingerprint":hashlib.sha256(re.sub(r"\s+"," ",text.lower()).encode()).hexdigest(),
      "missing_fields":[k for k,v in {"amount":amount,"date":date.group(1) if date else None}.items() if v is None]}
def expense_validate(category,amount,grade,nights=1,organization_id="default"):
    return {"category":category,"claimed_amount":float(amount),"eligible_amount":None,
      "organization_id":normalize_organization(organization_id),
      "status":"approved_policy_required","note":"No approved company policy is configured. Eligibility cannot be determined."}
def approval_draft(claim_id,employee_id,recommended_amount,reason):
    return {"claim_id":claim_id,"employee_id":employee_id,"recommended_amount":recommended_amount,"reason":reason,"status":"pending_human_review"}
