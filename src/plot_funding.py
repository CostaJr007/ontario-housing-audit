"""Render the two documented provincial/federal contrasts as an editorial chart."""
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from src.common import PROCESSED, REPORTS, read_json


def main():
    summary = read_json(PROCESSED / "funding_summary.json")
    with (PROCESSED / "funding_comparison.csv").open(encoding="utf-8", newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["bff_award_announced_cad"]]
    if len(rows) != 2:
        raise ValueError("This case-study layout expects exactly two documented award cases")
    fig = plt.figure(figsize=(12, 13), facecolor="#f5f3ee")
    navy, muted, green, purple = "#172d3a", "#566272", "#218b72", "#70539b"
    fig.text(.07, .955, "ONTARIO  /  TWO HOUSING FUNDING RULES", color=muted, fontsize=11, weight="bold")
    millions = summary["selected_bff_awards_announced_cad"] / 1_000_000
    fig.text(.07, .91, f"CAD {millions:.1f} million", color=navy, fontsize=40, weight="bold", va="top")
    fig.text(.07, .835, "in announced provincial awards to two municipalities\nwith documented adverse federal HAF decisions.", color=navy, fontsize=18, linespacing=1.4, va="top")
    for index, row in enumerate(rows):
        top = .72 - index * .255
        fig.add_artist(FancyBboxPatch((.06, top-.22), .88, .22, boxstyle="round,pad=0.008,rounding_size=0.012",
                                     transform=fig.transFigure, facecolor="white", edgecolor="#e4e1d9", zorder=0))
        fig.text(.085, top-.035, row["municipality"], color=navy, fontsize=22, weight="bold")
        pct = float(row["provincial_progress_pct"])
        award = float(row["bff_award_announced_cad"]) / 1_000_000
        fig.text(.57, top-.035, f"BFF: C${award:.1f}M", color=green, fontsize=15, weight="bold")
        fig.text(.085, top-.065, "Official progress / 2024 provincial target", color=muted, fontsize=11)
        ax = fig.add_axes((.085, top-.135, .64, .055), facecolor="white")
        ax.barh([0], [pct], height=.40, color=green)
        ax.axvline(80, color="#b3b6b8", linewidth=1, linestyle=":")
        ax.axvline(100, color=navy, linewidth=1, linestyle="--")
        ax.set_xlim(0, 240)
        ax.set_ylim(-.45, .45)
        ax.set_yticks([])
        ax.set_xticks([0, 80, 100, 200], labels=["0", "80%", "100%", "200%"])
        ax.tick_params(axis="x", labelsize=9, length=0, colors=muted)
        for spine in ax.spines.values():
            spine.set_visible(False)
        fig.text(.77, top-.11, f"{pct:.1f}%", color=green, fontsize=23, weight="bold")
        date = row["haf_event_date"][:7]
        fig.text(.085, top-.195, f"Federal HAF: {row['haf_event_label_en'].lower()} ({date})", color=purple, fontsize=13, weight="bold")
    fig.text(.07, .205, "What each program requires", color=navy, fontsize=17, weight="bold")
    fig.text(.07, .17, "Provincial · BFF", color=green, fontsize=13, weight="bold")
    fig.text(.07, .145, "At least 80% of the annual\nofficial housing-progress target.", color=muted, fontsize=12, linespacing=1.4, va="top")
    fig.text(.52, .17, "Federal · HAF", color=purple, fontsize=13, weight="bold")
    fig.text(.52, .145, "Committed municipal reforms\nand permitted housing-unit targets.", color=muted, fontsize=12, linespacing=1.4, va="top")
    fig.text(.07, .072, "2024 HAF events; BFF awards announced in 2025 for 2024 performance.\nTwo selected cases. Announced amounts; actual cash receipts have not been reconciled.", color=muted, fontsize=9, linespacing=1.4, va="top")
    fig.text(.07, .028, "Sources: Ontario Data Catalogue; official BFF releases, August 12 and September 24, 2025;\nCity of Windsor, CM 9/2024; Town of Oakville, September 2025 White Paper.", color=muted, fontsize=9, linespacing=1.4, va="top")
    REPORTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORTS / "funding_contrast.png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    main()
