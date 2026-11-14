"""FIELD SIGNAL — Straight Rows fleet guidance investigation (Streamlit dashboard).

Launch from the repository root (Windows CMD):
    .venv\\Scripts\\python.exe -m streamlit run src\\dashboard.py

Read-only view of the existing pipeline. Detections, evidence, actions and the working flag
all come from `straightrows` (io.load, pipeline.detect, export.to_submission, features +
candidates; measurement tables use evidence._stats, the function behind the exported evidence).
The dashboard only selects intervals, chooses which channels to draw, and aggregates raw
telemetry for display. Nothing here changes detection.
"""
import subprocess
import sys
from dataclasses import asdict
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

TRACTORS = ["T1", "T2", "T3"]
# Same tractor colours on every chart: categorical slots 1-3, T2/T3 darkened to >= 3.6:1 on the ivory paper.
TRACTOR_COLORS = ["#2a78d6", "#d0581f", "#128a5f"]
INK, INK_SOFT, RULE, PAPER = "#23221e", "#5b574d", "#cfc7b4", "#f5f1e6"
WINDOWS = {"Development (labeled)": DEV, "Evaluation (unlabeled)": EVAL}
REQUIRED = ["farm/tractor_telemetry.csv.gz", "sda/sgi_indices.json", "sda/scintillation_series.json",
            "sda/constellation_advisories.json", "sda/rfi_reports.json"]
AGGREGATIONS = {"1 min": "1min", "10 s": "10s", "1 s (raw, intervals up to 30 min)": "1s"}

# Cause identity: colour AND a short text code, so the ribbon never relies on colour alone.
CAUSES = {
    "SPACE_WEATHER": dict(code="SW", color="#6250d6", short="Space weather",
                          headline="Regional signal degradation, attributed to space weather"),
    "JAMMING": dict(code="JAM", color="#c23432", short="Jamming",
                    headline="Signal loss attributed to radio-frequency interference (jamming)"),
    "SPOOFING": dict(code="SPF", color="#b0446d", short="Spoofing",
                     headline="Guidance error without signal collapse, attributed to spoofing"),
    "EQUIPMENT_FAULT": dict(code="EF", color="#8a5e00", short="Equipment fault",
                            headline="Machine-specific equipment fault"),
    "MULTIPATH": dict(code="MP", color="#008300", short="Multipath", headline="Multipath (not detected)"),
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
    "xte": ("Cross-track error (m)", True),
    "cn0": ("Mean C/N0 (dB-Hz)", False),
    "min_cn0": ("Min C/N0 (dB-Hz)", False),
    "sats": ("Satellites (median)", False),
    "link": ("RTK link up (%)", True),
    "fixed": ("RTK_FIXED (% of bin)", True),
    "s4": ("Regional S4 (15 min)", True),
    "kp": ("Kp (3 h)", True),
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


def ef_channels(sa, su, cfg):
    """Equipment fault: show the signal(s) that the evidence text names (same test as evidence.py)."""
    link = sa["link"] < 100 * cfg.link_low_frac or bool(su and sa["link"] < su["link"])
    dropout = sa["mincn0"] < cfg.dropout_dbhz
    if link and dropout:
        return ["min_cn0", "link", "fixed"]
    if link:
        return ["link", "fixed", "min_cn0"]
    return ["min_cn0", "sats", "cn0"]   # antenna dropouts: min C/N0 and satellite dips; mean C/N0 for context
CHART_WIDTH = 400    # px plot area for the evidence column (axes add ~90 px; fits a 1366 px viewport)
ALL_WIDTH = 370      # plot area inside the "Inspect all signals" expander (extra padding)
RIBBON_WIDTH = 760   # px plot area for the fleet ribbon

st.set_page_config(page_title="Field Signal · Straight Rows", layout="wide")
alt.data_transformers.disable_max_rows()  # intervals are bounded below; rows stay in the low thousands


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


def display_bins(tele, tractors, a, b, rule):
    """Aggregate raw 1 Hz telemetry into display bins (same aggregations as features.py for shared channels)."""
    seg = tele[(tele.ts >= a) & (tele.ts < b) & tele.tractor_id.isin(tractors)]
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


def held(df, col, a, b):
    """Piecewise-constant SDA series over [a, b]: value in force at a, changes inside, held to b."""
    df = df.sort_values("ts")
    before = df[df.ts <= a].tail(1).assign(ts=a)
    s = pd.concat([before, df[(df.ts > a) & (df.ts < b)]])
    return pd.concat([s, s.tail(1).assign(ts=b)])[["ts", col]] if len(s) else s


def fmt(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M UTC")


def hm(ts):
    return pd.Timestamp(ts).strftime("%H:%M")


def git_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def det_label(i, x):
    c = CAUSES[x["class"]]
    return (f"#{i + 1}  {c['short']} · {' '.join(x['tractors'])} · "
            f"{pd.Timestamp(x['start']):%m-%d %H:%M}–{pd.Timestamp(x['end']):%H:%M} UTC")


# ---------------------------------------------------------------- charts
def x_enc(a, b, title=None, labels=True):
    return alt.X("ts:T", title=title, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
                 axis=alt.Axis(format="%m-%d %H:%M", labelAngle=0, labels=labels, grid=False,
                               labelFont="monospace", labelColor=INK_SOFT, tickColor=RULE, domainColor=RULE))


def bands_layer(bands, a, b):
    """Shaded selected incident + dashed start/end rules."""
    if bands.empty:
        return None
    shade = alt.Chart(bands).mark_rect(opacity=0.09, color=INK).encode(x=x_enc(a, b), x2="end:T")
    rules = alt.Chart(bands.melt(value_vars=["ts", "end"], value_name="t")).mark_rule(
        strokeDash=[4, 3], color=INK_SOFT).encode(x=alt.X("t:T", scale=alt.Scale(type="utc")))
    return shade + rules


def line_panel(df, field, a, b, bands, affected, show_legend=False, xtitle=None, height=105):
    title, zero = CHANNELS[field]
    colour = alt.Color("tractor_id:N", title="Tractor", scale=alt.Scale(domain=TRACTORS, range=TRACTOR_COLORS),
                       legend=alt.Legend(orient="top", direction="horizontal") if show_legend else None)
    dash = alt.StrokeDash("role:N", title="Line", scale=alt.Scale(
        domain=["affected", "other"] if affected else ["custom"],
        range=[[1, 0], [5, 3]] if affected else [[1, 0]]),
        legend=alt.Legend(orient="top", direction="horizontal") if show_legend and affected else None)
    if affected:
        d2 = df.assign(role=df.tractor_id.map(lambda t: "affected" if t in affected else "other"))
    else:
        d2 = df.assign(role="custom")  # no incident selected: all lines solid
    line = alt.Chart(d2).mark_line(strokeWidth=1.5).encode(
        x=x_enc(a, b, xtitle), y=alt.Y(f"{field}:Q", title=title, scale=alt.Scale(zero=zero),
                                       axis=alt.Axis(labelFont="monospace", gridColor="#e6e0d1", titleFontWeight="normal")),
        color=colour, strokeDash=dash, detail="seg:N",
        tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="time"), alt.Tooltip(f"{field}:Q", format=".3f")])
    b_layer = bands_layer(bands, a, b)
    return (b_layer + line if b_layer is not None else line).properties(height=height)


def step_panel(df, field, a, b, bands, xtitle=None, height=80):
    if df.empty:
        return None
    title, zero = CHANNELS[field]
    df = df.assign(time_utc=df.ts.dt.strftime("%Y-%m-%d %H:%M UTC"))
    line = alt.Chart(df).mark_line(interpolate="step-after", color=INK, strokeWidth=1.5).encode(
        x=x_enc(a, b, xtitle), y=alt.Y(f"{field}:Q", title=title, scale=alt.Scale(zero=zero),
                                       axis=alt.Axis(labelFont="monospace", gridColor="#e6e0d1", titleFontWeight="normal")),
        tooltip=[alt.Tooltip("time_utc:N", title="value in force from"), alt.Tooltip(f"{field}:Q", format=".3f")])
    b_layer = bands_layer(bands, a, b)
    return (b_layer + line if b_layer is not None else line).properties(height=height)


def panel_for(key, bins, d, a, b, bands, affected, show_legend, xtitle):
    if key in ("s4", "kp"):
        return step_panel(held(d[key], key, a, b), key, a, b, bands, xtitle=xtitle)
    return line_panel(bins, key, a, b, bands, affected, show_legend=show_legend, xtitle=xtitle)


def incident_lane(dets, sel_idx, a, b):
    """Detections overlapping the charted interval; the selected one is solid, others faded and labelled."""
    rows = [{"lane": CAUSES[x["class"]]["code"], "cause": x["class"],
             "label": f"{CAUSES[x['class']]['code']} · {' '.join(x['tractors'])}",
             "when": f"{fmt(x['start'])} → {fmt(x['end'])}", "s": max(pd.Timestamp(x["start"]), a),
             "e": min(pd.Timestamp(x["end"]), b), "state": "selected" if i == sel_idx else "adjacent"}
            for i, x in enumerate(dets) if pd.Timestamp(x["start"]) < b and pd.Timestamp(x["end"]) > a]
    if not rows:
        return None
    items = pd.DataFrame(rows)
    base = alt.Chart(items).encode(y=alt.Y("lane:N", title=None, sort=None,
                                           axis=alt.Axis(labelLimit=60, labelFont="monospace", ticks=False, domain=False)))
    bars = base.mark_bar(height=12, stroke=INK, strokeWidth=0.6).encode(
        x=alt.X("s:T", title=None, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
                axis=alt.Axis(format="%m-%d %H:%M", labelAngle=0, labelFont="monospace", grid=False, labels=False)),
        x2="e:T",
        color=alt.Color("cause:N", scale=alt.Scale(domain=list(CAUSES), range=[c["color"] for c in CAUSES.values()]),
                        legend=None),
        opacity=alt.Opacity("state:N", scale=alt.Scale(domain=["selected", "adjacent"], range=[0.95, 0.35]),
                            legend=None),  # explained in the caption; keeps the legend row narrow
        tooltip=["label:N", "when:N", "state:N"])
    text = base.mark_text(align="left", dx=4, color=INK, fontSize=10, font="monospace").encode(x="s:T", text="label:N")
    return (bars + text).properties(height=max(26, 20 * items.lane.nunique()))


def fleet_ribbon(dets, sel_idx, a, b):
    """T1/T2/T3 lanes across the whole window; concurrent causes on one tractor sit in separate sub-rows."""
    rows = []
    for i, x in enumerate(dets):
        c = CAUSES[x["class"]]
        dur = (pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).total_seconds() / 60
        for t in x["tractors"]:
            rows.append({"det_id": i, "tractor": t, "cause": x["class"], "code": c["code"],
                         "start": pd.Timestamp(x["start"]), "end": pd.Timestamp(x["end"]),
                         "text": c["code"] if dur >= (90 if (b - a) > pd.Timedelta(days=1) else 45) else "",
                         "label": det_label(i, x), "sel": "selected" if i == sel_idx else "other"})
    df = pd.DataFrame(rows)
    pick = alt.selection_point(name="pick", fields=["det_id"], on="click", clear=False)
    x = alt.X("start:T", title=None, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
              axis=alt.Axis(format="%m-%d %H:%M", labelAngle=0, labelFont="monospace", labelColor=INK_SOFT,
                            gridColor="#e6e0d1", tickCount=12))
    y = alt.Y("tractor:N", title=None, sort=TRACTORS, scale=alt.Scale(domain=TRACTORS),
              axis=alt.Axis(labelFont="monospace", labelFontWeight="bold", ticks=False, domain=False))
    present = [c for c in CAUSES if c in set(df.cause)]   # sub-rows only for causes in this window
    base = alt.Chart(df).encode(x=x, x2="end:T", y=y,
                                yOffset=alt.YOffset("cause:N", sort=present, scale=alt.Scale(domain=present)))
    bars = base.mark_bar(cornerRadius=1).encode(
        color=alt.Color("cause:N", title="Attributed cause",
                        scale=alt.Scale(domain=present, range=[CAUSES[c]["color"] for c in present]),
                        legend=alt.Legend(orient="top", direction="horizontal", labelFont="monospace",
                                          labelExpr=" : ".join(
                                              f"datum.label == '{k}' ? '{v['code']} {v['short'].lower()}'"
                                              for k, v in CAUSES.items()) + " : datum.label")),
        stroke=alt.condition(alt.datum.sel == "selected", alt.value(INK), alt.value(None)),
        strokeWidth=alt.condition(alt.datum.sel == "selected", alt.value(2), alt.value(0)),
        tooltip=[alt.Tooltip("label:N", title="incident"), alt.Tooltip("tractor:N")],
    ).add_params(pick)
    text = base.mark_text(align="left", dx=3, fontSize=9, font="monospace", color="#ffffff").encode(
        x="start:T", text="text:N")
    # Wrapped in vconcat: a bare layered chart rendered by Streamlit collapsed its band scale.
    return alt.vconcat((bars + text).properties(width=RIBBON_WIDTH, height=130)).configure_view(stroke=RULE)


# ---------------------------------------------------------------- page
with st.sidebar:
    st.markdown("**Investigation window**")
    window_name = st.radio("Analysis window", list(WINDOWS), index=1, label_visibility="collapsed")
    a_w, b_w = WINDOWS[window_name]
    st.caption(f"`{fmt(a_w)}` → `{fmt(b_w)}` (end exclusive). Simulated dates.")
    with st.expander("Advanced settings", expanded=False):
        data_dir = st.text_input("Data folder", value=str(ROOT / "data"),
                                 help="Folder produced by scripts\\get_data.py (contains farm\\, sda\\, labels\\).")
        agg_label = st.radio("Display aggregation", list(AGGREGATIONS), index=0,
                             help="Charts only. Detection always uses the pipeline's 1-minute features.")

dev = window_name.startswith("Development")
status = ("Development window · labeled · any score shown is in-sample" if dev
          else "Evaluation window · no public labels · accuracy is not measured here")
st.markdown(
    f"""<div style="border-bottom:1px solid {RULE};padding-bottom:6px;margin-bottom:4px">
<div style="font-family:serif;font-size:2rem;letter-spacing:0.18em;font-weight:600;color:{INK};line-height:1.1">FIELD SIGNAL</div>
<div style="font-family:serif;font-size:1.05rem;color:{INK_SOFT}">Straight Rows · Fleet Guidance Investigation</div>
<div style="font-family:monospace;font-size:0.78rem;color:{INK_SOFT};margin-top:4px">
Challenge simulation data · Retrospective analysis · {status}</div></div>""",
    unsafe_allow_html=True)

missing, sig = data_signature(data_dir)
if missing:
    st.error("Challenge data not found in the selected folder (Advanced settings). Missing: " + ", ".join(missing))
    st.code(r".venv\Scripts\python.exe scripts\get_data.py --zip C:\path\to\StraightRows_Student_Package.zip",
            language="bat")
    st.stop()

cfg = Config()
cfg_items = tuple(sorted(asdict(cfg).items()))
try:
    d = load_data(data_dir, sig)
    dets = pipeline_results(data_dir, sig, window_name, cfg_items)
    flags = pipeline_flags(data_dir, sig, window_name, cfg_items)
except Exception as exc:  # malformed inputs: show the error instead of a blank page
    st.error(f"Could not load or analyse the data: {type(exc).__name__}: {exc}")
    st.stop()

tab_inv, tab_fleet, tab_method = st.tabs(["Investigation", "Fleet comparison", "Methodology and limitations"])
skey = f"{window_name}-{abs(hash(sig))}"          # selection keys change with window/data → no stale picks
rib_key, sel_key, last_key = f"ribbon-{skey}", f"incident-{skey}", f"lastpick-{skey}"

# ---------------------------------------------------------------- investigation
with tab_inv:
    sel_idx = None
    if dets:
        # Apply a ribbon click from the previous run (stored by Streamlit under the chart key).
        prev = st.session_state.get(rib_key)
        picked = (prev or {}).get("selection", {}).get("pick") if prev else None
        if picked and "det_id" in picked[0] and picked[0]["det_id"] != st.session_state.get(last_key):
            st.session_state[sel_key] = int(picked[0]["det_id"])
            st.session_state[last_key] = int(picked[0]["det_id"])
        if st.session_state.get(sel_key, 0) >= len(dets):
            st.session_state[sel_key] = 0
        cur = st.session_state.get(sel_key, 0)

        st.markdown(f"**Fleet incident ribbon** · {len(dets)} pipeline detections · click a bar or use the selector")
        st.altair_chart(fleet_ribbon(dets, cur, a_w, b_w), key=rib_key, on_select="rerun",
                        selection_mode="pick", width="content", theme="streamlit")
        c_sel, c_mode = st.columns([3, 1])
        sel_idx = c_sel.selectbox("Incident", list(range(len(dets))), key=sel_key,
                                  format_func=lambda i: det_label(i, dets[i]))
        mode = c_mode.radio("Inspect", ["Incident", "Custom interval"], horizontal=True)
        with st.expander(f"Detection register ({len(dets)})"):
            st.dataframe(pd.DataFrame([{
                "#": i + 1, "Start (UTC)": fmt(x["start"]), "End (UTC)": fmt(x["end"]),
                "Minutes": round((pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).total_seconds() / 60),
                "Tractors": ", ".join(x["tractors"]), "Cause (pipeline)": x["class"], "Action": x["action"],
                "Confidence": x["confidence"]} for i, x in enumerate(dets)]), hide_index=True, width="stretch")
    else:
        st.info("No pipeline detections in this window. Inspect any interval below.")
        mode = "Custom interval"

    selected = dets[sel_idx] if (dets and mode == "Incident") else None
    if selected:
        s0, e0 = pd.Timestamp(selected["start"]), pd.Timestamp(selected["end"])
        cz = CAUSES[selected["class"]]
        st.markdown(f"### {cz['headline']} on {', '.join(selected['tractors'])}")
        st.markdown(
            f"`{fmt(s0)}` → `{fmt(e0)}` · {round((e0 - s0).total_seconds() / 60)} min · "
            f":gray-badge[Pipeline attribution — not confirmed truth] "
            f"**Action:** {ACTION_TEXT[selected['action']]}")
        o1, o2 = st.columns([1, 2])
        pad = o1.slider("Context before/after (min)", 0, 180, 30, step=5, key=f"pad-{skey}")
        shown = o2.multiselect("Tractors on charts", TRACTORS, default=TRACTORS, key=f"tr-{skey}")
        a, b = max(a_w, s0 - pd.Timedelta(minutes=pad)), min(b_w, e0 + pd.Timedelta(minutes=pad))
        affected = selected["tractors"]
        # Measurements for the brief: evidence._stats, the function behind the exported evidence.
        tele_all = d["tele"]
        un = [t for t in TRACTORS if t not in affected]
        during = tele_all[(tele_all.ts >= s0) & (tele_all.ts < e0)]
        sa, su = _stats(during[during.tractor_id.isin(affected)]), _stats(during[during.tractor_id.isin(un)])
        sp = _stats(tele_all[(tele_all.ts >= s0 - PRE) & (tele_all.ts < s0) & tele_all.tractor_id.isin(affected)
                             & (tele_all.speed_mps > 0)])
        channels = (ef_channels(sa, su, cfg) if selected["class"] == "EQUIPMENT_FAULT"
                    else PRIMARY[selected["class"]])
    else:
        s0 = e0 = None
        hours = pd.date_range(a_w, b_w - pd.Timedelta(hours=1), freq="1h")
        o1, o2, o3 = st.columns([2, 1, 2])
        start = o1.select_slider("Interval start (UTC)", options=list(hours), value=hours[12], format_func=fmt,
                                 key=f"cstart-{skey}")
        length = o2.slider("Length (min)", 15, 360, 120, step=15, key=f"clen-{skey}")
        shown = o3.multiselect("Tractors on charts", TRACTORS, default=TRACTORS, key=f"ctr-{skey}")
        a, b = start, min(b_w, start + pd.Timedelta(minutes=length))
        affected, channels = [], PRIMARY[None]

    rule = AGGREGATIONS[agg_label]
    if rule == "1s" and (b - a) > pd.Timedelta(minutes=30):
        rule = "10s"
        st.caption("1 s display is limited to intervals of 30 minutes or less; showing 10 s bins.")

    left, right = st.columns([3, 2], gap="large")
    with left:
        if not shown:
            st.info("Select at least one tractor to draw the charts.")
            bins = pd.DataFrame()
        else:
            bins = display_bins(d["tele"], shown, a, b, rule)
        if shown and bins.empty:
            st.info("No telemetry in this interval for the selected tractors.")
        elif shown:
            bands = pd.DataFrame({"ts": [s0], "end": [e0]}) if s0 is not None else pd.DataFrame()
            # Working state: the pipeline's per-minute flag. A strip only when it changes.
            wf = flags[(flags.ts >= a) & (flags.ts < b) & flags.tractor_id.isin(shown)].copy()
            per = wf.groupby("tractor_id").working.agg(["all", "any"])
            if len(per) and (per["all"] | ~per["any"]).all():
                parts = [f"{t} {'working' if per.loc[t, 'all'] else 'parked'}" for t in per.index]
                st.caption(f"Working state, whole interval: `{' · '.join(parts)}` (1-min mean speed > "
                           f"{cfg.moving_mps:g} m/s)")
                working = None
            else:
                wf["state"] = wf.working.map({True: "working", False: "parked"})
                wf["end"] = wf.ts + pd.Timedelta(minutes=1)
                wf["time_utc"] = wf.ts.dt.strftime("%Y-%m-%d %H:%M UTC")
                working = alt.Chart(wf).mark_bar().encode(
                    x=x_enc(a, b, labels=False), x2="end:T",
                    y=alt.Y("tractor_id:N", title="Working", sort=TRACTORS,
                            axis=alt.Axis(labelFont="monospace", ticks=False, domain=False)),
                    color=alt.Color("state:N", scale=alt.Scale(domain=["working", "parked"],
                                                               range=["#6f6a5d", "#b5ad98"]),
                                    legend=None),  # thick dark = working, thin light = parked (caption + tooltip)
                    size=alt.Size("state:N", scale=alt.Scale(domain=["working", "parked"], range=[10, 3]), legend=None),
                    tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="minute"), "state:N",
                             alt.Tooltip("moving:Q", title="mean speed (m/s)", format=".2f")],
                ).properties(height=16 * max(1, wf.tractor_id.nunique()))
            lane = incident_lane(dets, sel_idx if selected else None, a, b)
            panels = [p for p in [lane, working] if p is not None]
            for i, key in enumerate(channels):
                panels.append(panel_for(key, bins, d, a, b, bands, affected, show_legend=(i == 0),
                                        xtitle="Time (UTC)" if i == len(channels) - 1 else None))
            panels = [p.properties(width=CHART_WIDTH) for p in panels if p is not None]
            chart = (alt.vconcat(*panels, spacing=6).resolve_scale(x="shared", color="independent",
                                                                   opacity="independent")
                     .configure_view(stroke=RULE).configure_legend(labelFont="monospace", titleFontWeight="normal"))
            st.altair_chart(chart, width="content", theme="streamlit")
            st.caption(f"Primary channels for this cause (display only) · `{rule}` bins · shaded band = selected "
                       "incident · top lane: solid bar = selected, faded = adjacent incidents · working strip: thick "
                       "dark = working, thin light = parked · lines break at missing bins. "
                       "Charts show inputs; they do not independently validate the detector.")
            with st.expander("Inspect all signals"):
                full = [panel_for(k, bins, d, a, b, bands, affected, show_legend=(k == "xte"),
                                  xtitle="Time (UTC)" if k == "kp" else None) for k in ALL_CHANNELS]
                full = [p.properties(width=ALL_WIDTH) for p in [lane, working] + full if p is not None]
                st.altair_chart(alt.vconcat(*full, spacing=6).resolve_scale(x="shared", color="independent",
                                                                          opacity="independent")
                                .configure_view(stroke=RULE), width="content", theme="streamlit")
                st.caption("Bin means for cross-track error (signed) and mean C/N0; bin minimum for min C/N0; bin "
                           "median for satellites; % of samples for RTK link and RTK_FIXED; S4 and Kp as the latest "
                           "published value.")
        if selected:
            with st.expander("Exact evidence exported to submission"):
                st.markdown("\n".join(f"- {line}" for line in selected["evidence"]))
        rfi = d["rfi"][(d["rfi"].ts >= a) & (d["rfi"].ts < b)]
        adv = d["adv"][(d["adv"].ts >= a) & (d["adv"].ts < b)]
        if len(rfi) or len(adv):
            with st.expander(f"SDA reports in this interval ({len(rfi) + len(adv)})"):
                for r in rfi.itertuples():
                    st.markdown(f"- RFI `{r.id}` at `{r.ts:%Y-%m-%d %H:%M:%S} UTC`, confidence {r.confidence}, "
                                f"ellipse {r.semiMajor_km}×{r.semiMinor_km} km: {r.text} "
                                "(observation vs. report time not documented)")
                for v in adv.itertuples():
                    st.markdown(f"- Advisory `{v.id}` ({v.type}) at `{v.ts:%Y-%m-%d %H:%M} UTC`: {v.text}")

    with right:
        if selected:
            st.markdown("#### Decision brief")
            ev = selected["evidence"]
            aff = selected["tractors"]
            rows = [("Mean C/N0 dB-Hz", "cn0", 1), ("Min C/N0 dB-Hz", "mincn0", 1), ("Satellites (median)", "sats", 0),
                    ("XTE median m", "xte_med", 2), ("XTE max m", "xte_max", 2), ("RTK_FIXED %", "fixed", 0),
                    ("RTK link up %", "link", 0)]
            cols = {"Incident": sa, "Others": su, "Prior 30 min": sp}
            table = pd.DataFrame({"": [r[0] for r in rows], **{
                name: [("—" if s is None else f"{s[k]:.{n}f}") for _, k, n in rows] for name, s in cols.items()}})
            st.markdown("**Observed measurements** · same calculation as the exported evidence")
            st.table(table.set_index(""))
            st.caption(f"Incident = {' '.join(aff)} during the interval; Others = "
                       f"{' '.join(un) or 'none'}; Prior 30 min = {' '.join(aff)}, working samples before onset.")
            sda_line = next((e for e in ev if e.startswith("Regional S4")), None)
            rfi_line = next((e for e in ev if e.startswith("RFI:") or e.startswith("No RFI report")), None)
            if sda_line:
                st.caption(sda_line)
            if rfi_line:
                st.caption(f"{rfi_line} RFI reports are evidence only; the attribution rules do not use them.")
            st.markdown("**Pipeline interpretation**")
            for e in ev:
                if e.startswith("Attributed") or e.startswith("Concurrent with"):
                    st.markdown(f"- {e}")
            st.markdown("**Recommended operator action**")
            st.markdown(ACTION_TEXT[selected["action"]])
            st.markdown("**Uncertainty**")
            unc = {
                "SPACE_WEATHER": f"Rule: all three tractors below {cfg.cn0_low_dbhz:g} dB-Hz with S4 ≥ {cfg.s4_storm}. "
                                 "The S4 cutoff was chosen by hand on development data. A storm does not rule out "
                                 "simultaneous jamming; jamming inside a storm is currently missed.",
                "JAMMING": f"Rule: mean C/N0 below {cfg.cn0_low_dbhz:g} dB-Hz with S4 below {cfg.s4_storm}. "
                           "RFI reports are not used in the decision, and the rule does not check whether the loss "
                           "is confined to one machine.",
                "SPOOFING": f"Rule: guidance-monitor cross-track error above {cfg.xte_high_m:g} m (minute mean) without "
                            f"C/N0 below {cfg.cn0_low_dbhz:g} dB-Hz. Reported position is not used. Spoofing during a "
                            "storm is currently missed.",
                "EQUIPMENT_FAULT": f"Rule: RTK link up < {cfg.link_low_frac:.0%} of a minute, or min C/N0 below "
                                   f"{cfg.dropout_dbhz:g} dB-Hz with normal mean C/N0. Same-cause gaps ≤ "
                                   f"{cfg.bridge_gap_s:g} s are bridged, so the interval can include normal minutes.",
            }[selected["class"]]
            st.markdown(f"- Confidence **{selected['confidence']}**: fixed heuristic value {CONFIDENCE}; not calibrated, "
                        "not a probability.\n- " + unc +
                        ("\n- Same-cause detections on different tractors are merged within 5 min, which can overstate "
                         "the affected set." if len(aff) > 1 else ""))
            with st.expander("Identifiers"):
                st.markdown(f"- class `{selected['class']}`\n- action `{selected['action']}`\n"
                            f"- start `{selected['start']}`\n- end `{selected['end']}`\n"
                            f"- tractors `{selected['tractors']}`\n- confidence `{selected['confidence']}`")
        else:
            st.markdown("#### Decision brief")
            st.caption("Select an incident to see its measurements, interpretation, action and uncertainty.")

    # ---- development labels: separate, never predictions
    if dev:
        with st.expander("Development labels — ground truth for the labeled window, not model output"):
            labels = d.get("labels")
            if labels is None:
                st.info("No labels file in this data folder.")
            else:
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
    st.markdown("#### Same interval across tractors")
    st.caption(f"Interval `{fmt(a)}` → `{fmt(b)}` (set on the Investigation tab). Statistics from raw 1 Hz "
               "telemetry; working share from the pipeline's per-minute flag.")
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
            "Incidents in interval": "; ".join(involved) or "none",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    with st.expander("Reported GNSS position (not ground truth)"):
        st.caption(
            "Reported lat/lon converted to metres from the interval's mean position with a local flat-earth "
            "approximation (1° latitude = 111,320 m; 1° longitude = 111,320 m × cos(mean latitude)); adequate over "
            "about 1 km. Reported position can be displaced during spoofing. No intended guidance line is drawn: "
            "the dataset provides no reference geometry. Points are 10 s means and are not joined.")
        pos = tele[(tele.ts >= a) & (tele.ts < b) & tele.tractor_id.isin(shown or TRACTORS)]
        if pos.empty:
            st.info("No telemetry in this interval.")
        else:
            import math
            p = pos.set_index("ts").groupby("tractor_id")[["lat", "lon"]].resample("10s").mean().dropna().reset_index()
            lat0 = p.lat.mean()
            p["east_m"] = (p.lon - p.lon.mean()) * 111320 * math.cos(math.radians(lat0))
            p["north_m"] = (p.lat - lat0) * 111320
            p["time_utc"] = p.ts.dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            path = alt.Chart(p).mark_point(size=10, filled=True, opacity=0.7).encode(
                x=alt.X("east_m:Q", title="East of interval mean (m)", scale=alt.Scale(zero=False)),
                y=alt.Y("north_m:Q", title="North of interval mean (m)", scale=alt.Scale(zero=False)),
                color=alt.Color("tractor_id:N", title="Tractor", scale=alt.Scale(domain=TRACTORS, range=TRACTOR_COLORS)),
                shape=alt.Shape("tractor_id:N", legend=None),
                tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="time")],
            ).properties(height=420, title="Reported GNSS position").configure_legend(orient="top")
            st.altair_chart(path, width="stretch", theme="streamlit")

# ---------------------------------------------------------------- methodology
with tab_method:
    st.markdown("#### Methodology and limitations")
    st.markdown(f"""
- **Detections come from the pipeline** (`src/straightrows`): per-minute features → cause-agnostic flags →
  one test per cause → interval assembly → evidence. The dashboard does not detect anything itself.
- **Causes are pipeline attributions**, not confirmed truth. Development labels exist only for the labeled window.
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
    st.markdown("**Display choices (do not affect detection)**")
    st.markdown(
        "- Primary channels per attributed cause: "
        + "; ".join(f"{CAUSES[c]['short']} → {', '.join(CHANNELS[k][0] for k in ks)}"
                    for c, ks in PRIMARY.items() if c and c != "EQUIPMENT_FAULT")
        + ". All channels remain under *Inspect all signals*.\n"
        "- Equipment fault: chosen per incident with the same test the evidence text uses. Antenna dropouts (min "
        "C/N0 below the dropout level) → min C/N0, satellites, mean C/N0; correction-link loss → RTK link up, "
        "RTK_FIXED, min C/N0; both → min C/N0, RTK link up, RTK_FIXED. Cross-track error is never primary for "
        "equipment fault: the rule does not use it, and a concurrent spoof can inflate it.\n"
        "- Aggregation: bin means (cross-track error keeps its sign; mean C/N0), bin minimum (min C/N0), bin median "
        "(satellites), percentage of samples (RTK link, RTK_FIXED). At 1 min these equal the pipeline's features.\n"
        "- Lines break at missing bins and never join different tractors. Tractor colours are fixed: "
        "T1 blue, T2 orange, T3 green. Cause bars carry a text code (SW, JAM, SPF, EF) as well as a colour.")
    st.markdown("**Provenance**")
    st.dataframe(pd.DataFrame(
        [("Window", window_name), ("Window UTC", f"{fmt(a_w)} → {fmt(b_w)} (end exclusive)"),
         ("Data folder", data_dir), ("Git commit", git_commit()), ("Detections", str(len(dets)))]
        + [(f"Config.{k}", str(v)) for k, v in asdict(cfg).items()],
        columns=["Item", "Value"]), hide_index=True, width="stretch")
