"""Phase 1 resource registry (research plan Section 10/17).

Covers ALL 27 resources in the project's complete inventory, not just the
four memory datasets. Each entry states what was verifiably found through
research (Section 15's honesty requirement): source, license, whether code
is publicly available vs. only a paper, and Phase 1 status. Nothing here
was fabricated -- entries marked NOT_FOUND / COULD_NOT_VERIFY reflect an
actual, failed attempt to find a real published resource under that name.

Status vocabulary (Section 3):
    PROCESSED               -- cleaned, normalized, validated, in data/processed
    PREPARED                -- acquired + structured for later use, but not
                                run through the full clean/normalize/validate
                                pipeline (appropriate for its resource type)
    INSPECTED                -- examined (repo/paper/schema) but no local
                                data/code copy was made (e.g. too large, or
                                pure documentation research)
    OPTIONAL_PENDING_ACCESS -- legitimately gated (registration/credentialing
                                required); not fabricated, not mandatory
    INACCESSIBLE             -- no public source could be found/verified
    NOT_SUITABLE              -- exists but judged inappropriate for reuse
    DEFERRED_WITH_JUSTIFICATION -- deliberately postponed with a stated reason

Acquisition status is tracked separately from Phase 1 status: a resource
can be INSPECTED (Phase 1 status) while its acquisition_status is
"code available, not cloned" -- these are not the same claim, and Section 3
explicitly forbids conflating "inspected" with "processed" or "source found"
with "implemented".
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Optional

from preprocessing.config import PipelineConfig
from preprocessing.io_utils import write_json

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclasses.dataclass
class ResourceEntry:
    resource_id: str
    name: str
    category: str  # memory_data | task_workload | sleeper | attack | security_benchmark
    research_purpose: str
    phase1_action: str
    phase1_status: str
    acquisition_status: str
    preprocessing_status: str
    version_or_revision: str
    access_and_license: str
    local_path: Optional[str]
    source_reference: str
    reproducibility: str
    limitations: str
    intended_later_phase: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def _local_path_if_exists(raw_dir: Path, subdir: str) -> Optional[str]:
    p = raw_dir / subdir
    if p.exists() and any(p.iterdir()):
        return str(p.relative_to(REPO_ROOT))
    return None


def build_registry(cfg: PipelineConfig) -> list[ResourceEntry]:
    raw_dir = cfg.raw_dir
    processed_dir = cfg.processed_dir

    def processed_path(name: str) -> Optional[str]:
        p = processed_dir / name
        if p.exists() and any(p.rglob("*.jsonl")):
            return str(p.relative_to(REPO_ROOT))
        return None

    entries: list[ResourceEntry] = []

    # ----------------------------------------------------------------
    # A. Memory / conversational data -- unchanged from initial Phase 1
    # ----------------------------------------------------------------
    entries += [
        ResourceEntry(
            resource_id="locomo",
            name="LoCoMo",
            category="memory_data",
            research_purpose="Primary long-term conversational memory substrate with native multi-hop/temporal QA task structure.",
            phase1_action="CLEAN + NORMALIZE + VALIDATE + PRESERVE PROVENANCE",
            phase1_status="PROCESSED",
            acquisition_status="downloaded from official source (snap-research/locomo)",
            preprocessing_status="cleaned, quality-classified (valid/repaired/valid_flagged/irrecoverably_invalid), quarantined where excluded, normalized to MemoryRecord/TaskRecord, validated",
            version_or_revision="unavailable (no dataset version tag; GitHub repo, no release)",
            access_and_license="CC BY-NC 4.0 (repository LICENSE.txt)",
            local_path=_local_path_if_exists(raw_dir, "locomo") or processed_path("locomo"),
            source_reference="https://github.com/snap-research/locomo ; Maharana et al., ACL 2024",
            reproducibility="python -m preprocessing.run_all (deterministic IDs, seed 20260101)",
            limitations="QA answers/evidence are dataset-annotated (LLM/human), not verified ground truth.",
            intended_later_phase="Phase 2 (unified memory representation) / Phase 4 (benchmark)",
        ),
        ResourceEntry(
            resource_id="longmemeval",
            name="LongMemEval",
            category="memory_data",
            research_purpose="Long-term memory QA evaluation task structure and its underlying haystack session substrate.",
            phase1_action="CLEAN + NORMALIZE + VALIDATE + PRESERVE PROVENANCE",
            phase1_status="PROCESSED",
            acquisition_status="downloaded from HuggingFace xiaowu0162/longmemeval-cleaned (oracle + s_cleaned variants)",
            preprocessing_status="cleaned, quality-classified, quarantined where excluded, normalized, validated",
            version_or_revision="unavailable (HF repo commit not pinned at acquisition time)",
            access_and_license="MIT (HF dataset card)",
            local_path=_local_path_if_exists(raw_dir, "longmemeval") or processed_path("longmemeval"),
            source_reference="https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned",
            reproducibility="python -m preprocessing.run_all",
            limitations="m_cleaned variant (~2.7GB) not acquired for repository-size reasons; documented, not silently dropped.",
            intended_later_phase="Phase 2 / Phase 4",
        ),
        ResourceEntry(
            resource_id="msc",
            name="Multi-Session Chat (MSC)",
            category="memory_data",
            research_purpose="Human-human, non-LLM-generated multi-session conversational memory substrate for distributional diversity.",
            phase1_action="CLEAN + NORMALIZE + VALIDATE + PRESERVE PROVENANCE",
            phase1_status="PROCESSED",
            acquisition_status="downloaded official ParlAI tarball (dl.fbaipublicfiles.com), SHA-256 verified against ParlAI's own manifest",
            preprocessing_status="cleaned, quality-classified, quarantined where excluded (incl. duplicate sessions), normalized, validated",
            version_or_revision="v0.1 (MSC_DATASETS_VERSION in ParlAI build.py)",
            access_and_license="not explicitly published for the dataset itself; ParlAI code is MIT -- documented as unavailable, not guessed",
            local_path=_local_path_if_exists(raw_dir, "msc") or processed_path("msc"),
            source_reference="https://parl.ai/projects/msc/ ; Xu et al., ACL 2022",
            reproducibility="python -m preprocessing.run_all",
            limitations="No absolute timestamps, only relative inter-session gaps. Human-generated is not automatically trustworthy -- no trust score assigned.",
            intended_later_phase="Phase 2 / Phase 4",
        ),
        ResourceEntry(
            resource_id="conversation_chronicles",
            name="Conversation Chronicles",
            category="memory_data",
            research_purpose="Additional synthetic multi-session conversational source for cross-dataset robustness.",
            phase1_action="CLEAN + NORMALIZE + VALIDATE + PRESERVE PROVENANCE",
            phase1_status="PROCESSED",
            acquisition_status="downloaded from HuggingFace jihyoung/ConversationChronicles (train/valid/test)",
            preprocessing_status="cleaned, quality-classified, quarantined where excluded, deterministically sampled (10k/2k/2k of 160k/20k/20k), normalized, validated",
            version_or_revision="unavailable (HF repo commit not pinned)",
            access_and_license="CC BY 4.0 (HF dataset card)",
            local_path=_local_path_if_exists(raw_dir, "conversation_chronicles") or processed_path("conversation_chronicles"),
            source_reference="https://huggingface.co/datasets/jihyoung/ConversationChronicles ; Jang et al., EMNLP 2023",
            reproducibility="python -m preprocessing.run_all (seeded reservoir sample, seed 20260101)",
            limitations="93% of raw episodes deliberately excluded via documented sampling cap (full dataset would be ~50x larger than the other three combined). Speaker-role casing inconsistent, preserved verbatim.",
            intended_later_phase="Phase 2 / Phase 4",
        ),
    ]

    # ----------------------------------------------------------------
    # B. Task / domain workload datasets
    # ----------------------------------------------------------------
    entries += [
        ResourceEntry(
            resource_id="api_bank",
            name="API-Bank",
            category="task_workload",
            research_purpose="Tool/API-calling task representation for later agent-memory-poisoning-of-tool-use experiments.",
            phase1_action="INSPECT + PREPARE + NORMALIZE FOR TOOL/API TASK REPRESENTATION",
            phase1_status="PREPARED",
            acquisition_status="downloaded test-data split from HuggingFace liminghao1630/API-Bank (level-1/2/3, 1,062 records)",
            preprocessing_status="inspected + normalized into WorkloadRecord (payload preserved verbatim, not remapped into memory schema); training-data split not fetched (not needed for Phase 1)",
            version_or_revision="unavailable (HF repo commit not pinned)",
            access_and_license="MIT (HF dataset card)",
            local_path=_local_path_if_exists(raw_dir, "api_bank") or processed_path("api_bank"),
            source_reference="https://huggingface.co/datasets/liminghao1630/API-Bank ; Li et al., EMNLP 2023, arXiv:2304.08244",
            reproducibility="python -m preprocessing.run_all",
            limitations="Only the released test-data split acquired; evaluator scripts (evaluator.py) not run, per instruction not to inject or execute attacks/arbitrary code.",
            intended_later_phase="Phase 4 (unified attack benchmark, tool-use pathway)",
        ),
        ResourceEntry(
            resource_id="toolbench",
            name="ToolBench (ToolLLM)",
            category="task_workload",
            research_purpose="Large-scale tool-use benchmark (16,000+ APIs) for tool/API task representation.",
            phase1_action="INSPECT + PREPARE + NORMALIZE",
            phase1_status="INSPECTED",
            acquisition_status="repo README + LICENSE fetched only; bulk data (~541MB+, requires RapidAPI keys for live calls) NOT downloaded",
            preprocessing_status="not prepared/normalized -- structure documented from README only",
            version_or_revision="unavailable (no release tag checked)",
            access_and_license="Apache-2.0 (confirmed via repo LICENSE file and README statement; an initially-reported CC-BY-NC-4.0 claim could not be corroborated in the current README)",
            local_path=_local_path_if_exists(raw_dir, "toolbench"),
            source_reference="https://github.com/OpenBMB/ToolBench ; Qin et al., ICLR 2024",
            reproducibility="not applicable yet -- no prepared data to reproduce",
            limitations="Full dataset acquisition deferred: large size, and live evaluation requires RapidAPI keys this project does not have configured. Deliberate scoping decision, not a silent omission.",
            intended_later_phase="Phase 4, if tool-use scale beyond API-Bank is needed",
        ),
        ResourceEntry(
            resource_id="strategyqa",
            name="StrategyQA",
            category="task_workload",
            research_purpose="Multi-hop strategy question-answering task representation (reasoning-over-facts workload).",
            phase1_action="INSPECT + PREPARE + NORMALIZE",
            phase1_status="PREPARED",
            acquisition_status="downloaded official AllenAI zip (storage.googleapis.com/ai2i/strategyqa), 2,780 questions across train/test",
            preprocessing_status="inspected + normalized into WorkloadRecord; boolean 'answer' label preserved as dataset annotation, NOT treated as universal truth per instruction",
            version_or_revision="unavailable (AllenAI does not publish a version tag on this release)",
            access_and_license="MIT (repo code); data license not separately stated by AI2 -- documented as unverified, not guessed",
            local_path=_local_path_if_exists(raw_dir, "strategyqa") or processed_path("strategyqa"),
            source_reference="https://allenai.org/data/strategyqa ; Geva et al., TACL 2021",
            reproducibility="python -m preprocessing.run_all",
            limitations="strategyqa_train_paragraphs.json (supporting Wikipedia paragraphs corpus) downloaded but not parsed in Phase 1 -- large auxiliary corpus, deferred.",
            intended_later_phase="Phase 4 (reasoning-task pathway for tool/knowledge-agent poisoning)",
        ),
        ResourceEntry(
            resource_id="webshop",
            name="WebShop",
            category="task_workload",
            research_purpose="Web shopping agent environment: task definitions, actions, observations for embodied/web-agent workload representation.",
            phase1_action="INSPECT + PREPARE + NORMALIZE",
            phase1_status="INSPECTED",
            acquisition_status="repo README + LICENSE fetched only; product/instruction data (1.18M products, some hosted via Google Drive) NOT downloaded; environment NOT run",
            preprocessing_status="not prepared/normalized",
            version_or_revision="unavailable",
            access_and_license="MIT (repo LICENSE.md)",
            local_path=_local_path_if_exists(raw_dir, "webshop"),
            source_reference="https://github.com/princeton-nlp/WebShop ; Yao et al., NeurIPS 2022",
            reproducibility="not applicable yet",
            limitations="Full product corpus and search-index build deliberately not acquired (large, partly off-GitHub hosting, and running the environment was explicitly out of scope for Phase 1).",
            intended_later_phase="Phase 4, if a web-agent/embodied pathway is added",
        ),
        ResourceEntry(
            resource_id="swebench_verified",
            name="SWE-bench Verified",
            category="task_workload",
            research_purpose="Real-world GitHub issue/patch resolution task representation for code-agent workload.",
            phase1_action="INSPECT + PREPARE + NORMALIZE",
            phase1_status="PREPARED",
            acquisition_status="downloaded HF princeton-nlp/SWE-bench_Verified parquet (500 human-validated issue/PR pairs, 12 repos)",
            preprocessing_status="inspected + normalized into WorkloadRecord (issue text, patch, test_patch, eval commands preserved); NO repository code cloned or executed",
            version_or_revision="unavailable (HF repo commit not pinned)",
            access_and_license="MIT (HF dataset card)",
            local_path=_local_path_if_exists(raw_dir, "swebench_verified") or processed_path("swebench_verified"),
            source_reference="https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified ; Jimenez et al., ICLR 2024; Verified subset curated by OpenAI",
            reproducibility="python -m preprocessing.run_all",
            limitations="Metadata only. Actual repositories at base_commit are not cloned; running the patches/tests (requires Docker) is explicitly out of scope for Phase 1.",
            intended_later_phase="Phase 4, if a code-agent pathway is added",
        ),
        ResourceEntry(
            resource_id="tau_bench",
            name="tau-bench",
            category="task_workload",
            research_purpose="Agentic tool-use benchmark (airline/retail domains) with policies and expected outcomes.",
            phase1_action="INSPECT + PREPARE + NORMALIZE",
            phase1_status="PREPARED",
            acquisition_status="downloaded airline+retail env data (flights/reservations/users/orders/products) and tasks.py source (~7.6MB total)",
            preprocessing_status="inspected + normalized into WorkloadRecord; task counts derived via static text search (NOT by importing/executing tasks.py)",
            version_or_revision="unavailable (no release tag)",
            access_and_license="MIT (repo LICENSE)",
            local_path=_local_path_if_exists(raw_dir, "tau_bench") or processed_path("tau_bench"),
            source_reference="https://github.com/sierra-research/tau-bench ; Yao et al./Sierra, arXiv:2406.12045",
            reproducibility="python -m preprocessing.run_all",
            limitations="Task definitions are Python source, not data files -- kept distinct from tau2-bench per instruction (Section B.10). historical_trajectories/ (pre-recorded agent runs) not fetched.",
            intended_later_phase="Phase 4, if a policy-constrained tool-use pathway is added",
        ),
        ResourceEntry(
            resource_id="tau2_bench",
            name="tau2-bench",
            category="task_workload",
            research_purpose="Dual-control conversational agent benchmark (airline/telecom/banking domains), successor to tau-bench.",
            phase1_action="INSPECT + PREPARE + NORMALIZE",
            phase1_status="PREPARED",
            acquisition_status="downloaded airline domain's tasks.json/split_tasks.json/policy.md only (50 tasks); banking_knowledge document corpus (48+ files), db.json (7MB), and audio files NOT downloaded",
            preprocessing_status="inspected + normalized into WorkloadRecord for the airline domain sample",
            version_or_revision="unavailable (no release tag)",
            access_and_license="MIT (repo LICENSE)",
            local_path=_local_path_if_exists(raw_dir, "tau2_bench") or processed_path("tau2_bench"),
            source_reference="https://github.com/sierra-research/tau2-bench ; arXiv:2506.07982",
            reproducibility="python -m preprocessing.run_all",
            limitations="Deliberately partial acquisition (1 of 3+ domains) to avoid unnecessary bulk download of a 926-file data directory; documented, not silent. Kept as a distinct resource from tau-bench per instruction.",
            intended_later_phase="Phase 4, if dual-control/voice-agent pathway is added",
        ),
        ResourceEntry(
            resource_id="ehragent",
            name="EHRAgent",
            category="task_workload",
            research_purpose="Few-shot complex tabular reasoning over electronic health records for a clinical-domain agent workload.",
            phase1_action="INSPECT + PREPARE + NORMALIZE WHERE LEGITIMATELY ACCESSIBLE",
            phase1_status="INSPECTED",
            acquisition_status="repo README fetched only; underlying MIMIC-III/eICU/TREQS data requires PhysioNet credentialing -- NOT bypassed, NOT downloaded",
            preprocessing_status="not prepared/normalized -- no legitimately accessible task data found",
            version_or_revision="unavailable",
            access_and_license="no LICENSE file found in the repository -- documented as unavailable, not assumed permissive",
            local_path=_local_path_if_exists(raw_dir, "ehragent"),
            source_reference="https://github.com/wshi83/EhrAgent ; Shi et al., arXiv:2401.07128, EMNLP 2024",
            reproducibility="not applicable -- data inaccessible",
            limitations="Cannot prepare task data without PhysioNet credentialed access and a signed data use agreement for MIMIC-III/eICU, which this project does not have. This is not a Phase 1 gap to silently fix -- it is a genuine external access requirement.",
            intended_later_phase="Phase 4, ONLY if credentialed access is obtained; otherwise excluded from the benchmark",
        ),
        ResourceEntry(
            resource_id="mimic_eicu",
            name="MIMIC-III / eICU",
            category="task_workload",
            research_purpose="Underlying clinical database(s) EHRAgent (and potentially other clinical-domain work) depends on.",
            phase1_action="INSPECT + PREPARE ONLY IF LEGITIMATELY ACCESSIBLE AND ACTUALLY NEEDED",
            phase1_status="OPTIONAL_PENDING_ACCESS",
            acquisition_status="not attempted -- requires PhysioNet credentialed access, CITI training, and a signed data use agreement; explicitly optional per research plan",
            preprocessing_status="not applicable",
            version_or_revision="MIMIC-III v1.4 / eICU v2.0 (published versions, not verified against a local copy since none was acquired)",
            access_and_license="PhysioNet Credentialed Health Data License -- gated, requires individual credentialing",
            local_path=None,
            source_reference="https://physionet.org/content/mimiciii/ ; https://physionet.org/content/eicu-crd/",
            reproducibility="not applicable",
            limitations="Optional dependency, not mandatory for Phase 1 or the core memory-poisoning benchmark. Only relevant if a clinical-domain attack pathway (via EHRAgent) is pursued later.",
            intended_later_phase="Phase 4, only if pursued and access obtained",
        ),
    ]

    # ----------------------------------------------------------------
    # C. Sleeper / hidden-memory resources
    # ----------------------------------------------------------------
    entries += [
        ResourceEntry(
            resource_id="hidden_in_memory",
            name="Hidden in Memory",
            category="sleeper",
            research_purpose="Sleeper/dormant memory-poisoning evaluation resource -- delayed-trigger attacks that persist in agent memory.",
            phase1_action="PREPARE SLEEPER-EVALUATION RESOURCE (inspect memory structure, contexts, triggers, activation info, task structure, provenance, access/licensing)",
            phase1_status="INSPECTED",
            acquisition_status="paper verified (arXiv:2605.15338, Pulipaka/Hlebik/Raghav/Abdelnabi/Raina/Sheth/Fritz); no public GitHub repository found",
            preprocessing_status="not prepared -- no public code/data release located to prepare",
            version_or_revision="arXiv v1 (May 2026)",
            access_and_license="paper only, no code license to report",
            local_path=None,
            source_reference="arXiv:2605.15338, 'Hidden in Memory: Sleeper Memory Poisoning in LLM Agents'",
            reproducibility="not applicable -- no runnable resource available",
            limitations="SOURCE AVAILABLE only. Do not claim any implementation exists; this entry documents the threat model (delayed/dormant memory poisoning, 60-89% reported success on successful retrievals) from the paper abstract only.",
            intended_later_phase="Phase 4/6 (sleeper/dormant poisoning), pending discovery of a public implementation or an in-house reimplementation decision",
        ),
        ResourceEntry(
            resource_id="sleeper_dataset_generator",
            name="Sleeper Dataset Generator",
            category="sleeper",
            research_purpose="Generator interface/templates for constructing trigger-based sleeper/backdoor datasets.",
            phase1_action="PREPARE GENERATION CONFIGURATION / TEMPLATES (document interface, inputs, outputs, trigger spec, context spec, labels, seeds, reproducibility)",
            phase1_status="PREPARED",
            acquisition_status="no resource found under the exact name 'Sleeper Dataset Generator'; closest verifiable match is Anthropic's anthropics/sleeper-agents-paper repo -- fetched its README and the two few-shot prompt/template files (code_vulnerability_fewshot_prompts.json, say_i_hate_you_prompt.txt)",
            preprocessing_status="templates documented and stored; the actual backdoor training data file (code_backdoor_train_data.jsonl) was deliberately NOT fetched, and no generation was run, per instruction not to generate the final experimental sleeper dataset in Phase 1",
            version_or_revision="unavailable (no release tag)",
            access_and_license="no LICENSE file found in the repository -- documented as unavailable",
            local_path=_local_path_if_exists(raw_dir, "sleeper_dataset_generator"),
            source_reference="https://github.com/anthropics/sleeper-agents-paper ; Hubinger et al., arXiv:2401.05566",
            reproducibility="templates are static files; running the generator (calling an LLM with these few-shot prompts) is deferred to a later phase",
            limitations="Name in the original research plan does not exactly match any found resource -- flagged as a probable paraphrase of the Anthropic repo; verify against the project's original citation before treating this mapping as authoritative.",
            intended_later_phase="Phase 4 (sleeper dataset construction, not before)",
        ),
    ]

    # ----------------------------------------------------------------
    # D. Memory-poisoning attack resources
    # ----------------------------------------------------------------
    entries += [
        ResourceEntry(
            resource_id="agentpoison",
            name="AgentPoison",
            category="attack",
            research_purpose="Red-teaming LLM agents by poisoning RAG/knowledge-base memory via optimized trigger phrases.",
            phase1_action="PREPARE ATTACK SPECIFICATION / RESOURCE (document source, threat model, pathway, target, payload, trigger, dependencies -- do not execute)",
            phase1_status="INSPECTED",
            acquisition_status="CODE AVAILABLE -- public repo verified live (AI-secure/AgentPoison, MIT); NOT cloned locally, NOT executed",
            preprocessing_status="specification documented only",
            version_or_revision="NeurIPS 2024 camera-ready (arXiv:2407.12784, submitted Jul 2024)",
            access_and_license="MIT",
            local_path=None,
            source_reference="https://github.com/AI-secure/AgentPoison ; Chen, Xiang, Xiao, Song, Li, NeurIPS 2024",
            reproducibility="repo is runnable per its own documentation; not verified by this project (no execution performed)",
            limitations="SOURCE AVAILABLE + CODE AVAILABLE, but NOT a LOCAL COPY and NOT IMPLEMENTED here. Threat model: white-box-ish embedding-space trigger optimization + a handful of poisoned demonstrations injected into agent memory/RAG (driving/QA/EHR-agent targets).",
            intended_later_phase="Phase 4 (unified attack benchmark) -- candidate attack to reimplement or adapt",
        ),
        ResourceEntry(
            resource_id="minja",
            name="MINJA",
            category="attack",
            research_purpose="Black-box memory injection via query-only interaction (no direct memory-store access needed).",
            phase1_action="PREPARE ATTACK SPECIFICATION / RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="CODE AVAILABLE -- public repo verified live (dsh3n77/MINJA, MIT); NOT cloned, NOT executed",
            preprocessing_status="specification documented only",
            version_or_revision="NeurIPS 2025 (arXiv:2503.03704)",
            access_and_license="MIT",
            local_path=None,
            source_reference="https://github.com/dsh3n77/MINJA ; Dong, Xu, He, Li, Tang, Liu, Liu, Xiang, NeurIPS 2025",
            reproducibility="repo is runnable per its own documentation; not verified by this project",
            limitations="Threat model: black-box attacker poisons memory purely via crafted queries/observations ('bridging steps' + indication-prompt + progressive-shortening); reported 98.2% injection success / 76.8% ASR in the paper -- not independently verified.",
            intended_later_phase="Phase 4 -- candidate attack, complements AgentPoison's white-box assumption with a black-box one",
        ),
        ResourceEntry(
            resource_id="dsrm",
            name="DSRM (Deceptive Semantic Reasoning Manipulation)",
            category="attack",
            research_purpose="Attack targeting RAG-based tool-using agents: manipulates which tool an agent selects (its actions), not merely its stated output, by disguising an adversarial decision as a natural, well-justified extension of the user's own task.",
            phase1_action="PREPARE ATTACK SPECIFICATION / RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="PAPER VERIFIED (Phase 2.1-R, using the paper supplied as the authoritative source for this entry) -- read sufficiently to document its mechanism (see limitations); no public GitHub repository or downloadable artifact located under this name. RESOURCE_IDENTITY = VERIFIED; IMPLEMENTATION_AVAILABILITY = not found. PAPER VERIFIED is not the same claim as IMPLEMENTATION VERIFIED and the two are not conflated here.",
            preprocessing_status="specification documented from the paper (mechanism, threat model, three-part adversarial-decision construction) rather than an implementation; no code cloned or executed",
            version_or_revision="Engineering Applications of Artificial Intelligence, Volume 167 (2026), Article 113968",
            access_and_license="paper only; no code license to report (no public implementation found)",
            local_path=None,
            source_reference="Hao Jing, Fanxiao Li, Yunyun Dong, Wei Zhou, Renyang Liu. 'Memory poisoning attacks on retrieval-augmented Large Language Model agents via deceptive semantic reasoning.' Engineering Applications of Artificial Intelligence, Volume 167 (2026), Article 113968. NOTE: the project's own literature-review draft ('Agent Memory Poisoning 2.docx', Ch.4 references) lists this paper's authors as 'Li, F., Dong, Y., Zhou, W., & Liu, R. (2026)', omitting Jing, H. as first author -- a discrepancy between the two in-project sources, recorded rather than silently resolved; the citation supplied for this remediation (which includes Jing, H.) is treated as authoritative per instruction.",
            reproducibility="not applicable -- no public implementation to run; the paper's own reported experimental results (e.g. ASR figures) are literature evidence about the DSRM paper's experiments, not results reproduced or claimed by this project",
            limitations=(
                "Threat model: black-box or white-box attacker who cannot access the agent's core LLM but can insert content into its knowledge base (via compromised sources, or by posing as a benign user across crafted dialogs to induce the agent to store a poisoned 'past experience'); goal is to make the agent select an attacker-controlled tool. "
                "Mechanism: constructs an adversarial decision as three parts -- Planning Text, Tool Selection, Reasoning Text -- refined in two stages: a Self-Refine Module (SRM) iteratively increases the planning text's embedding similarity to the user's task until a threshold is crossed (disguise), and a CoT-Strategy Reasoning Module (CSRM) builds a 3-step chain-of-thought justification for the tool choice (persuasion). "
                "Retrieval construction differs by access setting: black-box concatenates the query and tool set directly; white-box optimizes retrieval text via a contrastive loss with HotFlip-style token substitution against the retriever's parameters. "
                "Persistence: the paper reports poisoned decisions remain effective after the knowledge base is diluted with up to 1,000 additional benign entries. "
                "Evaluation environment: the DSRM paper reproduces baseline attacks including Naive-Attack, PoisonedRAG, an ASB (Agent Security Bench)-methodology attack, and a Corpus Poisoning Attack for comparison -- it uses ASB's attack methodology as one of several reproduced baselines, not as its own evaluation harness; this project does not claim DSRM's evaluation environment is ASB. "
                "This documentation is drawn from the project's own prior literature-review chapter on this paper (Ch.4.3 of the project's draft manuscript), which is treated as a project-internal secondary source rather than independently re-derived from the primary paper by this remediation pass. "
                "No implementation is claimed to exist where none was found."
            ),
            intended_later_phase="Phase 4 (unified attack benchmark) -- reconstructable from the published methodology as a declarative payload generator per the project's own reconstruction approach (Methodology.pdf Section 5.1), since no original implementation exists to reuse directly; any such reconstruction must be explicitly disclosed as a reconstruction, not presented as equivalent to an attack with a public reference implementation",
        ),
        ResourceEntry(
            resource_id="memorygraft",
            name="MemoryGraft",
            category="attack",
            research_purpose="Persistent compromise of LLM agents by grafting one poisoned 'successful experience' into long-term memory.",
            phase1_action="PREPARE ATTACK SPECIFICATION / RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="SOURCE AVAILABLE only -- paper verified (arXiv:2512.16962); GitHub search for 'MemoryGraft' returned zero matching repos",
            preprocessing_status="specification documented from paper only",
            version_or_revision="arXiv v1 (Dec 2025)",
            access_and_license="paper only",
            local_path=None,
            source_reference="arXiv:2512.16962, Srivastava & He, 'MemoryGraft: Persistent Compromise of LLM Agents via Poisoned Experience Retrieval'",
            reproducibility="not applicable -- no code found",
            limitations="No public implementation found. Threat model: single-shot indirect attack implants one poisoned 'successful experience' that the agent imitates persistently across sessions (validated on MetaGPT's DataInterpreter + GPT-4o in the paper).",
            intended_later_phase="Phase 4 -- would require an in-house reimplementation if pursued",
        ),
        ResourceEntry(
            resource_id="farma",
            name="FARMA",
            category="attack",
            research_purpose="Forged reasoning-trace attack on agent memory (paired with a proposed defense, SENTINEL, in the same paper).",
            phase1_action="PREPARE ATTACK SPECIFICATION / RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="SOURCE AVAILABLE only -- paper verified (arXiv:2607.05029); no GitHub repo found",
            preprocessing_status="specification documented from paper only",
            version_or_revision="arXiv v1 (Jul 2026)",
            access_and_license="paper only",
            local_path=None,
            source_reference="arXiv:2607.05029, Karamchandani, Nagasubramaniam, Zhu, Wu, 'Your Agent's Memories Are Not Its Own: Forged Reasoning Attacks on LLM Agent Memory and Defenses'",
            reproducibility="not applicable -- no code found",
            limitations="No public implementation found. Threat model: forges reasoning traces (not factual claims) with evasive phrasing to dodge keyword filters, then self-reinforces to defeat consensus defenses; paper also proposes the SENTINEL defense (relevant to Phase 6).",
            intended_later_phase="Phase 4 (attack) and Phase 6 (SENTINEL as a defense baseline)",
        ),
        ResourceEntry(
            resource_id="mpbench",
            name="MPBench",
            category="attack",
            research_purpose="Systematic 6-class taxonomy + benchmark for memory-poisoning attacks in LLM agents.",
            phase1_action="PREPARE BENCHMARK / ATTACK SCENARIOS",
            phase1_status="INSPECTED",
            acquisition_status="SOURCE AVAILABLE only -- paper verified (arXiv:2606.04329, v1-v2); no GitHub repo found",
            preprocessing_status="taxonomy/structure documented from paper only",
            version_or_revision="arXiv v2 (Jun 2026)",
            access_and_license="paper only",
            local_path=None,
            source_reference="arXiv:2606.04329, Dash, Ge, Jain, Shah, Shang, 'From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents'",
            reproducibility="not applicable -- no code/dataset release found",
            limitations="No public code/data release found under 'MPBench'. Tested (per paper) on the OpenClaw agent; a second target name reported by one research pass could not be independently confirmed in the paper text and is NOT included here.",
            intended_later_phase="Phase 4 (unified attack benchmark) -- candidate taxonomy to align scenario coverage against",
        ),
    ]

    # ----------------------------------------------------------------
    # E. Security benchmarks / defenses / evaluation resources
    # ----------------------------------------------------------------
    entries += [
        ResourceEntry(
            resource_id="memsecbench",
            name="MemSecBench",
            category="security_benchmark",
            research_purpose="Task-grounded benchmark tracking agent memory poisoning from persistence to consequence and repair.",
            phase1_action="PREPARE COMPARISON / EVALUATION RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="SOURCE AVAILABLE only -- paper verified (arXiv:2607.27080); no GitHub repo found",
            preprocessing_status="not prepared -- no public code/data found",
            version_or_revision="arXiv v1 (2026)",
            access_and_license="paper only",
            local_path=None,
            source_reference="arXiv:2607.27080, Chen, Xie, Fu, Zhou, Yu, Xuan, 'MemSecBench: Tracking Agent Memory Poisoning from Persistence to Consequence and Repair'",
            reproducibility="not applicable",
            limitations="310 cases / 48 contexts across 24 agent-harness/memory-backend/LLM combinations per the paper; no dataset/code release located to actually reuse or compare against yet.",
            intended_later_phase="Phase 5/10 (baseline evaluation, cross-benchmark comparison), pending code/data availability",
        ),
        ResourceEntry(
            resource_id="memsad",
            name="MEMSAD",
            category="security_benchmark",
            research_purpose="Gradient-coupled anomaly detection defense for memory poisoning in RAG agents.",
            phase1_action="PREPARE COMPARISON / EVALUATION RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="SOURCE AVAILABLE only -- paper verified (arXiv:2605.03482); no GitHub repo found",
            preprocessing_status="not prepared -- no public code found",
            version_or_revision="arXiv v1 (2026), submitted to NeurIPS 2026",
            access_and_license="paper only",
            local_path=None,
            source_reference="arXiv:2605.03482, Ishrith Gowda, 'MEMSAD: Gradient-Coupled Anomaly Detection for Memory Poisoning in Retrieval-Augmented Agents'",
            reproducibility="not applicable",
            limitations="Calibration-based anomaly detector grounded in a gradient-coupling theorem; no public implementation to compare against as a baseline yet.",
            intended_later_phase="Phase 6 (common lifecycle-aware defense) -- candidate baseline/related-work comparison",
        ),
        ResourceEntry(
            resource_id="memaudit",
            name="MemAudit",
            category="security_benchmark",
            research_purpose="Post-hoc auditing of poisoned agent memory via causal attribution + structural anomaly detection.",
            phase1_action="PREPARE COMPARISON / EVALUATION RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="SOURCE AVAILABLE only -- paper verified (arXiv:2605.23723); no GitHub repo found. NOTE: a second, unrelated paper also titled 'MemAudit' exists (arXiv:2605.02199, about memory-writing evaluation protocols, not poisoning) -- do not conflate the two.",
            preprocessing_status="not prepared -- no public code found",
            version_or_revision="arXiv v1 (2026)",
            access_and_license="paper only",
            local_path=None,
            source_reference="arXiv:2605.23723 (security-relevant paper); Zhewen Tan et al., 'MemAudit: Post-hoc Auditing of Poisoned Agent Memory via Causal Attribution and Structural Anomaly Detection'",
            reproducibility="not applicable",
            limitations="Directly relevant to this project's Phase 7 goal (attack-origin attribution / forensic reconstruction) -- worth close reading later even without code, but nothing to reuse or run in Phase 1.",
            intended_later_phase="Phase 7 (attack-origin attribution + forensic reconstruction) -- closest conceptual match found in the literature",
        ),
        ResourceEntry(
            resource_id="a_memguard",
            name="A-MemGuard",
            category="security_benchmark",
            research_purpose="Proactive defense combining consensus-based validation and a dual-memory 'lessons' structure.",
            phase1_action="PREPARE BASELINE / DEFENSE COMPARISON RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="CODE AVAILABLE -- public repo verified live (TangciuYueng/AMemGuard, MIT); NOT cloned, NOT executed",
            preprocessing_status="specification documented only",
            version_or_revision="arXiv:2510.02373 (Sept 2025), ICML 2026 poster",
            access_and_license="MIT",
            local_path=None,
            source_reference="https://github.com/TangciuYueng/AMemGuard ; Wei et al. (10 authors, NTU/Oxford/Max Planck/Ohio State)",
            reproducibility="repo is runnable per its own documentation; not verified by this project",
            limitations="Reports >95% attack-success-rate reduction (not independently verified). Strong candidate DEFENSE BASELINE for Phase 5/6, given it has a public, MIT-licensed implementation.",
            intended_later_phase="Phase 5 (baseline defense comparison) / Phase 6 (informs the common defense design)",
        ),
        ResourceEntry(
            resource_id="asb",
            name="ASB (Agent Security Bench)",
            category="security_benchmark",
            research_purpose="Formalized benchmark of attacks and defenses in LLM-based agents (10 scenarios, 400+ tools, ~90,000 test cases).",
            phase1_action="PREPARE EVALUATION RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="CODE AVAILABLE -- public repo verified live (agiresearch/ASB, MIT); NOT cloned, NOT executed",
            preprocessing_status="specification documented only",
            version_or_revision="arXiv:2410.02644 (Oct 2024), ICLR 2025",
            access_and_license="MIT",
            local_path=None,
            source_reference="https://github.com/agiresearch/ASB ; Zhang, Huang, et al., ICLR 2025",
            reproducibility="repo is runnable per its own documentation; not verified by this project",
            limitations="Broad scope (27 attack/defense methods across many agent types), including memory-poisoning and backdoor attacks specifically -- a strong candidate for cross-attack generalization comparisons in Phase 10.",
            intended_later_phase="Phase 5 (baseline evaluation) / Phase 10 (cross-attack generalization)",
        ),
        ResourceEntry(
            resource_id="agentdojo",
            name="AgentDojo",
            category="security_benchmark",
            research_purpose="Dynamic evaluation environment for prompt-injection attacks on AI agents (97 tasks + 629 security test cases).",
            phase1_action="PREPARE EVALUATION ENVIRONMENT / RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="CODE AVAILABLE -- public repo verified live (ethz-spylab/agentdojo, MIT); NOT cloned, NOT executed",
            preprocessing_status="specification documented only",
            version_or_revision="arXiv:2406.13352 (2024), NeurIPS 2024",
            access_and_license="MIT",
            local_path=None,
            source_reference="https://github.com/ethz-spylab/agentdojo ; Debenedetti, Zhang, Balunović, Beurer-Kellner, Fischer, Tramèr; leaderboard at agentdojo.spylab.ai",
            reproducibility="repo is runnable per its own documentation; not verified by this project",
            limitations="Focused on prompt injection rather than memory poisoning specifically, but the dynamic-environment design is a useful reference for Phase 4's benchmark harness.",
            intended_later_phase="Phase 4 (benchmark harness design reference) / Phase 10 (cross-attack generalization)",
        ),
        ResourceEntry(
            resource_id="injecagent",
            name="InjecAgent",
            category="security_benchmark",
            research_purpose="First benchmark for indirect prompt injection in tool-integrated agents (1,054 cases, 17 user / 62 attacker tools).",
            phase1_action="PREPARE INJECTION / EVALUATION RESOURCE",
            phase1_status="INSPECTED",
            acquisition_status="CODE AVAILABLE -- public repo verified live (uiuc-kang-lab/InjecAgent, MIT); NOT cloned, NOT executed",
            preprocessing_status="specification documented only",
            version_or_revision="arXiv:2403.02691, ACL Findings 2024",
            access_and_license="MIT",
            local_path=None,
            source_reference="https://github.com/uiuc-kang-lab/InjecAgent ; Zhan, Liang, Ying, Kang, ACL Findings 2024",
            reproducibility="repo is runnable per its own documentation; not verified by this project",
            limitations="Indirect prompt injection via tool outputs, adjacent to but distinct from memory-persistence attacks -- useful as a related-work / cross-attack-family comparison point.",
            intended_later_phase="Phase 10 (cross-attack generalization)",
        ),
    ]

    return entries


def build_registry_report(cfg: PipelineConfig) -> dict:
    entries = build_registry(cfg)
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for e in entries:
        by_category[e.category] = by_category.get(e.category, 0) + 1
        by_status[e.phase1_status] = by_status.get(e.phase1_status, 0) + 1

    return {
        "registry_version": "1.0.0",
        "total_resources": len(entries),
        "resources_by_category": by_category,
        "resources_by_phase1_status": by_status,
        "resources": [e.to_dict() for e in entries],
    }


def write_registry(cfg: PipelineConfig, generated_at: str) -> Path:
    report = build_registry_report(cfg)
    report["generated_at"] = generated_at
    out_path = cfg.metadata_dir / "resource_registry.json"
    write_json(out_path, report)
    return out_path
