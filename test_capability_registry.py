"""Comprehensive test suite for Capability Registry & Plugin Framework (Capability 10)."""

import json
from concurrent.futures import ThreadPoolExecutor
import pytest

from capability_models import (
    Capability,
    CapabilityStatus,
    CapabilityType,
    Plugin,
    PluginStatus,
    CapabilitySummary,
)
from capability_registry import CapabilityRegistry
from plugin_manager import PluginManager
from workspace import TaskWorkspace, workspace_store, workspace_to_dict
from brain import AntigravityBrain
from ai_orchestrator_mcp import handle_request, TOOL_SCHEMAS


# ---------------------------------------------------------------------------
# 1. Domain Models Tests
# ---------------------------------------------------------------------------

def test_capability_model_serialization():
    cap = Capability(
        capability_id="cap-1",
        name="Planner",
        version="1.0.0",
        description="Task planning capability",
        capability_type=CapabilityType.CORE,
        status=CapabilityStatus.ENABLED,
        dependencies=["cap-0"],
        mcp_tools=["create_plan", "expand_task"],
        metadata={"author": "AI-Orchestrator"},
    )
    d = cap.to_dict()
    assert d["capability_id"] == "cap-1"
    assert d["name"] == "Planner"
    assert d["version"] == "1.0.0"
    assert d["capability_type"] == "CORE"
    assert d["status"] == "ENABLED"
    assert d["dependencies"] == ["cap-0"]
    assert d["mcp_tools"] == ["create_plan", "expand_task"]
    assert d["metadata"] == {"author": "AI-Orchestrator"}


def test_plugin_model_serialization():
    cap = Capability(
        capability_id="cap-ext",
        name="Extenser",
        version="0.5.0",
        description="Extension cap",
    )
    plugin = Plugin(
        plugin_id="plugin-1",
        name="Sample Plugin",
        version="1.0.0",
        description="Plugin test",
        status=PluginStatus.LOADED,
        capabilities=[cap],
        metadata={"category": "analytics"},
    )
    d = plugin.to_dict()
    assert d["plugin_id"] == "plugin-1"
    assert d["status"] == "LOADED"
    assert len(d["capabilities"]) == 1
    assert d["capabilities"][0]["capability_id"] == "cap-ext"


def test_capability_summary_serialization():
    summary = CapabilitySummary(
        capability_count=5,
        enabled_count=3,
        disabled_count=2,
        plugin_count=1,
        version_summary={"cap-1": "1.0.0"},
    )
    d = summary.to_dict()
    assert d["capability_count"] == 5
    assert d["enabled_count"] == 3
    assert d["disabled_count"] == 2
    assert d["plugin_count"] == 1
    assert d["version_summary"] == {"cap-1": "1.0.0"}


# ---------------------------------------------------------------------------
# 2. CapabilityRegistry Tests
# ---------------------------------------------------------------------------

def test_registry_registration_and_retrieval():
    reg = CapabilityRegistry()
    cap = Capability(capability_id="c1", name="Cap 1", version="1.0.0", description="Desc 1")
    reg.register_capability(cap)

    fetched = reg.get_capability("c1")
    assert fetched.capability_id == "c1"

    with pytest.raises(ValueError, match="already registered"):
        reg.register_capability(cap)

    with pytest.raises(KeyError, match="not found"):
        reg.get_capability("nonexistent")


def test_registry_deterministic_ordering():
    reg = CapabilityRegistry()
    reg.register_capability(Capability(capability_id="z_cap", name="Z", version="1.0", description=""))
    reg.register_capability(Capability(capability_id="a_cap", name="A", version="1.0", description=""))
    reg.register_capability(Capability(capability_id="m_cap", name="M", version="1.0", description=""))

    caps = reg.list_capabilities()
    ids = [c.capability_id for c in caps]
    assert ids == ["a_cap", "m_cap", "z_cap"]


def test_registry_enable_disable_and_dependencies():
    reg = CapabilityRegistry()
    c1 = Capability(capability_id="c1", name="Base", version="1.0", description="")
    c2 = Capability(capability_id="c2", name="Dependent", version="1.0", description="", dependencies=["c1"])

    reg.register_capability(c1)
    reg.register_capability(c2)

    # Attempting to enable c2 should fail because c1 is not ENABLED
    assert not reg.validate_dependencies("c2")
    with pytest.raises(ValueError, match="is not ENABLED"):
        reg.enable_capability("c2")

    # Enable c1 first
    reg.enable_capability("c1")
    assert c1.status == CapabilityStatus.ENABLED

    # Now enabling c2 should succeed
    assert reg.validate_dependencies("c2")
    reg.enable_capability("c2")
    assert c2.status == CapabilityStatus.ENABLED

    # Disabling c1 should fail because active c2 depends on it
    with pytest.raises(ValueError, match="enabled capabilities depend on it"):
        reg.disable_capability("c1")

    # Disable c2 first, then c1
    reg.disable_capability("c2")
    assert c2.status == CapabilityStatus.DISABLED
    reg.disable_capability("c1")
    assert c1.status == CapabilityStatus.DISABLED


def test_registry_unregister_and_dependents():
    reg = CapabilityRegistry()
    c1 = Capability(capability_id="c1", name="Base", version="1.0", description="")
    c2 = Capability(capability_id="c2", name="Dependent", version="1.0", description="", dependencies=["c1"])

    reg.register_capability(c1)
    reg.register_capability(c2)

    assert reg.list_dependents("c1") == ["c2"]

    # Cannot unregister c1 while c2 exists
    with pytest.raises(ValueError, match="depended upon by"):
        reg.unregister_capability("c1")

    reg.unregister_capability("c2")
    unregistered = reg.unregister_capability("c1")
    assert unregistered.capability_id == "c1"


def test_registry_summary():
    reg = CapabilityRegistry()
    c1 = Capability(capability_id="c1", name="Cap 1", version="1.0", description="")
    c2 = Capability(capability_id="c2", name="Cap 2", version="2.0", description="")
    reg.register_capability(c1)
    reg.register_capability(c2)
    reg.enable_capability("c1")

    summary = reg.summary(plugin_count=2)
    assert summary.capability_count == 2
    assert summary.enabled_count == 1
    assert summary.disabled_count == 0
    assert summary.plugin_count == 2
    assert summary.version_summary == {"c1": "1.0", "c2": "2.0"}


def test_registry_thread_safety():
    reg = CapabilityRegistry()

    def _register(i: int):
        cap = Capability(
            capability_id=f"cap-{i:03d}",
            name=f"Cap {i}",
            version="1.0.0",
            description="",
        )
        reg.register_capability(cap)

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(_register, range(50)))

    caps = reg.list_capabilities()
    assert len(caps) == 50


# ---------------------------------------------------------------------------
# 3. PluginManager Tests
# ---------------------------------------------------------------------------

def test_plugin_manager_lifecycle():
    reg = CapabilityRegistry()
    pm = PluginManager(capability_registry=reg)

    c1 = Capability(capability_id="plug-cap-1", name="Cap 1", version="1.0", description="")
    plugin = Plugin(
        plugin_id="plug-1",
        name="Test Plugin",
        version="1.0.0",
        description="Desc",
        capabilities=[c1],
    )

    pm.register_plugin(plugin)
    assert pm.get_plugin("plug-1").status == PluginStatus.LOADED
    # Forwarded into capability registry
    assert reg.get_capability("plug-cap-1").capability_id == "plug-cap-1"

    # Duplicate prevention
    with pytest.raises(ValueError, match="already registered"):
        pm.register_plugin(plugin)

    assert pm.validate_plugin("plug-1") is True

    # Unload plugin
    pm.unload_plugin("plug-1")
    assert pm.get_plugin("plug-1").status == PluginStatus.UNLOADED

    # Load plugin
    pm.load_plugin("plug-1")
    assert pm.get_plugin("plug-1").status == PluginStatus.LOADED

    # Unregister plugin
    unreg = pm.unregister_plugin("plug-1")
    assert unreg.plugin_id == "plug-1"

    # Capability also removed from registry
    with pytest.raises(KeyError):
        reg.get_capability("plug-cap-1")


def test_plugin_manager_summary():
    reg = CapabilityRegistry()
    pm = PluginManager(capability_registry=reg)
    pm.register_plugin(Plugin(plugin_id="p1", name="P1", version="1.0", description=""))
    pm.register_plugin(Plugin(plugin_id="p2", name="P2", version="1.0", description=""))
    pm.unload_plugin("p2")

    s = pm.summary()
    assert s["plugin_count"] == 2
    assert s["loaded_count"] == 1
    assert s["unloaded_count"] == 1
    assert s["error_count"] == 0


# ---------------------------------------------------------------------------
# 4. TaskWorkspace Integration Tests
# ---------------------------------------------------------------------------

def test_workspace_owns_registry_and_plugin_manager():
    ws = TaskWorkspace(workspace_id="ws-cap10-1", created_at="2026-01-01T00:00:00Z")
    assert isinstance(ws.capability_registry, CapabilityRegistry)
    assert isinstance(ws.plugin_manager, PluginManager)

    # Verify workspace serialization
    cap = Capability(capability_id="ws-c1", name="WS Cap", version="1.0", description="")
    ws.capability_registry.register_capability(cap)

    plug = Plugin(plugin_id="ws-p1", name="WS Plug", version="1.0", description="")
    ws.plugin_manager.register_plugin(plug)

    d = workspace_to_dict(ws)
    assert "capabilities" in d
    assert "plugins" in d
    assert "capability_summary" in d

    assert len(d["capabilities"]) >= 1
    assert len(d["plugins"]) == 1
    assert d["capability_summary"]["plugin_count"] == 1


# ---------------------------------------------------------------------------
# 5. AntigravityBrain Façade Routing Tests
# ---------------------------------------------------------------------------

def test_brain_facade_routing():
    ws = workspace_store.create_workspace(title="Brain Test Workspace")
    brain = AntigravityBrain(execute_model=lambda args: {})

    # Register capability via brain
    res = brain.register_capability(
        workspace_id=ws.workspace_id,
        capability_id="brain-c1",
        name="Brain Capability",
        version="1.0.0",
        description="Test desc",
    )
    assert res["capability"]["capability_id"] == "brain-c1"

    # List capabilities via brain
    res = brain.list_capabilities(ws.workspace_id)
    assert len(res["capabilities"]) == 1

    # Get capability via brain
    res = brain.get_capability(ws.workspace_id, "brain-c1")
    assert res["capability"]["name"] == "Brain Capability"

    # Enable capability via brain
    res = brain.enable_capability(ws.workspace_id, "brain-c1")
    assert res["capability"]["status"] == "ENABLED"

    # Disable capability via brain
    res = brain.disable_capability(ws.workspace_id, "brain-c1")
    assert res["capability"]["status"] == "DISABLED"

    # Register plugin via brain
    res = brain.register_plugin(
        workspace_id=ws.workspace_id,
        plugin_id="brain-p1",
        name="Brain Plugin",
        version="1.0.0",
        description="Desc",
        capabilities=[{"capability_id": "p-cap-1", "name": "P Cap 1", "version": "1.0", "description": ""}],
    )
    assert res["plugin"]["plugin_id"] == "brain-p1"

    # List plugins via brain
    res = brain.list_plugins(ws.workspace_id)
    assert len(res["plugins"]) == 1

    # Get plugin via brain
    res = brain.get_plugin(ws.workspace_id, "brain-p1")
    assert res["plugin"]["name"] == "Brain Plugin"

    # Unload & Load plugin via brain
    res = brain.unload_plugin(ws.workspace_id, "brain-p1")
    assert res["plugin"]["status"] == "UNLOADED"

    res = brain.load_plugin(ws.workspace_id, "brain-p1")
    assert res["plugin"]["status"] == "LOADED"

    # Capability summary via brain
    res = brain.get_capability_summary(ws.workspace_id)
    assert res["summary"]["capability_count"] == 2
    assert res["summary"]["plugin_count"] == 1

    # Unregister plugin via brain
    res = brain.unregister_plugin(ws.workspace_id, "brain-p1")
    assert res["plugin"]["plugin_id"] == "brain-p1"

    # Unregister capability via brain
    res = brain.unregister_capability(ws.workspace_id, "brain-c1")
    assert res["capability"]["capability_id"] == "brain-c1"


# ---------------------------------------------------------------------------
# 6. MCP Tool Schema & Dispatch Tests
# ---------------------------------------------------------------------------

def test_mcp_tool_schemas_count():
    tool_names = [t["name"] for t in TOOL_SCHEMAS]
    cap10_tools = [
        "register_capability",
        "unregister_capability",
        "get_capability",
        "list_capabilities",
        "enable_capability",
        "disable_capability",
        "register_plugin",
        "unregister_plugin",
        "load_plugin",
        "unload_plugin",
        "list_plugins",
        "get_plugin",
        "capability_summary",
    ]
    for tool_name in cap10_tools:
        assert tool_name in tool_names


def test_mcp_dispatch_capability_lifecycle():
    ws = workspace_store.create_workspace(title="MCP Test Workspace")

    def _call(name: str, arguments: dict):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        res = handle_request(req)
        assert "result" in res, f"MCP Call Failed: {res}"
        return json.loads(res["result"]["content"][0]["text"])

    # 1. register_capability
    res = _call("register_capability", {
        "workspace_id": ws.workspace_id,
        "capability_id": "mcp-c1",
        "name": "MCP Cap",
        "version": "1.0.0",
        "description": "MCP desc",
    })
    assert res["capability"]["capability_id"] == "mcp-c1"

    # 2. get_capability
    res = _call("get_capability", {
        "workspace_id": ws.workspace_id,
        "capability_id": "mcp-c1",
    })
    assert res["capability"]["name"] == "MCP Cap"

    # 3. list_capabilities
    res = _call("list_capabilities", {
        "workspace_id": ws.workspace_id,
    })
    assert len(res["capabilities"]) == 1

    # 4. enable_capability
    res = _call("enable_capability", {
        "workspace_id": ws.workspace_id,
        "capability_id": "mcp-c1",
    })
    assert res["capability"]["status"] == "ENABLED"

    # 5. disable_capability
    res = _call("disable_capability", {
        "workspace_id": ws.workspace_id,
        "capability_id": "mcp-c1",
    })
    assert res["capability"]["status"] == "DISABLED"

    # 6. register_plugin
    res = _call("register_plugin", {
        "workspace_id": ws.workspace_id,
        "plugin_id": "mcp-p1",
        "name": "MCP Plug",
        "version": "1.0.0",
        "description": "MCP desc",
    })
    assert res["plugin"]["plugin_id"] == "mcp-p1"

    # 7. get_plugin
    res = _call("get_plugin", {
        "workspace_id": ws.workspace_id,
        "plugin_id": "mcp-p1",
    })
    assert res["plugin"]["name"] == "MCP Plug"

    # 8. list_plugins
    res = _call("list_plugins", {
        "workspace_id": ws.workspace_id,
    })
    assert len(res["plugins"]) == 1

    # 9. unload_plugin
    res = _call("unload_plugin", {
        "workspace_id": ws.workspace_id,
        "plugin_id": "mcp-p1",
    })
    assert res["plugin"]["status"] == "UNLOADED"

    # 10. load_plugin
    res = _call("load_plugin", {
        "workspace_id": ws.workspace_id,
        "plugin_id": "mcp-p1",
    })
    assert res["plugin"]["status"] == "LOADED"

    # 11. capability_summary
    res = _call("capability_summary", {
        "workspace_id": ws.workspace_id,
    })
    assert res["summary"]["capability_count"] == 1
    assert res["summary"]["plugin_count"] == 1

    # 12. unregister_plugin
    res = _call("unregister_plugin", {
        "workspace_id": ws.workspace_id,
        "plugin_id": "mcp-p1",
    })
    assert res["plugin"]["plugin_id"] == "mcp-p1"

    # 13. unregister_capability
    res = _call("unregister_capability", {
        "workspace_id": ws.workspace_id,
        "capability_id": "mcp-c1",
    })
    assert res["capability"]["capability_id"] == "mcp-c1"
