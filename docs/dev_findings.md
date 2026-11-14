# Development-window findings (labeled episodes only)

Data: May 4 00:00Z – May 6 00:00Z, 12 labeled episodes. All times UTC. No evaluation data used.
Regenerate: `python src/plot_dev_episodes.py` (→ `outputs/dev_plots/`) and
`python src/dev_episode_stats.py` (→ `outputs/dev_episode_stats.csv`).

"Pre" = affected tractors, 30 min before onset, moving samples only. "Unaff" = tractors not in the label, same interval.
Nothing below is a threshold; numbers are observed values.

## Cross-cutting observations

- **Labels cover working tractors only.** Every second of every episode has speed 4.5 m/s on the labeled tractors.
  TRN-01 starts exactly when the fleet starts moving (11:00); mean C/N0 was already ~31 dB-Hz while parked from 10:15.
- **Cross-track error is 0.000 while parked**, so it carries no information then.
- **Fleet moves in lockstep.** At both multipath episodes all three tractors report the same latitude (46.907026)
  at the same instant, ~0.0035° (~265 m) apart in longitude.
- **Recurrent headland dips.** On May 4 (quiet S4), outside non-multipath labels, each tractor shows ~180–200
  brief min-C/N0 dips (median 9 s, max 17 s, median low 29 dB-Hz), every ~5.8 min, all at latitude σ ≈ 5 m
  (north headland), 79 % of T3 dips co-timed with a T1 dip within 5 s. Only **two** are labeled (TRN-11, TRN-12).
  (Exploratory dip definition: ≥5 dB below a 121-s rolling median, ≥5 s. My choice, dev data only.)
- **RFI feed has one `ts` per report** and no separate observation time. The two reports near jamming labels
  arrived +14.8 and +10.7 min after onset. RFI-004 (05-05 10:36Z, conf 0.35, "may be storm-related receiver noise")
  sits during the storm with tractors parked and no label: a false alarm or unscored event.
- **Advisories:** ADV-2026-117 (routine, G14 unusable 08:00–09:30Z May 4) has no label near it.
  ADV-2026-118 (05-05 07:00Z, G4–G5 storm) precedes TRN-01 by 4 h.

## SPACE_WEATHER — TRN-01 (05-05 11:00–16:00, all), TRN-02 (19:00–22:00, all)

**Supporting**
- All three tractors degrade together and equally: mean C/N0 29.7 (TRN-01) and 32.4 (TRN-02) vs. 45.0 pre-TRN-02;
  median satellites 10–11 vs. 12; RTK_FIXED 0 % and 0.4 %; fix mostly DGPS/AUTONOMOUS; NO_FIX 0 % / 6 %.
- S4 high for the whole episode: 0.650–0.795 (TRN-01), 0.418–0.466 after 19:00 (TRN-02). Pre-TRN-02 S4 max 0.068.
- Episode ends coincide with S4 dropping: 0.795 → ~0.05 at 16:00; ~0.44 → 0.020 at 22:00.
- Dst −412 nT (TRN-01), −193 nT (TRN-02).
- RTK link 100 % ok: the correction link is not the cause.

**Contradictory / caution**
- Kp does not track the episode ends: 3.0 from 15:00 and from 21:00 while degradation continues for another hour.
- Kp 6.8 from 18:00, but S4 and farm C/N0 stay normal until 19:00 (Kp leads farm impact; S4 matches it).
- Mean C/N0 steps down again at 13:00 inside TRN-01 (≈31 → 29), matching an S4 rise to ~0.78.
- RTK link stays up, yet the fix leaves RTK, so "not RTK_FIXED" alone does not separate this from a link fault.

**Overlap:** TRN-02 contains TRN-05 (jamming, all), TRN-08 (spoofing, T3) and TRN-12 (multipath, T1).

## JAMMING — TRN-03 (05-04 16:30–17:12, all), TRN-04 (21:00–21:36, T1,T3), TRN-05 (05-05 20:00–20:36, all)

**Supporting**
- Abrupt, simultaneous step at onset and recovery, with a periodic sawtooth inside (tractors moving relative to a source).
  - TRN-03: mean C/N0 27.6 vs. 45.0 pre (min 4.9); min C/N0 down to −6.0; median sats 6; RTK_FIXED 0 %; NO_FIX 11.4 %; XTE max 26.5 m.
  - TRN-05: mean C/N0 22.5 vs. 35.0 pre (storm baseline); NO_FIX 30 %; min sats 3.
- Quiet space weather for TRN-03/04: S4 ≤ 0.074, Kp 2.0–2.3, Dst −14/−15 nT.
- RFI corroboration: RFI-001 arrived +14.8 min, conf 0.6, centre 0.69 km from the tractors (ellipse 3.44 × 1.04 km);
  RFI-002 arrived +10.7 min, conf 0.55, 0.94 km (ellipse 1.63 × 1.53 km).
- RTK link 100 % ok.

**Contradictory / caution**
- **TRN-05 sits inside a storm** (S4 0.427–0.448, Kp 6.8, Dst −166 nT) and has **no RFI report**. What separates it
  from storm degradation is the step at 20:00 while S4 stays flat (~0.44), plus the sawtooth.
- **TRN-04 has graded impact.** The unlabeled T2 also drops (mean C/N0 42.1 vs. 45.0) but less than T1/T3 (38.2 overall;
  T3 lowest in the plot); T2 sats min 11 and RTK_FIXED 100 %. The label boundary is a severity judgement.
- TRN-04 is mild: XTE max 1.2 m, RTK_FIXED 59 %, NO_FIX 0 %. Not every jamming case looks like TRN-03.

**Overlap:** TRN-05 with TRN-02 (space weather).

## SPOOFING — TRN-06 (05-04 13:12–13:54, T2), TRN-07 (05-05 00:30–01:18, T1), TRN-08 (21:30–22:06, T3)

**Supporting**
- Guidance error grows on one tractor while its signal health matches the others:
  - TRN-07: XTE median 6.00 m (max 12.6) vs. 0.01 unaffected; mean C/N0 44.98 vs. 45.01; RTK_FIXED 100 %; sats 12 vs. 12.
  - TRN-06: XTE ramps linearly 0 → ~3.9 m over 13:12–13:39, steps to ~6.0 m, then returns to ~0 at 13:54 (plot).
    Median 2.99 m vs. 0.02.
  - TRN-08: XTE median 2.00 m vs. 0.17 unaffected; mean C/N0 36.39 vs. 36.42.
- No RFI reports and no S4 change at onset (TRN-06/07: S4 ≤ 0.082, Kp 0.9).

**Contradictory / caution**
- **TRN-08 is inside the storm.** Storm XTE noise reaches 4.0 m on unaffected tractors and 5.1 m in the pre window,
  so XTE max does not separate it (4.5 vs. 4.0); the median does.
- TRN-06's signal health is degraded, but by the overlapping T2 antenna fault, not the spoof:
  mean C/N0 44.20 vs. 44.99 on the others, minimum C/N0 9.2.
- Reported lat/lon is not trusted during spoofing (guide), so position-based checks need care.

**Overlap:** TRN-06 lies entirely inside TRN-09 (equipment fault, same tractor T2). TRN-08 is inside TRN-02 (space weather).

## EQUIPMENT_FAULT — TRN-09 (05-04 12:00–14:00, T2), TRN-10 (05-05 02:00–02:48, T1)

**Supporting**
- Machine-specific: neighbours unaffected under quiet space weather (S4 ≤ 0.082, Kp 0.9).
  - TRN-09 (antenna dropouts): T2 minimum C/N0 down to 6.2 vs. 26.3 on T1/T3; mean C/N0 44.21 vs. 44.99;
    sats min 8 vs. 11; RTK link 100 %; RTK_FIXED 100 %.
  - TRN-10 (correction link): T1 `base_link_ok` 69.9 % vs. 100 % on T2/T3; RTK_FIXED 69.9 % (RTK_FLOAT when the link drops);
    C/N0 unchanged (44.99 vs. 45.02).
- TRN-10's link drops are intermittent: 10-s link fraction cycles between ~0.1 and 1.0 roughly every 4 min (plot).

**Contradictory / caution**
- TRN-09's XTE max of 6.51 m comes from the overlapping spoof (TRN-06), not from the fault (median 0.03 m).
- TRN-09's C/N0 effect is subtle in the mean (−0.8 dB); it shows mainly in the minimum C/N0 and satellite dips.
- Two fault types with no shared signal: dropouts (C/N0) vs. link (`base_link_ok`, fix state).

**Overlap:** TRN-09 contains TRN-06 (spoofing, same tractor).

## MULTIPATH — TRN-11 (05-04 14:04:18–14:04:35, T3), TRN-12 (05-05 19:00:35–19:00:52, T1)

**Supporting**
- 17-second dips at the north headland (latitude 46.907026): TRN-11 minimum C/N0 28.8 vs. ~40 around it;
  XTE median 0.12 m (small); RTK_FIXED 100 %; RTK link 100 %.
- Recurs on every pass at the same latitude, about every 5.8 min (see cross-cutting).

**Contradictory / caution**
- **The unlabeled tractors dip at the same instant and depth**: TRN-11 T1/T2 minimum C/N0 28.7/27.6 vs. 28.8 on T3;
  TRN-12 all three 15.7–16.1. Nothing in the telemetry singles out the labeled tractor.
- Only one dip per day is labeled ("representative"). How the representative was chosen is not documented.
  The scorer exempts other ≤3-min multipath reports but penalises duplicates overlapping the representative.
- TRN-12 is inside the storm (S4 0.418): baseline C/N0 is already low and RTK_FIXED is 5.9 %.

**Overlap:** TRN-12 with TRN-02 (space weather).

## Implications to verify (not yet implemented)

1. Use S4 rather than Kp for storm timing (already applied in `src/baseline.py`).
2. Score only working-tractor minutes.
3. Within a storm, look for step changes relative to the storm baseline (TRN-05) rather than absolute C/N0.
4. Spoofing: XTE growth relative to neighbours with matched C/N0; use median, not max, during storms.
5. Equipment fault: compare each tractor with its neighbours. Keep the link fault (`base_link_ok`) separate from dropouts (min C/N0, sats).
6. Multipath: report short headland dips individually; ask the organizers how the representative is chosen.
7. Ask the organizers whether RFI `ts` is the observation time or the arrival time.
