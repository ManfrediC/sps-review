"""Optimisation matrix helpers for Stage 07 benchmarking.

Matrix files describe candidate configurations; they do not execute providers
or resolve secrets. The normaliser keeps configuration rows comparable across
heuristic, OpenAI, DeepSeek, and future source-unit architecture experiments.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODEL_MATRIX_SCHEMA_VERSION = "stage07_benchmark_model_matrix_v2"
SECRET_KEY_FRAGMENTS = ("api_key", "apikey", "secret", "password", "bearer", "access_token")


DEFAULT_OPTIMISATION_MATRIX: list[dict[str, Any]] = [
    {
        "name": "H0_current_baseline",
        "provider": "heuristic",
        "model": "deterministic_stage07_xml",
        "endpoint": "local",
        "architecture_variant": "block_offsets",
        "notes": "Current deterministic and validated Stage 07 XML baseline.",
    },
    {
        "name": "H1_improved_heuristics",
        "provider": "heuristic",
        "model": "deterministic_stage07_xml",
        "endpoint": "local",
        "architecture_variant": "block_offsets",
        "notes": "Placeholder for improved deterministic section, label, and contamination heuristics.",
    },
    {
        "name": "O1_gpt55_medium_25k",
        "provider": "openai",
        "model": "gpt-5.5",
        "endpoint": "responses",
        "architecture_variant": "block_offsets",
        "reasoning_effort": "medium",
        "max_output_tokens": 25000,
        "strict_json_schema": True,
    },
    {
        "name": "O2_gpt55_high_40k",
        "provider": "openai",
        "model": "gpt-5.5",
        "endpoint": "responses",
        "architecture_variant": "block_offsets",
        "reasoning_effort": "high",
        "max_output_tokens": 40000,
        "strict_json_schema": True,
    },
    {
        "name": "O3_gpt55_retry_high_64k",
        "provider": "openai",
        "model": "gpt-5.5",
        "endpoint": "responses",
        "architecture_variant": "block_offsets",
        "reasoning_effort": "high",
        "max_output_tokens": 64000,
        "strict_json_schema": True,
        "notes": "Retry tier for incomplete or high-risk cases only.",
    },
    {
        "name": "D1_deepseek_v4_flash_json",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "endpoint": "chat_completions",
        "architecture_variant": "block_offsets",
        "thinking_mode": "disabled",
        "notes": "Benchmark-only candidate generation; no production promotion without holdout success.",
    },
    {
        "name": "D2_deepseek_v4_flash_thinking",
        "provider": "deepseek",
        "model": "deepseek-v4-flash",
        "endpoint": "chat_completions",
        "architecture_variant": "block_offsets",
        "thinking_mode": "enabled",
        "reasoning_effort": "high",
        "notes": "Do not persist reasoning_content in traces.",
    },
    {
        "name": "D3_deepseek_v4_pro_hard_cases",
        "provider": "deepseek",
        "model": "deepseek-v4-pro",
        "endpoint": "chat_completions",
        "architecture_variant": "block_offsets",
        "thinking_mode": "enabled",
        "reasoning_effort": "high",
        "notes": "Hard-case benchmark tier only.",
    },
    {
        "name": "A1_source_unit_ids",
        "provider": "openai",
        "model": "gpt-5.5",
        "endpoint": "responses",
        "architecture_variant": "source_unit_ids",
        "reasoning_effort": "medium",
        "max_output_tokens": 25000,
        "strict_json_schema": True,
        "notes": "Model selects deterministic unit_ids; Python compiles offsets.",
    },
]


def default_matrix_payload() -> dict[str, Any]:
    return {
        "schema_version": MODEL_MATRIX_SCHEMA_VERSION,
        "configs": DEFAULT_OPTIMISATION_MATRIX,
    }


def secret_bearing_keys(value: Any, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if any(fragment in key_text.casefold() for fragment in SECRET_KEY_FRAGMENTS):
                keys.append(path)
            keys.extend(secret_bearing_keys(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            keys.extend(secret_bearing_keys(item, f"{prefix}[{index}]"))
    return keys


def normalise_matrix_configs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    secret_keys = secret_bearing_keys(payload)
    if secret_keys:
        raise ValueError(f"Matrix files must not contain secret-like keys: {', '.join(secret_keys)}")
    configs = payload.get("configs") or payload.get("runs") or []
    if not isinstance(configs, list):
        raise ValueError("Model matrix must contain a list under 'configs' or 'runs'.")
    normalised: list[dict[str, Any]] = []
    for index, item in enumerate(configs, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Model matrix item {index} is not an object.")
        name = str(item.get("name") or "").strip()
        provider = str(item.get("provider") or "").strip()
        model = str(item.get("model") or "").strip()
        if not name or not provider or not model:
            raise ValueError(f"Model matrix item {index} needs name, provider, and model.")
        normalised.append(
            {
                "name": name,
                "provider": provider,
                "model": model,
                "endpoint": str(item.get("endpoint") or "").strip(),
                "architecture_variant": str(item.get("architecture_variant") or "block_offsets").strip(),
                "route_scope": str(item.get("route_scope") or "").strip(),
                "reasoning_effort": str(item.get("reasoning_effort") or "").strip(),
                "max_output_tokens": item.get("max_output_tokens"),
                "temperature": item.get("temperature"),
                "top_p": item.get("top_p"),
                "strict_json_schema": item.get("strict_json_schema"),
                "thinking_mode": str(item.get("thinking_mode") or "").strip(),
                "max_block_chars": item.get("max_block_chars"),
                "prompt_variant": str(item.get("prompt_variant") or "").strip(),
                "schema_variant": str(item.get("schema_variant") or "").strip(),
                "candidate_annotation_dir": str(item.get("candidate_annotation_dir") or "").strip(),
                "candidate_stage07_root": str(item.get("candidate_stage07_root") or "").strip(),
                "candidate_registry_path": str(item.get("candidate_registry_path") or "").strip(),
                "execution_enabled": bool(item.get("execution_enabled", False)),
                "notes": str(item.get("notes") or "").strip(),
            }
        )
    return normalised


def load_model_matrix(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Model matrix must be a JSON object.")
    return normalise_matrix_configs(payload)
