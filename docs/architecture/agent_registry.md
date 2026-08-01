# Agent Registry Architecture

## Overview
The `AgentRegistry` is a thread-safe domain store for `Agent` entities. It serves as the single source of truth for agent identity, status, role categorization, and capability discovery.

## Features
- **Registration**: Register agents with explicit roles (`GENERAL`, `PLANNER`, `EXECUTOR`, `REVIEWER`, `RESEARCHER`, `CODER`, `TESTER`, `SYNTHESIZER`, `MEMORY`, `CUSTOM`) and capabilities.
- **Lookup & Query**: Retrieve agents by `agent_id`, or filter registered agents by role or capability tags.
- **Status Transitions**: Manage agent availability states (`IDLE`, `BUSY`, `WAITING`, `OFFLINE`, `ERROR`).
- **Thread Safety**: Uses internal `threading.Lock()` to prevent race conditions in multi-threaded workflows.
