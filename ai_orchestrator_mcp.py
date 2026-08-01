#!/usr/bin/env python3
"""Minimal MCP server exposing explicit model execution primitives."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

from brain import AntigravityBrain
from config import config
from task_graph import DependencyType, TaskStatus
from workspace import workspace_store, workspace_summary, workspace_to_dict
from artifact_store import Artifact, ArtifactType



DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "groq": "llama-3.1-8b-instant",
    "openrouter": "openai/gpt-4o-mini",
    "ollama": "llama3.1",
}


EXECUTE_MODEL_TOOL_SCHEMA = {
    "name": "execute_model",
    "description": "Execute a prompt or messages against an explicitly selected provider and return a normalized response.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["gemini", "groq", "openrouter", "ollama"],
                "description": "Provider to execute. The caller chooses; this server does not route.",
            },
            "model": {
                "type": "string",
                "description": "Optional provider model name. A provider default is used when omitted.",
            },
            "prompt": {
                "type": "string",
                "description": "Single user prompt. Use either prompt or messages.",
            },
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
                "description": "Chat messages. Use either prompt or messages.",
            },
            "workspace_id": {
                "type": "string",
                "description": "Optional in-memory task workspace to record this execution in.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional task ID to bind this execution to.",
            },
            "execution_type": {
                "type": "string",
                "enum": ["PRIMARY", "REVIEW", "RETRY", "PARALLEL", "SYNTHESIS", "VALIDATION"],
                "description": "Optional execution type. Defaults to PRIMARY.",
            },
        },
        "required": ["provider"],
        "additionalProperties": False,
    },
}

EXECUTE_MODELS_TOOL_SCHEMA = {
    "name": "execute_models",
    "description": "Execute multiple explicitly requested provider/model calls without routing or model selection.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "requests": {
                "type": "array",
                "items": EXECUTE_MODEL_TOOL_SCHEMA["inputSchema"],
                "minItems": 1,
                "description": "Provider/model execution requests chosen by Antigravity.",
            },
            "parallel": {
                "type": "boolean",
                "description": "When true, execute requests concurrently. When false, execute sequentially.",
                "default": False,
            },
            "workspace_id": {
                "type": "string",
                "description": "Optional in-memory task workspace to record all executions in.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional task ID to bind all executions to.",
            },
            "execution_type": {
                "type": "string",
                "enum": ["PRIMARY", "REVIEW", "RETRY", "PARALLEL", "SYNTHESIS", "VALIDATION"],
                "description": "Optional execution type to apply to all bindings. Defaults to PRIMARY.",
            },
        },
        "required": ["requests"],
        "additionalProperties": False,
    },
}

CREATE_WORKSPACE_TOOL_SCHEMA = {
    "name": "create_workspace",
    "description": "Create an in-memory task workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Optional workspace title."},
            "metadata": {"type": "object", "description": "Optional workspace metadata."},
        },
        "additionalProperties": False,
    },
}

GET_WORKSPACE_TOOL_SCHEMA = {
    "name": "get_workspace",
    "description": "Return workspace metadata and execution records.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

LIST_WORKSPACES_TOOL_SCHEMA = {
    "name": "list_workspaces",
    "description": "List all active in-memory workspaces.",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

CREATE_TASK_TOOL_SCHEMA = {
    "name": "create_task",
    "description": "Create a task in a workspace's task graph.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID that owns the task graph.",
            },
            "title": {
                "type": "string",
                "description": "The title of the task.",
            },
            "description": {
                "type": "string",
                "description": "Optional task description.",
            },
            "status": {
                "type": "string",
                "enum": ["PENDING", "READY", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
                "description": "Optional initial task status. Defaults to PENDING.",
            },
            "metadata": {
                "type": "object",
                "description": "Optional task metadata.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional custom task ID. If omitted, a UUID will be generated.",
            },
        },
        "required": ["workspace_id", "title"],
        "additionalProperties": False,
    },
}

CREATE_SUBTASK_TOOL_SCHEMA = {
    "name": "create_subtask",
    "description": "Create a subtask under a parent task in a workspace's task graph.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID that owns the task graph.",
            },
            "parent_task_id": {
                "type": "string",
                "description": "The parent task ID.",
            },
            "title": {
                "type": "string",
                "description": "The title of the subtask.",
            },
            "description": {
                "type": "string",
                "description": "Optional subtask description.",
            },
            "status": {
                "type": "string",
                "enum": ["PENDING", "READY", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"],
                "description": "Optional initial subtask status. Defaults to PENDING.",
            },
            "metadata": {
                "type": "object",
                "description": "Optional subtask metadata.",
            },
            "task_id": {
                "type": "string",
                "description": "Optional custom task ID. If omitted, a UUID will be generated.",
            },
        },
        "required": ["workspace_id", "parent_task_id", "title"],
        "additionalProperties": False,
    },
}

ADD_DEPENDENCY_TOOL_SCHEMA = {
    "name": "add_dependency",
    "description": "Add a dependency edge between two tasks in a workspace's task graph.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID that owns the task graph.",
            },
            "source_task_id": {
                "type": "string",
                "description": "The task that depends on (or is blocked by, etc.) the target task.",
            },
            "target_task_id": {
                "type": "string",
                "description": "The task being depended on (or blocking, etc.).",
            },
            "dependency_type": {
                "type": "string",
                "enum": ["DEPENDS_ON", "BLOCKS", "RELATED"],
                "description": "The type of dependency relationship. Defaults to DEPENDS_ON.",
            },
        },
        "required": ["workspace_id", "source_task_id", "target_task_id"],
        "additionalProperties": False,
    },
}

GET_TASK_TOOL_SCHEMA = {
    "name": "get_task",
    "description": "Retrieve a specific task by ID from a workspace's task graph.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID that owns the task graph.",
            },
            "task_id": {
                "type": "string",
                "description": "The ID of the task to retrieve.",
            },
        },
        "required": ["workspace_id", "task_id"],
        "additionalProperties": False,
    },
}

LIST_TASKS_TOOL_SCHEMA = {
    "name": "list_tasks",
    "description": "List all tasks in a workspace's task graph.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID that owns the task graph.",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_TASK_EXECUTIONS_TOOL_SCHEMA = {
    "name": "get_task_executions",
    "description": "Retrieve every execution binding attached to a specific task in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID containing the task.",
            },
            "task_id": {
                "type": "string",
                "description": "The ID of the task.",
            },
        },
        "required": ["workspace_id", "task_id"],
        "additionalProperties": False,
    },
}

LIST_EXECUTION_BINDINGS_TOOL_SCHEMA = {
    "name": "list_execution_bindings",
    "description": "Retrieve every execution binding inside a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID to list bindings for.",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

EXECUTE_TASK_TOOL_SCHEMA = {
    "name": "execute_task",
    "description": "Execute a single task in a workspace using its ExecutionEngine. Updates the task lifecycle (RUNNING → COMPLETED or FAILED) and persists the execution record and binding.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "Target workspace ID.",
            },
            "task_id": {
                "type": "string",
                "description": "ID of the task to execute.",
            },
            "provider": {
                "type": "string",
                "enum": ["gemini", "groq", "openrouter", "ollama"],
                "description": "Provider to execute against.",
            },
            "model": {
                "type": "string",
                "description": "Optional model override.",
            },
            "prompt": {
                "type": "string",
                "description": "Single user prompt. Use either prompt or messages.",
            },
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
                "description": "Chat messages. Use either prompt or messages.",
            },
            "execution_type": {
                "type": "string",
                "enum": ["PRIMARY", "REVIEW", "RETRY", "PARALLEL", "SYNTHESIS", "VALIDATION"],
                "description": "Execution binding type. Defaults to PRIMARY.",
            },
        },
        "required": ["workspace_id", "task_id", "provider"],
        "additionalProperties": False,
    },
}

EXECUTE_TASKS_TOOL_SCHEMA = {
    "name": "execute_tasks",
    "description": "Execute multiple tasks in a workspace, sequentially or in parallel. Each task is a separate provider call.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "Target workspace ID.",
            },
            "tasks": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string"},
                        "provider": {"type": "string"},
                        "model": {"type": "string"},
                        "prompt": {"type": "string"},
                        "messages": {"type": "array"},
                        "execution_type": {"type": "string"},
                    },
                    "required": ["task_id", "provider"],
                },
                "description": "List of task execution requests.",
            },
            "parallel": {
                "type": "boolean",
                "description": "Execute tasks concurrently when true. Default false.",
                "default": False,
            },
            "execution_type": {
                "type": "string",
                "enum": ["PRIMARY", "REVIEW", "RETRY", "PARALLEL", "SYNTHESIS", "VALIDATION"],
                "description": "Default execution binding type applied to all tasks.",
            },
        },
        "required": ["workspace_id", "tasks"],
        "additionalProperties": False,
    },
}

CREATE_ARTIFACT_TOOL_SCHEMA = {
    "name": "create_artifact",
    "description": "Explicitly store an artifact in a workspace. Artifacts are never created automatically; only Antigravity decides when to store one.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "name": {"type": "string", "description": "Human-readable artifact name."},
            "artifact_type": {
                "type": "string",
                "enum": [t.value for t in ArtifactType],
                "description": "Artifact type.",
            },
            "content": {"description": "Artifact content (string, object, or any JSON-serialisable value)."},
            "mime_type": {"type": "string", "description": "Optional MIME type. Defaults to text/plain."},
            "task_id": {"type": "string", "description": "Optional task to associate with."},
            "execution_id": {"type": "string", "description": "Optional execution to associate with."},
            "metadata": {"type": "object", "description": "Optional artifact metadata."},
        },
        "required": ["workspace_id", "name", "artifact_type", "content"],
        "additionalProperties": False,
    },
}

GET_ARTIFACTS_TOOL_SCHEMA = {
    "name": "get_artifacts",
    "description": "List all artifacts in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_TASK_ARTIFACTS_TOOL_SCHEMA = {
    "name": "get_task_artifacts",
    "description": "List all artifacts associated with a specific task.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
            "task_id": {"type": "string"},
        },
        "required": ["workspace_id", "task_id"],
        "additionalProperties": False,
    },
}

GET_READY_TASKS_TOOL_SCHEMA = {
    "name": "get_ready_tasks",
    "description": "Get all tasks in a workspace that are currently ready for execution.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID to query.",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_BLOCKED_TASKS_TOOL_SCHEMA = {
    "name": "get_blocked_tasks",
    "description": "Get all tasks in a workspace that are currently blocked by uncompleted dependencies.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID to query.",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_EXECUTION_QUEUE_TOOL_SCHEMA = {
    "name": "get_execution_queue",
    "description": "Get the ordered execution queue of tasks for a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID to query.",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_SCHEDULER_STATE_TOOL_SCHEMA = {
    "name": "get_scheduler_state",
    "description": "Get the complete state of the dependency scheduler for a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {
                "type": "string",
                "description": "The workspace ID to query.",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

CREATE_PLAN_TOOL_SCHEMA = {
    "name": "create_plan",
    "description": "Decompose an objective into a structured, validated Task Graph with generic planning levels, dependencies, and priorities.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "objective": {"description": "Objective string or objective specification object."},
            "levels": {"type": "array", "description": "Optional generic planning levels."},
            "phases": {"type": "array", "description": "Alias for levels."},
            "options": {"type": "object", "description": "Optional planning configuration options."},
        },
        "required": ["workspace_id", "objective"],
        "additionalProperties": False,
    },
}

EXPAND_TASK_TOOL_SCHEMA = {
    "name": "expand_task",
    "description": "Dynamically expand an existing task into subtasks within a plan while preserving graph validation.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "task_id": {"type": "string", "description": "Target task ID to expand."},
            "subtasks": {"type": "array", "minItems": 1, "description": "List of subtask specifications."},
            "plan_id": {"type": "string", "description": "Optional target plan ID."},
        },
        "required": ["workspace_id", "task_id", "subtasks"],
        "additionalProperties": False,
    },
}

REGENERATE_PLAN_TOOL_SCHEMA = {
    "name": "regenerate_plan",
    "description": "Regenerate unexecuted/pending tasks in a plan without touching completed/failed tasks or execution records.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
            "plan_id": {"type": "string", "description": "Target plan ID."},
            "target_task_id": {"type": "string", "description": "Optional subtree task ID."},
            "objective": {"description": "Optional updated objective."},
            "levels": {"type": "array", "description": "Optional updated level specs."},
            "options": {"type": "object"},
        },
        "required": ["workspace_id", "plan_id"],
        "additionalProperties": False,
    },
}

GET_PLAN_TOOL_SCHEMA = {
    "name": "get_plan",
    "description": "Retrieve structured PlanningResult snapshot for a workspace plan.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
            "plan_id": {"type": "string", "description": "Optional plan ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

VISUALIZE_PLAN_TOOL_SCHEMA = {
    "name": "visualize_plan",
    "description": "Render textual ASCII tree, JSON, or Mermaid diagram string of the plan structure.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string"},
            "plan_id": {"type": "string"},
            "format": {
                "type": "string",
                "enum": ["text", "json", "mermaid"],
                "default": "text",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

REVIEW_TASK_TOOL_SCHEMA = {
    "name": "review_task",
    "description": "Evaluate a task node and its bound execution outputs against defined criteria.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "task_id": {"type": "string", "description": "Target task ID to evaluate."},
            "criteria": {"type": "array", "description": "Optional list of review criteria objects."},
            "metadata": {"type": "object", "description": "Optional evaluation metadata."},
        },
        "required": ["workspace_id", "task_id"],
        "additionalProperties": False,
    },
}

REVIEW_TASKS_TOOL_SCHEMA = {
    "name": "review_tasks",
    "description": "Evaluate multiple tasks and their bound execution outputs sequentially.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "task_ids": {"type": "array", "description": "List of task IDs to evaluate."},
            "tasks": {"type": "array", "description": "Alias for task_ids (list of task IDs or task objects)."},
            "criteria": {"type": "array", "description": "Optional list of review criteria objects."},
            "metadata": {"type": "object", "description": "Optional evaluation metadata."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

REVIEW_EXECUTION_TOOL_SCHEMA = {
    "name": "review_execution",
    "description": "Evaluate a completed execution record against defined quality criteria.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "execution_id": {"type": "string", "description": "Target execution record ID."},
            "criteria": {"type": "array", "description": "Optional list of review criteria objects."},
            "metadata": {"type": "object", "description": "Optional evaluation metadata."},
        },
        "required": ["workspace_id", "execution_id"],
        "additionalProperties": False,
    },
}

REVIEW_PLAN_TOOL_SCHEMA = {
    "name": "review_plan",
    "description": "Evaluate an entire plan and all associated task outputs in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plan_id": {"type": "string", "description": "Optional target plan ID."},
            "criteria": {"type": "array", "description": "Optional list of review criteria objects."},
            "metadata": {"type": "object", "description": "Optional evaluation metadata."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_REVIEW_TOOL_SCHEMA = {
    "name": "get_review",
    "description": "Retrieve a stored review report by report_id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "report_id": {"type": "string", "description": "Target review report ID."},
        },
        "required": ["workspace_id", "report_id"],
        "additionalProperties": False,
    },
}

LIST_REVIEWS_TOOL_SCHEMA = {
    "name": "list_reviews",
    "description": "List all review reports stored in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

STORE_MEMORY_TOOL_SCHEMA = {
    "name": "store_memory",
    "description": "Store a persistent knowledge record in a workspace's MemoryEngine.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "title": {"type": "string", "description": "Title of the memory record."},
            "content": {"description": "Structured content or body of the memory record."},
            "memory_type": {
                "type": "string",
                "enum": ["OBJECTIVE", "PLAN", "EXECUTION", "REVIEW", "ARTIFACT", "TEMPLATE", "NOTE"],
                "description": "Memory type category. Defaults to NOTE.",
            },
            "description": {"type": "string", "description": "Optional brief summary or description."},
            "metadata": {"type": "object", "description": "Optional metadata dictionary."},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional tags for search and categorization.",
            },
        },
        "required": ["workspace_id", "title", "content"],
        "additionalProperties": False,
    },
}

RETRIEVE_MEMORY_TOOL_SCHEMA = {
    "name": "retrieve_memory",
    "description": "Retrieve a specific stored memory record by memory_id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "memory_id": {"type": "string", "description": "Target memory ID to retrieve."},
        },
        "required": ["workspace_id", "memory_id"],
        "additionalProperties": False,
    },
}

SEARCH_MEMORIES_TOOL_SCHEMA = {
    "name": "search_memories",
    "description": "Search stored memory records deterministically using text, memory types, tags, and limits.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "text": {"type": "string", "description": "Sub-string text query to match in title, description, tags, or content."},
            "memory_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["OBJECTIVE", "PLAN", "EXECUTION", "REVIEW", "ARTIFACT", "TEMPLATE", "NOTE"],
                },
                "description": "Optional list of memory types to filter by.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of tags that must be present in records.",
            },
            "limit": {"type": "integer", "description": "Optional maximum number of records to return."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

LIST_MEMORIES_TOOL_SCHEMA = {
    "name": "list_memories",
    "description": "List all stored memory records in a workspace with optional type and status filtering.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "memory_type": {
                "type": "string",
                "enum": ["OBJECTIVE", "PLAN", "EXECUTION", "REVIEW", "ARTIFACT", "TEMPLATE", "NOTE"],
                "description": "Optional memory type filter.",
            },
            "status": {
                "type": "string",
                "enum": ["ACTIVE", "ARCHIVED", "DELETED"],
                "description": "Optional memory status filter (defaults to non-deleted records).",
            },
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

DELETE_MEMORY_TOOL_SCHEMA = {
    "name": "delete_memory",
    "description": "Mark a stored memory record as DELETED.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "memory_id": {"type": "string", "description": "Memory record ID to delete."},
        },
        "required": ["workspace_id", "memory_id"],
        "additionalProperties": False,
    },
}

ARCHIVE_MEMORY_TOOL_SCHEMA = {
    "name": "archive_memory",
    "description": "Mark a stored memory record as ARCHIVED.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "memory_id": {"type": "string", "description": "Memory record ID to archive."},
        },
        "required": ["workspace_id", "memory_id"],
        "additionalProperties": False,
    },
}

SUMMARIZE_MEMORIES_TOOL_SCHEMA = {
    "name": "summarize_memories",
    "description": "Generate summary metrics for stored memory records in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

SYNTHESIZE_TOOL_SCHEMA = {
    "name": "synthesize",
    "description": "Synthesize collected execution outputs, review reports, artifacts, or memories into a final deliverable report.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "title": {"type": "string", "description": "Title of the synthesis output."},
            "task_id": {"type": "string", "description": "Optional task ID to pull sources from."},
            "plan_id": {"type": "string", "description": "Optional plan ID to pull sources from."},
            "execution_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit execution IDs to synthesize.",
            },
            "review_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit review report IDs to synthesize.",
            },
            "artifact_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit artifact IDs to synthesize.",
            },
            "memory_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit memory IDs to synthesize.",
            },
            "metadata": {"type": "object", "description": "Optional metadata dictionary."},
        },
        "required": ["workspace_id", "title"],
        "additionalProperties": False,
    },
}

SYNTHESIZE_TASK_TOOL_SCHEMA = {
    "name": "synthesize_task",
    "description": "Synthesize all execution outputs, review reports, and artifacts bound to a single task.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "task_id": {"type": "string", "description": "Target task ID to synthesize."},
            "title": {"type": "string", "description": "Optional custom title for synthesis report."},
            "include_reviews": {"type": "boolean", "description": "Whether to include review reports (default true)."},
            "include_artifacts": {"type": "boolean", "description": "Whether to include task artifacts (default true)."},
            "include_memories": {"type": "boolean", "description": "Whether to include tagged memory records (default false)."},
            "metadata": {"type": "object", "description": "Optional metadata dictionary."},
        },
        "required": ["workspace_id", "task_id"],
        "additionalProperties": False,
    },
}

SYNTHESIZE_PLAN_TOOL_SCHEMA = {
    "name": "synthesize_plan",
    "description": "Synthesize execution outputs, review reports, and artifacts across an entire plan.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plan_id": {"type": "string", "description": "Optional target plan ID."},
            "title": {"type": "string", "description": "Optional custom title for synthesis report."},
            "include_reviews": {"type": "boolean", "description": "Whether to include review reports (default true)."},
            "include_artifacts": {"type": "boolean", "description": "Whether to include artifacts (default true)."},
            "include_memories": {"type": "boolean", "description": "Whether to include memory records (default false)."},
            "metadata": {"type": "object", "description": "Optional metadata dictionary."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_SYNTHESIS_TOOL_SCHEMA = {
    "name": "get_synthesis",
    "description": "Retrieve a stored synthesis report by report_id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "report_id": {"type": "string", "description": "Synthesis report ID to retrieve."},
        },
        "required": ["workspace_id", "report_id"],
        "additionalProperties": False,
    },
}

LIST_SYNTHESES_TOOL_SCHEMA = {
    "name": "list_syntheses",
    "description": "List all synthesis reports stored in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

DELETE_SYNTHESIS_TOOL_SCHEMA = {
    "name": "delete_synthesis",
    "description": "Delete a stored synthesis report from a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "report_id": {"type": "string", "description": "Synthesis report ID to delete."},
        },
        "required": ["workspace_id", "report_id"],
        "additionalProperties": False,
    },
}

REGISTER_AGENT_TOOL_SCHEMA = {
    "name": "register_agent",
    "description": "Register a new agent entity in a workspace's AgentRegistry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "name": {"type": "string", "description": "Agent name."},
            "role": {
                "type": "string",
                "enum": ["GENERAL", "PLANNER", "EXECUTOR", "REVIEWER", "RESEARCHER", "CODER", "TESTER", "SYNTHESIZER", "MEMORY", "CUSTOM"],
                "description": "Agent role. Defaults to GENERAL.",
            },
            "description": {"type": "string", "description": "Optional description of agent capabilities."},
            "capabilities": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of capability tags.",
            },
            "metadata": {"type": "object", "description": "Optional agent metadata."},
            "agent_id": {"type": "string", "description": "Optional custom agent ID."},
            "status": {
                "type": "string",
                "enum": ["IDLE", "BUSY", "WAITING", "OFFLINE", "ERROR"],
                "description": "Initial status. Defaults to IDLE.",
            },
        },
        "required": ["workspace_id", "name"],
        "additionalProperties": False,
    },
}

UNREGISTER_AGENT_TOOL_SCHEMA = {
    "name": "unregister_agent",
    "description": "Remove an agent from a workspace's AgentRegistry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "agent_id": {"type": "string", "description": "Agent ID to unregister."},
        },
        "required": ["workspace_id", "agent_id"],
        "additionalProperties": False,
    },
}

GET_AGENT_TOOL_SCHEMA = {
    "name": "get_agent",
    "description": "Retrieve a specific registered agent by agent_id.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "agent_id": {"type": "string", "description": "Target agent ID."},
        },
        "required": ["workspace_id", "agent_id"],
        "additionalProperties": False,
    },
}

LIST_AGENTS_TOOL_SCHEMA = {
    "name": "list_agents",
    "description": "List all registered agents in a workspace with optional role or capability filters.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "role": {"type": "string", "description": "Optional role filter."},
            "capability": {"type": "string", "description": "Optional capability tag filter."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

CREATE_COLLABORATION_TOOL_SCHEMA = {
    "name": "create_collaboration",
    "description": "Create a new multi-agent collaboration session within a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "objective": {"type": "string", "description": "Shared objective for the session."},
            "participant_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of initial participating agent IDs.",
            },
            "participants": {"type": "array", "items": {"type": "string"}, "description": "Alias for participant_ids."},
            "metadata": {"type": "object", "description": "Optional session metadata."},
            "session_id": {"type": "string", "description": "Optional custom session ID."},
        },
        "required": ["workspace_id", "objective"],
        "additionalProperties": False,
    },
}

CLOSE_COLLABORATION_TOOL_SCHEMA = {
    "name": "close_collaboration",
    "description": "Close an active collaboration session in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "session_id": {"type": "string", "description": "Target session ID."},
            "status": {
                "type": "string",
                "enum": ["ACTIVE", "PAUSED", "COMPLETED", "FAILED"],
                "description": "Final status. Defaults to COMPLETED.",
            },
        },
        "required": ["workspace_id", "session_id"],
        "additionalProperties": False,
    },
}

ASSIGN_AGENT_TOOL_SCHEMA = {
    "name": "assign_agent",
    "description": "Explicitly assign an agent to a collaboration session and optional task.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "session_id": {"type": "string", "description": "Target collaboration session ID."},
            "agent_id": {"type": "string", "description": "Agent ID to assign."},
            "task_id": {"type": "string", "description": "Optional task ID."},
            "metadata": {"type": "object", "description": "Optional assignment metadata."},
            "assignment_id": {"type": "string", "description": "Optional custom assignment ID."},
        },
        "required": ["workspace_id", "session_id", "agent_id"],
        "additionalProperties": False,
    },
}

SEND_AGENT_MESSAGE_TOOL_SCHEMA = {
    "name": "send_agent_message",
    "description": "Send an immutable inter-agent message within a collaboration session.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "session_id": {"type": "string", "description": "Target session ID."},
            "sender_agent_id": {"type": "string", "description": "Sender agent ID."},
            "content": {"description": "Message payload/content (string or object)."},
            "message_type": {
                "type": "string",
                "enum": ["REQUEST", "RESPONSE", "STATUS", "INFO", "WARNING", "ERROR"],
                "description": "Message type. Defaults to INFO.",
            },
            "receiver_agent_id": {"type": "string", "description": "Optional recipient agent ID for direct messages. Omit for broadcast to session."},
            "metadata": {"type": "object", "description": "Optional message metadata."},
        },
        "required": ["workspace_id", "session_id", "sender_agent_id", "content"],
        "additionalProperties": False,
    },
}

LIST_MESSAGES_TOOL_SCHEMA = {
    "name": "list_messages",
    "description": "List inter-agent messages from a collaboration session.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "session_id": {"type": "string", "description": "Target session ID."},
            "receiver_agent_id": {"type": "string", "description": "Optional recipient filter."},
            "limit": {"type": "integer", "description": "Optional maximum number of recent messages."},
        },
        "required": ["workspace_id", "session_id"],
        "additionalProperties": False,
    },
}

LIST_ASSIGNMENTS_TOOL_SCHEMA = {
    "name": "list_assignments",
    "description": "List agent assignments in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "session_id": {"type": "string", "description": "Optional session ID filter."},
            "agent_id": {"type": "string", "description": "Optional agent ID filter."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

LIST_SESSIONS_TOOL_SCHEMA = {
    "name": "list_sessions",
    "description": "List all collaboration sessions in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

REGISTER_CAPABILITY_TOOL_SCHEMA = {
    "name": "register_capability",
    "description": "Register a new capability in the workspace capability registry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "capability_id": {"type": "string", "description": "Unique capability ID."},
            "name": {"type": "string", "description": "Capability name."},
            "version": {"type": "string", "description": "Capability version."},
            "description": {"type": "string", "description": "Capability description."},
            "capability_type": {
                "type": "string",
                "enum": ["CORE", "EXTENSION", "PLUGIN", "EXPERIMENTAL"],
                "description": "Type of capability. Defaults to EXTENSION.",
            },
            "status": {
                "type": "string",
                "enum": ["REGISTERED", "ENABLED", "DISABLED", "ERROR"],
                "description": "Capability status. Defaults to REGISTERED.",
            },
            "dependencies": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of capability IDs this capability depends on.",
            },
            "mcp_tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of MCP tools exposed by this capability.",
            },
            "metadata": {"type": "object", "description": "Optional metadata."},
        },
        "required": ["workspace_id", "capability_id", "name"],
        "additionalProperties": False,
    },
}

UNREGISTER_CAPABILITY_TOOL_SCHEMA = {
    "name": "unregister_capability",
    "description": "Unregister a capability from the workspace capability registry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "capability_id": {"type": "string", "description": "Capability ID to unregister."},
        },
        "required": ["workspace_id", "capability_id"],
        "additionalProperties": False,
    },
}

GET_CAPABILITY_TOOL_SCHEMA = {
    "name": "get_capability",
    "description": "Get capability details by ID.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "capability_id": {"type": "string", "description": "Capability ID to retrieve."},
        },
        "required": ["workspace_id", "capability_id"],
        "additionalProperties": False,
    },
}

LIST_CAPABILITIES_TOOL_SCHEMA = {
    "name": "list_capabilities",
    "description": "List all registered capabilities in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

ENABLE_CAPABILITY_TOOL_SCHEMA = {
    "name": "enable_capability",
    "description": "Enable a registered capability after dependency validation.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "capability_id": {"type": "string", "description": "Capability ID to enable."},
        },
        "required": ["workspace_id", "capability_id"],
        "additionalProperties": False,
    },
}

DISABLE_CAPABILITY_TOOL_SCHEMA = {
    "name": "disable_capability",
    "description": "Disable an active capability.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "capability_id": {"type": "string", "description": "Capability ID to disable."},
        },
        "required": ["workspace_id", "capability_id"],
        "additionalProperties": False,
    },
}

REGISTER_PLUGIN_TOOL_SCHEMA = {
    "name": "register_plugin",
    "description": "Register a plugin and forward its capabilities into the workspace CapabilityRegistry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plugin_id": {"type": "string", "description": "Unique plugin ID."},
            "name": {"type": "string", "description": "Plugin name."},
            "version": {"type": "string", "description": "Plugin version."},
            "description": {"type": "string", "description": "Plugin description."},
            "capabilities": {
                "type": "array",
                "items": {"type": "object"},
                "description": "List of capability objects contained in this plugin.",
            },
            "metadata": {"type": "object", "description": "Optional metadata."},
        },
        "required": ["workspace_id", "plugin_id", "name"],
        "additionalProperties": False,
    },
}

UNREGISTER_PLUGIN_TOOL_SCHEMA = {
    "name": "unregister_plugin",
    "description": "Unregister a plugin and remove its capabilities from the workspace CapabilityRegistry.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plugin_id": {"type": "string", "description": "Plugin ID to unregister."},
        },
        "required": ["workspace_id", "plugin_id"],
        "additionalProperties": False,
    },
}

LOAD_PLUGIN_TOOL_SCHEMA = {
    "name": "load_plugin",
    "description": "Load an unloaded plugin.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plugin_id": {"type": "string", "description": "Plugin ID to load."},
        },
        "required": ["workspace_id", "plugin_id"],
        "additionalProperties": False,
    },
}

UNLOAD_PLUGIN_TOOL_SCHEMA = {
    "name": "unload_plugin",
    "description": "Unload an active plugin.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plugin_id": {"type": "string", "description": "Plugin ID to unload."},
        },
        "required": ["workspace_id", "plugin_id"],
        "additionalProperties": False,
    },
}

LIST_PLUGINS_TOOL_SCHEMA = {
    "name": "list_plugins",
    "description": "List all registered plugins in a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

GET_PLUGIN_TOOL_SCHEMA = {
    "name": "get_plugin",
    "description": "Get plugin details by ID.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
            "plugin_id": {"type": "string", "description": "Plugin ID to retrieve."},
        },
        "required": ["workspace_id", "plugin_id"],
        "additionalProperties": False,
    },
}

CAPABILITY_SUMMARY_TOOL_SCHEMA = {
    "name": "capability_summary",
    "description": "Get summary metrics of capabilities and plugins for a workspace.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "Target workspace ID."},
        },
        "required": ["workspace_id"],
        "additionalProperties": False,
    },
}

TOOL_SCHEMAS = [
    EXECUTE_MODEL_TOOL_SCHEMA,
    EXECUTE_MODELS_TOOL_SCHEMA,
    EXECUTE_TASK_TOOL_SCHEMA,
    EXECUTE_TASKS_TOOL_SCHEMA,
    CREATE_WORKSPACE_TOOL_SCHEMA,
    GET_WORKSPACE_TOOL_SCHEMA,
    LIST_WORKSPACES_TOOL_SCHEMA,
    CREATE_TASK_TOOL_SCHEMA,
    CREATE_SUBTASK_TOOL_SCHEMA,
    ADD_DEPENDENCY_TOOL_SCHEMA,
    GET_TASK_TOOL_SCHEMA,
    LIST_TASKS_TOOL_SCHEMA,
    GET_TASK_EXECUTIONS_TOOL_SCHEMA,
    LIST_EXECUTION_BINDINGS_TOOL_SCHEMA,
    CREATE_ARTIFACT_TOOL_SCHEMA,
    GET_ARTIFACTS_TOOL_SCHEMA,
    GET_TASK_ARTIFACTS_TOOL_SCHEMA,
    GET_READY_TASKS_TOOL_SCHEMA,
    GET_BLOCKED_TASKS_TOOL_SCHEMA,
    GET_EXECUTION_QUEUE_TOOL_SCHEMA,
    GET_SCHEDULER_STATE_TOOL_SCHEMA,
    CREATE_PLAN_TOOL_SCHEMA,
    EXPAND_TASK_TOOL_SCHEMA,
    REGENERATE_PLAN_TOOL_SCHEMA,
    GET_PLAN_TOOL_SCHEMA,
    VISUALIZE_PLAN_TOOL_SCHEMA,
    REVIEW_TASK_TOOL_SCHEMA,
    REVIEW_TASKS_TOOL_SCHEMA,
    REVIEW_EXECUTION_TOOL_SCHEMA,
    REVIEW_PLAN_TOOL_SCHEMA,
    GET_REVIEW_TOOL_SCHEMA,
    LIST_REVIEWS_TOOL_SCHEMA,
    STORE_MEMORY_TOOL_SCHEMA,
    RETRIEVE_MEMORY_TOOL_SCHEMA,
    SEARCH_MEMORIES_TOOL_SCHEMA,
    LIST_MEMORIES_TOOL_SCHEMA,
    DELETE_MEMORY_TOOL_SCHEMA,
    ARCHIVE_MEMORY_TOOL_SCHEMA,
    SUMMARIZE_MEMORIES_TOOL_SCHEMA,
    SYNTHESIZE_TOOL_SCHEMA,
    SYNTHESIZE_TASK_TOOL_SCHEMA,
    SYNTHESIZE_PLAN_TOOL_SCHEMA,
    GET_SYNTHESIS_TOOL_SCHEMA,
    LIST_SYNTHESES_TOOL_SCHEMA,
    DELETE_SYNTHESIS_TOOL_SCHEMA,
    REGISTER_AGENT_TOOL_SCHEMA,
    UNREGISTER_AGENT_TOOL_SCHEMA,
    GET_AGENT_TOOL_SCHEMA,
    LIST_AGENTS_TOOL_SCHEMA,
    CREATE_COLLABORATION_TOOL_SCHEMA,
    CLOSE_COLLABORATION_TOOL_SCHEMA,
    ASSIGN_AGENT_TOOL_SCHEMA,
    SEND_AGENT_MESSAGE_TOOL_SCHEMA,
    LIST_MESSAGES_TOOL_SCHEMA,
    LIST_ASSIGNMENTS_TOOL_SCHEMA,
    LIST_SESSIONS_TOOL_SCHEMA,
    REGISTER_CAPABILITY_TOOL_SCHEMA,
    UNREGISTER_CAPABILITY_TOOL_SCHEMA,
    GET_CAPABILITY_TOOL_SCHEMA,
    LIST_CAPABILITIES_TOOL_SCHEMA,
    ENABLE_CAPABILITY_TOOL_SCHEMA,
    DISABLE_CAPABILITY_TOOL_SCHEMA,
    REGISTER_PLUGIN_TOOL_SCHEMA,
    UNREGISTER_PLUGIN_TOOL_SCHEMA,
    LOAD_PLUGIN_TOOL_SCHEMA,
    UNLOAD_PLUGIN_TOOL_SCHEMA,
    LIST_PLUGINS_TOOL_SCHEMA,
    GET_PLUGIN_TOOL_SCHEMA,
    CAPABILITY_SUMMARY_TOOL_SCHEMA,
]


brain = AntigravityBrain(execute_model=lambda arguments: execute_model(arguments))


class McpError(Exception):
    def __init__(self, message: str, code: int = -32000) -> None:
        super().__init__(message)
        self.code = code


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        request = json.loads(line)
        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ai-orchestrator", "version": "0.1.0"},
            }
        elif method == "notifications/initialized":
            return None
        elif method == "tools/list":
            result = {"tools": TOOL_SCHEMAS}
        elif method == "tools/call":
            name = params.get("name")
            if name == "execute_model":
                payload = brain.execute(params.get("arguments") or {})
            elif name == "execute_models":
                payload = brain.execute_many(params.get("arguments") or {})
            elif name == "execute_task":
                payload = execute_task_tool(params.get("arguments") or {})
            elif name == "execute_tasks":
                payload = execute_tasks_tool(params.get("arguments") or {})
            elif name == "create_workspace":
                payload = create_workspace(params.get("arguments") or {})
            elif name == "get_workspace":
                payload = get_workspace(params.get("arguments") or {})
            elif name == "list_workspaces":
                payload = list_workspaces()
            elif name == "create_task":
                payload = create_task_tool(params.get("arguments") or {})
            elif name == "create_subtask":
                payload = create_subtask_tool(params.get("arguments") or {})
            elif name == "add_dependency":
                payload = add_dependency_tool(params.get("arguments") or {})
            elif name == "get_task":
                payload = get_task_tool(params.get("arguments") or {})
            elif name == "list_tasks":
                payload = list_tasks_tool(params.get("arguments") or {})
            elif name == "get_task_executions":
                payload = get_task_executions_tool(params.get("arguments") or {})
            elif name == "list_execution_bindings":
                payload = list_execution_bindings_tool(params.get("arguments") or {})
            elif name == "create_artifact":
                payload = create_artifact_tool(params.get("arguments") or {})
            elif name == "get_artifacts":
                payload = get_artifacts_tool(params.get("arguments") or {})
            elif name == "get_task_artifacts":
                payload = get_task_artifacts_tool(params.get("arguments") or {})
            elif name == "get_ready_tasks":
                payload = get_ready_tasks_tool(params.get("arguments") or {})
            elif name == "get_blocked_tasks":
                payload = get_blocked_tasks_tool(params.get("arguments") or {})
            elif name == "get_execution_queue":
                payload = get_execution_queue_tool(params.get("arguments") or {})
            elif name == "get_scheduler_state":
                payload = get_scheduler_state_tool(params.get("arguments") or {})
            elif name == "create_plan":
                payload = brain.create_plan(params.get("arguments") or {})
            elif name == "expand_task":
                payload = brain.expand_task(params.get("arguments") or {})
            elif name == "regenerate_plan":
                payload = brain.regenerate_plan(params.get("arguments") or {})
            elif name == "get_plan":
                args = params.get("arguments") or {}
                payload = brain.get_plan(workspace_id=args.get("workspace_id", ""), plan_id=args.get("plan_id"))
            elif name == "visualize_plan":
                args = params.get("arguments") or {}
                payload = brain.visualize_plan(
                    workspace_id=args.get("workspace_id", ""),
                    plan_id=args.get("plan_id"),
                    format=args.get("format", "text"),
                )
            elif name == "review_task":
                payload = review_task_tool(params.get("arguments") or {})
            elif name == "review_tasks":
                payload = review_tasks_tool(params.get("arguments") or {})
            elif name == "review_execution":
                payload = review_execution_tool(params.get("arguments") or {})
            elif name == "review_plan":
                payload = review_plan_tool(params.get("arguments") or {})
            elif name == "get_review":
                payload = get_review_tool(params.get("arguments") or {})
            elif name == "list_reviews":
                payload = list_reviews_tool(params.get("arguments") or {})
            elif name == "store_memory":
                payload = store_memory_tool(params.get("arguments") or {})
            elif name == "retrieve_memory":
                payload = retrieve_memory_tool(params.get("arguments") or {})
            elif name == "search_memories":
                payload = search_memories_tool(params.get("arguments") or {})
            elif name == "list_memories":
                payload = list_memories_tool(params.get("arguments") or {})
            elif name == "delete_memory":
                payload = delete_memory_tool(params.get("arguments") or {})
            elif name == "archive_memory":
                payload = archive_memory_tool(params.get("arguments") or {})
            elif name == "summarize_memories":
                payload = summarize_memories_tool(params.get("arguments") or {})
            elif name == "synthesize":
                payload = synthesize_tool(params.get("arguments") or {})
            elif name == "synthesize_task":
                payload = synthesize_task_tool(params.get("arguments") or {})
            elif name == "synthesize_plan":
                payload = synthesize_plan_tool(params.get("arguments") or {})
            elif name == "get_synthesis":
                payload = get_synthesis_tool(params.get("arguments") or {})
            elif name == "list_syntheses":
                payload = list_syntheses_tool(params.get("arguments") or {})
            elif name == "delete_synthesis":
                payload = delete_synthesis_tool(params.get("arguments") or {})
            elif name == "register_agent":
                payload = register_agent_tool(params.get("arguments") or {})
            elif name == "unregister_agent":
                payload = unregister_agent_tool(params.get("arguments") or {})
            elif name == "get_agent":
                payload = get_agent_tool(params.get("arguments") or {})
            elif name == "list_agents":
                payload = list_agents_tool(params.get("arguments") or {})
            elif name == "create_collaboration":
                payload = create_collaboration_tool(params.get("arguments") or {})
            elif name == "close_collaboration":
                payload = close_collaboration_tool(params.get("arguments") or {})
            elif name == "assign_agent":
                payload = assign_agent_tool(params.get("arguments") or {})
            elif name == "send_agent_message":
                payload = send_agent_message_tool(params.get("arguments") or {})
            elif name == "list_messages":
                payload = list_messages_tool(params.get("arguments") or {})
            elif name == "list_assignments":
                payload = list_assignments_tool(params.get("arguments") or {})
            elif name == "list_sessions":
                payload = list_sessions_tool(params.get("arguments") or {})
            elif name == "register_capability":
                payload = register_capability_tool(params.get("arguments") or {})
            elif name == "unregister_capability":
                payload = unregister_capability_tool(params.get("arguments") or {})
            elif name == "get_capability":
                payload = get_capability_tool(params.get("arguments") or {})
            elif name == "list_capabilities":
                payload = list_capabilities_tool(params.get("arguments") or {})
            elif name == "enable_capability":
                payload = enable_capability_tool(params.get("arguments") or {})
            elif name == "disable_capability":
                payload = disable_capability_tool(params.get("arguments") or {})
            elif name == "register_plugin":
                payload = register_plugin_tool(params.get("arguments") or {})
            elif name == "unregister_plugin":
                payload = unregister_plugin_tool(params.get("arguments") or {})
            elif name == "load_plugin":
                payload = load_plugin_tool(params.get("arguments") or {})
            elif name == "unload_plugin":
                payload = unload_plugin_tool(params.get("arguments") or {})
            elif name == "list_plugins":
                payload = list_plugins_tool(params.get("arguments") or {})
            elif name == "get_plugin":
                payload = get_plugin_tool(params.get("arguments") or {})
            elif name == "capability_summary":
                payload = capability_summary_tool(params.get("arguments") or {})
            else:
                raise McpError(f"Unknown tool: {name}", -32602)
            result = {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}
        else:
            raise McpError(f"Method not found: {method}", -32601)

        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except McpError as exc:
        return error_response(request_id, exc.code, str(exc))
    except Exception as exc:  # Keep unexpected failures visible to Antigravity.
        return error_response(request_id, -32000, str(exc))


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def create_workspace(arguments: dict[str, Any]) -> dict[str, Any]:
    metadata = arguments.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise McpError("metadata must be an object.", -32602)

    workspace = workspace_store.create_workspace(
        title=arguments.get("title"),
        metadata=metadata,
    )
    return {
        "workspace_id": workspace.workspace_id,
        "created_at": workspace.created_at,
    }


def get_workspace(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return workspace_to_dict(workspace_store.get_workspace(str(workspace_id)))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_workspaces() -> dict[str, Any]:
    return {"workspaces": [workspace_summary(workspace) for workspace in workspace_store.list_workspaces()]}


def execute_model(arguments: dict[str, Any]) -> dict[str, Any]:
    provider = str(arguments.get("provider", "")).lower()
    if provider not in DEFAULT_MODELS:
        raise McpError("provider must be one of: gemini, groq, openrouter, ollama", -32602)

    model = arguments.get("model") or DEFAULT_MODELS[provider]
    messages = normalize_messages(arguments)

    try:
        if provider == "gemini":
            return call_gemini(model, messages)
        if provider == "groq":
            return call_openai_compatible(
                "groq",
                model,
                messages,
                "https://api.groq.com/openai/v1/chat/completions",
                "GROQ_API_KEY",
                config.groq_api_key,
            )
        if provider == "openrouter":
            return call_openai_compatible(
                "openrouter",
                model,
                messages,
                "https://openrouter.ai/api/v1/chat/completions",
                "OPENROUTER_API_KEY",
                config.openrouter_api_key,
            )
        if provider == "ollama":
            return call_ollama(model, messages)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return failure(provider, model, f"HTTP {exc.code}", body)
    except urllib.error.URLError as exc:
        return failure(provider, model, "connection_error", str(exc.reason))

    raise McpError(f"Unsupported provider: {provider}", -32602)


def normalize_messages(arguments: dict[str, Any]) -> list[dict[str, str]]:
    prompt = arguments.get("prompt")
    messages = arguments.get("messages")

    if prompt and messages:
        raise McpError("Use either prompt or messages, not both.", -32602)
    if prompt:
        return [{"role": "user", "content": str(prompt)}]
    if isinstance(messages, list) and messages:
        normalized = []
        for message in messages:
            if not isinstance(message, dict) or "role" not in message or "content" not in message:
                raise McpError("Each message must include role and content.", -32602)
            normalized.append({"role": str(message["role"]), "content": str(message["content"])})
        return normalized

    raise McpError("Either prompt or messages is required.", -32602)


def call_openai_compatible(provider: str, model: str, messages: list[dict[str, str]], url: str, api_key_name: str, api_key: str) -> dict[str, Any]:
    if not api_key:
        return failure(provider, model, "missing_api_key", f"Set {api_key_name}.")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://localhost/ai-orchestrator"
        headers["X-Title"] = "AI Orchestrator"

    data = post_json(url, {"model": model, "messages": messages}, headers)
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}

    return success(
        provider=provider,
        model=data.get("model", model),
        text=message.get("content", ""),
        raw=data,
    )


def call_gemini(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    api_key = config.gemini_api_key
    if not api_key:
        return failure("gemini", model, "missing_api_key", "Set GEMINI_API_KEY.")

    contents = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message["content"]}]})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    data = post_json(url, {"contents": contents}, {"Content-Type": "application/json"})
    candidate = (data.get("candidates") or [{}])[0]
    parts = ((candidate.get("content") or {}).get("parts") or [])
    text = "".join(part.get("text", "") for part in parts)

    return success(provider="gemini", model=model, text=text, raw=data)


def call_ollama(model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    host = config.ollama_base_url.rstrip("/")
    data = post_json(f"{host}/api/chat", {"model": model, "messages": messages, "stream": False}, {"Content-Type": "application/json"})
    message = data.get("message") or {}
    return success(provider="ollama", model=data.get("model", model), text=message.get("content", ""), raw=data)


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def success(provider: str, model: str, text: str, raw: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "provider": provider, "model": model, "text": text, "raw": raw}


def failure(provider: str, model: str, error: str, detail: str) -> dict[str, Any]:
    return {"ok": False, "provider": provider, "model": model, "error": error, "detail": detail}


def get_task_graph(workspace_id: str):
    try:
        workspace = workspace_store.get_workspace(workspace_id)
        return workspace.task_graph
    except KeyError as exc:
        raise McpError(f"Workspace not found: {workspace_id}", -32602) from exc


def create_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    graph = get_task_graph(str(workspace_id))

    title = arguments.get("title")
    if not title:
        raise McpError("title is required.", -32602)

    status_str = arguments.get("status", "PENDING")
    try:
        status = TaskStatus(status_str)
    except ValueError as exc:
        raise McpError(f"Invalid status: {status_str}", -32602) from exc

    try:
        node = graph.create_task(
            title=str(title),
            description=arguments.get("description"),
            metadata=arguments.get("metadata"),
            status=status,
            task_id=arguments.get("task_id"),
        )
        return node.to_dict()
    except Exception as exc:
        raise McpError(str(exc), -32602) from exc


def create_subtask_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    graph = get_task_graph(str(workspace_id))

    parent_task_id = arguments.get("parent_task_id")
    if not parent_task_id:
        raise McpError("parent_task_id is required.", -32602)

    title = arguments.get("title")
    if not title:
        raise McpError("title is required.", -32602)

    status_str = arguments.get("status", "PENDING")
    try:
        status = TaskStatus(status_str)
    except ValueError as exc:
        raise McpError(f"Invalid status: {status_str}", -32602) from exc

    try:
        node = graph.create_subtask(
            parent_task_id=str(parent_task_id),
            title=str(title),
            description=arguments.get("description"),
            metadata=arguments.get("metadata"),
            status=status,
            task_id=arguments.get("task_id"),
        )
        return node.to_dict()
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except Exception as exc:
        raise McpError(str(exc), -32602) from exc


def add_dependency_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    graph = get_task_graph(str(workspace_id))

    source_task_id = arguments.get("source_task_id")
    if not source_task_id:
        raise McpError("source_task_id is required.", -32602)

    target_task_id = arguments.get("target_task_id")
    if not target_task_id:
        raise McpError("target_task_id is required.", -32602)

    dep_type_str = arguments.get("dependency_type", "DEPENDS_ON")
    try:
        dep_type = DependencyType(dep_type_str)
    except ValueError as exc:
        raise McpError(f"Invalid dependency_type: {dep_type_str}", -32602) from exc

    try:
        edge = graph.add_dependency(
            source_task_id=str(source_task_id),
            target_task_id=str(target_task_id),
            dependency_type=dep_type,
        )
        return edge.to_dict()
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except Exception as exc:
        raise McpError(str(exc), -32602) from exc


def get_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    graph = get_task_graph(str(workspace_id))

    task_id = arguments.get("task_id")
    if not task_id:
        raise McpError("task_id is required.", -32602)

    try:
        node = graph.get_task(str(task_id))
        return node.to_dict()
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_tasks_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    graph = get_task_graph(str(workspace_id))

    return {"tasks": [node.to_dict() for node in graph.list_tasks()]}


def get_task_executions_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    task_id = arguments.get("task_id")
    if not task_id:
        raise McpError("task_id is required.", -32602)

    try:
        workspace = workspace_store.get_workspace(str(workspace_id))
        workspace.task_graph.get_task(str(task_id)) # Verify task exists
        bindings = workspace.task_execution_index.get_task_executions(str(task_id))
        return {
            "workspace_id": str(workspace_id),
            "task_id": str(task_id),
            "bindings": [b.to_dict() for b in bindings]
        }
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_execution_bindings_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)

    try:
        workspace = workspace_store.get_workspace(str(workspace_id))
        bindings = workspace.task_execution_index.list_bindings()
        return {
            "workspace_id": str(workspace_id),
            "bindings": [b.to_dict() for b in bindings]
        }
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 3 – Task execution & artifact tools
# ---------------------------------------------------------------------------

def execute_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    task_id = arguments.get("task_id")
    if not task_id:
        raise McpError("task_id is required.", -32602)
    if not arguments.get("provider"):
        raise McpError("provider is required.", -32602)

    try:
        return brain.execute_task(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def execute_tasks_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not isinstance(arguments.get("tasks"), list) or not arguments["tasks"]:
        raise McpError("tasks must be a non-empty list.", -32602)

    try:
        return brain.execute_tasks(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def create_artifact_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    from uuid import uuid4
    from datetime import UTC, datetime

    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    name = arguments.get("name")
    if not name:
        raise McpError("name is required.", -32602)
    artifact_type_str = arguments.get("artifact_type")
    if not artifact_type_str:
        raise McpError("artifact_type is required.", -32602)
    content = arguments.get("content")
    if content is None:
        raise McpError("content is required.", -32602)

    try:
        atype = ArtifactType(str(artifact_type_str).upper())
    except ValueError as exc:
        raise McpError(f"Invalid artifact_type: {artifact_type_str}", -32602) from exc

    try:
        workspace = workspace_store.get_workspace(str(workspace_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc

    artifact = Artifact(
        artifact_id=str(uuid4()),
        task_id=arguments.get("task_id"),
        execution_id=arguments.get("execution_id"),
        workspace_id=str(workspace_id),
        name=str(name),
        artifact_type=atype,
        mime_type=str(arguments.get("mime_type") or "text/plain"),
        content=content,
        metadata=arguments.get("metadata") or {},
        created_at=datetime.now(UTC).isoformat(),
    )
    workspace.artifact_store.create_artifact(artifact)
    return {
        "artifact_id": artifact.artifact_id,
        "workspace_id": artifact.workspace_id,
        "name": artifact.name,
        "artifact_type": artifact.artifact_type.value,
        "created_at": artifact.created_at,
    }


def _artifact_to_dict(a: Artifact) -> dict[str, Any]:
    return {
        "artifact_id": a.artifact_id,
        "task_id": a.task_id,
        "execution_id": a.execution_id,
        "workspace_id": a.workspace_id,
        "name": a.name,
        "artifact_type": a.artifact_type.value if hasattr(a.artifact_type, "value") else a.artifact_type,
        "mime_type": a.mime_type,
        "metadata": a.metadata,
        "created_at": a.created_at,
    }


def get_artifacts_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        workspace = workspace_store.get_workspace(str(workspace_id))
        return {
            "workspace_id": str(workspace_id),
            "artifacts": [_artifact_to_dict(a) for a in workspace.artifact_store.list_artifacts()],
        }
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def get_task_artifacts_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    task_id = arguments.get("task_id")
    if not task_id:
        raise McpError("task_id is required.", -32602)
    try:
        workspace = workspace_store.get_workspace(str(workspace_id))
        workspace.task_graph.get_task(str(task_id))  # verify task exists
        return {
            "workspace_id": str(workspace_id),
            "task_id": str(task_id),
            "artifacts": [_artifact_to_dict(a) for a in workspace.artifact_store.list_task_artifacts(str(task_id))],
        }
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 4 – Dependency-Aware Scheduler tools
# ---------------------------------------------------------------------------

def get_ready_tasks_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.get_ready_tasks(str(workspace_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def get_blocked_tasks_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.get_blocked_tasks(str(workspace_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def get_execution_queue_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.get_execution_queue(str(workspace_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def get_scheduler_state_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.get_scheduler_state(str(workspace_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 6 – Review & Validation Engine tools
# ---------------------------------------------------------------------------

def review_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    task_id = arguments.get("task_id")
    if not task_id:
        raise McpError("task_id is required.", -32602)
    try:
        return brain.review_task(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def review_tasks_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.review_tasks(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def review_execution_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    execution_id = arguments.get("execution_id")
    if not execution_id:
        raise McpError("execution_id is required.", -32602)
    try:
        return brain.review_execution(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def review_plan_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.review_plan(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def get_review_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(arguments.get("workspace_id") or "")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    report_id = str(arguments.get("report_id") or "")
    if not report_id:
        raise McpError("report_id is required.", -32602)
    try:
        return brain.get_review(workspace_id=workspace_id, report_id=report_id)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_reviews_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(arguments.get("workspace_id") or "")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_reviews(workspace_id=workspace_id)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 7 – Long-Term Memory tools
# ---------------------------------------------------------------------------

def store_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not arguments.get("title"):
        raise McpError("title is required.", -32602)
    if arguments.get("content") is None:
        raise McpError("content is required.", -32602)
    try:
        return brain.store_memory(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def retrieve_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    memory_id = arguments.get("memory_id")
    if not memory_id:
        raise McpError("memory_id is required.", -32602)
    try:
        return brain.retrieve_memory(workspace_id=str(workspace_id), memory_id=str(memory_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def search_memories_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.search_memories(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_memories_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_memories(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def delete_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    memory_id = arguments.get("memory_id")
    if not memory_id:
        raise McpError("memory_id is required.", -32602)
    try:
        return brain.delete_memory(workspace_id=str(workspace_id), memory_id=str(memory_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def archive_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    memory_id = arguments.get("memory_id")
    if not memory_id:
        raise McpError("memory_id is required.", -32602)
    try:
        return brain.archive_memory(workspace_id=str(workspace_id), memory_id=str(memory_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def summarize_memories_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.summarize_memories(workspace_id=str(workspace_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 8 – Result Synthesis Engine tools
# ---------------------------------------------------------------------------

def synthesize_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not arguments.get("title"):
        raise McpError("title is required.", -32602)
    try:
        return brain.synthesize(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def synthesize_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    task_id = arguments.get("task_id")
    if not task_id:
        raise McpError("task_id is required.", -32602)
    try:
        return brain.synthesize_task(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def synthesize_plan_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.synthesize_plan(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def get_synthesis_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(arguments.get("workspace_id") or "")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    report_id = str(arguments.get("report_id") or "")
    if not report_id:
        raise McpError("report_id is required.", -32602)
    try:
        return brain.get_synthesis(workspace_id=workspace_id, report_id=report_id)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_syntheses_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(arguments.get("workspace_id") or "")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_syntheses(workspace_id=workspace_id)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def delete_synthesis_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(arguments.get("workspace_id") or "")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    report_id = str(arguments.get("report_id") or "")
    if not report_id:
        raise McpError("report_id is required.", -32602)
    try:
        return brain.delete_synthesis(workspace_id=workspace_id, report_id=report_id)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 9 – Multi-Agent Collaboration Framework tools
# ---------------------------------------------------------------------------

def register_agent_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not arguments.get("name"):
        raise McpError("name is required.", -32602)
    try:
        return brain.register_agent(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def unregister_agent_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    agent_id = arguments.get("agent_id")
    if not agent_id:
        raise McpError("agent_id is required.", -32602)
    try:
        return brain.unregister_agent(workspace_id=str(workspace_id), agent_id=str(agent_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def get_agent_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    agent_id = arguments.get("agent_id")
    if not agent_id:
        raise McpError("agent_id is required.", -32602)
    try:
        return brain.get_agent(workspace_id=str(workspace_id), agent_id=str(agent_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_agents_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_agents(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def create_collaboration_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not arguments.get("objective"):
        raise McpError("objective is required.", -32602)
    try:
        return brain.create_collaboration(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def close_collaboration_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    session_id = arguments.get("session_id")
    if not session_id:
        raise McpError("session_id is required.", -32602)
    try:
        return brain.close_collaboration(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def assign_agent_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    session_id = arguments.get("session_id")
    if not session_id:
        raise McpError("session_id is required.", -32602)
    agent_id = arguments.get("agent_id")
    if not agent_id:
        raise McpError("agent_id is required.", -32602)
    try:
        return brain.assign_agent(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def send_agent_message_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    session_id = arguments.get("session_id")
    if not session_id:
        raise McpError("session_id is required.", -32602)
    sender_agent_id = arguments.get("sender_agent_id")
    if not sender_agent_id:
        raise McpError("sender_agent_id is required.", -32602)
    if arguments.get("content") is None:
        raise McpError("content is required.", -32602)
    try:
        return brain.send_agent_message(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def list_messages_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    session_id = arguments.get("session_id")
    if not session_id:
        raise McpError("session_id is required.", -32602)
    try:
        return brain.list_messages(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_assignments_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_assignments(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_sessions_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_sessions(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


# ---------------------------------------------------------------------------
# Capability 10 – Capability Registry & Plugin Framework tools
# ---------------------------------------------------------------------------

def register_capability_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not arguments.get("capability_id"):
        raise McpError("capability_id is required.", -32602)
    if not arguments.get("name"):
        raise McpError("name is required.", -32602)
    try:
        return brain.register_capability(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def unregister_capability_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    capability_id = arguments.get("capability_id")
    if not capability_id:
        raise McpError("capability_id is required.", -32602)
    try:
        return brain.unregister_capability(workspace_id=str(workspace_id), capability_id=str(capability_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def get_capability_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    capability_id = arguments.get("capability_id")
    if not capability_id:
        raise McpError("capability_id is required.", -32602)
    try:
        return brain.get_capability(workspace_id=str(workspace_id), capability_id=str(capability_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_capabilities_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_capabilities(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def enable_capability_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    capability_id = arguments.get("capability_id")
    if not capability_id:
        raise McpError("capability_id is required.", -32602)
    try:
        return brain.enable_capability(workspace_id=str(workspace_id), capability_id=str(capability_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def disable_capability_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    capability_id = arguments.get("capability_id")
    if not capability_id:
        raise McpError("capability_id is required.", -32602)
    try:
        return brain.disable_capability(workspace_id=str(workspace_id), capability_id=str(capability_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def register_plugin_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    if not arguments.get("plugin_id"):
        raise McpError("plugin_id is required.", -32602)
    if not arguments.get("name"):
        raise McpError("name is required.", -32602)
    try:
        return brain.register_plugin(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc
    except ValueError as exc:
        raise McpError(str(exc), -32602) from exc


def unregister_plugin_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    plugin_id = arguments.get("plugin_id")
    if not plugin_id:
        raise McpError("plugin_id is required.", -32602)
    try:
        return brain.unregister_plugin(workspace_id=str(workspace_id), plugin_id=str(plugin_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def load_plugin_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    plugin_id = arguments.get("plugin_id")
    if not plugin_id:
        raise McpError("plugin_id is required.", -32602)
    try:
        return brain.load_plugin(workspace_id=str(workspace_id), plugin_id=str(plugin_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def unload_plugin_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    plugin_id = arguments.get("plugin_id")
    if not plugin_id:
        raise McpError("plugin_id is required.", -32602)
    try:
        return brain.unload_plugin(workspace_id=str(workspace_id), plugin_id=str(plugin_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def list_plugins_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.list_plugins(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def get_plugin_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    plugin_id = arguments.get("plugin_id")
    if not plugin_id:
        raise McpError("plugin_id is required.", -32602)
    try:
        return brain.get_plugin(workspace_id=str(workspace_id), plugin_id=str(plugin_id))
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


def capability_summary_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    workspace_id = arguments.get("workspace_id")
    if not workspace_id:
        raise McpError("workspace_id is required.", -32602)
    try:
        return brain.get_capability_summary(arguments)
    except KeyError as exc:
        raise McpError(str(exc), -32602) from exc


if __name__ == "__main__":
    main()
