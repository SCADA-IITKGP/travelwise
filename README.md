# TravelWise — Travel & Expense Policy Agent

Travel and expense workflow application with a React interface, FastAPI, policy retrieval, expense conversion, published FX reference rates, SQLite traces, Docker and Kubernetes/OpenShift manifests.

## Quick start
Python 3.10+ and Node.js 22+:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --port 8000
```
Second terminal:
```bash
cd frontend
npm install
npm run dev
```
API docs: http://localhost:8000/docs ; React UI: http://localhost:5173

Default `LLM_MODE=mock` runs without a key. It does not generate hosted-model answers. Company travel and expense records are not connected until an approved corporate system and credentials are configured.

## Published currency rates
The Live FX Rates tab and expense conversion use the latest published reference rates from [Frankfurter](https://frankfurter.dev/). The backend records provider timestamps, caches results for 15 minutes, retries briefly, serves a cached rate for up to 24 hours during provider outages, and reports stale data and provider health in Monitoring. API requests are limited to 120 per client per minute in the single-process deployment. These are published reference rates, not live market quotes.

Expense eligibility checks require approved policy documents in `data/policies`. Supported source files are `.md`, `.txt`, `.html`, `.htm`, `.pdf` and `.docx`. Compose mounts this folder read-only so policy updates are visible to the running API. Without approved documents, the application converts the amount when possible and returns `approved_policy_required`; it does not apply invented grade limits.

### Document ingestion and retrieval
Use **Ingest approved policy document** in the UI to add a source document to the selected organization, or post a multipart file to `POST /api/v1/policies/ingest` with an `organization_id` field. Uploads are limited to 20 MB and stored under the persistent `data/ingested_policies/<organization>/` directory (in Compose, inside the `appdata` volume). The service extracts text, splits it into clauses and bounded overlapping chunks, builds TF-IDF vectors, and uses cosine similarity plus lexical overlap for retrieval. Indexes refresh when source files change; policy questions pass the retrieved evidence to the configured response model with source citations. PDF extraction uses pypdf; scanned PDFs need OCR before ingestion. Only approved, readable policy sources should be ingested.

The supplied GlobalTech corpus is synthetic test material. The project includes DOCX copies of the 200 unique documents in batches 06–10 and the validated 06–10 metadata catalogue; the CSV is the canonical ingestion catalogue. The guide describes a 500-document, 10-batch corpus, so batches 01–05 are still needed before the full corpus is present. The 06–09 validation report is a stale/inconsistent subset (174 rows and failed overall validation); use the 06–10 report (200 unique IDs, passing) for this package. Retrieval citations use metadata document IDs and retain title, batch, jurisdiction, version and effective date. Do not present this fictional corpus as real company policy.

Evaluation runners accept `organization_id` and multiple `expected_citations` per case. The repository's `evaluation/gold_cases.json` currently has five starter questions; add the agreed 50+20 reviewed questions there when they are provided, with `organization_id: "globaltech"` and citations that match the synthetic corpus where applicable. No questions have been fabricated to inflate the gold set.

### Multiple organizations and policy clauses
Place each organization's approved `.md` or `.txt` policies in a separate folder such as `data/policies/acme/` or `data/policies/contoso/`. The UI organization selector scopes policy search to the selected folder; legacy files directly in `data/policies` map to `default`. Markdown headings, numbered or bulleted items, and blank-line separated paragraphs are indexed as clauses. The Policy Status view reports progress toward a 500-clause target per organization. Supply approved source material to meet that target; the app does not invent policy rules. `GET /api/v1/policies/organizations` lists configured organizations, and `GET /api/v1/policies/status?organization_id=acme` reports that organization's document and clause counts.

## Hosted Qwen endpoint
For the supplied group 046–065 connection, set the group key in the local, ignored `.env` and set `LLM_CA_CERT_HOST_PATH` to the assigned `vm04-ca.crt` file. Do not commit API keys. If a key has been exposed outside the authorized group, rotate it with the coordinator before use. The hosted overlay enforces a separate CA mount:
```env
LLM_MODE=hosted
LLM_BASE_URL=https://103.42.50.41:1034/v1
LLM_MODEL=Qwen/Qwen3-8B
LLM_CA_CERT_HOST_PATH=C:/Users/YOUR_WINDOWS_USER/Downloads/vm04-ca.crt
LLM_MAX_TOKENS=512
```
Then run `docker compose -f docker-compose.yml -f docker-compose.hosted.yml up --build -d`. The overlay mounts the CA file read-only, preserves HTTPS verification, serializes model requests, limits this app to 55 provider calls per minute, and retries 429/503 responses after 2, 4 and 8 seconds. Run `docker compose -f docker-compose.yml -f docker-compose.hosted.yml exec api python -m scripts.check_hosted_api` to verify the key, CA and model through `/models` without printing credentials. Keep `.env` untracked; provider-side limits remain authoritative. The CA must match the endpoint group; never disable certificate verification to work around a mismatch.

## Docker
```bash
docker compose up --build
```
UI: port 8501; API: port 8000. SQLite is suitable for a single-instance demo only. Use managed PostgreSQL and durable object storage for multi-replica production.

Compose defaults to `LLM_MODE=mock` and works without a `.env` file. To configure a hosted provider, copy `.env.example` to `.env` and fill in the confirmed HTTPS endpoint and credentials. `.env` is excluded from the Docker build context and Git.

If port 8501 is already in use, set `UI_PORT=8502` in `.env` (or your shell) before starting Compose.

Stop the services with `docker compose down`; keep the `appdata` volume to retain SQLite traces. Use `docker compose down -v` only when you also want to erase that data.

## Kubernetes / OpenShift
Build and push the API and React UI images:
```bash
docker build -f deployment/Dockerfile.backend -t YOUR_REGISTRY/ai-travel-expense:1.0 .
docker build -f deployment/Dockerfile.frontend -t YOUR_REGISTRY/ai-travel-expense-ui:1.0 .
docker push YOUR_REGISTRY/ai-travel-expense:1.0
docker push YOUR_REGISTRY/ai-travel-expense-ui:1.0
```
Replace both image names in `deployment/k8s.yaml`, configure the secret, then:
```bash
kubectl apply -f deployment/k8s.yaml
oc apply -f deployment/openshift-route.yaml
```
The Route exposes the UI. Adapt namespace, image pull secret, TLS, storage and identity configuration to your cluster.

## Week 1 gate — do this before agent development
1. Review and freeze `evaluation/gold_cases.json`.
2. Add the agreed 70 domain-reviewed questions (50 + 20). Extend to 100 only if the project rubric requires it.
3. Run `python -m evaluation.run_baseline`.
4. Commit the dataset and baseline output; record commit hash.
5. Only then change prompts/agent code.
The repository currently contains five starter cases. The 70 agreed questions have not yet been added; provide that set before treating the evaluation as complete.

Run evaluation:
```bash
python -m evaluation.run_evaluation
pytest -q
```

## API examples
```bash
curl "http://localhost:8000/api/v1/market/fx?base=USD&quote=INR&amount=100"
curl -X POST http://localhost:8000/api/v1/expenses/validate -H "Content-Type: application/json" -d '{"employee_id":"EMP1001","grade":"M6","category":"hotel","amount":100,"currency":"USD","nights":1}'
curl http://localhost:8000/api/v1/market/status
```

## Six workstreams
1. Domain spec & evaluation: scope, gold-answer set, refusal policy.
2. Prompt engineering: prompt strategies, structured output, failure analysis.
3. RAG/retrieval: chunking, hybrid search, reranking, citations.
4. Agent orchestration & tools: planner/executor/critic, tools, state and memory.
5. Observability & safety: traces, failure taxonomy, injection and PII tests.
6. Front-end & deployment: UI, containerisation, rate limiting, caching and demo.
For five members, combine domain specification and prompt engineering.

## Failure taxonomy
`retrieval_failure`, `hallucination_or_unsupported`, `tool_failure`, `orchestration_failure`, `structured_output_failure`, `policy_validation_failure`, `security_prompt_injection`, `pii_exposure`, `latency_or_timeout`.

## Production hardening
This is an academic starter, not a certified expense/payment system. Add SSO/OIDC, RBAC, tenant isolation, approved policy governance, encrypted object storage, malware scanning, robust OCR, database migrations, secret manager, provider-side quota enforcement, immutable audit storage and security review before enterprise use. Use synthetic/de-identified data only.


## Hosted API security and connectivity check

The API adapter in `backend/llm.py` supports an OpenAI-compatible
`POST /chat/completions` contract and requires HTTPS. The endpoint shared in
the chat used `http://` even though it specified port 443; do not send a key
to that URL until the programme confirms the official HTTPS endpoint and API
contract. Port 443 does not itself enable TLS.

After the programme confirms the endpoint, set the replacement credential
only in your local `.env` (never in Git), then run:

```bash
python -m scripts.check_hosted_api
```

If the provider is not OpenAI-compatible, obtain its API documentation and
adapt only `backend/llm.py`. Do not disable your operating-system firewall.
Rotate any credential that has been pasted into chat, email, screenshots or
source control.
