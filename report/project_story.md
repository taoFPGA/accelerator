# taoFPGA — Project Story: Verification Phase

Chronological record of the problems encountered, how each was investigated, what was
tried, what actually fixed it, and what it taught the team. Written for knowledge transfer
into the final project book and for anyone picking up verification work on this design
later. Companion to `simulation_data.md`, which holds the numeric results referenced below.

---

## 1. The starting symptom: PBS jobs stuck forever, no visible reason

**Problem:** Two jobs submitted via `qsub -v TARGET=run_mm run_xrun.pbs` and
`qsub -v TARGET=profile_transformer run_xrun.pbs` sat in `qstat` showing `R` (running) for
45+ minutes with `SessID` and `Elap Time` both permanently `--` — i.e. no real session was
ever established, but the scheduler reported them as running.

**Investigation:** `qstat -f` on the jobs revealed `Exit_status = -3` and, critically,
`run_count` in the tens of thousands (48,224 and 44,398 respectively) — the scheduler was
silently retrying job launch many times per second in an invisible crash loop, never
surfacing a failure to the user.

**Outcome:** Root cause #1 found and fixed (see §2), but this turned out to be only the
first of several layers — the underlying infrastructure problem was not actually
software-fixable (see §5).

**Lesson:** A job sitting at `R` with no `SessID` is not "still starting" — it's a strong
signal to check `run_count` immediately.

---

## 2. `run_xrun.pbs` pointed at another user's directory

**Problem:** `run_xrun.pbs`'s `cd` target and `#PBS -o` output path both hardcoded
`/project/tsmc65/users/turgeme/ws/taoFPGA/...` — a different user's home directory, which
`rasksha` had no permission to even traverse (confirmed directly: `cd` failed with
`Permission denied`).

**Investigation:** Traced via `namei -l` on the full path, confirming the permission wall
at the `turgeme` directory itself. This looked like a copy-paste leftover from a shared
template.

**Fix:** Changed `cd` to `cd "$PBS_O_WORKDIR"` (portable, resolves to wherever the job was
submitted from) and pointed `#PBS -o` at the submitting user's own directory. Committed as
`0ed9392`.

**Outcome:** Necessary fix, but **not sufficient** — jobs kept failing the same way
afterward, which is what led to the deeper infrastructure investigation in §3.

**Lesson:** Fixing an obvious bug doesn't guarantee it was *the* bug. Always re-verify the
original symptom is actually gone before declaring victory.

---

## 3. Deeper PBS/SOCA infrastructure dig — hit a hard visibility wall

**Problem:** Even with the path bug fixed, resubmitted jobs still failed to provision a
compute node — stuck at `Can Never Run: Insufficient amount of resource: compute_node
(tbd`, a literal unresolved placeholder.

**Investigation:**
- `qmgr -c "print queue normal"` showed `default_chunk.compute_node = tbd` — every job gets
  this placeholder, resolved (in theory) by an external hook.
- `qmgr -c "print hook"` returned `unauthorized` — no visibility into the actual
  provisioning logic.
- `pbsnodes -a` revealed the environment provisions a **dedicated EC2 instance per job**
  (AWS SOCA), showing real `instance_id`, `asg_spotfleet_id`, `availability_zone` fields —
  but this session's assumed IAM role (`ComputeNodeRole`) got `AccessDenied` on
  `cloudformation:DescribeStacks`, `autoscaling:DescribeScalingActivities`, and even plain
  `ec2:DescribeInstances`. No path to see *why* the provisioning hook was failing from this
  side.
- `tracejob` failed with "couldn't find Job Id in logs" — it only works run from the PBS
  server itself, not this login node.

**Outcome:** Compiled findings into a structured report for the cluster admin (job IDs,
`Exit_status=-3`, `run_count` figures, the per-job EC2 provisioning pattern, and exactly
which AWS permissions this session lacked) — since this was now genuinely beyond what could
be diagnosed or fixed from the user side.

**Lesson:** Know when to stop self-diagnosing and hand off a precise, evidence-backed report
instead of continuing to guess blind.

---

## 4. Admin said "should be fixed now" — retested, found it wasn't (reliably)

**Problem:** After an admin update claiming the issue was resolved, resubmission was tested
three separate times.

**Investigation (all three watched live, 3–15 minutes each, with a safety kill-switch on
any crash-loop signature):**
- Job 17: progressed further than before — `(tbd)` → `(job)` → an actual EC2 instance
  provisioned, and its PBS node state eventually reached `free` (healthy) after ~7–8
  minutes. Killed right as it became usable, before it got to actually simulate anything.
- Jobs 18 and 19 (later, separate attempts): **zero progress** in a full 15 minutes each —
  no node ever provisioned, stuck at `(tbd)` the entire time.

**Outcome:** Confirmed the fix was partial and non-deterministic — sometimes works after a
long delay, sometimes never works at all, with no pattern found from the user side. This
was reported back honestly rather than assumed "fixed."

**Lesson:** "Should be fixed" claims need re-verification with the same rigor as the
original bug report — and intermittent failures need multiple independent trials before
being called reliable *or* unreliable.

---

## 5. The actual ground truth: PBS was never a supported path here

**Problem/revelation:** The user clarified directly — this is a BIU cloud environment used
for courses only. PBS is installed but was never actually configured to be usable, and no
proper cloud permissions for it are coming. All of §1–4's investigation, while individually
correct and well-evidenced, was chasing something that was never going to work by design.

**Outcome:** Full strategic pivot — stop using PBS/`qsub` entirely for any future work in
this project. Run every `make` target directly on the login node instead. This was saved as
a standing memory note so it persists across sessions.

**Lesson (the big one from this whole thread):** When infrastructure behaves inconsistently
in ways that don't fully make sense even after deep investigation, it's worth asking early
whether the infrastructure path is actually supposed to be used at all — rather than
assuming a fixable bug and spending hours chasing evidence for something structurally not
going to work. This alone was the single biggest time sink of the verification phase.

---

## 6. First real bug found once we could actually run things: `start_trans` forward reference

**Problem:** Running `make run_mm` directly (finally past the PBS layer) immediately hit a
genuine compile error: `MM_Ultra_tb.sv,229|23: 'start_trans': undeclared identifier`.

**Investigation:** `git blame` showed the `hw_latency_cycles` instrumentation block
(referencing `start_trans`) was added on 2026-07-20 by commit `9cde003`, positioned
**above** the existing `reg start_trans;` declaration (which dated back to the original
2026-03-01 import, commit `15036ce`). `MM_Ultra_tb.sv` had been silently uncompilable since
that commit — every PBS attempt in §1–5 had failed before ever reaching this point, so this
bug was never actually hit until now.

**Fix:** Moved `reg start_trans; initial start_trans = 0;` above the block that references
it — pure reordering, no logic change.

**Lesson:** A working simulation pipeline can hide a real compile bug indefinitely if
nothing ever gets far enough to hit it — this bug had been present for the entire PBS saga
without anyone knowing.

---

## 7. Full-scale run crashed the entire session

**Problem:** After the §6 fix, running `make run_mm` at full scale (200×96×160) crashed the
whole environment hard enough to require a full session restart — not just a failed
command.

**Investigation:** After restart, checked for orphaned processes (none found — the crash
took the whole host down, not just the process) and inspected the partial `xrun.log` left
behind. It showed the crash occurred during **"Generating native compiled code"** —
Xcelium's elaboration-time native code generation phase — after successfully compiling
individual DUT modules but while processing `MM_Ultra_tb`'s own generated code
(`words: 38249`).

**Hypothesis formed:** The testbench's `x_in_array`/`y_in_array` and `z_hard_array` are each
built via a `generate` loop that unrolls **one hardware object per scalar array element** —
at full scale, tens of thousands of individually-elaborated `assign`/`always` blocks. This
matched the elaboration-phase crash location exactly.

**Lesson:** When a crash takes down the whole session (not just the job), don't retry
blindly — inspect whatever partial log survived first; it usually points straight at the
phase that failed.

---

## 8. Proving the hypothesis without crashing the session again

**Problem:** Needed to confirm the elaboration-blowup theory and find the actual breaking
point, without risking a second full crash.

**Method:** Built a monitored-launch protocol (documented in full in `simulation_data.md`):
background the simulation, poll combined `xrun`-family RSS every 2 seconds, and hard-kill
at a 5,500MB safety threshold before the host itself could be endangered. Then staged the
testbench size up step by step: 16³ → 32³ → 64³ → 128³.

**Result:** Confirmed decisively. Memory grew **worse than quadratically**: 59MB → 76MB →
482MB → **>5,900MB and still climbing when killed** at 128³. The kill switch worked exactly
as designed — no second crash, full memory recovery confirmed afterward.

**Outcome:** This was presented to the user as two real options: restructure the testbench
(fix the actual root cause) or permanently accept a reduced validation scale. The team chose
to fix it properly, since full-scale verification is a hard project requirement.

**Lesson:** A reproducible, boxed experiment (with an automatic safety net) beats guessing —
this is what turned "the cloud crashed, we don't know why" into a precise, provable root
cause with exact before/after numbers.

---

## 9. The structural fix: on-demand packing instead of pre-elaborated arrays

**Problem:** Needed to eliminate the per-element `generate` unrolling without changing any
simulated behavior.

**Fix:** Both `x_in_array`/`y_in_array` (read one word per cycle, indexed by an address
counter) and `z_hard_array` (read only inside the final checker loop) were replaced with
`automatic` SystemVerilog functions (`pack_x_word`, `pack_y_word`, `unpack_z_word`) that
compute the needed word **at runtime, on demand**, instead of pre-elaborating every possible
word as a separate hardware object. Same bit-packing math, verified index-for-index
equivalent before implementation.

**Result:** Full-scale (200×96×160) now runs in **~51MB peak, ~4 seconds** — down from a
guaranteed session crash. Functional output is bit-for-bit unchanged (confirmed via the
64³ hardware-latency figure being identical before and after: 2,894 cycles both times).

**Lesson:** `generate` loops are elaboration-time constructs — appropriate for structurally
parallel hardware, wrong for "materialize a big lookup table," which a procedural
function handles far more cheaply at effectively zero elaboration cost.

---

## 10. A separate, pre-existing bug found along the way: GELU/Softmax scale mismatch

**Problem:** While investigating the pipeline, discovered `Softmax_control`'s
`scale_out_input` was 4 bits wide (documented valid range 7–12) but `gelu.v`/`EightGelus`'s
`scale` port was only 3 bits wide (max value 7) — the two IPs could only agree at exactly
scale=7. This was **already known and explicitly flagged in-code** (a "REAL GAP" comment in
`transformer_block_top.v`, left deliberately unfixed by whoever wrote the integration
blueprint) — not something introduced by this session's work.

**Investigation:** Read `gelu.v`'s actual shift logic and found it wasn't a trivial
port-width bump — the code assumed `in_scale` maxed out at 7 (`if (in_scale < 7) ... else //
== 7`), so simply widening the port would have silently mis-shifted any newly-representable
value 8–15, treating them as if they were 7. A real fix needed a genuine third branch (a
right-shift case) in both the input and output conversion stages.

**Fix:** Widened `in_scale` through `gelu.v` → `EightGelus.v` → `transformer_block_top.v`
to 4 bits, added the missing shift-direction branch in `gelu.v`, and extended `gelu_tb.sv`'s
randomized test range from 0–6 to 0–11 (the old range never even reached the boundary value
7). Committed as `bc9364c`.

**Lesson:** A documented, deliberately-deferred gap is still a real correctness bug — code
comments flagging "known limitation, not fixed here" are worth actively hunting down, not
just trusting will get addressed "later."

---

## 11. Same elaboration-blowup pattern found in `transformer_block_tb.sv` — and a second trap avoided

**Problem:** Once `MM_Ultra_tb` was proven correct at full scale, needed the full pipeline
(`transformer_block_tb.sv`) at real scale too for meaningful performance numbers ahead of
synthesis. That testbench had the exact same `x_in_array`/`y_in_array` generate-unrolling
pattern — just dormant because the testbench was deliberately kept tiny (4×32×32) up to
that point.

**Fix applied:** Identical `pack_x_word`/`pack_y_word` function replacement.

**Second trap found and avoided:** The file's own header comment explicitly warned that
`IN_Feature_Block_num`/`Weight_Block_num`/`OUT_Feature_Block_num` (256 at the time) must
have real headroom above the actual beat count used, not just match it — undersizing this
exact parameter had previously caused a register-overflow bug that permanently blocked the
weight stream (already fixed once before this session, commit `1c09132`). Scaling the
matmul dimensions up to 200×96×160 without also raising this parameter would have silently
reintroduced that exact bug. Bumped to 2400 (matching `MM_Ultra_tb`'s proven-safe headroom
ratio) before any size step-up.

**Result:** Verified clean at every step (32³ → 64³ → 128³ → 200×96×160), full scale
passing with 0/32,000 elements outside tolerance, 18,083-cycle end-to-end latency, ~53MB
peak.

**Lesson:** A fix applied once should always be checked for siblings elsewhere in the
codebase — and a file's own inline warnings (like the block-num headroom note) should be
read and respected, not just skimmed past, especially when about to do exactly the thing
the warning is about.

---

## 12. A third, smaller stale-code find in the same file

**Problem:** While re-reading `transformer_block_tb.sv` for §11, spotted that its local
`gelu_scale` register was still declared `[2:0]` (3 bits) even though the DUT-side fix in
§10 had already widened the actual port to 4 bits — meaning this testbench still could not
drive any scale value above 7, silently, even after the "real" bug was fixed.

**Fix:** Widened to `[3:0]`, and updated the accompanying comment (which still claimed
"7 is the only value valid for both ports" — no longer true post-§10) to reflect the actual
current state.

**Lesson:** Fixing a DUT port width doesn't automatically fix every testbench that drives
it — always grep for all consumers of a changed interface, not just the ones actively being
tested at the time.

---

## 13. Housekeeping along the way

- **Stale unused filelist removed:** `sourcecode/files.f` (a manual `xrun -f`-style filelist)
  was found to be untracked in git (never committed, ever), unreferenced by the current
  Makefile-driven build, and structurally stale — missing `tb/stall_monitor.sv` (now a hard
  dependency of `MM_Ultra_tb.sv`) and predating the entire `top/` directory. Confirmed dead
  and deleted.
- **Commit message mistake caught and fixed:** One commit accidentally carried over an
  unrelated prior commit's title via a copy-paste error in the message heredoc. Caught
  immediately, and since it hadn't been pushed yet, fixed cleanly with `git commit --amend`
  before pushing.

**Lesson:** Small process hygiene items (stale files, commit message accuracy) are cheap to
catch immediately and expensive to leave for someone else to puzzle over later.

---

## 14. Performance baseline established

With both testbenches finally correct and running at real scale, `run_transformer` and
`profile_transformer` (both re-run at full 200×96×160 scale, the latter via the same
monitored-launch protocol) together gave the first real performance picture of the
pipeline: an 18,083-cycle end-to-end latency, dominated by a ~93% stall rate on the final
output stage — a structural characteristic (single-buffered downsizer, no skid buffer in
`EightGelus`) that's already documented in code as a known blueprint simplification, not a
new defect. `profile_transformer`'s full-scale re-run (peak RSS 74.9MB, 8s) produced a real
toggle-coverage database and function-level profile data at representative scale, matching
the plain run's functional results exactly. This closes out the performance-analysis phase
and is now the baseline going into synthesis and timing/area closure. See
`simulation_data.md` §4 for full figures.

---

## 15. `prj.tcl` integration script silently drifted from verified RTL — six parameter mismatches found

**Context:** With the verification phase closed out (§14) and Vivado 2026.1 installed, review turned
to `scripts/prj.tcl` ahead of synthesis — an auto-generated Vivado IP Integrator (Block Design)
Tcl script, originally exported from someone else's earlier Vivado 2019.1 session, that builds
the full SoC-level integration: a Zynq-7000 (`xc7z020clg400-1`, PYNQ-Z1 board preset)
`processing_system7` talking to our `MM_ultra_top` core over AXI-DMA/AXI-Stream, with an
AXI-Lite control interface for software configuration. This script is external, adopted source
— not something written or maintained against our verified RTL — so there was no guarantee its
parameter values still matched what `MM_Ultra_tb.sv`/`transformer_block_tb.sv` had actually
verified.

**Problem found:** `prj.tcl` configures the `MM_ultra_top_0` block instance with
`CONFIG.array_size {24}`, but every verified testbench uses `A_size=16`. Investigating this one
value turned into a full audit, because it wasn't an isolated typo — it was a wrapper-layer
default that had simply never been updated.

**Investigation:**
- `grep`'d every `A_size`/`array_size` reference across the whole repo. Found a naming split:
  the core RTL (`MM_ultra.v` and everything it instantiates directly) uses `A_size`, correctly
  defaulting to 16 and matching every verified testbench. But the AXI/IP-Integrator wrapper
  layer above it (`MM_ultra_axi.v` → `MM_ultra_top.v` — the module `prj.tcl` actually
  instantiates) renames the same concept to `array_size`, with its own declared default of 24,
  never synced to the verified value.
- Read `MM_ultra_top.v`'s full parameter list and cross-referenced every one of its ten
  RTL-facing parameters against the corresponding verified testbench value, not just
  `array_size`.
- Result: **six mismatches**, not one:

  | Parameter | Verified value | What `prj.tcl`/`MM_ultra_top.v` actually used | How wrong |
  |---|---|---|---|
  | `array_size` | 16 | 24 (explicit in prj.tcl) | Visible but wrong |
  | `Weight_block_num` | 2400 | 2500 (explicit in prj.tcl) | Visible but wrong |
  | `in_feature_Block_num` | 2400 | 2500 (explicit in prj.tcl) | Visible but wrong |
  | `out_feature_block_num` | 2400 | 2500 (explicit in prj.tcl) | Visible but wrong |
  | `shift_width` | 10 | 5 (never overridden — silent) | **Invisible and wrong** |
  | `feature_width_block_num_width` | 5 | 6 (never overridden — silent) | **Invisible and wrong** |

  The last two are the ones that matter most: `prj.tcl` never mentions them at all, so they were
  silently pulling the stale RTL wrapper's own defaults with no trace in the integration script
  itself. A review that only checked what `prj.tcl` explicitly sets (i.e. just `array_size`)
  would have missed both.
- One more consequence found by tracing the actual signal path: `axis_dwidth_converter_0` and
  `axis_dwidth_converter_1` (which feed `MM_ultra_top_0`'s `s0_axis`/`s1_axis` inputs) had
  `M_TDATA_NUM_BYTES {24}` — sized to match the *wrong* `array_size=24` (24 lanes × 8-bit
  `data_width`). Fixing `array_size` alone without also fixing these would have left the
  upstream stream width converters mismatched against the corrected port width.

**Governing principle established (explicitly, by the user, for this and future integration
work):** our verified RTL/testbench values are the project's source of truth. Externally-adopted
integration scripts like `prj.tcl` get adapted to match what we've simulated and verified — never
the other way around, and never assumed correct just because they were generated by the
original tooling.

**Fix:** Applied all six parameter corrections to `prj.tcl`'s `MM_ultra_top_0` config block
(`array_size`→16, the three `*_Block_num` values→2400, and added the two previously-missing
`shift_width`→10 and `feature_width_block_num_width`→5 overrides so they're no longer silent),
plus the two downstream `axis_dwidth_converter_0`/`_1` width fixes (24→16 bytes).

**Outcome:** `prj.tcl` now matches the verified RTL configuration exactly. Not yet
end-to-end validated by actually running it through Vivado (open item, planned as part of the
synthesis pass) — one thing specifically flagged to verify then: whether
`axis_dwidth_converter_2`'s input side (fed by `MM_ultra_top_0/m0_axis`, also affected by the
`array_size` correction) auto-propagates its width correctly, since unlike the other two
converters it has no explicit input-side byte-count override to fix by hand.

**Lesson:** An externally-adopted integration script can look complete and authoritative (it's
long, detailed, and was machine-generated by the real tool) while still silently encoding stale
assumptions — and the most dangerous drift isn't in the values you can see and check, it's in
the values nobody thought to override at all, which fall back to whatever the original author's
module defaults happened to be. Auditing "does this match what we verified" has to check the
full parameter list against the RTL's own declarations, not just the specific value someone
already suspected was wrong.

---

## 16. Validating the six-parameter fix in Vivado — a stale version guard, a licensing side-quest,
    and a minor property-drift finding

**Context:** Before committing §15's six parameter fixes, the goal was to actually prove
`prj.tcl` builds and validates cleanly in the Vivado 2026.1 we'd installed — not just trust
that the corrected values were self-evidently right.

**Blocker #1 — the script's own version guard:** `prj.tcl` hard-blocks (ERROR + early
`return`) unless run in exactly Vivado 2019.1, the version it was originally generated with.
Sourcing it under 2026.1 aborted immediately, before `create_root_design` ever ran.
Investigated by neutralizing *only the version check* in a throwaway scratch copy (never
touching the committed file) and re-running, to see whether the actual IP Integrator commands
underneath were compatible with the new version or not. Result: **complete success** — the
design built, all IP/module checks passed, `validate_bd_design` reported zero errors, and
`design_1.bd` saved cleanly. Reopening the saved design and querying it directly confirmed
every one of §15's six fixes actually took (`array_size=16`, the three `*_Block_num`
values=2400, `shift_width=10`, `feature_width_block_num_width=5`), all three
`MM_ultra_top_0` AXI-Stream ports resolved to the correct 16-byte width, and —
the one thing flagged as uncertain in §15 — `axis_dwidth_converter_2`'s input side
auto-propagated to 16 bytes correctly with no explicit override needed. Based on this proof,
updated the real `scripts/prj.tcl`'s guard from a hard block to a non-fatal warning (commit
`fa4c006`), then re-ran the validation against the actual committed file (not just the
scratch copy) to confirm the real change works end-to-end before committing.

**Blocker #2 — Vivado's free tier needs an explicit license, not just a device selection:**
launching Vivado at all failed with "a valid license was not found," despite having installed
the free "Vivado Design Suite" edition. Turned out selecting free device families at install
time isn't sufficient on its own — AMD's current licensing model (the modern successor to the
old always-free WebPACK model) requires generating a no-cost, node-locked license certificate
through their account portal (Host ID = this machine's MAC address), separate from and after
the installer step. This is an account-tied action, so it was done by the user directly, not
automated; once downloaded, installed at `~/.Xilinx/Xilinx.lic` and wired into `setup.sh` via
`XILINXD_LICENSE_FILE` (commit `f881cc5`) so it's automatic for future sessions rather than a
step that gets forgotten.

**Non-blocker — missing PYNQ-Z1 board file:** `set_property board_part
www.digilentinc.com:pynq-z1:part0:1.0` also failed, because that board definition isn't in
Digilent's current public `vivado-boards` GitHub repo (checked directly — 26 boards listed,
PYNQ-Z1 not among them). Made non-fatal in the validation wrapper rather than chased further,
since `board_part` is only I/O pin-constraint metadata for physical hardware bring-up and has
no bearing on block-design elaboration — the actual chip part (`xc7z020clg400-1`) was accepted
fine on its own. Left as an open item for whenever physical PYNQ-Z1 bring-up starts.

**Minor finding worth tracking — `axi_dma_2` property drift:** during IP instantiation,
Vivado emitted `WARNING: [IP_Flow 19-3374] An attempt to modify the value of disabled
parameter 'c_m_axi_mm2s_data_width' from '32' to '64' has been ignored for IP 'axi_dma_2'`.
Non-fatal, and didn't block validation, but it means this specific property in `prj.tcl` is no
longer settable the way the script tries to set it in Vivado 2026.1 (an IP property-model
change between versions) — silently ignored rather than erroring. Not yet investigated
whether this affects `axi_dma_2`'s actual configured behavior; worth checking before finalizing
the DMA read-path (S2MM) configuration in the synthesis pass.

**Lesson:** A vendor-generated compatibility guard errs conservative by design — it can't know
in advance whether a 7-version-old script will still work, so it blocks first and asks
questions never. Testing that assumption empirically (in a disposable scratch copy, never the
committed file) turned "we can't even source this script" into "the script is fine, only six
specific values were wrong," which is a much smaller and more precise problem. Separately,
getting third-party/adopted tooling actually running end-to-end tends to surface a cluster of
unrelated environmental gaps (version guards, licensing, missing board files) that have nothing
to do with RTL correctness — worth triaging each one by whether it's actually blocking versus
just noisy, rather than treating all of them as equally urgent.

---

## 17. Synthesis phase kicked off — first baseline established, real gap found

**Context:** With `prj.tcl` validated (§16) and the toolchain fully working, moved into the
synthesis phase proper: establish an actual area/timing baseline for the transformer
accelerator, not just prove the integration script builds.

**Built:** `scripts/synth.tcl` — an in-memory, non-project batch synthesis script targeting
`xc7z020clg400-1` (PYNQ-Z1's part), synthesizing `transformer_block_top` (the full verified
pipeline, deliberately chosen over the AXI-wrapped `MM_ultra_top` sub-block that `prj.tcl`
integrates — "our transformer accelerator" reads as the complete pipeline, not just the
matmul core) with `-mode out_of_context` (this block has no board-level I/O of its own and is
meant to be instantiated inside the larger SoC, so OOC mode avoids Vivado inserting artificial
top-level IBUF/OBUF pairs that would skew utilization numbers). Applied the same
lesson from §15/§16 proactively this time: checked `transformer_block_top.v`'s own declared
parameter defaults against verified simulation values *before* writing the script, rather than
after finding a mismatch — they already matched exactly, so no `-generic` overrides were
needed.

**First run, tested with the same resource-monitored protocol used throughout the
verification phase:** clean synthesis, 0 errors, 0 critical warnings, 6 warnings, ~3.3GB peak
memory, ~3.5 minutes wall time. Full results logged in `synthesis_data.md` — summary:
utilization comfortable (LUTs tightest at 51.37%, everything else under 20%), timing passes
with positive margin at the 100MHz target (WNS +0.682ns, WHS +0.219ns, matching the Zynq PS7's
actual FCLK0 frequency from `prj.tcl`), and DRC surfaced one **real** finding worth tracking:
40+ instances (`REQP-1839`/`REQP-1840`) of block RAM control pins in `MM_in_buffer` and
`MM_buffer` driven by asynchronous set/reset — Xilinx's own DRC description warns this "may
cause corruption of the memory contents... not analyzed by the default static timing
analysis." This is exactly the class of issue that doesn't reliably surface in simulation
(a timing/silicon-corner race, not a functional-correctness bug a testbench would catch) — the
first concrete example this project has hit of synthesis catching something verification
structurally couldn't. Not yet root-caused or fixed; logged as the top open item for the next
synthesis pass.

**Lesson:** Passing simulation at full scale (as this design has, extensively — see the whole
verification phase above) proves functional correctness under the testbench's stimulus and
timing model, not synthesis-level or silicon-level correctness. Async-reset-driving-BRAM-control
is a textbook example of a class of bug that a behavioral simulator generally won't expose
(no real clock-domain/reset-assertion race modeled) but that DRC exists specifically to catch.
The two techniques are complementary, not redundant — this is the first time in this project
where synthesis found something simulation structurally could not have.

---

## 18. Closing the async-reset gap — a three-round whack-a-mole that kept revealing the same
    bug in new places

**Context:** §17 left one real gap open: `REQP-1839`/`REQP-1840`, 40+ DRC warnings about block
RAM control pins driven by asynchronously-reset registers in `MM_in_buffer`/`MM_buffer`. Asked
to root-cause and fix it, extending to `MM_out_buffer.v` too on the theory it likely had the
same latent issue (confirmed correct on inspection — it did).

**What looked like a three-file fix turned into a twelve-file one.** The actual memory
read/write `always` blocks in every buffer module were already reset-free and correct; the
problem was every address counter, valid-pipeline register, and FSM state register *feeding*
those ports, which universally used `always @(posedge clk or negedge rst_n)`. The fix itself
is simple and mechanical — drop `or negedge rst_n` from the sensitivity list, exactly Xilinx's
own recommended remedy — but finding the true extent of it took three rounds:
1. **Round 1** (`MM_in_buffer.v`, `MM_buffer.v`, `MM_out_buffer.v`, 37 blocks): the files
   directly named in Run 1's DRC violations. Re-synthesizing afterward, the warnings didn't go
   away — they just started pointing at a *different* driving register:
   `MM_out_data_valid_reg_array` inside `MM.v`, a module one level deeper in the hierarchy
   (instantiated inside `MM_buffer.v` as `u_MM`) that nothing in the original request had named.
2. **Round 2** (`MM.v`, 10 blocks): fixed, re-synthesized again. The violation moved *again* —
   this time to `draining_reg` inside `axis_downsizer.v`, a module with no relation to "buffers"
   at all (it's the width-adapter bridging `MM_ultra`'s output to Softmax's input). The
   connection: `out_data_ready` backpressure from outside `MM_ultra` entirely was reaching
   `F_array`'s enable logic combinationally. Also converted `PE_array.v`/`PE.v` (same round,
   proactively, since they sit inside the same subtree and a full audit showed they had the
   identical pattern) — 6 more blocks.
3. **Round 3** (`Softmax_control.v`, `Softmax.v`, `EightGelus.v`, `axis_upsizer_fifo.v`,
   `transformer_block_top.v`, 17 blocks): re-synthesized once more; `REQP-1839` finally cleared
   completely, but `REQP-1840` revealed yet another BRAM — `Softmax_control.v` has its own
   internal `in_data_buffer` memory, invisible in every prior run because Run 1's DRC report
   caps each rule at 20 reported violations and that cap was fully saturated by
   `MM_in_buffer`/`MM_buffer` instances until those got fixed.

Given a full project-wide audit (a simple `grep` count per file) had already enumerated every
remaining async-reset block with no more unknowns left to discover, round 3 converted the
entire remaining list in one pass rather than continuing to trace one violation at a time —
confirmed with the user first, since by that point the fix had grown well past the three files
originally scoped and into a module (`axis_downsizer.v`) with no "buffer" in its name at all.

**Total: 12 files, 60 `always` blocks converted**, re-verified against full-scale regression
(`MM_Ultra_tb`, `transformer_block_tb`) after every single round — all four re-runs produced
results bit-for-bit identical to the pre-fix baseline (21,544 cycles / 18,083 cycles, same
error counts), confirming the change really is invisible to simulation, exactly as predicted.

**Result:** `REQP-1839`/`REQP-1840` fully cleared — 0 instances, down from 40+. Two unplanned
bonuses came with it: two of Run 1's six `synth_design` warnings disappeared as a side effect
(the `fifo_mem_reg` set/reset-priority warning and its companion BRAM-inference failure — same
root cause, already flagged as Run 1 open item #2, resolved without being separately chased),
and utilization measurably *improved* (LUTs 51.37%→47.94%, Registers 16.75%→12.80%, F7/F8
Muxes down from 560/263 to 40/0) — removing async reset from ~60 registers let Vivado pack
flip-flops more efficiently. Full numbers in `synthesis_data.md`'s Run 2 section.

**Lesson:** A DRC violation naming one specific register is telling you about the *nearest*
offender on a signal path, not the full extent of the pattern — the same root cause can recur
at every hop upstream through a design's valid/ready handshake network, in modules that share
no obvious naming or folder relationship with where the symptom first appeared. A `grep`-based
project-wide audit for the anti-pattern itself (here: `negedge rst_n` across every file in the
relevant hierarchy) is more reliable than iteratively chasing wherever the next DRC violation
happens to point — it converts an open-ended "keep re-synthesizing until it's clean" loop into
a bounded, enumerable list, and in this case revealed the true scope (12 files) was known
before round 3 even started, making it safe to fix comprehensively in one pass instead of
continuing to whack-a-mole one file at a time.

---

## 19. Full SoC integration phase begins — discovering the accelerator had never actually been
    wrapped for it

**Context:** With the standalone accelerator fully optimized (§18) and validated, asked to move
into full SoC integration: run `prj.tcl` to generate the complete block design (Zynq PS + DMA +
accelerator), then full system synthesis, checking 100MHz timing and new warnings.

**First finding, before running anything:** `prj.tcl` as it existed only integrated
`MM_ultra_top` — the matmul engine alone, wrapped in AXI years ago via `MM_ultra_axi.v`/
`MM_ultra_top.v`. The complete pipeline this whole project has been calling "the transformer
accelerator" (`transformer_block_top`, MM→Softmax→GELU) had never been given AXI wrapping at
all — it only had raw signal ports, the way the testbenches drive it directly. Running `prj.tcl`
as-is would have integrated a different, narrower thing than what §14-18 actually verified and
optimized. Flagged this explicitly rather than silently proceeding with the mismatch; asked to
build the missing wrapper first.

**Built `transformer_block_axi.v` and `transformer_block_axi_top.v`**, mirroring
`MM_ultra_axi.v`/`MM_ultra_top.v`'s structure (AXI4-Lite register file + AXI4-Stream
slave/master wrapping) but sized for the full pipeline's larger config surface (7 config
registers instead of 4, plus a read-only status register for
`softmax_to_gelu_fifo_overflow`) and its output stream's `tkeep` signal (needed for GELU's
partial-final-beat case, which the matmul-only wrapper never had to handle). One deliberate,
explicit deviation from the existing wrapper's own convention: kept `transformer_block_top.v`'s
own parameter names instead of inventing lowercase aliases the way `MM_ultra_axi.v` did — that
renaming is exactly what caused the `array_size`/`A_size` drift bug chased across Sections
15-16. Set every default to already match the verified simulation values, so — unlike
`MM_ultra_top`, which needed 6 parameter corrections in `prj.tcl` — the new wrapper needed
**zero** `CONFIG` overrides. Applying a documented lesson before it could bite twice.

**Validated in isolation before touching `prj.tcl`:** synthesized the new wrapper standalone
first — 0 errors, 23 warnings, every one audited and traced to either pre-existing items or
benign patterns already understood from the original wrapper (implicit truncation connecting
32-bit AXI registers to narrower config ports; unused `AWPROT`/`ARPROT`, inherent to this
AXI4-Lite template and present in the original too, just never previously surfaced).

**Updated `prj.tcl`:** renamed every `MM_ultra_top_0` reference, removed the now-unnecessary
`CONFIG` block, left all downstream DMA/SmartConnect connectivity untouched since the new
wrapper deliberately kept identical pin names to the old one. Ran it — clean, `validate_bd_design`
reported zero errors, and reopening the saved design confirmed every parameter resolved
correctly with zero drift, `m0_axis` correctly narrowed to 4 bytes (matching GELU's output width
vs. the matmul's 16), `HAS_TKEEP=1` present, and — the one thing flagged as worth checking —
`axis_dwidth_converter_2`'s input side auto-propagated to the new width with no explicit
reconfiguration, exactly like the equivalent check in Section 16.

**Full SoC synthesis** (new `scripts/synth_soc.tcl`, on-disk project this time since the
block-design/wrapper flow needs real project files unlike `synth.tcl`'s in-memory OOC
approach): succeeded, 0 errors. **100MHz still met** (WNS +0.507ns, WHS +0.033ns — both margins
shrank somewhat from the standalone numbers, as expected with real interconnect/DMA fan-out
added, but stayed comfortably positive). Utilization grew proportionally to the added PS7-side
infrastructure (LUTs 47.94%→58.29%, Registers 12.80%→19.09%) — still well within the
`xc7z020`'s capacity. 207 warnings this time (up from 4), all individually categorized and
audited: every one traces to Xilinx's own pre-built `axi_dma`/`smartconnect` IP's unused
optional features, none of it attributable to our RTL or the new wrapper. **DRC stayed clean of
correctness-risk items** — zero `REQP-1839`/`REQP-1840`, confirming Section 18's async-reset fix
holds even with the newly-exercised `Softmax_control.v` BRAM path now driven by real
DMA/interconnect traffic patterns instead of the isolated OOC block. `ZPS7-1` ("PS7 block
required") disappeared on its own, since the real PS7 is now actually present.

**Lesson:** "Run the integration script" is not always as simple as running the existing
script — the very first step surfaced that the script's scope (`MM_ultra_top` alone) had
silently diverged from what "the accelerator" had come to mean everywhere else in this project
(the full pipeline). Catching a scope mismatch before spending a synthesis run on the wrong
target is worth the pause; and having already-documented lessons (parameter-naming drift,
audit-before-assume, resource-monitored validation) meant the new wrapper needed none of the
same fixes the original one did — proof that writing the lesson down in Sections 15-18 actually
changed how Section 19 got built, not just how it got debugged afterward.

---

## 20. First post-route sign-off baseline, and a DSP-inference architectural gap fixed

**Context:** With full-SoC synthesis established (§19), asked to take two sequential steps:
establish the project's first genuine post-route (place-and-route + power) baseline, then fix an
architectural anomaly flagged by the utilization data across §17-19 — DSP48E1 usage sitting at
just 5.91% while LUT usage climbed toward 58.29% at the full-SoC level, an inversion of what a
matmul-dominated systolic-array accelerator should look like.

**Step 1 — establishing the baseline.** Wrote `scripts/impl.tcl`: regenerate the synthesized
design via `synth_soc.tcl`, then run `opt_design → place_design → route_design` with default
directives (deliberately not `prj.tcl`'s pre-configured `impl_1` managed run, which uses a more
expensive multi-pass "Explore" strategy not worth the resource risk on this 7.4GB VM). Launched
under the same resource-monitored, kill-switch-protected protocol established back in §6-9 —
except the first monitoring attempt itself had a bug: it tracked only `vivado`'s immediate child
process via `--ppid`, completely missing the actual heavy process living several forks deeper in
the tree, and reported a flat, meaningless ~6.7MB RSS for the whole run while real memory use
climbed to 5.1GB used / 1.7GB available system-wide. Caught this by cross-checking `ps` directly
rather than trusting the monitor's own output, and immediately launched a corrected guard tracking
total system `MemAvailable` instead — robust regardless of process-tree shape. The run completed
successfully without needing the kill-switch, peaking at 1.7GB available (the closest this
project has come to its crash threshold since the original PE-array elaboration blowup in §7-9),
producing the first real signoff numbers this project has ever had: **WNS +0.361ns** at 100MHz
(vs. the post-synthesis-only estimate of +0.507ns — the expected direction, since real routing
delay is always worse than the synthesis estimate) and **Total On-Chip Power 1.741W** (1.590W
dynamic + 0.151W static).

**A path-collision bug surfaced immediately after.** `impl.tcl` sources `synth_soc.tcl` to
regenerate the design before implementation; both scripts independently declare a top-level `set
REPORTS ...` pointing at different paths. Tcl's `source` runs in the *same* variable scope as the
caller (not a fresh scope the way a function call gets), so `synth_soc.tcl`'s own assignment
silently overwrote `impl.tcl`'s — the genuine post-route reports, including the project's
first-ever `power.rpt`, landed in `reports/syn/soc/` instead of `reports/impl/`, overwriting what
had been post-synthesis-only data there. Caught by checking the target directory immediately
after the run reported success rather than assuming a clean exit meant a clean result — found it
empty, traced the cause, recovered the real data by copying it out before it could be lost, and
fixed the script by giving the variable a collision-proof name computed after the `source` call.

**Step 2 — the DSP-inference fix.** Before touching `PE.v`, checked whether the highest-payoff
fix (DSP48E1 dual-8-bit SIMD packing — two independent MACs sharing one DSP48E1 via a
shared-multiplicand trick) was actually achievable as a local edit. It isn't, for this array:
tracing `PE_line.v`'s actual cycle timing shows adjacent PEs do eventually process the same `x`
value, but staggered by exactly one cycle — the deliberate systolic skew — never simultaneously,
which is what the shared-multiplicand technique requires. True dual-MAC packing would mean
restructuring `PE_line.v`'s skew scheme and `PE_array.v`'s output-alignment logic to match, a
real microarchitecture change carrying real re-verification cost, not a `PE.v`-local edit.
Flagged this explicitly and let the lower-risk **partial 1:1 DSP mapping** be the chosen path:
force 12 of the array's 16 systolic rows (192 of 256 PEs) onto dedicated DSP48E1s via a new
`NUM_DSP_ROWS` parameter threaded `PE_array.v` → `PE_line.v` → `PE.v`, leaving 4 rows (64 PEs)
LUT-mapped, sized to fit the `xc7z020`'s 220-DSP budget alongside the ~13 already used by the
Softmax/GELU scalar pipeline.

**The fix's first attempt was a silent no-op.** Placing `(* use_dsp = "yes" *)` directly above
the `always @(posedge clk)` block containing the MAC produced byte-identical LUT/DSP/CARRY4
counts on re-synthesis — no error, just no effect. Per Xilinx UG901, `use_dsp` has to attach to
the register **declaration** holding the multiply result, not the enclosing procedural block; an
attribute on the `always` statement itself isn't a recognized attachment point and is silently
dropped during elaboration. Fixed by changing `psum_out` from `output reg` to `output wire`,
introducing a per-branch internal register (`(* use_dsp = "yes"/"no" *) reg psum_out_r`) inside
each `generate if/else` branch to carry the attribute correctly, and driving the port via a
continuous `assign` — functionally and cycle-timing identical to the original RTL, confirmed by
both branches' `always`-block bodies remaining byte-for-byte unchanged. Re-synthesized: DSP48E1
jumped 13→205, CARRY4 dropped 4,874→1,674 (standalone accelerator).

**Result:** Ran the same `impl.tcl` flow a second time against the DSP-fixed RTL for a genuine,
apples-to-apples post-route comparison (with the pre-fix reports preserved first, so the
comparison wouldn't be lost to the same overwrite risk just fixed). Post-route: **LUTs
30,276→15,363 (−49.3%), CARRY4-driven fabric usage collapsed accordingly, Total On-Chip Power
1.741W→1.687W (−3.1%)** — but **WNS also shrank, +0.361ns→+0.293ns (−19% margin)**, still
comfortably meeting 100MHz. This is a real, physically-grounded trade-off, not a partial failure:
packing 205 of the device's 220 DSP48E1 slices (93.18%) into a much denser physical footprint
than the previous LUT-diffuse implementation increases local placement/routing congestion around
those columns, which is exactly where the lost timing slack goes. The design's resource profile
has now visibly inverted — from **LUT-bound** (58.29% LUT vs. 5.91% DSP before this section) to
**DSP-bound** (93.18% DSP vs. 28.88% LUT after), with exactly 15 DSP48E1 slices of headroom left
on the device.

**Lesson:** A metric moving in the "wrong" direction after a fix isn't automatically a bug —
WNS shrinking while power and area both improved is a predictable physical consequence of
concentrating arithmetic into a denser footprint, and reporting it plainly (rather than only
reporting the metrics that improved) is what makes the result trustworthy. Separately: two
distinct tool/language gotchas surfaced in the same afternoon — an unrecognized Verilog attribute
placement that fails silently instead of erroring, and a Tcl scripting-language scoping rule that
silently overwrites state instead of erroring — and both were only caught by verifying the actual
output against expectation rather than trusting a clean exit code, the same discipline this
project has leaned on since §4's non-deterministic "should be fixed" claim.

## 21. Bitstream generated, and the repository audited for reproducibility

**Context:** With the DSP-fixed post-route baseline established (§20), asked to take the final
two steps to close out this phase: generate the actual bitstream from that signed-off
checkpoint, and audit `.gitignore` to make sure a fresh clone of this repository — potentially on
a machine without Vivado or Xcelium installed at all — would have everything needed to review
this project's real results, not just the scripts to regenerate them.

**Bitstream generation.** New `scripts/bitgen.tcl` reopens `scripts/soc_build/post_route.dcp` —
§20's final checkpoint, WNS +0.293ns at 100MHz, 205 of 220 DSP48E1 in use — directly, with no
re-synthesis or re-place/re-route needed, and runs `write_bitstream` followed by
`write_hw_platform -fixed -include_bit` for the `.xsa` hardware handoff. Both completed with the
cleanest possible signoff: the pre-bitstream DRC check reported **0 Errors**, and
`write_bitstream` itself reported **0 Warnings, 0 Critical Warnings, 0 Errors** — "Bitgen
Completed Successfully." `exports/design.bit` (4.05MB, verified as a genuine Xilinx bitstream via
`file`) and `exports/design.xsa` (1.08MB) are this project's first physically-implementable
hardware artifacts — not a separate or re-derived build, but the direct output of the exact
signoff numbers documented in §20.

**Repository integrity audit.** Framed the question plainly before touching `.gitignore`: if
someone clones this repo fresh onto a machine without any EDA tools at all, can they actually see
this project's real results, or only the means to regenerate them? The answer was no — every
report `.rpt` file this entire documentation has been citing specific numbers from (WNS, power,
utilization, stall-monitor percentages, the 0/32,000-tolerance verification result) was
gitignored. Un-ignored `reports/sim/`, `reports/syn/`, `reports/syn/soc/`, and `reports/impl/`'s
`.rpt` files so the actual data survives a clone, not just the prose describing it. For the
post-route checkpoint, chose not to un-ignore `scripts/soc_build/` wholesale — it's roughly 589
files of disposable Vivado project internals, fully regenerable from the tracked Tcl scripts, and
tracking all of it would work against the repo staying clean — and instead copied just the final
signoff checkpoint into `dbs/`, the directory `README.md` already documented as the intended home
for exactly this ("Design Checkpoints... intermediate snapshots of synthesized/routed design")
back when that directory was still empty scaffolding (the housekeeping-pass discussion earlier in
this project). Verified every category — documentation, scripts, RTL, the new checkpoint, the new
bitstream/xsa — with `git check-ignore` directly rather than assuming the edits were correct.

**Lesson:** Documentation that cites specific numbers is only as trustworthy as the artifacts
behind those numbers being actually reachable — a report file gitignored "to keep the repo clean"
quietly converts every number in `project_story.md`/`synthesis_data.md` from a verifiable fact
into an unverifiable claim for anyone without the exact tool licenses used to produce it. The fix
wasn't to track everything indiscriminately (that's exactly the mistake `scripts/soc_build/`
would have been) — it was to distinguish analysis-relevant artifacts, which earn their place in
version control precisely because they're the evidence, from disposable intermediate build
state, which doesn't. That distinction, not a blanket policy in either direction, is what
"the repository stays clean" and "the analysis is reproducible" turn out to have in common.

---

## 22. PYNQ-Z1 → PYNQ-Z2 hardware audit — same chip, but the DDR board preset doesn't travel

**Context:** The physical board actually on hand is a PYNQ-Z2 (TUL), not the PYNQ-Z1 this whole
flow was built against. Asked to audit the project for what needs to change to run on the real
Z2 and to write hardware bring-up instructions.

**Good news first:** `design_1_wrapper`'s only top-level ports are `DDR`/`FIXED_IO` (§19-21) —
there is no XDC in this repo at all (`inputs/` is empty), and none is needed, because the
accelerator has zero PL-side user I/O (no LEDs/switches/HDMI/audio pins are used — everything is
driven from software over AXI-Lite/AXI-DMA). Both boards use the identical
`xc7z020clg400-1` part, so the chip target, DSP/LUT/timing numbers throughout this document, and
the bitstream's fabric logic are unaffected by the board swap.

**Real gap found:** `scripts/prj.tcl`'s `processing_system7_0` CONFIG block hardcodes Digilent's
real PYNQ-Z1 board preset — not just the `BOARD_PART` string (already known non-fatal, §16/§20 —
that only disables the GUI's "Apply Board Preset" convenience button) but the actual
`PCW_UIPARAM_DDR_*` values themselves: DDR3 part number (`MT41J256M16 RE-125`), and per-pin
board-delay/DQS-to-CLK/trace-length numbers (`PCW_UIPARAM_DDR_BOARD_DELAY0-3`,
`PCW_UIPARAM_DDR_DQ/DQS/CLOCK_*_LENGTH_MM`, etc.) that model the PYNQ-Z1 PCB's specific DDR3
trace geometry. §20's optimistic read ("board files may not actually be a hard blocker for a
functional bitstream") is correct for *Vivado accepting the script and building a bitstream* —
but is a different claim from *DDR3 training succeeding reliably on physical PYNQ-Z2 silicon*,
since TUL's Z2 is a different PCB layout (and, per public TUL documentation, a different DDR3
device) than Digilent's Z1. This is exactly the class of gap simulation and synthesis DRC
structurally cannot catch (§17-18's lesson again, one layer further out: this time it's a
physical-layer PHY calibration concern, not a logic-timing one), and it was never actually
exercised — real hardware bring-up on PYNQ-Z1 itself was never attempted either (§20's open
item #5).

**Deliberately not fixed by hand-editing numbers:** the correct DDR3 board-delay/trace-length
values are derived from TUL's real PCB layout and DRAM part, not something to approximate or
guess — a plausible-looking wrong number is worse than the current, honestly-wrong PYNQ-Z1
number, because it would look fixed while still being fabricated. The correct fix is
installing TUL's official `pynq-z2` Vivado board files and re-applying the board preset to
`processing_system7_0` in the GUI (which pulls the authoritative numbers from that board
definition), then re-exporting `prj.tcl` via `write_bd_tcl` — not something to do inside this
Tcl file directly. Updated `BOARD_PART` in both `prj.tcl` and `synth_soc.tcl` to attempt
`tul.com.tw:pynq-z2:part0:1.0` (still non-fatal if the board files aren't installed, matching
the existing pattern) and left explicit comments on the `processing_system7_0` CONFIG block
flagging exactly which values are still PYNQ-Z1-specific, so this isn't silently forgotten the
way the `array_size` drift in §15 was.

**Unrelated bug found in the same pass, also blocking real hardware bring-up regardless of
board:** `apps/Defines.h` defines `MM_ADDR` from `XPAR_MM_ULTRA_TOP_0_BASEADDR` — a stale symbol
name from before the AXI-wrapped block was renamed to `transformer_block_axi_top` (§19's
renaming). The block Vitis will actually generate `xparameters.h` for is
`transformer_block_axi_top_0`, so this would fail to compile against any XSA generated from the
current design, on either board. Fixed to `XPAR_TRANSFORMER_BLOCK_AXI_TOP_0_BASEADDR`.

**Lesson:** "Same silicon part number" and "same board" are not the same claim — the Zynq
`xc7z020clg400-1` chip is identical between Z1 and Z2, so everything about this project that
lives inside the fabric (RTL, timing closure, DSP/LUT utilization, the lack of any XDC) travels
unchanged, but anything that models the physical PCB the chip sits on (DDR3 trace lengths, the
specific DRAM device, board-preset metadata) does not, and needs the target board's own
authoritative board file rather than a hand-patched guess.

---

## 23. Pivoted to the PYNQ/Jupyter run path, and found `apps/MM.py` was a stale, mismatched
    driver — rewrote it against the real register map

**Context:** Hardware access changed: the PYNQ-Z2 is now booting the standard PYNQ Linux image
from its SD card and being driven from Jupyter over a direct Ethernet link, not JTAG/UART with a
bare-metal Vitis app (§22's path). This meant `apps/MM.py` — the repo's existing PYNQ/Python
driver attempt — became the relevant file to get right, in place of `apps/main.cpp`/`Matrix.cpp`.

**Found `apps/MM.py` was comprehensively stale, not just outdated in one field.** Reading it in
full turned up four independent mismatches against the actual integrated hardware: `A_SIZE = 25`
(the real, synthesized systolic array is `A_size=16` everywhere else in this project);
hardcoded peripheral addresses in the `0xA00x0000` range that don't match `prj.tcl`'s real
address map (`0x43C00000` control, `0x40400000`/`0x40410000`/`0x40420000` for the three DMAs);
and — the significant one — it only ever configured the old 4-register `mm_*` control interface
and streamed a raw matmul result, with no knowledge of `softmax_scale_in/out` or `gelu_scale` at
all. That's consistent with this file predating §19's integration of the full
`transformer_block_axi_top` (MM→Softmax→GELU) pipeline in place of the bare `MM_ultra_top`
matmul-only wrapper — it was never updated for that change. Its one saving grace: the AXI DMA
direct-register-mode offsets it pokes (`0x00/0x04/0x18/0x28` for MM2S, `0x30/0x34/0x48/0x58` for
S2MM) are the real Xilinx-documented `axi_dma` register layout — those were never wrong, just
irrelevant once the base addresses and register count were.

**Rewrote `apps/MM.py` from scratch** as `TransformerAccelerator`, a small class wrapping the
real `transformer_block_axi_top_0` control interface and the three real `axi_dma_N` PYNQ IP
objects (resolved by name from the `Overlay`, not hardcoded addresses — the whole point of
building the driver from `design.hwh` instead of guessing). Register offsets and the
softmax_scale_out == gelu_scale constraint come directly from
`sourcecode/top/transformer_block_axi.v`'s own header comment; the default calibration constants
(`shift=9`, `softmax_scale_in=6`, `softmax_scale_out=7`, `gelu_scale=7`) are not new guesses —
they're the exact values `sourcecode/tb/transformer_block_tb.sv` already verified end-to-end
(`P_shift`/`P_softmax_scale_in`/`P_softmax_scale_out`/`P_gelu_scale`), so a first hardware run
using the driver's defaults is calibrated the same way the last verified simulation was, not an
arbitrary new configuration. `run()` mirrors `apps/Matrix.cpp`'s DMA-ordering discipline (arm the
S2MM receive channel before the two MM2S sends), waits on each channel with an explicit timeout
rather than blocking forever, and surfaces the `softmax_to_gelu_fifo_overflow` status bit after
the transfer.

**Explicitly scoped out, not silently skipped:** this driver validates that data moves through
the real pipeline correctly — transfer completes, output shape/dtype are right, no FIFO
overflow — it does not check output values against a bit-exact numerical golden model of
softmax+GELU. Building that would mean porting the real-valued reference model
`transformer_block_tb.sv` already chains from `MM_Ultra_tb.sv`/`Softmax_top_tb.sv`/`gelu_tb.sv`'s
individual golden models into Python, which is a real follow-up task, not something to fake with
an unverified approximation.

**Lesson:** A driver file that "looks done" (helper functions, matrix wrapper, DMA transfer
calls, error-checked shape validation) can still be built entirely against the wrong version of
the hardware — every symptom here (wrong array size, wrong addresses, missing registers) traces
back to one root cause: nobody had updated it since `transformer_block_axi_top` replaced
`MM_ultra_top`. The fix wasn't a patch to the wrong addresses; it was re-deriving the whole
register/DMA contract from the current RTL's own source of truth, the same discipline
Sections 15-16 established for `prj.tcl`.

---

## 24. Ported the verified golden model into Python, for bit-accurate hardware validation from Jupyter

**Context:** §23's driver validates that data moves through the real pipeline correctly, but
explicitly stopped short of checking output values against a numerical reference — asked to
close that gap for final project verification/documentation, by porting the actual golden model
already validated in simulation (not inventing a new one).

**Found the exact reference chain already exists, in three testbenches.**
`transformer_block_tb.sv`'s `initial` block chains `MM_soft` (matmul + round + saturate) ->
`Softmax_task` (numerically-stable softmax) -> `gelu_ref` (tanh-approximation GELU) row by row,
and its final `always` block compares the hardware's actual int8 output — dequantized by
`2**-gelu_scale` — against that chain within a **6-LSB tolerance**, because errors compound
across the two int8 quantization stages (softmax's output, then GELU's). `Softmax_top_tb.sv` and
`gelu_tb.sv` independently verify the softmax and GELU stages alone with the same math. This is
the project's real, already-verified ground truth — porting it faithfully was the job, not
writing a new golden model from a textbook formula that might not match what the RTL was
actually checked against.

**Cross-checked `MM_soft`'s rounding against the actual synthesized hardware before trusting
it.** `MM_soft` computes `(temp + (1<<(scale-1))) >>> scale` (round-then-shift) before saturating
to int8 — read `sourcecode/core/right_shifter.v` (the real rounding hardware inside `MM_ultra`)
line by line to confirm this isn't just a testbench convenience: `right_shifter.v` computes
`temp1_out = data_in >>> shift; temp2_out = data_in[shift-1] ? temp1_out+1 : temp1_out` (round up
if the top discarded bit is set) before the same saturate-to-int8 clamp. These are two different-
looking formulations of the identical round-half-up-on-arithmetic-shift operation — confirmed
mathematically equivalent, not just "close enough," before treating `MM_soft` as trustworthy.

**Ported to `apps/golden_model.py`:** `mm_soft()`, `softmax_ref()`, `gelu_ref()`, and
`transformer_golden()` (the full per-row chain) mirror the SV tasks/functions 1:1, and
`compare_to_hardware()` reproduces the testbench's exact final check — same dequantization, same
6-LSB tolerance — against a `TransformerAccelerator.run()` result from §23's driver. One quirk
preserved verbatim rather than silently "fixed": `Softmax_task`'s row-max seed starts at `0.0`,
not `-inf`, so an all-negative row would compute the wrong max — documented in the module
docstring as intentional literal replication of the verified reference, not an oversight, since
the goal is reproducing what was actually validated, not a mathematically idealized softmax.

**Lesson:** "Write a golden model" is ambiguous between two very different tasks — deriving
correct math from first principles, or faithfully reproducing the specific reference a design was
already verified against — and only the second one is actually useful for hardware validation
here, because the RTL's own quantization/rounding choices (confirmed by reading
`right_shifter.v` directly) are baked into what "correct" means for this design. A textbook
GELU/softmax implementation that didn't replicate `MM_soft`'s specific round-half-up scheme, or
used a tighter tolerance than the two-quantization-stage error the testbench already established
as expected, would produce false failures against genuinely correct hardware.

---

## 25. First real hardware run on the PYNQ-Z2 — `ol.ip_dict` named the control IP differently
    than assumed, caught before it could silently break `TransformerAccelerator`

**Context:** With `design.bit`/`design.hwh`/`MM.py`/`golden_model.py` uploaded to the board over
Jupyter's own content API (Samba write access to the board's share turned out to be read-only for
the `xilinx` account — not worth fighting; Jupyter's `/api/contents` PUT endpoint, authenticated
the same way the browser session is, worked directly once the content root's path convention was
corrected — it's already rooted at `jupyter_notebooks/`, so paths must NOT repeat that prefix),
ran the very first real command against the physical accelerator: `Overlay("design.bit")` +
`ol.ip_dict.keys()`.

**Result:** `['axi_dma_0', 'axi_dma_1', 'axi_dma_2', 'transformer_block_axi_top_0/s00_axi']` — the
overlay loaded and PYNQ found all four expected peripherals, but the control IP's key is
`transformer_block_axi_top_0/s00_axi`, not the plain `transformer_block_axi_top_0` §23's driver
assumed. PYNQ names a custom AXI-Lite peripheral like this after its actual AXI interface name
(`s00_axi`, from `transformer_block_axi.v`'s own S_AXI port), not the block instance, because
that's what the `.hwh` associates the address segment with — `self.ol.transformer_block_axi_top_0`
would have resolved to a hierarchy wrapper, not the register-accessible object, and every
`.write()`/`.read()` call in `configure()`/`fifo_overflowed()` would have failed the moment they
were exercised on real hardware.

**Fix:** replaced the hardcoded attribute access with `_resolve_ip()`, a small helper that
searches `ol.ip_dict` for a key equal to or prefixed by the expected instance name and walks the
resulting `/`-separated path via `getattr` — so it resolves correctly whether PYNQ exposes the IP
under its bare instance name or `<instance>/<interface>`, instead of hardcoding the one naming
convention this build happened to produce. Re-uploaded the fixed `MM.py` to the board the same
way.

**Also noted, not a defect:** the browser showed `Javascript Error: require is not defined`
alongside the correct Python output — JupyterLab's widget renderer failing on a legacy RequireJS
call `Overlay()` makes for its progress display. Cosmetic only; the Python-side result was
correct regardless.

**Lesson:** a driver can be internally consistent and still be wrong about how the *tool*
(PYNQ, here) names things — `ol.ip_dict` is the actual ground truth for what an overlay looks
like once built, and checking a key list before trusting an attribute-access guess is exactly the
kind of fact that only surfaces by running against the real generated `.hwh`, not by reading RTL.
Consistent with every other finding in this project's hardware bring-up phase (§22-24): each
layer — board, register map, IP naming — has its own source of truth, and none of them can be
safely assumed from a previous layer being correct.

---

## 26. First numerical hardware test FAILs against the golden model — real, reproducible,
    and not yet root-caused

**Context:** With `_resolve_ip()` fixed (§25), ran the first real accelerator test against
`golden_model.py`'s reference: an 8×32 feature matrix times a 32×32 weight matrix, comparing the
hardware's dequantized output to `transformer_golden()` within the testbench's own 6-LSB
tolerance.

**Result: 11 / 256 elements (~4.3%) outside tolerance.** Investigated methodically rather than
guessing at a fix:

1. **Ruled out a timing/race explanation.** Re-ran the identical seeded input three times —
   `bad_indices` and `max_abs_diff` came back bit-for-bit identical every time. Real electrical/
   timing noise would show at least some run-to-run variation; full determinism points at
   something structural instead.
2. **Ruled out the FIFO-overflow safeguard** (`fifo_overflowed()` read `False` throughout) and
   **ruled out `EightGelus.v`'s known missing-skid-buffer gap** (§19's documented limitation) —
   that would corrupt a contiguous run of a row from the drop point onward, not isolated,
   modest-magnitude single elements.
3. **Batched 15 additional random trials** and correlated every element's pass/fail against its
   `gap` (row-max minus that element's own matmul-output value). Failures cluster overwhelmingly
   at `gap=0` (the element ties the row's own maximum) — but reconstructing the actual failing
   row from the very first test (`np.random.seed(0)`, exact `mm_soft` output, done locally in
   Python rather than re-extracting from the board) showed one of the two failures, column 19,
   is the row's **unique, untied** maximum — so "duplicate ties" alone isn't the full story either.
4. **Every failing hardware output was exactly `0`** (not a rounding-magnitude miss) against
   golden values of ~0.05-0.10 — a flat, suspicious value rather than an approximation error.
5. **Traced `Softmax_control.v`/`Softmax.v`/`Exp_module.v`/`Ln_module.v` by hand**, specifically
   checking whether `exp(0)` (the case for an element exactly at the row max) could wrap to zero
   in `Exp_module.v`'s `U0Q25` (zero-integer-bit) output format. It doesn't — the module correctly
   saturates to `25'h1FFFFFF` (~0.99999997), refuting that specific hypothesis. Found one other
   suspicious spot (`Softmax.v`'s `x_max_ln_S9Q10` forces exactly `0` whenever the log-probability
   computation comes out non-negative, which should only happen near `x==max`), but hand-tracing
   its downstream effect predicts a **large** output (~127, near-maximum probability), not zero —
   so it doesn't cleanly explain the symptom either.

**Deliberately stopped hand-tracing rather than guessing further.** A 10-stage pipelined
fixed-point circuit is exactly the kind of thing manual RTL reading gets subtly wrong — the
responsible next step is a targeted simulation, not another round of eyeballing `always` blocks.
Wrote `sourcecode/tb/Softmax_row1_debug_tb.sv`: reproduces the exact 32-element failing row from
the first hardware run standalone through `Softmax_control` (not the full pipeline), with a
`$display` trace of every internal pipeline signal (`data_in_max`, `x_max_S9Q10`, `e_sum_U8Q12`,
`ln_U3Q10`, `x_max_ln_S9Q10`, both `Exp_module` outputs) every cycle, tagged by source column
index so column 10's and column 19's exact processing cycles across all 3 of
`Softmax_control`'s internal passes can be found directly in the log. Added a
`run_softmax_row1_debug` target to `sourcecode/sim/Makefile` alongside the existing four
suites. **Not yet run** — needs the project's Xcelium/PBS environment, which this session
doesn't have; this is the next concrete action, not a resolved finding.

**Lesson:** a hardware result that's real, reproducible, and doesn't match simulation-verified
software math is a genuine open finding, not something to paper over with a plausible-sounding
guess. The discipline that mattered here was the same one from §17-18 (the async-reset DRC gap):
narrow the failure with cheap, checkable tests before touching RTL (determinism check, FIFO
status, gap-correlation across 15 trials, reconstructing the exact failing input locally instead
of re-asking for board output) — and know when hand-analysis has stopped being reliable and a
real simulation is the only honest way to get the next fact.

---

## 27. Deployment logistics: getting files onto the board, and an older-numpy gotcha

**Context:** Getting `design.bit`/`design.hwh`/`MM.py`/`golden_model.py` from the dev machine onto
the PYNQ-Z2's Jupyter workspace, and getting the smoke test to actually run, surfaced two small
but real environmental facts worth recording so nobody re-discovers them the hard way.

**Samba share is read-only for the `xilinx` account.** The board's SMB share
(`\\<board-ip>\xilinx`) is reachable and lists directory contents fine, but `Copy-Item` onto it
fails with `UnauthorizedAccessException` — not a networking problem, a permissions one. Worked
around it by using Jupyter's own `/api/contents` REST endpoint instead (login via `/login` with
the board's password to get a session + `_xsrf` token, then `PUT` file content as base64 to
`/api/contents/<path>`).

**That API's path convention tripped a same-looking 500 error the first time.** The server's
content root is already `jupyter_notebooks/` — a path like `jupyter_notebooks/transformer_test/
design.bit` gets silently doubled server-side into
`/home/xilinx/jupyter_notebooks/jupyter_notebooks/transformer_test/design.bit` (a `No such file or
directory` 500, with an empty body unless read via `$_.ErrorDetails.Message` rather than the
default exception message). Paths must be relative to `jupyter_notebooks/` already, e.g.
`transformer_test/design.bit`, not repeat that prefix.

**The board's numpy predates 1.17** (no `np.random.default_rng`/`Generator` API) — use the legacy
`np.random.seed(n)` + `np.random.randint(...)` interface in any notebook code intended to run on
this board, not the modern `Generator`-based one that's become the default recommendation
elsewhere.

**Lesson:** deployment mechanics are not exempt from this project's own standing principle
(§16's rollup, restated at §22 and again here) that "same silicon" or "same framework" doesn't
mean "same everything" — a board's actual filesystem permissions, its content-API's root
convention, and its installed package versions are all board-specific facts that don't transfer
from documentation written for a generic PYNQ image, and are worth writing down once discovered
rather than re-derived by whoever automates this next.

## Summary of lessons learned (rollup)

1. **Verify infrastructure assumptions before deep technical investigation** — the PBS saga
   (§1–5) was the single largest time cost of this phase, and was ultimately not a bug at
   all.
2. **A fix isn't proven until the original symptom is confirmed gone**, ideally more than
   once (see §4's non-deterministic "should be fixed" claim).
3. **`generate` loops don't scale as lookup tables** — one hardware object per array element
   is fine for genuinely parallel structures, catastrophic for large data arrays; use
   on-demand functions instead.
4. **Headroom parameters must scale in lockstep with data size**, or a previously-fixed bug
   can silently reappear — read and respect a file's own inline warnings.
5. **A resource-monitored, kill-switch-protected staged rollout** is the safe way to find a
   scaling limit on a constrained shared host — this exact protocol prevented a second full
   session crash and produced the precise before/after data that proved the fix worked.
6. **A fix to a shared interface needs its consumers re-checked**, not just the interface
   itself.
7. **Small process hygiene mistakes** (stale files, commit messages) are worth fixing the
   moment they're noticed.
8. **Externally-adopted integration scripts aren't authoritative just because they were
   machine-generated** — audit their full parameter list against the verified RTL's own
   declarations, not just the one value you already suspect. The values nobody explicitly
   overrode (silently inheriting a stale wrapper default) were more dangerous than the ones
   visibly set wrong.
9. **A vendor version-compatibility guard is a conservative default, not proof of actual
   incompatibility** — test it empirically in a disposable copy before assuming a script needs
   a rewrite. Also: getting adopted tooling running end-to-end tends to surface a cluster of
   unrelated environmental gaps (version guards, licensing, missing board files) — triage each
   by whether it actually blocks the task at hand, not by treating all of them as equally
   urgent.
10. **Full-scale simulation and synthesis DRC catch different classes of bug** — passing
    verification proves functional correctness under the testbench's stimulus and timing
    model, not silicon-level correctness. Asynchronous resets driving block RAM control pins
    are a textbook example of something a behavioral simulator won't expose but DRC exists
    specifically to catch — don't treat a clean simulation pass as reducing the value of a
    synthesis/DRC pass, they're complementary, not sequential rubber-stamps.
11. **A DRC violation names the nearest offender, not the full extent of the pattern** — the
    same root cause can recur at every upstream hop in a signal path, in modules with no
    obvious naming relationship to the symptom. When a fix doesn't fully clear a warning class
    after one round, don't keep iteratively chasing wherever the next violation points — do a
    project-wide audit for the anti-pattern itself first, to convert an open-ended loop into a
    bounded, known list before fixing comprehensively in one pass.
12. **"Run the existing integration script" deserves a scope check before running it** — a
    script that builds cleanly can still target a narrower or different thing than what a
    project's own vocabulary ("the accelerator") has since come to mean. Cheaper to catch a
    scope mismatch before a run than after. Separately: documented lessons only pay off if
    they're actually applied on the next build, not just consulted when debugging — the new AXI
    wrapper needed zero of the fixes the original one did, specifically because Sections 15-16's
    lessons were applied while writing it, not after.
13. **Silent no-ops are more dangerous than errors, in both RTL attributes and scripting
    languages** — a `use_dsp` attribute misplaced above an `always` block, and a Tcl `source`
    call silently overwriting a same-named variable, both produced a clean exit code and zero
    warnings while doing nothing (or the wrong thing). A monitoring script has the identical
    failure mode: tracking the wrong process in a fork tree reports a plausible-looking but
    meaningless number instead of erroring. The only defense that caught all three was checking
    actual output against expectation (byte-identical utilization counts; an empty target
    directory; a flat RSS reading) rather than trusting that "it ran without error" meant "it did
    what I intended."
14. **A metric getting worse after a fix isn't automatically a regression** — it can be the
    direct, predictable physical cost of the fix's own mechanism, and is worth reporting exactly
    as plainly as the metrics that improved. Concentrating 256 MAC units from diffuse LUT fabric
    into 93% of the device's DSP columns was always going to trade some placement/routing
    freedom for area and power — the honest result is the trade-off stated together, not just
    the headline win.
15. **Documentation citing specific numbers is only as trustworthy as the artifacts behind those
    numbers being reachable** — gitignoring report files "to keep the repo clean" quietly turns
    every cited figure into an unverifiable claim for anyone without the same tool licenses.
    The fix isn't to track everything indiscriminately (that trades one failure mode for its
    opposite); it's distinguishing analysis-relevant evidence from disposable intermediate build
    state, and verifying the distinction actually holds (`git check-ignore`, checked directly)
    rather than assuming an edit did what it was meant to.
