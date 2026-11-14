"""Cause-agnostic anomaly flags per tractor-minute. No attribution happens here."""


def flag(feat, cfg):
    f = feat.copy()
    f["working"] = f.moving > cfg.moving_mps
    f["cn0_low"] = f.cn0 < cfg.cn0_low_dbhz
    f["xte_high"] = (f.xte > cfg.xte_high_m) & f.working
    f["link_low"] = f.link < cfg.link_low_frac
    f["dropout"] = (f.min_cn0 < cfg.dropout_dbhz) & ~f.cn0_low
    # Fleet context: how many tractors show signal loss in the same minute.
    f["n_cn0_low"] = f.groupby("ts")["cn0_low"].transform("sum")
    return f
