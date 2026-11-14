#!/usr/bin/env python3
"""Plot every labeled development episode with surrounding context.

python src/plot_dev_episodes.py --data data --out outputs/dev_plots

One PNG per episode. Panels share one UTC time axis (no dual y-axes):
mean C/N0, min C/N0, satellites, cross-track error, fix state, correction link,
speed, regional S4, Kp. The labeled episode is shaded; other labeled episodes
that overlap in time are outlined. RFI report and advisory times are marked.
Uses development data only; no thresholds are drawn.
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from devdata import TRACTORS, context, load, overlapping  # noqa: E402

# Validated categorical slots 1-3 (dataviz reference palette, light mode).
COLOR = {"T1": "#2a78d6", "T2": "#eb6834", "T3": "#1baf7a"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
FIX_ORDER = ["NO_FIX", "AUTONOMOUS", "DGPS", "RTK_FLOAT", "RTK_FIXED"]


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.tick_params(colors=INK2, labelsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def held(df, col, a, b):
    """Piecewise-constant series over [a, b]: the value in force at a, changes inside, held to b."""
    df = df.sort_values("ts")
    before = df[df.ts <= a].tail(1).assign(ts=a)
    inside = df[(df.ts > a) & (df.ts < b)]
    s = pd.concat([before, inside])
    return pd.concat([s, s.tail(1).assign(ts=b)])[["ts", col]]


def plot_episode(d, ep, out):
    a, b = context(ep)
    short = (ep.end - ep.start) < pd.Timedelta(minutes=5)
    seg = d["tele"][(d["tele"].ts >= a) & (d["tele"].ts < b)].copy()
    if not short:  # 10 s means keep long windows legible without hiding minute-scale structure
        num = seg.set_index("ts").groupby("tractor_id")[
            ["mean_cn0_dbhz", "min_cn0_dbhz", "num_sats", "cross_track_error_m", "speed_mps"]
        ].resample("10s").mean()
        link = seg.set_index("ts").groupby("tractor_id")["base_link_ok"].resample("10s").mean()
        fix = seg.assign(f=seg.fix_state.map(FIX_ORDER.index)).set_index("ts").groupby("tractor_id")["f"].resample("10s").min()
        seg = num.join(link).join(fix.rename("fix_i")).reset_index()
    else:
        seg["fix_i"] = seg.fix_state.map(FIX_ORDER.index)
        seg["base_link_ok"] = seg.base_link_ok.astype(float)

    panels = [
        ("mean_cn0_dbhz", "mean C/N0\n(dB-Hz)"),
        ("min_cn0_dbhz", "min C/N0\n(dB-Hz)"),
        ("num_sats", "satellites"),
        ("cross_track_error_m", "cross-track\nerror (m)"),
        ("fix_i", "fix state\n(worst)"),
        ("base_link_ok", "RTK link ok\n(fraction)"),
        ("speed_mps", "speed (m/s)"),
    ]
    fig, axes = plt.subplots(len(panels) + 2, 1, figsize=(12, 13), sharex=True,
                             gridspec_kw={"hspace": 0.12})
    fig.patch.set_facecolor(SURFACE)
    others = overlapping(d["eps"], ep)

    for ax, (col, label) in zip(axes, panels):
        style(ax)
        for tr in TRACTORS:
            g = seg[seg.tractor_id == tr]
            affected = tr in ep.tractors
            ax.plot(g.ts, g[col], color=COLOR[tr], lw=1.6 if affected else 1.0,
                    alpha=1.0 if affected else 0.55, label=f"{tr}{' (labeled)' if affected else ''}",
                    drawstyle="steps-post" if col in ("fix_i", "num_sats") else "default")
        ax.set_ylabel(label, color=INK2, fontsize=8, rotation=0, ha="right", va="center")
    axes[4].set_yticks(range(len(FIX_ORDER)), FIX_ORDER, fontsize=7)
    axes[5].set_ylim(-0.05, 1.05)

    s4 = held(d["s4"], "s4", a, b)
    kp = held(d["kp"], "kp", a, b)
    ax = axes[-2]; style(ax)
    ax.step(s4.ts, s4.s4, where="post", color=INK, lw=1.4)
    ax.set_ylim(0, max(0.1, s4.s4.max() * 1.15))
    ax.set_ylabel("regional S4\n(15 min)", color=INK2, fontsize=8, rotation=0, ha="right", va="center")
    ax = axes[-1]; style(ax)
    ax.step(kp.ts, kp.kp, where="post", color=INK, lw=1.4)
    ax.set_ylim(0, 9.5)
    ax.set_ylabel("Kp (3 h)", color=INK2, fontsize=8, rotation=0, ha="right", va="center")

    # RFI report arrival times and advisories: vertical markers on every panel, labeled on the SDA panels.
    for _, r in d["rfi"][(d["rfi"].ts >= a) & (d["rfi"].ts < b)].iterrows():
        for x in axes:
            x.axvline(r.ts, color=INK2, ls=":", lw=1)
        axes[-2].annotate(f"{r.id} ({r.confidence})", (r.ts, 0.95), xycoords=("data", "axes fraction"),
                          fontsize=7, color=INK2, rotation=90, va="top", ha="right")
    for _, v in d["adv"][(d["adv"].ts >= a) & (d["adv"].ts < b)].iterrows():
        for x in axes:
            x.axvline(v.ts, color=INK2, ls="--", lw=0.8)
        axes[-1].annotate(f"{v.id} {v.type}", (v.ts, 1), xycoords=("data", "axes fraction"),
                          fontsize=7, color=INK2, rotation=90, va="top", ha="right")

    for x in axes:
        x.axvspan(ep.start, ep.end, color="#2a78d6", alpha=0.08, lw=0)
        for _, o in others.iterrows():
            x.axvspan(max(o.start, a), min(o.end, b), fill=False, hatch="///", edgecolor=GRID, lw=0)
    title = (f"{ep.id}  {ep['class']}  tractors {','.join(ep.tractors)}  "
             f"{ep.start:%Y-%m-%d %H:%M:%S}Z – {ep.end:%H:%M:%S}Z")
    if len(others):
        title += "\noverlaps (hatched): " + "; ".join(
            f"{o.id} {o['class']} {','.join(o.tractors)}" for _, o in others.iterrows())
    fig.suptitle(title, x=0.01, y=0.935, ha="left", fontsize=11, color=INK)
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.0), fontsize=8, frameon=False, ncol=3)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S" if short else "%H:%M", tz="UTC"))
    axes[-1].set_xlabel("UTC", color=INK2, fontsize=8)
    axes[-1].set_xlim(a, b)
    fig.savefig(out / f"{ep.id}_{ep['class']}.png", dpi=110, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default="data")
    p.add_argument("--out", default="outputs/dev_plots")
    args = p.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    d = load(args.data)
    for _, ep in d["eps"].sort_values("start").iterrows():
        plot_episode(d, ep, out)
        print("wrote", out / f"{ep.id}_{ep['class']}.png")


if __name__ == "__main__":
    main()
