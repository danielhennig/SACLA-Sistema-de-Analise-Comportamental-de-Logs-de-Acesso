"""Mudanças legítimas de rotina: tráfego normal não estacionário (Fase 8; pré-registro D55).

Só `simulate --drift` usa este módulo. Cada mudança do catálogo (config/drift.yaml) sorteia os
usuários afetados e o dia de início com um gerador próprio ("{semente}:drift:{mudança}"), sem
consumir os geradores do tráfego normal nem o das anomalias. O efeito entra pela `Routine` de
cada usuário (simlab/behavior.py).

As janelas afetadas continuam normais (rótulo 0). O plano sorteado vai para drift.csv, só para
a análise: ele nunca entra no log nem nos eventos que o executor lê.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from sacla.config import CONFIG_DIR, ConfigError, load_yaml
from simlab.behavior import BehaviorConfig, Period, Routine, WeeklyTask, parse_weekly
from simlab.catalog import Catalog
from simlab.profiles import Profiles

DRIFT_FILE = "drift.csv"
TROCA_TURNO = "troca_turno"
FERIAS = "ferias"
PICO = "pico_movimento"
CRESCIMENTO = "crescimento"
HOME_OFFICE = "home_office"
NOVA_ROTINA = "nova_rotina"
PLANTAO = "plantao"
KINDS = (TROCA_TURNO, FERIAS, PICO, CRESCIMENTO, HOME_OFFICE, NOVA_ROTINA, PLANTAO)
INTERACTIVE_ONLY = (TROCA_TURNO, FERIAS, HOME_OFFICE, NOVA_ROTINA, PLANTAO)
TEMPORARY = (FERIAS, PICO, PLANTAO)  # não se sobrepõem no mesmo usuário
DAYS_PER_WEEK = 7
MIDNIGHT = time(0, 0)


@dataclass(frozen=True)
class ChangeSpec:
    kind: str
    roles: tuple[str, ...]
    users: int
    days: tuple[int, int] | None = None
    rate_multiplier: tuple[float, float] | None = None
    weekly_growth: float | None = None
    networks: dict[str, float] | None = None
    weekly: WeeklyTask | None = None
    weekday: int | None = None


@dataclass(frozen=True)
class DriftConfig:
    run_suffix: str
    start_day: tuple[int, int]
    max_attempts: int
    changes: tuple[ChangeSpec, ...]


@dataclass(frozen=True)
class Change:
    """Uma mudança sorteada para um usuário, de first_day até last_day (inclusive)."""

    kind: str
    user: str
    role: str
    first_day: date
    last_day: date
    shift: str | None = None
    rate_multiplier: float = 1.0
    weekly_growth: float = 0.0
    networks: dict[str, float] | None = None
    weekly: WeeklyTask | None = None

    def covers(self, day: date) -> bool:
        return self.first_day <= day <= self.last_day


@dataclass
class UserDrift(Routine):
    """A rotina de um usuário com as mudanças sorteadas para ele."""

    changes: list[Change] = field(default_factory=list)

    def _active(self, kind: str, day: date) -> list[Change]:
        return [c for c in self.changes if c.kind == kind and c.covers(day)]

    def absent(self, day: date) -> bool:
        return bool(self._active(FERIAS, day))

    def on_duty(self, day: date) -> bool:
        return bool(self._active(PLANTAO, day))

    def shift(self, day: date, default: str) -> str:
        active = self._active(TROCA_TURNO, day)
        return (active[0].shift or default) if active else default

    def rate_multiplier(self, day: date) -> float:
        multiplier = 1.0
        for change in self._active(PICO, day):
            multiplier *= change.rate_multiplier
        for change in self._active(CRESCIMENTO, day):
            weeks = (day - change.first_day).days / DAYS_PER_WEEK
            multiplier *= (1 + change.weekly_growth) ** weeks
        return multiplier

    def networks(self, day: date, default: dict[str, float]) -> dict[str, float]:
        active = self._active(HOME_OFFICE, day)
        return (active[0].networks or default) if active else default

    def weekly(self, day: date) -> tuple[WeeklyTask, ...]:
        return tuple(c.weekly for c in self._active(NOVA_ROTINA, day) if c.weekly is not None)


@dataclass
class DriftPlan:
    changes: list[Change]
    routines: dict[str, UserDrift]

    def frame(self, period: Period) -> pd.DataFrame:
        """drift.csv: uma linha por mudança, com o período em ms (fim exclusivo)."""
        rows = []
        for c in self.changes:
            params: dict[str, Any] = {}
            if c.shift:
                params["shift"] = c.shift
            if c.kind == PICO:
                params["rate_multiplier"] = round(c.rate_multiplier, 4)
            if c.kind == CRESCIMENTO:
                params["weekly_growth"] = c.weekly_growth
            if c.networks:
                params["networks"] = c.networks
            if c.weekly:
                params["action"] = c.weekly.action
            rows.append(
                {
                    "change": c.kind,
                    "user": c.user,
                    "role": c.role,
                    "first_day": c.first_day.isoformat(),
                    "last_day": c.last_day.isoformat(),
                    "start_ms": period.local_ms(c.first_day, MIDNIGHT),
                    "end_ms": period.local_ms(c.last_day + timedelta(days=1), MIDNIGHT),
                    "params": json.dumps(params, sort_keys=True),
                }
            )
        columns = ["change", "user", "role", "first_day", "last_day", "start_ms", "end_ms"]
        return pd.DataFrame(rows, columns=[*columns, "params"])


# --- Configuração ----------------------------------------------------------------------------


def drift_suffix(path: Path | None = None) -> str:
    """Sufixo do run_id das simulações com deriva (sim-s101-28d -> sim-s101-28d-deriva)."""
    suffix = str(load_yaml(path or CONFIG_DIR / "drift.yaml").get("run_suffix") or "")
    if not suffix:
        raise ConfigError("drift.yaml: run_suffix vazio")
    return suffix


def load_drift(
    profiles: Profiles, behaviors: BehaviorConfig, catalog: Catalog, path: Path | None = None
) -> DriftConfig:
    raw = load_yaml(path or CONFIG_DIR / "drift.yaml")
    try:
        low, high = (int(v) for v in raw["start_day"])
        config = DriftConfig(
            run_suffix=str(raw["run_suffix"]),
            start_day=(low, high),
            max_attempts=int(raw["max_attempts"]),
            changes=tuple(_parse_change(str(k), v) for k, v in raw["changes"].items()),
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ConfigError(f"drift.yaml malformado: {exc!r}") from exc
    if not config.run_suffix or not 1 <= low <= high or config.max_attempts < 1:
        raise ConfigError("drift.yaml: run_suffix vazio, start_day ou max_attempts inválido")
    known_networks = {n for b in behaviors.behaviors.values() for n in b.networks}
    for spec in config.changes:
        _validate(spec, profiles, behaviors, catalog, known_networks)
    return config


def _parse_change(kind: str, spec: dict[str, Any]) -> ChangeSpec:
    if kind not in KINDS:
        raise ConfigError(f"drift.yaml: mudança desconhecida {kind} (conhecidas: {KINDS})")
    days = spec.get("days")
    multiplier = spec.get("rate_multiplier")
    return ChangeSpec(
        kind=kind,
        roles=tuple(str(r) for r in spec["roles"]),
        users=int(spec["users"]),
        days=(int(days[0]), int(days[1])) if days else None,
        rate_multiplier=(float(multiplier[0]), float(multiplier[1])) if multiplier else None,
        weekly_growth=float(spec["weekly_growth"]) if "weekly_growth" in spec else None,
        networks={str(k): float(v) for k, v in spec["networks"].items()}
        if "networks" in spec
        else None,
        weekly=parse_weekly(spec["weekly"]) if "weekly" in spec else None,
        weekday=int(spec["weekday"]) if "weekday" in spec else None,
    )


def _validate(
    spec: ChangeSpec,
    profiles: Profiles,
    behaviors: BehaviorConfig,
    catalog: Catalog,
    known_networks: set[str],
) -> None:
    where = f"drift.yaml, {spec.kind}"
    if spec.users < 1 or not spec.roles:
        raise ConfigError(f"{where}: users >= 1 e ao menos um papel")
    for role in spec.roles:
        behavior = behaviors.behaviors.get(role)
        if behavior is None or role not in profiles.roles:
            raise ConfigError(f"{where}: papel desconhecido {role}")
        if spec.kind in INTERACTIVE_ONLY and behavior.kind != "interactive":
            raise ConfigError(f"{where}: só vale para papéis interativos ({role})")
        if spec.kind == TROCA_TURNO and len(behavior.shifts or {}) < 2:
            raise ConfigError(f"{where}: o papel {role} não tem outro turno")
        if spec.kind == PLANTAO and spec.weekday in behavior.weekdays:
            raise ConfigError(f"{where}: o dia {spec.weekday} já é de trabalho para {role}")
    required = {
        FERIAS: spec.days,
        PICO: spec.days and spec.rate_multiplier,
        CRESCIMENTO: spec.weekly_growth,
        HOME_OFFICE: spec.networks,
        NOVA_ROTINA: spec.weekly,
        PLANTAO: spec.weekday is not None,
    }
    if spec.kind in required and not required[spec.kind]:
        raise ConfigError(f"{where}: parâmetros obrigatórios ausentes")
    if spec.days and not 1 <= spec.days[0] <= spec.days[1]:
        raise ConfigError(f"{where}: days inválido")
    if spec.rate_multiplier and min(spec.rate_multiplier) <= 0:
        raise ConfigError(f"{where}: rate_multiplier deve ser positivo")
    if spec.weekly_growth is not None and spec.weekly_growth <= -1:
        raise ConfigError(f"{where}: weekly_growth deve ser maior que -1")
    if spec.networks and (set(spec.networks) - known_networks or sum(spec.networks.values()) <= 0):
        raise ConfigError(f"{where}: redes desconhecidas ou pesos nulos em {spec.networks}")
    if spec.weekly:
        catalog.require([spec.weekly.action], where)


# --- Sorteio ---------------------------------------------------------------------------------


def plan_drift(
    config: DriftConfig,
    profiles: Profiles,
    behaviors: BehaviorConfig,
    period: Period,
    seed: int,
) -> DriftPlan:
    """Sorteia, para cada mudança, os usuários e o período (dias contados de 1).

    Mudanças temporárias do mesmo usuário não se sobrepõem: o início é sorteado de novo, até
    max_attempts vezes.
    """
    last_period_day = period.start_date + timedelta(days=period.days - 1)
    first, last = config.start_day[0], min(config.start_day[1], period.days)
    changes: list[Change] = []
    temporary: dict[str, list[tuple[date, date]]] = {}
    for spec in config.changes:
        if first > last:
            break  # período curto demais para qualquer mudança
        rng = random.Random(f"{seed}:drift:{spec.kind}")
        candidates = [u for u in profiles.users if u.role in spec.roles]
        for user in rng.sample(candidates, min(spec.users, len(candidates))):
            taken = temporary.setdefault(user.name, []) if spec.kind in TEMPORARY else []
            for _ in range(config.max_attempts):
                start, end = _span(spec, rng, period, first, last, last_period_day)
                if all(end < a or start > b for a, b in taken):
                    break
            else:
                raise ConfigError(
                    f"drift.yaml: {spec.kind} não coube para {user.name} em "
                    f"{config.max_attempts} tentativas"
                )
            if start > last_period_day:
                continue
            if spec.kind in TEMPORARY:
                taken.append((start, end))
            changes.append(
                Change(
                    kind=spec.kind,
                    user=user.name,
                    role=user.role,
                    first_day=start,
                    last_day=end,
                    shift=_other_shift(behaviors, user.role, user.shift)
                    if spec.kind == TROCA_TURNO
                    else None,
                    rate_multiplier=rng.uniform(*spec.rate_multiplier)
                    if spec.rate_multiplier
                    else 1.0,
                    weekly_growth=spec.weekly_growth or 0.0,
                    networks=spec.networks,
                    weekly=spec.weekly,
                )
            )
    routines: dict[str, UserDrift] = {}
    for change in changes:
        routines.setdefault(change.user, UserDrift()).changes.append(change)
    return DriftPlan(changes=changes, routines=routines)


def _span(
    spec: ChangeSpec, rng: random.Random, period: Period, first: int, last: int, last_day: date
) -> tuple[date, date]:
    """Primeiro e último dia de uma mudança (a permanente vai até o fim do período)."""
    start = period.start_date + timedelta(days=rng.randint(first, last) - 1)
    if spec.kind == PLANTAO:
        while start.weekday() != spec.weekday:
            start += timedelta(days=1)
        end = start
    elif spec.days:
        end = start + timedelta(days=rng.randint(*spec.days) - 1)
    else:
        end = last_day
    return start, min(end, last_day)


def _other_shift(behaviors: BehaviorConfig, role: str, current: str | None) -> str:
    shifts = sorted(behaviors.behaviors[role].shifts or {})
    return next(s for s in shifts if s != current)
