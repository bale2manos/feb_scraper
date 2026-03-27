from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import AUTO_SYNC_TARGETS_FILE, DEFAULT_AUTO_SYNC_TARGETS, get_liga_fases


def normalize_target(target: dict[str, Any]) -> dict[str, Any]:
    league = str(target.get("league", "")).strip()
    season = str(target.get("season", "")).strip()
    phases = target.get("phases") or get_liga_fases(league)
    jornadas = [int(value) for value in (target.get("jornadas") or [])]
    enabled = bool(target.get("enabled", True))
    return {
        "season": season,
        "league": league,
        "phases": list(phases),
        "jornadas": jornadas,
        "enabled": enabled,
    }


def expand_targets_by_phase(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    for raw_target in targets:
        target = normalize_target(raw_target)
        phases = list(target.get("phases") or [])
        if not phases:
            expanded.append(target)
            continue
        for phase in phases:
            expanded.append(
                {
                    "season": target["season"],
                    "league": target["league"],
                    "phases": [phase],
                    "jornadas": list(target.get("jornadas", [])),
                    "enabled": bool(target.get("enabled", True)),
                }
            )
    return expanded


def default_config() -> dict[str, Any]:
    return {
        "revalidate_window": 2,
        "publish": True,
        "targets": expand_targets_by_phase([normalize_target(target) for target in DEFAULT_AUTO_SYNC_TARGETS]),
    }


def load_auto_sync_config(path: Path | str = AUTO_SYNC_TARGETS_FILE) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return default_config()

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    targets = [normalize_target(target) for target in raw.get("targets", [])]
    return {
        "revalidate_window": int(raw.get("revalidate_window", 2)),
        "publish": bool(raw.get("publish", True)),
        "targets": targets,
    }


def save_auto_sync_config(config: dict[str, Any], path: Path | str = AUTO_SYNC_TARGETS_FILE) -> Path:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = {
        "revalidate_window": int(config.get("revalidate_window", 2)),
        "publish": bool(config.get("publish", True)),
        "targets": [normalize_target(target) for target in config.get("targets", [])],
    }
    config_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_path


def iter_enabled_targets(config: dict[str, Any]) -> list[dict[str, Any]]:
    enabled_targets = [target for target in config.get("targets", []) if target.get("enabled", True)]
    return expand_targets_by_phase(enabled_targets)


def target_label(target: dict[str, Any]) -> str:
    phases = target.get("phases") or []
    phase_text = ", ".join(phases) if phases else "todas las fases"
    jornadas = target.get("jornadas") or []
    jornada_text = ",".join(str(value) for value in jornadas) if jornadas else "todas"
    return f"{target.get('season', '')} | {target.get('league', '')} | {phase_text} | jornadas: {jornada_text}"
