"""Map candidate flags + SDA context to causes.

Each cause has its own test. In multi-label mode every passing test yields a row,
so a machine fault and a spoof (or any pair) on the same tractor-minute are both
kept. Single-label mode keeps only the first passing cause in PRIORITY order,
which is exactly the starter baseline's if-chain.
"""
import pandas as pd

from .config import PRIORITY


def tests(f, cfg):
    storm = f.s4 >= cfg.s4_storm
    return {
        "SPACE_WEATHER": f.cn0_low & (f.n_cn0_low == 3) & storm,
        "JAMMING": f.cn0_low & ~storm,
        "SPOOFING": f.xte_high & ~f.cn0_low,
        "EQUIPMENT_FAULT": f.link_low | f.dropout,
    }


def attribute(f, cfg):
    t = tests(f, cfg)
    taken = pd.Series(False, index=f.index)
    rows = []
    for cause in PRIORITY:
        hit = t[cause] if cfg.multi_label else (t[cause] & ~taken)
        taken |= t[cause]
        rows.append(f[hit].assign(cause=cause))
    return pd.concat(rows, ignore_index=True)
