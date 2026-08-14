.PHONY: test api web schema
PYTHONPATH := packages/sequence-ir:packages/physics:packages/recon:services/api
export PYTHONPATH
test:
	python -m pytest
api:
	uvicorn mrqlab_api.main:app --app-dir services/api --reload
web:
	npm --prefix apps/web run dev
schema:
	python packages/sequence-ir/export_schema.py > packages/sequence-ir/sequence-ir.schema.json
