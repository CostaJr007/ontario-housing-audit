"""Produce a readable 4:5 feed graphic and scalable master from the audited map."""
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import box

from src.bff import SOUTH_BOUNDS
from src.common import REPORTS


def render(geo, province, mapped, summary):
    bg, ink, muted, blue = '#f4f2ed', '#172e3c', '#596574', '#226b9b'
    recipients = {r['MUNID'] for r in mapped if r['award_confirmed']}
    colors = geo['MUNID'].map(lambda mid: blue if mid in recipients else '#d6dce0')
    fig = plt.figure(figsize=(10.8, 13.5), facecolor=bg)
    fig.text(.055, .957, 'ONTARIO  /  BUILDING FASTER FUND', fontsize=13, weight='bold', color=muted)
    fig.text(.05, .92, f"{summary['award_confirmed']} of {summary['with_targets']}", fontsize=77, weight='bold', color=ink, va='top')
    fig.text(.055, .805, 'targeted municipalities\nhad funding confirmed.', fontsize=30, weight='bold', color=ink, va='top', linespacing=1.1)
    fig.text(.055, .707, '2025 performance · October 5, 2026 update', fontsize=15, color=muted)
    full = fig.add_axes((.025, .33, .29, .32))
    south = fig.add_axes((.32, .275, .65, .40))
    for ax in (full, south):
        province.plot(ax=ax, color='#e8e7e1', edgecolor='#a9b6bd', linewidth=.65)
        geo.plot(ax=ax, color=colors, edgecolor=bg, linewidth=.20)
        ax.set_axis_off()
    bounds = gpd.GeoSeries([box(*SOUTH_BOUNDS)], crs=4326).to_crs(3347).total_bounds
    south.set_xlim(bounds[0], bounds[2]); south.set_ylim(bounds[1], bounds[3])
    full.set_title('Entire province', fontsize=12, color=muted)
    south.set_title('Southern and eastern Ontario', fontsize=12, color=muted)
    offsets = {'kitchener': (-160_000, 95_000), 'london': (-100_000, -110_000), 'welland': (70_000, -95_000)}
    for row in mapped:
        if row['MUNID'] not in recipients or row['municipality_key'] not in offsets:
            continue
        point = geo.loc[geo['MUNID'] == row['MUNID']].geometry.iloc[0].representative_point()
        dx, dy = offsets[row['municipality_key']]
        south.annotate(row['municipality'], (point.x, point.y), (point.x+dx, point.y+dy),
            fontsize=12, color=ink, bbox={'facecolor': bg, 'edgecolor': 'none', 'pad': 2},
            arrowprops={'arrowstyle': '-', 'color': muted, 'lw': .8})
    fig.legend(handles=[Patch(facecolor=blue, label='Confirmed funding'), Patch(facecolor='#d6dce0', label='Other municipalities')],
        loc='lower left', bbox_to_anchor=(.045, .245), frameon=False, fontsize=14, ncol=2, columnspacing=1.6)
    fig.add_artist(Line2D([.055, .945], [.224, .224], transform=fig.transFigure, color='#b8c1c6', lw=.8))
    fig.text(.055, .203, '80%', fontsize=30, weight='bold', color=ink, va='top')
    fig.text(.055, .157, 'Annual target threshold\nfor BFF funding', fontsize=14, color=muted, va='top', linespacing=1.3)
    fig.text(.55, .203, 'Up to C$1.2B', fontsize=28, weight='bold', color=ink, va='top')
    fig.text(.55, .157, 'Three-year infrastructure\nfund launched in 2023', fontsize=14, color=muted, va='top', linespacing=1.3)
    fig.text(.055, .087, 'Further reviews were pending at the time of the update.\nConfirmed allocations are distinct from cash received.', fontsize=12, color=muted, va='top', linespacing=1.35)
    fig.text(.055, .03, 'Source: Ontario Legislature, Oct. 5, 2026 · Boundaries: Ontario GeoHub', fontsize=10, color=muted)
    base = REPORTS / f"bff_{summary['year']}_linkedin"
    fig.savefig(base.with_suffix('.png'), dpi=200, facecolor=bg)
    fig.savefig(base.with_suffix('.svg'), facecolor=bg)
    plt.close(fig)
