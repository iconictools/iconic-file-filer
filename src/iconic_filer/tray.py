"""System tray icon for Iconic File Filer (pystray-based)."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont

# pystray connects to the X display at import time on Linux (via the xorg
# backend's module-level Display() probe).  Guard the import so that a
# missing display or absent Xlib/six dependency raises a *deferred* error
# that TrayIcon.start() can surface as a visible dialog rather than an
# unhandled crash before any UI is shown.
_pystray_import_error: Optional[Exception] = None
try:
    import pystray
except Exception as _e:  # noqa: BLE001
    _pystray_import_error = _e
    pystray = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
PAUSED_ICON_COLOR = "#f87171"

# ── Icon drawing helpers ─────────────────────────────────────────────

def _create_icon_image(
    color: str = "#89b4fa",
    size: int = 64,
    badge_count: int = 0,
) -> Image.Image:
    """Draw a compass/waypoint tray icon with optional badge."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Compass ring
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        outline=color, width=4,
    )
    # Waypoint diamond marker in the center
    cx, cy = size // 2, size // 2
    r = size // 5
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(points, fill=color)
    # Badge with pending count
    if badge_count > 0:
        badge_r = 14
        badge_x = size - badge_r - 2
        badge_y = badge_r + 2
        draw.ellipse(
            [badge_x - badge_r, badge_y - badge_r,
             badge_x + badge_r, badge_y + badge_r],
            fill="#f38ba8",
        )
        label = str(badge_count) if badge_count <= 99 else "99+"
        font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(
            (badge_x - tw // 2, badge_y - th // 2 - 1),
            label, fill="#ffffff", font=font,
        )
    return img


def _icon_idle() -> Image.Image:
    return _create_icon_image("#89b4fa")


def _icon_pending(count: int = 0) -> Image.Image:
    return _create_icon_image("#f38ba8", badge_count=count)


def _icon_paused(count: int = 0) -> Image.Image:
    return _create_icon_image(PAUSED_ICON_COLOR, badge_count=count)


# ── TrayIcon wrapper ─────────────────────────────────────────────────

class TrayIcon:
    """Manages the system-tray icon and its context menu.

    Parameters
    ----------
    on_open_dashboard:
        Called when the user clicks "Dashboard".
    on_toggle_focus:
        Called when the user toggles focus/snooze mode.
    on_undo:
        Called when the user clicks "Undo last".
    on_open_settings:
        Called when the user clicks "Settings".
    on_open_rules:
        Called when the user clicks "Manage Rules".
    on_add_folder:
        Called when the user clicks "Add folder to watch...".
    on_rescan:
        Called when the user clicks "Rescan watched folders".
    on_quit:
        Called when the user clicks "Quit".
    """

    def __init__(
        self,
        on_open_dashboard: Callable[[], None] | None = None,
        on_toggle_focus: Callable[[], None] | None = None,
        on_undo: Callable[[], None] | None = None,
        on_open_settings: Callable[[], None] | None = None,
        on_open_rules: Callable[[], None] | None = None,
        on_open_manual: Callable[[], None] | None = None,
        on_add_folder: Callable[[], None] | None = None,
        on_rescan: Callable[[], None] | None = None,
        on_process_pending: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._on_dashboard = on_open_dashboard or (lambda: None)
        self._on_focus = on_toggle_focus or (lambda: None)
        self._on_undo = on_undo or (lambda: None)
        self._on_settings = on_open_settings or (lambda: None)
        self._on_rules = on_open_rules or (lambda: None)
        self._on_manual = on_open_manual or (lambda: None)
        self._on_add_folder = on_add_folder or (lambda: None)
        self._on_rescan = on_rescan or (lambda: None)
        self._on_process_pending = on_process_pending or (lambda: None)
        self._on_quit = on_quit or (lambda: None)
        self._icon: pystray.Icon | None = None
        self._pending = False
        self._pending_count = 0
        self._prompts_paused = False
        self._monitored_count = 0

    @staticmethod
    def _action(callback: Callable[[], None]) -> Callable[..., None]:
        """Return a pystray-compatible action callback."""
        def _wrapped(*_args: object) -> None:
            callback()
        return _wrapped

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                "Folder setup...",
                self._action(self._on_add_folder),
            ),
            pystray.MenuItem(
                "Rescan watched folders",
                self._action(self._on_rescan),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _: (
                    f"Sort {self._pending_count} pending file{'s' if self._pending_count != 1 else ''}"
                    if self._pending_count > 0
                    else "Sort pending files"
                ),
                self._action(self._on_process_pending),
                visible=lambda _: self._pending,
            ),
            pystray.MenuItem(
                lambda _: (
                    "Pause sorting prompts"
                    if not self._prompts_paused
                    else "Resume sorting prompts"
                ),
                self._action(self._on_focus),
                default=True,
                checked=lambda _: self._prompts_paused,
            ),
            pystray.MenuItem("Undo last move", self._action(self._on_undo)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Activity & Queue", self._action(self._on_dashboard)),
            pystray.MenuItem("Settings", self._action(self._on_settings)),
            pystray.MenuItem("Sorting Rules...", self._action(self._on_rules)),
            pystray.MenuItem("Manual", self._action(self._on_manual)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._action(self._quit)),
        )

    def _quit(self) -> None:
        self._on_quit()
        if self._icon:
            self._icon.stop()

    def start(self) -> None:
        """Create and run the tray icon (blocks the calling thread).

        On Linux, pystray selects a backend (AppIndicator, GTK, or Xorg) at
        runtime.  If none of the backends are available (missing system libs or
        no display), it raises an exception.  We catch it here, show a visible
        error to the user, and re-raise so the main thread can shut down cleanly.
        """
        import sys

        def _show_error(msg: str) -> None:
            """Best-effort: show a Tk error dialog so the user sees the problem."""
            try:
                import tkinter as _tk
                from tkinter import messagebox as _mb
                _root = _tk.Tk()
                _root.withdraw()
                _mb.showerror("Iconic File Filer — Tray error", msg)
                _root.destroy()
            except Exception:
                pass

        # If pystray itself failed to import (e.g. no X display at import
        # time, or missing Xlib/six in the bundle), surface the error now.
        if _pystray_import_error is not None:
            logger.error(
                "pystray could not be imported: %s", _pystray_import_error,
                exc_info=_pystray_import_error,
            )
            if sys.platform != "win32":
                _show_error(
                    f"pystray failed to load:\n\n{_pystray_import_error}\n\n"
                    "On Wayland, make sure XWayland is running (DISPLAY must "
                    "be set) and that python3-xlib is installed.\n\n"
                    "Check ~/.iconic-filer/iconic-filer.log for details."
                )
            raise _pystray_import_error

        try:
            self._icon = pystray.Icon(
                "iconic-filer",
                _icon_idle(),
                "Iconic File Filer",
                menu=self._build_menu(),
            )
            self._icon.run()
        except Exception as exc:  # noqa: BLE001
            # On Linux a missing tray backend produces a cryptic error.
            # Attempt to surface it via a Tk messagebox so the user sees it.
            if sys.platform != "win32":
                _show_error(
                    f"The system tray could not be initialised:\n\n{exc}\n\n"
                    "On Wayland, make sure XWayland is running (DISPLAY "
                    "must be set) and that libayatana-appindicator3 or "
                    "python3-xlib is installed.\n\n"
                    "Check ~/.iconic-filer/iconic-filer.log for details."
                )
            logger.error("Tray icon failed to initialize: %s", exc, exc_info=True)
            raise

    def start_threaded(self) -> threading.Thread:
        """Start the tray icon in a background thread and return it."""
        t = threading.Thread(target=self.start, daemon=True)
        t.start()
        return t

    def set_focus_mode(self, enabled: bool) -> None:
        """Update the focus-mode checkmark state in the tray menu."""
        self._prompts_paused = enabled
        if self._icon:
            self._refresh_idle_icon()

    def set_pending(self, pending: bool, count: int = 0) -> None:
        """Update the icon to reflect pending items with a badge count."""
        self._pending = pending
        self._pending_count = count
        if self._icon:
            if self._prompts_paused:
                self._apply_paused_visual(count if pending else 0)
            elif pending:
                self._icon.icon = _icon_pending(count)
                self._icon.title = f"Iconic File Filer ({count} pending)"
            else:
                self._refresh_idle_icon()

    def set_monitored_count(self, count: int) -> None:
        """Update the tray tooltip to show how many folders are being monitored."""
        self._monitored_count = count
        if self._icon and not self._pending:
            self._refresh_idle_icon()

    def _refresh_idle_icon(self) -> None:
        """Refresh the icon and title to reflect the monitored folder count."""
        if self._icon:
            if self._prompts_paused:
                self._apply_paused_visual()
                return
            self._icon.icon = _icon_idle()
            n = self._monitored_count
            if n > 0:
                self._icon.title = f"Iconic File Filer ({n} folder{'s' if n != 1 else ''} watched)"
            else:
                self._icon.title = "Iconic File Filer"

    def _apply_paused_visual(self, queued_count: int = 0) -> None:
        """Apply paused icon/title style, with optional queued badge count."""
        if not self._icon:
            return
        self._icon.icon = _icon_paused(queued_count)
        status = "paused"
        if queued_count:
            status += f", {queued_count} queued"
        self._icon.title = f"Iconic File Filer ({status})"

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
