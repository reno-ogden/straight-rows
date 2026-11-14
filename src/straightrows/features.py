"""Per-tractor, per-minute features with the SDA values in force at each minute."""
import pandas as pd


def minute_features(d, window):
    tele = d["tele"]
    feat = (
        tele.set_index("ts").groupby("tractor_id").resample("1min", include_groups=False)
        .agg(cn0=("mean_cn0_dbhz", "mean"), min_cn0=("min_cn0_dbhz", "min"),
             xte=("cross_track_error_m", "mean"), moving=("speed_mps", "mean"),
             link=("base_link_ok", "mean")).reset_index()
    )
    feat = feat.sort_values("ts")
    # Backward as-of joins: each minute sees the latest published Kp / S4 value.
    feat = pd.merge_asof(feat, d["kp"].sort_values("ts"), on="ts")
    feat = pd.merge_asof(feat, d["s4"].sort_values("ts"), on="ts")
    a, b = window
    return feat[(feat.ts >= a) & (feat.ts < b)].sort_values(["tractor_id", "ts"]).reset_index(drop=True)
