import json
import subprocess
import sys


def send(process, message):
    process.stdin.write(json.dumps(message) + "\n")
    process.stdin.flush()
    return json.loads(process.stdout.readline())


def test_mcp_smoke():
    process = subprocess.Popen(
        [sys.executable, "ai_orchestrator_mcp.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        initialized = send(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert initialized["result"]["serverInfo"]["name"] == "ai-orchestrator"

        tools = send(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tool_names = [tool["name"] for tool in tools["result"]["tools"]]
        assert "execute_model" in tool_names
        assert "execute_models" in tool_names
        assert "create_workspace" in tool_names
        assert "get_workspace" in tool_names
        assert "list_workspaces" in tool_names
        assert "create_task" in tool_names
        assert "create_subtask" in tool_names
        assert "add_dependency" in tool_names
        assert "get_task" in tool_names
        assert "list_tasks" in tool_names
        assert "get_task_executions" in tool_names
        assert "list_execution_bindings" in tool_names
        assert "create_plan" in tool_names
        assert "expand_task" in tool_names
        assert "regenerate_plan" in tool_names
        assert "get_plan" in tool_names
        assert "visualize_plan" in tool_names

        # Smoke test creating a workspace and then a task in it
        ws_res = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "create_workspace",
                    "arguments": {"title": "Smoke WS"},
                },
            },
        )
        ws_data = json.loads(ws_res["result"]["content"][0]["text"])
        ws_id = ws_data["workspace_id"]
        assert ws_id

        task_res = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "create_task",
                    "arguments": {
                        "workspace_id": ws_id,
                        "title": "Smoke Task",
                    },
                },
            },
        )
        task_data = json.loads(task_res["result"]["content"][0]["text"])
        assert task_data["task_id"]
        assert task_data["title"] == "Smoke Task"

        result = send(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "execute_model",
                    "arguments": {"provider": "groq"},
                },
            },
        )
        assert result["error"]["message"] == "Either prompt or messages is required."
    finally:
        process.kill()


def test_mcp_execution_binding_tools():
    from unittest.mock import patch
    import ai_orchestrator_mcp

    with patch("ai_orchestrator_mcp.execute_model") as mock_exec:
        mock_exec.return_value = {
            "ok": True,
            "provider": "gemini",
            "model": "gemini-1.5-flash",
            "text": "mcp response",
            "raw": {"mock": True},
        }

        # 1. Create Workspace
        res = ai_orchestrator_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "create_workspace",
                "arguments": {"title": "MCP WS"},
            },
        })
        ws_data = json.loads(res["result"]["content"][0]["text"])
        ws_id = ws_data["workspace_id"]

        # 2. Create Task
        res = ai_orchestrator_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "create_task",
                "arguments": {
                    "workspace_id": ws_id,
                    "title": "MCP Task",
                },
            },
        })
        task_data = json.loads(res["result"]["content"][0]["text"])
        task_id = task_data["task_id"]

        # 3. Execute Model with task_id
        res = ai_orchestrator_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "execute_model",
                "arguments": {
                    "workspace_id": ws_id,
                    "task_id": task_id,
                    "provider": "gemini",
                    "prompt": "hello mcp",
                    "execution_type": "SYNTHESIS",
                },
            },
        })
        exec_data = json.loads(res["result"]["content"][0]["text"])
        assert exec_data["ok"] is True

        # 4. Get Task Executions
        res = ai_orchestrator_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_task_executions",
                "arguments": {
                    "workspace_id": ws_id,
                    "task_id": task_id,
                },
            },
        })
        bind_data = json.loads(res["result"]["content"][0]["text"])
        assert bind_data["workspace_id"] == ws_id
        assert bind_data["task_id"] == task_id
        assert len(bind_data["bindings"]) == 1
        assert bind_data["bindings"][0]["execution_type"] == "SYNTHESIS"

        # 5. List Execution Bindings
        res = ai_orchestrator_mcp.handle_request({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "list_execution_bindings",
                "arguments": {
                    "workspace_id": ws_id,
                },
            },
        })
        list_data = json.loads(res["result"]["content"][0]["text"])
        assert list_data["workspace_id"] == ws_id
        assert len(list_data["bindings"]) == 1
        assert list_data["bindings"][0]["task_id"] == task_id
        assert list_data["bindings"][0]["execution_type"] == "SYNTHESIS"


def test_mcp_planner_tools():
    import ai_orchestrator_mcp

    # 1. Create Workspace
    res = ai_orchestrator_mcp.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_workspace",
            "arguments": {"title": "Planner MCP WS"},
        },
    })
    ws_data = json.loads(res["result"]["content"][0]["text"])
    ws_id = ws_data["workspace_id"]

    # 2. Create Plan via MCP
    res = ai_orchestrator_mcp.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "create_plan",
            "arguments": {
                "workspace_id": ws_id,
                "objective": {"title": "Build Capability 5 MCP Plan"},
            },
        },
    })
    plan_data = json.loads(res["result"]["content"][0]["text"])
    assert plan_data["status"] == "VALIDATED"
    plan_id = plan_data["plan_id"]

    # 3. Get Plan via MCP
    res = ai_orchestrator_mcp.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_plan",
            "arguments": {"workspace_id": ws_id, "plan_id": plan_id},
        },
    })
    get_data = json.loads(res["result"]["content"][0]["text"])
    assert get_data["plan_id"] == plan_id

    # 4. Visualize Plan via MCP
    res = ai_orchestrator_mcp.handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "visualize_plan",
            "arguments": {"workspace_id": ws_id, "plan_id": plan_id, "format": "mermaid"},
        },
    })
    viz_data = json.loads(res["result"]["content"][0]["text"])
    assert "graph TD" in viz_data["visualization"]


