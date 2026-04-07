from __future__ import annotations

import argparse
import sys
from pathlib import Path

for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream is not None and hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config import AUTO_SYNC_TARGETS_FILE, LIGA_DEFAULT, TEMPORADA_TXT, get_liga_fases
from storage import DataStore
from utils.auto_sync import expand_targets_by_phase, iter_enabled_targets, load_auto_sync_config, target_label
from utils.cloud_publish import (
    DEFAULT_CLOUD_PUBLISH_CONFIG_FILE,
    load_cloud_publish_config,
    publish_sqlite_snapshot_to_cloud,
)
from utils.sync_runtime import SyncAlreadyRunningError, SyncExecutionLock, SyncRuntimeTracker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sincroniza partidos FEB pendientes, exporta compatibilidad y opcionalmente publica cambios."
    )
    parser.add_argument("--season", default=TEMPORADA_TXT, help="Temporada objetivo. Default: configuracion actual.")
    parser.add_argument("--league", default=LIGA_DEFAULT, help="Liga objetivo. Default: configuracion actual.")
    parser.add_argument(
        "--phases",
        nargs="*",
        default=None,
        help="Fases a sincronizar. Si se omite, se usan todas las fases conocidas de la liga.",
    )
    parser.add_argument(
        "--jornadas",
        nargs="*",
        type=int,
        default=None,
        help="Jornadas concretas. Si se omite, se consideran todas.",
    )
    parser.add_argument(
        "--revalidate-window",
        type=int,
        default=2,
        help="Numero de jornadas recientes por fase a revalidar.",
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="No generar exportes Excel de compatibilidad despues del sync.",
    )
    parser.add_argument(
        "--skip-player-bios",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--player-bio-limit",
        type=int,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Hace commit/push de la carpeta data si hay cambios tras el sync.",
    )
    parser.add_argument(
        "--publish-cloud",
        action="store_true",
        help="Sube la snapshot de SQLite a Google Cloud Storage y fuerza una nueva revision de Cloud Run.",
    )
    parser.add_argument(
        "--skip-cloud-publish",
        action="store_true",
        help="Desactiva la publicacion cloud aunque exista configuracion local activa.",
    )
    parser.add_argument(
        "--all-targets",
        action="store_true",
        help="Sincroniza todos los objetivos guardados en el archivo de autosync.",
    )
    parser.add_argument(
        "--targets-file",
        default=str(AUTO_SYNC_TARGETS_FILE),
        help="Archivo JSON con objetivos de autosync.",
    )
    parser.add_argument(
        "--cloud-config",
        default=str(DEFAULT_CLOUD_PUBLISH_CONFIG_FILE),
        help="Archivo JSON local con la configuracion de subida a Cloud Storage y redeploy de Cloud Run.",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Importa el historico Excel a SQLite si hace falta y termina sin sincronizar.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Ruta al repositorio Git para publicar los cambios.",
    )
    parser.add_argument(
        "--commit-message",
        default=None,
        help="Mensaje de commit para la publicacion.",
    )
    return parser


def log_callback(level: str, message: str) -> None:
    print(f"[{level.upper()}] {message}")


def serialize_summary(summary) -> dict[str, object]:
    return {
        "discovered_games": summary.discovered_games,
        "missing_games": summary.missing_games,
        "refreshed_games": summary.refreshed_games,
        "scraped_games": summary.scraped_games,
        "skipped_games": summary.skipped_games,
        "failed_games": summary.failed_games,
        "changed_scopes": list(summary.changed_scopes),
    }


def build_progress_callback(tracker: SyncRuntimeTracker | None):
    def callback(level: str, message: str) -> None:
        log_callback(level, message)
        if tracker is not None:
            tracker.record_event(level, message)

    return callback


def sync_one_target(
    store: DataStore,
    *,
    season: str,
    league: str,
    phases: list[str],
    jornadas: tuple[int, ...],
    revalidate_window: int,
    skip_export: bool,
    sync_player_bios: bool,
    player_bio_limit: int | None,
    progress_callback,
    runtime_tracker: SyncRuntimeTracker | None = None,
) -> dict[str, object]:
    print(
        f"[INFO] Sync FEB -> temporada={season} liga={league} fases={len(phases)} jornadas={list(jornadas) if jornadas else 'todas'}"
    )
    summary = store.sync_games(
        season=season,
        league=league,
        phases=phases,
        jornadas=jornadas,
        revalidate_window=revalidate_window,
        export_compat_files=not skip_export,
        scrape_player_bios=sync_player_bios,
        player_bio_limit=player_bio_limit,
        progress_callback=progress_callback,
        runtime_tracker=runtime_tracker,
    )
    print(
        "[SUCCESS] Sync terminado: "
        f"discovered={summary.discovered_games} "
        f"missing={summary.missing_games} "
        f"refreshed={summary.refreshed_games} "
        f"scraped={summary.scraped_games} "
        f"skipped={summary.skipped_games} "
        f"failed={summary.failed_games}"
    )
    return {
        "season": season,
        "league": league,
        "phases": phases,
        "jornadas": list(jornadas),
        "summary": summary,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    store = DataStore()
    tracker = SyncRuntimeTracker()

    try:
        with SyncExecutionLock():
            if args.all_targets:
                config = load_auto_sync_config(args.targets_file)
                targets = iter_enabled_targets(config)
                if not targets:
                    print(f"[WARNING] No hay objetivos habilitados en {args.targets_file}")
                    return 0
                revalidate_window = int(config.get("revalidate_window", args.revalidate_window))
                publish_after = bool(config.get("publish", False)) or args.publish
                mode = "autosync"
                print(f"[INFO] Objetivos autosync cargados desde {args.targets_file}: {len(targets)}")
            else:
                phases = args.phases if args.phases else get_liga_fases(args.league)
                targets = expand_targets_by_phase(
                    [
                        {
                            "season": args.season,
                            "league": args.league,
                            "phases": list(phases),
                            "jornadas": list(args.jornadas or []),
                        }
                    ]
                )
                revalidate_window = args.revalidate_window
                publish_after = args.publish
                mode = "manual"

            cloud_config = load_cloud_publish_config(args.cloud_config) if (args.publish_cloud or args.all_targets) else None
            publish_cloud_after = _resolve_cloud_publish_flag(
                explicit_publish=args.publish_cloud,
                skip_publish=args.skip_cloud_publish,
                all_targets=args.all_targets,
                cloud_config=cloud_config,
            )

            tracker.start_run(
                mode=mode,
                targets=targets,
                command=" ".join(sys.argv),
                cwd=str(REPO_ROOT),
            )
            progress_callback = build_progress_callback(tracker)

            if not store.has_data():
                print("[INFO] Base SQLite vacia. Importando historico Excel...")
                tracker.set_step(step="bootstrap", message="Importando historico Excel a SQLite")
                result = store.import_historical(progress_callback=progress_callback)
                print(f"[SUCCESS] Importacion completada: {result}")

            if args.bootstrap_only:
                tracker.finish_run(published=False, results=[])
                return 0

            results: list[dict[str, object]] = []
            total_targets = len(targets)
            for index, target in enumerate(targets, start=1):
                print(f"[INFO] Objetivo: {target_label(target)}")
                tracker.set_scope(target=target, index=index, total=total_targets)
                result = sync_one_target(
                    store,
                    season=target["season"],
                    league=target["league"],
                    phases=list(target["phases"]),
                    jornadas=tuple(target.get("jornadas", [])),
                    revalidate_window=revalidate_window,
                    skip_export=args.skip_export,
                    sync_player_bios=not args.skip_player_bios,
                    player_bio_limit=args.player_bio_limit,
                    progress_callback=progress_callback,
                    runtime_tracker=tracker,
                )
                tracker.complete_scope(target=target, summary=serialize_summary(result["summary"]))
                results.append(result)

            published = False
            if publish_after:
                tracker.set_step(step="publishing", message="Publicando cambios en GitHub")
                published = store.publish_data_changes(
                    repo_root=Path(args.repo_root),
                    commit_message=args.commit_message,
                    progress_callback=progress_callback,
                )
                print(f"[INFO] Publicacion realizada: {published}")

            if publish_cloud_after:
                tracker.set_step(step="cloud_publish", message="Subiendo snapshot SQLite a Google Cloud Storage")
                cloud_result = publish_sqlite_snapshot_to_cloud(
                    cloud_config,
                    progress_callback=progress_callback,
                )
                print(
                    "[INFO] Publicacion cloud realizada: "
                    f"{cloud_result['gcsUri']} -> {cloud_result['service']} "
                    f"({cloud_result['snapshotVersion']})"
                )

            tracker.finish_run(
                published=published,
                results=[
                    {
                        "season": result["season"],
                        "league": result["league"],
                        "phases": result["phases"],
                        "jornadas": result["jornadas"],
                        "summary": serialize_summary(result["summary"]),
                    }
                    for result in results
                ],
            )
            print(f"[INFO] Scopes procesados: {len(results)}")
            return 0
    except SyncAlreadyRunningError as exc:
        message = str(exc)
        print(f"[WARNING] {message}")
        return 1
    except Exception as exc:
        if tracker.state:
            tracker.fail_run(f"Sync abortado: {type(exc).__name__}: {exc}")
        raise

def _resolve_cloud_publish_flag(
    *,
    explicit_publish: bool,
    skip_publish: bool,
    all_targets: bool,
    cloud_config,
) -> bool:
    if skip_publish:
        return False
    if explicit_publish:
        if cloud_config is None:
            raise RuntimeError("Has pedido --publish-cloud pero no existe el archivo de configuracion cloud.")
        if not cloud_config.enabled:
            raise RuntimeError("La configuracion cloud existe pero esta deshabilitada.")
        return True
    return bool(all_targets and cloud_config is not None and cloud_config.enabled)


if __name__ == "__main__":
    raise SystemExit(main())
