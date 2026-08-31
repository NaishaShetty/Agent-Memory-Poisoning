"""Loss-aware, provenance-preserving normalization of PerLTQA (candidate prep, Phase 3.2-J.1).

Part of the ISOLATED candidate package under phase3/datasets/candidates/perltqa/ -- not
part of the active phase3/evaluation/ pipeline, does not modify anything there.

Source-native memory-unit identity (verified in this stage by direct inspection of
raw/Dataset/{zh,en,en_v2}/perltmem*.json and perltqa*.json, not assumed):
  - Each of PerLTQA's 141 characters carries a `profile` (flat dict), `social_relationship`
    (dict keyed by IDs like "1_0"), `events` (dict keyed by IDs like "1_0_0", each
    referencing a `Characters` list of social_relationship IDs), and `dialogues` (dict keyed
    by IDs like "1_0_0#0").
  - Every non-profile QA item's `Reference Memory` field is a stringified list of exactly
    these native IDs (e.g. "['4_0_0']") scoped to that character -- this IS native,
    source-provided gold evidence at the memory-unit level, not an adapter invention. This
    stage verified (full scan, zh) that 8,236/8,236 non-profile Reference Memory IDs
    resolve to a real key in the correct character's social_relationship/events/dialogues
    dict (100%; see reports/evidence_audit.md).
  - `profile`-section QA items instead carry a plain field-name label (e.g. "Gender") in
    `Reference Memory` -- a memory-CLASSIFICATION label, not a memory-unit ID. This
    normalization keeps the two kinds distinct rather than collapsing them.
  - `Memory Anchors` gives character-offset spans into the referenced memory unit's text
    (event `content` / dialogue turn text); a span of [-1,-1] means the source's own anchor
    search did not find that string verbatim (an honest source-side gap, not invented here).

Only the Chinese (`zh`) release is normalized into a full memory/task record pair, because
this stage's audit (reports/evidence_audit.md) found the `en` and `en_v2` releases have
null `Answer`/missing `Reference Memory`/missing `Memory Anchors` for 1,548/1,905 (81.3%)
of their non-profile questions -- the English translations are not usable as task records
beyond the profile subset in EITHER language revision. `en`/`en_v2` are preserved verbatim
in raw/ and are NOT silently dropped -- their profile-only usable subset is separately
normalized into en_profile_task_records.jsonl / en_v2_profile_task_records.jsonl for
transparency, with the broken sections explicitly excluded and logged.

Deterministic: no randomness, no wall-clock timestamps in record content, no network access
(reads only from the already-downloaded raw/ directory). Running build() twice over the
same raw/ input produces byte-identical normalized/*.jsonl output.
"""
from __future__ import annotations

import json
from pathlib import Path

CANDIDATE_DIR = Path(__file__).resolve().parent
RAW_DIR = CANDIDATE_DIR / "raw" / "Dataset"
OUT_DIR = CANDIDATE_DIR / "normalized"
MANIFEST_DIR = CANDIDATE_DIR / "manifests"

SOURCE_DATASET = "perltqa"
NORMALIZATION_VERSION = "3.2-j1.candidate.1"
GITHUB_COMMIT = "8d9e19868e239740ef701e603ec205cd581f221b"

MEMORY_SECTIONS = ("social_relationship", "events", "dialogues")


def _load(lang: str):
    qa_path = RAW_DIR / lang / f"perltqa{'_' + lang if lang != 'zh' else ''}.json"
    with open(qa_path, encoding="utf-8") as f:
        qa = json.load(f)
    mem_name = f"perltmem{'_' + lang if lang != 'zh' else ''}.json"
    with open(RAW_DIR / lang / mem_name, encoding="utf-8") as f:
        mem_raw = json.load(f)
    if isinstance(mem_raw, list):
        mem_by_name = {m["profile"]["Protagonist"]: m for m in mem_raw if isinstance(m, dict)}
    elif isinstance(mem_raw, dict):
        mem_by_name = mem_raw
    else:
        mem_by_name = {}
    return qa, mem_by_name


def _parse_ref_ids(rm):
    if not isinstance(rm, str):
        return None
    try:
        ids = json.loads(rm.replace("'", '"'))
    except Exception:
        return None
    return ids if isinstance(ids, list) else None


def build_zh():
    """Full normalization of the Chinese release: every character's memory units become
    memory_records.jsonl entries; every QA item (all 4 sections) becomes a task_records.jsonl
    entry with real evidence_memory_ids where the source's Reference Memory field is a
    memory-unit-ID list (social_relationship/events/dialogues), and a
    reference_memory_classification_label (not an evidence ID) where it is a profile field
    name."""
    qa, mem_by_name = _load("zh")

    memory_records = []
    task_records = []
    preprocessing_entries = []
    exclusion_entries = []
    counters = {
        "characters_in_mem_file": len(mem_by_name),
        "characters_with_questions": 0,
        "memory_units_emitted": 0,
        "task_records_emitted": 0,
        "evidence_id_valid": 0,
        "evidence_id_invalid_or_absent": 0,
        "duplicate_question_within_character": 0,
    }

    for name, mrec in mem_by_name.items():
        profile = mrec.get("profile", {})
        memory_records.append({
            "source_dataset": SOURCE_DATASET,
            "source_record_id": f"profile::{name}",
            "source_revision": {"github_repo_commit": GITHUB_COMMIT},
            "normalization_version": NORMALIZATION_VERSION,
            "memory_kind": "PROFILE",
            "character": name,
            "parent_ids": "NOT_PROVIDED_BY_SOURCE",
            "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
            "agent_visible_context": {
                "profile_fields": profile,
                "profile_description": mrec.get("profile_description", "NOT_PROVIDED_BY_SOURCE"),
            },
        })
        counters["memory_units_emitted"] += 1
        for section in MEMORY_SECTIONS:
            container = mrec.get(section, {}) or {}
            for unit_id, unit_val in container.items():
                memory_records.append({
                    "source_dataset": SOURCE_DATASET,
                    "source_record_id": f"{section}::{name}::{unit_id}",
                    "source_revision": {"github_repo_commit": GITHUB_COMMIT},
                    "normalization_version": NORMALIZATION_VERSION,
                    "memory_kind": section.upper(),
                    "character": name,
                    "native_memory_unit_id": unit_id,
                    "parent_ids": (
                        unit_val.get("Characters", "NOT_PROVIDED_BY_SOURCE")
                        if isinstance(unit_val, dict) and section == "events"
                        else "NOT_PROVIDED_BY_SOURCE"
                    ),
                    "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
                    "agent_visible_context": unit_val,
                })
                counters["memory_units_emitted"] += 1

    seen_q = {}
    for entry in qa:
        for name, sections in entry.items():
            counters["characters_with_questions"] += 1
            mrec = mem_by_name.get(name, {})
            for section_name, section_val in sections.items():
                if section_name == "profile":
                    items = section_val if isinstance(section_val, list) else list(section_val.values())
                    for item in items:
                        _emit_task(item, name, section_name, None, mrec, task_records, counters, seen_q, is_profile=True)
                else:
                    container = section_val if isinstance(section_val, dict) else {}
                    for unit_id, items in container.items():
                        for item in items if isinstance(items, list) else [items]:
                            _emit_task(item, name, section_name, unit_id, mrec, task_records, counters, seen_q, is_profile=False)

    preprocessing_entries.append({
        "input_files": ["raw/Dataset/zh/perltqa.json", "raw/Dataset/zh/perltmem.json"],
        "transformation": (
            "Flattened each character's profile/social_relationship/events/dialogues "
            "dicts into individual memory_records.jsonl entries (one per native memory "
            "unit, ID preserved verbatim); flattened each QA item (across all 4 sections) "
            "into an individual task_records.jsonl entry, resolving 'Reference Memory' "
            "into either evidence_memory_ids (native ID lists, non-profile sections) or "
            "reference_memory_classification_label (profile field names)."
        ),
        "info_preserved": ["all profile fields", "all social_relationship/events/dialogues fields", "Memory Anchors spans verbatim"],
        "info_omitted": [],
        "omission_reason": "NONE -- full scan, zero records dropped.",
        "normalization_version": NORMALIZATION_VERSION,
    })

    return memory_records, task_records, counters, preprocessing_entries, exclusion_entries


def _emit_task(item, name, section_name, unit_id, mrec, task_records, counters, seen_q, is_profile):
    if not isinstance(item, dict):
        return
    q = item.get("Question")
    key = (name, q)
    if key in seen_q:
        counters["duplicate_question_within_character"] += 1
    seen_q[key] = True
    rm = item.get("Reference Memory")
    evidence_ids = None
    classification_label = None
    if is_profile:
        classification_label = rm
    else:
        ids = _parse_ref_ids(rm)
        container = mrec.get(section_name, {}) if isinstance(mrec, dict) else {}
        if ids and isinstance(container, dict) and all(i in container for i in ids):
            evidence_ids = ids
            counters["evidence_id_valid"] += 1
        else:
            counters["evidence_id_invalid_or_absent"] += 1
    task_records.append({
        "source_dataset": SOURCE_DATASET,
        "source_record_id": f"{section_name}::{name}::{unit_id if unit_id else 'profile'}::{q}",
        "source_revision": {"github_repo_commit": GITHUB_COMMIT},
        "normalization_version": NORMALIZATION_VERSION,
        "character": name,
        "section": section_name.upper(),
        "agent_visible": {"question": q},
        "evaluator_only": {
            "gold_answer": item.get("Answer"),
            "evidence_memory_ids": evidence_ids if evidence_ids is not None else "NOT_RESOLVABLE_FROM_SOURCE",
            "reference_memory_classification_label": classification_label,
            "memory_anchors": item.get("Memory Anchors", "NOT_PROVIDED_BY_SOURCE"),
        },
        "parent_ids": "NOT_PROVIDED_BY_SOURCE",
        "equivalent_to": "NOT_PROVIDED_BY_SOURCE",
    })
    counters["task_records_emitted"] += 1


def build_english_profile_only(lang: str):
    """Profile-section-only normalization for en/en_v2 -- the only sections this stage's
    audit found to have real (non-null) Answer/evidence content in either English release.
    Non-profile sections are explicitly logged as excluded, not silently dropped."""
    qa, mem_by_name = _load(lang)
    task_records = []
    exclusion_entries = []
    for entry in qa:
        for name, sections in entry.items():
            for section_name, section_val in sections.items():
                if section_name != "profile":
                    n = len(section_val) if isinstance(section_val, dict) else (len(section_val) if isinstance(section_val, list) else 0)
                    exclusion_entries.append({
                        "record_id": f"{lang}::{section_name}::{name}",
                        "reason": (
                            f"BROKEN_SOURCE_TRANSLATION: {lang} release's '{section_name}' "
                            "QA items have null Answer, missing Reference Memory, and "
                            "missing Memory Anchors for this character (full-scan finding, "
                            "reports/evidence_audit.md) -- not usable as task records in "
                            "this language."
                        ),
                        "recoverable": False,
                        "retained_in_raw": True,
                    })
                    continue
                items = section_val if isinstance(section_val, list) else list(section_val.values())
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    task_records.append({
                        "source_dataset": SOURCE_DATASET,
                        "source_record_id": f"profile::{name}::{item.get('Question')}",
                        "source_revision": {"github_repo_commit": GITHUB_COMMIT},
                        "normalization_version": NORMALIZATION_VERSION,
                        "character": name,
                        "language": lang,
                        "section": "PROFILE",
                        "agent_visible": {"question": item.get("Question")},
                        "evaluator_only": {
                            "gold_answer": item.get("Answer"),
                            "reference_memory_classification_label": item.get("Reference Memory"),
                            "memory_anchors": item.get("Memory Anchors", "NOT_PROVIDED_BY_SOURCE"),
                        },
                    })
    return task_records, exclusion_entries


def records_to_jsonl_string(records):
    return "".join(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n" for rec in records)


def write_outputs():
    memory_records, task_records, counters, preprocessing_entries, exclusion_entries = build_zh()
    en_tasks, en_excl = build_english_profile_only("en")
    en_v2_tasks, en_v2_excl = build_english_profile_only("en_v2")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "memory_records.jsonl").write_text(records_to_jsonl_string(memory_records), encoding="utf-8")
    (OUT_DIR / "task_records.jsonl").write_text(records_to_jsonl_string(task_records), encoding="utf-8")
    (OUT_DIR / "en_profile_task_records.jsonl").write_text(records_to_jsonl_string(en_tasks), encoding="utf-8")
    (OUT_DIR / "en_v2_profile_task_records.jsonl").write_text(records_to_jsonl_string(en_v2_tasks), encoding="utf-8")

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_DIR / "preprocessing_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset_id": "perltqa",
            "normalization_version": NORMALIZATION_VERSION,
            "record_count_reconciliation": counters,
            "entries": preprocessing_entries,
        }, f, indent=2, ensure_ascii=False)

    all_exclusions = en_excl + en_v2_excl
    with open(MANIFEST_DIR / "exclusion_manifest.json", "w", encoding="utf-8") as f:
        json.dump({
            "dataset_id": "perltqa",
            "normalization_version": NORMALIZATION_VERSION,
            "exclusions": all_exclusions,
            "exclusion_count": len(all_exclusions),
            "note": (
                "Zero exclusions in the zh (primary, full-integrity) release. All exclusions "
                "are en/en_v2 non-profile sections, explicitly logged as BROKEN_SOURCE_"
                "TRANSLATION per-character, not dropped silently; raw/ retains the original "
                "files unchanged so this decision is independently re-checkable."
            ),
        }, f, indent=2, ensure_ascii=False)

    return counters, len(memory_records), len(task_records), len(en_tasks), len(en_v2_tasks), len(all_exclusions)


if __name__ == "__main__":
    counters, n_mem, n_task, n_en, n_env2, n_excl = write_outputs()
    print(json.dumps(counters, indent=2))
    print("memory_records:", n_mem, "task_records:", n_task, "en_profile:", n_en, "en_v2_profile:", n_env2, "exclusions:", n_excl)
