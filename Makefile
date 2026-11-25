api:
	uvicorn backend.main:app --reload --port 8000
ui:
	streamlit run frontend/app.py
test:
	pytest -q
baseline:
	python -m evaluation.run_baseline
evaluate:
	python -m evaluation.run_evaluation
