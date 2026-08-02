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

With both testbenches finally correct and running at real scale, `profile_transformer` (at
the original small config) and the full-scale `run_transformer` together gave the first
real performance picture of the pipeline: an 18,083-cycle end-to-end latency at full scale,
dominated by a ~93% stall rate on the final output stage — a structural characteristic
(single-buffered downsizer, no skid buffer in `EightGelus`) that's already documented in
code as a known blueprint simplification, not a new defect. This is now the baseline going
into synthesis and timing/area closure. See `simulation_data.md` §4 for full figures, and
note the flagged open item: `profile_transformer` itself (with coverage) should be re-run
at full scale before the performance chapter is considered final.

---

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
