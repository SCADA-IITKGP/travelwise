from pydantic import BaseModel, Field
from typing import Optional, Literal

class TravelContext(BaseModel):
    destination_country: Optional[str] = Field(default=None, max_length=100)
    employee_grade: Optional[str] = Field(default=None, max_length=32)
    trip_type: Optional[str] = Field(default=None, max_length=32)

class ChatRequest(BaseModel):
    query: str = Field(min_length=3, max_length=5000)
    employee_id: str = "DEMO-EMP"
    grade: Optional[str] = None
    organization_id: str = Field(default="default", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    travel_context: Optional[TravelContext] = None
    model: Optional[str] = Field(default=None, max_length=128)
    session_id: Optional[str] = Field(default=None, max_length=64)
    prompt_strategy: Literal["v1_baseline", "v2_grounded", "v3_structured_critic"] = "v3_structured_critic"


class StructuredAgentOutput(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    recommended_action: Literal["answer", "clarify", "abstain", "refuse", "escalate"] = "answer"
    requires_human_approval: bool = False


class ModelSelectionRequest(BaseModel):
    selection: Optional[str] = Field(default=None, max_length=128)
    mode: Optional[Literal["mock", "hosted"]] = None
    model: Optional[str] = Field(default=None, max_length=128)
    base_url: Optional[str] = Field(default=None, max_length=500)
    api_key: Optional[str] = Field(default=None, max_length=500)
    ca_cert_file: Optional[str] = Field(default=None, max_length=500)


class EmbeddingConfigRequest(BaseModel):
    mode: Optional[Literal["tfidf", "hybrid", "hosted"]] = None
    model: Optional[str] = Field(default=None, max_length=128)
    base_url: Optional[str] = Field(default=None, max_length=500)
    api_key: Optional[str] = Field(default=None, max_length=500)
    ca_cert_file: Optional[str] = Field(default=None, max_length=500)


class PipelineDiagnosticRequest(BaseModel):
    query: str = Field(default="What receipts are required for expense reimbursement?", min_length=3, max_length=2000)
    organization_id: str = Field(default="globaltech", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    travel_context: Optional[TravelContext] = None

class TravelRequest(BaseModel):
    employee_id: str
    grade: str
    origin: str
    destination: str
    start_date: str
    end_date: str
    purpose: str
    estimated_budget: float = Field(gt=0)

class ExpenseValidationRequest(BaseModel):
    employee_id: str
    grade: str
    organization_id: str = Field(default="default", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    category: Literal["hotel", "meal", "flight", "local_transport", "other"]
    amount: float = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    nights: int = Field(default=1, ge=1)
    receipt_text: Optional[str] = None

class ReceiptTextRequest(BaseModel):
    text: str = Field(min_length=3, max_length=20000)

class ApprovalRequest(BaseModel):
    claim_id: str
    employee_id: str
    recommended_amount: float = Field(ge=0)
    reason: str
