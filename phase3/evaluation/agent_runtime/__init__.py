"""Phase 3.3-B -- the real MAMBench agent runtime.

Implements `PHASE3_3_EXPERIMENTAL_SPEC.md` Part 6 (agent contract) and Part 7 (canonical
agent loop) on top of Phase 3.2's existing, unmodified `phase3/evaluation/agent/`
diagnostic package, `phase3/evaluation/foundations/` (`MemoryFoundationAdapter`,
lifecycle), and `phase3/evaluation/contracts/boundary.py`. This package adds no second
evaluator, no second metrics implementation, no second memory-foundation interface --
every classification/metric it produces is a direct call into the existing Phase 3.2
code.
"""
