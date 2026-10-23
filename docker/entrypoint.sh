#!/bin/sh
set -e

# Ensure persistence directories exist
mkdir -p /app/.chromadb /app/reports

echo "Starting Safety Graph Orchestrator..."
echo "Ollama URL: ${SAFETY_GRAPH_OLLAMA_BASE_URL:-http://localhost:11434}"
echo "Model: ${SAFETY_GRAPH_OLLAMA_MODEL:-llama3.2:latest}"

exec "$@"
