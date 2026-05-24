"""User prompt dialogs for Iconic File Filer (customtkinter-based)."""

from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
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
        on_delete: Callable[[str], None] | None = None,
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
        on_delete:
            Called with the file path when the user chooses to delete it.
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
        self._on_delete = on_delete
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

        def _append_destination(dest: str, is_last: bool = False) -> None:
            if dest in _key_dests:
                return
            _key_dests.append(dest)
            self._dest_card(card_container, len(_key_dests) - 1, dest, is_last, t, _choose)

        # "Same as last time" appears first with a distinct visual
        if last_dest is not None:
            _append_destination(last_dest, True)

        for dest in self._destinations:
            _append_destination(dest)

        if not _key_dests:
            ctk.CTkLabel(
                card_container,
                text="No destination folders yet. Add one to start moving files.",
                font=_font(10),
                text_color=t["muted"],
                anchor="w",
                justify="left",
            ).pack(anchor="w", pady=(0, 6))

        action_container = ctk.CTkFrame(root, fg_color="transparent")
        action_container.pack(fill="x", padx=20, pady=(0, 6))

        # ── "Add new folder to list" card ─────────────────────────────
        # Picks a folder, saves it permanently, then routes the file there.
        if self._on_save_destination is not None:
            _save_dest_cb = self._on_save_destination

            def _add_existing_and_send() -> None:
                folder = filedialog.askdirectory(
                    title="Choose folder to add to your list"
                )
                if not folder:
                    return
                _save_dest_cb(folder)
                _append_destination(folder)
                _choose(folder)

            def _create_new_folders() -> None:
                parent_dir = filedialog.askdirectory(
                    title="Choose where to create new folders"
                )
                if not parent_dir:
                    return
                names = simpledialog.askstring(
                    "Create new folders",
                    "Enter one or more folder names (comma- or line-separated):",
                    parent=root,
                )
                if not names:
                    return
                created: list[str] = []
                parts: list[str] = []
                for line in names.splitlines():
                    parts.extend(line.split(","))
                for raw in parts:
                    name = raw.strip()
                    if not name:
                        continue
                    path = os.path.join(parent_dir, name)
                    try:
                        os.makedirs(path, exist_ok=True)
                    except OSError as exc:
                        messagebox.showwarning(
                            "Could not create folder",
                            f"{path}\n\n{exc}",
                            parent=root,
                        )
                        continue
                    _save_dest_cb(path)
                    _append_destination(path)
                    created.append(path)
                if not created:
                    return
                if len(created) == 1:
                    _choose(created[0])
                else:
                    messagebox.showinfo(
                        "Folders created",
                        f"Created {len(created)} folders. Pick one above to move this file.",
                        parent=root,
                    )

            ctk.CTkButton(
                action_container,
                text="➕  Add folder",
                height=40,
                fg_color="transparent",
                border_color=t["accent"],
                border_width=1,
                text_color=t["accent"],
                hover_color=t["btn_bg"],
                font=_font(11),
                corner_radius=10,
                anchor="w",
                command=_add_existing_and_send,
            ).pack(fill="x", pady=(6, 3))
            ctk.CTkButton(
                action_container,
                text="🆕  Create new folder(s)",
                height=40,
                fg_color="transparent",
                border_color=t["accent"],
                border_width=1,
                text_color=t["accent"],
                hover_color=t["btn_bg"],
                font=_font(11),
                corner_radius=10,
                anchor="w",
                command=_create_new_folders,
            ).pack(fill="x", pady=(0, 3))

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
            action_container,
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
        deleted = [False]

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

        if self._on_delete is not None:
            _delete_cb = self._on_delete

            def _do_delete() -> None:
                if not messagebox.askyesno(
                    "Delete file",
                    "Permanently delete this item?",
                    parent=root,
                ):
                    return
                deleted[0] = True
                root.destroy()
                _delete_cb(self._filepath)

            ctk.CTkButton(
                footer,
                text="🗑 Delete",
                text_color=t["danger"],
                command=_do_delete,
                **_ghost_kw,
            ).pack(side="right", padx=(0, 4))

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

        if whitelisted[0] or deleted[0]:
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

    def __init__(
        self,
        theme: str = "dark",
        initial_folders: dict[str, list[str]] | None = None,
    ) -> None:
        self.result: dict[str, list[str]] = {}
        self._root: ctk.CTk | None = None
        self._theme_name = theme
        self._initial_folders = initial_folders

    def run(self) -> dict[str, list[str]]:
        """Show the wizard and return ``{folder: [destinations]}``."""
        t = get_theme(self._theme_name)
        apply_ctk_appearance(self._theme_name)

        root = ctk.CTk()
        self._root = root
        root.title("Iconic File Filer — Setup Wizard")
        root.resizable(False, False)

        w, h = 640, 560
        sx = root.winfo_screenwidth() // 2 - w // 2
        sy = root.winfo_screenheight() // 2 - h // 2
        root.geometry(f"{w}x{h}+{sx}+{sy}")

        ctk.CTkLabel(
            root,
            text="🧭 Iconic File Filer — Setup Wizard",
            font=_font(19, "bold"),
            text_color=t["accent"],
        ).pack(pady=(22, 4))
        ctk.CTkLabel(
            root,
            text="Follow the steps to choose watched folders and destinations.",
            font=_font(11),
            text_color=t["muted"],
        ).pack(pady=(0, 10))

        step_label = ctk.CTkLabel(
            root,
            text="",
            font=_font(11, "bold"),
            text_color=t["btn_fg"],
        )
        step_label.pack(pady=(0, 6))

        progress = ctk.CTkProgressBar(root, width=320)
        progress.pack(pady=(0, 12))

        content = ctk.CTkFrame(root, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(6, 0))

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

        def _normalize_path(path: str) -> str:
            return os.path.abspath(path)

        folders_data: dict[str, list[str]] = {}
        if self._initial_folders is None:
            folders_data = _detect_default_folders()
        else:
            for folder, dests in self._initial_folders.items():
                if not folder:
                    continue
                folders_data[_normalize_path(folder)] = [
                    _normalize_path(d) for d in dests
                ]

        # ── Step 1: Watched folders ────────────────────────────────────
        step_one = ctk.CTkFrame(content, fg_color="transparent")
        ctk.CTkLabel(
            step_one,
            text="Step 1 — Choose watched folders",
            font=_font(14, "bold"),
            text_color=t["accent"],
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            step_one,
            text="Pick the folders you want Iconic File Filer to watch.",
            font=_font(10),
            text_color=t["muted"],
        ).pack(anchor="w", pady=(0, 10))

        watch_list = ctk.CTkScrollableFrame(step_one, height=230)
        watch_list.pack(fill="x", pady=4)

        def _remove_folder(folder: str) -> None:
            folders_data.pop(folder, None)
            _refresh_watch_list()

        def _refresh_watch_list() -> None:
            for child in watch_list.winfo_children():
                child.destroy()
            if not folders_data:
                ctk.CTkLabel(
                    watch_list,
                    text="No watched folders yet. Add one to continue.",
                    font=_font(10),
                    text_color=t["muted"],
                ).pack(anchor="w", padx=6, pady=6)
                return
            for folder in sorted(folders_data):
                row = ctk.CTkFrame(watch_list, corner_radius=8)
                row.pack(fill="x", padx=4, pady=4)
                label = ctk.CTkLabel(
                    row,
                    text=f"📂  {os.path.basename(folder) or folder}\n{folder}",
                    font=_font(11),
                    anchor="w",
                    justify="left",
                )
                label.pack(side="left", fill="x", expand=True, padx=10, pady=8)
                ctk.CTkButton(
                    row,
                    text="Remove",
                    width=90,
                    fg_color=t["btn_bg"],
                    text_color=t["btn_fg"],
                    hover_color=t["btn_active"],
                    command=lambda f=folder: _remove_folder(f),
                ).pack(side="right", padx=10, pady=8)

        def _add_folder() -> None:
            folder = filedialog.askdirectory(title="Select folder to monitor")
            if not folder:
                return
            folder = _normalize_path(folder)
            if folder in folders_data:
                messagebox.showinfo(
                    "Already added",
                    f"This folder is already being watched:\n{folder}",
                    parent=root,
                )
                return
            folders_data[folder] = folders_data.get(folder, [])
            _refresh_watch_list()

        ctk.CTkButton(
            step_one,
            text="+ Add watched folder",
            fg_color=t["accent"],
            text_color="#1e1e2e",
            hover_color=t["btn_active"],
            font=_font(12, "bold"),
            corner_radius=10,
            command=_add_folder,
        ).pack(anchor="w", pady=(8, 0))

        # ── Step 2: Destinations ───────────────────────────────────────
        step_two = ctk.CTkFrame(content, fg_color="transparent")
        ctk.CTkLabel(
            step_two,
            text="Step 2 — Pick destination folders",
            font=_font(14, "bold"),
            text_color=t["accent"],
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            step_two,
            text="Each watched folder needs one or more destination folders.",
            font=_font(10),
            text_color=t["muted"],
        ).pack(anchor="w", pady=(0, 10))

        dest_list = ctk.CTkScrollableFrame(step_two, height=230)
        dest_list.pack(fill="x", pady=4)

        def _pick_destinations(folder: str) -> None:
            dests = pick_destination_folders(folder, parent=root)
            if dests:
                folders_data[folder] = dests
                _refresh_dest_list()

        def _refresh_dest_list() -> None:
            for child in dest_list.winfo_children():
                child.destroy()
            if not folders_data:
                ctk.CTkLabel(
                    dest_list,
                    text="No watched folders selected yet.",
                    font=_font(10),
                    text_color=t["muted"],
                ).pack(anchor="w", padx=6, pady=6)
                return
            for folder, dests in folders_data.items():
                dest_names = ", ".join(
                    os.path.basename(d) for d in dests if d
                )
                dest_text = dest_names or "No destinations yet"
                row = ctk.CTkFrame(dest_list, corner_radius=8)
                row.pack(fill="x", padx=4, pady=4)
                ctk.CTkLabel(
                    row,
                    text=f"📂  {os.path.basename(folder) or folder}\n{dest_text}",
                    font=_font(11),
                    anchor="w",
                    justify="left",
                ).pack(side="left", fill="x", expand=True, padx=10, pady=8)
                ctk.CTkButton(
                    row,
                    text="Choose destinations",
                    width=150,
                    fg_color=t["btn_bg"],
                    text_color=t["btn_fg"],
                    hover_color=t["btn_active"],
                    command=lambda f=folder: _pick_destinations(f),
                ).pack(side="right", padx=10, pady=8)

        # ── Step 3: Review ─────────────────────────────────────────────
        step_three = ctk.CTkFrame(content, fg_color="transparent")
        ctk.CTkLabel(
            step_three,
            text="Step 3 — Review & finish",
            font=_font(14, "bold"),
            text_color=t["accent"],
        ).pack(anchor="w", pady=(0, 6))
        ctk.CTkLabel(
            step_three,
            text="Confirm everything looks right, then start the app.",
            font=_font(10),
            text_color=t["muted"],
        ).pack(anchor="w", pady=(0, 10))

        summary_list = ctk.CTkScrollableFrame(step_three, height=230)
        summary_list.pack(fill="x", pady=4)

        def _refresh_summary() -> None:
            for child in summary_list.winfo_children():
                child.destroy()
            if not folders_data:
                ctk.CTkLabel(
                    summary_list,
                    text="No watched folders configured.",
                    font=_font(10),
                    text_color=t["muted"],
                ).pack(anchor="w", padx=6, pady=6)
                return
            for folder, dests in folders_data.items():
                dest_names = ", ".join(
                    os.path.basename(d) for d in dests if d
                )
                text = (
                    f"📂  {os.path.basename(folder) or folder}\n"
                    f"➡  {dest_names or 'No destinations'}"
                )
                ctk.CTkLabel(
                    summary_list,
                    text=text,
                    font=_font(11),
                    anchor="w",
                    justify="left",
                ).pack(fill="x", padx=8, pady=6)

        steps = [step_one, step_two, step_three]
        step_titles = [
            "Watched folders",
            "Destination folders",
            "Review",
        ]
        state = {"idx": 0}

        def _update_step() -> None:
            for frame in steps:
                frame.pack_forget()
            steps[state["idx"]].pack(fill="both", expand=True)
            step_label.configure(
                text=f"Step {state['idx'] + 1} of 3 — {step_titles[state['idx']]}",
            )
            progress.set((state["idx"] + 1) / len(steps))
            back_btn.configure(
                state="normal" if state["idx"] > 0 else "disabled"
            )
            next_btn.configure(
                state="normal" if state["idx"] < len(steps) - 1 else "disabled"
            )
            finish_btn.configure(
                state="normal" if state["idx"] == len(steps) - 1 else "disabled"
            )
            _refresh_watch_list()
            _refresh_dest_list()
            _refresh_summary()

        def _validate_step_one() -> bool:
            if folders_data:
                return True
            messagebox.showwarning(
                "Add a watched folder",
                "Please add at least one folder to watch before continuing.",
                parent=root,
            )
            return False

        def _validate_step_two() -> bool:
            missing = [
                folder
                for folder, dests in folders_data.items()
                if not dests
            ]
            if not missing:
                return True
            messagebox.showwarning(
                "Destinations missing",
                "Each watched folder needs at least one destination folder.",
                parent=root,
            )
            return False

        def _next() -> None:
            if state["idx"] == 0 and not _validate_step_one():
                return
            if state["idx"] == 1 and not _validate_step_two():
                return
            if state["idx"] < len(steps) - 1:
                state["idx"] += 1
                _update_step()

        def _back() -> None:
            if state["idx"] > 0:
                state["idx"] -= 1
                _update_step()

        def _done() -> None:
            if not _validate_step_two():
                state["idx"] = 1
                _update_step()
                return
            self.result = folders_data
            root.destroy()

        nav = ctk.CTkFrame(root, fg_color="transparent")
        nav.pack(pady=16)
        back_btn = ctk.CTkButton(
            nav,
            text="Back",
            width=100,
            fg_color=t["btn_bg"],
            text_color=t["btn_fg"],
            hover_color=t["btn_active"],
            command=_back,
        )
        back_btn.pack(side="left", padx=8)
        next_btn = ctk.CTkButton(
            nav,
            text="Next",
            width=110,
            fg_color=t["accent"],
            text_color="#1e1e2e",
            hover_color=t["btn_active"],
            command=_next,
        )
        next_btn.pack(side="left", padx=8)
        finish_btn = ctk.CTkButton(
            nav,
            text="Complete setup & start in tray ✓",
            width=240,
            fg_color=t["btn_bg"],
            text_color=t["btn_fg"],
            hover_color=t["accent"],
            command=_done,
        )
        finish_btn.pack(side="left", padx=8)

        _update_step()

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
