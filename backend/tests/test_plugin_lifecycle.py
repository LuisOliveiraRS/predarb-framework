from pathlib import Path

from app.plugins.loader import PluginLoader
from app.plugins.manager import PluginManager
from app.plugins.registry import PluginRegistry


def test_plugin_loader_is_independent_from_current_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loader = PluginLoader()
    discovered = loader.discover()

    assert any(item["name"] == "mock_market" for item in discovered)
    assert Path(loader.last_report["base_path"]).is_absolute()


def test_plugin_manager_load_is_idempotent_and_stoppable(capsys):
    manager = PluginManager(
        loader=PluginLoader(),
        plugin_registry=PluginRegistry(),
    )

    first = manager.load()
    second = manager.load()
    stopped = manager.stop()

    assert first["loaded"] == ["mock_market"]
    assert second["skipped"] == ["mock_market"]
    assert stopped["stopped"] == ["mock_market"]
