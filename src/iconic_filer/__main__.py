"""Entry point for Iconic File Filer.

Usage:
    python -m iconic_filer          # Run the app (GUI)
    python -m iconic_filer --help   # Show help
    python -m iconic_filer --setup-cli  # CLI setup wizard
"""

from __future__ import annotations

import sys

# Reconfigure stdout/stderr to UTF-8 early, before any other imports or
# print/log calls.  On Windows the default encoding is cp1252 which cannot
# represent many Unicode characters and causes UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import argparse  # noqa: E402
import logging  # noqa: E402
import logging.handlers  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402

from iconic_filer import __version__  # noqa: E402
from iconic_filer.constants import DEFAULT_CONFIG_DIR, DEFAULT_LOG_FILE  # noqa: E402


def _setup_logging(verbose: bool) -> None:
    """Configure logging to both console and a rotating log file."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console handler -- sys.stderr is already reconfigured to UTF-8 at
    # module level, so we can attach directly.
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(console)

    # Rotating file handler -- always active
    os.makedirs(DEFAULT_CONFIG_DIR, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        DEFAULT_LOG_FILE,
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(file_handler)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="iconic-filer",
        description="Tray-resident real-time file organizer assistant.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to config JSON file.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    parser.add_argument(
        "--setup-cli",
        action="store_true",
        help="Run the CLI setup wizard instead of the GUI wizard.",
    )
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    # ── Auto-migrate old config dir ───────────────────────────────────
    _old_dir = os.path.join(os.path.expanduser("~"), ".sort-it-now")
    _new_dir = DEFAULT_CONFIG_DIR
    if os.path.isdir(_old_dir) and not os.path.exists(
        os.path.join(_new_dir, "config.json")
    ):
        try:
            shutil.copytree(_old_dir, _new_dir, dirs_exist_ok=True)
            logging.getLogger(__name__).info(
                "Auto-migrated config from %s to %s", _old_dir, _new_dir
            )
        except Exception as _exc:
            logging.getLogger(__name__).warning(
                "Could not migrate old config: %s", _exc
            )

    from iconic_filer.config import Config

    config = Config(args.config)

    # CLI setup mode (Q2.1c)
    if args.setup_cli:
        from iconic_filer.prompt import cli_setup

        folders = cli_setup()
        for folder, dests in folders.items():
            config.add_monitored_folder(folder, dests)
        if not folders:
            return

    # ── Apply customtkinter appearance early ─────────────────────────
    try:
        from iconic_filer.themes import apply_ctk_appearance
        apply_ctk_appearance(config.get_setting("theme", "dark"))
    except Exception:
        pass

    # ── Multi-instance handling ──────────────────────────────────────
    from iconic_filer.ipc import is_running, send_command

    if is_running():
        behavior = config.get_setting("multi_instance_behavior", "prompt")

        if behavior == "ignore":
            # Start a completely independent second instance (no merge).
            pass

        else:
            # "always-merge" or "prompt" — try to merge into the running instance.
            merge = True
            if behavior == "prompt":
                import tkinter as tk
                from tkinter import messagebox

                _root = tk.Tk()
                _root.withdraw()
                merge = messagebox.askyesno(
                    "Iconic File Filer is already running",
                    "Another instance is already running.\n\n"
                    "Do you want to add a new folder to the running instance?\n\n"
                    "(Choose No to open a separate, independent instance.)",
                )
                _root.destroy()

            if merge:
                # Ask the user which folder to add, then send it via IPC.
                import tkinter as tk
                from tkinter import filedialog

                _root = tk.Tk()
                _root.withdraw()
                folder = filedialog.askdirectory(
                    title="Choose a folder for the running Iconic File Filer to watch"
                )
                _root.destroy()
                if folder:
                    send_command(f"ADD_FOLDER:{folder}")
                    logging.getLogger(__name__).info(
                        "Sent ADD_FOLDER command to running instance: %s", folder
                    )
                return  # second instance exits after delegating

    # ── Normal startup ────────────────────────────────────────────────
    # Wrap the entire startup in a try/except so that fatal errors (e.g.
    # pystray failing to import, no display, missing libraries in a bundle)
    # are surfaced as a visible error dialog rather than silently disappearing
    # when the app is launched without a terminal (AppImage / double-click).
    try:
        from iconic_filer.app import App
        app = App(config=config)
        app.run()
    except Exception as exc:  # noqa: BLE001
        _log = logging.getLogger(__name__)
        _log.exception("Fatal startup error: %s", exc)
        # Best-effort: show a visible error dialog.
        try:
            import tkinter as _tk
            from tkinter import messagebox as _mb
            _root = _tk.Tk()
            _root.withdraw()
            _mb.showerror(
                "Iconic File Filer — Fatal error",
                f"The application failed to start:\n\n{exc}\n\n"
                "Check ~/.iconic-filer/iconic-filer.log for details.\n\n"
                "On Linux, ensure DISPLAY is set (XWayland must be running) "
                "and that python3-xlib is installed.",
            )
            _root.destroy()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
