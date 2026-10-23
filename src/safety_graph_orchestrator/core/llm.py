import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from safety_graph_orchestrator.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class MockOllamaChatModel:
    """Deterministic mock provider mimicking Ollama responses.
    
    Ensures CI/CD pipelines, offline developer laptops, and unit tests
    execute robustly without hard dependency on a live Ollama daemon.
    """

    def __init__(self, model_name: str = "llama3.2"):
        self.model_name = model_name

    def invoke(self, messages: List[BaseMessage] | str, **kwargs: Any) -> AIMessage:
        prompt_text = str(messages)
        content = self._generate_heuristic_response(prompt_text)
        return AIMessage(content=content)

    def _generate_heuristic_response(self, prompt: str) -> str:
        prompt_lower = prompt.lower()

        # Heuristic 5 Whys RCA response
        if "5 whys" in prompt_lower or "root cause" in prompt_lower:
            return json.dumps({
                "incident_summary": "High-pressure mud line barrier breach and toxic gas exposure risk during drilling operations.",
                "direct_cause": "Flange seal on choke manifold ruptured during pressure pulsation.",
                "contributing_factors": [
                    "Flange bolts were torqued without calibrated torque wrench",
                    "H2S fixed sensor was tagged out for recalibration without secondary handheld detector",
                    "Operations resumed without documented inspection sign-off"
                ],
                "five_whys": [
                    {
                        "level": 1,
                        "question": "Why did the choke manifold develop a weeping leak at 4,800 PSI?",
                        "answer": "The ring joint gasket (BX-154) was pinched and did not seat flush against the flange face.",
                        "causal_category": "Equipment Integrity & Mechanical Failure",
                        "confidence_score": 0.95
                    },
                    {
                        "level": 2,
                        "question": "Why was the ring joint gasket pinched during installation?",
                        "answer": "Uneven torque sequence was applied across the 8-bolt pattern during late-night maintenance.",
                        "causal_category": "Procedural Adherence & SOP Gap",
                        "confidence_score": 0.92
                    },
                    {
                        "level": 3,
                        "question": "Why was an uneven torque sequence used instead of SOP-042 torque procedure?",
                        "answer": "The mechanical crew used an uncalibrated impact gun because the hydraulic torque unit was locked in the tool room.",
                        "causal_category": "Procedural Adherence & SOP Gap",
                        "confidence_score": 0.90
                    },
                    {
                        "level": 4,
                        "question": "Why was work performed with uncalibrated tools rather than retrieving the approved unit?",
                        "answer": "Pressure to maintain drilling schedule prior to shift change led to unauthorized shortcut.",
                        "causal_category": "Human Factors (Situational Awareness / Fatigue)",
                        "confidence_score": 0.88
                    },
                    {
                        "level": 5,
                        "question": "Why did supervisor verification fail to catch the uncalibrated make-up?",
                        "answer": "Shift handover lacked a standardized QA/QC barrier sign-off checklist and SWA verification protocol.",
                        "causal_category": "Management Systems & Resource Allocation",
                        "confidence_score": 0.94
                    }
                ],
                "root_cause_statement": "Systemic failure in shift handover governance and QA/QC verification permitting uncalibrated make-up of high-pressure well control barriers under operational schedule pressure.",
                "primary_category": "Management Systems & Resource Allocation",
                "systemic_failure_pattern": "Schedule pressure superseding procedural verification of critical pressure-containing barriers."
            })

        # Default fallback
        return json.dumps({
            "status": "ANALYZED",
            "findings": ["Procedural variance detected", "Barrier verification incomplete"]
        })


def is_ollama_available(base_url: str = settings.ollama_base_url) -> bool:
    """Check if the local Ollama daemon is reachable."""
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def get_llm():
    """Factory to acquire either ChatOllama or MockOllamaChatModel.
    
    If Ollama is available, instantiates `ChatOllama` from langchain_ollama.
    Otherwise, gracefully falls back to `MockOllamaChatModel` if configured.
    """
    if is_ollama_available(settings.ollama_base_url):
        try:
            from langchain_ollama import ChatOllama
            logger.info("Connecting to local Ollama at %s using model %s", settings.ollama_base_url, settings.ollama_model)
            return ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=settings.llm_temperature,
            )
        except Exception as e:
            logger.warning("Failed to initialize ChatOllama: %s", e)
    
    if settings.use_mock_llm_fallback:
        logger.info("Using enterprise deterministic MockOllamaChatModel fallback")
        return MockOllamaChatModel(model_name=settings.ollama_model)
    
    raise ConnectionError(
        f"Ollama server is unavailable at {settings.ollama_base_url} and mock fallback is disabled."
    )
