"""FIELD SIGNAL — Straight Rows fleet guidance investigation workspace (Streamlit dashboard).

Launch from the repository root (Windows CMD):
    .venv\\Scripts\\python.exe -m streamlit run src\\dashboard.py

Read-only view of the existing pipeline. Detections, evidence, actions and the working flag
all come from `straightrows` (io.load, pipeline.detect, export.to_submission, features +
candidates; measurement tables use evidence._stats, the function behind the exported evidence).
The dashboard only selects intervals, chooses which channels to draw, aggregates raw telemetry
for display, and looks up exact 1 Hz samples for the replay cursor. Nothing here changes detection.
"""
import html
import math
import subprocess
import sys
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from straightrows.candidates import flag  # noqa: E402
from straightrows.config import DEV, EVAL, Config  # noqa: E402
from straightrows.evidence import PRE, _stats  # noqa: E402
from straightrows.export import CONFIDENCE, to_submission  # noqa: E402
from straightrows.features import minute_features  # noqa: E402
from straightrows.io import load  # noqa: E402
from straightrows.pipeline import detect  # noqa: E402

# ---------------------------------------------------------------- palette (project palette, not Bluestaq branding)
BG, PANEL, RAISED = "#091321", "#122238", "#1A304B"
BLUE, CYAN, TEXT, TEXT2 = "#4C8DFF", "#35D0DB", "#EDF4FF", "#A9BCD3"
AMBER, CORAL = "#F5B85A", "#FF7B86"
GRID, RULE = "#1E3452", "#2A4566"

TRACTORS = ["T1", "T2", "T3"]
# Tractor identity: blue / amber / cyan, used ONLY for tractors (lines, markers, readout headers).
TRACTOR_COLORS = {"T1": BLUE, "T2": AMBER, "T3": CYAN}
TRACTOR_SHAPES = {"T1": "circle", "T2": "square", "T3": "triangle-up"}
WINDOWS = {"Evaluation (unlabeled)": EVAL, "Development (labeled)": DEV}
REQUIRED = ["farm/tractor_telemetry.csv.gz", "sda/sgi_indices.json", "sda/scintillation_series.json",
            "sda/constellation_advisories.json", "sda/rfi_reports.json"]
AGGREGATIONS = {"1 min": "1min", "10 s": "10s", "1 s (raw, intervals up to 30 min)": "1s"}
AFTER = pd.Timedelta(minutes=30)   # display-only "after" window; mirrors evidence.PRE (30 min before onset)

# Cause identity: a hue family disjoint from the tractor colours AND a short text code on every bar.
CAUSES = {
    "SPACE_WEATHER": dict(code="SW", color="#A98BFF", short="Space weather",
                          headline="Regional signal degradation, suspected space weather"),
    "JAMMING": dict(code="JAM", color=CORAL, short="Jamming",
                    headline="Signal loss, suspected radio-frequency interference (jamming)"),
    "SPOOFING": dict(code="SPF", color="#E37BD6", short="Spoofing",
                     headline="Guidance error without signal collapse, suspected spoofing"),
    "EQUIPMENT_FAULT": dict(code="EF", color="#9FB3C8", short="Equipment fault",
                            headline="Machine-specific fault, suspected equipment problem"),
    "MULTIPATH": dict(code="MP", color="#7BD88F", short="Multipath", headline="Multipath (not detected)"),
}
ACTION_TEXT = {
    "HALT_OR_DEGRADED_MODE": "Halt, or continue only in a degraded guidance mode, until conditions improve.",
    "HALT_AND_REPORT": "Halt and report suspected interference.",
    "HALT_CROSSCHECK_AND_REPORT": "Halt, cross-check position with an independent source, and report.",
    "SERVICE_MACHINE_OTHERS_CONTINUE": "Service the affected machine; the other machines continue.",
    "CONTINUE_FALSE_ALARM": "Continue; treat as a false alarm.",
}

# Display-only channel registry and cause → primary channels mapping (does not affect detection).
CHANNELS = {
    "xte": ("Cross-track error (m, signed)", True),
    "cn0": ("Mean C/N0 (dB-Hz)", False),
    "min_cn0": ("Min C/N0 (dB-Hz)", False),
    "sats": ("Satellites (median)", False),
    "link": ("RTK correction link up (%)", True),
    "fixed": ("RTK_FIXED (% of bin)", True),
    "s4": ("Regional S4 (15-min series)", True),
    "kp": ("Kp (3-hour index)", True),
}
PRIMARY = {
    # EQUIPMENT_FAULT: chosen per incident by ef_channels() from the sub-rule the evidence names (link loss
    # and/or antenna dropouts). Cross-track error is not part of the rule and can be inflated by a concurrent
    # spoof (TRN-09/TRN-06), so it is never primary. This entry is the documented fallback.
    "EQUIPMENT_FAULT": ["min_cn0", "link", "fixed"],
    "JAMMING": ["cn0", "sats", "xte"],
    "SPACE_WEATHER": ["cn0", "s4", "fixed"],
    "SPOOFING": ["xte", "cn0", "sats"],
    None: ["xte", "cn0", "min_cn0"],
}
ALL_CHANNELS = ["xte", "cn0", "min_cn0", "sats", "link", "fixed", "s4", "kp"]
UNCERTAINTY = {   # one-line main uncertainty per cause; full rule text lives in the expander
    "SPACE_WEATHER": "The S4 cutoff was chosen by hand on development data, and jamming during a storm is "
                     "currently missed.",
    "JAMMING": "RFI reports are not used by the rule, and it does not test whether the loss is confined to "
               "one machine.",
    "SPOOFING": "The rule uses only the guidance-monitor error; reported position is not checked, and "
                "spoofing during a storm is currently missed.",
    "EQUIPMENT_FAULT": "Short same-cause gaps are bridged, so the interval can include normal minutes.",
}


def ef_channels(sa, su, cfg):
    """Equipment fault: show the signal(s) that the evidence text names (same test as evidence.py)."""
    link = sa["link"] < 100 * cfg.link_low_frac or bool(su and sa["link"] < su["link"])
    dropout = sa["mincn0"] < cfg.dropout_dbhz
    if link and dropout:
        return ["min_cn0", "link", "fixed"]
    if link:
        return ["link", "fixed", "min_cn0"]
    return ["min_cn0", "sats", "cn0"]   # antenna dropouts: min C/N0 and satellite dips; mean C/N0 for context


st.set_page_config(page_title="Field Signal · Straight Rows", layout="wide", initial_sidebar_state="collapsed")
alt.data_transformers.disable_max_rows()  # intervals are bounded below; rows stay in the low thousands

# Panels are keyed containers (Streamlit adds the class st-key-<key>); no generated-ID selectors.
st.markdown(f"""<style>
[data-testid="stMainBlockContainer"] {{ padding: 1.1rem 1.6rem 2.5rem 1.6rem; max-width: 1900px; }}
[data-testid="stHeader"] {{ display: none; }}
.fs-ro td:first-child {{ white-space: nowrap; }}
div[class*="st-key-panel-"] {{ background: {PANEL}; border: 1px solid {RULE}; border-radius: 10px;
  padding: 12px 16px 14px 16px; }}
div[class*="st-key-panel-"] [data-testid="stExpander"] details {{ background: {BG}22; border-color: {RULE}; }}
div.st-key-evcharts {{ gap: 0.15rem; }}
.fs-title {{ font-size: 1.35rem; font-weight: 700; letter-spacing: 0.16em; color: {TEXT}; line-height: 1.15; }}
.fs-sub {{ font-size: 0.9rem; color: {TEXT2}; margin-top: 2px; }}
.fs-chips {{ margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap; }}
.fs-chip {{ font-size: 0.78rem; padding: 2px 8px; border: 1px solid {RULE}; border-radius: 6px; color: {TEXT2};
  background: {RAISED}; }}
.fs-chip.warn {{ color: {AMBER}; border-color: #5a4625; }}
.fs-h {{ font-size: 0.82rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: {TEXT2};
  margin: 0 0 6px 0; }}
.fs-h span {{ text-transform: none; letter-spacing: 0; font-weight: 400; margin-left: 8px; }}
.fs-mono, .fs-summary code, .fs-ro td.v {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
.fs-summary {{ display: flex; flex-wrap: wrap; gap: 10px 28px; align-items: flex-start; }}
.fs-summary .main {{ flex: 2 1 360px; }}
.fs-summary .kv {{ flex: 1 1 150px; font-size: 0.92rem; color: {TEXT}; }}
.fs-summary .kv > div:first-child {{ font-size: 0.78rem; color: {TEXT2}; margin-bottom: 2px; }}
.fs-summary code {{ background: none; color: {TEXT}; padding: 0; font-size: 0.9rem; }}
.fs-tag {{ font-size: 0.75rem; color: {AMBER}; border: 1px solid #5a4625; border-radius: 6px; padding: 1px 7px; }}
.fs-headline {{ font-size: 1.12rem; font-weight: 600; color: {TEXT}; margin-top: 5px; }}
.fs-code {{ display: inline-block; font-family: ui-monospace, Consolas, monospace; font-size: 0.8rem; font-weight: 700;
  color: {BG}; padding: 0 6px; border-radius: 4px; margin-right: 6px; }}
.fs-tr {{ display: inline-block; font-family: ui-monospace, Consolas, monospace; font-weight: 700; padding: 0 6px 0 5px;
  border-left: 4px solid; margin-right: 6px; background: {RAISED}; border-radius: 3px; }}
.fs-action {{ font-size: 1.0rem; font-weight: 600; color: {TEXT}; }}
.fs-obs {{ margin: 0; padding-left: 1.1rem; font-size: 0.9rem; }}
.fs-obs li {{ margin-bottom: 4px; }}
.fs-note {{ font-size: 0.82rem; color: {TEXT2}; }}
.fs-legend {{ font-size: 0.82rem; color: {TEXT2}; display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }}
.fs-legend i {{ display: inline-block; width: 18px; height: 0; border-top: 2px solid; vertical-align: middle;
  margin-right: 5px; }}
.fs-ro {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; }}
.fs-ro th, .fs-ro td {{ padding: 3px 6px; border-bottom: 1px solid {GRID}; text-align: right; }}
.fs-ro th:first-child, .fs-ro td:first-child {{ text-align: left; color: {TEXT2}; font-weight: 400; }}
.fs-ro th {{ font-family: ui-monospace, Consolas, monospace; }}
.fs-ro td.focus, .fs-ro th.focus {{ background: {RAISED}; }}
.fs-ro td.na {{ color: {AMBER}; }}
</style>""", unsafe_allow_html=True)


# ---------------------------------------------------------------- data access (cached)
def data_signature(data_dir):
    """(missing files, signature). The signature changes when any input file changes."""
    p = Path(data_dir)
    missing = [f for f in REQUIRED if not (p / f).is_file()]
    files = REQUIRED + ["labels/train_episodes.json"]
    sig = tuple((f, (p / f).stat().st_size, (p / f).stat().st_mtime_ns) for f in files if (p / f).is_file())
    return missing, sig


@st.cache_resource(show_spinner="Loading challenge data…", max_entries=2)
def load_data(data_dir, sig):
    # Shared, read-only. Keyed by path + file signature (sizes, mtimes) so changed inputs are reloaded.
    return load(data_dir)


@st.cache_resource(max_entries=2)
def sample_index(data_dir, sig):
    """Raw 1 Hz telemetry indexed by (tractor, timestamp) for exact-second replay lookups."""
    return load_data(data_dir, sig)["tele"].set_index(["tractor_id", "ts"]).sort_index()


@st.cache_data(show_spinner="Running the pipeline…", max_entries=8)
def pipeline_results(data_dir, sig, window_name, cfg_items):
    """Detections with the exact evidence/action/confidence the submission export produces."""
    d = load_data(data_dir, sig)
    cfg = Config(**dict(cfg_items))
    dets = detect(d, cfg, WINDOWS[window_name])
    sub = to_submission(dets, d, cfg, "dashboard", "https://github.com/dashboard/view")
    return sub["detections"]


@st.cache_data(show_spinner="Computing working state…", max_entries=8)
def pipeline_flags(data_dir, sig, window_name, cfg_items):
    """Per tractor-minute pipeline features + flags (includes the existing `working` flag)."""
    d = load_data(data_dir, sig)
    cfg = Config(**dict(cfg_items))
    return flag(minute_features(d, WINDOWS[window_name]), cfg)


@st.cache_data(max_entries=48)
def display_bins(data_dir, sig, a, b, rule):
    """Aggregate raw 1 Hz telemetry into display bins (same aggregations as features.py for shared channels)."""
    tele = load_data(data_dir, sig)["tele"]
    seg = tele[(tele.ts >= a) & (tele.ts < b)]
    if seg.empty:
        return pd.DataFrame()
    g = seg.set_index("ts").groupby("tractor_id")
    out = pd.concat({
        "xte": g["cross_track_error_m"].resample(rule).mean(),
        "cn0": g["mean_cn0_dbhz"].resample(rule).mean(),
        "min_cn0": g["min_cn0_dbhz"].resample(rule).min(),
        "sats": g["num_sats"].resample(rule).median(),
        "link": g["base_link_ok"].resample(rule).mean() * 100,
        "fixed": g["fix_state"].resample(rule).apply(lambda s: 100 * (s == "RTK_FIXED").mean() if len(s) else float("nan")),
    }, axis=1).reset_index()
    out = out.dropna(subset=["cn0"]).sort_values(["tractor_id", "ts"])
    # Break lines at gaps: a new segment whenever consecutive bins are more than one bin apart.
    step = pd.Timedelta(rule)
    gap = out.groupby("tractor_id").ts.diff().fillna(step) > step
    out["seg"] = out.tractor_id + "-" + gap.groupby(out.tractor_id).cumsum().astype(str)
    out["time_utc"] = out.ts.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return out


@st.cache_data(max_entries=24)
def position_bins(data_dir, sig, a, b):
    """Reported lat/lon as 10 s means, converted to local metres about the interval's mean position."""
    tele = load_data(data_dir, sig)["tele"]
    seg = tele[(tele.ts >= a) & (tele.ts < b)]
    if seg.empty:
        return pd.DataFrame(), None
    lat0, lon0 = seg.lat.mean(), seg.lon.mean()
    p = seg.set_index("ts").groupby("tractor_id")[["lat", "lon"]].resample("10s").mean().dropna().reset_index()
    p = p.sort_values(["tractor_id", "ts"])
    gap = p.groupby("tractor_id").ts.diff().fillna(pd.Timedelta("10s")) > pd.Timedelta("10s")
    p["seg"] = p.tractor_id + "-" + gap.groupby(p.tractor_id).cumsum().astype(str)
    p["east_m"], p["north_m"] = to_local(p.lat, p.lon, lat0, lon0)
    p["time_utc"] = p.ts.dt.strftime("%H:%M:%S UTC")
    return p, (lat0, lon0)


def to_local(lat, lon, lat0, lon0):
    """Flat-earth metres east/north of (lat0, lon0): 1° lat = 111,320 m; 1° lon = 111,320 m × cos(lat0)."""
    return (lon - lon0) * 111320 * math.cos(math.radians(lat0)), (lat - lat0) * 111320


def held(df, col, a, b):
    """Piecewise-constant SDA series over [a, b]: value in force at a, changes inside, held to b."""
    df = df.sort_values("ts")
    before = df[df.ts <= a].tail(1).assign(ts=a)
    s = pd.concat([before, df[(df.ts > a) & (df.ts < b)]])
    return pd.concat([s, s.tail(1).assign(ts=b)])[["ts", col]] if len(s) else s


def in_force(df, col, t):
    """Latest published value at or before t (the pipeline's backward as-of rule), or None."""
    prior = df[df.ts <= t]
    if prior.empty:
        return None
    r = prior.sort_values("ts").iloc[-1]
    return r[col], r.ts


def fmt(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M UTC")


def hm(ts):
    return pd.Timestamp(ts).strftime("%H:%M")


def age(dt):
    s = int(dt.total_seconds())
    return f"{s // 3600}h {s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m {s % 60:02d}s"


def git_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def det_label(i, x):
    c = CAUSES[x["class"]]
    return (f"#{i + 1}  {c['code']} {c['short']} · {' '.join(x['tractors'])} · "
            f"{pd.Timestamp(x['start']):%m-%d %H:%M}–{pd.Timestamp(x['end']):%H:%M} UTC")


def code_chip(cause):
    c = CAUSES[cause]
    return f'<span class="fs-code" style="background:{c["color"]}">{c["code"]}</span>'


def tractor_chip(t):
    return f'<span class="fs-tr" style="border-left-color:{TRACTOR_COLORS[t]}">{t}</span>'


def heading(text, note=""):
    st.markdown(f'<div class="fs-h">{text}{f"<span>{note}</span>" if note else ""}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------- charts
def styled(ch):
    return (ch.configure(background="transparent", font="sans-serif")
            .configure_view(stroke=None)
            .configure_axis(labelColor=TEXT2, titleColor=TEXT2, gridColor=GRID, domainColor=RULE, tickColor=RULE,
                            labelFontSize=11, titleFontWeight="normal")
            .configure_title(color=TEXT, fontSize=12, fontWeight="normal", anchor="start", offset=4)
            .configure_legend(labelColor=TEXT, titleColor=TEXT2))


def time_format(a, b):
    return "%H:%M" if (b - a) <= pd.Timedelta(hours=26) else "%m-%d %H:%M"


def x_enc(a, b, labels=True, field="ts"):
    return alt.X(f"{field}:T", title=None, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
                 axis=alt.Axis(format=time_format(a, b), labelAngle=0, labels=labels, grid=False,
                               labelFont="monospace", tickCount=8))


Y_AXIS = dict(title=None, labelFont="monospace", minExtent=44, maxExtent=44, tickCount=4, format=".4~r")


def overlays(a, b, s0, e0, cursor):
    """Selected-incident band + boundary rules + replay cursor, on the shared time axis."""
    layers = []
    if s0 is not None:
        band = pd.DataFrame({"ts": [max(s0, a)], "end": [min(e0, b)]})
        layers.append(alt.Chart(band).mark_rect(color=BLUE, opacity=0.13).encode(x=x_enc(a, b), x2="end:T"))
        edges = pd.DataFrame({"ts": [t for t in (s0, e0) if a <= t <= b]})
        if len(edges):
            layers.append(alt.Chart(edges).mark_rule(color=BLUE, strokeDash=[4, 3], strokeWidth=1).encode(
                x=x_enc(a, b)))
    if cursor is not None:
        layers.append(alt.Chart(pd.DataFrame({"ts": [cursor]})).mark_rule(color=TEXT, strokeWidth=1.3).encode(
            x=x_enc(a, b)))
    return layers


def line_chart(df, field, a, b, ov, affected, focus, height, labels):
    title, zero = CHANNELS[field]
    d2 = df.assign(role=df.tractor_id.map(lambda t: "affected" if (not affected or t in affected) else "other"))
    focused = alt.datum.tractor_id == focus
    line = alt.Chart(d2).mark_line(interpolate="linear").encode(
        x=x_enc(a, b, labels=labels),
        y=alt.Y(f"{field}:Q", scale=alt.Scale(zero=zero), axis=alt.Axis(**Y_AXIS)),
        color=alt.Color("tractor_id:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_COLORS.values())),
                        legend=None),
        strokeDash=alt.StrokeDash("role:N", scale=alt.Scale(domain=["affected", "other"], range=[[1, 0], [5, 3]]),
                                  legend=None),
        opacity=alt.value(1) if focus is None else alt.condition(focused, alt.value(1), alt.value(0.22)),
        strokeWidth=alt.value(1.6) if focus is None else alt.condition(focused, alt.value(2.4), alt.value(1.2)),
        detail="seg:N",
        tooltip=[alt.Tooltip("tractor_id:N", title="tractor"), alt.Tooltip("time_utc:N", title="bin start"),
                 alt.Tooltip(f"{field}:Q", title=title, format=".3f")])
    return styled(alt.layer(*ov[:2], line, *ov[2:]).properties(height=height, width="container", title=title))


def step_chart(d, key, a, b, ov, height, labels):
    df = held(d[key], key, a, b)
    if df.empty:
        return None
    title, zero = CHANNELS[key]
    df = df.assign(time_utc=df.ts.dt.strftime("%Y-%m-%d %H:%M UTC"))
    line = alt.Chart(df).mark_line(interpolate="step-after", color=TEXT, strokeWidth=1.5).encode(
        x=x_enc(a, b, labels=labels), y=alt.Y(f"{key}:Q", scale=alt.Scale(zero=zero), axis=alt.Axis(**Y_AXIS)),
        tooltip=[alt.Tooltip("time_utc:N", title="value in force from"), alt.Tooltip(f"{key}:Q", format=".3f")])
    return styled(alt.layer(*ov[:2], line, *ov[2:]).properties(height=height, width="container",
                                                              title=title + " · regional, not per tractor"))


def chart_for(key, bins, d, a, b, ov, affected, focus, height, labels):
    if key in ("s4", "kp"):
        return step_chart(d, key, a, b, ov, height, labels)
    return line_chart(bins, key, a, b, ov, affected, focus, height, labels)


def context_chart(dets, sel_idx, wf, a, b, cursor):
    """Compact strip: detections overlapping the interval (selected vs adjacent) + pipeline working state."""
    rows = [{"lane": "Det.", "cause": x["class"], "code": f"#{i + 1} {CAUSES[x['class']]['code']} "
             + " ".join(x["tractors"]), "when": f"{fmt(x['start'])} → {fmt(x['end'])}",
             "ts": max(pd.Timestamp(x["start"]), a), "end": min(pd.Timestamp(x["end"]), b),
             "state": "selected" if i == sel_idx else "adjacent"}
            for i, x in enumerate(dets) if pd.Timestamp(x["start"]) < b and pd.Timestamp(x["end"]) > a]
    layers = []
    lanes = ["Det."] + [f"{t} working" for t in TRACTORS]
    y = alt.Y("lane:N", sort=lanes, scale=alt.Scale(domain=lanes), title=None,
              axis=alt.Axis(labelFont="monospace", ticks=False, domain=False, minExtent=44, maxExtent=44,
                            labelExpr="replace(datum.label, ' working', '')", labelLimit=44))
    if rows:
        items = pd.DataFrame(rows)
        base = alt.Chart(items).encode(x=x_enc(a, b, labels=False), x2="end:T", y=y)
        layers.append(base.mark_bar(height=13, cornerRadius=2).encode(
            color=alt.Color("cause:N", scale=alt.Scale(domain=list(CAUSES), range=[c["color"] for c in CAUSES.values()]),
                            legend=None),
            opacity=alt.Opacity("state:N", scale=alt.Scale(domain=["selected", "adjacent"], range=[1.0, 0.4]),
                                legend=None),
            stroke=alt.condition(alt.datum.state == "selected", alt.value(TEXT), alt.value(None)),
            tooltip=[alt.Tooltip("code:N", title="detection"), "when:N", "state:N"]))
        layers.append(base.mark_text(align="left", dx=4, fontSize=10, font="monospace", color=BG, fontWeight="bold")
                      .encode(x="ts:T", text="code:N"))
    if len(wf):
        w = wf.assign(lane=wf.tractor_id + " working", end=wf.ts + pd.Timedelta(minutes=1),
                      state=wf.working.map({True: "working", False: "parked"}),
                      time_utc=wf.ts.dt.strftime("%Y-%m-%d %H:%M UTC"))
        layers.append(alt.Chart(w).mark_bar().encode(
            x=x_enc(a, b, labels=False), x2="end:T", y=y,
            # Fixed values, not a colour scale: a scale here would merge with the cause colours of the top lane.
            color=alt.condition(alt.datum.state == "working", alt.value("#7F95B0"), alt.value("#2E4868")),
            size=alt.Size("state:N", scale=alt.Scale(domain=["working", "parked"], range=[9, 3]), legend=None),
            tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="minute"), "state:N",
                     alt.Tooltip("moving:Q", title="mean speed (m/s)", format=".2f")]))
    if cursor is not None:
        layers.append(alt.Chart(pd.DataFrame({"ts": [cursor]})).mark_rule(color=TEXT, strokeWidth=1.3)
                      .encode(x=x_enc(a, b, labels=False)))
    return styled(alt.layer(*layers).properties(height=78, width="container")) if layers else None


def fleet_ribbon(dets, sel_idx, a, b):
    """T1/T2/T3 lanes across the whole window; concurrent causes on one tractor sit in separate sub-rows."""
    rows = []
    for i, x in enumerate(dets):
        c = CAUSES[x["class"]]
        dur = (pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).total_seconds() / 60
        for t in x["tractors"]:
            rows.append({"det_id": i, "tractor": t, "cause": x["class"], "start": pd.Timestamp(x["start"]),
                         "end": pd.Timestamp(x["end"]), "text": c["code"] if dur >= 80 else "",
                         "label": det_label(i, x), "sel": "selected" if i == sel_idx else "other"})
    df = pd.DataFrame(rows)
    pick = alt.selection_point(name="pick", fields=["det_id"], on="click", clear=False)
    x = alt.X("start:T", title=None, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
              axis=alt.Axis(format="%m-%d %H:%M", labelAngle=0, labelFont="monospace", gridColor=GRID, tickCount=12))
    y = alt.Y("tractor:N", title=None, sort=TRACTORS, scale=alt.Scale(domain=TRACTORS),
              axis=alt.Axis(labelFont="monospace", labelFontWeight="bold", labelColor=TEXT, ticks=False, domain=False,
                            labelFontSize=12))
    present = [c for c in CAUSES if c in set(df.cause)]   # sub-rows only for causes in this window
    layers = []
    if sel_idx is not None:
        s = dets[sel_idx]
        layers.append(alt.Chart(pd.DataFrame({"start": [pd.Timestamp(s["start"])], "end": [pd.Timestamp(s["end"])]}))
                      .mark_rect(color=BLUE, opacity=0.18).encode(x=x, x2="end:T"))
    base = alt.Chart(df).encode(x=x, x2="end:T", y=y,
                                yOffset=alt.YOffset("cause:N", sort=present, scale=alt.Scale(domain=present)))
    layers.append(base.mark_bar(cornerRadius=2, cursor="pointer").encode(
        color=alt.Color("cause:N", title=None, scale=alt.Scale(domain=present, range=[CAUSES[c]["color"] for c in present]),
                        legend=alt.Legend(orient="top", direction="horizontal", labelFont="monospace", symbolType="square",
                                          labelExpr=" : ".join(f"datum.label == '{k}' ? '{v['code']} {v['short'].lower()}'"
                                                               for k, v in CAUSES.items()) + " : datum.label")),
        opacity=alt.condition(alt.datum.sel == "selected", alt.value(1.0), alt.value(0.55)),
        stroke=alt.condition(alt.datum.sel == "selected", alt.value(TEXT), alt.value(None)),
        strokeWidth=alt.condition(alt.datum.sel == "selected", alt.value(2), alt.value(0)),
        tooltip=[alt.Tooltip("label:N", title="detection"), alt.Tooltip("tractor:N")],
    ).add_params(pick))
    layers.append(base.mark_text(align="left", dx=3, fontSize=9, font="monospace", color=BG, fontWeight="bold")
                  .encode(x="start:T", text="text:N"))
    return styled(alt.layer(*layers).properties(height=150, width="container"))


def position_chart(p, origin, tele_idx, a, b, cursor, focus):
    """Reported GNSS position: equal-scaled local metres, gap-aware trails, selected-time markers."""
    span = max(p.east_m.max() - p.east_m.min(), p.north_m.max() - p.north_m.min(), 10) * 1.08 / 2
    ce, cn = (p.east_m.max() + p.east_m.min()) / 2, (p.north_m.max() + p.north_m.min()) / 2
    xs = alt.Scale(domain=[ce - span, ce + span], nice=False)
    ys = alt.Scale(domain=[cn - span, cn + span], nice=False)
    col = alt.Color("tractor_id:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_COLORS.values())), legend=None)
    enc = dict(x=alt.X("east_m:Q", scale=xs, title="East (m)"), y=alt.Y("north_m:Q", scale=ys, title="North (m)"),
               color=col, detail="seg:N", order="ts:T")
    fo = (lambda hi, lo: alt.value(hi)) if focus is None else (
        lambda hi, lo: alt.condition(alt.datum.tractor_id == focus, alt.value(hi), alt.value(lo)))
    layers = [alt.Chart(p).mark_line(strokeWidth=1).encode(**enc, opacity=fo(0.25, 0.08))]
    past = p[p.ts <= cursor]
    if len(past):
        layers.append(alt.Chart(past).mark_line(strokeWidth=1.8).encode(**enc, opacity=fo(0.95, 0.2)))
    marks = []
    for t in TRACTORS:
        try:
            r = tele_idx.loc[(t, cursor)]
        except KeyError:
            continue
        e, n = to_local(r.lat, r.lon, *origin)
        marks.append({"tractor_id": t, "east_m": e, "north_m": n, "shape": TRACTOR_SHAPES[t],
                      "time_utc": f"{cursor:%H:%M:%S} UTC (1 Hz sample)"})
    if marks:
        m = pd.DataFrame(marks)
        layers.append(alt.Chart(m).mark_point(size=110, filled=True, stroke=BG, strokeWidth=1.2).encode(
            x=alt.X("east_m:Q", scale=xs), y=alt.Y("north_m:Q", scale=ys), color=col,
            shape=alt.Shape("tractor_id:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_SHAPES.values())),
                            legend=None),
            opacity=fo(1, 0.35),
            tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="time"),
                     alt.Tooltip("east_m:Q", format=".1f"), alt.Tooltip("north_m:Q", format=".1f")]))
        layers.append(alt.Chart(m).mark_text(dx=9, dy=-9, font="monospace", fontWeight="bold", fontSize=11).encode(
            x=alt.X("east_m:Q", scale=xs), y=alt.Y("north_m:Q", scale=ys), text="tractor_id:N", color=col))
    # Plot area is square and both axes span the same distance, so 1 m east = 1 m north on screen.
    return styled(alt.layer(*layers).properties(width=330, height=330)), len(marks)


# ---------------------------------------------------------------- readout + tables (HTML)
def readout_html(idx, flags, dets, cursor, focus, d):
    def cell(v, cls="v"):
        return f'<td class="{cls}{" focus" if focus == cur_t else ""}">{v}</td>'
    head = "".join(f'<th class="{"focus" if focus == t else ""}" style="color:{TRACTOR_COLORS[t]}">{t}</th>'
                   for t in TRACTORS)
    samples = {}
    for t in TRACTORS:
        try:
            samples[t] = idx.loc[(t, cursor)]
        except KeyError:
            samples[t] = None
    minute = cursor.floor("min")
    fl = flags[flags.ts == minute].set_index("tractor_id")
    fields = [
        ("Sample", lambda r, t: f"{cursor:%H:%M:%S}"),
        ("Speed m/s", lambda r, t: f"{r.speed_mps:.1f}"),
        (f"Working {minute:%H:%M}", lambda r, t: ("yes" if fl.loc[t, "working"] else "no")
         if t in fl.index else '<span title="minute outside the pipeline window">n/a</span>'),
        ("XTE m", lambda r, t: f"{r.cross_track_error_m:+.3f}"),
        ("C/N0 mean dB-Hz", lambda r, t: f"{r.mean_cn0_dbhz:.1f}"),
        ("C/N0 min dB-Hz", lambda r, t: f"{r.min_cn0_dbhz:.1f}"),
        ("Satellites", lambda r, t: f"{r.num_sats:d}"),
        ("Fix state", lambda r, t: html.escape(str(r.fix_state)).replace("RTK_", "")),
        ("RTK link", lambda r, t: "up" if r.base_link_ok else "down"),
    ]
    body = ""
    for name, fn in fields:
        body += f"<tr><td>{name}</td>"
        for cur_t in TRACTORS:
            r = samples[cur_t]
            body += cell("no sample", "v na") if r is None else cell(fn(r, cur_t))
        body += "</tr>"
    body += "<tr><td>In detection</td>"
    for cur_t in TRACTORS:
        hits = [f"#{i + 1} {CAUSES[x['class']]['code']}" for i, x in enumerate(dets) if cur_t in x["tractors"]
                and pd.Timestamp(x["start"]) <= cursor < pd.Timestamp(x["end"])]
        body += cell(" ".join(hits) or "—")
    body += "</tr>"
    sda = []
    for key, label, src in (("s4", "S4", d["s4"]), ("kp", "Kp", d["kp"])):
        v = in_force(src, key, cursor)
        sda.append(f"{label} <span class='fs-mono'>{v[0]:g}</span> (published {v[1]:%H:%M}, {age(cursor - v[1])} "
                   "earlier)" if v else f"{label} unavailable")
    return (f'<table class="fs-ro"><tr><th></th>{head}</tr>{body}</table>'
            f'<div class="fs-note" style="margin-top:6px">{" · ".join(sda)} — regional values in force at the cursor.'
            "</div>")


def stats_table_html(cols, rows):
    head = "".join(f"<th>{html.escape(n)}</th>" for n in cols)
    body = ""
    for label, key, nd in rows:
        body += f"<tr><td>{label}</td>"
        for s, n in cols.values():
            if s is None:
                body += '<td class="v na">unavailable</td>'
            elif key == "n":
                body += f'<td class="v">{n:,}</td>'
            else:
                body += f'<td class="v">{s[key]:.{nd}f}</td>'
        body += "</tr>"
    return f'<table class="fs-ro"><tr><th></th>{head}</tr>{body}</table>'


def stats_n(seg):
    return _stats(seg), len(seg)


def observations(channels, sa, sp, su, aff, un, ev):
    """Up to three measured observations for the cause's primary channels (same statistics as the evidence)."""
    who = " ".join(aff)

    def ctx(k, nd, unit=""):
        parts = []
        if sp:
            parts.append(f"prior 30 min {sp[k]:.{nd}f}{unit}")
        if su:
            parts.append(f"{' '.join(un)} {su[k]:.{nd}f}{unit}")
        return f" <span class='fs-note'>({'; '.join(parts)})</span>" if parts else ""

    out = []
    for k in channels:
        if k == "cn0":
            out.append(f"Mean C/N0 <b class='fs-mono'>{sa['cn0']:.1f} dB-Hz</b> on {who}" + ctx("cn0", 1))
        elif k == "min_cn0":
            out.append(f"Min C/N0 <b class='fs-mono'>{sa['mincn0']:.1f} dB-Hz</b> on {who}" + ctx("mincn0", 1))
        elif k == "sats":
            out.append(f"Median satellites <b class='fs-mono'>{sa['sats']:.0f}</b> on {who}" + ctx("sats", 0))
        elif k == "xte":
            out.append(f"Cross-track error median <b class='fs-mono'>{sa['xte_med']:.2f} m</b>, max "
                       f"<b class='fs-mono'>{sa['xte_max']:.2f} m</b>" + ctx("xte_med", 2, " m"))
        elif k == "link":
            out.append(f"RTK link up <b class='fs-mono'>{sa['link']:.0f}%</b> on {who}" + ctx("link", 0, "%"))
        elif k == "fixed":
            out.append(f"RTK_FIXED <b class='fs-mono'>{sa['fixed']:.0f}%</b> of samples on {who}" + ctx("fixed", 0, "%"))
        elif k == "s4":
            line = next((e for e in ev if e.startswith("Regional S4")), None)
            if line:
                out.append(html.escape(line))
    return out[:3]


# ---------------------------------------------------------------- selection callbacks
def on_ribbon(rib_key, sel_key, mode_key):
    """Ribbon click → the single selection state (the selector widget shares the same key)."""
    pts = ((st.session_state.get(rib_key) or {}).get("selection") or {}).get("pick") or []
    if pts and "det_id" in pts[0]:
        st.session_state[sel_key] = int(pts[0]["det_id"])
        st.session_state[mode_key] = "Incident"


def nudge(key, delta, lo, hi):
    st.session_state[key] = min(hi, max(lo, st.session_state[key] + delta))


def jump(key, t):
    st.session_state[key] = t


# ---------------------------------------------------------------- header
h1, h2, h3 = st.columns([5, 4, 1.1], vertical_alignment="center")
with h3:
    with st.popover("Settings", width="stretch"):
        data_dir = st.text_input("Data folder", value=str(ROOT / "data"),
                                 help="Folder produced by scripts\\get_data.py (contains farm\\, sda\\, labels\\).")
        agg_label = st.radio("Chart aggregation", list(AGGREGATIONS), index=0,
                             help="Charts only. Detection always uses the pipeline's 1-minute features.")
with h2:
    window_name = st.radio("Analysis window", list(WINDOWS), index=0, horizontal=True, key="window")
    a_w, b_w = WINDOWS[window_name]
    st.markdown(f'<div class="fs-note fs-mono">{fmt(a_w)} → {fmt(b_w)} (end exclusive)</div>',
                unsafe_allow_html=True)
dev = window_name.startswith("Development")
with h1:
    status = (('<span class="fs-chip warn">Development · labeled · scores are in-sample</span>') if dev else
              ('<span class="fs-chip warn">Evaluation · unlabeled · accuracy not measured</span>'))
    st.markdown(
        '<div class="fs-title">FIELD SIGNAL</div>'
        '<div class="fs-sub">Straight Rows · GNSS guidance incident investigation for a three-tractor fleet</div>'
        f'<div class="fs-chips"><span class="fs-chip">Challenge simulation data</span>'
        f'<span class="fs-chip">Retrospective analysis</span>{status}</div>', unsafe_allow_html=True)

missing, sig = data_signature(data_dir)
if missing:
    st.error("Challenge data not found in the selected folder (Settings). Missing: " + ", ".join(missing))
    st.code(r".venv\Scripts\python.exe scripts\get_data.py --zip C:\path\to\StraightRows_Student_Package.zip",
            language="bat")
    st.stop()

cfg = Config()
cfg_items = tuple(sorted(asdict(cfg).items()))
try:
    d = load_data(data_dir, sig)
    dets = pipeline_results(data_dir, sig, window_name, cfg_items)
    flags = pipeline_flags(data_dir, sig, window_name, cfg_items)
    idx = sample_index(data_dir, sig)
except Exception as exc:  # malformed inputs: show the error instead of a blank page
    st.error(f"Could not load or analyse the data: {type(exc).__name__}: {exc}")
    st.stop()

tab_inv, tab_fleet, tab_method = st.tabs(["Investigation", "Fleet comparison", "Methodology and provenance"])
skey = f"{window_name}-{abs(hash(sig))}"          # selection keys change with window/data → no stale picks
rib_key, sel_key, mode_key = f"ribbon-{skey}", f"incident-{skey}", f"mode-{skey}"

# ---------------------------------------------------------------- investigation
with tab_inv:
    # ---- 1. fleet overview: one selection state shared by ribbon and selector
    if mode_key not in st.session_state:
        st.session_state[mode_key] = "Incident" if dets else "Custom interval"
    if dets and (not isinstance(st.session_state.get(sel_key), int) or st.session_state[sel_key] >= len(dets)):
        st.session_state[sel_key] = 0
    with st.container(border=True, key="panel-fleet"):
        if dets:
            heading("Fleet overview", f"{len(dets)} pipeline detections · click a bar or use the selector")
            cur = st.session_state[sel_key] if st.session_state[mode_key] == "Incident" else None
            st.altair_chart(fleet_ribbon(dets, cur, a_w, b_w), key=rib_key, selection_mode="pick", theme=None,
                            on_select=lambda: on_ribbon(rib_key, sel_key, mode_key), width="stretch")
            f1, f2, f3 = st.columns([4, 2, 2], vertical_alignment="bottom")
            f1.selectbox("Selected detection", list(range(len(dets))), key=sel_key,
                         format_func=lambda i: det_label(i, dets[i]), label_visibility="collapsed",
                         on_change=lambda: st.session_state.__setitem__(mode_key, "Incident"))
            f2.radio("Inspect", ["Incident", "Custom interval"], key=mode_key, horizontal=True,
                     label_visibility="collapsed")
            with f3.popover(f"Detection register ({len(dets)})", width="stretch"):
                st.dataframe(pd.DataFrame([{
                    "#": i + 1, "Start (UTC)": fmt(x["start"]), "End (UTC)": fmt(x["end"]),
                    "Minutes": round((pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).total_seconds() / 60),
                    "Tractors": ", ".join(x["tractors"]), "Cause (pipeline)": x["class"], "Action": x["action"],
                    "Confidence (fixed)": x["confidence"]} for i, x in enumerate(dets)]), hide_index=True,
                    width=900)
        else:
            heading("Fleet overview")
            st.info("No pipeline detections in this window. Inspect any interval below.")
            st.session_state[mode_key] = "Custom interval"
        mode = st.session_state[mode_key]

    selected = dets[st.session_state[sel_key]] if (dets and mode == "Incident") else None
    sel_idx = st.session_state[sel_key] if selected else None

    # ---- 2. incident summary
    with st.container(border=True, key="panel-summary"):
        if selected:
            s0, e0 = pd.Timestamp(selected["start"]), pd.Timestamp(selected["end"])
            cz = CAUSES[selected["class"]]
            mins = round((e0 - s0).total_seconds() / 60)
            st.markdown(
                f'<div class="fs-summary"><div class="main"><span class="fs-tag">Pipeline attribution · suspected, '
                f'not confirmed</span><div class="fs-headline">{code_chip(selected["class"])}{cz["headline"]}</div></div>'
                f'<div class="kv"><div>Tractors</div>{"".join(tractor_chip(t) for t in selected["tractors"])}</div>'
                f'<div class="kv"><div>Interval (UTC) · #{sel_idx + 1}</div><code>{s0:%m-%d %H:%M} → {e0:%H:%M}</code>'
                f' · {mins} min</div>'
                f'<div class="kv" style="flex-basis:240px"><div>Operator action</div>{ACTION_TEXT[selected["action"]]}</div>'
                f'<div class="kv"><div>Confidence</div><code>{selected["confidence"]}</code> fixed heuristic, '
                f'not calibrated</div></div>', unsafe_allow_html=True)
        else:
            s0 = e0 = None
            st.markdown('<div class="fs-summary"><div class="main"><div class="fs-headline">Custom interval</div>'
                        '<div class="fs-note">No detection selected; charts show the chosen interval.</div></div></div>',
                        unsafe_allow_html=True)

    # ---- 3. investigation workspace
    ev_col, dec_col = st.columns([2.55, 1], gap="medium")
    with ev_col:
        with st.container(border=True, key="panel-evidence"):
            if selected:
                t1, t2, t3 = st.columns([1.6, 3, 1.4], vertical_alignment="bottom")
                pad = t1.slider("Context before/after (min)", 0, 180, 30, step=5, key=f"pad-{skey}")
                a, b = max(a_w, s0 - pd.Timedelta(minutes=pad)), min(b_w, e0 + pd.Timedelta(minutes=pad))
                affected = selected["tractors"]
                tele_all = d["tele"]
                un = [t for t in TRACTORS if t not in affected]
                during = tele_all[(tele_all.ts >= s0) & (tele_all.ts < e0)]
                sa, su = _stats(during[during.tractor_id.isin(affected)]), _stats(during[during.tractor_id.isin(un)])
                sp = _stats(tele_all[(tele_all.ts >= s0 - PRE) & (tele_all.ts < s0) & tele_all.tractor_id.isin(affected)
                                     & (tele_all.speed_mps > 0)])
                channels = (ef_channels(sa, su, cfg) if selected["class"] == "EQUIPMENT_FAULT"
                            else PRIMARY[selected["class"]])
                scrub_key = f"scrub-{skey}-{sel_idx}-{pad}"
                default_t = s0
            else:
                t1, t2, t3 = st.columns([1.6, 3, 1.4], vertical_alignment="bottom")
                hours = pd.date_range(a_w, b_w - pd.Timedelta(hours=1), freq="1h")
                start = t1.selectbox("Interval start (UTC)", list(hours), index=12, format_func=fmt,
                                     key=f"cstart-{skey}")
                length = t3.slider("Length (min)", 15, 360, 120, step=15, key=f"clen-{skey}")
                a, b = start, min(b_w, start + pd.Timedelta(minutes=length))
                affected, channels, un = [], PRIMARY[None], []
                scrub_key = f"scrub-{skey}-custom-{start:%Y%m%d%H}-{length}"
                default_t = a
            focus_v = t2.segmented_control("Tractor focus", ["All", *TRACTORS], default="All", required=True,
                                           key=f"focus-{skey}", format_func=lambda v: "All tractors" if v == "All" else v)
            focus = None if focus_v in (None, "All") else focus_v

            # ---- manual replay: one cursor time, exact 1 Hz samples, shared by charts, readout and map
            lo, hi = a.to_pydatetime().replace(tzinfo=None), (b - pd.Timedelta(seconds=1)).to_pydatetime().replace(tzinfo=None)
            if scrub_key not in st.session_state or not (lo <= st.session_state[scrub_key] <= hi):
                st.session_state[scrub_key] = default_t.to_pydatetime().replace(tzinfo=None)
            r1, r2 = st.columns([3, 2.2], vertical_alignment="bottom")
            r1.slider("Replay time (UTC)", min_value=lo, max_value=hi, step=timedelta(seconds=1), format="HH:mm:ss",
                      key=scrub_key)
            with r2.container(horizontal=True, gap="small"):
                for lab, dt in (("−1 min", -60), ("−10 s", -10), ("+10 s", 10), ("+1 min", 60)):
                    st.button(lab, key=f"{scrub_key}{lab}", on_click=nudge,
                              args=(scrub_key, timedelta(seconds=dt), lo, hi))
                if selected:
                    st.button("Onset", key=f"{scrub_key}on", on_click=jump,
                              args=(scrub_key, s0.to_pydatetime().replace(tzinfo=None)))
            cursor = pd.Timestamp(st.session_state[scrub_key], tz="UTC")

            rule = AGGREGATIONS[agg_label]
            note = ""
            if rule == "1s" and (b - a) > pd.Timedelta(minutes=30):
                rule, note = "10s", " (1 s display is limited to 30-minute intervals)"
            bins = display_bins(data_dir, sig, a, b, rule)
            if bins.empty:
                st.info("No telemetry in this interval.")
            else:
                ov = overlays(a, b, s0, e0, cursor)
                legend = "".join(f'<span><i style="border-color:{TRACTOR_COLORS[t]}"></i>{t}</span>' for t in TRACTORS)
                legend += (f'<span><i style="border-color:{TEXT2}"></i>affected</span>'
                           f'<span><i style="border-color:{TEXT2};border-top-style:dashed"></i>not in detection</span>'
                           if affected else "")
                legend += (f'<span><i style="border-color:{BLUE};border-top-width:8px;opacity:.5"></i>selected '
                           f'detection</span>' if selected else "")
                legend += f'<span><i style="border-color:{TEXT}"></i>replay cursor {cursor:%H:%M:%S}</span>'
                st.markdown(f'<div class="fs-legend">{legend}<span class="fs-mono">· {rule} bins{note}</span></div>',
                            unsafe_allow_html=True)
                wf = flags[(flags.ts >= a) & (flags.ts < b)]
                with st.container(key="evcharts", gap=None):
                    ctx_ch = context_chart(dets, sel_idx, wf, a, b, cursor)
                    if ctx_ch is not None:
                        st.altair_chart(ctx_ch, theme=None, width="stretch")
                    for i, key in enumerate(channels):
                        ch = chart_for(key, bins, d, a, b, ov, affected, focus, 200 if i == 0 else 96,
                                       labels=(i == 0 or i == len(channels) - 1))
                        if ch is not None:
                            st.altair_chart(ch, theme=None, width="stretch")
                st.caption("Top strip: detections overlapping the interval (outlined = selected, faded = adjacent) and "
                           "the pipeline's per-minute working flag (thick = working, thin = parked). Lines are display "
                           "bins of the 1 Hz telemetry and break at missing bins; the cursor readout shows single "
                           "1 Hz samples. Channel choice per cause is display-only.")
                with st.expander("Inspect all signals"):
                    for k in ALL_CHANNELS:
                        ch = chart_for(k, bins, d, a, b, ov, affected, focus, 90, labels=True)
                        if ch is not None:
                            st.altair_chart(ch, theme=None, width="stretch")
                    st.caption("Bin means for cross-track error (signed) and mean C/N0; bin minimum for min C/N0; bin "
                               "median for satellites; % of samples for RTK link and RTK_FIXED; S4 and Kp as the "
                               "latest published value (step).")
            rfi = d["rfi"][(d["rfi"].ts >= a) & (d["rfi"].ts < b)]
            adv = d["adv"][(d["adv"].ts >= a) & (d["adv"].ts < b)]
            with st.expander(f"SDA reports in this interval ({len(rfi) + len(adv)})"):
                if not (len(rfi) or len(adv)):
                    st.caption("No RFI reports or constellation advisories timestamped inside the charted interval.")
                for r in rfi.itertuples():
                    st.markdown(f"- RFI `{r.id}` at `{r.ts:%Y-%m-%d %H:%M:%S} UTC`, confidence {r.confidence}, "
                                f"ellipse {r.semiMajor_km}×{r.semiMinor_km} km: {r.text} "
                                "(observation vs. report time not documented)")
                for v in adv.itertuples():
                    st.markdown(f"- Advisory `{v.id}` ({v.type}) at `{v.ts:%Y-%m-%d %H:%M} UTC`: {v.text}")

    with dec_col:
        with st.container(border=True, key="panel-decision"):
            heading("Decision")
            if selected:
                ev = selected["evidence"]
                st.markdown(f'<div class="fs-note">Recommended action · episode-level</div>'
                            f'<div class="fs-action">{ACTION_TEXT[selected["action"]]}</div>',
                            unsafe_allow_html=True)
                obs = observations(channels, sa, sp, su, affected, un, ev)
                st.markdown('<div class="fs-note" style="margin-top:10px">Observations (measured over the detection '
                            'interval)</div><ul class="fs-obs">' + "".join(f"<li>{o}</li>" for o in obs) + "</ul>",
                            unsafe_allow_html=True)
                st.markdown(f'<div class="fs-note" style="margin-top:6px">Main uncertainty</div>'
                            f'<div style="font-size:0.9rem">{UNCERTAINTY[selected["class"]]} Confidence '
                            f'{selected["confidence"]} is a fixed value, not a probability.</div>',
                            unsafe_allow_html=True)
                with st.expander("Full measurements"):
                    rows = [("Samples", "n", 0), ("Mean C/N0 dB-Hz", "cn0", 1), ("Min C/N0 dB-Hz", "mincn0", 1),
                            ("Satellites (median)", "sats", 0), ("XTE median m", "xte_med", 2),
                            ("XTE max m", "xte_max", 2), ("RTK_FIXED %", "fixed", 0), ("RTK link up %", "link", 0)]
                    seg_a = during[during.tractor_id.isin(affected)]
                    seg_u = during[during.tractor_id.isin(un)]
                    st.markdown(stats_table_html({"Detection": (sa, len(seg_a)), "Others": (su, len(seg_u))}, rows),
                                unsafe_allow_html=True)
                    st.caption(f"Detection = {' '.join(affected)} over the interval, all samples; Others = "
                               f"{' '.join(un) or 'none'}. Same function (evidence._stats) as the exported evidence.")
                with st.expander("Rule and uncertainty details"):
                    unc = {
                        "SPACE_WEATHER": f"Rule: all three tractors below {cfg.cn0_low_dbhz:g} dB-Hz with S4 ≥ "
                                         f"{cfg.s4_storm}. The S4 cutoff was chosen by hand on development data. A storm "
                                         "does not rule out simultaneous jamming; jamming inside a storm is currently missed.",
                        "JAMMING": f"Rule: mean C/N0 below {cfg.cn0_low_dbhz:g} dB-Hz with S4 below {cfg.s4_storm}. "
                                   "RFI reports are not used in the decision, and the rule does not check whether the "
                                   "loss is confined to one machine.",
                        "SPOOFING": f"Rule: guidance-monitor cross-track error above {cfg.xte_high_m:g} m (minute mean) "
                                    f"without C/N0 below {cfg.cn0_low_dbhz:g} dB-Hz. Reported position is not used. "
                                    "Spoofing during a storm is currently missed.",
                        "EQUIPMENT_FAULT": f"Rule: RTK link up < {cfg.link_low_frac:.0%} of a minute, or min C/N0 below "
                                           f"{cfg.dropout_dbhz:g} dB-Hz with normal mean C/N0. Same-cause gaps ≤ "
                                           f"{cfg.bridge_gap_s:g} s are bridged, so the interval can include normal minutes.",
                    }[selected["class"]]
                    st.markdown(f"- {unc}\n- Confidence {selected['confidence']}: fixed heuristic value {CONFIDENCE}; "
                                "not calibrated, not a probability.\n- Pipeline interpretation from the evidence: "
                                + " ".join(e for e in ev if e.startswith("Attributed") or e.startswith("Concurrent with"))
                                + ("\n- Same-cause detections on different tractors are merged within 5 min, which can "
                                   "overstate the affected set." if len(affected) > 1 else "")
                                + "\n- RFI reports are evidence only; the attribution rules do not use them.")
                with st.expander("Exact evidence exported to submission"):
                    st.markdown("\n".join(f"- {line}" for line in ev))
                with st.expander("Identifiers"):
                    st.markdown(f"- class `{selected['class']}`\n- action `{selected['action']}`\n"
                                f"- start `{selected['start']}`\n- end `{selected['end']}`\n"
                                f"- tractors `{selected['tractors']}`\n- confidence `{selected['confidence']}`")
            else:
                st.caption("Select a detection to see its action, observations and uncertainty.")
        with st.container(border=True, key="panel-readout"):
            heading("Replay readout", f"{cursor:%Y-%m-%d %H:%M:%S} UTC")
            st.markdown(readout_html(idx, flags, dets, cursor, focus, d), unsafe_allow_html=True)
            st.caption("Single 1 Hz samples at exactly this second; nothing is interpolated or taken from a nearby "
                       "second. \"In detection\" is episode-level membership, not a fresh diagnosis at this time.")

    # ---- 4. before / during / after + reported position
    c_cmp, c_pos = st.columns([1.35, 1], gap="medium")
    with c_cmp:
        with st.container(border=True, key="panel-compare"):
            if selected:
                aff_tele = tele_all[tele_all.tractor_id.isin(affected)]
                before = aff_tele[(aff_tele.ts >= s0 - PRE) & (aff_tele.ts < s0) & (aff_tele.speed_mps > 0)]
                after = aff_tele[(aff_tele.ts >= e0) & (aff_tele.ts < e0 + AFTER) & (aff_tele.speed_mps > 0)]
                dur = aff_tele[(aff_tele.ts >= s0) & (aff_tele.ts < e0)]
                heading("Before · during · after", f"{' '.join(affected)}")
                rows = [("Samples", "n", 0), ("Mean C/N0 dB-Hz", "cn0", 1), ("Min C/N0 dB-Hz", "mincn0", 1),
                        ("Satellites (median)", "sats", 0), ("XTE median m", "xte_med", 2), ("XTE max m", "xte_max", 2),
                        ("RTK_FIXED %", "fixed", 0), ("RTK link up %", "link", 0)]
                st.markdown(stats_table_html({
                    f"Before {hm(s0 - PRE)}–{hm(s0)}": stats_n(before), f"During {hm(s0)}–{hm(e0)}": stats_n(dur),
                    f"After {hm(e0)}–{hm(e0 + AFTER)}": stats_n(after)}, rows), unsafe_allow_html=True)
                overlap = [f"#{i + 1} {CAUSES[x['class']]['code']}" for i, x in enumerate(dets) if i != sel_idx
                           and set(x["tractors"]) & set(affected) and pd.Timestamp(x["start"]) < e0 + AFTER
                           and pd.Timestamp(x["end"]) > s0 - PRE]
                st.caption("Before = 30 min before onset, working samples (speed > 0) — the pipeline's evidence "
                           "baseline. During = all samples in the detection (the evidence statistics). After = 30 min "
                           "after the end, working samples — display-only, mirrors the baseline. All via "
                           "evidence._stats on raw 1 Hz telemetry; 'unavailable' = no qualifying samples."
                           + (f" Other detections on these tractors overlap these windows: {', '.join(overlap)}."
                              if overlap else ""))
            else:
                heading("Before · during · after")
                st.caption("Available for a selected detection.")
    with c_pos:
        with st.container(border=True, key="panel-position"):
            heading("Reported GNSS position", "may be misleading during spoofing")
            p, origin = position_bins(data_dir, sig, a, b)
            if p.empty:
                st.info("No telemetry in this interval.")
            else:
                chart, n_marks = position_chart(p, origin, idx, a, b, cursor, focus)
                st.altair_chart(chart, theme=None, width="content")
                st.caption(f"Retrospective playback of reported positions, not verified motion. Equal scale; metres "
                           f"from the interval's mean reported position (flat-earth: 1° lat = 111,320 m, 1° lon = "
                           f"111,320 m × cos {origin[0]:.4f}°). Faint = whole interval, bright = up to the cursor (10 s "
                           f"means, broken at gaps); markers = 1 Hz samples at the cursor ({n_marks}/3 present). No field "
                           "boundary, intended row or true location is drawn — the dataset provides none.")

    # ---- development labels: separate, never predictions
    if dev:
        with st.container(border=True, key="panel-labels"):
            heading("Development labels", "ground truth for the labeled window, not model output")
            labels = d.get("labels")
            if labels is None:
                st.info("No labels file in this data folder.")
            else:
                with st.expander(f"Labeled episodes ({len(labels)})"):
                    lab = labels.sort_values("start")
                    st.dataframe(pd.DataFrame({
                        "Label": lab.id, "Start (UTC)": lab.start.map(fmt), "End (UTC)": lab.end.map(fmt),
                        "Tractors": lab.tractors.map(", ".join), "Labeled cause": lab["class"],
                        "Labeled action": lab.recommended_action}), hide_index=True, width="stretch")
                if st.button("Score detections against development labels (official scorer, in-sample)"):
                    import score_submission
                    key = {"episodes": [{**r, "start": r["start"].isoformat(), "end": r["end"].isoformat()}
                                        for r in labels.to_dict("records")]}
                    res = score_submission.score({"detections": dets}, key)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Diagnostic (of 40)", f"{res['diagnostic_score']:.2f}")
                    m2.metric("Macro-F1", f"{res['macro_f1']:.3f}")
                    m3.metric("Onset credit", f"{res['mean_timing_credit']:.3f}")
                    m4.metric("False positives", len(res["false_positives"]))
                    st.caption("In-sample: parameters were chosen on these same labels. Not evaluation performance.")

# ---------------------------------------------------------------- fleet comparison
with tab_fleet:
    with st.container(border=True, key="panel-fleetcmp"):
        heading("Same interval across tractors", f"{fmt(a)} → {fmt(b)} · set on the Investigation tab")
        tele = d["tele"]
        rows = []
        for t in TRACTORS:
            seg = tele[(tele.ts >= a) & (tele.ts < b) & (tele.tractor_id == t)]
            wf_t = flags[(flags.ts >= a) & (flags.ts < b) & (flags.tractor_id == t)]
            involved = [f"{CAUSES[x['class']]['code']} {hm(x['start'])}-{hm(x['end'])}" for x in dets
                        if t in x["tractors"] and pd.Timestamp(x["start"]) < b and pd.Timestamp(x["end"]) > a]
            if seg.empty:
                rows.append({"Tractor": t, "Samples": 0})
                continue
            rows.append({
                "Tractor": t, "Samples": len(seg),
                "Working minutes (%)": round(100 * wf_t.working.mean(), 1) if len(wf_t) else None,
                "Mean C/N0 (dB-Hz)": round(seg.mean_cn0_dbhz.mean(), 1),
                "Lowest min C/N0 (dB-Hz)": round(seg.min_cn0_dbhz.min(), 1),
                "Median satellites": seg.num_sats.median(),
                "Median XTE (m)": round(seg.cross_track_error_m.median(), 3),
                "Largest |XTE| (m)": round(seg.cross_track_error_m.abs().max(), 3),
                "RTK link up (%)": round(100 * seg.base_link_ok.mean(), 1),
                "RTK_FIXED (%)": round(100 * (seg.fix_state == "RTK_FIXED").mean(), 1),
                "Detections in interval": "; ".join(involved) or "none",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption("Statistics from raw 1 Hz telemetry; working share from the pipeline's per-minute flag.")

# ---------------------------------------------------------------- methodology
with tab_method:
    with st.container(border=True, key="panel-method"):
        heading("Methodology and limitations")
        st.markdown(f"""
- **Detections come from the pipeline** (`src/straightrows`): per-minute features → cause-agnostic flags →
  one test per cause → interval assembly → evidence. The dashboard does not detect anything itself.
- **Causes are pipeline attributions** (suspected), not confirmed truth. Development labels exist only for the
  labeled window; evaluation detections are unverified predictions.
- **Cross-track error** is the simulation's separate guidance-monitor channel (metres, signed). It is
  not computed from position.
- **Reported GNSS position is not ground truth**; it can be displaced during spoofing. Detection never uses it.
- **Working state** = the tractor's 1-minute mean speed > {cfg.moving_mps:g} m/s (speed is only 0 or 4.5 m/s, so at
  least 14 moving seconds). Space weather, jamming, spoofing and equipment fault require a working tractor.
- **Short stops can be bridged:** a stop of at most {cfg.bridge_gap_s:g} s inside one incident is joined.
- **Multipath is not detected.**
- **Confidence is a fixed heuristic value ({CONFIDENCE})**, not a calibrated probability.
- **Development results are in-sample:** parameters were chosen on the same 12 labeled episodes they are
  scored on. The evaluation window has no public labels; its accuracy is not measured here.
- **SDA and RFI timestamp meanings are not documented** (interval start or end; RFI observation or report time).
  The pipeline uses the latest value at or before each minute.
- Merging the same cause across tractors can overstate which tractors were affected.
""")
    with st.container(border=True, key="panel-display"):
        heading("Display choices", "none of these affect detection")
        st.markdown(
            "- **Primary channels per attributed cause:** "
            + "; ".join(f"{CAUSES[c]['short']} → {', '.join(CHANNELS[k][0] for k in ks)}"
                        for c, ks in PRIMARY.items() if c and c != "EQUIPMENT_FAULT")
            + ". All channels remain under *Inspect all signals*.\n"
            "- **Equipment fault** channels are chosen per detection with the same test the evidence text uses. Antenna "
            "dropouts → min C/N0, satellites, mean C/N0; correction-link loss → RTK link up, RTK_FIXED, min C/N0; both → "
            "min C/N0, RTK link up, RTK_FIXED. Cross-track error is never primary for equipment fault.\n"
            "- **Aggregation:** bin means (cross-track error keeps its sign; mean C/N0), bin minimum (min C/N0), bin median "
            "(satellites), percentage of samples (RTK link, RTK_FIXED). At 1 min these equal the pipeline's features. "
            "No smoothing. Lines break at missing bins and never join different tractors.\n"
            "- **Replay cursor:** the slider moves in whole UTC seconds inside the charted interval. The readout shows "
            "the raw 1 Hz sample whose timestamp equals the cursor exactly (tolerance 0 s; the telemetry is 1 Hz "
            "without gaps). If no sample exists at that second it shows *no sample*, never a neighbouring value. "
            "Working state in the readout is the pipeline's flag for the containing minute. S4 and Kp are the latest "
            "published values at or before the cursor (the pipeline's as-of rule), with their publication time.\n"
            "- **Before / during / after:** Before = affected tractors, 30 min before onset, working samples "
            "(speed > 0) — exactly the evidence baseline. During = affected tractors over the detection, all samples. "
            "After = affected tractors, 30 min after the end, working samples — a display-only mirror of the baseline. "
            "All computed with evidence._stats; empty windows show *unavailable*.\n"
            "- **Reported position:** 10 s means of reported lat/lon converted to metres from the interval's mean "
            "position with a flat-earth approximation (adequate over about 1 km); equal scale on both axes; trails "
            "break at missing 10 s bins. No external map tiles.\n"
            "- **Colours:** tractors T1 blue, T2 amber, T3 cyan (with T1/T2/T3 text and marker shapes ●■▲). Causes use a "
            "separate hue set (violet SW, coral JAM, magenta SPF, slate EF) and always carry a text code. Unaffected "
            "tractors are dashed; tractor focus dims the others without hiding them.")
    with st.container(border=True, key="panel-prov"):
        heading("Configuration and provenance")
        st.dataframe(pd.DataFrame(
            [("Window", window_name), ("Window UTC", f"{fmt(a_w)} → {fmt(b_w)} (end exclusive)"),
             ("Data folder", data_dir), ("Git commit", git_commit()), ("Detections", str(len(dets))),
             ("Chart aggregation", agg_label)]
            + [(f"Config.{k}", str(v)) for k, v in asdict(cfg).items()],
            columns=["Item", "Value"]), hide_index=True, width="stretch")
