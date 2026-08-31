"""Loss-aware, provenance-preserving normalization of ConvoMem (candidate prep).

Phase 3.2-J.1 built the ISOLATED candidate package under
phase3/datasets/candidates/convomem/. Phase 3.2-J.2 replaced this file's evidence
resolution logic with a deterministic, source-grounded, ambiguity-aware waterfall,
after a full-corpus feasibility investigation (see
phase3/evaluation/datasets/PHASE3_2_J2_CONVOMEM_FEASIBILITY.md) found the J.1 exact-match
adapter's 72.5% coverage could be raised to ~97.0% using ONLY exact-text and
structural-substring matching -- no fuzzy/semantic/LLM matching, no fabrication.

## Source structure (unchanged from J.1, re-verified in J.2)

  core_benchmark/evidence_questions/<category>/<N>_evidence/<uuid>_<Role>.json, each:
    {"evidence_items": [{"question","answer","message_evidences":[{speaker,text},...],
                          "conversations":[{"id": str, "containsEvidence": bool,
                                             "messages":[{speaker,text},...]}, ...],
                          "category","scenario_description","personId", ...},...],
     "checkpoint": str|null}

J.2 discovered two source fields J.1's audit had not surfaced: each `conversations[i]`
carries a genuine, globally-unique `id` field (verified: 0/74,391+ conversations reused
across a large scan) and a `containsEvidence` boolean (verified: always True within
evidence_questions/ -- it does not disambiguate anything here, it simply confirms every
bundled conversation is evidence-bearing). `conversations[i]`'s `id` is used below as the
source-grounded conversation identity component of every derived evidence reference.

## The resolution waterfall (mutually exclusive, in this exact order; see
`resolve_evidence_span` below and the feasibility report for full-corpus counts)

1. EXACT_RAW: message_evidences[k].text equals some message's text verbatim.
2. EXACT_NORMALIZED: equal after NFKC unicode normalization + whitespace collapse +
   ASCII-punctuation normalization (curly quotes/dashes/ellipsis -> ASCII) -- a
   deterministic, documented, semantically-inert transformation applied identically to
   both sides. Full-corpus impact: negligible (4/144,598) -- confirms formatting drift is
   NOT the real cause of the J.1 gap.
3. TRUNCATED_UNIQUE: the (normalized) evidence text is an exact contiguous substring of
   exactly ONE message in the item's conversations (96.7% of these are the evidence being
   a message's text minus a short leading conversational phrase, e.g. "Oh, absolutely."
   dropped from the front -- consistent with how the source's own generation pipeline
   appears to have extracted evidence spans). This is the dominant recovery mechanism:
   35,328/144,598 spans (24.4% of the full corpus) on the full-corpus audit.
4. MULTIMESSAGE_UNIQUE: the evidence text equals, or is contained in, the join of 2-4
   CONSECUTIVE messages within one conversation (plain or "speaker: text" labeled, joined
   with '', ' ', or '\\n') -- genuine multi-message/partial-span evidence, deterministically
   reconstructed from message order + speaker fields only. Full-corpus impact: small (3
   spans) once TRUNCATED_UNIQUE runs first (most multi-message-look candidates turn out to
   already be single-message substrings).
5. TRUNCATED_AMBIGUOUS / MULTIMESSAGE_AMBIGUOUS: the same text/structural relationship
   matches 2+ DISTINCT locations. Per this stage's explicit rule, these are NEVER guessed
   -- left `NOT_RESOLVABLE_FROM_SOURCE` with the ambiguity reason recorded. Full-corpus:
   75 + 13 = 88 spans (0.06%).
6. TOO_SHORT: normalized text under 30 characters is excluded from structural matching
   (steps 3-4) entirely -- short strings risk spurious substring hits that would not be a
   real evidence relationship. This threshold is a documented, deterministic policy
   choice, not tuned per-item. Full-corpus: 17 spans (0.01%).
7. UNRESOLVED: no exact or structural relationship found by any of the above. Full-corpus:
   4,268 spans (2.95%) -- genuinely dataset-inherent; most inspected examples are answers/
   evidence that appear to synthesize or paraphrase conversation content rather than quote
   it, which this stage's rules explicitly forbid trying to reconstruct via inference.

No case anywhere in this waterfall uses embeddings, an LLM, fuzzy/edit-distance matching,
or manual selection among candidates. Every identity produced is labeled
`ADAPTER_DERIVED_IDENTITY` and is never described as a native evidence ID.

Deterministic: no randomness, no wall-clock timestamps, no network access (reads only from
raw/). Running build() twice over the same raw/ input produces byte-identical output.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

CANDIDATE_DIR = Path(__file__).resolve().parent
RAW_DIR = CANDIDATE_DIR / "raw" / "core_benchmark" / "evidence_questions"
OUT_DIR = CANDIDATE_DIR / "normalized"
MANIFEST_DIR = CANDIDATE_DIR / "manifests"

SOURCE_DATASET = "convomem"
NORMALIZATION_VERSION = "3.2-j2.candidate.2"
HF_REVISION = "e3e9b39115b02346824c70d349350de738f8be41"

MIN_STRUCTURAL_MATCH_LEN = 30  # documented, deterministic; see module docstring

_PUNCT_MAP = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", " ": " ",
    "′": "'", "″": '"',
}


def normalize_text(s: str) -> str:
    """NFKC unicode normalization + whitespace collapse + ASCII-punctuation
    normalization. Deterministic, documented, applied identically to evidence text and
    message text on both sides of every comparison. Never stems, paraphrases, translates,
    or otherwise changes semantic content -- only canonicalizes equivalent renderings of
    the same characters."""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    for k, v in _PUNCT_MAP.items():
        s = s.replace(k, v)
    return s


def resolve_evidence_span(text: str, conv_msgs, raw_text_set):
    """Mutually-exclusive resolution waterfall for one message_evidences[k].text.

    conv_msgs: list of conversations, each a list of (speaker, raw_text, normalized_text)
    raw_text_set: set of every raw message text in this item's conversations (fast path)

    Returns a dict: {"status": ..., "locations": [...]} where each location is
    {"conversation_id": <native id>, "conversation_index": int, "message_index": int} for
    a single-message match, or {"conversation_id", "conversation_index",
    "message_index_start", "message_index_end"} for a multi-message match. `locations`
    has more than one entry only for the *_AMBIGUOUS statuses (never silently collapsed).
    """
    if text is None:
        return {"status": "UNRESOLVED", "locations": []}
    if text in raw_text_set:
        # Phase 3.2-J.3 addition (additive, does not change J.2's status/count taxonomy):
        # locate the matching message(s) so EXACT_RAW spans carry real location data too
        # (J.2 only recorded the status; J.3's foundation/metric integration needs a
        # concrete memory-id-level location for the 72.5%-majority EXACT_RAW case).
        # Status remains EXACT_RAW regardless of how many locations are found -- this does
        # NOT reclassify any span as *_AMBIGUOUS; J.2's full-corpus audit already
        # established 0 within/cross-conversation duplicate raw text for this component.
        locs = []
        for ci, cid, lst in conv_msgs_indexed(conv_msgs):
            for mi, (_, raw, _nm) in enumerate(lst):
                if raw == text:
                    locs.append({"conversation_id": cid, "conversation_index": ci, "message_index": mi})
        return {"status": "EXACT_RAW", "locations": locs}

    nt = normalize_text(text)
    exact_norm_locs = []
    for ci, cid, lst in conv_msgs_indexed(conv_msgs):
        for mi, (_, _, nm) in enumerate(lst):
            if nm == nt:
                exact_norm_locs.append({"conversation_id": cid, "conversation_index": ci, "message_index": mi})
    if exact_norm_locs:
        return {"status": "EXACT_NORMALIZED", "locations": exact_norm_locs}

    if len(nt) < MIN_STRUCTURAL_MATCH_LEN:
        return {"status": "TOO_SHORT", "locations": []}

    single_hits = []
    for ci, cid, lst in conv_msgs_indexed(conv_msgs):
        for mi, (_, _, nm) in enumerate(lst):
            if nt != nm and nt in nm:
                single_hits.append({"conversation_id": cid, "conversation_index": ci, "message_index": mi})
    if single_hits:
        if len(single_hits) == 1:
            return {"status": "TRUNCATED_UNIQUE", "locations": single_hits}
        return {"status": "TRUNCATED_AMBIGUOUS", "locations": single_hits}

    multi_hits = []
    for ci, cid, lst in conv_msgs_indexed(conv_msgs):
        n = len(lst)
        for start in range(n):
            for window in (2, 3, 4):
                end = start + window
                if end > n:
                    break
                chunk = lst[start:end]
                plain = [c[2] for c in chunk]
                labeled = [f"{c[0]}: {c[2]}" for c in chunk]
                for parts in (plain, labeled):
                    for sep in ("", " ", "\n"):
                        joined = sep.join(parts)
                        if nt == joined or nt in joined:
                            multi_hits.append({
                                "conversation_id": cid, "conversation_index": ci,
                                "message_index_start": start, "message_index_end": end - 1,
                            })
    if multi_hits:
        # de-duplicate identical location entries produced by multiple separator schemes;
        # sort by canonical JSON string for a stable order independent of Python's
        # per-process string-hash randomization (PYTHONHASHSEED), which would otherwise
        # make plain set-iteration order vary between runs and break determinism.
        dedup = sorted({json.dumps(h, sort_keys=True) for h in multi_hits})
        uniq_locs = [json.loads(h) for h in dedup]
        if len(uniq_locs) == 1:
            return {"status": "MULTIMESSAGE_UNIQUE", "locations": uniq_locs}
        return {"status": "MULTIMESSAGE_AMBIGUOUS", "locations": uniq_locs}

    return {"status": "UNRESOLVED", "locations": []}


def conv_msgs_indexed(conv_msgs):
    """conv_msgs as built by _build_conv_msgs is already (ci, cid, lst); passthrough
    helper kept so resolve_evidence_span reads top-to-bottom without re-deriving cid."""
    return conv_msgs


def _build_conv_msgs(conversations):
    out = []
    for ci, conv in enumerate(conversations):
        cid = conv.get("id")
        lst = []
        for m in conv.get("messages", []) or []:
            t = m.get("text")
            if t is None:
                continue
            lst.append((m.get("speaker"), t, normalize_text(t)))
        out.append((ci, cid, lst))
    return out


def _iter_source_files():
    if not RAW_DIR.exists():
        return
    for p in sorted(RAW_DIR.rglob("*.json")):
        yield p


def build(limit: int | None = None):
    memory_records = []
    task_records = []
    preprocessing_entries = []
    exclusion_entries = []
    counters = {
        "files_scanned": 0,
        "evidence_items_total": 0,
        "message_evidences_total": 0,
        "status_counts": {},
        "items_fully_resolved": 0,
        "items_partially_resolved": 0,
        "items_unresolved": 0,
        "null_or_empty_answers": 0,
    }

    files = list(_iter_source_files())
    if limit is not None:
        files = files[:limit]

    for path in files:
        counters["files_scanned"] += 1
        rel = path.relative_to(CANDIDATE_DIR / "raw")
        parts = rel.parts
        category = parts[2] if len(parts) > 2 else "UNKNOWN"
        evidence_count_bucket = parts[3] if len(parts) > 3 else "UNKNOWN"

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            exclusion_entries.append({
                "record_id": str(rel), "reason": f"JSON_PARSE_ERROR: {e}",
                "recoverable": False, "retained_in_raw": True,
            })
            continue

        checkpoint = data.get("checkpoint")
        for item_index, item in enumerate(data.get("evidence_items", []) or []):
            counters["evidence_items_total"] += 1
            question = item.get("question")
            answer = item.get("answer")
            if not answer or (isinstance(answer, str) and answer.strip() == ""):
                counters["null_or_empty_answers"] += 1

            convs = item.get("conversations", []) or []
            conv_msgs = _build_conv_msgs(convs)
            raw_text_set = {t for _, _, lst in conv_msgs for (_, t, _) in lst}

            mevs = item.get("message_evidences", []) or []
            resolutions = []
            for me in mevs:
                counters["message_evidences_total"] += 1
                res = resolve_evidence_span(me.get("text"), conv_msgs, raw_text_set)
                counters["status_counts"][res["status"]] = counters["status_counts"].get(res["status"], 0) + 1
                resolutions.append(res)

            statuses = [r["status"] for r in resolutions]
            resolvable = {"EXACT_RAW", "EXACT_NORMALIZED", "TRUNCATED_UNIQUE", "MULTIMESSAGE_UNIQUE"}
            n_resolved = sum(1 for s in statuses if s in resolvable)
            if mevs:
                if n_resolved == len(mevs):
                    counters["items_fully_resolved"] += 1
                elif n_resolved == 0:
                    counters["items_unresolved"] += 1
                else:
                    counters["items_partially_resolved"] += 1

            memory_record_id = f"{category}::{evidence_count_bucket}::{rel.name}::item{item_index}::conversations"
            memory_records.append({
                "source_dataset": SOURCE_DATASET,
                "source_record_id": memory_record_id,
                "source_revision": {"huggingface_dataset_sha": HF_REVISION},
                "normalization_version": NORMALIZATION_VERSION,
                "category": category,
                "evidence_count_bucket": evidence_count_bucket,
                "persona_file": rel.name,
                "generation_checkpoint": checkpoint if checkpoint is not None else "NOT_PROVIDED_BY_SOURCE",
                "parent_ids": "NOT_PROVIDED_BY_SOURCE",
                "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
                "agent_visible_context": {"conversations": convs},
            })

            evidence_refs = []
            for me, res in zip(mevs, resolutions):
                evidence_refs.append({
                    "status": res["status"],
                    "locations": res["locations"],
                })

            task_records.append({
                "source_dataset": SOURCE_DATASET,
                "source_record_id": f"{memory_record_id}::qa",
                "source_revision": {"huggingface_dataset_sha": HF_REVISION},
                "normalization_version": NORMALIZATION_VERSION,
                "category": category,
                "evidence_count_bucket": evidence_count_bucket,
                "memory_ref": memory_record_id,
                "agent_visible": {"question": question},
                "evaluator_only": {
                    "gold_answer": answer,
                    "evidence_resolution": evidence_refs if evidence_refs else "NOT_RESOLVABLE_FROM_SOURCE",
                    "evidence_identity_kind": (
                        "ADAPTER_DERIVED_IDENTITY (deterministic exact/structural text "
                        "matching against this item's own conversations, anchored to the "
                        "source's native conversation `id` field; NOT a native evidence-ID "
                        "field -- ConvoMem provides none)"
                    ),
                    "resolvable_evidence_count": n_resolved,
                    "total_evidence_count": len(mevs),
                },
                "parent_ids": "NOT_PROVIDED_BY_SOURCE",
                "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
            })

        preprocessing_entries.append({
            "input_file": str(rel),
            "transformation": (
                "One memory_records.jsonl entry per evidence_item (its bundled "
                "conversations, verbatim); one task_records.jsonl entry per evidence_item "
                "(question/answer), with evidence_resolution computed via the "
                "EXACT_RAW -> EXACT_NORMALIZED -> TRUNCATED_UNIQUE -> MULTIMESSAGE_UNIQUE "
                "waterfall (module docstring); ambiguous/too-short/unresolved spans keep "
                "their status explicitly rather than being silently dropped or guessed."
            ),
            "info_preserved": ["question", "answer", "message_evidences (verbatim)", "conversations (verbatim)", "checkpoint"],
            "info_omitted": [],
            "omission_reason": "NONE -- every field present in the source is carried over.",
            "normalization_version": NORMALIZATION_VERSION,
        })

    return memory_records, task_records, counters, preprocessing_entries, exclusion_entries


def records_to_jsonl_string(records):
    return "".join(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n" for rec in records)


def write_outputs(limit: int | None = None):
    memory_records, task_records, counters, preprocessing_entries, exclusion_entries = build(limit=limit)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "memory_records.jsonl").write_text(records_to_jsonl_string(memory_records), encoding="utf-8")
    (OUT_DIR / "task_records.jsonl").write_text(records_to_jsonl_string(task_records), encoding="utf-8")

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_DIR / "preprocessing_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset_id": "convomem",
            "normalization_version": NORMALIZATION_VERSION,
            "record_count_reconciliation": counters,
            "entries_count": len(preprocessing_entries),
        }, f, indent=2, ensure_ascii=False)

    with open(MANIFEST_DIR / "exclusion_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset_id": "convomem",
            "normalization_version": NORMALIZATION_VERSION,
            "exclusions": exclusion_entries,
            "exclusion_count": len(exclusion_entries),
        }, f, indent=2, ensure_ascii=False)

    return counters, len(memory_records), len(task_records), len(exclusion_entries)


if __name__ == "__main__":
    counters, n_mem, n_task, n_excl = write_outputs()
    print(json.dumps(counters, indent=2))
    print("memory_records:", n_mem, "task_records:", n_task, "exclusions:", n_excl)
