# Demo script — Straight Rows / FIELD SIGNAL (5 min + 3 min Q&A)

The detection results below match `outputs\submission.json` (SHA-256 `27ed40c5…`) and commit `91262e3`
(input-validation and display-only fixes on top of the earlier analysis; output unchanged). The "fresh clone,
41 tests, byte-for-byte" claim in the script was checked on that commit (README → *Current clean-copy results*).
Offline fallback for this version: open `outputs\demo-fallback-91262e3-20261114T191815Z\index.html`
(local only; `outputs\` is not in Git). Do not use `outputs\demo-fallback-91262e3-20261114T191722Z` (invalid).
All development numbers are **in-sample** (parameters were chosen on the same 12 labeled episodes).
Evaluation-window detections are **unverified predictions** — the evaluation labels are not public.

**Before you start**

```bat
.venv\Scripts\python.exe -m streamlit run src\dashboard.py
```

Open http://localhost:8501 (add `--server.port 8502` if busy). Wait for the fleet list to appear once
(first load runs the pipeline; afterwards navigation is quick). The app opens on the **Evaluation** window —
switch to **Development** for the labeled examples. Have `outputs\submission.json` open in an editor as backup.

---

## 1. Five-minute script

### 0:00–0:30 — The operator problem

> "Three autonomous tractors steer by GNSS. When guidance degrades, the operator needs to know *when*, *which
> tractors*, *why*, and *what to do* — because the right action differs: a solar storm means slow down or wait,
> jamming means stop and report, spoofing means stop and cross-check position, and a broken antenna means
> service that one machine while the others keep working. My system reads the farm telemetry plus space-weather
> and interference reports, and produces exactly that, with evidence you can check."

### 0:30–1:00 — Data and pipeline

> "The data is the organizers' **simulation**: 72 hours of 1-second telemetry from three tractors, plus space
> weather indices, scintillation, constellation advisories and RFI reports. Two days are labeled for development,
> one day is the evaluation day with no public labels. The pipeline is plain, rule-based Python: it summarizes
> each tractor-minute, flags symptoms, applies one rule per cause, joins minutes into incidents, and writes
> evidence computed from the measurements. The dashboard on screen calls that same code — it has no detector of
> its own."

*(Screen: fleet overview, click **Development**. Point at the T1/T2/T3 timeline: "9 pipeline detections over
May 4–5; colour plus a text code per cause.")*

### 1:00–2:30 — One strong episode: TRN-03 jamming (development, labeled)

*(Click **Open report** on row 3: "Suspected jamming · T1 T2 T3", 05-04 · 16:30–17:12 UTC.)*

> "This is labeled jamming, May 4, 16:30 to 17:12 UTC, all three tractors. The pipeline's interval is exactly
> the labeled one."

Point to, in order:

1. **Receiver health chart (opens by default):** mean C/N0 drops from about 45 to below the dotted 38 dB-Hz rule
   line on all three tractors at 16:30 and recovers at 17:12. Finding panel: *mean C/N0 27.6 dB-Hz* (45.0 in
   the 30 working minutes before).
2. **Finding → Pipeline interpretation:** rule "C/N0 below 38 dB-Hz with regional S4 below 0.2, tractor
   working", true in **42/42 minutes on each tractor**.
3. **Space / RF view:** S4 stays at **0.052–0.074**, far below the amber 0.2 line, so the pipeline does not
   attribute the loss to space weather. A coral tick: **RFI-001 timestamped 16:44 UTC (+15 min), 0.7 km** from the tractors' mean
   *reported* position.
4. **Guidance view:** cross-track error spikes — exported evidence says max **26.52 m** (median 0.99 m), RTK_FIXED
   **0%**, NO_FIX 11%.
5. **Recommended action:** "Halt and report suspected interference." Confidence 0.5 — "a fixed value, not a
   probability."

> "Notice RFI-001 is timestamped 15 minutes after onset — the rule doesn't use RFI reports; they're
> context only, and whether that timestamp marks observation or report arrival isn't documented."

*(Optional, 10 s: drag the replay slider to ~16:40; the inspector shows each tractor's raw 1-second C/N0 at that
exact second.)*

### 2:30–3:30 — A contrasting, ambiguous case: the May 5 storm (development, labeled)

*(Back to fleet → **Open report** row 8: "Suspected space weather · T1 T2 T3", 05-05 · 19:00–22:00 UTC.)*

> "This one is a strong match — labeled space weather, 19:00–22:00, interval exact — S4 is **0.418–0.466**, above
> the 0.2 line, all three tractors low for **180/180 minutes**. But two other labeled incidents happened *inside*
> this storm, and my system misses both."

- **Jamming inside the storm (TRN-05, 20:00–20:36):** fleet mean C/N0 steps from ~35 to **22.5** and back while S4
  stays ~0.44. My jamming rule requires S4 below 0.2, so it never fires; those minutes stay space weather.
- **Spoofing inside the storm (TRN-08, T3, 21:30–22:06):** T3's guidance error is above 1 m in 21 of the 30 storm
  minutes, but my spoofing rule requires C/N0 *not* to be low — which the storm makes impossible.
  *(Click **Next ›** → row 9, "Suspected spoofing · T3", 22:00–22:06.)* When the storm ends at 22:00 the rule
  fires — but only for 6 minutes. The panel even shows the error was already **1.67 m in the 30 minutes before**.
  The scorer counts this as my **one false positive** and TRN-08 as missed.

> "So absolute thresholds work in calm conditions but break when two causes overlap. The fix is to compare
> against the storm's own baseline — a step down inside a storm — which I haven't implemented."

### 3:30–4:15 — Validation and limitations

> "On the 12 labeled development episodes, with the organizers' scorer: diagnostic **27.29 / 40**, macro-F1
> **0.693**, onset credit **0.664**, **8 of 12** correct, **1** false positive. These are in-sample — I tuned on these
> same labels — so they're not a prediction of evaluation accuracy, which is unknown."

> "Misses: the two in-storm cases you just saw, and two multipath episodes. I built an opt-in multipath detector —
> it matches both labels, but it reports every recurring headland dip, about 160 per tractor per day, so I kept it
> **off** in the submission. Confidence is a fixed 0.5 for every detection. Merging the same cause across tractors
> can overstate which tractors were affected — the evidence says how many minutes the rule held on each one."

### 4:15–5:00 — Reproduction and practical value

> "It's reproducible: from a fresh clone, a Python 3.11 venv and the pinned requirements, the official download is
> checksum-verified, 41 tests pass, and one command regenerates the submission byte-for-byte:"

```bat
.venv\Scripts\python.exe src\run_pipeline.py --data data --output outputs\submission.json --github-handle reno-ogden --repo-url https://github.com/reno-ogden/straight-rows
```

> "No LLM or online service runs at analysis time. The practical value: an operator gets one report per incident —
> cause, tractors, UTC interval, action — and every claim links to a measurement they can inspect, including what
> the system is *not* sure about."

---

## 2. Example episodes (exact facts)

### A. TRN-03 — jamming (strong, labeled)

| | |
|---|---|
| Window | Development (May 4–5, labeled) |
| Interval | **2026-05-04 16:30–17:12 UTC** (42 min); label identical (onset +0 min, time IoU 1.00) |
| Tractors | T1, T2, T3 |
| Dashboard | Development → row 3 → Open report (opens on Receiver health) |
| Point to | Mean C/N0 27.6 dB-Hz vs 45.0 prior (per tractor T1 27.1, T2 30.7, T3 25.0); min C/N0 −6.0; median satellites 6; rule true 42/42 min on each tractor; S4 0.052–0.074; RTK_FIXED 0%, NO_FIX 11%; cross-track error max 26.52 m; RFI-001 timestamped 16:44 UTC (+15 min), confidence 0.6, 0.7 km from mean reported position |
| Can claim | Pipeline output matches the labeled jamming interval and tractors exactly; strong simultaneous C/N0 loss with quiet S4; RFI-001 is timestamped 15 minutes after onset |
| Must not claim | That the RFI report proves jamming (rules don't use RFI; timestamp meaning undocumented); that 0.7 km is the true distance (it uses reported position); real-time detection; anything about evaluation accuracy |

### B. TRN-02 storm with missed TRN-05 / TRN-08 (ambiguous, labeled)

| | |
|---|---|
| Window | Development |
| Intervals | Storm **2026-05-05 19:00–22:00 UTC** (matched exactly); TRN-05 jamming 20:00–20:36 (missed); TRN-08 spoofing T3 21:30–22:06 (missed); pipeline spoofing T3 **22:00–22:06** (false positive) |
| Tractors | Storm T1 T2 T3; spoofing T3 |
| Dashboard | Development → row 8 (opens on Space / RF) → Guidance view, focus **T3** → Next › to row 9 |
| Point to | S4 0.418–0.466; storm rule 180/180 min per tractor; fleet mean C/N0 35.0 → 22.5 → 35.0 around 20:00–20:36 with S4 flat ~0.44; T3 error >1 m in 21/30 storm minutes but C/N0 low in 30/30; row 9: 6/6 min, error median 3.99 m, "before: 1.67 m" |
| Can claim | Why both are missed, directly from the rules (jamming needs S4 < 0.2; spoofing needs C/N0 not low) |
| Must not claim | That the system handles overlapping storm + jamming/spoofing; that the 6-minute detection is a correct spoofing report (it is scored as a false positive) |

### C. (If asked) TRN-06 inside TRN-09 — overlapping causes on one tractor

Development rows 1 and 2: **equipment fault T2, 2026-05-04 12:00–14:00 UTC** (antenna dropouts to min C/N0 6.2
vs 26.3 on T1/T3; rule 108/120 min) and **spoofing T2, 13:19–13:54 UTC** (error median 3.52 m; onset +7 min vs
label 13:12). Each detection's evidence names the other as concurrent. Claim: concurrent causes stay separate.
Don't claim the spoofing onset is exact (it is 7 minutes late).

### Evaluation window (only if asked)

7 pipeline detections on 2026-05-06 (e.g. equipment fault T1 01:00–02:00, jamming T1 T2 T3 02:12–02:54, space
weather 13:00–16:00). Say: "**unverified predictions** — no public labels; accuracy unknown."

---

## 3. Click-by-click checklist

1. [ ] Dashboard running; fleet list visible; browser zoom 100%.
2. [ ] Click **Development** in the header (status line says "labeled · scores are in-sample").
3. [ ] Row 3 → **Open report** → heading "Suspected jamming … · T1 T2 T3".
4. [ ] Point at the Receiver health chart and the 38 dB-Hz dotted line.
5. [ ] Point at Finding → Pipeline interpretation "42/42 minutes".
6. [ ] Click **Space / RF** → S4 below amber line; coral RFI tick.
7. [ ] Click **Guidance** → cross-track spikes.
8. [ ] (Optional) drag replay slider; mention exact-second inspector.
9. [ ] **← Back to fleet** → row 8 → **Open report** (space weather).
10. [ ] Point at S4 0.418–0.466 and 180/180.
11. [ ] Click **Guidance**, focus **T3**.
12. [ ] Click **Next ›** → row 9 spoofing T3 22:00–22:06; point at "before: 1.67 m" and "6/6".
13. [ ] (Optional) **Details** → *Exported evidence* — "exactly what is in submission.json".
14. [ ] Back to fleet; end on the reproduction command.

If the dashboard fails: open `outputs\submission.json` and `docs/pipeline.md` (results table) instead.

---

## 4. Sixty-second emergency version

> "Three simulated GNSS-guided tractors; when guidance degrades, the operator needs when, which tractors, why,
> and what to do. My rule-based pipeline summarizes each tractor-minute, applies one rule per cause, joins minutes
> into incidents and writes evidence from the measurements. Example: labeled jamming on May 4, 16:30–17:12 UTC,
> all three tractors — C/N0 drops from 45 to about 28 dB-Hz while space-weather scintillation stays low, so it's
> called jamming and the action is halt and report; the interval matches the label exactly. On the 12 labeled
> development episodes I get 8 correct and 1 false positive — in-sample, so not an accuracy claim. It misses
> jamming and spoofing that happen *during* a solar storm, because my thresholds are absolute. Confidence is a
> fixed 0.5. Everything regenerates byte-for-byte with one command, with no AI or network at run time."

---

## 5. The pipeline in plain language

1. **Load** — read the files; every time becomes UTC.
2. **Summarize per minute** — for each tractor and minute: average and lowest signal strength (C/N0), average
   guidance error, average speed, how often the RTK correction link was up; plus the space-weather values in force.
3. **Flag symptoms** — "signal low" (< 38 dB-Hz), "guidance error high" (> 1 m), "link mostly down" (< 70%),
   "antenna dropout" (lowest C/N0 < 20 with normal average), "working" (moving > 1 m/s on average).
4. **One rule per cause** — space weather: all three low *and* S4 ≥ 0.2; jamming: low *and* S4 < 0.2; spoofing:
   error high while signal is fine; equipment fault: link down or dropouts. All require the tractor to be working.
   A minute can match more than one cause.
5. **Join into incidents** — consecutive minutes become one interval; gaps of up to 3 minutes on the same tractor
   are bridged; incidents shorter than 3 minutes are dropped; the same cause on different tractors starting within
   5 minutes is merged. Different causes are never merged.
6. **Evidence** — numbers measured over each incident: compared with the same tractor's previous 30 working
   minutes and with the other tractors; S4/Kp/Dst; minutes the rule held per tractor; nearby RFI reports.
7. **Export** — the official JSON template; the dashboard reads the same output.

---

## 6. Likely judge questions

**Why not trust reported GNSS position?**
Short: spoofing attacks the position itself, so it's not ground truth. Deeper: detection never uses lat/lon. It
appears only as descriptive context (distance to an RFI report's centre, position playback in the dashboard),
always labelled "reported" and "may be misleading during spoofing".

**How is cross-track error used?**
Short: as its own input — the simulation's guidance monitor, in metres. Deeper: the spoofing rule is a 1-minute
mean above 1 m while working and while signal strength is normal. It is not computed from reported position. It's
exactly 0 while parked, so it carries no information then.

**How are space weather and jamming distinguished?**
Short: by regional scintillation (S4). Deeper: both lower C/N0; with S4 ≥ 0.2 and all three tractors low it's space
weather, with S4 < 0.2 it's jamming. Kp was not used because in development it didn't track the episode ends
(e.g. it dropped to 3 while S4 and the degradation continued). Weakness: jamming *during* a storm is called space
weather (TRN-05).

**How are overlapping causes handled?**
Short: each cause is tested independently and never merged with another cause. Deeper: TRN-06 spoofing inside
TRN-09 equipment fault on T2 comes out as two detections that reference each other. Limitation: my absolute
thresholds can't see a second cause when the first one already pushes signal below the threshold (the storm case).

**What does confidence mean?**
Short: nothing calibrated — it is a fixed 0.5 for every detection, inherited from the starter. Deeper: I didn't
have enough labeled episodes to calibrate a probability honestly, so I don't present it as one.

**How were labels used?**
Short: only the 12 development episodes, for choosing parameters and scoring. Deeper: the loader reads the labels
file if it's present, but no detection, attribution, assembly or evidence step uses it; only `evaluate_dev.py`
(scoring) and the dashboard's separate labels section look at them. Because I tuned on them, the development
score is in-sample. There are no evaluation labels anywhere in the project.

**Is this real-time?**
Short: no, it's retrospective. Deeper: incidents are assembled after the whole window is available (bridging and
merging look ahead). Onset credit compares my start time with the labeled start; it is not alert latency.

**How were false positives evaluated?**
Short: with the organizers' published scorer on development labels — 1 false positive (spoofing T3 05-05
22:00–22:06). Deeper: I also inspected it: it's the tail of a real labeled spoof that my rule couldn't see during
the storm. For multipath I did not treat the scorer's exemption for short reports as proof they're harmless — that's
why the multipath detector is off.

**What are the main failure modes?**
In-storm jamming and spoofing (absolute thresholds); multipath off by default; cross-tractor merging can list a
tractor for longer than it was affected (the evidence shows per-tractor minutes, e.g. T2 33/42 in the evaluation
jamming detection); bridging can include normal minutes (evaluation T2 equipment fault: rule held 19 of 40 minutes);
the S4 cutoff was chosen by hand; RFI/SDA timestamp meanings are undocumented.

**How was AI used, and how was its work checked?**
Short: I used Claude (Anthropic) through Claude Code to write and revise much of the code, tests and docs, under
my direction — it's documented in the README and in every commit's co-author line. Deeper: each change was
checked by running the tests (41), regenerating the submission into a new folder and comparing it byte-for-byte,
running the official validator, scoring development labels with the official scorer, and inspecting episodes and
the dashboard by hand. No AI runs at analysis time.

**What would improve the system next?**
(1) Storm-relative rules: detect a step down from the storm's own baseline (fixes TRN-05/TRN-08). (2) A calibrated
confidence once there are more labeled episodes. (3) A held-out split instead of in-sample scoring. (4) Multipath
reported in a form an operator can use (e.g. one recurring-zone note) instead of hundreds of reports.
