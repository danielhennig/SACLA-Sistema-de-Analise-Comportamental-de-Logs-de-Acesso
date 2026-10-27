"""Diagrama do fluxo do experimento para a monografia (docs/monografia/figuras/fluxo.png).

Usa os mesmos tokens de cor e tipografia das figuras da avaliação (evaluation.plots).
Uso (serviço `analise`): python docs/monografia/diagramas.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from evaluation.plots import AXIS, INK, SECONDARY, SEQUENTIAL, SURFACE

OUT = Path(__file__).resolve().parent / "figuras" / "fluxo.png"
WIDTH_IN, HEIGHT_IN, DPI = 6.3, 3.3, 300
BOX_W, BOX_H = 0.205, 0.17
LAB_FILL, SACLA_FILL, EVAL_FILL = "#eeede8", SEQUENTIAL[0], "#f6f1e3"
ROWS = {"Laboratório": 0.80, "SACLA": 0.49, "Avaliação": 0.17}
COLUMNS = (0.19, 0.42, 0.65, 0.88)

BOXES = {
    "simulador": ("Laboratório", 0, "Simulador", "usuários, ruído\ne anomalias", LAB_FILL),
    "executor": ("Laboratório", 1, "Executor", "comandos SQL\nreais", LAB_FILL),
    "postgres": ("Laboratório", 2, "PostgreSQL 18", "Pagila; jsonlog\ne auto_explain", LAB_FILL),
    "retime": ("Laboratório", 3, "Remapeamento", "horários\nsimulados", LAB_FILL),
    "leitura": ("SACLA", 0, "Leitura", "linhas do log\nviram eventos", SACLA_FILL),
    "janelas": ("SACLA", 1, "Janelas de 5 min", "28 atributos;\nhistórico do usuário", SACLA_FILL),
    "modelo": ("SACLA", 2, "Isolation Forest", "escore e\nlimiar", SACLA_FILL),
    "relatorio": ("SACLA", 3, "Relatório", "alertas explicados\ne episódios", SACLA_FILL),
    "manifesto": ("Avaliação", 0, "Manifesto", "rótulos, fora\ndo log", EVAL_FILL),
    "avaliacao": ("Avaliação", 2, "Avaliação", "métricas, regras\ne estatística", EVAL_FILL),
}
ARROWS = [
    ("simulador", "executor"),
    ("executor", "postgres"),
    ("postgres", "retime"),
    ("leitura", "janelas"),
    ("janelas", "modelo"),
    ("modelo", "relatorio"),
    ("manifesto", "avaliacao"),
    ("modelo", "avaliacao"),
]
GUTTER = 0.035  # afastamento das setas em ângulo reto em relação às caixas


def center(key: str) -> tuple[float, float]:
    row, column, *_ = BOXES[key]
    return COLUMNS[column], ROWS[row]


def elbow(ax: plt.Axes, points: list[tuple[float, float]]) -> None:
    """Seta em ângulo reto: segmentos retos e a ponta no último trecho."""
    xs, ys = zip(*points[:-1], strict=True)
    ax.plot(xs, ys, color=SECONDARY, linewidth=0.9, solid_capstyle="butt")
    ax.add_patch(
        FancyArrowPatch(points[-2], points[-1], arrowstyle="-|>", mutation_scale=9,
                        color=SECONDARY, linewidth=0.9, shrinkA=0, shrinkB=1)
    )


def main() -> None:
    plt.rcParams.update({"font.family": "sans-serif", "font.size": 7.5})
    fig = plt.figure(figsize=(WIDTH_IN, HEIGHT_IN), facecolor=SURFACE)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for name, y in ROWS.items():
        ax.text(0.008, y, name, rotation=90, ha="left", va="center", color=SECONDARY,
                fontsize=8, fontweight="bold")
    for key, (_, _, title, detail, fill) in BOXES.items():
        x, y = center(key)
        ax.add_patch(
            FancyBboxPatch(
                (x - BOX_W / 2, y - BOX_H / 2), BOX_W, BOX_H,
                boxstyle="round,pad=0,rounding_size=0.015",
                facecolor=fill, edgecolor=AXIS, linewidth=0.8,
            )
        )
        ax.text(x, y + 0.035, title, ha="center", va="center", color=INK, fontsize=8,
                fontweight="bold")
        ax.text(x, y - 0.03, detail, ha="center", va="center", color=SECONDARY, fontsize=7,
                linespacing=1.2)
    for start, end in ARROWS:
        (x0, y0), (x1, y1) = center(start), center(end)
        if y0 == y1:  # mesma linha: da borda direita à esquerda
            a, b = (x0 + BOX_W / 2, y0), (x1 - BOX_W / 2, y1)
        else:  # mesma coluna: de cima para baixo
            a, b = (x0, y0 - BOX_H / 2), (x1, y1 + BOX_H / 2)
        ax.add_patch(
            FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=9, color=SECONDARY,
                            linewidth=0.9, shrinkA=1, shrinkB=1)
        )
    # Remapeamento -> leitura: desce, corre entre as linhas e desce de novo.
    (rx, ry), (lx, ly) = center("retime"), center("leitura")
    middle = ((ry - BOX_H / 2) + (ly + BOX_H / 2)) / 2
    elbow(ax, [(rx, ry - BOX_H / 2), (rx, middle), (lx, middle), (lx, ly + BOX_H / 2)])
    # Simulador -> manifesto: pela esquerda das caixas, sem cruzar a leitura.
    (sx, sy), (mx, my) = center("simulador"), center("manifesto")
    side = sx - BOX_W / 2 - GUTTER
    elbow(ax, [(sx - BOX_W / 2, sy), (side, sy), (side, my), (mx - BOX_W / 2, my)])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=DPI, facecolor=SURFACE)
    print(f"ok {OUT}")


if __name__ == "__main__":
    main()
