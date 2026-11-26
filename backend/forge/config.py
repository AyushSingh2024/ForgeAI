"""Engine configuration (no web imports).

Order of precedence: explicit overrides > environment variables > forge.toml > dataclass defaults.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import asdict, dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TOML = BACKEND_DIR / "forge.toml"
PROMPTS_DIR = BACKEND_DIR / "prompts"


@dataclass(frozen=True)
class IntakeCfg:
    max_questions: int = 5


@dataclass(frozen=True)
class RetrievalDefaults:
    default_chunk_size: int = 600
    default_overlap: int = 90
    default_top_k: int = 6
    bm25_weight: float = 0.4
    min_score: float = 0.25


@dataclass(frozen=True)
class EvalsCfg:
    target_cases: int = 24
    min_cases: int = 20
    holdout_fraction: float = 0.25
    dedupe_similarity: float = 0.9
    max_rounds: int = 3


@dataclass(frozen=True)
class JudgeCfg:
    pass_key_fact_coverage: float = 0.8
    pass_judge_mean: float = 3.5
    temperature: float = 0.0
    seed: int = 7


@dataclass(frozen=True)
class OptimizerCfg:
    max_iterations: int = 3
    target_pass_rate: float = 0.85
    revert_on_regress: bool = True


@dataclass(frozen=True)
class BudgetCfg:
    max_llm_calls: int = 400
    max_seconds: int = 1800
    max_tokens: int = 1_500_000


@dataclass(frozen=True)
class RuntimeCfg:
    max_tool_hops: int = 3
    max_answer_words: int = 250


@dataclass(frozen=True)
class LLMCfg:
    agent_provider: str = "ollama"
    agent_model: str = "qwen2.5:7b-instruct"
    judge_provider: str = "ollama"
    judge_model: str = "gemma2:9b"
    ollama_base_url: str = "http://localhost:11434"
    groq_api_key: str = ""
    hf_api_token: str = ""
    openai_api_key: str = ""
    embedder: str = "BAAI/bge-small-en-v1.5"
    cache_path: str = str(BACKEND_DIR / ".cache" / "llm.sqlite")
    use_cache: bool = True
    requests_per_minute: int = 0
    timeout_s: float = 180.0


@dataclass(frozen=True)
class ForgeConfig:
    intake: IntakeCfg = field(default_factory=IntakeCfg)
    retrieval: RetrievalDefaults = field(default_factory=RetrievalDefaults)
    evals: EvalsCfg = field(default_factory=EvalsCfg)
    judge: JudgeCfg = field(default_factory=JudgeCfg)
    optimizer: OptimizerCfg = field(default_factory=OptimizerCfg)
    budget: BudgetCfg = field(default_factory=BudgetCfg)
    runtime: RuntimeCfg = field(default_factory=RuntimeCfg)
    llm: LLMCfg = field(default_factory=LLMCfg)

    def to_dict(self, redact: bool = True) -> dict[str, Any]:
        d = asdict(self)
        if redact:
            for k in ("groq_api_key", "hf_api_token", "openai_api_key"):
                if d["llm"].get(k):
                    d["llm"][k] = "***"
        return d

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


# env var -> (section, field, type)
_ENV_MAP: dict[str, tuple[str, str, type]] = {
    "LLM_PROVIDER": ("llm", "agent_provider", str),
    "AGENT_MODEL": ("llm", "agent_model", str),
    "JUDGE_PROVIDER": ("llm", "judge_provider", str),
    "JUDGE_MODEL": ("llm", "judge_model", str),
    "OLLAMA_BASE_URL": ("llm", "ollama_base_url", str),
    "GROQ_API_KEY": ("llm", "groq_api_key", str),
    "HF_API_TOKEN": ("llm", "hf_api_token", str),
    "OPENAI_API_KEY": ("llm", "openai_api_key", str),
    "EMBEDDER": ("llm", "embedder", str),
    "LLM_RPM": ("llm", "requests_per_minute", int),
    "LLM_CACHE_PATH": ("llm", "cache_path", str),
    "BUDGET_MAX_LLM_CALLS": ("budget", "max_llm_calls", int),
    "BUDGET_MAX_SECONDS": ("budget", "max_seconds", int),
    "BUDGET_MAX_TOKENS": ("budget", "max_tokens", int),
    "FORGE_MAX_ITERATIONS": ("optimizer", "max_iterations", int),
    "EVAL_TARGET_CASES": ("evals", "target_cases", int),
    "EVAL_MAX_ROUNDS": ("evals", "max_rounds", int),
}


def read_dotenv(path: Path) -> dict[str, str]:
    """Minimal .env parser (KEY=value lines, # comments). Real environment variables take precedence."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        out[key.strip()] = value
    return out


def _build_section(cls: type, data: dict[str, Any]) -> Any:
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_config(toml_path: Path | None = None, overrides: dict[str, dict[str, Any]] | None = None,
                env: dict[str, str] | None = None) -> ForgeConfig:
    """Load forge.toml, apply environment variables (and backend/.env), then explicit overrides."""
    if env is None:
        env = {**read_dotenv(BACKEND_DIR / ".env"), **os.environ}
    raw: dict[str, dict[str, Any]] = {}
    path = toml_path or DEFAULT_TOML
    if path.exists():
        with path.open("rb") as fh:
            raw = tomllib.load(fh)

    for key, (section, name, typ) in _ENV_MAP.items():
        val = env.get(key)
        if val not in (None, ""):
            raw.setdefault(section, {})[name] = typ(val)
    if env.get("FORGE_NO_CACHE") == "1":
        raw.setdefault("llm", {})["use_cache"] = False

    for section, values in (overrides or {}).items():
        raw.setdefault(section, {}).update(values)

    base = ForgeConfig()
    kwargs = {}
    for f in fields(ForgeConfig):
        current = getattr(base, f.name)
        if is_dataclass(current):
            merged = {**asdict(current), **raw.get(f.name, {})}
            kwargs[f.name] = _build_section(type(current), merged)
    return ForgeConfig(**kwargs)


def with_overrides(cfg: ForgeConfig, section: str, **values: Any) -> ForgeConfig:
    """Return a copy of cfg with some fields of one section replaced."""
    return replace(cfg, **{section: replace(getattr(cfg, section), **values)})
