"""FIELD SIGNAL — Straight Rows interactive incident report (Streamlit dashboard).

Launch from the repository root (Windows CMD):
    .venv\\Scripts\\python.exe -m streamlit run src\\dashboard.py

Three levels, one on screen at a time: Fleet overview (choose a case) → Incident report (finding and
decision) with its Evidence lab (one question per view), plus a custom-interval lab.

Read-only view of the existing pipeline. Detections, evidence, actions and the working flag all come
from `straightrows` (io.load, pipeline.detect, export.to_submission, features.minute_features +
candidates.flag, attribution.tests for per-minute rule counts, evidence._stats for measurements).
The dashboard selects intervals, chooses which channels to draw, aggregates raw telemetry for display,
and looks up exact 1 Hz samples for the replay cursor. Nothing here changes detection.
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
from straightrows.attribution import tests as rule_tests  # noqa: E402
from straightrows.candidates import flag  # noqa: E402
from straightrows.config import DEV, EVAL, Config  # noqa: E402
from straightrows.evidence import PRE, _stats  # noqa: E402
from straightrows.export import CONFIDENCE, to_submission  # noqa: E402
from straightrows.features import minute_features  # noqa: E402
from straightrows.io import load  # noqa: E402
from straightrows.pipeline import detect  # noqa: E402

# ---------------------------------------------------------------- design tokens (project design, not Bluestaq)
NAVY, CANVAS, SURFACE = "#0B1A30", "#F3F6FA", "#FFFFFF"
INK, INK2, RULE, GRID = "#14213D", "#4A5A70", "#D3DCE8", "#E7ECF3"
BLUE, BLUE_BG, CYAN = "#1F5FD1", "#E3ECFB", "#0C8599"
AMBER, AMBER_BG, CORAL = "#B7791F", "#FBF0DC", "#C2364A"

TRACTORS = ["T1", "T2", "T3"]
# Tractor identity (lines, markers, inspector headers) — never used for causes.
TRACTOR_COLORS = {"T1": "#1971C2", "T2": "#D9480F", "T3": "#2B8A3E"}
TRACTOR_SHAPES = {"T1": "circle", "T2": "square", "T3": "triangle-up"}
WINDOWS = {"Evaluation": EVAL, "Development": DEV}
WCODE = {"Evaluation": "eval", "Development": "dev"}
REQUIRED = ["farm/tractor_telemetry.csv.gz", "sda/sgi_indices.json", "sda/scintillation_series.json",
            "sda/constellation_advisories.json", "sda/rfi_reports.json"]
AGGREGATIONS = {"1 min": "1min", "10 s": "10s", "1 s (intervals up to 30 min)": "1s"}
AFTER = pd.Timedelta(minutes=30)   # display-only "after" window; mirrors evidence.PRE (30 min before onset)

# Cause identity: separate hue family from tractors, and always a text code.
CAUSES = {
    "SPACE_WEATHER": dict(code="SW", color="#6741D9", noun="space weather (regional scintillation)",
                          short="Space weather"),
    "JAMMING": dict(code="JAM", color="#C2255C", noun="jamming (radio-frequency interference)", short="Jamming"),
    "SPOOFING": dict(code="SPF", color="#9C36B5", noun="spoofing", short="Spoofing"),
    "EQUIPMENT_FAULT": dict(code="EF", color="#5C677D", noun="equipment fault", short="Equipment fault"),
    "MULTIPATH": dict(code="MP", color="#0C8599", noun="multipath", short="Multipath"),
}
ACTION_TEXT = {
    "HALT_OR_DEGRADED_MODE": "Halt, or continue only in a degraded guidance mode, until conditions improve.",
    "HALT_AND_REPORT": "Halt and report suspected interference.",
    "HALT_CROSSCHECK_AND_REPORT": "Halt, cross-check position with an independent source, and report.",
    "SERVICE_MACHINE_OTHERS_CONTINUE": "Service the affected machine; the other machines continue.",
    "CONTINUE_FALSE_ALARM": "Continue; treat as a false alarm.",
}
ACTION_SHORT = {
    "HALT_OR_DEGRADED_MODE": "Halt or degraded mode",
    "HALT_AND_REPORT": "Halt and report",
    "HALT_CROSSCHECK_AND_REPORT": "Halt, cross-check, report",
    "SERVICE_MACHINE_OTHERS_CONTINUE": "Service machine, others continue",
    "CONTINUE_FALSE_ALARM": "Continue (false alarm)",
}

# Display-only channel registry.
CHANNELS = {
    "xte": "Cross-track error (m, signed)",
    "cn0": "Mean C/N0 (dB-Hz)",
    "min_cn0": "Min C/N0 (dB-Hz)",
    "sats": "Satellites (median)",
    "link": "RTK correction link up (% of bin)",
    "fixed": "RTK_FIXED (% of bin)",
    "s4": "Regional S4 index (15-min series)",
    "kp": "Kp index (3-hour series)",
}
# Fixed physical floor/ceiling for C/N0 axes (widened only if data fall outside) so small changes are not
# magnified by auto-zoom; other channels start at zero except signed cross-track error (auto, includes 0).
FLOOR = {"cn0": (20, 50), "min_cn0": (0, 50)}
ZERO = {"xte": True, "cn0": False, "min_cn0": False, "sats": True, "link": True, "fixed": True, "s4": True, "kp": True}

# Evidence-lab views (display-only). Each view: question, channels drawn.
VIEWS = {
    "guidance": dict(label="Guidance", q="Did guidance error rise, and on which tractors?", ch=["xte"]),
    "receiver": dict(label="Receiver health", q="Did signal quality drop, and was it shared or isolated?",
                     ch=["cn0", "min_cn0", "sats"]),
    "link": dict(label="Link & fix", q="Did the RTK correction link or fix quality fail?",
                 ch=["link", "fixed"]),
    "space": dict(label="Space / RF", q="Did regional conditions or RF reports coincide with the detection?",
                  ch=["s4", "kp"]),
    "compare": dict(label="Before / after", q="How did each tractor compare before, during and after?",
                    ch=[]),
    "position": dict(label="Position", q="Where did each receiver report itself? (not ground truth)",
                     ch=[]),
    "all": dict(label="All signals", q="Every channel on the same time axis.", ch=[]),
}
# Display-only default view per attributed cause.
DEFAULT_VIEW = {"SPOOFING": "guidance", "JAMMING": "receiver", "SPACE_WEATHER": "space", "EQUIPMENT_FAULT": "receiver"}
# Rule that the pipeline applies per tractor-minute (attribution.tests), in words.
RULE_TEXT = {
    "SPACE_WEATHER": "1-min mean C/N0 below {cn0:g} dB-Hz on all three tractors, regional S4 ≥ {s4}, tractor working",
    "JAMMING": "1-min mean C/N0 below {cn0:g} dB-Hz with regional S4 below {s4}, tractor working",
    "SPOOFING": "1-min mean cross-track error above {xte:g} m while working, without C/N0 below {cn0:g} dB-Hz",
    "EQUIPMENT_FAULT": "RTK link up < {link:.0%} of the minute, or min C/N0 below {drop:g} dB-Hz with normal mean "
                       "C/N0, tractor working",
}
UNCERTAINTY = {
    "SPACE_WEATHER": "The S4 cutoff was chosen by hand on development data; jamming during a storm would be missed.",
    "JAMMING": "RFI reports are not used by the rule, and it does not test whether the loss is confined to one "
               "machine.",
    "SPOOFING": "The rule uses only the guidance-monitor error; reported position is not checked, and spoofing "
                "during a storm would be missed.",
    "EQUIPMENT_FAULT": "Short same-cause gaps are bridged, so the interval can include normal minutes; a concurrent "
                       "spoof can also raise cross-track error.",
}

st.set_page_config(page_title="Field Signal · Straight Rows", layout="wide", initial_sidebar_state="collapsed")
alt.data_transformers.disable_max_rows()  # intervals are bounded; rows stay in the low thousands

MONO = "ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace"
SANS = "'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif"
# Styling targets only keyed containers (st-key-<key>) and our own HTML classes.
st.markdown(f"""<style>
[data-testid="stHeader"] {{ display: none; }}
[data-testid="stMainBlockContainer"] {{ padding: 0 1.5rem 2.5rem 1.5rem; max-width: none; }}
html, body, [data-testid="stAppViewContainer"] {{ font-family: {SANS}; }}
/* Header band: Streamlit gives the block width/max-width 100%, so negative margins alone cannot widen it; width
   is set to the container width plus its 1.5rem side padding (no vw units, so no scrollbar compensation).
   -1rem cancels the flex gap after the hidden <style> element. */
.st-key-shell {{ background: {NAVY}; width: calc(100% + 3rem) !important; max-width: none !important;
  margin: -1rem -1.5rem 1rem -1.5rem;
  padding: 12px 1.5rem 14px 1.5rem; }}
.st-key-shell [data-testid="stVerticalBlock"] {{ gap: 0.35rem; }}
.st-key-shell [data-testid="stMarkdownContainer"] {{ margin-bottom: 0; }}
.st-key-shell [data-testid="stPopover"] button {{ background: #FFFFFF; color: {INK}; }}
.st-key-shell .fs-dates {{ color: #C9D6EA; }}
.st-key-shell [data-testid="stButtonGroup"] {{ background: #FFFFFF; border-radius: 6px; padding: 2px;
  width: fit-content; }}
.fs-brand {{ color: #FFFFFF; font-weight: 700; font-size: 1.12rem; letter-spacing: 0.04em; line-height: 1.2; }}
.fs-brand span {{ color: #9DB4D6; font-weight: 400; letter-spacing: 0; font-size: 0.9rem; margin-left: 10px; }}
.fs-dates {{ font-family: {MONO}; font-size: 0.8rem; }}
.fs-state {{ font-size: 0.8rem; color: #F2C98A; }}
div[class*="st-key-surface"] {{ background: {SURFACE}; border: 1px solid {RULE}; border-radius: 8px;
  padding: 14px 18px 16px 18px; }}
.fs-eyebrow {{ font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: {INK2}; }}
.fs-h1 {{ font-size: 1.65rem; font-weight: 700; color: {INK}; line-height: 1.2; margin: 2px 0 4px 0; }}
.fs-h2 {{ font-size: 1.05rem; font-weight: 650; color: {INK}; margin: 0 0 2px 0; }}
.fs-meta {{ color: {INK2}; font-size: 0.95rem; }}
.fs-mono {{ font-family: {MONO}; font-size: 0.92em; }}
.fs-q {{ font-size: 1.02rem; font-weight: 600; color: {INK}; margin: 2px 0 2px 0; }}
.fs-note {{ font-size: 0.86rem; color: {INK2}; }}
.fs-warn {{ font-size: 0.86rem; color: #7A4D0B; background: {AMBER_BG}; border-left: 3px solid {AMBER};
  padding: 6px 10px; border-radius: 0 4px 4px 0; }}
.fs-code {{ display: inline-block; font-family: {MONO}; font-size: 0.78rem; font-weight: 700; color: #fff;
  padding: 1px 6px; border-radius: 4px; margin-right: 8px; vertical-align: 2px; }}
.fs-tr {{ display: inline-block; font-family: {MONO}; font-weight: 700; font-size: 0.86rem; padding: 0 6px 0 5px;
  border-left: 4px solid; margin-right: 5px; background: #EEF2F7; border-radius: 2px; color: {INK}; }}
.fs-action {{ border-left: 4px solid {BLUE}; background: {BLUE_BG}; padding: 10px 12px; border-radius: 0 6px 6px 0;
  font-weight: 600; color: #102A5C; font-size: 1.0rem; }}
.fs-sec {{ margin-top: 14px; }}
.fs-sec h4 {{ font-size: 0.78rem; font-weight: 650; letter-spacing: 0.06em; text-transform: uppercase; color: {INK2};
  margin: 0 0 4px 0; padding: 0; }}
.fs-list {{ margin: 0; padding-left: 1.05rem; font-size: 0.93rem; color: {INK}; }}
.fs-list li {{ margin-bottom: 3px; }}
.fs-obs {{ border-top: 1px solid {GRID}; padding-top: 8px; margin-top: 6px; font-size: 0.93rem; color: {INK}; }}
.fs-insp {{ display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 0.9rem; color: {INK}; align-items: baseline; }}
.fs-insp b {{ font-family: {MONO}; font-weight: 600; }}
.fs-insp .na {{ color: {CORAL}; }}
.fs-tbl {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
.fs-tbl th, .fs-tbl td {{ padding: 4px 8px; border-bottom: 1px solid {GRID}; text-align: right; }}
.fs-tbl th {{ font-weight: 600; color: {INK2}; font-size: 0.8rem; }}
.fs-tbl th:first-child, .fs-tbl td:first-child {{ text-align: left; white-space: nowrap; }}
.fs-tbl td.v {{ font-family: {MONO}; }}
.fs-tbl td.na {{ color: {CORAL}; font-family: {SANS}; }}
.fs-tbl td.focus, .fs-tbl th.focus {{ background: #F1F5FB; }}
div[class*="st-key-row-"] {{ border-bottom: 1px solid {GRID}; padding: 4px 8px; border-left: 3px solid transparent; }}
div[class*="st-key-row-"]:hover {{ background: #F6F9FD; }}
div[class*="st-key-row-"]:focus-within {{ background: #F6F9FD; border-left-color: #8FB1EA; }}
div[class*="st-key-row-on"], div[class*="st-key-row-on"]:hover {{ background: {BLUE_BG}; border-left-color: {BLUE}; }}
.fs-sel {{ font-size: 0.75rem; font-weight: 650; color: {BLUE}; margin-left: 8px; }}
.fs-row-cause {{ font-weight: 600; color: {INK}; }}
.fs-legend {{ font-size: 0.84rem; color: {INK2}; display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }}
.fs-legend i {{ display: inline-block; width: 18px; height: 0; border-top: 2px solid; vertical-align: middle;
  margin-right: 5px; }}
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
    return load(data_dir)   # shared, read-only; keyed by path + file signature


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
    return to_submission(dets, d, cfg, "dashboard", "https://github.com/dashboard/view")["detections"]


@st.cache_data(show_spinner="Computing per-minute flags…", max_entries=8)
def pipeline_flags(data_dir, sig, window_name, cfg_items):
    """Per tractor-minute features + candidate flags + the per-cause rule results (attribution.tests)."""
    d = load_data(data_dir, sig)
    cfg = Config(**dict(cfg_items))
    f = flag(minute_features(d, WINDOWS[window_name]), cfg)
    for cause, hit in rule_tests(f, cfg).items():
        f[f"rule_{cause}"] = hit
    return f


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
    step = pd.Timedelta(rule)   # break lines where consecutive bins are more than one bin apart
    gap = out.groupby("tractor_id").ts.diff().fillna(step) > step
    out["seg"] = out.tractor_id + "-" + gap.groupby(out.tractor_id).cumsum().astype(str)
    out["time_utc"] = out.ts.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return out


@st.cache_data(max_entries=48)
def phase_stats(data_dir, sig, s0, e0, affected):
    """evidence._stats for: affected pooled (exactly the exported evidence definitions) and per tractor.

    before = [s0 - 30 min, s0), working samples (speed > 0)      — evidence baseline (evidence.PRE)
    during = [s0, e0), all samples                               — evidence statistics
    after  = [e0, e0 + 30 min), working samples (speed > 0)      — display-only mirror of the baseline
    """
    tele = load_data(data_dir, sig)["tele"]
    win = {"before": (s0 - PRE, s0, True), "during": (s0, e0, False), "after": (e0, e0 + AFTER, True)}
    out = {}
    for ph, (lo, hi, working) in win.items():
        seg = tele[(tele.ts >= lo) & (tele.ts < hi)]
        if working:
            seg = seg[seg.speed_mps > 0]
        out[(ph, "affected")] = (_stats(seg[seg.tractor_id.isin(affected)]), int(seg.tractor_id.isin(affected).sum()))
        un = seg[~seg.tractor_id.isin(affected)]
        out[(ph, "others")] = (_stats(un), len(un))
        for t in TRACTORS:
            s = seg[seg.tractor_id == t]
            out[(ph, t)] = (_stats(s), len(s))
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


# ---------------------------------------------------------------- small helpers
def ts_(x):
    return pd.Timestamp(x)


def fmt(t):
    return ts_(t).strftime("%Y-%m-%d %H:%M UTC")


def hm(t):
    return ts_(t).strftime("%H:%M")


def mins(x):
    return round((ts_(x["end"]) - ts_(x["start"])).total_seconds() / 60)


def age(dt):
    s = int(dt.total_seconds())
    return f"{s // 3600} h {s % 3600 // 60:02d} min" if s >= 3600 else f"{s // 60} min {s % 60:02d} s"


def show(chart, width="stretch"):
    """Render an Altair chart via its Vega-Lite spec, serialised once without JSON-schema re-validation.

    st.altair_chart validates every spec against the full Vega-Lite schema on each rerun (~0.5 s per report
    view across six charts). The specs are fixed code paths, checked when developed; skipping the repeated
    validation changes no data or encoding.
    """
    st.vega_lite_chart(spec=to_spec(chart), theme=None, width=width)


@st.cache_data(max_entries=64, show_spinner=False)
def timeline_spec(data_dir, sig, window_name, cfg_items, sel_idx, compact):
    """Fleet timeline spec; depends only on the window's detections and the selection, so it is cached."""
    dets_ = pipeline_results(data_dir, sig, window_name, cfg_items)
    a_, b_ = WINDOWS[window_name]
    return to_spec(fleet_timeline(dets_, sel_idx, a_, b_, compact=compact))


def interval_text(x, short=False):
    """'2026-05-06 01:00–02:00 UTC' (short: '05-06 · 01:00–02:00 UTC'); both dates when the interval crosses midnight."""
    s, e = ts_(x["start"]), ts_(x["end"])
    dfmt = "%m-%d" if short else "%Y-%m-%d"
    if s.normalize() == (e - pd.Timedelta(seconds=1)).normalize():
        return f"{s:{dfmt}}{' ·' if short else ''} {s:%H:%M}–{e:%H:%M} UTC"
    return f"{s:{dfmt} %H:%M} – {e:{dfmt} %H:%M} UTC"


def det_id(x):
    """Stable identifier: cause, start and tractors (unique per window; row numbers are only for display)."""
    return f"{x['class']}|{x['start']}|{','.join(x['tractors'])}"


@st.cache_data(ttl=120, show_spinner=False)
def git_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def code_chip(cause):
    c = CAUSES[cause]
    return f'<span class="fs-code" style="background:{c["color"]}">{c["code"]}</span>'


def tractor_chips(trs):
    return "".join(f'<span class="fs-tr" style="border-left-color:{TRACTOR_COLORS[t]}">{t}</span>' for t in trs)


def title_of(x):
    return f"Suspected {CAUSES[x['class']]['noun']} · {' '.join(x['tractors'])}"


def H(s):
    st.markdown(s, unsafe_allow_html=True)


def rule_counts(flags, cause, s0, e0, trs):
    """Per tractor: minutes in [s0, e0) where the cause's pipeline rule is true, and minutes present."""
    m = flags[(flags.ts >= s0) & (flags.ts < e0)]
    out = {}
    for t in trs:
        mt = m[m.tractor_id == t]
        out[t] = (int(mt[f"rule_{cause}"].sum()), len(mt))
    return out


def flag_counts(flags, col, s0, e0):
    m = flags[(flags.ts >= s0) & (flags.ts < e0)]
    return {t: (int(m[m.tractor_id == t][col].sum()), int((m.tractor_id == t).sum())) for t in TRACTORS}


def counts_text(c):
    return " · ".join(f"{t} <b class='fs-mono'>{k}/{n}</b>" for t, (k, n) in c.items())


def who_flagged(c):
    hit = [t for t, (k, _) in c.items() if k > 0]
    if not hit:
        return "no tractor"
    return "all three tractors" if len(hit) == 3 else " and ".join(hit) + " only"


# ---------------------------------------------------------------- charts
# Chart theme as a plain Vega-Lite config, merged into each serialised spec (Altair's .configure_*() chain
# deep-copies the whole chart, data included, once per call).
CHART_CONFIG = {
    "background": SURFACE, "font": SANS, "view": {"stroke": None},
    "axis": {"labelColor": INK2, "titleColor": INK2, "gridColor": GRID, "domainColor": RULE, "tickColor": RULE,
             "labelFontSize": 12, "titleFontSize": 12, "titleFontWeight": "normal"},
    "title": {"color": INK, "fontSize": 13, "fontWeight": 600, "anchor": "start", "offset": 6},
    "legend": {"labelColor": INK, "titleColor": INK2, "labelFontSize": 12},
}


def styled(ch):
    return ch   # theme is applied in to_spec()


def to_spec(chart):
    spec = chart.to_dict(validate=False)
    spec["config"] = CHART_CONFIG
    # Fit only the width to the container; the height stays the plot height (plus title and axes), as with
    # st.altair_chart. A full "fit" squeezed titles and axes into the stated height and clipped titles.
    spec["autosize"] = {"type": "fit-x", "contains": "padding"}
    return spec


def x_enc(a, b, labels=True, title=True):
    same_day = a.normalize() == (b - pd.Timedelta(seconds=1)).normalize()
    return alt.X("ts:T", scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
                 title=(f"UTC · {a:%Y-%m-%d}" if same_day else "UTC") if (labels and title) else None,
                 axis=alt.Axis(format="%H:%M" if same_day else "%m-%d %H:%M", labelAngle=0, labels=labels,
                               grid=False, labelFont=MONO, tickCount=8))


Y_AXIS = dict(title=None, labelFont=MONO, minExtent=52, maxExtent=52, tickCount=5, format=".4~r")


def overlays(a, b, s0, e0, cursor):
    """Selected-detection band (defined meaning: the detection interval) + boundaries + replay cursor."""
    under, over = [], []
    if s0 is not None:
        band = pd.DataFrame({"ts": [max(s0, a)], "end": [min(e0, b)]})
        under.append(alt.Chart(band).mark_rect(color=BLUE, opacity=0.08).encode(
            x=x_enc(a, b), x2="end:T", tooltip=alt.value(None)))
        edges = pd.DataFrame({"ts": [t for t in (s0, e0) if a <= t <= b]})
        if len(edges):
            under.append(alt.Chart(edges).mark_rule(color=BLUE, strokeDash=[5, 3], strokeWidth=1.2).encode(
                x=x_enc(a, b), tooltip=alt.value(None)))
    if cursor is not None:
        over.append(alt.Chart(pd.DataFrame({"ts": [cursor]})).mark_rule(color=INK, strokeWidth=1.5).encode(
            x=x_enc(a, b), tooltip=alt.value(None)))
    return under, over


def line_chart(df, field, a, b, ov, affected, focus, height, labels=True):
    d2 = df.assign(role=df.tractor_id.map(lambda t: "affected" if (not affected or t in affected) else "other"))
    focused = alt.datum.tractor_id == focus
    if field in FLOOR:
        lo_, hi_ = FLOOR[field]
        yscale = alt.Scale(domain=[min(lo_, math.floor(df[field].min())), max(hi_, math.ceil(df[field].max()))])
    else:
        yscale = alt.Scale(zero=ZERO[field])
    line = alt.Chart(d2).mark_line().encode(
        x=x_enc(a, b, labels=labels),
        y=alt.Y(f"{field}:Q", scale=yscale, axis=alt.Axis(**Y_AXIS)),
        color=alt.Color("tractor_id:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_COLORS.values())),
                        legend=None),
        strokeDash=alt.StrokeDash("role:N", scale=alt.Scale(domain=["affected", "other"], range=[[1, 0], [5, 3]]),
                                  legend=None),
        opacity=alt.value(1) if focus is None else alt.condition(focused, alt.value(1), alt.value(0.2)),
        strokeWidth=alt.value(1.7) if focus is None else alt.condition(focused, alt.value(2.6), alt.value(1.2)),
        detail="seg:N",
        tooltip=[alt.Tooltip("tractor_id:N", title="tractor"), alt.Tooltip("time_utc:N", title="bin start"),
                 alt.Tooltip(f"{field}:Q", title=CHANNELS[field], format=".3f")])
    under, over = ov
    thr = THRESHOLD.get(field)
    if thr is not None:
        under = under + [alt.Chart(pd.DataFrame({"y": [thr]})).mark_rule(color=AMBER, strokeDash=[2, 2],
                                                                           strokeWidth=1.3).encode(y="y:Q")]
    return styled(alt.layer(*under, line, *over).properties(height=height, width="container", title=CHANNELS[field]))


THRESHOLD = {"cn0": Config().cn0_low_dbhz, "min_cn0": Config().dropout_dbhz, "xte": Config().xte_high_m,
             "link": 100 * Config().link_low_frac}   # pipeline rule levels (per 1-min value), drawn dotted amber


def step_chart(d, key, a, b, ov, height, labels=True, rfi=None):
    df = held(d[key], key, a, b)
    if df.empty:
        return None
    df = df.assign(time_utc=df.ts.dt.strftime("%Y-%m-%d %H:%M UTC"))
    line = alt.Chart(df).mark_line(interpolate="step-after", color=INK, strokeWidth=1.8).encode(
        x=x_enc(a, b, labels=labels), y=alt.Y(f"{key}:Q", scale=alt.Scale(zero=True), axis=alt.Axis(**Y_AXIS)),
        tooltip=[alt.Tooltip("time_utc:N", title="value in force from"), alt.Tooltip(f"{key}:Q", format=".3f")])
    under, over = ov
    extra = []
    if key == "s4":
        cut = pd.DataFrame({"y": [Config().s4_storm]})
        extra.append(alt.Chart(cut).mark_rule(color=AMBER, strokeDash=[2, 2]).encode(y="y:Q"))
    if rfi is not None and len(rfi):
        r = rfi.assign(time_utc=rfi.ts.dt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        extra.append(alt.Chart(r).mark_rule(color=CORAL, strokeWidth=2.2).encode(
            x=x_enc(a, b, labels=labels), tooltip=[alt.Tooltip("id:N", title="RFI report"),
                                                   alt.Tooltip("time_utc:N", title="timestamp"), "confidence:Q"]))
    title = CHANNELS[key] + " · regional, not per tractor"
    return styled(alt.layer(*under, line, *extra, *over).properties(height=height, width="container", title=title))


def context_strip(dets, sel_idx, wf, a, b, cursor):
    """Detections overlapping the interval (selected outlined, adjacent faded) + pipeline working state."""
    lanes = ["Det."] + [f"{t} working" for t in TRACTORS]
    y = alt.Y("lane:N", sort=lanes, scale=alt.Scale(domain=lanes), title=None,
              axis=alt.Axis(labelFont=MONO, ticks=False, domain=False, minExtent=52, maxExtent=52,
                            labelExpr="replace(datum.label, ' working', '')"))
    layers = []
    rows = [{"lane": "Det.", "cause": x["class"], "code": f"{CAUSES[x['class']]['code']} " + " ".join(x["tractors"]),
             "when": f"{fmt(x['start'])} → {fmt(x['end'])}", "ts": max(ts_(x["start"]), a), "end": min(ts_(x["end"]), b),
             "state": "selected" if i == sel_idx else "adjacent"}
            for i, x in enumerate(dets) if ts_(x["start"]) < b and ts_(x["end"]) > a]
    if rows:
        items = pd.DataFrame(rows)
        base = alt.Chart(items).encode(x=x_enc(a, b, labels=False), x2="end:T", y=y)
        layers.append(base.mark_bar(height=12, cornerRadius=2).encode(
            color=alt.Color("cause:N", scale=alt.Scale(domain=list(CAUSES), range=[c["color"] for c in CAUSES.values()]),
                            legend=None),
            opacity=alt.condition(alt.datum.state == "selected", alt.value(1.0), alt.value(0.35)),
            stroke=alt.condition(alt.datum.state == "selected", alt.value(INK), alt.value(None)),
            tooltip=[alt.Tooltip("code:N", title="detection"), "when:N", "state:N"]))
        layers.append(base.mark_text(align="left", dx=4, fontSize=10, font=MONO, color="#FFFFFF", fontWeight="bold")
                      .encode(x="ts:T", text="code:N"))
    if len(wf):
        w = wf.assign(lane=wf.tractor_id + " working", end=wf.ts + pd.Timedelta(minutes=1),
                      state=wf.working.map({True: "working", False: "parked"}),
                      time_utc=wf.ts.dt.strftime("%Y-%m-%d %H:%M UTC"))
        layers.append(alt.Chart(w).mark_bar().encode(
            x=x_enc(a, b, labels=False), x2="end:T", y=y,
            # Fixed values, not a colour scale: a scale would merge with the cause colours above.
            color=alt.condition(alt.datum.state == "working", alt.value("#8C9BB0"), alt.value("#D9E0EA")),
            size=alt.condition(alt.datum.state == "working", alt.value(8), alt.value(3)),
            tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="minute"), "state:N",
                     alt.Tooltip("moving:Q", title="mean speed (m/s)", format=".2f")]))
    if cursor is not None:
        layers.append(alt.Chart(pd.DataFrame({"ts": [cursor]})).mark_rule(color=INK, strokeWidth=1.5)
                      .encode(x=x_enc(a, b, labels=False)))
    return styled(alt.layer(*layers).properties(height=66, width="container")) if layers else None


def fleet_timeline(dets, sel_idx, a, b, compact=False):
    """T1/T2/T3 lanes across the window; concurrent causes on one tractor sit in separate sub-rows."""
    rows = []
    for i, x in enumerate(dets):
        c = CAUSES[x["class"]]
        for t in x["tractors"]:
            rows.append({"det": i, "tractor": t, "cause": x["class"], "start": ts_(x["start"]), "end": ts_(x["end"]),
                         "text": c["code"] if (mins(x) >= 75 and not compact) else "",
                         "label": f"#{i + 1} {c['short']} · {' '.join(x['tractors'])} · {hm(x['start'])}–{hm(x['end'])} UTC",
                         "sel": "selected" if i == sel_idx else "other"})
    df = pd.DataFrame(rows)
    pick = alt.selection_point(name="pick", fields=["det"], on="click", clear=False)
    x = alt.X("start:T", title=None, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
              axis=alt.Axis(format="%m-%d %H:%M" if (b - a) > pd.Timedelta(days=1) else "%H:%M", labelAngle=0,
                            labelFont=MONO, gridColor=GRID, tickCount=12, labels=not compact or True,
                            labelFontSize=11 if compact else 12))
    y = alt.Y("tractor:N", title=None, sort=TRACTORS, scale=alt.Scale(domain=TRACTORS),
              axis=alt.Axis(labelFont=MONO, labelFontWeight="bold", labelColor=INK, ticks=False, domain=False,
                            labelFontSize=13, labels=not compact))
    present = [c for c in CAUSES if c in set(df.cause)]
    layers = []
    if sel_idx is not None:
        s = dets[sel_idx]
        layers.append(alt.Chart(pd.DataFrame({"start": [ts_(s["start"])], "end": [ts_(s["end"])]}))
                      .mark_rect(color=BLUE, opacity=0.14).encode(x=x, x2="end:T"))
    # Full timeline: concurrent causes in sub-rows. Compact navigator: one 10 px bar per tractor lane (sub-rows
    # there were ~2 px tall and could not be clicked); the selected detection is drawn last so it stays on top.
    if compact:
        df = pd.concat([df[df.sel != "selected"], df[df.sel == "selected"]])
        base = alt.Chart(df).encode(x=x, x2="end:T", y=y)
    else:
        # Sub-rows only where detections overlap on the same tractor (greedy interval packing), so concurrent
        # causes stay visible without thinning every bar to one row per cause in the window.
        df = df.sort_values(["tractor", "start"]).copy()
        rows_ = []
        for _, g in df.groupby("tractor", sort=False):
            ends = []
            for r in g.itertuples():
                j = next((n for n, e in enumerate(ends) if e <= r.start), len(ends))
                ends[j:j + 1] = [r.end]
                rows_.append(j)
        df["row"] = rows_
        nrow = int(df.row.max()) + 1
        base = alt.Chart(df).encode(x=x, x2="end:T", y=y,
                                    yOffset=alt.YOffset("row:O", scale=alt.Scale(domain=list(range(nrow)))))
    legend = None if compact else alt.Legend(
        orient="top", direction="horizontal", labelFont=MONO, symbolType="square", title=None,
        labelExpr=" : ".join(f"datum.label == '{k}' ? '{v['code']} {v['short'].lower()}'" for k, v in CAUSES.items())
        + " : datum.label")
    layers.append(base.mark_bar(cornerRadius=2, cursor="pointer", **({"height": 9} if compact else {})).encode(
        color=alt.Color("cause:N", scale=alt.Scale(domain=present, range=[CAUSES[c]["color"] for c in present]),
                        legend=legend),
        opacity=alt.condition(alt.datum.sel == "selected", alt.value(1.0), alt.value(0.6 if sel_idx is not None else 0.9)),
        stroke=alt.condition(alt.datum.sel == "selected", alt.value(INK), alt.value(None)),
        strokeWidth=alt.condition(alt.datum.sel == "selected", alt.value(2), alt.value(0)),
        tooltip=[alt.Tooltip("label:N", title="detection"), alt.Tooltip("tractor:N")]).add_params(pick))
    layers.append(base.mark_text(align="left", dx=3, fontSize=10, font=MONO, color="#FFFFFF", fontWeight="bold")
                  .encode(x="start:T", text="text:N"))
    return styled(alt.layer(*layers).properties(height=44 if compact else 118, width="container"))


def compare_chart(ps, metric, nd, affected, focus):
    """Dot/slope chart: per-tractor value before, during, after (evidence._stats per tractor)."""
    rows = []
    for t in TRACTORS:
        for ph in ("before", "during", "after"):
            s, n = ps[(ph, t)]
            if s is not None:
                rows.append({"tractor": t, "phase": ph.capitalize(), "v": s[metric], "n": n,
                             "role": "affected" if t in affected else "other"})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    order = ["Before", "During", "After"]
    enc = dict(x=alt.X("phase:N", sort=order, scale=alt.Scale(domain=order), title=None,
                       axis=alt.Axis(labelAngle=0, labelFontSize=13, labelColor=INK)),
               y=alt.Y("v:Q", title=None, scale=alt.Scale(zero=metric in ("fixed", "link", "nofix")),
                       axis=alt.Axis(labelFont=MONO, format=".4~r")),
               color=alt.Color("tractor:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_COLORS.values())),
                               legend=alt.Legend(orient="right", title=None)),
               detail="tractor:N")
    op = alt.value(1) if focus is None else alt.condition(alt.datum.tractor == focus, alt.value(1), alt.value(0.25))
    tips = [alt.Tooltip("tractor:N"), alt.Tooltip("phase:N"), alt.Tooltip("v:Q", title="value", format=f".{nd}f"),
            alt.Tooltip("n:Q", title="samples")]
    lines = alt.Chart(df).mark_line(strokeWidth=2).encode(
        **enc, opacity=op, strokeDash=alt.StrokeDash("role:N", scale=alt.Scale(domain=["affected", "other"],
                                                                                 range=[[1, 0], [5, 3]]), legend=None))
    pts = alt.Chart(df).mark_point(size=90, filled=True).encode(
        **enc, opacity=op, shape=alt.Shape("tractor:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_SHAPES.values())),
                                           legend=None), tooltip=tips)
    return styled(alt.layer(lines, pts).properties(height=300, width="container"))


def position_chart(p, origin, idx, cursor, focus, size=420):
    """Reported GNSS position: equal-scaled local metres, gap-aware trails, selected-time markers."""
    span = max(p.east_m.max() - p.east_m.min(), p.north_m.max() - p.north_m.min(), 10) * 1.08 / 2
    ce, cn = (p.east_m.max() + p.east_m.min()) / 2, (p.north_m.max() + p.north_m.min()) / 2
    xs = alt.Scale(domain=[ce - span, ce + span], nice=False)
    ys = alt.Scale(domain=[cn - span, cn + span], nice=False)
    col = alt.Color("tractor_id:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_COLORS.values())), legend=None)
    enc = dict(x=alt.X("east_m:Q", scale=xs, title="East of interval mean (m)", axis=alt.Axis(labelFont=MONO)),
               y=alt.Y("north_m:Q", scale=ys, title="North of interval mean (m)", axis=alt.Axis(labelFont=MONO)),
               color=col, detail="seg:N", order="ts:T")

    def fo(hi, lo):
        return alt.value(hi) if focus is None else alt.condition(alt.datum.tractor_id == focus, alt.value(hi), alt.value(lo))
    layers = [alt.Chart(p).mark_line(strokeWidth=1).encode(**enc, opacity=fo(0.25, 0.08))]
    past = p[p.ts <= cursor]
    if len(past):
        layers.append(alt.Chart(past).mark_line(strokeWidth=1.8).encode(**enc, opacity=fo(0.9, 0.18)))
    marks = []
    for t in TRACTORS:
        try:
            r = idx.loc[(t, cursor)]
        except KeyError:
            continue
        e, n = to_local(r.lat, r.lon, *origin)
        marks.append({"tractor_id": t, "east_m": e, "north_m": n, "time_utc": f"{cursor:%H:%M:%S} UTC (1 Hz sample)"})
    if marks:
        m = pd.DataFrame(marks)
        layers.append(alt.Chart(m).mark_point(size=130, filled=True, stroke="#FFFFFF", strokeWidth=1.5).encode(
            x=alt.X("east_m:Q", scale=xs), y=alt.Y("north_m:Q", scale=ys), color=col, opacity=fo(1, 0.35),
            shape=alt.Shape("tractor_id:N", scale=alt.Scale(domain=TRACTORS, range=list(TRACTOR_SHAPES.values())),
                            legend=None),
            tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="time"), alt.Tooltip("east_m:Q", format=".1f"),
                     alt.Tooltip("north_m:Q", format=".1f")]))
        layers.append(alt.Chart(m).mark_text(dx=10, dy=-10, font=MONO, fontWeight="bold", fontSize=12).encode(
            x=alt.X("east_m:Q", scale=xs), y=alt.Y("north_m:Q", scale=ys), text="tractor_id:N", color=col))
    # Square plot area with equal spans on both axes → 1 m east = 1 m north on screen.
    return styled(alt.layer(*layers).properties(width=size, height=size)), len(marks)


# ---------------------------------------------------------------- HTML tables / inspector
def stats_table(cols, rows, focus_col=None):
    head = "".join(f'<th class="{"focus" if n == focus_col else ""}">{html.escape(n)}</th>' for n in cols)
    body = ""
    for label, key, nd in rows:
        body += f"<tr><td>{label}</td>"
        for name, (s, n) in cols.items():
            fc = " focus" if name == focus_col else ""
            if s is None:
                body += f'<td class="na{fc}">unavailable</td>'
            elif key == "n":
                body += f'<td class="v{fc}">{n:,}</td>'
            else:
                body += f'<td class="v{fc}">{s[key]:.{nd}f}</td>'
        body += "</tr>"
    return f'<table class="fs-tbl"><tr><th></th>{head}</tr>{body}</table>'


STAT_ROWS = [("Samples (1 Hz)", "n", 0), ("Mean C/N0 dB-Hz · mean", "cn0", 1), ("Min C/N0 dB-Hz · minimum", "mincn0", 1),
             ("Satellites · median", "sats", 0), ("Cross-track error m · median", "xte_med", 2),
             ("Cross-track error m · maximum", "xte_max", 2), ("RTK_FIXED · % of samples", "fixed", 0),
             ("NO_FIX · % of samples", "nofix", 0), ("RTK link up · % of samples", "link", 0)]


def samples_at(idx, cursor):
    out = {}
    for t in TRACTORS:
        try:
            out[t] = idx.loc[(t, cursor)]
        except KeyError:
            out[t] = None
    return out


INSPECT = {   # fields shown inline per lab view (raw 1 Hz sample values)
    "guidance": [("XTE", lambda r: f"{r.cross_track_error_m:+.3f} m")],
    "receiver": [("C/N0 mean", lambda r: f"{r.mean_cn0_dbhz:.1f}"), ("· min", lambda r: f"{r.min_cn0_dbhz:.1f} dB-Hz"),
                 ("· satellites", lambda r: f"{r.num_sats:d}")],
    "link": [("RTK link", lambda r: "up" if r.base_link_ok else "down"), ("· fix", lambda r: str(r.fix_state))],
}


def inspector_html(samples, view, cursor, focus, d):
    if view == "space":
        parts = []
        for key, label in (("s4", "S4"), ("kp", "Kp")):
            v = in_force(d[key], key, cursor)
            parts.append(f"{label} <b>{v[0]:g}</b> <span class='fs-note'>published {v[1]:%H:%M}, {age(cursor - v[1])} "
                         "earlier</span>" if v else f"{label} <span class='na'>unavailable</span>")
        return f'<div class="fs-insp">{" &nbsp; ".join(parts)}</div>'
    fields = INSPECT.get(view, [("speed", lambda r: f"{r.speed_mps:.1f} m/s"), ("XTE", lambda r: f"{r.cross_track_error_m:+.3f} m")])
    items = []
    for t in TRACTORS:
        r = samples[t]
        style = "" if (focus is None or focus == t) else "opacity:.45"
        lab = f'<span class="fs-tr" style="border-left-color:{TRACTOR_COLORS[t]}">{t}</span>'
        if r is None:
            items.append(f'<span style="{style}">{lab}<span class="na">no sample at this second</span></span>')
        else:
            vals = " ".join(f"{n} <b>{fn(r)}</b>" for n, fn in fields)
            items.append(f'<span style="{style}">{lab}{vals}</span>')
    return f'<div class="fs-insp">{"".join(items)}</div>'


def readout_table(samples, flags, dets, cursor, focus, d):
    minute = cursor.floor("min")
    fl = flags[flags.ts == minute].set_index("tractor_id")
    fields = [
        ("Sample timestamp", lambda r, t: f"{cursor:%H:%M:%S}"),
        ("Speed m/s", lambda r, t: f"{r.speed_mps:.1f}"),
        (f"Working (minute {minute:%H:%M})", lambda r, t: ("yes" if fl.loc[t, "working"] else "no") if t in fl.index else "n/a"),
        ("Cross-track error m", lambda r, t: f"{r.cross_track_error_m:+.3f}"),
        ("Mean C/N0 dB-Hz", lambda r, t: f"{r.mean_cn0_dbhz:.1f}"),
        ("Min C/N0 dB-Hz", lambda r, t: f"{r.min_cn0_dbhz:.1f}"),
        ("Satellites", lambda r, t: f"{r.num_sats:d}"),
        ("Fix state", lambda r, t: html.escape(str(r.fix_state))),
        ("RTK link", lambda r, t: "up" if r.base_link_ok else "down"),
        ("Reported lat, lon", lambda r, t: f"{r.lat:.6f}, {r.lon:.6f}"),
    ]
    head = "".join(f'<th class="{"focus" if focus == t else ""}" style="color:{TRACTOR_COLORS[t]}">{t}</th>' for t in TRACTORS)
    body = ""
    for name, fn in fields:
        body += f"<tr><td>{name}</td>"
        for t in TRACTORS:
            r, fc = samples[t], (" focus" if focus == t else "")
            body += f'<td class="na{fc}">no sample</td>' if r is None else f'<td class="v{fc}">{fn(r, t)}</td>'
        body += "</tr>"
    body += "<tr><td>Within detection (episode-level)</td>"
    for t in TRACTORS:
        hits = [f"{CAUSES[x['class']]['code']} {hm(x['start'])}" for x in dets
                if t in x["tractors"] and ts_(x["start"]) <= cursor < ts_(x["end"])]
        body += f'<td class="v{" focus" if focus == t else ""}">{", ".join(hits) or "—"}</td>'
    body += "</tr>"
    sda = []
    for key, label in (("s4", "S4"), ("kp", "Kp")):
        v = in_force(d[key], key, cursor)
        sda.append(f"{label} {v[0]:g} (published {v[1]:%H:%M} UTC, {age(cursor - v[1])} earlier)" if v else f"{label} unavailable")
    return (f'<table class="fs-tbl"><tr><th></th>{head}</tr>{body}</table>'
            f'<div class="fs-note" style="margin-top:6px">Regional values in force: {" · ".join(sda)}.</div>')


# ---------------------------------------------------------------- state transitions (callbacks)
def k(w, name):
    return f"{name}-{w}"


def open_report(w, did):
    st.session_state[k(w, "sel")] = did
    st.session_state[k(w, "view")] = "report"
    st.session_state["_scroll_top"] = True


def go_view(w, view):
    st.session_state[k(w, "view")] = view
    st.session_state["_scroll_top"] = True


def step_incident(w, ids, delta):
    cur = st.session_state.get(k(w, "sel"))
    i = ids.index(cur) if cur in ids else 0
    st.session_state[k(w, "sel")] = ids[min(len(ids) - 1, max(0, i + delta))]   # stops at the ends
    st.session_state[k(w, "view")] = "report"
    st.session_state["_scroll_top"] = True


def on_timeline(w, chart_key, ids):
    pts = ((st.session_state.get(chart_key) or {}).get("selection") or {}).get("pick") or []
    if pts and "det" in pts[0] and 0 <= int(pts[0]["det"]) < len(ids):
        open_report(w, ids[int(pts[0]["det"])])


def nudge(key, delta, lo, hi):
    st.session_state[key] = min(hi, max(lo, st.session_state[key] + delta))


def jump(key, t):
    st.session_state[key] = t


# ---------------------------------------------------------------- shell
with st.container(key="shell"):
    c1, c2, c3 = st.columns([5.2, 3.2, 1], vertical_alignment="center")
    with c3:
        with st.popover("Settings", width="stretch"):
            data_dir = st.text_input("Data folder", value=str(ROOT / "data"),
                                     help="Folder produced by scripts\\get_data.py (contains farm\\, sda\\, labels\\).")
            st.caption("Chart aggregation and context are set in the evidence lab (chart options).")
    with c2:
        window_name = st.segmented_control("Analysis window", list(WINDOWS), default="Evaluation", required=True,
                                           key="window", label_visibility="collapsed")
        a_w, b_w = WINDOWS[window_name]
        H(f'<div class="fs-dates">{a_w:%Y-%m-%d %H:%M} → {b_w:%Y-%m-%d %H:%M} UTC (end exclusive)</div>')
    dev = window_name == "Development"
    with c1:
        state = ("Development window · labeled · scores are in-sample" if dev
                 else "Evaluation window · unlabeled · accuracy unknown (not measured)")
        H('<div class="fs-brand">FIELD SIGNAL<span>Straight Rows · GNSS guidance incident report · '
          f'retrospective analysis of simulated data</span></div><div class="fs-state">{state}</div>')

w = WCODE[window_name]
missing, sig = data_signature(data_dir)
if missing:
    st.error("Challenge data was not found in the data folder (Settings). Missing: " + ", ".join(missing))
    st.markdown("Fetch it from the release package (repository root):")
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
except Exception as exc:  # malformed inputs: a readable message instead of a stack trace
    st.error(f"The data could not be loaded or analysed ({type(exc).__name__}: {exc}). "
             "Check the data folder in Settings; the files must match the official release.")
    st.stop()

ids = [det_id(x) for x in dets]
# Coherent state: validate the selection against this window's detections; fall back safely.
if st.session_state.get(k(w, "sel")) not in ids:
    st.session_state[k(w, "sel")] = ids[0] if ids else None
view = st.session_state.setdefault(k(w, "view"), "fleet")
if view == "report" and not ids:
    view = st.session_state[k(w, "view")] = "fleet"
sel_id = st.session_state[k(w, "sel")]
sel_idx = ids.index(sel_id) if sel_id in ids else None


# ---------------------------------------------------------------- shared details (methodology, provenance)
def methodology_md():
    return f"""
- **Detections come from the pipeline** (`src/straightrows`): per-minute features → cause-agnostic flags →
  one rule per cause → interval assembly → evidence. The dashboard does not detect anything itself.
- **Causes are pipeline attributions ("suspected")**, not confirmed truth. Evaluation detections are unverified
  predictions; development labels exist only for the labeled window.
- **Cross-track error** is the simulation's separate guidance-monitor channel (metres, signed). It is not
  computed from position.
- **Reported GNSS position is not ground truth** and can be displaced during spoofing. Detection never uses it.
- **Working state** = 1-minute mean speed > {cfg.moving_mps:g} m/s (speed is only 0 or 4.5 m/s, so ≥ 14 moving
  seconds). Space weather, jamming, spoofing and equipment fault require a working tractor.
- **Gap bridging:** same-tractor, same-cause gaps ≤ {cfg.bridge_gap_s:g} s are joined before the
  {cfg.min_duration_s:g} s minimum-duration filter; same-cause detections on different tractors that start within
  {cfg.merge_gap_s:g} s of a previous end are merged (this can overstate the affected set).
- **Multipath detection is off in this dashboard and submission.** An opt-in detector exists for analysis,
  but it produces hundreds of short reports and is not used here.
- **Confidence is a fixed heuristic value ({CONFIDENCE})** for every detection. It is not calibrated and is not
  a probability.
- **Development results are in-sample:** parameters were chosen on the same 12 labeled episodes. The evaluation
  window has no public labels; its accuracy is unknown.
- **Analysis is retrospective:** each detection is assembled after the whole window is available (minute runs,
  gap bridging, merging). Onset credit compares a detection's start with the labeled start; it is not real-time
  alerting latency.
- **SDA and RFI timestamp meanings are not documented** (interval start or end; RFI observation or report time).
  The pipeline uses the latest value at or before each minute. RFI reports are cited as evidence only.
- **Known gaps:** jamming or spoofing during a storm is missed; elevated Kp alone does not prove space weather.
"""


def display_md():
    return """
- **Evidence-lab views and default view per cause** (display only): spoofing → Guidance; jamming → Receiver
  health; space weather → Space / RF; equipment fault → Receiver health (antenna dropouts, min C/N0 first) or
  Link & fix (link loss), chosen with the same test the evidence text uses. Every channel stays under *All signals*.
- **Display bins:** cross-track error bin mean (signed), mean C/N0 bin mean, min C/N0 bin minimum, satellites bin
  median, RTK link and RTK_FIXED % of samples; S4 and Kp drawn as the latest published value (step). At 1 min
  these equal the pipeline's features. No smoothing; lines break at missing bins and never join tractors.
- **Axes:** mean C/N0 axes span at least 20–50 dB-Hz and min C/N0 at least 0–50 dB-Hz (wider if the data are),
  so small changes are not magnified; satellites, link and fix start at zero; cross-track error keeps its sign.
  Dotted amber lines are the pipeline's rule levels (C/N0 low, dropout, cross-track error high, link low, S4).
  The rules apply them to 1-minute values, so a finer display bin can cross a line without the rule firing.
- **Rule-minute counts** ("rule true in k of n minutes") are the pipeline's own per-minute results
  (`attribution.tests` on `candidates.flag`), counted over the detection interval per tractor.
- **Replay inspector:** values are the raw 1 Hz sample whose timestamp equals the cursor second exactly
  (tolerance 0 s; the telemetry is complete 1 Hz). Otherwise *no sample* is shown, never a neighbouring value.
  Working state is the pipeline's flag for the containing minute; S4/Kp are the values in force (as-of rule) with
  their publication time. "Within detection" is episode-level membership, not a fresh diagnosis.
- **Before · during · after:** `evidence._stats` over Before = 30 min before onset, working samples
  (speed > 0) — the exported evidence baseline; During = the detection interval, all samples — the exported
  evidence statistics; After = 30 min after the end, working samples — display-only mirror of the baseline.
  The table pools the affected tractors exactly as the evidence does; the chart applies the same function per
  tractor. Empty windows show *unavailable*. Differences are descriptive, not proof of cause.
- **Reported position:** 10 s means of reported lat/lon in metres from the interval's mean position
  (flat-earth: 1° lat = 111,320 m, 1° lon = 111,320 m × cos(mean latitude); adequate over ~1 km); equal scale;
  trails break at missing 10 s bins; no map tiles, field boundaries, guidance lines or true positions.
- **Colours:** tractors T1 blue, T2 orange, T3 green (plus labels and marker shapes ●■▲); causes use a separate
  hue set and always carry a text code (SW, JAM, SPF, EF). Tractors outside the detection are dashed; tractor
  focus dims, never hides.
"""


def provenance_df():
    return pd.DataFrame(
        [("Window", window_name), ("Window UTC", f"{fmt(a_w)} → {fmt(b_w)} (end exclusive)"), ("Data folder", data_dir),
         ("Git commit", git_commit()), ("Detections", str(len(dets)))]
        + [(f"Config.{kk}", str(v)) for kk, v in asdict(cfg).items()], columns=["Item", "Value"])


# ---------------------------------------------------------------- A. fleet overview
def render_fleet():
    H(f'<div class="fs-eyebrow">Fleet overview · {window_name.lower()} window</div>'
      f'<div class="fs-h1">{len(dets)} pipeline detection{"s" if len(dets) != 1 else ""}</div>'
      '<div class="fs-meta">Pipeline attributions, not verified events. Listed in time order; no ranking. '
      'Click a bar or open a report from the list.</div>')
    if not dets:
        st.info("The pipeline produced no detections in this window. You can still explore any interval.")
    else:
        with st.container(key="surface-timeline"):
            ck = f"tl-{w}-{sel_id}"
            st.vega_lite_chart(spec=timeline_spec(data_dir, sig, window_name, cfg_items, sel_idx, False), key=ck,
                               selection_mode="pick", theme=None, on_select=lambda: on_timeline(w, ck, ids),
                               width="stretch")
        with st.container(key="surface-list", gap=None):
            for i, x in enumerate(dets):
                on = ids[i] == sel_id
                with st.container(key=f"row-{'on' if on else 'off'}-{w}-{i}"):
                    r1, r2, r3, r4, r5 = st.columns([2.8, 1.2, 2.0, 2.4, 1.2], vertical_alignment="center")
                    r1.markdown(f'{code_chip(x["class"])}<span class="fs-row-cause">Suspected '
                                f'{CAUSES[x["class"]]["short"].lower()}</span>'
                                + ('<span class="fs-sel">● last opened</span>' if on else ""), unsafe_allow_html=True)
                    r2.markdown(tractor_chips(x["tractors"]), unsafe_allow_html=True)
                    r3.markdown(f'<span class="fs-mono" style="white-space:nowrap">{interval_text(x, short=True)}</span>'
                                f'<span class="fs-note"> · {mins(x)} min</span>', unsafe_allow_html=True)
                    r4.markdown(f'<span class="fs-note">{ACTION_SHORT[x["action"]]}</span>', unsafe_allow_html=True)
                    r5.button("Open report", key=f"open-{w}-{i}", type="primary" if on else "secondary",
                              on_click=open_report, args=(w, ids[i]), width="stretch")
    b1, b2 = st.columns([1, 3], vertical_alignment="center")
    b1.button("Explore a custom interval", on_click=go_view, args=(w, "custom"), width="stretch")
    if dets:
        with st.expander(f"Detection register ({len(dets)}) — exact exported fields"):
            st.dataframe(pd.DataFrame([{
                "#": i + 1, "Start (UTC)": x["start"], "End (UTC)": x["end"], "Minutes": mins(x),
                "Tractors": ", ".join(x["tractors"]), "class": x["class"], "action": x["action"],
                "confidence (fixed)": x["confidence"]} for i, x in enumerate(dets)]), hide_index=True, width="stretch")
    if dev:
        with st.expander("Development labels — ground truth for this window, not model output"):
            labels = d.get("labels")
            if labels is None:
                st.info("No labels file in this data folder.")
            else:
                lab = labels.sort_values("start")
                st.dataframe(pd.DataFrame({
                    "Label": lab.id, "Start (UTC)": lab.start.map(fmt), "End (UTC)": lab.end.map(fmt),
                    "Tractors": lab.tractors.map(", ".join), "Labeled cause": lab["class"],
                    "Labeled action": lab.recommended_action}), hide_index=True, width="stretch")
                if st.button("Score detections against these labels (official scorer, in-sample)"):
                    import score_submission
                    key = {"episodes": [{**r, "start": r["start"].isoformat(), "end": r["end"].isoformat()}
                                        for r in labels.to_dict("records")]}
                    res = score_submission.score({"detections": dets}, key)
                    H(stats_table({"In-sample result": ({"a": res["diagnostic_score"], "b": res["macro_f1"],
                                                         "c": res["mean_timing_credit"],
                                                         "e": len(res["false_positives"])}, 0)},
                                  [("Diagnostic score (of 40)", "a", 2), ("Macro-F1", "b", 3),
                                   ("Onset credit", "c", 3), ("False positives", "e", 0)]))
                    st.caption("In-sample: parameters were chosen on these same labels. Not evaluation performance. "
                               "Onset credit is retrospective start-time agreement, not real-time alerting latency.")
    with st.expander("About this analysis — methodology, display definitions, provenance"):
        t1, t2, t3 = st.tabs(["Methodology and limitations", "Display definitions", "Provenance"])
        t1.markdown(methodology_md())
        t2.markdown(display_md())
        t3.dataframe(provenance_df(), hide_index=True, width="stretch")


# ---------------------------------------------------------------- C. evidence lab (shared by report and custom)
def ef_view(sa, su):
    """Equipment fault: default view from the sub-rule the evidence text names (same test as evidence.py)."""
    link = sa["link"] < 100 * cfg.link_low_frac or bool(su and sa["link"] < su["link"])
    return "link" if (link and not sa["mincn0"] < cfg.dropout_dbhz) else "receiver"


def render_lab(x, a, b, s0, e0, affected, ps, lab_key, scrub_key, default_t, rule, rule_note):
    """One question at a time: view selector, prominent chart, replay, inspector, supported observation."""
    focus_v = None
    views = [v for v in VIEWS if not (x is None and v == "compare")] + (["tractors"] if x is None else [])
    labels = {**{v: VIEWS[v]["label"] for v in VIEWS}, "tractors": "Compare tractors"}
    cur_view = st.segmented_control("Evidence view", views, key=lab_key, required=True,
                                    format_func=lambda v: labels[v], label_visibility="collapsed")
    q = VIEWS[cur_view]["q"] if cur_view in VIEWS else "How did the three tractors compare over this interval?"
    tq, tc = st.columns([1.1, 1], vertical_alignment="center")
    tq.markdown(f'<div class="fs-q">{q}</div>', unsafe_allow_html=True)
    with tc.container(horizontal=True, vertical_alignment="center", gap="small", horizontal_alignment="right"):
        focus_v = st.segmented_control("Tractor focus", ["All", *TRACTORS], default="All", required=True,
                                       key=k(w, "focus"), format_func=lambda v: "All tractors" if v == "All" else v,
                                       label_visibility="collapsed")
        chart_opts = st.popover("Chart options")
    focus = None if focus_v in (None, "All") else focus_v
    with chart_opts:
        st.slider("Context before/after the detection (min)", 0, 180, step=5, key=k(w, "pad"),
                  disabled=x is None)
        st.radio("Display aggregation", list(AGGREGATIONS), key=k(w, "agg"),
                 help="Charts only. Detection always uses the pipeline's 1-minute features.")


    # ---- replay state (exact seconds inside the charted interval)
    lo = a.to_pydatetime().replace(tzinfo=None)
    hi = (b - pd.Timedelta(seconds=1)).to_pydatetime().replace(tzinfo=None)
    if scrub_key not in st.session_state or not (lo <= st.session_state[scrub_key] <= hi):
        st.session_state[scrub_key] = default_t.to_pydatetime().replace(tzinfo=None)
    cursor = pd.Timestamp(st.session_state[scrub_key], tz="UTC")
    samples = samples_at(idx, cursor)
    timed = cur_view in ("guidance", "receiver", "link", "space", "all", "position")

    bins = display_bins(data_dir, sig, a, b, rule) if cur_view in ("guidance", "receiver", "link", "all") else None
    ov = overlays(a, b, s0, e0, cursor)
    if timed and cur_view != "position":
        legend = "".join(f'<span><i style="border-color:{TRACTOR_COLORS[t]}"></i>{t}</span>' for t in TRACTORS)
        if affected:
            legend += (f'<span><i style="border-color:{INK2};border-top-style:dashed"></i>not in this detection</span>'
                       f'<span><i style="border-color:{BLUE};border-top-width:8px;opacity:.25"></i>detection interval</span>')
        legend += (f'<span><i style="border-color:{AMBER};border-top-style:dotted"></i>pipeline rule level</span>'
                   f'<span><i style="border-color:{INK}"></i>replay cursor</span>'
                   f'<span class="fs-mono">{rule} display bins{rule_note}</span>')
        H(f'<div class="fs-legend">{legend}</div>')
        strip = context_strip(dets, sel_idx if x is not None else None, flags[(flags.ts >= a) & (flags.ts < b)], a, b, cursor)
        if strip is not None:
            show(strip, width="stretch")

    if cur_view in ("guidance", "receiver", "link"):
        if bins is None or bins.empty:
            st.info("No telemetry in this interval.")
        else:
            chs = VIEWS[cur_view]["ch"]
            if x is not None and x["class"] == "EQUIPMENT_FAULT" and cur_view == "receiver":
                chs = ["min_cn0", "cn0", "sats"]   # dropout rule uses min C/N0: make it the primary chart
            for j, ch in enumerate(chs):
                show(line_chart(bins, ch, a, b, ov, affected, focus, 300 if j == 0 else 120,
                                labels=(j == len(chs) - 1)))
    elif cur_view == "space":
        rfi = d["rfi"][(d["rfi"].ts >= a) & (d["rfi"].ts < b)]
        c = step_chart(d, "s4", a, b, ov, 260, labels=False, rfi=rfi)
        if c is not None:
            show(c, width="stretch")
        c = step_chart(d, "kp", a, b, ov, 110, labels=True)
        if c is not None:
            show(c, width="stretch")
        st.caption(f"Amber dotted line: S4 = {cfg.s4_storm} (the pipeline's scintillation level). Coral ticks: RFI "
                   "report timestamps (observation vs. report time is not documented).")
    elif cur_view == "all":
        if bins is None or bins.empty:
            st.info("No telemetry in this interval.")
        else:
            for ch in ["xte", "cn0", "min_cn0", "sats", "link", "fixed"]:
                show(line_chart(bins, ch, a, b, ov, affected, focus, 105), width="stretch")
            for ch in ["s4", "kp"]:
                c = step_chart(d, ch, a, b, ov, 90)
                if c is not None:
                    show(c, width="stretch")
    elif cur_view == "compare":
        metric = st.segmented_control("Measure", ["cn0", "mincn0", "sats", "xte_med", "xte_max", "fixed", "link"],
                                      default=PRIMARY_METRIC.get(x["class"], "cn0"), required=True,
                                      key=f"{lab_key}-metric", label_visibility="collapsed",
                                      format_func=lambda m: METRIC_LABEL[m][0])
        ch = compare_chart(ps, metric, METRIC_LABEL[metric][1], affected, focus)
        if ch is None:
            st.info("No samples in any of the three windows.")
        else:
            show(ch, width="stretch")
        cols = {f"Before {hm(s0 - PRE)}–{hm(s0)} · working": ps[("before", "affected")],
                f"During {hm(s0)}–{hm(e0)} · all samples": ps[("during", "affected")],
                f"After {hm(e0)}–{hm(e0 + AFTER)} · working": ps[("after", "affected")]}
        H(f'<div class="fs-note" style="margin-top:4px"><b>{" ".join(affected)} pooled</b> — the exported evidence '
          'definitions (Before, During); After is a display-only mirror of the baseline.</div>')
        H(stats_table(cols, STAT_ROWS))
        overlap = [f"{CAUSES[o['class']]['code']} {' '.join(o['tractors'])} {hm(o['start'])}–{hm(o['end'])}"
                   for o in dets if det_id(o) != det_id(x) and set(o["tractors"]) & set(affected)
                   and ts_(o["start"]) < e0 + AFTER and ts_(o["end"]) > s0 - PRE]
        if overlap:
            H(f'<div class="fs-warn" style="margin-top:8px">Other detections on these tractors overlap the '
              f'before/after windows: {"; ".join(overlap)}. Their effects are included in those statistics.</div>')
        st.caption("Chart: the same statistic per tractor (solid = in this detection, dashed = not). Descriptive "
                   "differences do not by themselves prove the cause.")
    elif cur_view == "tractors":
        tele = d["tele"]
        seg = tele[(tele.ts >= a) & (tele.ts < b)]
        cols = {t: (_stats(seg[seg.tractor_id == t]), int((seg.tractor_id == t).sum())) for t in TRACTORS}
        H(stats_table(cols, STAT_ROWS, focus_col=focus))
        st.caption("evidence._stats on raw 1 Hz telemetry over the whole interval (all samples).")
    elif cur_view == "position":
        p, origin = position_bins(data_dir, sig, a, b)
        if p.empty:
            st.info("No telemetry in this interval.")
        else:
            H('<div class="fs-warn">Reported GNSS position — may be misleading during spoofing. Retrospective '
              'playback of reported positions, not verified motion.</div>')
            pc1, pc2 = st.columns([1.35, 1])
            with pc1:
                chart, n_marks = position_chart(p, origin, idx, cursor, focus)
                show(chart, width="content")
            pc2.markdown(
                f"- Equal scale: 1 m east = 1 m north. Metres from the interval's mean reported position "
                f"(flat-earth, cos {origin[0]:.4f}°).\n- Faint trail = whole interval; bright = up to the cursor "
                f"(10 s means, broken at gaps).\n- Markers = 1 Hz samples at {cursor:%H:%M:%S} UTC "
                f"({n_marks} of 3 present).\n- No field boundary, intended row or true location is drawn; the "
                "dataset provides none. Cross-track error is a separate channel and is not derived from these "
                "positions.")

    # ---- replay: one compact scrubber, exact timestamp, inspector on the current view
    if timed:
        st.slider("Replay time (UTC)", min_value=lo, max_value=hi, step=timedelta(seconds=1), format="HH:mm:ss",
                  key=scrub_key, label_visibility="collapsed")
        rc = st.container(horizontal=True, vertical_alignment="center", gap="small")
        rc.markdown(f'<div class="fs-note">Cursor <b class="fs-mono" style="color:{INK}">{cursor:%Y-%m-%d %H:%M:%S} '
                    'UTC</b> · raw 1 Hz samples (charts show display bins)</div>', unsafe_allow_html=True,
                    width="content")
        rc.button("−10 s", key=f"{scrub_key}-b", on_click=nudge, args=(scrub_key, timedelta(seconds=-10), lo, hi))
        rc.button("+10 s", key=f"{scrub_key}-f", on_click=nudge, args=(scrub_key, timedelta(seconds=10), lo, hi))
        with rc.popover("More"):
            st.button("−1 min", key=f"{scrub_key}-bm", on_click=nudge, args=(scrub_key, timedelta(minutes=-1), lo, hi))
            st.button("+1 min", key=f"{scrub_key}-fm", on_click=nudge, args=(scrub_key, timedelta(minutes=1), lo, hi))
            if s0 is not None:
                st.button("Go to onset", key=f"{scrub_key}-on", on_click=jump,
                          args=(scrub_key, s0.to_pydatetime().replace(tzinfo=None)))
                st.button("Go to end", key=f"{scrub_key}-en", on_click=jump,
                          args=(scrub_key, min(hi, (e0 - pd.Timedelta(seconds=1)).to_pydatetime().replace(tzinfo=None))))
        with rc.popover("Full readout"):
            H(f'<div class="fs-h2">Raw 1 Hz samples at <span class="fs-mono">{cursor:%Y-%m-%d %H:%M:%S}</span> UTC</div>')
            H(readout_table(samples, flags, dets, cursor, focus, d))
            st.caption("Exact-second match only (tolerance 0 s); nothing is interpolated or taken from a nearby second.")
        H(inspector_html(samples, cur_view, cursor, focus, d))
    return cur_view


PRIMARY_METRIC = {"SPOOFING": "xte_med", "JAMMING": "cn0", "SPACE_WEATHER": "cn0", "EQUIPMENT_FAULT": "mincn0"}
METRIC_LABEL = {"cn0": ("Mean C/N0 · mean", 1), "mincn0": ("Min C/N0 · minimum", 1), "sats": ("Satellites · median", 0),
                "xte_med": ("XTE · median", 2), "xte_max": ("XTE · maximum", 2), "fixed": ("RTK_FIXED %", 0),
                "link": ("RTK link up %", 0)}


def observation(view, x, s0, e0, affected, ps, ev):
    """A concise, measured observation for the current view (numbers from the pipeline's functions)."""
    sa, sp, su = ps[("during", "affected")][0], ps[("before", "affected")][0], ps[("during", "others")][0]
    un = [t for t in TRACTORS if t not in affected]
    who = " ".join(affected)
    ctx = lambda kk, nd, unit="": (f" (before: {sp[kk]:.{nd}f}{unit}" if sp else " (before: unavailable") + \
        (f"; {' '.join(un)}: {su[kk]:.{nd}f}{unit})" if su else ")")
    if view == "guidance":
        c = flag_counts(flags, "xte_high", s0, e0)
        return [f"Cross-track error on {who}: median <b class='fs-mono'>{sa['xte_med']:.2f} m</b>, max "
                f"<b class='fs-mono'>{sa['xte_max']:.2f} m</b>" + ctx("xte_med", 2, " m"),
                f"Minutes with 1-min mean error above {cfg.xte_high_m:g} m while working: {counts_text(c)} — "
                f"on {who_flagged(c)}."]
    if view == "receiver":
        c = flag_counts(flags, "cn0_low", s0, e0)
        dr = flag_counts(flags, "dropout", s0, e0)
        return [f"Mean C/N0 on {who}: <b class='fs-mono'>{sa['cn0']:.1f} dB-Hz</b>" + ctx("cn0", 1) +
                f"; min C/N0 <b class='fs-mono'>{sa['mincn0']:.1f}</b>.",
                f"Minutes with mean C/N0 below {cfg.cn0_low_dbhz:g} dB-Hz: {counts_text(c)} — on {who_flagged(c)}.",
                f"Antenna-dropout minutes (min C/N0 below {cfg.dropout_dbhz:g} with normal mean): {counts_text(dr)}."]
    if view == "link":
        c = flag_counts(flags, "link_low", s0, e0)
        return [f"RTK link up <b class='fs-mono'>{sa['link']:.0f}%</b>, RTK_FIXED "
                f"<b class='fs-mono'>{sa['fixed']:.0f}%</b> of samples on {who}" + ctx("fixed", 0, "% fixed"),
                f"Minutes with link up below {cfg.link_low_frac:.0%}: {counts_text(c)} — on {who_flagged(c)}."]
    if view == "space":
        out = [html.escape(e) for e in ev if e.startswith("Regional S4")]
        out += [html.escape(e) for e in ev if e.startswith("RFI:") or e.startswith("No RFI report")]
        out.append("Elevated Kp alone does not prove space weather; RFI reports are not used by the attribution rules.")
        return out
    return []


# ---------------------------------------------------------------- B. incident report
def render_report():
    x = dets[sel_idx]
    s0, e0 = ts_(x["start"]), ts_(x["end"])
    affected = x["tractors"]
    ev = x["evidence"]
    ps = phase_stats(data_dir, sig, s0, e0, tuple(affected))
    sa, su = ps[("during", "affected")][0], ps[("during", "others")][0]

    # ---- navigation bar: back, previous/next, slim clickable timeline (same selection state)
    nl, n5 = st.columns([4, 6], vertical_alignment="center")
    with nl.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.button("← Back to fleet", on_click=go_view, args=(w, "fleet"))
        st.button("‹ Previous", on_click=step_incident, args=(w, ids, -1), disabled=sel_idx == 0)
        st.markdown(f'<div class="fs-note" style="padding:0 4px"><b class="fs-mono">{sel_idx + 1}</b> of '
                    f'{len(ids)}</div>', unsafe_allow_html=True, width="content")
        st.button("Next ›", on_click=step_incident, args=(w, ids, 1), disabled=sel_idx == len(ids) - 1)
    with n5:
        mk = f"mini-{w}-{sel_id}"
        st.vega_lite_chart(spec=timeline_spec(data_dir, sig, window_name, cfg_items, sel_idx, True), key=mk,
                           selection_mode="pick", theme=None, on_select=lambda: on_timeline(w, mk, ids),
                           width="stretch")

    # ---- report heading
    counts = rule_counts(flags, x["class"], s0, e0, affected)
    rule_words = RULE_TEXT[x["class"]].format(cn0=cfg.cn0_low_dbhz, s4=cfg.s4_storm, xte=cfg.xte_high_m,
                                              link=cfg.link_low_frac, drop=cfg.dropout_dbhz)
    H(f'<div class="fs-eyebrow">Incident report · pipeline attribution, not confirmed</div>'
      f'<div class="fs-h1">{code_chip(x["class"])}{html.escape(title_of(x))}</div>'
      f'<div class="fs-meta"><span class="fs-mono">{interval_text(x)}</span> · {mins(x)} min · '
      f'{tractor_chips(affected)}</div>')

    rep, fin = st.columns([2.35, 1], gap="medium")
    with fin:
        with st.container(key="surface-finding"):
            H(f'<div class="fs-sec" style="margin-top:0"><h4>Recommended action</h4>'
              f'<div class="fs-action">{ACTION_TEXT[x["action"]]}</div>'
              f'<div class="fs-note" style="margin-top:4px">Applies to the whole episode; it is not re-decided at '
              f'each replay time.</div></div>')
            # Observed: measured, the same statistics as the exported evidence.
            obs = [f"Mean C/N0 <b class='fs-mono'>{sa['cn0']:.1f} dB-Hz</b>"
                   + (f", others <b class='fs-mono'>{su['cn0']:.1f}</b>" if su else ""),
                   f"Cross-track error median <b class='fs-mono'>{sa['xte_med']:.2f} m</b>, max "
                   f"<b class='fs-mono'>{sa['xte_max']:.2f} m</b>",
                   f"RTK link up <b class='fs-mono'>{sa['link']:.0f}%</b>, RTK_FIXED <b class='fs-mono'>{sa['fixed']:.0f}%</b>"]
            H(f'<div class="fs-sec"><h4>Observed on {" ".join(affected)} during the detection</h4>'
              f'<ul class="fs-list">{"".join(f"<li>{o}</li>" for o in obs)}</ul></div>')
            H(f'<div class="fs-sec"><h4>Pipeline interpretation</h4><div style="font-size:0.93rem">'
              f'Rule: {html.escape(rule_words)}. True in '
              + ", ".join(f"<b class='fs-mono'>{kk}/{n}</b> minutes on {t}" for t, (kk, n) in counts.items())
              + "." + (" Gaps of up to {:g} s are bridged.".format(cfg.bridge_gap_s) if any(kk < n for kk, n in counts.values()) else "")
              + "</div></div>")
            H(f'<div class="fs-sec"><h4>Main uncertainty</h4><div style="font-size:0.93rem">'
              f'{UNCERTAINTY[x["class"]]} Confidence <b class="fs-mono">{x["confidence"]}</b> is a fixed heuristic '
              'value, not a calibrated probability.</div></div>')
    with rep:
        with st.container(key="surface-lab"):
            default_view = (ef_view(sa, su) if x["class"] == "EQUIPMENT_FAULT" else DEFAULT_VIEW.get(x["class"], "receiver"))
            lab_key = f"lab-{w}-{sel_id}"
            if lab_key not in st.session_state:
                st.session_state[lab_key] = default_view
            st.session_state.setdefault(k(w, "pad"), 30)
            st.session_state.setdefault(k(w, "agg"), "1 min")
            pad = st.session_state[k(w, "pad")]
            a, b = max(a_w, s0 - pd.Timedelta(minutes=pad)), min(b_w, e0 + pd.Timedelta(minutes=pad))
            rule, note = AGGREGATIONS[st.session_state[k(w, "agg")]], ""
            if rule == "1s" and (b - a) > pd.Timedelta(minutes=30):
                rule, note = "10s", " (1 s limited to 30-min intervals)"
            cur_view = render_lab(x, a, b, s0, e0, affected, ps, lab_key, f"t-{w}-{sel_id}-{pad}", s0, rule, note)
            obs_lines = observation(cur_view, x, s0, e0, affected, ps, ev)
            if obs_lines:
                H('<div class="fs-obs"><div class="fs-eyebrow" style="margin-bottom:2px">Observation · measured over the '
                  'detection interval</div><ul class="fs-list">' + "".join(f"<li>{o}</li>" for o in obs_lines)
                  + "</ul></div>")

    # ---- details: one organised area
    with st.expander("Details — exported evidence, measurements, rules and confidence, methodology, provenance"):
        t1, t2, t3, t4, t5 = st.tabs(["Exported evidence", "Measurements", "Rules and confidence",
                                      "Methodology and limitations", "Provenance"])
        with t1:
            st.markdown("Exactly as written to `submission.json` for this detection:")
            st.markdown("\n".join(f"- {e}" for e in ev))
            st.markdown(f"Identifiers: class `{x['class']}` · action `{x['action']}` · start `{x['start']}` · end "
                        f"`{x['end']}` · tractors `{x['tractors']}` · confidence `{x['confidence']}`")
        with t2:
            un = [t for t in TRACTORS if t not in affected]
            H(stats_table({f"{' '.join(affected)} during": ps[("during", "affected")],
                           f"{' '.join(un) or 'others'} during": ps[("during", "others")],
                           f"{' '.join(affected)} prior 30 min (working)": ps[("before", "affected")]}, STAT_ROWS))
            st.caption("evidence._stats on raw 1 Hz telemetry — the function behind the exported evidence numbers.")
        with t3:
            st.markdown(f"- **Rule for {x['class']}** (per tractor-minute, `attribution.tests`): {rule_words}.\n"
                        f"- Thresholds: C/N0 low {cfg.cn0_low_dbhz:g} dB-Hz · cross-track error high {cfg.xte_high_m:g} m"
                        f" · link low {cfg.link_low_frac:.0%} · dropout {cfg.dropout_dbhz:g} dB-Hz · S4 {cfg.s4_storm}"
                        f" · working > {cfg.moving_mps:g} m/s.\n- Assembly: minimum {cfg.min_duration_s:g} s; same-tractor "
                        f"gaps ≤ {cfg.bridge_gap_s:g} s bridged; same-cause merge across tractors within "
                        f"{cfg.merge_gap_s:g} s.\n- **Confidence {x['confidence']}** is the same fixed value ({CONFIDENCE}) "
                        "for every detection; it is not calibrated and is not a probability.\n- Pipeline lines from the "
                        "evidence: " + " ".join(e for e in ev if e.startswith("Attributed") or e.startswith("Concurrent with")))
        t4.markdown(methodology_md() + "\n**Display definitions**\n" + display_md())
        t5.dataframe(provenance_df(), hide_index=True, width="stretch")


# ---------------------------------------------------------------- custom interval
def render_custom():
    n1, _ = st.columns([1.3, 8.7])
    n1.button("← Back to fleet", on_click=go_view, args=(w, "fleet"), width="stretch")
    hours = list(pd.date_range(a_w, b_w - pd.Timedelta(hours=1), freq="1h"))
    H('<div class="fs-eyebrow">Custom interval · no detection selected</div><div class="fs-h1">Explore an interval</div>')
    c1, c2, _ = st.columns([2, 2, 4])
    start = c1.selectbox("Start (UTC)", hours, index=min(12, len(hours) - 1), format_func=fmt, key=k(w, "cstart"))
    length = c2.slider("Length (min)", 15, 360, 120, step=15, key=k(w, "clen"))
    a, b = start, min(b_w, start + pd.Timedelta(minutes=length))
    st.session_state.setdefault(k(w, "pad"), 30)
    st.session_state.setdefault(k(w, "agg"), "1 min")
    rule, note = AGGREGATIONS[st.session_state[k(w, "agg")]], ""
    if rule == "1s" and (b - a) > pd.Timedelta(minutes=30):
        rule, note = "10s", " (1 s limited to 30-min intervals)"
    with st.container(key="surface-lab"):
        lab_key = f"lab-{w}-custom"
        st.session_state.setdefault(lab_key, "guidance")
        render_lab(None, a, b, None, None, [], None, lab_key, f"t-{w}-custom-{start:%Y%m%d%H}-{length}", a, rule, note)
        st.caption("Charts show inputs only; pipeline detections overlapping the interval appear in the top strip.")


if view == "report" and sel_idx is not None:
    render_report()
elif view == "custom":
    render_custom()
else:
    render_fleet()

# After a navigation click (open / back / previous / next / custom), start the new view at its top once.
# Emitted at the end of the page so it never shifts the layout above it; ordinary reruns (scrubbing,
# focus, view switches) keep the reader's scroll position.
if st.session_state.pop("_scroll_top", False):
    st.html("<script>(function(){var m=document.querySelector('[data-testid=\"stMain\"]');"
            "if(m){m.scrollTo({top:0});}window.scrollTo(0,0);})();</script>", unsafe_allow_javascript=True)
