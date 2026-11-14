"""Turn per-minute (tractor, cause) rows into detection intervals.

1. Runs of consecutive minutes per (tractor, cause); end = last minute + 1 min.
2. Optional: bridge same-(tractor, cause) gaps <= bridge_gap_s (done before step 3,
   so a flickering fault is not shredded into sub-minimum pieces and discarded).
3. Drop runs shorter than min_duration_s.
4. Merge same-cause runs across tractors when one starts within merge_gap_s of a
   previous one's end (starter rule), unioning tractors.
Different causes are never merged, so concurrent causes stay separate detections.
"""
import pandas as pd

MINUTE = pd.Timedelta(minutes=1)


def _runs(rows, window_end):
    out = []
    for (tr, cause), g in rows.sort_values("ts").groupby(["tractor_id", "cause"]):
        ts = g.ts.tolist()
        start = prev = ts[0]
        for t in ts[1:]:
            if t - prev != MINUTE:
                out.append({"tractor": tr, "cause": cause, "start": start, "end": min(prev + MINUTE, window_end)})
                start = t
            prev = t
        out.append({"tractor": tr, "cause": cause, "start": start, "end": min(prev + MINUTE, window_end)})
    return out


def _bridge(runs, gap):
    if gap <= 0:
        return runs
    out = []
    for r in sorted(runs, key=lambda r: (r["tractor"], r["cause"], r["start"])):
        last = out[-1] if out else None
        if last and last["tractor"] == r["tractor"] and last["cause"] == r["cause"] \
                and (r["start"] - last["end"]).total_seconds() <= gap:
            last["end"] = max(last["end"], r["end"])
        else:
            out.append(dict(r))
    return out


def assemble(rows, cfg, window):
    if rows.empty:
        return []
    runs = _bridge(_runs(rows, window[1]), cfg.bridge_gap_s)
    runs = [r for r in runs if (r["end"] - r["start"]).total_seconds() >= cfg.min_duration_s]
    merged = []
    # Same ordering as the starter (stable sort by start; ties keep tractor order).
    for r in sorted(runs, key=lambda r: r["start"]):
        hit = next((m for m in merged if m["cause"] == r["cause"]
                    and r["start"] <= m["end"] + pd.Timedelta(seconds=cfg.merge_gap_s)), None)
        if hit:
            hit["end"] = max(hit["end"], r["end"])
            hit["tractors"] = sorted(set(hit["tractors"]) | {r["tractor"]})
        else:
            merged.append({"cause": r["cause"], "start": r["start"], "end": r["end"], "tractors": [r["tractor"]]})
    return sorted(merged, key=lambda m: (m["start"], m["cause"]))
