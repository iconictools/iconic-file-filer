# Iconic File Filer 🗂️

> Tray-resident real-time file organizer assistant — put your files where you want, *right when they arrive*.

[![Build](https://github.com/trabalhefabricio/sort-it-now/actions/workflows/build.yml/badge.svg)](https://github.com/trabalhefabricio/sort-it-now/actions/workflows/build.yml)

## What it does

Iconic File Filer lives in your system tray and watches folders you choose (Downloads, Desktop, Screenshots, etc.). When a new file appears it asks you **"Where should this go?"** with a quick popup showing your configured destinations.

Instead of dumping files and cleaning up later, you make a micro-decision at the moment of action — building a tidy file system as a habit.

### Design philosophy

**Iconic File Filer never moves a file without your say-so.**

Every other file-watching tool eventually starts sorting files automatically (auto-learn rules, frequency heuristics, ML classifiers). Iconic File Filer deliberately does *not*. The point is that *you* are making the decision — the tool is just surfacing it at the right moment and making it instant. You can set explicit pattern rules (glob / regex) for repetitive cases, but nothing happens behind your back.

### Features

| Feature | Description |
|---|---|
| **Real-time monitoring** | Detects new, moved, and modified files instantly via `watchdog` |
| **Smart prompts** | Non-intrusive popup with context-aware destination suggestions |
| **File preview** | Image thumbnails, text file previews, and file type labels in the prompt |
| **Always asks — no auto-sorting** | Iconic File Filer **never** moves a file without your confirmation. Every tool auto-sorts eventually — this one doesn't. Your choices stay yours. |
| **Pattern rules** | Glob and regex rules (e.g. `invoice*.pdf` → Finances) that you set explicitly |
| **Smart download detection** | On Linux uses inotify `IN_CLOSE_WRITE` (fired the instant the browser closes the file) as the primary signal; falls back to size + mtime polling with exponential backoff on all platforms; on Windows confirms the file is not exclusively locked before prompting |
| **Rename on move** | Configurable rename patterns with `{name}`, `{date}`, `{ext}` tokens |
| **Duplicate detection** | SHA256-based duplicate check before moving |
| **Native notifications** | Toast notifications via plyer (cross-platform) |
| **Startup indicator window** | Every launch shows a visible startup window before tray mode begins |
| **Focus / Snooze mode** | Queues prompts during deep work, processes them when you're ready |
| **DND integration** | Pauses when Windows Focus Assist is active |
| **Undo** | One-click revert from the tray menu, plus clickable history |
| **Dashboard** | Quick view of recent actions, stats, and pending files |
| **Batch processing** | Single batch window for newly detected files (move / skip / whitelist / snooze) |
| **Settings UI** | Full tabbed settings dialog with watched-folder + destination add/remove management |
| **Rule management UI** | View, add, edit, and delete explicit rules visually |
| **Dark / Light theme** | Catppuccin-inspired themes via customtkinter — beautiful rounded widgets |
| **Polished UI** | Modern, rounded dialogs (customtkinter) on all platforms — Windows, macOS, Linux |
| **Whitelist** | Control exactly which files to ignore |
| **Catch folders** | Optionally detect and sort entire directories |
| **Quick Add** | Instantly start monitoring a new sub-folder from the sort prompt |
| **Config import/export** | Backup and restore your setup as a zip |
| **Delete all user data** | One-click destructive reset from Settings → System → Danger Zone |
| **Autostart** | Start on login (Windows registry, Linux XDG autostart, macOS LaunchAgent) |
| **AppImage** | Full-featured AppImage for Linux — no installation required |
| **Cross-platform** | Works on Windows, macOS, and Linux |
| **Self-loop prevention** | Files the app moves won't re-trigger the watcher |
| **Cross-platform** | Works on Windows, macOS, and Linux |
| **Self-building CI** | GitHub Actions builds executables on every push |
| **Manual build** | `python build.py` creates a standalone executable locally |

## Quick start

### Download a pre-built binary

Head to the [Releases](https://github.com/trabalhefabricio/sort-it-now/releases) page and grab the build for your platform:

| Platform | Download |
|---|---|
| **Linux** | `IconicFiler-<version>-x86_64.AppImage` — make executable, double-click to run |
| **Windows** | `IconicFileFiler-<version>-windows-x86_64.exe` — run directly, no installer needed |
| **macOS** | `iconic-filer` — run from Terminal or double-click |

#### Linux AppImage quick start
```bash
chmod +x IconicFiler-*.AppImage
./IconicFiler-*.AppImage
```

### Run from source

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python -m iconic_filer

# First launch opens a Setup Wizard where you pick
# folders to monitor and their destination folders.
```

### Build a standalone executable

```bash
# Install build deps
pip install -r requirements-dev.txt

# Build
python build.py            # directory bundle
python build.py --onefile  # single-file executable

# Output lands in dist/
```

### CI / CD

Every push triggers the **Build** workflow (`.github/workflows/build.yml`) which:

1. Runs the test suite (Python 3.9–3.12 matrix)
2. Runs ruff lint and mypy type checking
3. Builds executables for Linux, Windows, and macOS
4. Uploads them as workflow artifacts

Tag pushes (`v*`) trigger the **Release** workflow which creates a GitHub Release with built binaries.

## Configuration

Config is stored in `~/.iconic-filer/config.json`. Example:

```json
{
  "monitored_folders": {
    "/home/user/Downloads": [
      "/home/user/Documents",
      "/home/user/Images",
      "/home/user/Installers",
      "/home/user/Temporary"
    ],
    "/home/user/Desktop": [
      "/home/user/Projects",
      "/home/user/Documents"
    ]
  },
  "global_settings": {
    "focus_mode": false,
    "snooze_minutes": 0,
    "batch_mode": false,
    "auto_learn": true,
    "auto_learn_threshold": 3,
    "prompt_delay_seconds": 3.0,
    "theme": "dark",
    "native_notifications": true,
    "duplicate_detection": false,
    "scan_existing_enabled": false,
    "catch_folders": false,
    "pattern_rules_enabled": true,
    "pause_on_dnd": false,
    "batch_mode_style": "batch-list"
  },
  "ignore_patterns": [
    "~$*",
    ".~lock.*",
    "desktop.ini",
    ".DS_Store",
    "Thumbs.db"
  ],
  "whitelist": []
}
```

## Architecture

```
src/iconic_filer/
├── __main__.py       # CLI entry point
├── app.py            # Main orchestrator
├── watcher.py        # File system monitoring (watchdog)
├── classifier.py     # File type classification
├── rules.py          # Auto-learning rules engine + pattern rules
├── history.py        # Undo history (SQLite)
├── prompt.py         # User prompt dialogs (tkinter)
├── tray.py           # System tray icon (pystray)
├── constants.py      # Defaults and settings
├── config.py         # Configuration management (JSON, atomic writes)
├── themes.py         # Dark/light theme support
├── notifications.py  # Native toast notifications (plyer)
├── duplicate.py      # SHA256 duplicate detection
├── autostart.py      # Start on login (Windows)
├── settings_ui.py    # Settings dialog
├── rules_ui.py       # Rule management dialog
├── dashboard_ui.py   # Dashboard & batch processing windows
└── conflict_ui.py    # File conflict resolution dialog
```

## Development

```bash
# Install everything
pip install -r requirements-dev.txt
pip install -e .

# Run tests
pytest

# Run with debug logging
python -m iconic_filer -v

# Lint
ruff check src/ tests/
```

### Feature validation checklist (Linux + Windows)

- **Linux local run**: `pytest --tb=short -q`, `ruff check src/ tests/`, `mypy src/ --ignore-missing-imports`
- **Windows run**: execute the same test/lint/type-check commands in PowerShell (or via CI)
- **CI expectation**: Linux and Windows build/test jobs must pass before release

## License

MIT

---

## User Guide

### Getting Started

1. **Startup flow + first launch setup**  
   Every app launch shows a short startup window (so startup is never tray-only). On the very first run, the Setup Wizard opens and asks you to choose one or more folders to watch (e.g. `Downloads`) and one or more destination folders for each watched folder (e.g. `Documents`, `Pictures`, `Work`). You can add/remove folders at any time from **Settings → Folders**.

2. **Detected files action window**  
   Newly detected files are grouped into a single batch window instead of spawning one popup per file. For each file you can choose: **Move**, **Skip**, **Whitelist**, or **Snooze**.

3. **Focus mode**  
   Focus mode queues all incoming files instead of showing prompts. The tray icon turns red and displays a badge with the pending count. Toggle focus mode from the tray context menu. When you turn it off the queue is processed according to the **batch mode style** setting (one-by-one or batch list).

4. **Rules**  
   - **Extension auto-rules**: tick "Always send here" in the sort prompt to create an auto-rule. After three consistent choices for the same extension, the rule fires automatically.
   - **Pattern rules** (glob/regex): open **Tray → Manage Rules** to create explicit rules that match filenames and route them to a destination without prompting.
   - **Per-folder extension map**: in **Settings → Folders**, select a watched folder and configure per-folder extension overrides that take priority over the global rules.

5. **Dashboard**  
   Open the dashboard from the tray menu to see:
   - Pending files in the queue (focus mode).
   - Sorting stats: total, today, this week.
   - Top file types and top destinations (derived from your sort history).
   - Inbox Zero progress bar for today's activity.
   - Clickable undo history — select any action and click **Undo to selected** to roll back up to that point.

6. **Settings**  
   The settings dialog has five tabs:
   - **General** — theme (dark/light), notifications, undo behaviour, multi-instance handling.
   - **Monitoring** — prompt delay, scan existing files, catch new sub-folders, DND pause, pattern rules toggle, duplicate detection, cleanup reminder threshold.
   - **Folders** — add/remove watched folders (origins), add/remove per-folder destinations, set a folder label, and configure a per-folder whitelist.
   - **Rules** — global whitelist patterns, watcher ignore patterns, and auto-rename patterns.
   - **System** — login autostart, batch mode style, config export/import, and **Delete all user data**.

---

## FAQ

**Q: A file appeared in my watched folder but I wasn't prompted.**  
A: Check three things: (1) the file name may match a pattern in **Settings → Rules → Whitelist** or the per-folder whitelist for that folder; (2) the file landed inside a configured *destination* folder, which is always skipped to prevent re-sorting already-sorted files; (3) the file name matches an ignore pattern in **Settings → Rules → Ignore Patterns** (e.g. `~$*` for Office temp files).

**Q: The app stopped watching a folder.**  
A: The folder may have been removed or unmounted. Iconic File Filer logs a warning at startup when a monitored folder no longer exists. Re-add it in **Settings → Folders → + Watch** or via **Tray → Add folder to watch...** and the watcher will resume.

**Q: How do I undo a move?**  
A: You have two options. From the tray: click **Undo last** to reverse the most recent action. From the dashboard: open **Tray → Dashboard**, select any action in the history list, then click **Undo to selected** to roll back all actions up to and including the selected one.

**Q: Can I move files automatically without prompts?**  
A: Yes — two mechanisms skip the prompt entirely. (1) **Explicit pattern rules** (glob or regex): create them in **Tray → Manage Rules**; any file whose name matches is moved immediately. (2) **Extension auto-rules**: after you choose the same destination for a given extension three times and tick "Always send here", subsequent files of that extension are moved automatically. Per-folder extension maps (configured in **Settings → Folders**) also fire silently.

**Q: Files in my Downloads folder aren't triggering prompts.**  
A: Make sure `Downloads` appears in **Settings → Folders → Watched folders**. If it does, check that it isn't also listed as a *destination* for itself (destination folders are skipped). Also verify that the file extension isn't matched by a whitelist or ignore pattern, and that focus mode is not active (the tray icon would be red with a badge if it is).
