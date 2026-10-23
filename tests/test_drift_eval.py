"""Avaliação com deriva (Fase 8, D55): diferença das diferenças, alarmes por mudança, config."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import ttest_1samp

from evaluation.confirmatory import RunData
from evaluation.drift import (
    WITH,
    WITHOUT,
    affected_windows,
    difference_in_differences,
    false_alarms,
    load_drift_eval,
    planned_runs,
    seed_deltas,
)
from evaluation.experiment import DETECTORS
from evaluation.tuning import load_model_config
from sacla.config import ConfigError


def per_run(f1: dict[tuple[int, str, str], float]) -> pd.DataFrame:
    rows = [
        {
            "seed": seed,
            "condition": condition,
            "detector": detector,
            "f1_mean": value,
            "precision_mean": value,
            "recall_mean": value,
            "scenario_recall_mean": value,
        }
        for (seed, condition, detector), value in f1.items()
    ]
    return pd.DataFrame(rows)


def test_difference_in_differences_is_a_paired_t_test_over_seeds() -> None:
    # IF perde 2, 4 e 3 pontos; as regras perdem 5, 8 e 4: DiD = +3, +4 e +1.
    losses = {"isolation_forest": [0.02, 0.04, 0.03], "regras": [0.05, 0.08, 0.04]}
    table = {}
    for detector, values in losses.items():
        for seed, loss in enumerate(values):
            table[(seed, WITHOUT, detector)] = 0.80
            table[(seed, WITH, detector)] = 0.80 - loss
    deltas = seed_deltas(per_run(table))
    forest = deltas[deltas["detector"] == "isolation_forest"].sort_values("seed")
    assert forest["delta_f1"].to_numpy() == pytest.approx([-0.02, -0.04, -0.03])
    result = difference_in_differences(deltas, "f1", "isolation_forest", "regras", 0.95)
    did = np.array([0.03, 0.04, 0.01])
    assert result["diff"] == pytest.approx(did.mean())
    assert result["p"] == pytest.approx(ttest_1samp(did, 0.0).pvalue)
    assert result["diff_low"] < result["diff"] < result["diff_high"]
    assert result["seeds"] == 3


def test_affected_windows_match_user_and_period() -> None:
    windows = pd.DataFrame(
        {
            "user": ["ana", "ana", "ana", "bia"],
            "window_start_ms": [0, 100, 200, 100],
            "window_end_ms": [100, 200, 300, 200],
        }
    )
    changes = pd.DataFrame([{"change": "ferias", "user": "ana", "start_ms": 150, "end_ms": 250}])
    masks = affected_windows(windows, changes)
    # Sobreposição parcial conta (a janela 100–200 e a 200–300 tocam o período 150–250).
    assert masks["ferias"].tolist() == [False, True, True, False]


def test_false_alarms_count_only_normal_windows_and_average_the_seeds() -> None:
    windows = pd.DataFrame(
        {
            "user": ["ana"] * 4,
            "window_start_ms": [0, 100, 200, 300],
            "window_end_ms": [100, 200, 300, 400],
            "label": [0, 0, 1, 0],
        }
    )
    forest = np.array([[True, False], [True, True], [True, True], [False, False]])
    rules = np.array([[False], [True], [True], [False]])
    flags = {
        "isolation_forest": forest,
        "if_sem_rotulos": np.zeros((4, 2), bool),
        "regras": rules,
        "if_mais_regras": forest | rules,
    }
    run = RunData("r1", WITH, windows, flags, pd.DataFrame())
    changes = {
        "r1": pd.DataFrame([{"change": "pico", "user": "ana", "start_ms": 0, "end_ms": 250}])
    }
    table = false_alarms([run], changes).set_index(["change", "detector"])
    # Afetadas e normais: janelas 0 e 1 (a 2 é anômala). IF: (0,5 + 1) / 2; regras: 1 / 2.
    assert table.loc[("pico", "isolation_forest"), "false_alarm_rate"] == pytest.approx(0.75)
    assert table.loc[("pico", "regras"), "false_alarm_rate"] == pytest.approx(0.5)
    assert table.loc[("pico", "regras"), "normal_windows"] == 2
    assert table.loc[("nao_afetadas", "isolation_forest"), "false_alarm_rate"] == 0.0
    assert set(table.index.get_level_values("detector")) == set(DETECTORS)


def test_project_config_pairs_every_seed_with_and_without_drift() -> None:
    config = load_drift_eval(load_model_config().raw)
    assert [h.id for h in config.hypotheses] == ["H4", "H5"]
    assert config.run_suffix == "-deriva"
    runs = planned_runs(config, {s: f"sim-s{s}-28d" for s in config.seeds})
    assert len(runs) == 2 * len(config.seeds) == 20
    assert runs[:2] == [(101, WITHOUT, "sim-s101-28d"), (101, WITH, "sim-s101-28d-deriva")]


def test_drift_config_rejects_an_unknown_test() -> None:
    raw = load_model_config().raw
    bad = {
        **raw,
        "drift": {
            **raw["drift"],
            "hypotheses": [
                {
                    "id": "H9",
                    "test": "chute",
                    "metric": "f1",
                    "a": "regras",
                    "b": "isolation_forest",
                }
            ],
        },
    }
    with pytest.raises(ConfigError):
        load_drift_eval(bad)
