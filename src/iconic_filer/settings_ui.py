"""Settings dialog for Iconic File Filer (customtkinter-based).

Layout (tabbed):
  Tab 1 — General     : theme, notifications, undo restore-name, multi-instance
  Tab 2 — Monitoring  : prompt delay, scan existing, catch folders, DND, pattern rules, duplicate detection
  Tab 3 — Folders     : watched folders ↔ per-folder destinations (full CRUD)
  Tab 4 — Rules       : whitelist patterns, ignore patterns, rename patterns
  Tab 5 — System      : autostart, batch mode, export/import config
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from typing import TYPE_CHECKING, Any, Callable

import customtkinter as ctk

from iconic_filer.autostart import is_autostart_enabled, set_autostart
from iconic_filer.prompt import pick_destination_folders
from iconic_filer.themes import apply_ctk_appearance, get_theme

if TYPE_CHECKING:
    from iconic_filer.config import Config

logger = logging.getLogger(__name__)
SETTINGS_TABS = ("General", "Monitoring", "Folders", "Rules", "System")

# ── Shared button helpers ─────────────────────────────────────────────

def _btn(parent: Any, text: str, t: dict, cmd: Any, kind: str = "normal", **kw: Any) -> ctk.CTkButton:
    colors = {
        "accent":  (t["accent"], "#1e1e2e", t["btn_active"]),
        "danger":  (t["danger"], "#ffffff", "#c9374a"),
        "normal":  (t["btn_bg"], t["btn_fg"], t["muted"]),
        "ghost":   ("transparent", t["muted"], t["btn_bg"]),
    }.get(kind, (t["btn_bg"], t["btn_fg"], t["muted"]))
    return ctk.CTkButton(
        parent, text=text,
        fg_color=colors[0], text_color=colors[1], hover_color=colors[2],
        font=ctk.CTkFont(size=10, weight="bold" if kind in ("accent", "danger") else "normal"),
        corner_radius=8,
        command=cmd,
        **kw,
    )


def _section_lbl(parent: Any, text: str, t: dict) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text,
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=t["accent"])


def _lbl(parent: Any, text: str, t: dict, size: int = 10) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=size), anchor="w")


def _check(parent: Any, text: str, var: tk.BooleanVar, t: dict) -> ctk.CTkCheckBox:
    return ctk.CTkCheckBox(parent, text=text, variable=var,
                           font=ctk.CTkFont(size=10),
                           fg_color=t["accent"], hover_color=t["btn_active"])


def _tk_listbox(parent: Any, t: dict, height: int = 6) -> tk.Listbox:
    """Return a styled tk.Listbox (CTk has no Listbox equivalent)."""
    lb = tk.Listbox(
        parent,
        bg=t["list_bg"], fg=t["list_fg"],
        selectbackground=t["list_select_bg"], selectforeground=t["list_select_fg"],
        font=("TkDefaultFont", 9), relief="flat", height=height, exportselection=False,
    )
    return lb


# ── Tab builders ──────────────────────────────────────────────────────

def _build_general_tab(tabview: ctk.CTkTabview, cfg: "Config", t: dict) -> dict:
    f = tabview.tab("General")

    row = 0

    def _grid(widget: Any, r: int, c: int, **kw: Any) -> None:
        widget.grid(row=r, column=c, sticky="w", padx=(8, 4), pady=3, **kw)

    _section_lbl(f, "Appearance", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                           padx=8, pady=(12, 4))
    row += 1
    _lbl(f, "Theme:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    theme_var = tk.StringVar(value=cfg.get_setting("theme", "dark"))
    ctk.CTkOptionMenu(f, variable=theme_var, values=["dark", "light"],
                      font=ctk.CTkFont(size=10)).grid(row=row, column=1, sticky="ew",
                                                       padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Sort Prompt Behavior", t).grid(row=row, column=0, columnspan=2,
                                                      sticky="w", padx=8, pady=(12, 4))
    row += 1
    _lbl(f, 'Pre-check "Always send .ext here":', t).grid(row=row, column=0, sticky="w",
                                                           padx=8, pady=3)
    always_rule_var = tk.BooleanVar(value=cfg.get_setting("prompt_always_rule", False))
    _check(f, "Enabled", always_rule_var, t).grid(row=row, column=1, sticky="w",
                                                    padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Auto-accept top suggestion after (s, 0=off):", t).grid(row=row, column=0,
                                                                      sticky="w", padx=8, pady=3)
    auto_accept_var = tk.IntVar(value=cfg.get_setting("prompt_auto_accept_seconds", 0))
    ctk.CTkEntry(f, textvariable=auto_accept_var, width=80,
                 font=ctk.CTkFont(size=10), border_color=t["accent"]).grid(
        row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Snooze duration (minutes):", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    snooze_var = tk.IntVar(value=cfg.get_setting("snooze_minutes", 30))
    ctk.CTkEntry(f, textvariable=snooze_var, width=80,
                 font=ctk.CTkFont(size=10), border_color=t["accent"]).grid(
        row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Notifications", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                              padx=8, pady=(12, 4))
    row += 1
    _lbl(f, "Native notifications:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    notif_var = tk.BooleanVar(value=cfg.get_setting("native_notifications", True))
    _check(f, "Enabled", notif_var, t).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Fallback when native fails:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    fallback_var = tk.StringVar(value=cfg.get_setting("notification_fallback", "log-only"))
    ctk.CTkOptionMenu(f, variable=fallback_var,
                      values=["toast-fallback", "log-only", "plyer-only"],
                      font=ctk.CTkFont(size=10)).grid(row=row, column=1, sticky="ew",
                                                       padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Undo Behavior", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                                padx=8, pady=(12, 4))
    row += 1
    _lbl(f, "When undoing a renamed move:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    undo_name_var = tk.StringVar(value=cfg.get_setting("undo_restore_name", "ask"))
    ctk.CTkOptionMenu(f, variable=undo_name_var, values=["ask", "always", "never"],
                      font=ctk.CTkFont(size=10)).grid(row=row, column=1, sticky="ew",
                                                       padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Multi-Instance", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                               padx=8, pady=(12, 4))
    row += 1
    _lbl(f, "Second launch behavior:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    multi_var = tk.StringVar(value=cfg.get_setting("multi_instance_behavior", "prompt"))
    ctk.CTkOptionMenu(f, variable=multi_var, values=["prompt", "always-merge", "ignore"],
                      font=ctk.CTkFont(size=10)).grid(row=row, column=1, sticky="ew",
                                                       padx=(0, 8), pady=3)
    row += 1

    f.grid_columnconfigure(1, weight=1)
    return {
        "theme": theme_var,
        "prompt_always_rule": always_rule_var,
        "prompt_auto_accept_seconds": auto_accept_var,
        "snooze_minutes": snooze_var,
        "native_notifications": notif_var,
        "notification_fallback": fallback_var,
        "undo_restore_name": undo_name_var,
        "multi_instance_behavior": multi_var,
    }


def _build_monitoring_tab(
    tabview: ctk.CTkTabview,
    cfg: "Config",
    t: dict,
    on_rescan: Callable[[], None] | None = None,
) -> dict:
    f = tabview.tab("Monitoring")
    row = 0

    _section_lbl(f, "File Detection", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                               padx=8, pady=(12, 4))
    row += 1

    _lbl(f, "Prompt delay (s):", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    delay_var = tk.DoubleVar(value=cfg.get_setting("prompt_delay_seconds", 3.0))
    # Use CTkEntry for numeric input
    delay_entry = ctk.CTkEntry(f, textvariable=delay_var, width=80,
                                font=ctk.CTkFont(size=10), border_color=t["accent"])
    delay_entry.grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Scan existing files at startup:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    scan_var = tk.BooleanVar(value=cfg.get_setting("scan_existing_enabled", False))
    _check(f, "Enabled", scan_var, t).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    if on_rescan is not None:
        _lbl(f, "Run a one-time rescan now:", t).grid(
            row=row, column=0, sticky="w", padx=8, pady=3
        )
        _btn(
            f,
            "Rescan watched folders now",
            t,
            on_rescan,
            "accent",
            width=190,
        ).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
        row += 1

        _lbl(
            f,
            "Rescan respects ignore patterns and whitelist patterns.",
            t,
            size=9,
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 3))
        row += 1

    _lbl(f, "Watch folders too (catch folders):", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    catch_var = tk.BooleanVar(value=cfg.get_setting("catch_folders", False))
    _check(f, "Enabled", catch_var, t).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Pause when DND / Focus Assist active:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    dnd_var = tk.BooleanVar(value=cfg.get_setting("pause_on_dnd", False))
    _check(f, "Enabled", dnd_var, t).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Rules & Detection", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                                   padx=8, pady=(12, 4))
    row += 1

    _lbl(f, "Pattern rules (glob/regex):", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    pattern_var = tk.BooleanVar(value=cfg.get_setting("pattern_rules_enabled", True))
    _check(f, "Enabled", pattern_var, t).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Duplicate detection (SHA-256):", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    dup_var = tk.BooleanVar(value=cfg.get_setting("duplicate_detection", False))
    _check(f, "Enabled", dup_var, t).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Cleanup Reminders", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                                   padx=8, pady=(12, 4))
    row += 1

    _lbl(f, "Alert when folder has ≥N unsorted files (0=off):", t).grid(
        row=row, column=0, sticky="w", padx=8, pady=3)
    cleanup_var = tk.IntVar(value=cfg.get_setting("cleanup_reminder_threshold", 0))
    ctk.CTkEntry(f, textvariable=cleanup_var, width=80,
                 font=ctk.CTkFont(size=10), border_color=t["accent"]).grid(
        row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "File Conflicts & Auto-Learning", t).grid(
        row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(12, 4))
    row += 1

    _lbl(f, "When a file already exists in a destination folder:", t).grid(
        row=row, column=0, sticky="w", padx=8, pady=3)
    conflict_var = tk.StringVar(value=cfg.get_setting("conflict_resolution", "rename"))
    ctk.CTkOptionMenu(
        f, variable=conflict_var,
        values=["rename", "ask", "overwrite", "skip"],
        font=ctk.CTkFont(size=10),
    ).grid(row=row, column=1, sticky="ew", padx=(0, 8), pady=3)
    row += 1

    _lbl(f, "Auto-create rule after N manual same-ext sorts (0=off):", t).grid(
        row=row, column=0, sticky="w", padx=8, pady=3)
    learn_var = tk.IntVar(value=cfg.get_setting("auto_learn_threshold", 0))
    ctk.CTkEntry(f, textvariable=learn_var, width=80,
                 font=ctk.CTkFont(size=10), border_color=t["accent"]).grid(
        row=row, column=1, sticky="w", padx=(0, 8), pady=3)
    row += 1

    f.grid_columnconfigure(1, weight=1)
    return {
        "prompt_delay_seconds": delay_var,
        "scan_existing_enabled": scan_var,
        "catch_folders": catch_var,
        "pause_on_dnd": dnd_var,
        "pattern_rules_enabled": pattern_var,
        "duplicate_detection": dup_var,
        "cleanup_reminder_threshold": cleanup_var,
        "conflict_resolution": conflict_var,
        "auto_learn_threshold": learn_var,
    }


def _build_folders_tab(
    tabview: ctk.CTkTabview,
    cfg: "Config",
    t: dict,
    root: ctk.CTk,
    on_folder_added: Callable[[str], None] | None = None,
    on_folder_removed: Callable[[str], None] | None = None,
) -> dict:
    f = tabview.tab("Folders")
    f.grid_columnconfigure(0, weight=1)
    f.grid_columnconfigure(1, weight=1)
    f.grid_rowconfigure(2, weight=1)

    _section_lbl(f, "Watched Folders & Destinations", t).grid(
        row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 2))
    _lbl(f, "Select a watched folder, then add/remove destinations on the right.", t, size=9).grid(
        row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))

    # Left pane: watched folders
    left = ctk.CTkFrame(f, fg_color="transparent")
    left.grid(row=2, column=0, sticky="nsew", padx=(8, 4), pady=4)
    _lbl(left, "Watched folders (origins):", t, size=10).pack(anchor="w")
    watch_list = _tk_listbox(left, t, height=10)
    watch_list.pack(fill="both", expand=True)
    for folder in cfg.monitored_folders:
        watch_list.insert("end", folder)
    watch_empty = _lbl(left, "", t, size=9)
    watch_empty.pack(anchor="w", pady=(2, 0))
    wbtn = ctk.CTkFrame(left, fg_color="transparent")
    wbtn.pack(fill="x", pady=(4, 0))

    # Right pane: destinations
    right = ctk.CTkFrame(f, fg_color="transparent")
    right.grid(row=2, column=1, sticky="nsew", padx=(4, 8), pady=4)
    _lbl(right, "Destination folders:", t, size=10).pack(anchor="w")
    dest_list = _tk_listbox(right, t, height=10)
    dest_list.pack(fill="both", expand=True)
    dest_empty = _lbl(right, "", t, size=9)
    dest_empty.pack(anchor="w", pady=(2, 0))
    dbtn = ctk.CTkFrame(right, fg_color="transparent")
    dbtn.pack(fill="x", pady=(4, 0))

    _selected_folder: list[str] = []
    watch_add_btn: ctk.CTkButton | None = None
    watch_remove_btn: ctk.CTkButton | None = None
    watch_open_btn: ctk.CTkButton | None = None
    dest_add_btn: ctk.CTkButton | None = None
    dest_remove_btn: ctk.CTkButton | None = None
    dest_open_btn: ctk.CTkButton | None = None

    # Per-folder details (label + whitelist)
    sep2 = ctk.CTkFrame(f, fg_color=t["btn_bg"], height=1)
    sep2.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    detail_frame = ctk.CTkFrame(f, fg_color="transparent")
    detail_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=8, pady=(0, 4))

    _section_lbl(detail_frame, "Per-Folder Details", t).grid(
        row=0, column=0, columnspan=4, sticky="w", pady=(4, 4))

    _lbl(detail_frame, "Folder Label:", t).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
    folder_label_var = tk.StringVar(value="")
    ctk.CTkEntry(detail_frame, textvariable=folder_label_var, width=280,
                 font=ctk.CTkFont(size=10), border_color=t["accent"]).grid(
        row=1, column=1, columnspan=3, sticky="ew", pady=2)

    _lbl(detail_frame, "Per-folder whitelist:", t).grid(row=2, column=0, sticky="nw",
                                                         padx=(0, 6), pady=2)
    pfwl_list = _tk_listbox(detail_frame, t, height=3)
    pfwl_list.grid(row=2, column=1, columnspan=3, sticky="ew", pady=2)
    pfwl_btn = ctk.CTkFrame(detail_frame, fg_color="transparent")
    pfwl_btn.grid(row=3, column=1, columnspan=3, sticky="w", pady=(2, 4))

    def _pfwl_add() -> None:
        if not _selected_folder:
            return
        pat = simpledialog.askstring(
            "Add whitelist pattern", "Enter a glob pattern (e.g. *.log):", parent=root
        )
        if pat and pat.strip():
            cfg.add_to_folder_whitelist(_selected_folder[0], pat.strip())
            pfwl_list.insert("end", pat.strip())

    def _pfwl_remove() -> None:
        if not _selected_folder:
            return
        sel = pfwl_list.curselection()
        if not sel:
            return
        item = pfwl_list.get(sel[0])
        cfg.remove_from_folder_whitelist(_selected_folder[0], item)
        pfwl_list.delete(sel[0])

    _btn(pfwl_btn, "+ Add", t, _pfwl_add, "accent", width=80).pack(side="left", padx=(0, 4))
    _btn(pfwl_btn, "- Remove", t, _pfwl_remove, "danger", width=80).pack(side="left")

    _label_trace_active = False

    def _refresh_empty_state() -> None:
        if watch_list.size() == 0:
            watch_empty.configure(
                text="No watched folders yet. Add one to get started.",
                text_color=t["muted"],
            )
        else:
            watch_empty.configure(text="")
        if not _selected_folder:
            dest_empty.configure(
                text="Select a watched folder to view destinations.",
                text_color=t["muted"],
            )
        elif dest_list.size() == 0:
            dest_empty.configure(
                text="No destinations for this watched folder yet.",
                text_color=t["muted"],
            )
        else:
            dest_empty.configure(text="")

    def _refresh_action_states() -> None:
        has_watch = bool(watch_list.curselection())
        has_selected_folder = bool(_selected_folder)
        has_dest = bool(dest_list.curselection())
        if watch_remove_btn is not None:
            watch_remove_btn.configure(state="normal" if has_watch else "disabled")
        if watch_open_btn is not None:
            watch_open_btn.configure(state="normal" if has_watch else "disabled")
        if dest_add_btn is not None:
            dest_add_btn.configure(state="normal" if has_selected_folder else "disabled")
        if dest_remove_btn is not None:
            dest_remove_btn.configure(state="normal" if has_selected_folder and has_dest else "disabled")
        if dest_open_btn is not None:
            dest_open_btn.configure(state="normal" if has_selected_folder and has_dest else "disabled")

    def _open_path(path: str) -> None:
        if not os.path.isdir(path):
            messagebox.showwarning("Folder not found", f"This folder is not available:\n{path}", parent=root)
            return
        try:
            if sys.platform == "win32":
                # Windows-specific function guarded by platform check.
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except OSError as exc:
            messagebox.showwarning("Could not open folder", str(exc), parent=root)

    def _on_label_write(*_: object) -> None:
        nonlocal _label_trace_active
        if _label_trace_active and _selected_folder:
            cfg.set_folder_label(_selected_folder[0], folder_label_var.get())

    folder_label_var.trace_add("write", _on_label_write)

    def _refresh_per_folder_details() -> None:
        nonlocal _label_trace_active
        _label_trace_active = False
        pfwl_list.delete(0, "end")
        if not _selected_folder:
            folder_label_var.set("")
            _label_trace_active = True
            return
        folder = _selected_folder[0]
        folder_label_var.set(cfg.get_folder_label(folder))
        for pat in cfg.get_folder_whitelist(folder):
            pfwl_list.insert("end", pat)
        _label_trace_active = True

    def _refresh_dests() -> None:
        dest_list.delete(0, "end")
        if not _selected_folder:
            _refresh_empty_state()
            _refresh_action_states()
            return
        for d in cfg.get_folder_destinations(_selected_folder[0]):
            dest_list.insert("end", d)
        _refresh_empty_state()
        _refresh_action_states()

    def _on_watch_select(_event: object = None) -> None:
        sel = watch_list.curselection()
        if not sel:
            return
        _selected_folder.clear()
        _selected_folder.append(watch_list.get(sel[0]))
        _refresh_dests()
        _refresh_per_folder_details()
        _refresh_action_states()

    watch_list.bind("<<ListboxSelect>>", _on_watch_select)
    dest_list.bind("<<ListboxSelect>>", lambda _event: _refresh_action_states())

    def _add_watch() -> None:
        folder = filedialog.askdirectory(title="Choose a folder to watch")
        if not folder:
            return
        if not os.path.isdir(folder):
            messagebox.showwarning("Invalid folder", "Please choose an existing folder.", parent=root)
            return
        if not os.access(folder, os.R_OK | os.X_OK):
            messagebox.showwarning(
                "Missing permissions",
                f"You do not have access to watch this folder:\n{folder}",
                parent=root,
            )
            return
        folder = os.path.abspath(folder)
        if folder in cfg.monitored_folders:
            messagebox.showinfo("Already watched", f"Already watching:\n{folder}", parent=root)
            return

        initial_dests: list[str] = []
        if messagebox.askyesno(
            "Add destinations now?",
            "Would you like to add destination folders for this watched folder now?",
            parent=root,
        ):
            picked = pick_destination_folders(folder, parent=root)
            for dest in picked:
                if dest == folder:
                    messagebox.showwarning(
                        "Destination matches source",
                        "A destination cannot be the same as the watched folder.",
                        parent=root,
                    )
                    continue
                if not os.path.isdir(dest):
                    messagebox.showwarning("Invalid destination", f"Destination does not exist:\n{dest}", parent=root)
                    continue
                if not os.access(dest, os.W_OK | os.X_OK):
                    messagebox.showwarning(
                        "Missing permissions",
                        f"You may not be able to move files into:\n{dest}",
                        parent=root,
                    )
                    continue
                if dest not in initial_dests:
                    initial_dests.append(dest)

        cfg.add_monitored_folder(folder, initial_dests)
        if on_folder_added is not None:
            on_folder_added(folder)
        watch_list.insert("end", folder)
        _refresh_empty_state()
        _refresh_action_states()
        dest_msg = f"Now watching:\n{folder}\n\n"
        if initial_dests:
            dest_msg += f"Initial destinations: {len(initial_dests)}"
        else:
            dest_msg += "No destinations yet (you can add them anytime)."
        messagebox.showinfo("Watched folder added", dest_msg, parent=root)

    def _remove_watch() -> None:
        sel = watch_list.curselection()
        if not sel:
            return
        folder = watch_list.get(sel[0])
        if messagebox.askyesno("Remove folder", f"Stop watching:\n{folder}?", parent=root):
            cfg.remove_monitored_folder(folder)
            if on_folder_removed is not None:
                on_folder_removed(folder)
            watch_list.delete(sel[0])
            _selected_folder.clear()
            dest_list.delete(0, "end")
            _refresh_empty_state()
            _refresh_action_states()
            messagebox.showinfo("Watched folder removed", f"Stopped watching:\n{folder}", parent=root)

    def _open_watch() -> None:
        sel = watch_list.curselection()
        if not sel:
            messagebox.showwarning("No folder selected", "Select a watched folder first.", parent=root)
            return
        _open_path(watch_list.get(sel[0]))

    watch_add_btn = _btn(wbtn, "Add watched folder", t, _add_watch, "accent", width=140)
    watch_add_btn.pack(side="left", padx=(0, 4))
    watch_remove_btn = _btn(wbtn, "Remove watched folder", t, _remove_watch, "danger", width=140)
    watch_remove_btn.pack(side="left", padx=(0, 4))
    watch_open_btn = _btn(wbtn, "Open watched folder", t, _open_watch, "normal", width=130)
    watch_open_btn.pack(side="left")

    def _add_dest() -> None:
        if not _selected_folder:
            messagebox.showwarning("No folder selected", "Select a watched folder first.", parent=root)
            return
        folder = _selected_folder[0]
        picked = pick_destination_folders(folder, parent=root)
        if not picked:
            return
        current = list(cfg.get_folder_destinations(folder))
        added_any = False
        added_count = 0
        for dest in picked:
            if not os.path.isdir(dest):
                messagebox.showwarning("Invalid destination", f"Destination does not exist:\n{dest}", parent=root)
                continue
            if dest == folder:
                messagebox.showwarning(
                    "Destination matches source",
                    "A destination cannot be the same as the watched folder.",
                    parent=root,
                )
                continue
            if not os.access(dest, os.W_OK | os.X_OK):
                messagebox.showwarning(
                    "Missing permissions",
                    f"You may not be able to move files into:\n{dest}",
                    parent=root,
                )
                continue
            if dest in current:
                continue
            current.append(dest)
            dest_list.insert("end", dest)
            added_any = True
            added_count += 1
        if not added_any:
            messagebox.showinfo(
                "Already added",
                "All selected folders are already destinations for this watched folder.",
                parent=root,
            )
            return
        cfg.set_destinations(folder, current)
        _refresh_empty_state()
        _refresh_action_states()
        messagebox.showinfo(
            "Destination added",
            f"Added {added_count} destination folder(s).",
            parent=root,
        )

    def _remove_dest() -> None:
        if not _selected_folder:
            return
        sel = dest_list.curselection()
        if not sel:
            return
        folder = _selected_folder[0]
        dest = dest_list.get(sel[0])
        if not messagebox.askyesno(
            "Remove destination",
            f"Remove destination from this watched folder?\n{dest}",
            parent=root,
        ):
            return
        current = list(cfg.get_folder_destinations(folder))
        if dest in current:
            current.remove(dest)
            cfg.set_destinations(folder, current)
        dest_list.delete(sel[0])
        _refresh_empty_state()
        _refresh_action_states()
        messagebox.showinfo("Destination removed", f"Removed destination:\n{dest}", parent=root)

    def _open_dest() -> None:
        sel = dest_list.curselection()
        if not sel:
            messagebox.showwarning("No destination selected", "Select a destination first.", parent=root)
            return
        _open_path(dest_list.get(sel[0]))

    dest_add_btn = _btn(dbtn, "Add destination", t, _add_dest, "accent", width=130)
    dest_add_btn.pack(side="left", padx=(0, 4))
    dest_remove_btn = _btn(dbtn, "Remove destination", t, _remove_dest, "danger", width=130)
    dest_remove_btn.pack(side="left", padx=(0, 4))
    dest_open_btn = _btn(dbtn, "Open destination", t, _open_dest, "normal", width=130)
    dest_open_btn.pack(side="left")

    # Quick-Add options
    sep = ctk.CTkFrame(f, fg_color=t["btn_bg"], height=1)
    sep.grid(row=3, column=0, columnspan=3, sticky="ew", padx=8, pady=6)

    qa_frame = ctk.CTkFrame(f, fg_color="transparent")
    qa_frame.grid(row=4, column=0, columnspan=3, sticky="w", padx=8)

    _section_lbl(qa_frame, "Quick-Add Folder Options", t).pack(anchor="w", pady=(4, 4))
    _lbl(qa_frame, "When a new folder is added via the sort prompt:", t, size=9).pack(anchor="w")

    qa_inherit = tk.BooleanVar(value=cfg.get_setting("quick_add_inherit_destinations", True))
    qa_whitelist = tk.BooleanVar(value=cfg.get_setting("quick_add_auto_whitelist", True))
    qa_watch = tk.BooleanVar(value=cfg.get_setting("quick_add_auto_start_watch", True))

    _check(qa_frame, "Inherit parent destinations (skip picker)", qa_inherit, t).pack(anchor="w", pady=2)
    _check(qa_frame, "Auto-whitelist new folder name", qa_whitelist, t).pack(anchor="w", pady=2)
    _check(qa_frame, "Start watching immediately", qa_watch, t).pack(anchor="w", pady=2)

    _refresh_empty_state()
    _refresh_action_states()

    return {
        "quick_add_inherit_destinations": qa_inherit,
        "quick_add_auto_whitelist": qa_whitelist,
        "quick_add_auto_start_watch": qa_watch,
    }


def _build_rules_tab(
    tabview: ctk.CTkTabview,
    cfg: "Config",
    t: dict,
    root: ctk.CTk,
    on_open_sorting_rules: Callable[[], None] | None = None,
) -> None:
    f = tabview.tab("Rules")

    # Whitelist
    _section_lbl(f, "Whitelist (never sort these)", t).pack(anchor="w", padx=8, pady=(10, 2))
    _lbl(f, "Files matching these patterns are silently skipped (glob, e.g. *.log).", t, size=9).pack(
        anchor="w", padx=8)

    wl_list = _tk_listbox(f, t, height=4)
    wl_list.pack(fill="x", padx=8, pady=2)
    for pat in cfg.get_whitelist():
        wl_list.insert("end", pat)

    def _add_wl() -> None:
        dlg = ctk.CTkToplevel(root)
        dlg.title("Add Whitelist Pattern")
        dlg.geometry("320x130")
        dlg.attributes("-topmost", True)
        dlg.grab_set()
        _lbl(dlg, "Pattern (e.g. *.log):", t).pack(pady=(14, 4))
        entry = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=10), border_color=t["accent"])
        entry.pack(padx=16, fill="x")
        def _ok() -> None:
            p = entry.get().strip()
            if p:
                cfg.add_to_whitelist(p)
                wl_list.insert("end", p)
            dlg.destroy()
        _btn(dlg, "Add", t, _ok, "accent").pack(pady=10)

    def _rm_wl() -> None:
        sel = wl_list.curselection()
        if sel:
            p = wl_list.get(sel[0])
            cfg.remove_from_whitelist(p)
            wl_list.delete(sel[0])

    wl_btns = ctk.CTkFrame(f, fg_color="transparent")
    wl_btns.pack(anchor="w", padx=8, pady=2)
    _btn(wl_btns, "+ Add", t, _add_wl, "accent", width=80).pack(side="left", padx=(0, 4))
    _btn(wl_btns, "- Remove", t, _rm_wl, "danger", width=80).pack(side="left")

    # Ignore patterns
    _section_lbl(f, "Ignore Patterns (watcher skips these)", t).pack(anchor="w", padx=8, pady=(10, 2))
    _lbl(f, "Files matching these patterns are not detected at all (glob, e.g. ~$*).", t, size=9).pack(
        anchor="w", padx=8)

    ig_list = _tk_listbox(f, t, height=4)
    ig_list.pack(fill="x", padx=8, pady=2)
    for pat in cfg.ignore_patterns:
        ig_list.insert("end", pat)

    def _add_ig() -> None:
        dlg = ctk.CTkToplevel(root)
        dlg.title("Add Ignore Pattern")
        dlg.geometry("320x130")
        dlg.attributes("-topmost", True)
        dlg.grab_set()
        _lbl(dlg, "Pattern (e.g. *.tmp):", t).pack(pady=(14, 4))
        entry = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=10), border_color=t["accent"])
        entry.pack(padx=16, fill="x")
        def _ok() -> None:
            p = entry.get().strip()
            if p:
                cfg.add_ignore_pattern(p)
                ig_list.insert("end", p)
            dlg.destroy()
        _btn(dlg, "Add", t, _ok, "accent").pack(pady=10)

    def _rm_ig() -> None:
        sel = ig_list.curselection()
        if sel:
            p = ig_list.get(sel[0])
            cfg.remove_ignore_pattern(p)
            ig_list.delete(sel[0])

    ig_btns = ctk.CTkFrame(f, fg_color="transparent")
    ig_btns.pack(anchor="w", padx=8, pady=2)
    _btn(ig_btns, "+ Add", t, _add_ig, "accent", width=80).pack(side="left", padx=(0, 4))
    _btn(ig_btns, "- Remove", t, _rm_ig, "danger", width=80).pack(side="left")

    # Rename patterns
    _section_lbl(f, "Rename Patterns (auto-rename on move)", t).pack(anchor="w", padx=8, pady=(10, 2))
    _lbl(f, 'Tokens: {name} {ext} {date}   e.g. ".pdf" → "{date}_{name}{ext}"', t, size=9).pack(
        anchor="w", padx=8)

    rp_list = _tk_listbox(f, t, height=4)
    rp_list.pack(fill="x", padx=8, pady=2)

    def _fmt_rp(entry: dict) -> str:
        exts = ", ".join(entry.get("extensions", []))
        pat = entry.get("pattern", "")
        enabled = "" if entry.get("enabled", True) else " [disabled]"
        return f"{exts} → {pat}{enabled}"

    for rp in cfg.rename_patterns:
        rp_list.insert("end", _fmt_rp(rp))

    def _add_rp() -> None:
        dlg = ctk.CTkToplevel(root)
        dlg.title("Add Rename Pattern")
        dlg.geometry("400x200")
        dlg.attributes("-topmost", True)
        dlg.grab_set()

        _lbl(dlg, "Extensions (e.g. .pdf .doc):", t).pack(pady=(14, 2), anchor="w", padx=16)
        ext_entry = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=10), border_color=t["accent"])
        ext_entry.pack(padx=16, fill="x")
        _lbl(dlg, "Pattern (e.g. {date}_{name}{ext}):", t).pack(pady=(10, 2), anchor="w", padx=16)
        pat_entry = ctk.CTkEntry(dlg, font=ctk.CTkFont(size=10), border_color=t["accent"])
        pat_entry.pack(padx=16, fill="x")

        def _ok() -> None:
            raw_exts = ext_entry.get().strip()
            pat = pat_entry.get().strip()
            if not raw_exts or not pat:
                dlg.destroy()
                return
            exts = [e if e.startswith(".") else f".{e}" for e in raw_exts.split() if e]
            rp_entry = {"extensions": exts, "pattern": pat, "enabled": True}
            cfg.rename_patterns.append(rp_entry)
            cfg.save()
            rp_list.insert("end", _fmt_rp(rp_entry))
            dlg.destroy()

        _btn(dlg, "Add", t, _ok, "accent").pack(pady=12)

    def _rm_rp() -> None:
        sel = rp_list.curselection()
        if not sel:
            return
        idx = sel[0]
        patterns = cfg.rename_patterns
        if idx < len(patterns):
            del patterns[idx]
            cfg.save()
        rp_list.delete(idx)

    def _toggle_rp() -> None:
        sel = rp_list.curselection()
        if not sel:
            return
        idx = sel[0]
        patterns = cfg.rename_patterns
        if idx < len(patterns):
            patterns[idx]["enabled"] = not patterns[idx].get("enabled", True)
            cfg.save()
            rp_list.delete(idx)
            rp_list.insert(idx, _fmt_rp(patterns[idx]))

    rp_btns = ctk.CTkFrame(f, fg_color="transparent")
    rp_btns.pack(anchor="w", padx=8, pady=2)
    _btn(rp_btns, "+ Add", t, _add_rp, "accent", width=80).pack(side="left", padx=(0, 4))
    _btn(rp_btns, "- Remove", t, _rm_rp, "danger", width=80).pack(side="left", padx=(0, 4))
    _btn(rp_btns, "Enable/Disable", t, _toggle_rp, "normal", width=110).pack(side="left")

    if on_open_sorting_rules is not None:
        ctk.CTkFrame(f, fg_color=t["btn_bg"], height=1).pack(fill="x", padx=8, pady=(10, 8))
        sorting_rules_frame = ctk.CTkFrame(f, fg_color="transparent")
        sorting_rules_frame.pack(fill="x", padx=8, pady=(0, 4))
        _section_lbl(sorting_rules_frame, "Sorting Rules", t).pack(anchor="w")
        _lbl(
            sorting_rules_frame,
            "Open the connected sorting-rules manager (extension and pattern destinations).",
            t,
            size=9,
        ).pack(anchor="w", pady=(0, 4))
        _btn(
            sorting_rules_frame,
            "Open Sorting Rules Manager",
            t,
            on_open_sorting_rules,
            "accent",
            width=210,
        ).pack(anchor="w")


def _build_system_tab(
    tabview: ctk.CTkTabview,
    cfg: "Config",
    t: dict,
    root: ctk.CTk,
    on_delete_user_data: Callable[[], None] | None = None,
) -> dict:
    f = tabview.tab("System")
    row = 0

    _section_lbl(f, "Startup", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                        padx=8, pady=(12, 4))
    row += 1
    _lbl(f, "Start on login:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    autostart_var = tk.BooleanVar(value=is_autostart_enabled())
    _check(f, "Enabled", autostart_var, t).grid(row=row, column=1, sticky="w",
                                                  padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Batch Processing", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                                  padx=8, pady=(12, 4))
    row += 1
    _lbl(f, "Batch mode style:", t).grid(row=row, column=0, sticky="w", padx=8, pady=3)
    batch_var = tk.StringVar(value=cfg.get_setting("batch_mode_style", "batch-list"))
    ctk.CTkOptionMenu(f, variable=batch_var, values=["one-by-one", "batch-list"],
                      font=ctk.CTkFont(size=10)).grid(row=row, column=1, sticky="ew",
                                                       padx=(0, 8), pady=3)
    row += 1

    _section_lbl(f, "Config Backup", t).grid(row=row, column=0, columnspan=2, sticky="w",
                                              padx=8, pady=(12, 4))
    row += 1

    io_frame = ctk.CTkFrame(f, fg_color="transparent")
    io_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=4)
    row += 1

    def _export() -> None:
        path = filedialog.asksaveasfilename(
            title="Export Config", defaultextension=".zip",
            filetypes=[("Zip files", "*.zip")],
        )
        if path:
            cfg.export_config(path)
            messagebox.showinfo("Export", "Config exported successfully.", parent=root)

    def _import() -> None:
        path = filedialog.askopenfilename(
            title="Import Config", filetypes=[("Zip files", "*.zip")],
        )
        if path:
            try:
                cfg.import_config(path)
            except Exception as exc:
                messagebox.showerror(
                    "Import failed",
                    f"Could not import config:\n\n{exc}",
                    parent=root,
                )
                return
            messagebox.showinfo(
                "Import", "Config imported. Restart Iconic File Filer to apply.", parent=root
            )

    _btn(io_frame, "Export Config…", t, _export, "normal").pack(side="left", padx=(0, 6))
    _btn(io_frame, "Import Config…", t, _import, "normal").pack(side="left")

    if on_delete_user_data is not None:
        _section_lbl(f, "Danger Zone", t).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(14, 4)
        )
        row += 1
        _lbl(
            f,
            "Delete all user data (watched folders config, rules, history, achievements, logs).",
            t,
            size=9,
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 3))
        row += 1

        def _delete_all_data() -> None:
            if not messagebox.askyesno(
                "Delete all user data?",
                "This will permanently delete all Iconic File Filer user data.\n\nContinue?",
                parent=root,
            ):
                return
            if not messagebox.askyesno(
                "Final confirmation",
                "This cannot be undone. Delete all user data now and quit the app?",
                parent=root,
            ):
                return
            on_delete_user_data()
            root.destroy()

        _btn(
            f,
            "Delete all user data…",
            t,
            _delete_all_data,
            "danger",
            width=200,
        ).grid(row=row, column=0, sticky="w", padx=8, pady=(0, 6))
        row += 1

    f.grid_columnconfigure(1, weight=1)
    return {
        "autostart": autostart_var,
        "batch_mode_style": batch_var,
    }


# ── Main dialog ───────────────────────────────────────────────────────

class SettingsDialog:
    """Tabbed modal settings window."""

    def __init__(
        self,
        config: "Config",
        initial_tab: str = "General",
        on_open_sorting_rules: Callable[[], None] | None = None,
        on_rescan: Callable[[], None] | None = None,
        on_folder_added: Callable[[str], None] | None = None,
        on_folder_removed: Callable[[str], None] | None = None,
        on_delete_user_data: Callable[[], None] | None = None,
    ) -> None:
        self._config = config
        self._theme_name = config.get_setting("theme", "dark")
        self._theme = get_theme(self._theme_name)
        self._initial_tab = initial_tab
        self._on_open_sorting_rules = on_open_sorting_rules
        self._on_rescan = on_rescan
        self._on_folder_added = on_folder_added
        self._on_folder_removed = on_folder_removed
        self._on_delete_user_data = on_delete_user_data

    def show(self) -> None:
        """Display the settings dialog (blocks until closed)."""
        t = self._theme
        cfg = self._config
        apply_ctk_appearance(self._theme_name)

        root = ctk.CTk()
        root.title("Iconic File Filer — Settings")
        root.resizable(True, True)
        root.minsize(560, 560)

        w, h = 640, 660
        sx = root.winfo_screenwidth() // 2 - w // 2
        sy = root.winfo_screenheight() // 2 - h // 2
        root.geometry(f"{w}x{h}+{sx}+{sy}")

        ctk.CTkLabel(
            root,
            text="⚙ Settings",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=t["accent"],
        ).pack(pady=(16, 4))

        tabview = ctk.CTkTabview(root, corner_radius=10)
        tabview.pack(fill="both", expand=True, padx=16, pady=(4, 4))

        for tab_name in SETTINGS_TABS:
            tabview.add(tab_name)

        gen_vars = _build_general_tab(tabview, cfg, t)
        mon_vars = _build_monitoring_tab(
            tabview,
            cfg,
            t,
            on_rescan=self._on_rescan,
        )
        folders_vars = _build_folders_tab(
            tabview,
            cfg,
            t,
            root,
            on_folder_added=self._on_folder_added,
            on_folder_removed=self._on_folder_removed,
        )
        _build_rules_tab(
            tabview,
            cfg,
            t,
            root,
            on_open_sorting_rules=self._on_open_sorting_rules,
        )
        sys_vars = _build_system_tab(
            tabview,
            cfg,
            t,
            root,
            on_delete_user_data=self._on_delete_user_data,
        )
        if self._initial_tab in SETTINGS_TABS:
            tabview.set(self._initial_tab)

        # Save / Cancel
        def _save() -> None:
            settings: dict = {}
            for key, var in gen_vars.items():
                settings[key] = var.get()
            for key, var in mon_vars.items():
                settings[key] = var.get()
            for key, var in folders_vars.items():
                settings[key] = var.get()
            settings["batch_mode_style"] = sys_vars["batch_mode_style"].get()
            cfg.save_many(settings)
            set_autostart(sys_vars["autostart"].get())
            logger.info("Settings saved.")
            root.destroy()

        btn_row = ctk.CTkFrame(root, fg_color="transparent")
        btn_row.pack(pady=10)
        _btn(btn_row, "Save", t, _save, "accent", width=110).pack(side="left", padx=8)
        _btn(btn_row, "Cancel", t, root.destroy, "normal", width=110).pack(side="left", padx=8)

        root.mainloop()
