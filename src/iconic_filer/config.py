"""Configuration management for Iconic File Filer.

Stores monitored folders, destination sets, and user preferences as JSON.

Monitored folder schema (per-folder dict, migrated from old list format):
    {
        "/path": {
            "destinations": ["/dest1", "/dest2"],
            "whitelist": [],
            "ignore_patterns": [],
            "extension_map": {},
            "label": "",
            "rename_patterns": [],
        }
    }
"""

from __future__ import annotations

import json
import logging
import os
import copy
import shutil
import time
import zipfile
from typing import Any

from iconic_filer.constants import DEFAULT_CONFIG_FILE

logger = logging.getLogger(__name__)

# Default per-folder settings structure
_FOLDER_DEFAULTS: dict[str, Any] = {
    "destinations": [],
    "whitelist": [],
    "ignore_patterns": [],
    "extension_map": {},
    "label": "",
    "rename_patterns": [],
}

# Default configuration template
_DEFAULT_CONFIG: dict[str, Any] = {
    "monitored_folders": {},
    "global_settings": {
        # UI / behaviour
        "focus_mode": False,
        # Minutes to snooze a file before re-prompting (default 30; set to 0 to disable)
        "snooze_minutes": 30,
        "batch_mode": False,
        "batch_mode_style": "batch-list",
        "prompt_delay_seconds": 3.0,
        "theme": "dark",
        # Pre-check "Always send .ext files here" in the sort prompt
        # (default False — the prompt focuses on one-click sorting, not rule creation)
        "prompt_always_rule": False,
        # Auto-accept the top suggestion after N seconds (0 = disabled)
        "prompt_auto_accept_seconds": 0,
        # Monitoring
        "scan_existing_enabled": False,
        "catch_folders": False,
        "pause_on_dnd": False,
        # Notifications
        "native_notifications": True,
        # "plyer-only" | "log-only"
        "notification_fallback": "log-only",
        # Pattern rules
        "pattern_rules_enabled": True,
        # Duplicate detection
        "duplicate_detection": False,
        # Conflict resolution: "rename" | "overwrite" | "skip" | "ask"
        # What to do when a file already exists at the destination.
        "conflict_resolution": "rename",
        # Undo behaviour: "ask" | "always" | "never"
        # When undoing a move that also involved a rename, should the
        # original filename be restored?
        "undo_restore_name": "ask",
        # Multi-instance: "prompt" | "always-merge" | "ignore"
        # When a second instance launches while one is already running,
        # how should they behave?
        "multi_instance_behavior": "prompt",
        # Show startup welcome once after install/update.
        "startup_welcome_seen": False,
        # Quick-Add Folder
        "quick_add_inherit_destinations": True,
        "quick_add_auto_whitelist": True,
        "quick_add_auto_start_watch": True,
        # Cleanup reminders: 0 = disabled, N = alert when folder has >= N files
        "cleanup_reminder_threshold": 0,
        # Auto-learn: automatically create an extension rule after this many
        # manual sorts of the same extension to the same destination.
        # Default is 0 (disabled) — rule building is opt-in via Settings.
        "auto_learn_threshold": 0,
    },
    "ignore_patterns": [
        "~$*",
        ".~lock.*",
        "desktop.ini",
        ".DS_Store",
        "Thumbs.db",
    ],
}


class Config:
    """Manages application configuration stored as a JSON file."""

    def __init__(self, config_path: str | None = None) -> None:
        self.path = config_path or DEFAULT_CONFIG_FILE
        self._data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load configuration from disk, creating defaults if missing.

        If the file exists but contains invalid JSON, back it up and
        reset to defaults.  Also migrates old per-folder list format to
        the new per-folder dict format.
        """
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    "Config file corrupted (%s) -- backing up and resetting.",
                    exc,
                )
                backup = f"{self.path}.bak.{int(time.time())}"
                try:
                    shutil.copy2(self.path, backup)
                    logger.info("Backup saved to %s", backup)
                except OSError:
                    pass
                self._data = json.loads(json.dumps(_DEFAULT_CONFIG))
                self.save()
        else:
            self._data = json.loads(json.dumps(_DEFAULT_CONFIG))
            self.save()

        # Migrate old monitored_folders format: {path: [list]} → {path: {dict}}
        mf = self._data.get("monitored_folders", {})
        migrated = False
        for path, value in list(mf.items()):
            if isinstance(value, list):
                mf[path] = {**_FOLDER_DEFAULTS, "destinations": value}
                migrated = True
        if migrated:
            logger.info("Migrated monitored_folders to per-folder dict format.")
            self.save()

    def save(self) -> None:
        """Persist current configuration to disk (atomic write)."""
        dir_path = os.path.dirname(self.path) or "."
        os.makedirs(dir_path, exist_ok=True)
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)
        os.replace(tmp_path, self.path)

    # ------------------------------------------------------------------
    # Monitored folders
    # ------------------------------------------------------------------

    @property
    def monitored_folders(self) -> dict[str, dict[str, Any]]:
        """Return ``{folder_path: {per-folder settings}}`` mapping."""
        return self._data.get("monitored_folders", {})

    @staticmethod
    def _path_key(path: str) -> str:
        """Return a normalized key for cross-platform path identity checks."""
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    def _find_folder_key(self, folder: str) -> str | None:
        """Return the existing stored key matching *folder*, if any."""
        target = self._path_key(folder)
        for key in self._data.get("monitored_folders", {}):
            if self._path_key(key) == target:
                return key
        return None

    def add_monitored_folder(
        self, folder: str, destinations: list[str] | None = None
    ) -> None:
        """Register *folder* for monitoring with optional *destinations*."""
        folder = os.path.abspath(folder)
        if self._find_folder_key(folder) is None:
            self._data["monitored_folders"][folder] = {
                **_FOLDER_DEFAULTS,
                "destinations": destinations or [],
            }
            self.save()

    def remove_monitored_folder(self, folder: str) -> None:
        """Stop monitoring *folder*."""
        key = self._find_folder_key(folder)
        if key is not None:
            self._data["monitored_folders"].pop(key, None)
        self.save()

    def set_destinations(self, folder: str, destinations: list[str]) -> None:
        """Set destination folders for a monitored *folder*."""
        folder = os.path.abspath(folder)
        mf = self._data["monitored_folders"]
        key = self._find_folder_key(folder) or folder
        if key not in mf:
            mf[key] = {**_FOLDER_DEFAULTS}
        mf[key]["destinations"] = destinations
        self.save()

    # ------------------------------------------------------------------
    # Per-folder helpers
    # ------------------------------------------------------------------

    def _folder_data(self, folder: str) -> dict[str, Any]:
        """Return the per-folder settings dict, auto-creating if absent."""
        folder = os.path.abspath(folder)
        mf = self._data.setdefault("monitored_folders", {})
        key = self._find_folder_key(folder) or folder
        if key not in mf:
            mf[key] = {**_FOLDER_DEFAULTS}
        entry = mf[key]
        # Fill in any missing keys from defaults (forward-compat)
        for k, v in _FOLDER_DEFAULTS.items():
            if k not in entry:
                entry[k] = copy.deepcopy(v)
        return entry

    def get_folder_destinations(self, folder: str) -> list[str]:
        """Return the destination list for *folder*."""
        return self._folder_data(folder).get("destinations", [])

    def get_folder_whitelist(self, folder: str) -> list[str]:
        """Return the per-folder whitelist glob patterns."""
        return self._folder_data(folder).get("whitelist", [])

    def add_to_folder_whitelist(self, folder: str, pattern: str) -> None:
        """Add a glob pattern to the per-folder whitelist."""
        wl = self._folder_data(folder).setdefault("whitelist", [])
        if pattern not in wl:
            wl.append(pattern)
            self.save()

    def remove_from_folder_whitelist(self, folder: str, pattern: str) -> None:
        """Remove a glob pattern from the per-folder whitelist."""
        wl = self._folder_data(folder).get("whitelist", [])
        if pattern in wl:
            wl.remove(pattern)
            self.save()

    def get_folder_extension_map(self, folder: str) -> dict[str, str]:
        """Return the per-folder extension→destination map."""
        return self._folder_data(folder).get("extension_map", {})

    def set_folder_extension_map(
        self, folder: str, ext_map: dict[str, str]
    ) -> None:
        """Set the per-folder extension→destination map."""
        self._folder_data(folder)["extension_map"] = ext_map
        self.save()

    def get_folder_label(self, folder: str) -> str:
        """Return the human-readable label for *folder*."""
        return self._folder_data(folder).get("label", "")

    def set_folder_label(self, folder: str, label: str) -> None:
        """Set the human-readable label for *folder*."""
        self._folder_data(folder)["label"] = label
        self.save()

    def get_folder_rename_patterns(self, folder: str) -> list[dict[str, Any]]:
        """Return the list of per-folder rename pattern dicts."""
        return self._folder_data(folder).get("rename_patterns", [])

    def get_folder_rename_pattern(self, folder: str, ext: str) -> str | None:
        """Return the rename pattern string for *ext* in *folder*, or *None*."""
        ext = ext.lower()
        for entry in self.get_folder_rename_patterns(folder):
            if not entry.get("enabled", True):
                continue
            if ext in entry.get("extensions", []):
                return entry.get("pattern")
        return None

    def set_folder_setting(self, folder: str, key: str, value: Any) -> None:
        """Set an arbitrary per-folder setting by *key*."""
        self._folder_data(folder)[key] = value
        self.save()

    # ------------------------------------------------------------------
    # Global settings helpers
    # ------------------------------------------------------------------

    @property
    def global_settings(self) -> dict[str, Any]:
        return self._data.get("global_settings", {})

    def get_setting(self, key: str, default: Any = None) -> Any:
        return self.global_settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._data.setdefault("global_settings", {})[key] = value
        self.save()

    def save_many(self, settings: dict[str, Any]) -> None:
        """Batch-update multiple settings in a single disk write."""
        gs = self._data.setdefault("global_settings", {})
        gs.update(settings)
        self.save()

    # ------------------------------------------------------------------
    # Ignore patterns
    # ------------------------------------------------------------------

    @property
    def ignore_patterns(self) -> list[str]:
        return self._data.get("ignore_patterns", [])

    def add_ignore_pattern(self, pattern: str) -> None:
        patterns = self._data.setdefault("ignore_patterns", [])
        if pattern not in patterns:
            patterns.append(pattern)
            self.save()

    def remove_ignore_pattern(self, pattern: str) -> None:
        patterns = self._data.get("ignore_patterns", [])
        if pattern in patterns:
            patterns.remove(pattern)
            self.save()

    # ------------------------------------------------------------------
    # Whitelist
    # ------------------------------------------------------------------

    def get_whitelist(self) -> list[str]:
        """Return the list of whitelist glob patterns."""
        return self._data.get("whitelist", [])

    def add_to_whitelist(self, pattern: str) -> None:
        """Add a glob pattern to the whitelist."""
        wl = self._data.setdefault("whitelist", [])
        if pattern not in wl:
            wl.append(pattern)
            self.save()

    def remove_from_whitelist(self, pattern: str) -> None:
        """Remove a glob pattern from the whitelist."""
        wl = self._data.get("whitelist", [])
        if pattern in wl:
            wl.remove(pattern)
            self.save()

    # ------------------------------------------------------------------
    # Rename patterns
    # ------------------------------------------------------------------

    @property
    def rename_patterns(self) -> list[dict[str, Any]]:
        """Return the list of rename pattern dicts."""
        return self._data.setdefault("rename_patterns", [])

    def get_rename_pattern(self, ext: str) -> str | None:
        """Return the rename pattern string for *ext*, or *None*."""
        ext = ext.lower()
        for entry in self.rename_patterns:
            if not entry.get("enabled", True):
                continue
            if ext in entry.get("extensions", []):
                return entry.get("pattern")
        return None

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def export_config(self, export_path: str) -> None:
        """Export config.json and rules.json into a zip file."""
        rules_path = os.path.join(
            os.path.dirname(self.path) or ".", "rules.json"
        )
        with zipfile.ZipFile(export_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(self.path):
                zf.write(self.path, "config.json")
            if os.path.exists(rules_path):
                zf.write(rules_path, "rules.json")

    def import_config(self, import_path: str) -> None:
        """Import config.json and rules.json from a zip file.

        Raises
        ------
        zipfile.BadZipFile
            If *import_path* is not a valid zip archive.
        ValueError
            If a member inside the zip contains a path traversal component or
            the extracted JSON is not parseable.
        OSError
            If extraction fails due to a filesystem error.
        """
        dest_dir = os.path.abspath(os.path.dirname(self.path) or ".")
        with zipfile.ZipFile(import_path, "r") as zf:
            # Guard against path-traversal entries in the zip.
            for info in zf.infolist():
                # Resolve where the entry would land after extraction.
                target = os.path.realpath(os.path.join(dest_dir, info.filename))
                if not (target == dest_dir or target.startswith(dest_dir + os.sep)):
                    raise ValueError(
                        f"Unsafe zip entry (path traversal): {info.filename!r}"
                    )
            for name in ("config.json", "rules.json"):
                if name in zf.namelist():
                    raw = zf.read(name)
                    # Validate JSON before writing to disk.
                    try:
                        json.loads(raw)
                    except (json.JSONDecodeError, ValueError) as exc:
                        raise ValueError(
                            f"Invalid JSON in {name!r}: {exc}"
                        ) from exc
                    target_path = os.path.join(dest_dir, name)
                    os.makedirs(dest_dir, exist_ok=True)
                    with open(target_path, "wb") as fh:
                        fh.write(raw)
        self.load()
