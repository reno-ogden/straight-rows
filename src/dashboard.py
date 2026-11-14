"""Straight Rows — Fleet Guidance Monitor (Streamlit dashboard).

Launch from the repository root (Windows CMD):
    .venv\\Scripts\\python.exe -m streamlit run src\\dashboard.py

Read-only view of the existing pipeline. Detections, evidence, actions and the working flag
all come from `straightrows` (io.load, pipeline.detect, export.to_submission, features +
candidates). The dashboard only selects intervals and aggregates raw telemetry for display.
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
from straightrows.config import ACTION, DEV, EVAL, Config  # noqa: E402
from straightrows.export import CONFIDENCE, to_submission  # noqa: E402
from straightrows.features import minute_features  # noqa: E402
from straightrows.io import load  # noqa: E402
from straightrows.pipeline import detect  # noqa: E402

TRACTORS = ["T1", "T2", "T3"]
# Same tractor colours on every chart (validated categorical slots 1-3, dark mode).
TRACTOR_COLORS = ["#3987e5", "#d95926", "#199e70"]
WINDOWS = {"Development (labeled)": DEV, "Evaluation (unlabeled, scored by organizers)": EVAL}
REQUIRED = ["farm/tractor_telemetry.csv.gz", "sda/sgi_indices.json", "sda/scintillation_series.json",
            "sda/constellation_advisories.json", "sda/rfi_reports.json"]
AGGREGATIONS = {"1 min": "1min", "10 s": "10s", "1 s (raw, intervals up to 30 min)": "1s"}

CAUSE_TEXT = {
    "SPACE_WEATHER": "Regional signal degradation during elevated ionospheric scintillation (all tractors together).",
    "JAMMING": "Radio-frequency interference: signal loss while regional scintillation is quiet.",
    "SPOOFING": "Guidance error grows without the signal-health collapse that jamming or space weather cause.",
    "EQUIPMENT_FAULT": "Machine-specific problem: antenna dropouts or a correction-link fault on one tractor.",
    "MULTIPATH": "Brief reflections near an obstruction (not detected by this pipeline).",
}
ACTION_TEXT = {
    "HALT_OR_DEGRADED_MODE": "Halt or continue in a degraded guidance mode until conditions improve.",
    "HALT_AND_REPORT": "Halt and report suspected interference.",
    "HALT_CROSSCHECK_AND_REPORT": "Halt, cross-check position with an independent source, and report.",
    "SERVICE_MACHINE_OTHERS_CONTINUE": "Service the affected machine; the other machines continue.",
    "CONTINUE_FALSE_ALARM": "Continue; treat as a false alarm.",
}

st.set_page_config(page_title="Straight Rows — Fleet Guidance Monitor", layout="wide")
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


def git_commit():
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, timeout=5).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- charts
CHART_WIDTH = 820  # px plot area; total chart width (axes + labels) then fits a 1440 px wide layout


def x_enc(a, b, title=None):
    return alt.X("ts:T", title=title, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
                 axis=alt.Axis(format="%m-%d %H:%M", labelAngle=0))


def bands_layer(bands, a, b):
    """Shaded selected incident + dashed start/end rules."""
    if bands.empty:
        return None
    shade = alt.Chart(bands).mark_rect(opacity=0.10, color="#e6e4df").encode(x=x_enc(a, b), x2="end:T")
    rules = alt.Chart(bands.melt(value_vars=["ts", "end"], value_name="t")).mark_rule(
        strokeDash=[4, 3], color="#c3c2b7").encode(x=alt.X("t:T", scale=alt.Scale(type="utc")))
    return shade + rules


def line_panel(df, field, title, a, b, bands, affected, zero=False, height=120):
    colour = alt.Color("tractor_id:N", title="Tractor", scale=alt.Scale(domain=TRACTORS, range=TRACTOR_COLORS))
    dash = alt.StrokeDash("role:N", title="Line style", scale=alt.Scale(
        domain=["in selected detection", "other tractor", "no detection selected"], range=[[1, 0], [5, 3], [1, 0]]))
    if affected:
        d2 = df.assign(role=df.tractor_id.map(lambda t: "in selected detection" if t in affected else "other tractor"))
    else:
        d2 = df.assign(role="no detection selected")
    line = alt.Chart(d2).mark_line(strokeWidth=1.6, interpolate="linear").encode(
        x=x_enc(a, b), y=alt.Y(f"{field}:Q", title=title, scale=alt.Scale(zero=zero)),
        color=colour, strokeDash=dash, detail="seg:N",
        tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="time"), alt.Tooltip(f"{field}:Q", format=".3f")])
    layer = line
    b_layer = bands_layer(bands, a, b)
    if b_layer is not None:
        layer = b_layer + line
    return layer.properties(height=height)


def step_panel(df, field, title, a, b, bands, height=80, xtitle=None):
    if df.empty:
        return None
    df = df.assign(time_utc=df.ts.dt.strftime("%Y-%m-%d %H:%M UTC"))
    line = alt.Chart(df).mark_line(interpolate="step-after", color="#c3c2b7", strokeWidth=1.6).encode(
        x=x_enc(a, b, xtitle), y=alt.Y(f"{field}:Q", title=title),
        tooltip=[alt.Tooltip("time_utc:N", title="value in force from"), alt.Tooltip(f"{field}:Q", format=".3f")])
    b_layer = bands_layer(bands, a, b)
    return (b_layer + line if b_layer is not None else line).properties(height=height)


def lane_chart(items, a, b, title):
    """Horizontal bars for intervals (detections or labels) with text labels, not colour alone."""
    if items.empty:
        return None
    items = items.assign(s=items.start.clip(lower=a), e=items.end.clip(upper=b))
    base = alt.Chart(items).encode(y=alt.Y("lane:N", title=None, sort=None, axis=alt.Axis(labelLimit=150)))
    bars = base.mark_bar(height=14, color="#5b6070", stroke="#c3c2b7", strokeWidth=0.6).encode(
        x=alt.X("s:T", title=None, scale=alt.Scale(type="utc", domain=[a.isoformat(), b.isoformat()]),
                axis=alt.Axis(format="%m-%d %H:%M", labelAngle=0)), x2="e:T",
        tooltip=["label:N", "when:N"])
    text = base.mark_text(align="left", dx=4, color="#e6e4df", fontSize=11).encode(x="s:T", text="label:N")
    chart = (bars + text).properties(height=max(40, 24 * items.lane.nunique()))
    return chart.properties(title=title) if title else chart


# ---------------------------------------------------------------- page
st.title("Straight Rows — Fleet Guidance Monitor")
st.markdown(
    ":gray-badge[Challenge simulation data] :gray-badge[Retrospective analysis] "
    ":orange-badge[Development results are in-sample]")

with st.sidebar:
    st.header("Data and window")
    data_dir = st.text_input("Data folder", value=str(ROOT / "data"),
                             help="Folder produced by scripts\\get_data.py (contains farm\\, sda\\, labels\\).")
    window_name = st.radio("Analysis window", list(WINDOWS), index=1)
    a_w, b_w = WINDOWS[window_name]
    st.caption(f"UTC: {fmt(a_w)} to {fmt(b_w)} (end exclusive). Simulated dates.")
    agg_label = st.radio("Display aggregation", list(AGGREGATIONS), index=0,
                         help="Applies to the charts only. Detection always uses the pipeline's 1-minute features.")

missing, sig = data_signature(data_dir)
if missing:
    st.error("Challenge data not found in the selected folder. Missing: " + ", ".join(missing))
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

tab_inc, tab_fleet, tab_method = st.tabs(["Incidents", "Fleet comparison", "Methodology and limitations"])

# ---------------------------------------------------------------- incidents
with tab_inc:
    st.subheader(f"Pipeline detections — {window_name}")
    st.caption("Model output only. Development labels, when available, are shown separately and never as predictions.")
    det_df = pd.DataFrame([{
        "#": i + 1, "Start (UTC)": fmt(x["start"]), "End (UTC)": fmt(x["end"]),
        "Minutes": round((pd.Timestamp(x["end"]) - pd.Timestamp(x["start"])).total_seconds() / 60),
        "Tractors": ", ".join(x["tractors"]), "Cause": x["class"], "Operator action": x["action"],
    } for i, x in enumerate(dets)])
    selected = None
    if det_df.empty:
        st.info("No detections in this window. Use *Custom interval* below to inspect the telemetry.")
    else:
        ev = st.dataframe(det_df, hide_index=True, on_select="rerun", selection_mode="single-row",
                          key=f"eps-{window_name}-{abs(hash(sig))}", width="stretch")
        rows = ev.selection.rows if ev and ev.selection else []
        selected = dets[rows[0]] if rows else dets[0]
        if not rows:
            st.caption("Showing detection #1. Click a row to select another.")

    source = st.radio("Interval to inspect", ["Selected detection", "Custom interval"], horizontal=True,
                      index=0 if selected else 1, disabled=selected is None)
    c1, c2 = st.columns(2)
    if source == "Selected detection" and selected:
        s0, e0 = pd.Timestamp(selected["start"]), pd.Timestamp(selected["end"])
        pad = c1.slider("Context before/after (minutes)", 0, 180, 30, step=5)
        a, b = max(a_w, s0 - pd.Timedelta(minutes=pad)), min(b_w, e0 + pd.Timedelta(minutes=pad))
        affected = selected["tractors"]
    else:
        hours = pd.date_range(a_w, b_w - pd.Timedelta(hours=1), freq="1h")
        start = c1.select_slider("Interval start (UTC)", options=list(hours), value=hours[12], format_func=fmt)
        length = c2.slider("Interval length (minutes)", 15, 360, 120, step=15)
        a, b = start, min(b_w, start + pd.Timedelta(minutes=length))
        s0 = e0 = None
        affected = []
    shown = st.multiselect("Tractors on charts", TRACTORS, default=TRACTORS, key=f"tr-{window_name}")

    if selected and source == "Selected detection":
        st.markdown(f"#### Detection: `{selected['class']}` on {', '.join(selected['tractors'])}")
        m1, m2, m3 = st.columns([2, 2, 1])
        m1.markdown(f"**Cause** `{selected['class']}`  \n{CAUSE_TEXT[selected['class']]}")
        m2.markdown(f"**Recommended action** `{selected['action']}`  \n{ACTION_TEXT[selected['action']]}")
        m3.markdown(f"**Confidence** {selected['confidence']}  \nFixed heuristic value {CONFIDENCE}; not calibrated.")
        st.markdown(f"**Interval** {fmt(s0)} → {fmt(e0)}  ·  **Affected tractors** {', '.join(selected['tractors'])}")
        st.markdown("**Pipeline evidence** (exactly as written to `submission.json`):")
        st.markdown("\n".join(f"- {line}" for line in selected["evidence"]))

    # ---- aligned charts
    rule = AGGREGATIONS[agg_label]
    if rule == "1s" and (b - a) > pd.Timedelta(minutes=30):
        st.warning("1 s display is limited to intervals of 30 minutes or less; showing 10 s means instead.")
        rule = "10s"
    if not shown:
        st.info("Select at least one tractor to draw the charts.")
    else:
        bins = display_bins(d["tele"], shown, a, b, rule)
        bands = pd.DataFrame({"ts": [s0], "end": [e0]}) if s0 is not None else pd.DataFrame()
        if bins.empty:
            st.info("No telemetry in this interval for the selected tractors.")
        else:
            st.markdown(f"#### Aligned evidence · {fmt(a)} → {fmt(b)} · display bins: {rule}")
            in_view = pd.DataFrame([{
                "lane": x["class"], "label": f"{x['class']} · {', '.join(x['tractors'])}",
                "when": f"{fmt(x['start'])} → {fmt(x['end'])}",
                "start": pd.Timestamp(x["start"]), "end": pd.Timestamp(x["end"])}
                for x in dets if pd.Timestamp(x["start"]) < b and pd.Timestamp(x["end"]) > a])
            wf = flags[(flags.ts >= a) & (flags.ts < b) & flags.tractor_id.isin(shown)].copy()
            wf["state"] = wf.working.map({True: "working", False: "parked"})
            wf["end"] = wf.ts + pd.Timedelta(minutes=1)
            wf["time_utc"] = wf.ts.dt.strftime("%Y-%m-%d %H:%M UTC")
            working = alt.Chart(wf).mark_bar().encode(
                x=x_enc(a, b), x2="end:T", y=alt.Y("tractor_id:N", title="Working state", sort=TRACTORS),
                color=alt.Color("state:N", title="State", scale=alt.Scale(domain=["working", "parked"],
                                                                         range=["#9aa0aa", "#3a3d45"])),
                size=alt.Size("state:N", scale=alt.Scale(domain=["working", "parked"], range=[14, 4]), legend=None),
                tooltip=["tractor_id:N", alt.Tooltip("time_utc:N", title="minute"), "state:N",
                         alt.Tooltip("moving:Q", title="mean speed (m/s)", format=".2f")],
            ).properties(height=70)
            panels = [p for p in [
                lane_chart(in_view, a, b, None),
                working,
                line_panel(bins, "xte", "Cross-track error (m)", a, b, bands, affected, zero=True),
                line_panel(bins, "cn0", "Mean C/N0 (dB-Hz)", a, b, bands, affected),
                line_panel(bins, "min_cn0", "Min C/N0 (dB-Hz)", a, b, bands, affected),
                line_panel(bins, "sats", "Satellites (median)", a, b, bands, affected, height=90),
                line_panel(bins, "link", "RTK link up (%)", a, b, bands, affected, zero=True, height=90),
                line_panel(bins, "fixed", "RTK_FIXED (% of bin)", a, b, bands, affected, zero=True, height=90),
                step_panel(held(d["s4"], "s4", a, b), "s4", "Regional S4 (15 min)", a, b, bands),
                step_panel(held(d["kp"], "kp", a, b), "kp", "Kp (3 h)", a, b, bands, xtitle="Time (UTC)"),
            ] if p is not None]
            panels = [p.properties(width=CHART_WIDTH) for p in panels]
            chart = (alt.vconcat(*panels, spacing=8).resolve_scale(x="shared", color="independent")
                     .configure_legend(orient="top", direction="horizontal", titleOrient="left"))
            st.altair_chart(chart, width="content", theme="streamlit")  # keep the fixed panel width
            st.caption(
                f"Bins of {rule}: cross-track error and C/N0 are bin means (cross-track error keeps its sign), "
                "min C/N0 is the bin minimum, satellites the bin median, RTK link and RTK_FIXED the percentage of "
                "samples. Lines break at missing bins and never join different tractors. Working state is the "
                "pipeline's own per-minute flag (1-minute mean speed > 1.0 m/s). S4 and Kp are drawn as the latest "
                "published value at each time. Shaded band and dashed lines mark the selected detection. "
                "These charts show the inputs; they do not independently validate the detector.")
            rfi = d["rfi"][(d["rfi"].ts >= a) & (d["rfi"].ts < b)]
            adv = d["adv"][(d["adv"].ts >= a) & (d["adv"].ts < b)]
            if len(rfi) or len(adv):
                st.markdown("**SDA reports in this interval**")
                for r in rfi.itertuples():
                    st.markdown(f"- RFI `{r.id}` at {r.ts:%Y-%m-%d %H:%M:%S} UTC, confidence {r.confidence}, "
                                f"ellipse {r.semiMajor_km}×{r.semiMinor_km} km: {r.text} "
                                "(whether this time is the observation or the report time is not documented)")
                for v in adv.itertuples():
                    st.markdown(f"- Advisory `{v.id}` ({v.type}) at {v.ts:%Y-%m-%d %H:%M} UTC: {v.text}")

    # ---- development labels: separate, never predictions
    if window_name.startswith("Development"):
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
                lab_view = lab[(lab.start < b) & (lab.end > a)]
                if len(lab_view):
                    lanes = pd.DataFrame({"lane": lab_view["class"], "start": lab_view.start,
                                          "end": lab_view.end,
                                          "label": lab_view.id + " · " + lab_view["class"] + " · "
                                          + lab_view.tractors.map(", ".join),
                                          "when": lab_view.start.map(fmt) + " → " + lab_view.end.map(fmt)})
                    # Wrapped in vconcat like the main chart: a bare layered lane chart collapsed its lanes.
                    st.altair_chart(alt.vconcat(lane_chart(lanes, a, b, "Labels overlapping the charted interval")
                                                .properties(width=CHART_WIDTH)), width="content", theme="streamlit")
                if st.button("Score detections against development labels (official scorer, in-sample)"):
                    import score_submission
                    sub = {"detections": dets}
                    key = {"episodes": [{**r, "start": r["start"].isoformat(), "end": r["end"].isoformat()}
                                        for r in labels.to_dict("records")]}
                    res = score_submission.score(sub, key)
                    s1, s2, s3, s4c = st.columns(4)
                    s1.metric("Diagnostic (of 40)", f"{res['diagnostic_score']:.2f}")
                    s2.metric("Macro-F1", f"{res['macro_f1']:.3f}")
                    s3.metric("Onset credit", f"{res['mean_timing_credit']:.3f}")
                    s4c.metric("False positives", len(res["false_positives"]))
                    st.caption("In-sample: parameters were chosen on these same labels. Not evaluation performance.")

# ---------------------------------------------------------------- fleet comparison
with tab_fleet:
    st.subheader("Same interval across tractors")
    st.caption(f"Interval {fmt(a)} → {fmt(b)} (set on the Incidents tab). Statistics from raw 1 Hz telemetry; "
               "working share from the pipeline's per-minute flag.")
    tele = d["tele"]
    rows = []
    for t in TRACTORS:
        seg = tele[(tele.ts >= a) & (tele.ts < b) & (tele.tractor_id == t)]
        wf_t = flags[(flags.ts >= a) & (flags.ts < b) & (flags.tractor_id == t)]
        involved = [f"{x['class']} {pd.Timestamp(x['start']):%H:%M}-{pd.Timestamp(x['end']):%H:%M}" for x in dets
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
            p = pos.set_index("ts").groupby("tractor_id")[["lat", "lon"]].resample("10s").mean().dropna().reset_index()
            lat0, lon0 = p.lat.mean(), p.lon.mean()
            import math
            p["east_m"] = (p.lon - lon0) * 111320 * math.cos(math.radians(lat0))
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
    st.subheader("Methodology and limitations")
    st.markdown("""
- **Detections come from the pipeline** (`src/straightrows`): per-minute features → cause-agnostic flags →
  one test per cause → interval assembly → evidence. The dashboard does not detect anything itself.
- **Cross-track error** is the simulation's separate guidance-monitor channel (metres, signed). It is
  not computed from position.
- **Reported GNSS position is not ground truth**; it can be displaced during spoofing. Detection never uses it.
- **Working state** = the tractor's 1-minute mean speed > 1.0 m/s (speed is only 0 or 4.5 m/s, so at least
  14 moving seconds). Space weather, jamming, spoofing and equipment fault require a working tractor.
- **Short stops can be bridged:** a stop of at most 180 s inside one incident is joined, so the interval includes it.
- **Multipath is not detected.**
- **Confidence is a fixed heuristic value (0.5)**, not a calibrated probability.
- **Development results are in-sample:** parameters were chosen on the same 12 labeled episodes they are
  scored on. The evaluation window has no public labels.
- **SDA and RFI timestamp meanings are not documented** (interval start or end; RFI observation or report time).
  The pipeline uses the latest value at or before each minute.
- Merging the same cause across tractors can overstate which tractors were affected.
""")
    st.markdown("**Provenance**")
    st.dataframe(pd.DataFrame(
        [("Window", window_name), ("Window UTC", f"{fmt(a_w)} → {fmt(b_w)} (end exclusive)"),
         ("Data folder", data_dir), ("Git commit", git_commit()), ("Detections", str(len(dets)))]
        + [(f"Config.{k}", str(v)) for k, v in asdict(cfg).items()],
        columns=["Item", "Value"]), hide_index=True, width="stretch")
