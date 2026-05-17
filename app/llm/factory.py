from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import yaml

from app.config import AppConfig, load_app_config
from app.llm.base import AnswerGenerationResult, LLMClient, ToolChoiceResult
from app.runtime_overlays import get_format_payload, get_system_prompt_payload, get_tool_description_payload


SUPPORTED_PROVIDERS = {"openai", "gemini", "claude", "cortex"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _prompts_dir() -> Path:
    override = os.getenv("PROMPTS_DIR")
    if override:
        p = Path(override)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return PROJECT_ROOT / "prompts"

ToolName = Literal[
    "get_customer_profile",
    "get_transactions",
    "get_spending_summary",
    "get_alerts",
    "get_customer_profile_and_alerts",
    "get_full_picture",
    "compare_customers",
]


class ToolInputSchema(BaseModel):
    customer_id: str | None = Field(default=None, description="Customer ID like CUS007.")
    customer_id_a: str | None = Field(default=None, description="First customer ID for comparison requests.")
    customer_id_b: str | None = Field(default=None, description="Second customer ID for comparison requests.")
    fraud_only: bool | None = Field(default=None, description="Whether to return only fraud transactions.")
    group_by: str | None = Field(default=None, description='Grouping field for summaries, usually "category".')
    severity: str | None = Field(default=None, description="Alert severity filter if provided.")


class ToolChoiceSchema(BaseModel):
    tool_name: ToolName | None = Field(default=None, description="Best tool for the request, or null if none fits.")
    tool_input: ToolInputSchema = Field(default_factory=ToolInputSchema)
    reasoning: str = Field(
        min_length=1,
        description="Required short explanation of the tool choice in one sentence."
    )


class AnswerSchema(BaseModel):
    answer: str = Field(description="Final assistant response shown to the user.")
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence level for the grounded answer.")
    source: Literal["tool", "model"] = Field(description="Whether the answer is grounded in tools or not.")
    rationale: str | None = Field(
        default=None,
        description=(
            "Optional short rationale grounded only in the supplied tool result. "
            "Return null unless the user explicitly asks for reasoning, rationale, explanation, or why."
        ),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def load_system_prompt(config: AppConfig | None = None) -> str:
    payload = get_system_prompt_payload(config)
    if not payload:
        payload = _load_yaml(_prompts_dir() / "system.yaml")
    return str(payload.get("content") or "").strip()


def load_available_tools(config: AppConfig | None = None) -> list[str]:
    payload = get_tool_description_payload(config)
    if not payload:
        payload = _load_yaml(_prompts_dir() / "tools.yaml")
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        return []
    normalized: list[str] = []
    for tool in tools:
        if isinstance(tool, str) and tool.strip():
            normalized.append(tool)
        elif isinstance(tool, dict):
            name = tool.get("name")
            if isinstance(name, str) and name.strip():
                normalized.append(name)
    return normalized


def load_tool_descriptions(config: AppConfig | None = None) -> str:
    payload = get_tool_description_payload(config)
    if not payload:
        payload = _load_yaml(_prompts_dir() / "tools.yaml")
    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        return ""
    lines: list[str] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name", "")
        desc = tool.get("description", "")
        lines.append(f"TOOL: {name}")
        if desc:
            lines.append(f"  Description: {desc}")
        for field in ("use_for", "do_not_use_for", "examples", "out_of_scope_examples"):
            items = tool.get(field)
            if items and isinstance(items, list):
                label = field.replace("_", " ").capitalize()
                lines.append(f"  {label}:")
                for item in items:
                    lines.append(f"    - {item}")
        lines.append("")
    return "\n".join(lines).strip()


def load_answer_schema(config: AppConfig | None = None) -> str:
    payload = get_format_payload(config)
    if not payload:
        payload = _load_yaml(_prompts_dir() / "format.yaml")
    schema = payload.get("output_schema", {})
    return str(schema)


def load_answer_contract(config: AppConfig | None = None) -> str:
    payload = get_format_payload(config)
    if not payload:
        payload = _load_yaml(_prompts_dir() / "format.yaml")
    if not isinstance(payload, dict):
        return ""
    contract = {key: value for key, value in payload.items() if key != "output_schema"}
    if not contract:
        return ""
    return yaml.safe_dump(contract, sort_keys=False).strip()


def _normalize_tool_choice(choice: ToolChoiceSchema, available_tools: list[str]) -> ToolChoiceResult:
    tool_name = choice.tool_name
    if tool_name and tool_name not in available_tools:
        tool_name = None

    tool_input = choice.tool_input.model_dump(exclude_none=True)
    if tool_name == "get_transactions" and "fraud_only" not in tool_input:
        tool_input["fraud_only"] = False
    if tool_name == "get_spending_summary" and "group_by" not in tool_input:
        tool_input["group_by"] = "category"

    reasoning = choice.reasoning.strip()
    return ToolChoiceResult(tool_name=tool_name, tool_input=tool_input, reasoning=reasoning)


class LangChainLLMClient:
    def __init__(self, *, provider: str, model: str, api_key: str, api_base: str | None = None) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self._model = self._build_model()

    def _build_model(self):
        if self.provider in {"openai", "cortex"}:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "api_key": self.api_key,
                "temperature": 0,
            }
            if self.api_base:
                kwargs["base_url"] = self.api_base
            return ChatOpenAI(**kwargs)
        if self.provider == "gemini":
            return ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=self.api_key,
                temperature=0,
            )
        if self.provider == "claude":
            kwargs = {
                "model": self.model,
                "api_key": self.api_key,
                "temperature": 0,
            }
            if self.api_base:
                kwargs["base_url"] = self.api_base
            return ChatAnthropic(**kwargs)
        raise ValueError(f"Unsupported provider '{self.provider}'.")

    def choose_tool(
        self,
        *,
        user_input: str,
        available_tools: list[str],
        tool_descriptions: str | None = None,
        system_prompt: str | None = None,
    ) -> ToolChoiceResult:
        tools_block = tool_descriptions or ", ".join(available_tools)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt or load_system_prompt()),
                (
                    "human",
                    (
                        "Choose the best banking tool for the request.\n"
                        "Available tools:\n{tools_block}\n"
                        "Allowed tool_input keys: customer_id, customer_id_a, customer_id_b, fraud_only, group_by, severity.\n"
                        "Use null for tool_name if no tool fits.\n"
                        "Always return a non-empty reasoning value of exactly one short sentence.\n"
                        "The reasoning must cite the decisive wording or boundary that led to the choice.\n"
                        "Use customer IDs exactly as written, for example CUS007.\n"
                        'For spending summaries, default group_by to "category" when omitted.\n'
                        "User request: {user_input}"
                    ),
                ),
            ]
        )
        structured_model = self._model.with_structured_output(ToolChoiceSchema)
        choice = structured_model.invoke(
            prompt.invoke(
                {
                    "tools_block": tools_block,
                    "user_input": user_input,
                }
            )
        )
        return _normalize_tool_choice(choice, available_tools)

    def generate_answer(
        self,
        *,
        user_input: str,
        tool_name: str | None,
        tool_result: object,
        system_prompt: str | None = None,
    ) -> AnswerGenerationResult:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt or load_system_prompt()),
                (
                    "human",
                    (
                        "Write a concise banking answer grounded only in the supplied tool result.\n"
                        "Do not invent facts. If the tool result is empty, say so plainly.\n"
                        "Treat the answer format contract as an instruction set, not as documentation.\n"
                        "If the contract defines global guidance or tool-specific requirements for the selected tool, follow them exactly.\n"
                        "If the contract defines required sections for the selected tool, include each required section explicitly whenever the corresponding evidence exists in the tool result.\n"
                        "If the contract defines evidence-preservation or compression rules for the selected tool, follow them exactly.\n"
                        "If the user explicitly asks for reasoning, rationale, explanation, or why, "
                        "also return a short rationale of 1-3 sentences grounded in the tool result.\n"
                        "Do not reveal hidden chain-of-thought. Keep the rationale brief and evidence-based.\n"
                        "Desired response shape reference: {answer_schema}\n"
                        "Answer format contract: {answer_contract}\n"
                        "User request: {user_input}\n"
                        "Selected tool: {tool_name}\n"
                        "Tool result: {tool_result}"
                    ),
                ),
            ]
        )
        structured_model = self._model.with_structured_output(AnswerSchema)
        response = structured_model.invoke(
            prompt.invoke(
                {
                    "answer_schema": load_answer_schema(),
                    "answer_contract": load_answer_contract(),
                    "user_input": user_input,
                    "tool_name": tool_name,
                    "tool_result": repr(tool_result),
                }
            )
        )
        return AnswerGenerationResult(
            answer=response.answer.strip(),
            confidence=response.confidence,
            source=response.source,
            rationale=response.rationale.strip() if isinstance(response.rationale, str) and response.rationale.strip() else None,
        )

    def run_diagnostic_probe(self) -> str:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are being used for a live connectivity and identity probe. "
                        "Reply in one short sentence. "
                        "If you know your model family or model name, include it. "
                        "If you do not know it exactly, say that clearly. "
                        "Also include the exact marker LIVE_LLM_PROBE_OK."
                    ),
                ),
                (
                    "human",
                    (
                        "Identify yourself as the live LLM currently answering this application request. "
                        "Keep it concise."
                    ),
                ),
            ]
        )
        response = self._model.invoke(prompt.invoke({}))
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return " ".join(part for part in parts if part).strip()
        return str(content).strip()


@dataclass(frozen=True)
class LLMRuntime:
    mode: str
    summary: str
    provider: str | None
    model: str | None
    client: LLMClient | None = None

    @property
    def is_ready(self) -> bool:
        return self.client is not None


def build_llm_runtime(config: AppConfig | None = None) -> LLMRuntime:
    config = config or load_app_config()
    settings = config.llm

    if not settings.enabled:
        return LLMRuntime(
            mode="deterministic",
            summary="Keyword routing only. No LLM key required.",
            provider=None,
            model=None,
        )

    if settings.provider not in SUPPORTED_PROVIDERS:
        return LLMRuntime(
            mode="llm-misconfigured",
            summary=f"Unsupported provider '{settings.provider}'. Supported: openai, gemini, claude, cortex.",
            provider=settings.provider,
            model=settings.model,
        )

    api_key = os.getenv(settings.api_key_env)
    if not api_key:
        return LLMRuntime(
            mode="llm-misconfigured",
            summary=f"LLM is enabled but {settings.api_key_env} is not set.",
            provider=settings.provider,
            model=settings.model,
        )

    if settings.provider == "cortex" and not settings.api_base:
        return LLMRuntime(
            mode="llm-misconfigured",
            summary="LLM is enabled for cortex but api_base is missing.",
            provider=settings.provider,
            model=settings.model,
        )

    if settings.api_base and settings.api_base.startswith("REPLACE_WITH_"):
        return LLMRuntime(
            mode="llm-misconfigured",
            summary="LLM api_base still contains a placeholder value.",
            provider=settings.provider,
            model=settings.model,
        )

    if api_key.startswith("REPLACE_WITH_"):
        return LLMRuntime(
            mode="llm-misconfigured",
            summary=f"LLM is enabled but {settings.api_key_env} still contains a placeholder value.",
            provider=settings.provider,
            model=settings.model,
        )

    client = LangChainLLMClient(
        provider=settings.provider,
        model=settings.model,
        api_key=api_key,
        api_base=settings.api_base,
    )
    return LLMRuntime(
        mode="llm-ready",
        summary="Provider config and API key detected. Live LLM routing and answer generation are enabled.",
        provider=settings.provider,
        model=settings.model,
        client=client,
    )


def build_llm_from_env() -> LLMRuntime:
    return build_llm_runtime(load_app_config())
