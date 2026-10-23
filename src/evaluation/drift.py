"""Tráfego normal não estacionário (Fase 8; pré-registro em docs/decisoes.md, D55).

Cada semente tem duas simulações: sem deriva (sim-s<semente>-28d) e com as mudanças legítimas
de rotina de config/drift.yaml (...-deriva). A configuração do experimento fica congelada, e
cada simulação é avaliada com o protocolo da robustez (D36). Mede-se quanto cada detector perde
com a deriva:
- H4: diferença das diferenças por semente, [IF com − sem] − [regras com − sem], com teste t
  pareado nas sementes;
- H5: IF ∪ regras × regras nos cenários, no agregado com deriva (McNemar exato);
- alarmes falsos nas janelas normais afetadas por cada mudança (drift.csv, nunca o log).
Saída: results/deriva/<exp_id>/.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
from scipy.stats import ttest_rel

from evaluation.confirmatory import (
    Resampler,
    RunData,
    flags_frame,
    interval_table,
    pool,
    run_data,
)
from evaluation.experiment import DETECTORS
from evaluation.robustness import NAMES, evaluate_run, frozen_setup
from evaluation.rules_baseline import load_rules
from evaluation.stats import (
    Comparison,
    StatsConfig,
    holm,
    load_stats_config,
    mcnemar_exact,
    mean_interval,
)
from evaluation.tuning import load_model_config
from evaluation.validation_plots import drift_figures
from sacla.config import CONFIG_DIR, PROJECT_ROOT, ConfigError, SaclaSettings, load_yaml

log = logging.getLogger(__name__)

WITHOUT, WITH = "sem_deriva", "com_deriva"
CONDITION_NAMES = {WITHOUT: "sem deriva", WITH: "com deriva"}
TESTS = ("did_t", "mcnemar")
# Medidas por simulação (colunas da tabela de comparação) usadas nas diferenças por semente.
MEASURES = {
    "f1": "f1_mean",
    "precision": "precision_mean",
    "recall": "recall_mean",
    "scenarios": "scenario_recall_mean",
}
DRIFT_FILE = "drift.csv"
REPRODUCED = ("precision_mean", "recall_mean", "f1_mean", "scenario_recall_mean")
REPRODUCTION_TOLERANCE = 1e-9


@dataclass(frozen=True)
class DriftHypothesis:
    id: str
    test: str
    metric: str
    a: str
    b: str
    subset: str = "all"


@dataclass(frozen=True)
class DriftEvalConfig:
    seeds: tuple[int, ...]
    results_dir: str
    hypotheses: tuple[DriftHypothesis, ...]
    run_suffix: str


def load_drift_eval(raw: dict[str, Any], drift_yaml: Path | None = None) -> DriftEvalConfig:
    """Seção `drift` de config/model.yaml e o sufixo das simulações (config/drift.yaml)."""
    try:
        section = raw["drift"]
        config = DriftEvalConfig(
            seeds=tuple(int(s) for s in section["simulation_seeds"]),
            results_dir=str(section["results_dir"]),
            hypotheses=tuple(
                DriftHypothesis(
                    id=str(h["id"]),
                    test=str(h["test"]),
                    metric=str(h["metric"]),
                    a=str(h["a"]),
                    b=str(h["b"]),
                    subset=str(h.get("subset", "all")),
                )
                for h in section["hypotheses"]
            ),
            run_suffix=str(load_yaml(drift_yaml or CONFIG_DIR / "drift.yaml")["run_suffix"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"model.yaml: seção drift malformada ({exc!r})") from exc
    if len(config.seeds) < 2 or len(set(config.seeds)) != len(config.seeds):
        raise ConfigError("drift: ao menos duas sementes, sem repetição")
    for h in config.hypotheses:
        if h.test not in TESTS or h.a not in DETECTORS or h.b not in DETECTORS or h.a == h.b:
            raise ConfigError(f"drift: hipótese inválida {h}")
        if h.metric not in MEASURES or (h.test == "mcnemar" and h.metric != "scenarios"):
            raise ConfigError(f"drift: métrica inválida em {h}")
    return config


# --- Diferenças por semente ------------------------------------------------------------------


def seed_deltas(per_run: pd.DataFrame) -> pd.DataFrame:
    """Por semente e detector: cada medida sem e com deriva e a perda (com − sem)."""
    wide = per_run.pivot_table(
        index=["seed", "detector"], columns="condition", values=list(MEASURES.values())
    )
    rows = []
    for key, row in wide.iterrows():
        seed, detector = cast(tuple[int, str], key)
        item: dict[str, Any] = {"seed": seed, "detector": detector}
        for metric, column in MEASURES.items():
            item[f"{metric}_{WITHOUT}"] = float(row[(column, WITHOUT)])
            item[f"{metric}_{WITH}"] = float(row[(column, WITH)])
            item[f"delta_{metric}"] = item[f"{metric}_{WITH}"] - item[f"{metric}_{WITHOUT}"]
        rows.append(item)
    return pd.DataFrame(rows)


def difference_in_differences(
    deltas: pd.DataFrame, metric: str, a: str, b: str, confidence: float
) -> dict[str, float]:
    """Média de [a com − sem] − [b com − sem] nas sementes, intervalo t e teste t pareado."""
    column = f"delta_{metric}"
    da = deltas[deltas["detector"] == a].set_index("seed")[column]
    db = deltas[deltas["detector"] == b].set_index("seed")[column].reindex(da.index)
    did = (da - db).to_numpy(dtype=float)
    mean, low, high = mean_interval(did, confidence)
    p = float(ttest_rel(da.to_numpy(dtype=float), db.to_numpy(dtype=float)).pvalue)
    return {
        "delta_a": float(da.mean()),
        "delta_b": float(db.mean()),
        "diff": mean,
        "diff_low": low,
        "diff_high": high,
        "seeds": len(did),
        "p": p,
    }


def hypothesis_table(
    config: DriftEvalConfig,
    deltas: pd.DataFrame,
    drifted: Resampler,
    stats: StatsConfig,
) -> pd.DataFrame:
    rows = []
    for h in config.hypotheses:
        row: dict[str, Any] = {"id": h.id, "test": h.test, "metric": h.metric, "a": h.a, "b": h.b}
        if h.test == "did_t":
            row.update(difference_in_differences(deltas, h.metric, h.a, h.b, stats.confidence))
        else:
            test = mcnemar_exact(drifted.majority(h.a, h.subset), drifted.majority(h.b, h.subset))
            row.update(drifted.difference(Comparison(h.metric, h.subset, h.a, h.b)))
            row.update(only_a=test["only_a"], only_b=test["only_b"], p=test["p"])
        rows.append(row)
    table = pd.DataFrame(rows)
    table["p_holm"] = holm(table["p"].tolist())
    table["alpha"] = stats.alpha
    table["rejects_h0"] = table["p_holm"] <= stats.alpha
    return table


def loss_table(deltas: pd.DataFrame, confidence: float) -> pd.DataFrame:
    """Perda média (com − sem) de cada detector, com intervalo t nas sementes."""
    rows = []
    for detector in DETECTORS:
        frame = deltas[deltas["detector"] == detector]
        row: dict[str, Any] = {"detector": detector, "seeds": len(frame)}
        for metric in MEASURES:
            mean, low, high = mean_interval(frame[f"delta_{metric}"].to_numpy(), confidence)
            row[f"{metric}_{WITHOUT}"] = float(frame[f"{metric}_{WITHOUT}"].mean())
            row[f"{metric}_{WITH}"] = float(frame[f"{metric}_{WITH}"].mean())
            row[f"delta_{metric}_mean"] = mean
            row[f"delta_{metric}_low"] = low
            row[f"delta_{metric}_high"] = high
            row[f"delta_{metric}_worse_seeds"] = int((frame[f"delta_{metric}"] < 0).sum())
        rows.append(row)
    return pd.DataFrame(rows)


# --- Alarmes falsos nas janelas afetadas -----------------------------------------------------


def affected_windows(
    windows: pd.DataFrame, changes: pd.DataFrame
) -> dict[str, np.ndarray[Any, Any]]:
    """Por mudança: máscara das janelas do usuário que se sobrepõem ao período dela."""
    masks: dict[str, np.ndarray[Any, Any]] = {}
    for change in changes.itertuples(index=False):
        hit = (
            (windows["user"] == change.user)
            & (windows["window_start_ms"] < change.end_ms)
            & (windows["window_end_ms"] > change.start_ms)
        ).to_numpy()
        masks[str(change.change)] = (
            masks.get(str(change.change), np.zeros(len(windows), bool)) | hit
        )
    return masks


def false_alarms(runs: list[RunData], changes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Fração das janelas normais de teste sinalizadas, por mudança e detector (média nas
    sementes do modelo), e a mesma fração nas janelas normais não afetadas.

    `share_of_false_alarms`: parte de todos os alarmes falsos do detector nas simulações com
    deriva que cai nas janelas da mudança (uma janela de duas mudanças conta nas duas).
    """
    counts: dict[tuple[str, str], list[float]] = {}
    totals = dict.fromkeys(DETECTORS, 0.0)
    for data in runs:
        normal = data.windows["label"].to_numpy() == 0
        for detector in DETECTORS:
            totals[detector] += float(data.flags[detector][normal].mean(axis=1).sum())
        masks = affected_windows(data.windows, changes[data.run_id])
        any_change = np.zeros(len(data.windows), bool)
        for mask in masks.values():
            any_change |= mask
        masks["nao_afetadas"] = ~any_change
        for change, mask in masks.items():
            selected = mask & normal
            for detector in DETECTORS:
                flagged = data.flags[detector][selected]
                key = (change, detector)
                total = counts.setdefault(key, [0.0, 0.0])
                total[0] += float(flagged.mean(axis=1).sum()) if len(flagged) else 0.0
                total[1] += float(selected.sum())
    rows = [
        {
            "change": change,
            "detector": detector,
            "normal_windows": int(windows),
            "false_alarms": flagged,
            "false_alarm_rate": flagged / windows if windows else float("nan"),
            "share_of_false_alarms": flagged / totals[detector] if totals[detector] else 0.0,
        }
        for (change, detector), (flagged, windows) in counts.items()
    ]
    return pd.DataFrame(rows)


# --- Execução --------------------------------------------------------------------------------


def planned_runs(config: DriftEvalConfig, stationary: dict[int, str]) -> list[tuple[int, str, str]]:
    """(semente, condição, run_id) de cada simulação, na ordem da avaliação."""
    return [
        (seed, condition, stationary[seed] + (config.run_suffix if condition == WITH else ""))
        for seed in config.seeds
        for condition in (WITHOUT, WITH)
    ]


def run_drift(
    exp_dir: Path,
    stationary: dict[int, str],
    data_root: Path,
    features_root: Path,
    settings: SaclaSettings,
) -> Path:
    params, window, _ = frozen_setup(exp_dir)
    model_config = load_model_config(settings=settings)
    stats = load_stats_config(model_config.raw, DETECTORS)
    config = load_drift_eval(model_config.raw)
    rules = load_rules()
    out = PROJECT_ROOT / config.results_dir / exp_dir.name
    (out / "janelas").mkdir(parents=True, exist_ok=True)

    tables, runs, changes = [], [], {}
    for seed, condition, run_id in planned_runs(config, stationary):
        result = evaluate_run(
            run_id, params, window, model_config, rules, data_root, features_root, settings
        )
        tables.append(result.comparison().assign(seed=seed, condition=condition))
        data = run_data(result, condition)
        flags_frame(data).to_parquet(out / "janelas" / f"{run_id}.parquet", index=False)
        runs.append(data)
        if condition == WITH:
            changes[run_id] = pd.read_csv(data_root / run_id / DRIFT_FILE)
    per_run = pd.concat(tables, ignore_index=True)
    reproduction = reproduction_check(per_run, model_config.raw, exp_dir.name)

    deltas = seed_deltas(per_run)
    losses = loss_table(deltas, stats.confidence)
    resamplers = {
        condition: Resampler(pool([r for r in runs if r.group == condition]), stats)
        for condition in (WITHOUT, WITH)
    }
    hypotheses = hypothesis_table(config, deltas, resamplers[WITH], stats)
    intervals = pd.concat(
        [interval_table(f"agregado_{c}", r) for c, r in resamplers.items()], ignore_index=True
    )
    alarms = false_alarms([r for r in runs if r.group == WITH], changes)
    plan = pd.concat(
        [frame.assign(run_id=run_id) for run_id, frame in changes.items()], ignore_index=True
    )
    for name, table in {
        "drift_runs": per_run,
        "drift_deltas": deltas,
        "drift_losses": losses,
        "hypotheses": hypotheses,
        "intervals": intervals,
        "false_alarms_by_change": alarms,
        "drift_plans": plan,
    }.items():
        table.to_csv(out / f"{name}.csv", index=False, lineterminator="\n")
    summary = {
        "exp_id": exp_dir.name,
        "params": params.as_dict(),
        "seeds": list(config.seeds),
        "runs": [run_id for _, _, run_id in planned_runs(config, stationary)],
        "reproduction": reproduction,
        "stats": model_config.raw["stats"],
        "hypotheses": model_config.raw["drift"]["hypotheses"],
    }
    (out / "deriva.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8"
    )
    report = out / "deriva.md"
    report.write_text(
        markdown(params.slug(), config, hypotheses, losses, intervals, alarms, plan, summary),
        encoding="utf-8",
    )
    drift_figures(out, deltas, losses, alarms, model_config)
    log.info("resultados em %s", out.relative_to(PROJECT_ROOT))
    return report


def reproduction_check(per_run: pd.DataFrame, raw: dict[str, Any], exp_id: str) -> dict[str, Any]:
    """As simulações sem deriva já avaliadas na Fase 7 devem reproduzir os números publicados."""
    path = PROJECT_ROOT / str(raw["confirmatory"]["results_dir"]) / exp_id / "confirmatory_runs.csv"
    if not path.exists():
        return {"compared_runs": [], "max_abs_diff": float("nan")}
    published = pd.read_csv(path)
    merged = per_run[per_run["condition"] == WITHOUT].merge(
        published, on=["run_id", "detector"], suffixes=("", "_publicado")
    )
    gaps = [float((merged[c] - merged[f"{c}_publicado"]).abs().max()) for c in REPRODUCED]
    largest = max(gaps) if not merged.empty else float("nan")
    result = {"compared_runs": sorted(set(merged["run_id"])), "max_abs_diff": largest}
    if not merged.empty and largest > REPRODUCTION_TOLERANCE:
        raise RuntimeError(f"as simulações sem deriva não reproduzem a Fase 7: {result}")
    return result


# --- Relatório -------------------------------------------------------------------------------


def _pct(value: float) -> str:
    return "—" if np.isnan(value) else f"{100 * value:.1f}"


def _signed(value: float, low: float, high: float) -> str:
    return f"{100 * value:+.1f} [{100 * low:+.1f}; {100 * high:+.1f}]"


def _p(value: float) -> str:
    return f"{value:.2g}" if value >= 1e-4 else "< 0.0001"


def _interval(intervals: pd.DataFrame, scope: str, detector: str, metric: str) -> str:
    row = intervals[
        (intervals["scope"] == scope)
        & (intervals["detector"] == detector)
        & (intervals["metric"] == metric)
        & (intervals["subset"] == "all")
    ].iloc[0]
    return f"{_pct(row['value'])} [{_pct(row['low'])}; {_pct(row['high'])}]"


METRIC_NAMES = {
    "f1": "F1",
    "precision": "precisão",
    "recall": "recall",
    "scenarios": "cenários detectados",
}


def markdown(
    slug: str,
    config: DriftEvalConfig,
    hypotheses: pd.DataFrame,
    losses: pd.DataFrame,
    intervals: pd.DataFrame,
    alarms: pd.DataFrame,
    plan: pd.DataFrame,
    summary: dict[str, Any],
) -> str:
    lines = [
        f"# Tráfego não estacionário (configuração congelada `{slug}`)",
        "",
        f"Pré-registro: `docs/decisoes.md`, D55. {len(config.seeds)} sementes, cada uma simulada "
        "sem e com as mudanças de rotina de `config/drift.yaml`. Valores em %; perdas = com − "
        "sem deriva, em pontos percentuais.",
        "",
        "## Hipóteses",
        "",
        "| | Teste | Medida | A | B | Resultado A | Resultado B | A − B [IC] | p | p (Holm) | "
        "Decisão |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in hypotheses.to_dict(orient="records"):
        if row["test"] == "did_t":
            value_a, value_b = (
                f"{100 * row['delta_a']:+.1f} (perda)",
                f"{100 * row['delta_b']:+.1f} (perda)",
            )
        else:
            value_a, value_b = _pct(row["value_a"]), _pct(row["value_b"])
        verdict = "rejeita H0" if row["rejects_h0"] else "não rejeita H0"
        lines.append(
            f"| {row['id']} | {row['test']} | {METRIC_NAMES[row['metric']]} | {NAMES[row['a']]} | "
            f"{NAMES[row['b']]} | {value_a} | {value_b} | "
            f"{_signed(row['diff'], row['diff_low'], row['diff_high'])} | {_p(row['p'])} | "
            f"{_p(row['p_holm'])} | {verdict} |"
        )
    lines += [
        "",
        f"H4: diferença das diferenças por semente e teste t pareado ({len(config.seeds)} "
        "sementes; a simulação é a unidade). H5: McNemar exato no agregado com deriva, com a "
        "detecção em ao menos metade das sementes do modelo. Holm sobre as hipóteses.",
        "",
        "## Perda de cada detector com a deriva (média nas sementes, intervalo t de 95%)",
        "",
        "| Detector | F1 sem → com | Δ F1 | Precisão sem → com | Δ precisão | Cenários sem → com "
        "| Δ cenários |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in losses.to_dict(orient="records"):
        cells = []
        for metric in ("f1", "precision", "scenarios"):
            cells.append(f"{_pct(row[f'{metric}_{WITHOUT}'])} → {_pct(row[f'{metric}_{WITH}'])}")
            cells.append(
                _signed(
                    row[f"delta_{metric}_mean"],
                    row[f"delta_{metric}_low"],
                    row[f"delta_{metric}_high"],
                )
            )
        lines.append(f"| {NAMES[row['detector']]} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Agregado das simulações (intervalo de 95% por bootstrap estratificado)",
        "",
        "| Detector | F1 sem deriva | F1 com deriva | Cenários sem deriva | Cenários com deriva |",
        "|---|---:|---:|---:|---:|",
    ]
    for detector in DETECTORS:
        cells = [
            _interval(intervals, f"agregado_{condition}", detector, metric)
            for metric in ("f1", "scenarios")
            for condition in (WITHOUT, WITH)
        ]
        lines.append(f"| {NAMES[detector]} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Alarmes falsos nas janelas normais de teste afetadas por cada mudança (%)",
        "",
        "| Mudança | Janelas | " + " | ".join(NAMES[d] for d in DETECTORS) + " |",
        "|---|---:|" + "---:|" * len(DETECTORS),
    ]
    # dropna=False: uma mudança sem janelas no teste (férias: o usuário não acessa) fica com "—".
    table = alarms.pivot_table(
        index="change", columns="detector", values="false_alarm_rate", dropna=False
    )
    windows = alarms.groupby("change")["normal_windows"].first()
    order = [*sorted(c for c in windows.index if c != "nao_afetadas"), "nao_afetadas"]
    for change in order:
        name = "(não afetadas)" if change == "nao_afetadas" else change
        cells = [_pct(float(table.loc[change, d])) for d in DETECTORS]
        lines.append(f"| {name} | {int(windows[change])} | " + " | ".join(cells) + " |")
    share = alarms.pivot_table(
        index="change", columns="detector", values="share_of_false_alarms", dropna=False
    )
    lines += [
        "",
        "### Parte de todos os alarmes falsos com deriva que cai nas janelas de cada mudança (%)",
        "",
        "| Mudança | " + " | ".join(NAMES[d] for d in DETECTORS) + " |",
        "|---|" + "---:|" * len(DETECTORS),
    ]
    for change in order:
        name = "(não afetadas)" if change == "nao_afetadas" else change
        cells = [_pct(float(share.loc[change, d])) for d in DETECTORS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += [
        "",
        f"Mudanças sorteadas: {len(plan)} nas {len(config.seeds)} simulações com deriva "
        f"(`drift_plans.csv`); por tipo: "
        + ", ".join(f"{k} {v}" for k, v in plan["change"].value_counts().sort_index().items())
        + ". Nas férias o usuário não acessa o banco: não há janelas afetadas.",
        "",
        "## Conferência",
        "",
    ]
    check = summary["reproduction"]
    if check["compared_runs"]:
        compared = ", ".join(check["compared_runs"])
        lines.append(
            f"- As simulações sem deriva já avaliadas na Fase 7 ({compared}) reproduzem os "
            f"números publicados (diferença máxima: {check['max_abs_diff']:.1e})."
        )
    lines.append("")
    return "\n".join(lines)
