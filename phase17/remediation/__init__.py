"""Remediation analyses (2026-10-12) responding to the independent pre-submission review
(`docs/review/INDEPENDENT_IEEE_REVIEW_2026-10-12.md`).

Every module here READS existing frozen corpora and cached per-item results and WRITES new
artifacts under `phase17/data/remediation/`. None of them modifies a frozen corpus, an
existing artifact, or a defense parameter. Each module's docstring names the review issue it
answers (register: `REMEDIATION_MASTER_REGISTER.md`).
"""
