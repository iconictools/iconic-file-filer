"""User prompt dialogs for Iconic File Filer (customtkinter-based)."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Callable

import customtkinter as ctk

from iconic_filer.themes import apply_ctk_appearance, get_theme

logger = logging.getLogger(__name__)

# ── Font helpers ──────────────────────────────────────────────────────

def _font(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(size=size, weight=weight)


def pick_destination_folders(
    source_folder: str,
    *,
    parent: tk.Misc | None = None,
) -> list[str]:
    """Interactively pick one or more destination folders."""
    source_name = os.path.basename(source_folder) or source_folder
    destinations: list[str] = []
    while True:
        if parent is not None:
            dest = filedialog.askdirectory(
                title=f"Choose destination for {source_name}",
                parent=parent,
            )
        else:
            dest = filedialog.askdirectory(
                title=f"Choose destination for {source_name}",
            )
        if not dest:
            break
        dest = os.path.abspath(dest)
        if dest in destinations:
            if parent is not None:
                messagebox.showinfo(
                    "Already added",
                    f"This destination is already selected:\n{dest}",
                    parent=parent,
                )
            else:
                messagebox.showinfo(
                    "Already added",
                    f"This destination is already selected:\n{dest}",
                )
        else:
            destinations.append(dest)
        if parent is not None:
            add_more = messagebox.askyesno(
                "Add another destination?",
                "Do you want to add another destination folder?",
                parent=parent,
            )
        else:
            add_more = messagebox.askyesno(
                "Add another destination?",
                "Do you want to add another destination folder?",
            )
        if not add_more:
            break
    return destinations


# ── SortPrompt ────────────────────────────────────────────────────────

class SortPrompt:
    """Non-intrusive popup asking the user where to send a file."""

    def __init__(
        self,
        filepath: str,
        destinations: list[str],
        on_done: Callable[[str, str | None, bool], None],
        theme: str = "dark",
        on_whitelist: Callable[[str], None] | None = None,
        on_quick_add: Callable[[str], None] | None = None,
        history: Any = None,
        on_snooze: Callable[[], None] | None = None,
        on_save_destination: Callable[[str], None] | None = None,
        always_rule_default: bool = False,
        auto_accept_seconds: int = 0,
    ) -> None:
        """
        Parameters
        ----------
        filepath:
            Absolute path of the detected file.
        destinations:
            Ordered list of suggested destination folder paths.
        on_done:
            ``(filepath, chosen_destination_or_None, always_rule)``
        theme:
            Theme name (``'dark'`` or ``'light'``).
        on_whitelist:
            Called with a glob pattern when the user clicks "Add to whitelist".
        on_quick_add:
            Called with the folder path when the user clicks "Quick Add Folder"
            (only shown when the detected item is a directory).
        history:
            Optional History instance used for "Same as last time" suggestion.
        on_snooze:
            Called when the user clicks "Later" to defer the prompt.
        on_save_destination:
            Called with a folder path when the user picks a new destination
            and confirms they want it saved as a permanent destination.
        always_rule_default:
            Whether the "Always send .ext files here" checkbox is pre-checked.
        auto_accept_seconds:
            If > 0, automatically pick the top suggestion after this many
            seconds (user can cancel by pressing Escape or clicking elsewhere).
        """
        self._filepath = filepath
        self._destinations = destinations
        self._on_done = on_done
        self._always = False
        self._theme_name = theme
        self._on_whitelist = on_whitelist
        self._on_quick_add = on_quick_add
        self._history = history
        self._on_snooze = on_snooze
        self._on_save_destination = on_save_destination
        self._always_rule_default = always_rule_default
        self._auto_accept_seconds = auto_accept_seconds

    # ── Card-button factory ────────────────────────────────────────────

    @staticmethod
    def _dest_card(
        parent: Any,
        idx: int,
        dest: str,
        is_last_used: bool,
        t: dict,
        on_click: Callable[[str], None],
    ) -> None:
        """Create a tall, card-style destination button inside *parent*.

        The card shows the folder name prominently with the shortened path
        underneath and a keyboard-shortcut number on the left.  Hover
        changes the background to the accent colour on both Windows and Linux.
        """
        home = os.path.expanduser("~")
        folder_name = os.path.basename(dest) or dest
        short_path = dest.replace(home, "~") if dest.startswith(home) else dest

        normal_color = t["success"] if is_last_used else t["btn_bg"]
        hover_color = t["btn_active"] if is_last_used else t["accent"]
        num_label = "↵" if is_last_used else str(idx + 1)

        # Outer card frame
        card = ctk.CTkFrame(parent, fg_color=normal_color, corner_radius=10)
        card.pack(fill="x", pady=3)
        card.grid_columnconfigure(1, weight=1)

        # Number / shortcut badge
        badge = ctk.CTkLabel(
            card, text=num_label,
            font=_font(11, "bold"),
            text_color=t["muted"] if not is_last_used else "#1e1e2e",
            width=32,
        )
        badge.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=10, sticky="ns")

        # Folder name (primary)
        name_lbl = ctk.CTkLabel(
            card, text=f"📁  {folder_name}",
            font=_font(13, "bold"),
            text_color=t["btn_fg"] if not is_last_used else "#1e1e2e",
            anchor="w",
        )
        name_lbl.grid(row=0, column=1, sticky="w", pady=(8, 0))

        # Short path (secondary)
        path_lbl = ctk.CTkLabel(
            card, text=short_path,
            font=_font(9),
            text_color=t["muted"] if not is_last_used else "#3e3e5e",
            anchor="w",
        )
        path_lbl.grid(row=1, column=1, sticky="w", pady=(0, 8))

        # Hover effect + click binding on all child widgets
        def _enter(_e: Any = None) -> None:
            card.configure(fg_color=hover_color)

        def _leave(_e: Any = None) -> None:
            card.configure(fg_color=normal_color)

        def _click(_e: Any = None) -> None:
            on_click(dest)

        for widget in (card, badge, name_lbl, path_lbl):
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)
            widget.bind("<Button-1>", _click)

        # Make the frame expand on hover for keyboard-only users
        card.configure(cursor="hand2")

    def show(self) -> None:
        """Display the prompt (blocks until user responds)."""
        t = get_theme(self._theme_name)
        apply_ctk_appearance(self._theme_name)

        root = ctk.CTk()
        root.title("Iconic File Filer")
        root.attributes("-topmost", True)
        root.resizable(True, False)

        basename = os.path.basename(self._filepath)
        is_dir = os.path.isdir(self._filepath)
        _, ext_lower = os.path.splitext(self._filepath)
        ext_lower = ext_lower.lower()

        # ── File metadata ──────────────────────────────────────────────
        size_str = ""
        if not is_dir:
            try:
                size_bytes = os.path.getsize(self._filepath)
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
            except OSError:
                size_str = ""

        _TYPE_LABELS: dict[str, str] = {
            ".pdf": "📄", ".zip": "🗜", ".rar": "🗜", ".7z": "🗜",
            ".doc": "📝", ".docx": "📝", ".xls": "📊", ".xlsx": "📊",
            ".ppt": "📊", ".pptx": "📊", ".mp4": "🎬", ".mkv": "🎬",
            ".avi": "🎬", ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵",
            ".jpg": "🖼", ".jpeg": "🖼", ".png": "🖼", ".gif": "🖼",
            ".exe": "⚙", ".msi": "⚙", ".deb": "⚙", ".rpm": "⚙",
            ".py": "🐍", ".js": "📜", ".ts": "📜", ".go": "📜",
            ".txt": "📄", ".md": "📄", ".csv": "📊", ".json": "📄",
        }
        file_icon = "📁" if is_dir else _TYPE_LABELS.get(ext_lower, "🗂")

        # ── Header ────────────────────────────────────────────────────
        # Compact two-line header: icon + filename + size
        header_frame = ctk.CTkFrame(root, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            header_frame,
            text=file_icon,
            font=_font(28),
            width=48,
        ).pack(side="left", padx=(0, 12))

        name_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        name_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            name_frame,
            text=basename,
            font=_font(13, "bold"),
            anchor="w",
            wraplength=360,
            justify="left",
        ).pack(anchor="w")

        meta_parts = []
        if size_str:
            meta_parts.append(size_str)
        if ext_lower and not is_dir:
            meta_parts.append(ext_lower.upper().lstrip("."))
        if meta_parts:
            ctk.CTkLabel(
                name_frame,
                text="  ·  ".join(meta_parts),
                font=_font(10),
                text_color=t["muted"],
                anchor="w",
            ).pack(anchor="w")

        # Thin separator
        ctk.CTkFrame(root, fg_color=t["btn_bg"], height=1).pack(
            fill="x", padx=20, pady=(0, 8)
        )

        # ── "Send to:" label ───────────────────────────────────────────
        ctk.CTkLabel(
            root,
            text="Send to:",
            font=_font(10),
            text_color=t["muted"],
            anchor="w",
        ).pack(anchor="w", padx=20, pady=(0, 4))

        # ── Destination cards ──────────────────────────────────────────
        chosen: list[str | None] = [None]
        _key_dests: list[str] = []  # ordered for keyboard shortcuts 1-9 / Enter

        def _choose(dest: str) -> None:
            chosen[0] = dest
            root.destroy()

        # Find "same as last time" candidate
        last_dest: str | None = None
        if self._history is not None and ext_lower:
            last_dest = self._history.last_dest_for_ext(ext_lower)
            if last_dest is not None and not os.path.isdir(last_dest):
                last_dest = None
            if last_dest is not None and last_dest not in self._destinations:
                last_dest = None

        # Scroll only when there are many destinations (>5)
        SHOW_SCROLL_THRESHOLD = 5
        n_dests = len(self._destinations)
        card_container: Any
        if n_dests > SHOW_SCROLL_THRESHOLD:
            card_container = ctk.CTkScrollableFrame(
                root, height=300, fg_color="transparent"
            )
        else:
            card_container = ctk.CTkFrame(root, fg_color="transparent")
        card_container.pack(fill="x", padx=20, pady=(0, 6))

        # "Same as last time" appears first with a distinct visual
        if last_dest is not None:
            _key_dests.append(last_dest)
            self._dest_card(card_container, 0, last_dest, True, t, _choose)

        btn_idx = len(_key_dests)  # starts at 1 if last_dest was added
        for dest in self._destinations:
            if dest in _key_dests:
                continue
            _key_dests.append(dest)
            self._dest_card(card_container, btn_idx, dest, False, t, _choose)
            btn_idx += 1

        # ── "Add new folder to list" card ─────────────────────────────
        # Picks a folder, saves it permanently, then routes the file there.
        if self._on_save_destination is not None:
            _save_dest_cb = self._on_save_destination

            def _add_and_send() -> None:
                folder = filedialog.askdirectory(
                    title="Choose folder to add to your list"
                )
                if not folder:
                    return
                _save_dest_cb(folder)
                _choose(folder)

            ctk.CTkButton(
                card_container,
                text="➕  Add new folder to my list",
                height=44,
                fg_color="transparent",
                border_color=t["accent"],
                border_width=1,
                text_color=t["accent"],
                hover_color=t["btn_bg"],
                font=_font(11),
                corner_radius=10,
                anchor="w",
                command=_add_and_send,
            ).pack(fill="x", pady=(6, 3))

        # ── "One-time send" card ───────────────────────────────────────
        # Picks a folder and sends the file there — nothing is saved.
        def _one_time_send() -> None:
            folder = filedialog.askdirectory(
                title="Choose destination (will not be saved)"
            )
            if not folder:
                return
            _choose(folder)

        ctk.CTkButton(
            card_container,
            text="📁  Send to folder (one-time, not saved)",
            height=44,
            fg_color="transparent",
            border_color=t["muted"],
            border_width=1,
            text_color=t["muted"],
            hover_color=t["btn_bg"],
            font=_font(11),
            corner_radius=10,
            anchor="w",
            command=_one_time_send,
        ).pack(fill="x", pady=(0, 0))

        # ── Collapsible rename row ─────────────────────────────────────
        rename_var = tk.StringVar(value=basename)
        name_without_ext, _ = os.path.splitext(basename)
        rename_revealed = [False]
        rename_container = ctk.CTkFrame(root, fg_color="transparent")

        def _toggle_rename() -> None:
            if rename_revealed[0]:
                rename_container.pack_forget()
                rename_revealed[0] = False
            else:
                rename_container.pack(fill="x", padx=20, pady=(0, 4))
                rename_revealed[0] = True
                rename_entry.focus_set()
                rename_entry.select_range(0, len(name_without_ext))

        rename_lbl_frame = ctk.CTkFrame(root, fg_color="transparent")
        rename_lbl_frame.pack(anchor="w", padx=20, pady=(2, 0))
        ctk.CTkButton(
            rename_lbl_frame,
            text="✎  Rename before moving",
            fg_color="transparent",
            text_color=t["muted"],
            hover_color="transparent",
            font=_font(9),
            anchor="w",
            width=0,
            command=_toggle_rename,
        ).pack(side="left")

        rename_entry = ctk.CTkEntry(
            rename_container,
            textvariable=rename_var,
            font=_font(11),
            border_color=t["accent"],
            height=36,
        )
        rename_entry.pack(fill="x")

        # ── Footer: action bar ─────────────────────────────────────────
        # Quick Add (folders only) | Later | Never (whitelist) | Ignore
        ctk.CTkFrame(root, fg_color=t["btn_bg"], height=1).pack(
            fill="x", padx=20, pady=(8, 4)
        )
        footer = ctk.CTkFrame(root, fg_color="transparent")
        footer.pack(fill="x", padx=20, pady=(0, 14))

        whitelisted = [False]
        quick_added = [False]
        snoozed = [False]

        _ghost_kw: dict = dict(
            fg_color="transparent",
            hover_color=t["btn_bg"],
            font=_font(10),
            corner_radius=8,
            height=30,
        )

        # Quick Add Folder — directory detection only
        if is_dir and self._on_quick_add is not None:
            _fp = self._filepath
            _qa = self._on_quick_add

            def _do_quick_add() -> None:
                quick_added[0] = True
                root.destroy()
                _qa(_fp)

            ctk.CTkButton(
                footer,
                text="📂 Add & watch this folder",
                text_color=t["accent"],
                command=_do_quick_add,
                **_ghost_kw,
            ).pack(side="left")

        # Snooze / Later
        if self._on_snooze is not None:
            _snooze_cb = self._on_snooze

            def _do_snooze() -> None:
                snoozed[0] = True
                root.destroy()
                _snooze_cb()

            ctk.CTkButton(
                footer,
                text="⏰ Later",
                text_color=t["muted"],
                command=_do_snooze,
                **_ghost_kw,
            ).pack(side="left", padx=(0, 4))

        # Never / whitelist
        if self._on_whitelist is not None:
            def _add_to_whitelist() -> None:
                name = os.path.basename(self._filepath)
                if self._on_whitelist is not None:
                    self._on_whitelist(name)
                whitelisted[0] = True
                root.destroy()

            ctk.CTkButton(
                footer,
                text="🚫 Never",
                text_color=t["muted"],
                command=_add_to_whitelist,
                **_ghost_kw,
            ).pack(side="left", padx=(0, 4))

        # Ignore (right-aligned)
        ctk.CTkButton(
            footer,
            text="✕ Ignore",
            text_color=t["muted"],
            command=root.destroy,
            **_ghost_kw,
        ).pack(side="right")

        # Keyboard hint in footer
        ctk.CTkLabel(
            footer,
            text="1-9 · Enter · Esc",
            font=_font(9),
            text_color=t["muted"],
        ).pack(side="right", padx=(0, 8))

        # ── Auto-accept countdown ──────────────────────────────────────
        if self._auto_accept_seconds > 0 and _key_dests:
            _auto_dest = _key_dests[0]
            _remaining = [self._auto_accept_seconds]

            _cdown = ctk.CTkLabel(
                root,
                text=f"Auto-sorting in {_remaining[0]}s… Esc to cancel",
                font=_font(9),
                text_color=t["muted"],
            )
            _cdown.pack(pady=(0, 4))

            def _tick() -> None:
                _remaining[0] -= 1
                if _remaining[0] <= 0:
                    if chosen[0] is None:
                        _choose(_auto_dest)
                    return
                try:
                    _cdown.configure(
                        text=f"Auto-sorting in {_remaining[0]}s… Esc to cancel"
                    )
                    root.after(1000, _tick)
                except Exception:
                    pass

            root.after(1000, _tick)

        # ── Window geometry ────────────────────────────────────────────
        # Size to content then center; min width 440.
        root.update_idletasks()
        win_w = max(440, root.winfo_reqwidth())
        win_h = root.winfo_reqheight()
        sx = root.winfo_screenwidth() // 2 - win_w // 2
        sy = max(40, root.winfo_screenheight() // 2 - win_h // 2)
        root.geometry(f"{win_w}x{win_h}+{sx}+{sy}")
        root.minsize(440, 200)

        # ── Keyboard shortcuts ─────────────────────────────────────────
        def _on_key(event: Any) -> None:
            key = event.keysym
            if key == "Escape":
                root.destroy()
            elif key == "Return" and _key_dests:
                _choose(_key_dests[0])
            elif key.isdigit():
                idx = int(key) - 1
                if 0 <= idx < len(_key_dests):
                    _choose(_key_dests[idx])

        root.bind("<Key>", _on_key)
        root.focus_force()

        root.mainloop()

        # ── Post-close logic ───────────────────────────────────────────
        if quick_added[0]:
            return

        if snoozed[0]:
            return

        if whitelisted[0]:
            self._on_done(self._filepath, None, False)
            return

        # Apply optional rename before handing off
        new_name = rename_var.get().strip()
        if new_name and new_name != basename and os.path.exists(self._filepath):
            new_path = os.path.join(os.path.dirname(self._filepath), new_name)
            try:
                os.rename(self._filepath, new_path)
                self._filepath = new_path
            except OSError:
                pass

        # "always" is intentionally always False — rule creation is background-
        # only (auto-learn from history).  The user just clicks, not configures.
        self._on_done(self._filepath, chosen[0], False)


# ── SetupWizard ───────────────────────────────────────────────────────

class SetupWizard:
    """First-run wizard to configure monitored folders and destinations."""

    def __init__(self, theme: str = "dark") -> None:
        self.result: dict[str, list[str]] = {}
        self._root: ctk.CTk | None = None
        self._theme_name = theme

    def run(self) -> dict[str, list[str]]:
        """Show the wizard and return ``{folder: [destinations]}``."""
        t = get_theme(self._theme_name)
        apply_ctk_appearance(self._theme_name)

        root = ctk.CTk()
        self._root = root
        root.title("Iconic File Filer — Setup")
        root.resizable(False, False)

        w, h = 560, 520
        sx = root.winfo_screenwidth() // 2 - w // 2
        sy = root.winfo_screenheight() // 2 - h // 2
        root.geometry(f"{w}x{h}+{sx}+{sy}")

        ctk.CTkLabel(
            root,
            text="🗂 Iconic File Filer — Setup",
            font=_font(18, "bold"),
            text_color=t["accent"],
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            root,
            text="Choose folders to monitor and their destination folders.",
            font=_font(11),
            text_color=t["muted"],
        ).pack(pady=(0, 16))
        ctk.CTkLabel(
            root,
            text="1) Add a watched folder   2) Pick one or more destinations   3) Finalize and run in tray",
            font=_font(10),
            text_color=t["muted"],
        ).pack(pady=(0, 8))

        # Scrollable list of configured folders
        scroll_frame = ctk.CTkScrollableFrame(root, height=240)
        scroll_frame.pack(fill="x", padx=24, pady=4)
        scroll_frame.grid_columnconfigure(0, weight=1)

        # Pre-populate with common system folders if they exist.
        def _detect_default_folders() -> dict[str, list[str]]:
            home = os.path.expanduser("~")
            monitored_candidates = [
                os.path.join(home, "Downloads"),
                os.path.join(home, "Desktop"),
            ]
            destination_candidates = [
                os.path.join(home, "Documents"),
                os.path.join(home, "Pictures"),
                os.path.join(home, "Videos"),
                os.path.join(home, "Music"),
            ]
            detected: dict[str, list[str]] = {}
            for m in monitored_candidates:
                if os.path.isdir(m):
                    dests = [d for d in destination_candidates if os.path.isdir(d)]
                    if dests:
                        detected[m] = dests
            return detected

        folders_data: dict[str, list[str]] = _detect_default_folders()
        row_labels: list[ctk.CTkLabel] = []

        def _refresh_list() -> None:
            for lbl in row_labels:
                lbl.destroy()
            row_labels.clear()
            for folder, dests in folders_data.items():
                dest_names = ", ".join(os.path.basename(d) for d in dests)
                text = f"  {os.path.basename(folder)}  →  {dest_names}\n  {folder}"
                lbl = ctk.CTkLabel(
                    scroll_frame,
                    text=text,
                    font=_font(11),
                    anchor="w",
                    justify="left",
                )
                lbl.pack(fill="x", pady=4, padx=4)
                row_labels.append(lbl)

        def _add_folder() -> None:
            folder = filedialog.askdirectory(title="Select folder to monitor")
            if not folder:
                return
            dests = pick_destination_folders(folder, parent=root)
            if dests:
                folders_data[folder] = dests
                _refresh_list()

        def _done() -> None:
            if not folders_data:
                messagebox.showwarning(
                    "Setup incomplete",
                    "Add at least one folder to watch before finishing setup.",
                    parent=root,
                )
                return
            self.result = folders_data
            root.destroy()

        # Show pre-populated folders immediately
        _refresh_list()

        btn_frame = ctk.CTkFrame(root, fg_color="transparent")
        btn_frame.pack(pady=16)
        ctk.CTkButton(
            btn_frame,
            text="+ Add Folder",
            fg_color=t["accent"],
            text_color="#1e1e2e",
            hover_color=t["btn_active"],
            font=_font(12, "bold"),
            corner_radius=10,
            command=_add_folder,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame,
            text="Complete setup & start in tray ✓",
            fg_color=t["btn_bg"],
            text_color=t["btn_fg"],
            hover_color=t["accent"],
            font=_font(12),
            corner_radius=10,
            command=_done,
        ).pack(side="left", padx=10)

        root.mainloop()
        if self.result:
            messagebox.showinfo(
                "You're all set",
                "Iconic File Filer now runs in your system tray.\n\n"
                "Use the tray icon to open Activity & Queue, Settings, and Sorting Rules.\n"
                "When files arrive in watched folders, sorting prompts will appear.",
            )
        return self.result


# ── CLI setup ─────────────────────────────────────────────────────────

def cli_setup() -> dict[str, list[str]]:
    """CLI-based setup questionnaire (alternative to GUI wizard).

    Returns ``{folder: [destinations]}`` or empty dict if cancelled.
    """
    print("\n=== Iconic File Filer -- CLI Setup ===\n")
    folders: dict[str, list[str]] = {}

    while True:
        folder = input(
            "Folder to monitor (press Enter to finish): "
        ).strip()
        if not folder:
            break
        if not os.path.isdir(folder):
            print(f"  Warning: '{folder}' does not exist.")
            cont = input("  Add anyway? (y/n): ").strip().lower()
            if cont != "y":
                continue

        dests: list[str] = []
        while True:
            dest = input(
                f"  Destination for '{os.path.basename(folder)}' "
                "(press Enter to finish): "
            ).strip()
            if not dest:
                break
            dests.append(dest)

        if dests:
            folders[folder] = dests
            print(f"  Added: {folder} -> {', '.join(dests)}")

    if folders:
        print(f"\nConfigured {len(folders)} folder(s).")
    else:
        print("\nNo folders configured.")
    return folders
