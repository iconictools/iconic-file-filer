"""Native toast notifications for Iconic File Filer."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

# ── tkinter toast (fallback) ─────────────────────────────────────────


def _show_toast_fallback(title: str, message: str, timeout_ms: int = 4000) -> None:
    """Display a small, auto-dismissing tkinter overlay notification.

    Called on a background thread when plyer is unavailable or fails.
    The tkinter import is deferred so the module can be imported even in
    headless environments (e.g., during unit tests).
    """
    try:
        import tkinter as tk  # deferred — not available in all environments

        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.92)

        # Position bottom-right
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = 320, 70
        root.geometry(f"{w}x{h}+{sw - w - 20}+{sh - h - 60}")
        root.configure(bg="#1e1e2e")

        tk.Label(
            root, text=title, bg="#1e1e2e", fg="#cdd6f4",
            font=("Segoe UI", 10, "bold"), anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 0))
        tk.Label(
            root, text=message, bg="#1e1e2e", fg="#a6adc8",
            font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=12)

        root.after(timeout_ms, root.destroy)
        root.mainloop()
    except Exception as exc:
        logger.debug("Toast fallback failed: %s", exc)


def _notify_send(title: str, message: str, timeout_ms: int = 5000) -> bool:
    """Use the Linux ``notify-send`` utility.  Returns *True* on success."""
    try:
        subprocess.run(
            ["notify-send", "-t", str(timeout_ms), title, message],
            timeout=3,
            check=True,
        )
        return True
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────


def notify(
    title: str,
    message: str,
    timeout: int = 5,
    fallback_strategy: str = "log-only",
) -> None:
    """Show a notification (non-blocking).

    Parameters
    ----------
    title:
        Notification title.
    message:
        Notification body.
    timeout:
        Display duration in seconds (plyer only).
    fallback_strategy:
        What to do when plyer is unavailable or fails.
        ``"plyer-only"`` — silently drop the notification.
        ``"toast-fallback"`` — show a small tkinter overlay (default).
        ``"log-only"`` — write to the log, nothing more.
    """

    def _send() -> None:
        try:
            from plyer import notification

            notification.notify(
                title=title,
                message=message,
                timeout=timeout,
                app_name="Iconic File Filer",
            )
            return
        except Exception as exc:
            logger.debug("Native notification failed (%s): %s", type(exc).__name__, exc)

        # plyer failed — apply fallback strategy
        if fallback_strategy == "log-only":
            logger.info("Notification: %s -- %s", title, message)
            return
        if fallback_strategy == "plyer-only":
            return  # do nothing

        # "toast-fallback": on Linux try notify-send first, then tkinter overlay
        timeout_ms = timeout * 1000
        if sys.platform.startswith("linux") and _notify_send(title, message, timeout_ms):
            return
        _show_toast_fallback(title, message, timeout_ms=timeout_ms)

    threading.Thread(target=_send, daemon=True).start()
