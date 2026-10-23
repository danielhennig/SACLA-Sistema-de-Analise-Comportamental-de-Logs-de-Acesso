"""Agenda da simulação: tráfego normal + anomalias, exportados separadamente.

- events.parquet: o que o executor faz, em ordem (sem nenhuma informação de rótulo);
- manifest.csv: ground truth dos cenários anômalos (usuário, início, fim, tipo, intensidade);
- run.json: parâmetros da execução, limites dos splits e hashes da configuração;
- drift.csv (só com deriva, Fase 8): mudanças de rotina sorteadas, para a análise.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from sacla.config import CONFIG_DIR, PROJECT_ROOT, ConfigError
from simlab.anomalies import SPLITS, AnomalyConfig, AnomalyInjector, Scenario, Split
from simlab.behavior import BehaviorConfig, Period, generate_normal
from simlab.catalog import Catalog, IdPools
from simlab.drift import DRIFT_FILE, DriftPlan
from simlab.profiles import Profiles
from simlab.timeline import STATEMENT, Event, Timeline

log = logging.getLogger(__name__)

CONFIG_FILES = ("experiment.yaml", "profiles.yaml", "queries.yaml", "anomalies.yaml")
DRIFT_CONFIG = "drift.yaml"


@dataclass(frozen=True)
class SimulationSettings:
    seed: int
    start_date: date
    days: int
    nominal_days: int
    timezone: str
    data_dir: Path
    run_id_template: str
    wrong_password: str
    progress_every: int
    lock_timeout_ms: int
    expected_sqlstates: tuple[str, ...]
    retime_reorder_window: int
    results_dir: Path
    split_fractions: dict[str, float]
    run_suffix: str = ""  # com deriva (Fase 8): config/drift.yaml, run_suffix

    @classmethod
    def from_experiment(
        cls,
        experiment: dict[str, Any],
        seed: int | None = None,
        days: int | None = None,
        run_suffix: str = "",
    ) -> SimulationSettings:
        try:
            sim, split = experiment["simulation"], experiment["split"]
            fractions = {name: float(split[name]) for name in SPLITS}
            settings = cls(
                seed=int(seed if seed is not None else sim["seed"]),
                start_date=date.fromisoformat(str(sim["start_date"])),
                days=int(days if days is not None else sim["days"]),
                nominal_days=int(sim["nominal_days"]),
                timezone=str(sim["timezone"]),
                data_dir=PROJECT_ROOT / sim["data_dir"],
                run_id_template=str(sim["run_id"]),
                wrong_password=str(sim["wrong_password"]),
                progress_every=int(sim["progress_every"]),
                lock_timeout_ms=int(sim["lock_timeout_ms"]),
                expected_sqlstates=tuple(str(s) for s in sim["expected_sqlstates"]),
                retime_reorder_window=int(sim["retime_reorder_window"]),
                results_dir=PROJECT_ROOT / sim["results_dir"],
                split_fractions=fractions,
                run_suffix=run_suffix,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"seções simulation/split inválidas: {exc!r}") from exc
        if abs(sum(fractions.values()) - 1.0) > 1e-9 or min(fractions.values()) <= 0:
            raise ConfigError("as frações de split devem ser positivas e somar 1")
        if settings.days < 1:
            raise ConfigError("simulation.days deve ser >= 1")
        return settings

    @property
    def drift(self) -> bool:
        return bool(self.run_suffix)

    @property
    def run_id(self) -> str:
        return self.run_id_template.format(seed=self.seed, days=self.days) + self.run_suffix

    @property
    def results_run_dir(self) -> Path:
        return self.results_dir / self.run_id

    @property
    def run_dir(self) -> Path:
        return self.data_dir / self.run_id

    @property
    def period(self) -> Period:
        return Period(self.start_date, self.days, ZoneInfo(self.timezone))


@dataclass
class Schedule:
    events: list[Event]  # ordenados; event_id = posição + 1
    scenarios: list[Scenario]
    splits: dict[str, Split]
    normal_statements: int
    drift: DriftPlan | None = None


def compute_splits(period: Period, fractions: dict[str, float]) -> dict[str, Split]:
    splits, cursor = {}, period.start_ms
    total = period.end_ms - period.start_ms
    for i, name in enumerate(SPLITS):
        end = period.end_ms if i == len(SPLITS) - 1 else cursor + round(total * fractions[name])
        splits[name] = Split(name, cursor, end)
        cursor = end
    return splits


def build_schedule(
    settings: SimulationSettings,
    profiles: Profiles,
    behaviors: BehaviorConfig,
    catalog: Catalog,
    anomalies: AnomalyConfig,
    ids: IdPools,
    drift: DriftPlan | None = None,
) -> Schedule:
    """Agenda completa; com `drift` (Fase 8), a rotina de alguns usuários muda no período."""
    period = settings.period
    splits = compute_splits(period, settings.split_fractions)
    timeline = Timeline()
    routines = drift.routines if drift is not None else None
    activity = generate_normal(
        timeline, profiles, behaviors, catalog, ids, period, settings.seed, routines
    )
    injector = AnomalyInjector(
        timeline,
        profiles,
        behaviors,
        catalog,
        ids,
        period,
        activity,
        anomalies,
        splits,
        settings.seed,
        routines,
    )
    scenarios = injector.inject(scale=settings.days / settings.nominal_days)
    events = timeline.sorted_events()
    log.info(
        "agenda: %d eventos, %d comandos normais, %d cenários anômalos",
        len(events),
        activity.statements,
        len(scenarios),
    )
    return Schedule(events, scenarios, splits, activity.statements, drift)


def events_frame(events: list[Event]) -> pd.DataFrame:
    """Eventos para o executor e o retime. Não inclui o cenário (rótulo) de cada evento."""
    return pd.DataFrame(
        {
            "event_id": range(1, len(events) + 1),
            "ts_ms": [e.ts_ms for e in events],
            "kind": [e.kind for e in events],
            "session": [e.session for e in events],
            "user": [e.user for e in events],
            "network": [e.network for e in events],
            "application_name": [e.application_name for e in events],
            "sql": [e.statement.sql if e.statement else None for e in events],
            "params_json": [
                json.dumps(e.statement.params, sort_keys=True)
                if e.statement and e.statement.params
                else None
                for e in events
            ],
            "capture": [e.statement.capture if e.statement else None for e in events],
        }
    )


def manifest_frame(scenarios: list[Scenario]) -> pd.DataFrame:
    rows = []
    for sc in scenarios:
        row = asdict(sc)
        row["params"] = json.dumps(sc.params, sort_keys=True)
        row["start_utc"] = _iso(sc.start_ms)
        row["end_utc"] = _iso(sc.end_ms)
        rows.append(row)
    columns = [
        "scenario_id",
        "user",
        "role",
        "type",
        "intensity",
        "novel",
        "split",
        "network",
        "start_utc",
        "end_utc",
        "start_ms",
        "end_ms",
        "statements",
        "failed_logins",
        "params",
    ]
    return pd.DataFrame(rows, columns=columns).sort_values("start_ms", kind="stable")


def write_schedule(
    schedule: Schedule, settings: SimulationSettings, run_dir: Path, ids_digest: str
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    events_frame(schedule.events).to_parquet(run_dir / "events.parquet", index=False)
    manifest_frame(schedule.scenarios).to_csv(run_dir / "manifest.csv", index=False)
    config_files = (*CONFIG_FILES, DRIFT_CONFIG) if schedule.drift is not None else CONFIG_FILES
    if schedule.drift is not None:
        frame = schedule.drift.frame(settings.period)
        frame.to_csv(run_dir / DRIFT_FILE, index=False, lineterminator="\n")
    run_info = {
        "run_id": settings.run_id,
        "seed": settings.seed,
        "start_date": settings.start_date.isoformat(),
        "days": settings.days,
        "timezone": settings.timezone,
        "drift": schedule.drift is not None,
        "splits": {
            name: {
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "start_utc": _iso(s.start_ms),
                "end_utc": _iso(s.end_ms),
            }
            for name, s in schedule.splits.items()
        },
        "id_pools_sha256": ids_digest,
        "config_sha256": {
            name: hashlib.sha256((CONFIG_DIR / name).read_bytes()).hexdigest()
            for name in config_files
        },
    }
    (run_dir / "run.json").write_text(json.dumps(run_info, indent=2) + "\n", encoding="utf-8")
    summary = schedule_summary(schedule)
    (run_dir / "schedule_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def schedule_summary(schedule: Schedule) -> dict[str, Any]:
    kinds = Counter(e.kind for e in schedule.events)
    statements_by_user = Counter(e.user for e in schedule.events if e.kind == STATEMENT)
    by_cell = Counter(f"{sc.split}/{sc.type}/{sc.intensity}" for sc in schedule.scenarios)
    return {
        "events": len(schedule.events),
        "events_by_kind": dict(sorted(kinds.items())),
        "normal_statements": schedule.normal_statements,
        "statements_by_user": dict(sorted(statements_by_user.items())),
        "scenarios": len(schedule.scenarios),
        "scenarios_by_split": dict(Counter(sc.split for sc in schedule.scenarios)),
        "scenarios_by_split_type_intensity": dict(sorted(by_cell.items())),
    }


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat(timespec="milliseconds")
