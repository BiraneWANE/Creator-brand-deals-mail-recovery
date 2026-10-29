#!/usr/bin/env python3
"""Produit les figures du README à partir des agrégats anonymes (docs/figures/agregats.json).

Seuls des comptages sont publiés : ni nom, ni adresse, ni montant. Palette validée pour les
daltonismes (contrôle ΔE OKLab) ; chaque barre porte sa valeur, la couleur n'est jamais seule.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "docs" / "figures"
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # ordre fixe, validé


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=10, length=0)


def funnel(data: dict) -> None:
    labels, values = zip(*data["entonnoir"], strict=True)
    fig, ax = plt.subplots(figsize=(9, 3.6), facecolor=SURFACE)
    _style(ax)
    y = range(len(values))[::-1]
    ax.barh(list(y), values, color=SERIES[0], height=0.55)
    ax.set_xscale("log")
    ax.set_yticks(list(y), labels, color=INK)
    ax.set_xticks([])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.spines["bottom"].set_visible(False)
    for yi, v in zip(y, values, strict=True):
        ax.text(v * 1.08, yi, f"{v:,}".replace(",", " "), va="center", color=INK, fontsize=11, fontweight="bold")
    ax.set_xlim(right=max(values) * 4)
    ax.set_title("De la boîte mail au fichier de relance (échelle logarithmique)", loc="left", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(ROOT / "entonnoir.png", dpi=160)


def by_year(data: dict) -> None:
    cats = [("produit offert", "Produit offert"), ("payée", "Collab payée"), ("événement", "Événement"),
            (None, "Autres (campagne, UGC, mixte)")]
    years = sorted(y for y in data["partenariats_par_annee_et_type"] if y >= "2020")
    fig, ax = plt.subplots(figsize=(9, 4.2), facecolor=SURFACE)
    _style(ax)
    bottom = [0] * len(years)
    for (key, label), color in zip(cats, SERIES, strict=True):
        vals = []
        for y in years:
            row = data["partenariats_par_annee_et_type"][y]
            vals.append(row.get(key, 0) if key else sum(v for k, v in row.items()
                                                      if k not in ("produit offert", "payée", "événement")))
        ax.bar(years, vals, bottom=bottom, color=color, label=label, width=0.62, edgecolor=SURFACE, linewidth=2)
        bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
    for x, total in zip(years, bottom, strict=True):
        ax.text(x, total + 1.5, str(total), ha="center", color=INK, fontsize=10, fontweight="bold")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel("Nouveaux partenariats", color=INK2)
    ax.legend(frameon=False, ncol=4, loc="upper left", bbox_to_anchor=(0, -0.1), fontsize=9, labelcolor=INK)
    ax.set_title("Nouveaux partenariats par année et par type (2026 : jusqu'à fin octobre)", loc="left",
                 color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(ROOT / "partenariats_par_annee.png", dpi=160)


if __name__ == "__main__":
    agg = json.loads((ROOT / "agregats.json").read_text(encoding="utf-8"))
    funnel(agg)
    by_year(agg)
    print("Figures écrites dans", ROOT)
