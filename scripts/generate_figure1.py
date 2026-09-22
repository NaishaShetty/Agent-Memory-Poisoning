"""Regenerates Figure 1 (Overall Pipeline, Phases 1-13) for the MAMBench
methodology draft, extending the original Phases 1-11 diagram with real
Phase 12 (Security Metrics) and Phase 13 (Attribution Metrics) blocks, using
the same visual grammar (title, colored phase boxes, arrows, italic output
lines) as the original."""

from PIL import Image, ImageDraw, ImageFont

W = 1600
MARGIN = 40
BOX_W = W - 2 * MARGIN

FONT_DIR = "C:/Windows/Fonts/"
title_font = ImageFont.truetype(FONT_DIR + "arialbd.ttf", 30)
box_title_font = ImageFont.truetype(FONT_DIR + "arialbd.ttf", 20)
box_detail_font = ImageFont.truetype(FONT_DIR + "arial.ttf", 16)
output_font = ImageFont.truetype(FONT_DIR + "ariali.ttf", 15)
sub_title_font = ImageFont.truetype(FONT_DIR + "arialbd.ttf", 14)

WHITE = (255, 255, 255)
BLACK = (20, 20, 20)


def wrap(text, font, max_width, draw):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class Block:
    def __init__(self, title, detail_lines, output_lines, fill, border, sub_boxes=None, title_color=BLACK):
        self.title = title
        self.detail_lines = detail_lines
        self.output_lines = output_lines
        self.fill = fill
        self.border = border
        self.sub_boxes = sub_boxes or []
        self.title_color = title_color


BLOCKS = [
    Block(
        "RAW SOURCE DATASETS", ["LoCoMo · LongMemEval · MSC · Conversation Chronicles"], [],
        (235, 235, 235), (90, 90, 90),
    ),
    Block(
        "PHASE 1 — Dataset & Benchmark Foundations", ["Identification → Registry → Cleaning → Quality Classification"],
        ["Output: processed corpus, 1,266,194 records · 10-check validation (9 pass / 1 fail)"],
        (216, 232, 250), (46, 90, 160),
    ),
    Block(
        "PHASE 2 — Dataset Preparation & Benchmark Infrastructure", [],
        ["each subphase is additive; none regenerates the layer beneath it"],
        (255, 255, 255), (30, 60, 130),
        sub_boxes=[
            "2.1\nData Boundary &\nInput Approval", "2.2\nUnified Memory\nRecord (schema)", "2.3\nTemporal\nNormalization",
            "2.4\nBenchmark-Role\nOrganization", "2.5\nReproducibility\nMetadata", "2.6\nCross-Phase\nSubstrate Validation",
            "2.7\nAcceptance &\nFreeze",
        ],
    ),
    Block(
        "FREEZE TRIPWIRE — canonical Phase 2 identity hash; status: PASS WITH ISSUES",
        ["(no later phase may silently modify the frozen substrate)"], [],
        (253, 240, 200), (180, 130, 20),
    ),
    Block(
        "PHASE 3 — Clean Memory-Augmented Agent", ["Agent architecture · Mem0 / A-MEM foundations · V1→V5 iteration · V3-Hybrid (final)"],
        ["Output: validated V3-Hybrid foundation, 8-metric evaluation, n=120 × 2 foundations"],
        (222, 240, 222), (50, 120, 60),
    ),
    Block(
        "PHASE 4 — Unified Memory Manipulation Attack Benchmark",
        ["Common Attack Contract · AttackAdapter · 7 attacks (AgentPoison, MINJA, FARMA, MemoryGraft, DSRM, MPBench-PCFI, Sleeper) · nine-state ground-truth chain"],
        ["Output: 7 real, executed attack campaigns against unmodified V3-Hybrid, real counterfactual masking evidence · frozen 2026-09-11"],
        (250, 222, 222), (170, 50, 50),
    ),
    Block(
        "PHASE 5 — Instrumentation, Monitoring & Attribution",
        ["Canonical event schema (16 types) · lifecycle/retrieval/decision/lineage instrumentation · trace assembly · memory behavior dataset · 6-question attribution layer"],
        ["Output: frozen observability substrate (2079 tests passing), read-only attribution layer over the frozen Phase 3/4 evidence · frozen 2026-09-13"],
        (232, 222, 245), (110, 70, 160),
    ),
    Block(
        "PHASE 6 — Governance Defense Evaluation",
        ["Admission / retrieval / propagation / sleeper guards over a shared state machine · B0–B10 factorial design · real ASB (perplexity-filter) external baseline"],
        ["Output (final, post-Phase-11 semantic-retrieval fix): B9 100.0% detection at 14.6% FPR (75-scenario corpus) — up from 70.6%/7.3% at the 2026-09-17 post-freeze recalibration"],
        (222, 245, 225), (40, 130, 90),
    ),
    Block(
        "PHASE 7 — Propagation Monitoring",
        ["Propagation footprint · fan-out / re-entry / cycle-reinforcement / cross-task-bleed signals · campaign-level aggregation · real seven-attack + real two-stage retrieval studies"],
        ["Output: FARMA crowding closed with a real measurement · six real attack-specific studies · real Mem0 retrieval-pool-narrowing closure (Sleeper full, AgentPoison partial)"],
        (250, 232, 210), (190, 110, 30),
    ),
    Block(
        "PHASE 8 — Sleeper / Dormant Poison Detection",
        ["Content (directive-regex) · dormancy-count · dormancy-window · activation-shape signals over the real retrieval pipeline · real cross-signal trial (all four together)"],
        ["Output: real artifact evades the content signal entirely (Finding A) · activation-shape false positives cut 47%→17.6% · no single signal is both sensitive and safe"],
        (250, 222, 232), (180, 60, 100),
    ),
    Block(
        "PHASE 9 — Attack-Origin Attribution & Forensics",
        ["reconstruct_attack_origin(): a real backward walk (EXPOSURE → LINEAGE → ORIGIN → PROPAGATION) with a disclosed, worst-hop-wins chain-confidence verdict"],
        ["Output: validated against all 7 real attacks — 5 clean single origins, FARMA/MemoryGraft correctly report genuine multi-origin ambiguity, never an arbitrary pick"],
        (215, 240, 235), (30, 130, 115),
    ),
    Block(
        "PHASE 10 — Adaptive Risk-Based Hardening",
        ["compute_memory_risk_score(): combines Phase 6–9's real signals into one disclosed [0,1] estimate, driving retrieval, monitoring, verification, or quarantine"],
        ["Output: initial B9 regressed vs B8 (47.1% vs 70.6%); a real, non-circular dev-corpus recalibration closed the gap — B9 matched B8 exactly at 70.6%/7.3%, later further improved by Phase 11's own semantic-retrieval fix (see Phase 6, above)"],
        (232, 222, 245), (110, 70, 160),
    ),
    Block(
        "PHASE 11 — Learned Detection Components (GNN + GLN) & Generalization Research",
        ["From-scratch relation-aware GNN and Gated Linear Network over the sanctioned 9-signal vocabulary · Options 1-2 (anomaly framing, structural/semantic feature expansion) · Tracks A/B (real clean+poison data expansion) · leave-one-family-out (LOFO) generalization audit · grouped/MAX score composition"],
        ["Output: pooled-corpus GNN 55.9%/6.8% (real, disclosed data-scale ceiling) · LOFO macro detection 37.5%→87.5% after the grouped-score fix · real 7-attack corpus 33.3%→99.6% mean detection at a 9.1% FPR floor · the semantic consensus-divergence signal this work surfaced was fed back into Phase 6, raising B9/B10 to 100.0%/14.6%"],
        (212, 235, 245), (30, 110, 150),
    ),
    Block(
        "PHASE 12 — Security Metrics Evaluation",
        ["PAR / PR / SDR / AMR + Defense Generalization Score (DGS) over the real B0–B8 evaluation matrix · new Consolidation Guard (5th defense component) closing a real derivation-time gap · real cross-model validation (llama2, qwen2.5)"],
        ["Output: PR 86.1% grand mean (2 real local models × 3 real distractor sets) · Consolidation Guard 100.0% catch rate in all 6 real trials · non-circular threshold calibration (0.5347) via a disjoint held-out pool · every borderline family miss (DSRM, FARMA, AgentPoison, MemoryGraft) root-caused and closed"],
        (255, 235, 205), (200, 130, 20),
    ),
    Block(
        "PHASE 13 — Attribution Metrics Evaluation",
        ["All 7 real attribution types (ORIGIN, LINEAGE, INFLUENCE, EXPOSURE, REFERENCES, PROPAGATION, plus the composed FORENSICS/ACTION layers) run against the real 15-scenario corpus for the first time · persistent real ledger built from real Phase 4 injectors + real Phase 12 consolidation output"],
        ["Output: source accuracy 100% (15/15) · path fidelity 100% (19/19 real derivations, incl. 4 genuine multi-source branches, one 4-way) · influence accuracy 100% (6 real cases/6 attack families) · Consolidation Guard decisions 100% traceable (14/14 QUARANTINE, 4/4 ALLOW) · admission/propagation confidence correlation real but weak (r ≈ -0.11, root-caused at two resolutions) · origin ambiguity intentionally, permanently unreachable by a real ledger integrity invariant"],
        (238, 222, 245), (120, 60, 150),
    ),
    Block(
        "Downstream: Phases 14–16 — Systematic Evaluation (utility metrics, full cross-cutting sweep, and synthesis report)",
        [], [], (235, 235, 235), (90, 90, 90),
    ),
]


def draw_box(draw, y, block):
    pad_x = 24
    pad_y = 16
    line_gap = 6
    x0, x1 = MARGIN, MARGIN + BOX_W

    title_lines = wrap(block.title, box_title_font, BOX_W - 2 * pad_x, draw)
    detail_wrapped = []
    for d in block.detail_lines:
        detail_wrapped.extend(wrap(d, box_detail_font, BOX_W - 2 * pad_x, draw))

    content_h = pad_y * 2 + len(title_lines) * 26 + (len(detail_wrapped) * 22 if detail_wrapped else 0)
    if detail_wrapped:
        content_h += 10

    sub_h = 0
    if block.sub_boxes:
        sub_h = 110 + 20

    box_h = content_h + sub_h

    draw.rounded_rectangle([x0, y, x1, y + box_h], radius=10, fill=block.fill, outline=block.border, width=3)

    ty = y + pad_y
    for line in title_lines:
        w = draw.textlength(line, font=box_title_font)
        draw.text(((x0 + x1) / 2 - w / 2, ty), line, font=box_title_font, fill=block.title_color)
        ty += 26

    if detail_wrapped:
        ty += 4
        for line in detail_wrapped:
            w = draw.textlength(line, font=box_detail_font)
            draw.text(((x0 + x1) / 2 - w / 2, ty), line, font=box_detail_font, fill=(40, 40, 40))
            ty += 22

    if block.sub_boxes:
        ty += 10
        n = len(block.sub_boxes)
        gap = 10
        sub_w = (BOX_W - 2 * pad_x - gap * (n - 1)) / n
        sx = x0 + pad_x
        for label in block.sub_boxes:
            draw.rounded_rectangle([sx, ty, sx + sub_w, ty + 100], radius=6, fill=(40, 70, 130), outline=(20, 40, 90), width=2)
            lines = label.split("\n")
            ly = ty + 10
            for l in lines:
                w = draw.textlength(l, font=sub_title_font)
                draw.text((sx + sub_w / 2 - w / 2, ly), l, font=sub_title_font, fill=WHITE)
                ly += 18
            sx += sub_w + gap

    return y + box_h


def draw_output(draw, y, output_lines):
    if not output_lines:
        return y
    wrapped = []
    for o in output_lines:
        wrapped.extend(wrap(o, output_font, BOX_W - 20, draw))
    y += 8
    for line in wrapped:
        w = draw.textlength(line, font=output_font)
        draw.text(((MARGIN + BOX_W / 2) - w / 2, y), line, font=output_font, fill=(70, 70, 70))
        y += 20
    return y


def draw_arrow(draw, y, height=44):
    cx = MARGIN + BOX_W / 2
    draw.line([(cx, y), (cx, y + height - 12)], fill=(60, 60, 60), width=3)
    draw.polygon([(cx - 8, y + height - 12), (cx + 8, y + height - 12), (cx, y + height)], fill=(60, 60, 60))
    return y + height


def build():
    tmp = Image.new("RGB", (10, 10), WHITE)
    d = ImageDraw.Draw(tmp)

    title_text = "Figure 1 — Overall Pipeline (Phases 1–13)"
    title_h = 60

    y = title_h + 10
    heights = []
    for i, block in enumerate(BLOCKS):
        y = draw_box(d, y, block)
        heights.append(None)
        y = draw_output(d, y, block.output_lines)
        if i < len(BLOCKS) - 1:
            y = draw_arrow(d, y)
    total_h = y + 30

    img = Image.new("RGB", (W, int(total_h)), WHITE)
    draw = ImageDraw.Draw(img)

    tw = draw.textlength(title_text, font=title_font)
    draw.text((W / 2 - tw / 2, 15), title_text, font=title_font, fill=BLACK)

    y = title_h + 10
    for i, block in enumerate(BLOCKS):
        y = draw_box(draw, y, block)
        y = draw_output(draw, y, block.output_lines)
        if i < len(BLOCKS) - 1:
            y = draw_arrow(draw, y)

    return img


if __name__ == "__main__":
    img = build()
    out_path = "docs/figures/figure1_pipeline_phases_1_13.png"
    import os
    os.makedirs("docs/figures", exist_ok=True)
    img.save(out_path)
    print(f"Saved {out_path} size={img.size}")
