"""Deriva de rotina (Fase 8, D55): sem deriva nada muda; com deriva, cada mudança faz o que diz.

Usa a configuração real do projeto e pools de ids sintéticos (não precisa de banco).
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path

import pandas as pd
import pytest

from sacla.config import ConfigError
from simlab.anomalies import load_anomalies
from simlab.behavior import SAME_ROUTINE, BehaviorConfig, load_behaviors
from simlab.catalog import Catalog, load_catalog
from simlab.drift import (
    CRESCIMENTO,
    DRIFT_FILE,
    FERIAS,
    HOME_OFFICE,
    NOVA_ROTINA,
    PICO,
    PLANTAO,
    TROCA_TURNO,
    DriftConfig,
    DriftPlan,
    load_drift,
    plan_drift,
)
from simlab.lab import load_experiment
from simlab.profiles import Profiles, load_profiles
from simlab.schedule import Schedule, SimulationSettings, build_schedule, events_frame
from simlab.timeline import CONNECT, STATEMENT

DAYS = 28
SEED = 3
IDS = {
    pool: list(range(1, n + 1))
    for pool, n in {
        "customer": 999,
        "film": 1000,
        "inventory": 4581,
        "staff": 1500,
        "store": 500,
        "rental": 51805,
        "payment": 51061,
        "category": 16,
        "city": 600,
    }.items()
}


@cache
def _inputs() -> tuple[SimulationSettings, Profiles, BehaviorConfig, Catalog, DriftConfig]:
    profiles = load_profiles()
    catalog = load_catalog()
    behaviors = load_behaviors(profiles, catalog)
    settings = SimulationSettings.from_experiment(load_experiment(), seed=SEED, days=DAYS)
    return settings, profiles, behaviors, catalog, load_drift(profiles, behaviors, catalog)


def _build(drift: DriftPlan | None) -> Schedule:
    settings, profiles, behaviors, catalog, _ = _inputs()
    anomalies = load_anomalies(profiles, behaviors, catalog)
    return build_schedule(settings, profiles, behaviors, catalog, anomalies, IDS, drift)


@cache
def _plan() -> DriftPlan:
    settings, profiles, behaviors, _, config = _inputs()
    return plan_drift(config, profiles, behaviors, settings.period, settings.seed)


@cache
def _drifted() -> Schedule:
    return _build(_plan())


def _local(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000, tz=_inputs()[0].period.tz)


def _sessions(schedule: Schedule, user: str) -> list[datetime]:
    """Inícios das sessões NORMAIS do usuário (as de anomalias têm cenário)."""
    return [
        _local(e.ts_ms)
        for e in schedule.events
        if e.kind == CONNECT and e.user == user and e.scenario is None
    ]


def _changes(kind: str) -> list:  # type: ignore[type-arg]
    return [c for c in _plan().changes if c.kind == kind]


def test_without_drift_the_schedule_is_identical() -> None:
    # Regressão principal: a rotina padrão e um plano vazio não mudam nenhum evento.
    plain, empty = _build(None), _build(DriftPlan(changes=[], routines={}))
    assert events_frame(plain.events).equals(events_frame(empty.events))
    assert [(s.user, s.start_ms, s.type) for s in plain.scenarios] == [
        (s.user, s.start_ms, s.type) for s in empty.scenarios
    ]
    day = date(2026, 3, 10)
    assert SAME_ROUTINE.rate_multiplier(day) == 1.0 and not SAME_ROUTINE.absent(day)


def test_plan_follows_the_catalog_and_repeats_with_the_seed() -> None:
    settings, profiles, behaviors, _, config = _inputs()
    again = plan_drift(config, profiles, behaviors, settings.period, settings.seed)
    assert again.changes == _plan().changes
    period_start = settings.period.start_date
    for spec in config.changes:
        found = _changes(spec.kind)
        assert len(found) == spec.users
        assert len({c.user for c in found}) == spec.users  # usuários distintos na mudança
        for change in found:
            assert change.role in spec.roles
            day = (change.first_day - period_start).days + 1
            if spec.kind != PLANTAO:  # o plantão anda até o sábado seguinte
                assert config.start_day[0] <= day <= config.start_day[1]
            if spec.days:
                length = (change.last_day - change.first_day).days + 1
                cut = change.last_day == settings.period.start_date + timedelta(days=DAYS - 1)
                assert length <= spec.days[1] and (cut or length >= spec.days[0])
    other = plan_drift(config, profiles, behaviors, settings.period, SEED + 1)
    assert other.changes != _plan().changes
    # Temporárias do mesmo usuário nunca se sobrepõem.
    temporary = [c for c in _plan().changes if c.kind in (FERIAS, PICO, PLANTAO)]
    for a in temporary:
        for b in temporary:
            if a is not b and a.user == b.user:
                assert a.last_day < b.first_day or b.last_day < a.first_day


def test_vacation_has_no_sessions() -> None:
    for change in _changes(FERIAS):
        days = {s.date() for s in _sessions(_drifted(), change.user)}
        off = {
            change.first_day + timedelta(days=i)
            for i in range((change.last_day - change.first_day).days + 1)
        }
        assert not days & off


def test_shift_change_moves_the_sessions_to_the_new_shift() -> None:
    _, _, behaviors, _, _ = _inputs()
    for change in _changes(TROCA_TURNO):
        start, end = behaviors.behaviors[change.role].shifts[change.shift]  # type: ignore[index]
        after = [s for s in _sessions(_drifted(), change.user) if s.date() >= change.first_day]
        assert after, "o usuário trabalha depois da troca"
        # Início da sessão dentro do turno novo (com folga para a variação do horário).
        lo = datetime.combine(date.today(), start) - timedelta(hours=1)
        hi = datetime.combine(date.today(), end)
        assert all(lo.time() <= s.time() <= hi.time() for s in after)


def test_peak_and_growth_multiply_the_rate() -> None:
    for change in _changes(PICO):
        routine = _plan().routines[change.user]
        assert routine.rate_multiplier(change.first_day) == pytest.approx(change.rate_multiplier)
        assert routine.rate_multiplier(change.first_day - timedelta(days=1)) == 1.0
    for change in _changes(CRESCIMENTO):
        routine = _plan().routines[change.user]
        two_weeks = change.first_day + timedelta(days=14)
        if two_weeks <= change.last_day:
            expected = (1 + change.weekly_growth) ** 2
            assert routine.rate_multiplier(two_weeks) == pytest.approx(expected)
    # Efeito real na agenda: mais comandos normais do usuário durante o pico.
    plain = _build(None)
    for change in _changes(PICO):
        span = (change.first_day, change.last_day)
        assert _statements(_drifted(), change.user, span) > _statements(plain, change.user, span)


def _statements(schedule: Schedule, user: str, span: tuple[date, date]) -> int:
    return sum(
        1
        for e in schedule.events
        if e.user == user
        and e.kind == STATEMENT
        and e.scenario is None
        and span[0] <= _local(e.ts_ms).date() <= span[1]
    )


def test_home_office_uses_the_new_network_weights() -> None:
    for change in _changes(HOME_OFFICE):
        routine = _plan().routines[change.user]
        assert routine.networks(change.first_day, {"lan": 1.0}) == change.networks
        nets = {
            e.network
            for e in _drifted().events
            if e.user == change.user
            and e.kind == CONNECT
            and _local(e.ts_ms).date() >= change.first_day
        }
        assert "externa" in nets


def test_new_routine_reads_tables_never_used_before() -> None:
    for change in _changes(NOVA_ROTINA):
        reads = [
            _local(e.ts_ms).date()
            for e in _drifted().events
            if e.user == change.user and e.statement and "FROM city" in e.statement.sql
        ]
        assert reads and min(reads) >= change.first_day
        plain = [e for e in _build(None).events if e.statement and "FROM city" in e.statement.sql]
        assert not plain


def test_weekend_duty_adds_a_saturday_session() -> None:
    for change in _changes(PLANTAO):
        assert change.first_day.weekday() == 5 and change.first_day == change.last_day
        days = {s.date() for s in _sessions(_drifted(), change.user)}
        assert change.first_day in days
        assert change.first_day not in {s.date() for s in _sessions(_build(None), change.user)}


def test_off_hours_scenarios_avoid_the_shift_of_the_day() -> None:
    _, profiles, behaviors, _, _ = _inputs()
    schedule = _drifted()
    for sc in schedule.scenarios:
        routine = _plan().routines.get(sc.user)
        if sc.type != "fora_horario" or routine is None:
            continue
        behavior = behaviors.behaviors[sc.role]
        user = profiles.user(sc.user)
        start = _local(sc.start_ms)
        day = start.date()
        works = day.weekday() in behavior.weekdays or routine.on_duty(day)
        if not works or routine.absent(day):
            continue
        shift_start, shift_end = behavior.shifts[routine.shift(day, user.shift)]  # type: ignore[index]
        margin = timedelta(minutes=behavior.off_hours_margin_min)
        busy_from = datetime.combine(day, shift_start, tzinfo=start.tzinfo) - margin
        busy_to = datetime.combine(day, shift_end, tzinfo=start.tzinfo) + margin
        assert not busy_from <= start <= busy_to


def test_exported_events_carry_no_drift_information(tmp_path: Path) -> None:
    from simlab.schedule import write_schedule

    settings, *_ = _inputs()
    drifted = replace(settings, data_dir=tmp_path, run_suffix="-deriva")
    write_schedule(_drifted(), drifted, tmp_path, "pools")
    assert list(events_frame(_drifted().events).columns) == list(
        events_frame(_build(None).events).columns
    )
    frame = pd.read_csv(tmp_path / DRIFT_FILE)
    assert len(frame) == len(_plan().changes)
    assert set(frame["change"]) == {c.kind for c in _plan().changes}
    run = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert run["drift"] is True and "drift.yaml" in run["config_sha256"]
    assert drifted.run_id.endswith("-deriva")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("troca_turno: {roles: [gerente], users: 1}", "outro turno"),
        ("plantao: {roles: [gerente], users: 1, weekday: 2}", "já é de trabalho"),
        ("ferias: {roles: [svc_x], users: 1, days: [1, 2]}", "papel desconhecido"),
        ("teletransporte: {roles: [gerente], users: 1}", "desconhecida"),
        ("home_office: {roles: [gerente], users: 1, networks: {marte: 1}}", "redes"),
    ],
)
def test_invalid_catalog_is_rejected(tmp_path: Path, change: str, message: str) -> None:
    path = tmp_path / "drift.yaml"
    path.write_text(
        f"run_suffix: '-d'\nstart_day: [2, 5]\nmax_attempts: 10\nchanges:\n  {change}\n",
        encoding="utf-8",
    )
    _, profiles, behaviors, catalog, _ = _inputs()
    with pytest.raises(ConfigError, match=message):
        load_drift(profiles, behaviors, catalog, path)
