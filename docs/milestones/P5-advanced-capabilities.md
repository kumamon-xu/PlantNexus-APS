---
doc_id: MILESTONE-P5
title: P5 — Advanced Capabilities
status: planned
spec_version: 0.3.0
phase: P5
normative: true
source_sections: [27, 81, 82]
last_reviewed: 2026-08-19
---

# P5 — Advanced Capabilities

P5 不是一个整体交付包。只有真实需求或 Simulation/Benchmark 证据证明必要时，才逐项考虑 Secondary Resources、Setup Matrix、Batch、Split/Merge、Material Competition、Preemption、Buffer、Decomposition 或 Rolling Horizon。

每项能力独立提交 ADR、Schema、Capability Contract、Solver、Validator、正反 Fixture、Benchmark 和 Feature Flag。禁止 P5 big bang。

DecomposedStrategy 还需 scaling/memory/model explosion 证据、比较 Benchmark、merge Validator 和 quality impact report。
