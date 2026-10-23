# Docker Deployment Guide - Safety Graph Orchestrator

This directory contains containerization assets for building and deploying the Safety Graph Orchestrator alongside local Ollama LLM services.

## Architecture

The containerized stack consists of two services:
1. **`orchestrator`**: Python 3.12 multi-stage slim image running the FastAPI web operations portal, LangGraph workflow execution engine, deterministic rules engine, and ChromaDB vector store.
2. **`ollama`**: Official Ollama container for serving local LLM inference (`llama3.2:latest`) with persistent model weights.

## Quickstart

### Running from Project Root:
```bash
docker compose up --build -d
```

### Running from `docker/` Directory:
```bash
docker compose -f docker/docker-compose.yml up --build -d
```

### Pulling the Recommended Model:
If Ollama is started for the first time without a local volume, download `llama3.2`:
```bash
docker exec -it safety-graph-ollama ollama pull llama3.2:latest
```

## Persistent Volumes

- `chroma_data`: Stores ChromaDB vector embeddings and indexed SOP documents.
- `reports_data`: Stores generated executive HTML and JSON audit reports.
- `ollama_models`: Persists downloaded LLM model weights across container restarts.

## Health Checks

The orchestrator service includes a built-in healthcheck polling `/api/v1/rules`:
```bash
docker inspect --format='{{json .State.Health.Status}}' safety-graph-orchestrator
```
