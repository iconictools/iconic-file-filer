"""Tests for the config module."""

import os
import tempfile

from iconic_filer.config import Config


class TestConfig:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self._path = os.path.join(self._tmpdir, "test_config.json")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_creates_default_on_missing(self):
        cfg = Config(self._path)
        assert os.path.exists(self._path)
        assert cfg.monitored_folders == {}

    def test_add_monitored_folder(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/downloads", ["/tmp/docs", "/tmp/images"])
        assert "/tmp/downloads" in cfg.monitored_folders
        assert cfg.get_folder_destinations("/tmp/downloads") == ["/tmp/docs", "/tmp/images"]

    def test_remove_monitored_folder(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/downloads", ["/tmp/docs"])
        cfg.remove_monitored_folder("/tmp/downloads")
        assert "/tmp/downloads" not in cfg.monitored_folders

    def test_persistence(self):
        cfg1 = Config(self._path)
        cfg1.add_monitored_folder("/tmp/test", ["/tmp/dest"])
        cfg1.set_setting("focus_mode", True)

        cfg2 = Config(self._path)
        assert "/tmp/test" in cfg2.monitored_folders
        assert cfg2.get_setting("focus_mode") is True

    def test_ignore_patterns(self):
        cfg = Config(self._path)
        cfg.add_ignore_pattern("*.log")
        assert "*.log" in cfg.ignore_patterns

        cfg.remove_ignore_pattern("*.log")
        assert "*.log" not in cfg.ignore_patterns

    def test_set_destinations(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/test", ["/tmp/a"])
        cfg.set_destinations("/tmp/test", ["/tmp/b", "/tmp/c"])
        assert cfg.get_folder_destinations("/tmp/test") == ["/tmp/b", "/tmp/c"]

    def test_get_setting_default(self):
        cfg = Config(self._path)
        assert cfg.get_setting("nonexistent", 42) == 42

    def test_corrupt_json_resets_to_default(self):
        """Config with invalid JSON should back up and reset (Q8.2)."""
        with open(self._path, "w") as f:
            f.write("{invalid json!!!")
        cfg = Config(self._path)
        assert cfg.monitored_folders == {}
        # Backup file should exist
        assert any("bak" in f for f in os.listdir(self._tmpdir))

    def test_auto_learn_threshold_default(self):
        """Default auto-learn threshold should be 0 (disabled — opt-in)."""
        cfg = Config(self._path)
        assert cfg.get_setting("auto_learn_threshold", 0) == 0

    def test_batch_mode_style_default(self):
        """Default batch mode style should use one-by-one flow."""
        cfg = Config(self._path)
        assert cfg.get_setting("batch_mode_style") == "one-by-one"

    def test_per_folder_schema(self):
        """Newly added folder should have all per-folder keys."""
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/test", ["/tmp/dest"])
        entry = cfg.monitored_folders["/tmp/test"]
        assert "destinations" in entry
        assert "whitelist" in entry
        assert "ignore_patterns" in entry
        assert "extension_map" in entry
        assert "label" in entry
        assert "rename_patterns" in entry

    def test_folder_label(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/test", [])
        assert cfg.get_folder_label("/tmp/test") == ""
        cfg.set_folder_label("/tmp/test", "My Downloads")
        assert cfg.get_folder_label("/tmp/test") == "My Downloads"

    def test_folder_whitelist(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/test", [])
        cfg.add_to_folder_whitelist("/tmp/test", "*.log")
        assert "*.log" in cfg.get_folder_whitelist("/tmp/test")
        cfg.remove_from_folder_whitelist("/tmp/test", "*.log")
        assert "*.log" not in cfg.get_folder_whitelist("/tmp/test")

    def test_folder_extension_map(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/test", [])
        cfg.set_folder_extension_map("/tmp/test", {".pdf": "/tmp/docs"})
        assert cfg.get_folder_extension_map("/tmp/test") == {".pdf": "/tmp/docs"}

    def test_folder_rename_pattern(self):
        cfg = Config(self._path)
        cfg.add_monitored_folder("/tmp/test", [])
        cfg.set_folder_setting("/tmp/test", "rename_patterns", [
            {"extensions": [".pdf"], "pattern": "{date}_{name}", "enabled": True}
        ])
        assert cfg.get_folder_rename_pattern("/tmp/test", ".pdf") == "{date}_{name}"
        assert cfg.get_folder_rename_pattern("/tmp/test", ".txt") is None

    def test_migration_from_old_list_format(self):
        """Old list-based monitored_folders should be migrated to dict format."""
        import json
        # Write an old-format config directly
        with open(self._path, "w") as f:
            json.dump({
                "monitored_folders": {"/tmp/old": ["/tmp/dest"]},
                "global_settings": {},
                "ignore_patterns": [],
            }, f)
        cfg = Config(self._path)
        assert isinstance(cfg.monitored_folders["/tmp/old"], dict)
        assert cfg.get_folder_destinations("/tmp/old") == ["/tmp/dest"]

    def test_add_monitored_folder_dedups_by_normalized_path(self, monkeypatch):
        cfg = Config(self._path)
        monkeypatch.setattr("iconic_filer.config.os.path.normcase", lambda p: p.lower())
        cfg.add_monitored_folder("/tmp/Foo", ["/tmp/d1"])
        cfg.add_monitored_folder("/tmp/foo", ["/tmp/d2"])
        assert len(cfg.monitored_folders) == 1
        assert cfg.get_folder_destinations("/tmp/FOO") == ["/tmp/d1"]
        assert cfg.get_folder_destinations("/tmp/Foo") == ["/tmp/d1"]

    def test_remove_monitored_folder_matches_normalized_path(self, monkeypatch):
        cfg = Config(self._path)
        monkeypatch.setattr("iconic_filer.config.os.path.normcase", lambda p: p.lower())
        cfg.add_monitored_folder("/tmp/Foo", ["/tmp/d1"])
        cfg.remove_monitored_folder("/tmp/foo")
        assert cfg.monitored_folders == {}
