from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from config import DEFAULT_SYNC_TASK_NAME, SYNC_RUNTIME_LOCK_FILE, SYNC_RUNTIME_STATUS_FILE


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _target_label(target: dict[str, Any]) -> str:
    phases = ", ".join(target.get("phases", [])) or "todas"
    jornadas = ", ".join(str(value) for value in target.get("jornadas", [])) or "todas"
    return f"{target.get('league', '?')} {target.get('season', '?')} | fases: {phases} | jornadas: {jornadas}"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    last_error: Exception | None = None
    for attempt in range(8):
        try:
            temp_path.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.2 * (attempt + 1))
    if last_error is not None:
        raise last_error


def load_runtime_status(status_file: Path | str = SYNC_RUNTIME_STATUS_FILE) -> dict[str, Any]:
    return _read_json(Path(status_file))


def load_runtime_lock(lock_file: Path | str = SYNC_RUNTIME_LOCK_FILE) -> dict[str, Any]:
    return _read_json(Path(lock_file))


def is_process_running(pid: Any) -> bool:
    try:
        process_id = int(pid)
    except (TypeError, ValueError):
        return False

    if process_id <= 0:
        return False

    if os.name == "nt":
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"$p = Get-Process -Id {process_id} -ErrorAction SilentlyContinue; if ($p) {{ 'RUNNING' }}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        output = (result.stdout or "").strip()
        return output == "RUNNING"

    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def runtime_status_is_live(status: dict[str, Any], *, stale_after_minutes: int = 20) -> bool:
    if not status or status.get("status") != "running":
        return False
    heartbeat = parse_iso_datetime(status.get("heartbeat_at") or status.get("updated_at"))
    if heartbeat is None:
        return False
    if datetime.now(timezone.utc) - heartbeat > timedelta(minutes=stale_after_minutes):
        return False
    return is_process_running(status.get("pid"))


class SyncAlreadyRunningError(RuntimeError):
    pass


class SyncExecutionLock:
    def __init__(self, lock_file: Path | str = SYNC_RUNTIME_LOCK_FILE):
        self.lock_file = Path(lock_file)
        self.acquired = False
        self.owner_pid = os.getpid()

    def acquire(self) -> None:
        if self.acquired:
            return

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        existing = load_runtime_lock(self.lock_file)
        if existing:
            existing_pid = existing.get("pid")
            if is_process_running(existing_pid):
                raise SyncAlreadyRunningError(f"Ya hay una sincronizacion en marcha (PID {existing_pid}).")
            self.lock_file.unlink(missing_ok=True)

        payload = {
            "pid": self.owner_pid,
            "started_at": utc_now_iso(),
        }
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(str(self.lock_file), flags)
        try:
            os.write(fd, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        finally:
            os.close(fd)
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        with suppress_os_error():
            current = load_runtime_lock(self.lock_file)
            current_pid = current.get("pid")
            if current_pid in (None, self.owner_pid):
                self.lock_file.unlink(missing_ok=True)
        self.acquired = False

    def __enter__(self) -> "SyncExecutionLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class suppress_os_error:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is not None and issubclass(exc_type, OSError)


class SyncRuntimeTracker:
    def __init__(self, status_file: Path | str = SYNC_RUNTIME_STATUS_FILE, *, max_events: int = 80):
        self.status_file = Path(status_file)
        self.max_events = max_events
        self.state: dict[str, Any] = {}

    def _save(self) -> None:
        self.state["updated_at"] = utc_now_iso()
        self.state["heartbeat_at"] = self.state["updated_at"]
        _write_json(self.status_file, self.state)

    def record_event(self, level: str, message: str, **fields: Any) -> None:
        events = list(self.state.get("recent_events", []))
        events.append(
            {
                "timestamp": utc_now_iso(),
                "level": level,
                "message": message,
                **fields,
            }
        )
        self.state["recent_events"] = events[-self.max_events :]
        self.state["last_message"] = message
        self._save()

    def start_run(
        self,
        *,
        mode: str,
        targets: Sequence[dict[str, Any]],
        command: str,
        cwd: str,
    ) -> None:
        self.state = {
            "status": "running",
            "mode": mode,
            "pid": os.getpid(),
            "command": command,
            "cwd": cwd,
            "started_at": utc_now_iso(),
            "finished_at": None,
            "scopes_total": len(targets),
            "scope_index": 0,
            "queued_scopes": [_target_label(target) for target in targets],
            "completed_scopes": [],
            "current_scope": None,
            "current_step": "starting",
            "current_message": "Preparando sincronizacion...",
            "current_game": None,
            "next_games": [],
            "recent_events": [],
        }
        self.record_event("info", "Sincronizacion iniciada.")

    def set_scope(self, *, target: dict[str, Any], index: int, total: int) -> None:
        completed = list(self.state.get("completed_scopes", []))
        queued = list(self.state.get("queued_scopes", []))
        current_label = _target_label(target)
        if current_label in queued:
            queued.remove(current_label)
        self.state["scope_index"] = index
        self.state["scopes_total"] = total
        self.state["completed_scopes"] = completed
        self.state["queued_scopes"] = queued
        self.state["current_scope"] = {
            "label": current_label,
            "season": target.get("season"),
            "league": target.get("league"),
            "phases": list(target.get("phases", [])),
            "jornadas": list(target.get("jornadas", [])),
            "games_total": 0,
            "games_done": 0,
            "games_success": 0,
            "games_failed": 0,
        }
        self.state["current_step"] = "discover"
        self.state["current_message"] = f"Descubriendo partidos para {current_label}"
        self.state["current_game"] = None
        self.state["next_games"] = []
        self.record_event("info", f"Scope {index}/{total}: {current_label}")

    def set_scope_plan(
        self,
        *,
        target_games: int,
        next_games: Sequence[dict[str, Any]],
        recent_pairs: Sequence[dict[str, Any]],
    ) -> None:
        current_scope = dict(self.state.get("current_scope") or {})
        current_scope["games_total"] = int(target_games)
        current_scope["recent_revalidation"] = list(recent_pairs)
        self.state["current_scope"] = current_scope
        self.state["next_games"] = list(next_games)
        if target_games == 0:
            self.state["current_step"] = "idle"
            self.state["current_message"] = "No hay partidos pendientes en este scope."
        else:
            self.state["current_step"] = "scrape_queue_ready"
            self.state["current_message"] = f"Cola preparada con {target_games} partidos."
        self._save()

    def set_step(
        self,
        *,
        step: str,
        message: str,
        current_game: dict[str, Any] | None = None,
        next_games: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        self.state["current_step"] = step
        self.state["current_message"] = message
        if current_game is not None:
            self.state["current_game"] = current_game
        if next_games is not None:
            self.state["next_games"] = list(next_games)
        self._save()

    def mark_game_result(
        self,
        *,
        success: bool,
        index: int,
        total: int,
        current_game: dict[str, Any],
        next_games: Sequence[dict[str, Any]],
    ) -> None:
        scope = dict(self.state.get("current_scope") or {})
        scope["games_total"] = int(total)
        scope["games_done"] = int(index)
        if success:
            scope["games_success"] = int(scope.get("games_success", 0)) + 1
            self.state["current_message"] = f"Partido {index}/{total} scrapeado."
        else:
            scope["games_failed"] = int(scope.get("games_failed", 0)) + 1
            self.state["current_message"] = f"Partido {index}/{total} fallido."
        self.state["current_scope"] = scope
        self.state["current_game"] = current_game
        self.state["next_games"] = list(next_games)
        self.state["current_step"] = "scraping_game"
        self._save()

    def complete_scope(self, *, target: dict[str, Any], summary: dict[str, Any]) -> None:
        completed = list(self.state.get("completed_scopes", []))
        completed.append(
            {
                "label": _target_label(target),
                "summary": summary,
                "finished_at": utc_now_iso(),
            }
        )
        self.state["completed_scopes"] = completed
        self.state["current_scope"] = None
        self.state["current_game"] = None
        self.state["next_games"] = []
        self.state["current_step"] = "scope_complete"
        self.state["current_message"] = f"Scope completado: {_target_label(target)}"
        self._save()

    def finish_run(self, *, published: bool, results: Sequence[dict[str, Any]]) -> None:
        self.state["status"] = "completed"
        self.state["published"] = bool(published)
        self.state["results"] = list(results)
        self.state["finished_at"] = utc_now_iso()
        self.state["current_step"] = "completed"
        self.state["current_message"] = "Sincronizacion terminada."
        self.state["current_game"] = None
        self.state["next_games"] = []
        self.record_event("success", "Sincronizacion terminada.")

    def fail_run(self, error: str) -> None:
        self.state["status"] = "failed"
        self.state["finished_at"] = utc_now_iso()
        self.state["current_step"] = "failed"
        self.state["current_message"] = error
        self.record_event("warning", error)


def get_scheduled_task_status(task_name: str = DEFAULT_SYNC_TASK_NAME) -> dict[str, Any]:
    if os.name != "nt":
        return {"exists": False, "supported": False}

    ps_script = f"""
    $task = Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue
    if ($null -eq $task) {{
      [pscustomobject]@{{ exists = $false; task_name = '{task_name}' }} | ConvertTo-Json -Compress
      exit 0
    }}
    $lastRun = $null
    $nextRun = $null
    $schtasks = schtasks /Query /TN "{task_name}" /V /FO LIST
    foreach ($line in $schtasks) {{
      if ($line -match '^(Hora próxima ejecución|Next Run Time)\\s*:\\s*(.+)$') {{
        $nextRun = $matches[2].Trim()
      }}
      if ($line -match '^(Último tiempo de ejecución|Last Run Time)\\s*:\\s*(.+)$') {{
        $lastRun = $matches[2].Trim()
      }}
    }}
    [pscustomobject]@{{
      exists = $true
      task_name = $task.TaskName
      state = "$($task.State)"
      last_run_time = $lastRun
      next_run_time = $nextRun
    }} | ConvertTo-Json -Compress
    """

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        return {"exists": False, "supported": True, "error": (result.stderr or "").strip()}
    try:
        payload = json.loads((result.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        payload = {"exists": False, "supported": True, "error": "No se pudo leer el estado de la tarea programada."}
    payload.setdefault("supported", True)
    return payload
