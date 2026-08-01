# Memory Subsystem Architecture

## Overview

The Memory Subsystem in AI-Orchestrator provides a clean, deterministic knowledge preservation layer. It isolates persistence and information retrieval from execution, planning, scheduling, and validation logic.

---

## Architectural Layout

```
                  ┌──────────────────────────────┐
                  │       AntigravityBrain       │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │        TaskWorkspace         │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │         MemoryEngine         │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │         MemoryStore          │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │         MemoryRecord         │
                  └──────────────────────────────┘
```

---

## Key Design Principles

1. **Information Storage Only**: The subsystem does not execute code, plan goals, schedule tasks, or evaluate outputs.
2. **Explicit Store Ownership**: `MemoryStore` holds in-memory records behind a thread lock (`Lock`).
3. **Engine Coordination**: `MemoryEngine` acts as an un-opinionated coordinator, managing memory record creation, ID generation, workspace resolution, and query construction.
4. **Deterministic Query Engine**: Searches filter strictly by substring matching in title/description/content/tags, explicit enum type inclusion, tag set inclusion, and numeric result limits.
5. **Zero Hidden State**: All dependencies are passed explicitly via constructors (Dependency Injection).
