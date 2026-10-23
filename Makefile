.PHONY: test eval serve stream demo rules threads graph docker clean lint

test:
	uv run pytest -v

eval:
	uv run safety-graph-orchestrator evaluate

serve:
	uv run safety-graph-orchestrator serve --port 8000

stream:
	uv run safety-graph-orchestrator stream --steps 8 --kick

demo:
	uv run safety-graph-orchestrator demo

rules:
	uv run safety-graph-orchestrator rules

threads:
	uv run safety-graph-orchestrator threads

graph:
	uv run safety-graph-orchestrator graph

docker:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache reports/*.html .checkpoints.db
	find . -type d -name "__pycache__" -exec rm -rf {} +
