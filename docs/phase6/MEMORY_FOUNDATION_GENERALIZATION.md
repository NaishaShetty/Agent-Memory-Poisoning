# Stage 6.17 — Memory-Foundation Generalization

Status: 6.17 deliverable. Reports honest, current, freshly-executed evidence
about Mem0/A-MEM availability — including a correction to what a naive
reading of the brief might assume — plus one real, positive structural
finding about Phase 6's own design.

---

## 1. The Precise, Three-Way Distinction This Stage Must Not Flatten

The brief frames this as "Mem0 primary/validated, A-MEM subject to the known
limitation." **That framing does not hold unmodified in this session's
environment** — Stage 6.10 already confirmed neither `mem0`/`mem0ai` nor
`qdrant_client`/`chromadb` is installed here. Rather than force the brief's
assumed asymmetry, this stage draws the distinction that actually holds:

1. **Mem0 has real, historical, frozen validation** — Phase 3/4's own real
   campaign logs (e.g. `phase4/attacks/farma/milestone5_campaign_run_2026-09-
   11.txt`, inspected directly in Stage 6.10) show real `mem0` execution
   (`mem0/embeddings/huggingface.py` loading, real `add()` calls) — proof
   Mem0 was genuinely running in whatever environment produced that frozen
   evidence. This is real, not fabricated — the frozen logs are the evidence.
2. **A-MEM has never been validated for real-vendor identity-resolution
   behavior anywhere in this project's own history** — Methodology Section
   19.5 discloses this as a persistent, project-wide limitation, not specific
   to any one session: the two real, non-stub compatibility tests exist,
   ready to run, and have never yet run to completion because the isolated
   interpreter A-mem-sys needs has never been available even in the
   project's own typical working environment.
3. **Neither is available in THIS session** — confirmed by re-running the
   project's own existing test file live (Section 2), not merely inspected.

Collapsing these three into "both equally unavailable" would erase a real
distinction (Mem0's prior real validation vs. A-MEM's persistent, project-wide
absence of it) that matters for interpreting what Phase 6 can and cannot
claim.

## 2. Real, Freshly-Executed Evidence — Not Assumed From Prior Documentation

`phase5/tests/test_real_vendor_compatibility_gate.py` — this project's own,
already-frozen test file — was run live in this session
(`test_real_vendor_compatibility_gate_reports_honest_current_status`
re-executes it as part of Phase 6's own test suite, rather than trusting that
Methodology Section 19.5's description still holds without checking):

```
test_real_mem0_adapter_confirmed_unavailable_in_this_environment   PASSED
test_real_amem_adapter_confirmed_unavailable_in_this_environment   PASSED
test_real_mem0_retrieval_identity_chain_when_available             SKIPPED
test_real_mem0_identity_continuity_across_update_when_available    SKIPPED
```

The two "PASSED" results are themselves **positive confirmations of
unavailability** (real tests asserting the vendor SDK is not importable
here) — not failures, and not evidence anything is broken. The two "SKIPPED"
results are the real, non-stub identity-chain tests Methodology 19.5
describes, self-skipping exactly as documented, still never having run to a
real pass or fail in this environment.

**One correction to Methodology 19.5's own framing, noted precisely**: the
two real, non-stub compatibility tests found in this file are both named for
Mem0 specifically (`test_real_mem0_retrieval_identity_chain_when_available`,
`test_real_mem0_identity_continuity_across_update_when_available`) — there is
no equivalently-named A-MEM identity-chain test in this file. Methodology
19.5's prose describes the limitation as covering "Mem0 or A-MEM" generally;
the actual, concrete, real-code compatibility tests target Mem0's identity
behavior specifically. This is stated here as a documentation-precision note,
not a claim that A-MEM's own limitation is any less real — Section 1's point
2 (A-MEM's real-vendor behavior has never been validated at all) stands
regardless of which specific test file does or doesn't name it.

## 3. A Real, Positive Structural Finding: Phase 6 Is Foundation-Agnostic by Construction

Checked directly, not assumed: **no file under `phase6/defense/` imports
`mem0`, `chromadb`, `qdrant`, or any A-MEM-specific module** — confirmed by
`ast`-based import inspection across every Phase 6 defense module
(`test_no_phase6_defense_module_imports_a_specific_memory_foundation`). Every
Phase 6 decision function operates on `SignalContext`/`RetrievalCandidate`/
`AncestorRecord` — plain, Phase-6-native dataclasses, confirmed to be defined
in Phase 6's own modules, never a vendor SDK type
(`test_defense_components_operate_only_on_foundation_agnostic_types`). This
means Phase 6's defense logic is foundation-agnostic **by construction**, not
merely by absence of foundation-specific testing — it inherits this property
directly from Phase 3's own `CanonicalMemoryRecord`/`CanonicalEvent`
abstraction layer, which already sits above the Mem0/A-MEM distinction (per
Phase 3's own `MemoryFoundationAdapter` design,
`phase3/evaluation/foundations_real/mem0_real_adapter.py` and
`amem_real_adapter.py` being the two concrete implementations beneath it).

## 4. What This Does and Does Not License Claiming

**Licensed**: Phase 6's defense components will accept input built from
either foundation's real data without any code change, since nothing in
Phase 6 branches on which foundation produced a `CanonicalMemoryRecord`.

**Not licensed, and not claimed**: that Phase 6's defense has been *tested*
against a live Mem0 or A-MEM instance. It has not — Stage 6.10's wiring tests
used directly-constructed `CanonicalMemoryRecord`/`Phase5Event` objects (real
schema, real validation, but not sourced from an actual running Mem0/A-MEM
call). "Foundation-agnostic by construction" is a real, checked design
property; it is not a substitute for the live cross-foundation execution the
brief asks for, which remains blocked by the same environment limitation
Stage 6.10 confirmed.

## 5. Tests and Evidence

3 new tests: the foundation-specific-import check (zero found), the
foundation-agnostic-type-origin check, and the live re-execution of the
project's own real-vendor compatibility gate with its actual current output
asserted line-by-line.

**Full Phase 6 suite: 266 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged.

## 6. Limitations Carried Forward

1. Mem0 = real, historical validation exists (Phase 3/4's frozen campaign
   evidence) but not reproducible in this session, and never exercised
   against Phase 6's own new defense code in any session.
2. A-MEM = environment unavailable / unverified, exactly as instructed —
   never reported as "passed." This is a persistent, project-wide limitation
   (Methodology 19.5), not newly discovered here.
3. Phase 6's foundation-agnostic design is a real, structural property, not a
   substitute for live cross-foundation validation — stated plainly so it is
   never later cited as if it were.

## Verdict

**PASS** as a 6.17 deliverable. Both foundations' unavailability is reported
using the project's own existing, live-re-executed compatibility gate rather
than assumed from prior documentation, the real asymmetry between Mem0's
historical validation and A-MEM's persistent absence of it is preserved
rather than flattened, and one genuine positive finding (Phase 6's real,
checked foundation-agnostic construction) is reported without overclaiming it
as equivalent to live cross-foundation testing.
