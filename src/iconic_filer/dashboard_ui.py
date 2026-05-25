"""Extracted dashboard and pending-list windows for Iconic File Filer."""

from __future__ import annotations

import logging
import shutil
import os
import sqlite3
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

import customtkinter as ctk

from iconic_filer.notifications import notify
from iconic_filer.themes import apply_ctk_appearance, get_theme

logger = logging.getLogger(__name__)

# ── Colour palette used only for the Canvas-drawn heatmap ────────────
_HEATMAP_COLORS = {
    "none": "#2a2a3e",
    "low": "#2d6a2d",
    "mid": "#3fa53f",
    "high": "#a6e3a1",
}


def show_dashboard(
    config: Any,
    history: Any,
    batch_queue: list[str],
    lock: threading.Lock,
    watcher: Any,
    theme_name: str,
    on_rescan: Callable[[], None] | None = None,
) -> None:
    """Open the activity window (blocks until closed)."""
    theme = get_theme(theme_name)
    apply_ctk_appearance(theme_name)

    root = ctk.CTk()
    root.title("Iconic File Filer — Activity")
    root.geometry("600x680")

    body = ctk.CTkScrollableFrame(root)
    body.pack(fill="both", expand=True)

    # ── Header ────────────────────────────────────────────────────────
    ctk.CTkLabel(
        body,
        text="📊 Activity & Queue",
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=theme["accent"],
    ).pack(pady=(20, 4))

    # ── Pending files notice ──────────────────────────────────────────
    with lock:
        pending = sum(1 for p in batch_queue if os.path.exists(p))
    if pending:
        ctk.CTkLabel(
            body,
            text=f"⏳ {pending} file(s) pending (focus mode)",
            font=ctk.CTkFont(size=11),
            text_color=theme["danger"],
        ).pack(pady=4)
        ctk.CTkLabel(
            body,
            text="Next step: use the tray menu and open the pending file list.",
            font=ctk.CTkFont(size=10),
            text_color=theme["muted"],
        ).pack(pady=(0, 4))

    if on_rescan is not None:
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=(2, 6))
        ctk.CTkButton(
            actions,
            text="Rescan watched folders now",
            fg_color=theme["accent"],
            text_color="#1e1e2e",
            hover_color=theme["btn_active"],
            font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=8,
            height=30,
            command=on_rescan,
        ).pack(anchor="w")

    # ── Sorting stats ─────────────────────────────────────────────────
    total = history.total_count()
    today = history.count_since(time.time() - 86400)
    week = history.count_since(time.time() - 7 * 86400)

    stats_frame = ctk.CTkFrame(body, corner_radius=10)
    stats_frame.pack(fill="x", padx=24, pady=8)
    stats_inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
    stats_inner.pack(padx=16, pady=12)

    for label_text, value in [("Total sorted", total), ("Today", today), ("This week", week)]:
        col = ctk.CTkFrame(stats_inner, fg_color="transparent")
        col.pack(side="left", padx=20)
        ctk.CTkLabel(col, text=str(value), font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=theme["accent"]).pack()
        ctk.CTkLabel(col, text=label_text, font=ctk.CTkFont(size=10),
                     text_color=theme["muted"]).pack()

    # ── Taxonomy stats ────────────────────────────────────────────────
    try:
        rows = history.all_moves()
        ext_counts: dict[str, int] = {}
        dest_counts: dict[str, int] = {}
        for src_path, dst_path in rows:
            _, ext = os.path.splitext(src_path)
            if ext:
                ext_lower = ext.lower()
                ext_counts[ext_lower] = ext_counts.get(ext_lower, 0) + 1
            dest_name = os.path.basename(os.path.dirname(dst_path))
            if dest_name:
                dest_counts[dest_name] = dest_counts.get(dest_name, 0) + 1

        tax_frame = ctk.CTkFrame(body, corner_radius=10)
        tax_frame.pack(fill="x", padx=24, pady=4)
        tax_inner = ctk.CTkFrame(tax_frame, fg_color="transparent")
        tax_inner.pack(padx=16, pady=8, fill="x")

        if ext_counts:
            top_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            ext_str = "   ".join(f"{e} ×{c}" for e, c in top_exts)
            row_f = ctk.CTkFrame(tax_inner, fg_color="transparent")
            row_f.pack(anchor="w", pady=2)
            ctk.CTkLabel(row_f, text="Top file types: ", font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=theme["accent"]).pack(side="left")
            ctk.CTkLabel(row_f, text=ext_str, font=ctk.CTkFont(size=10)).pack(side="left")

        if dest_counts:
            top_dests = sorted(dest_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            dest_str = "   ".join(f"{d} ×{c}" for d, c in top_dests)
            row_f2 = ctk.CTkFrame(tax_inner, fg_color="transparent")
            row_f2.pack(anchor="w", pady=2)
            ctk.CTkLabel(row_f2, text="Top destinations: ", font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=theme["accent"]).pack(side="left")
            ctk.CTkLabel(row_f2, text=dest_str, font=ctk.CTkFont(size=10)).pack(side="left")
    except (sqlite3.Error, OSError, AttributeError):
        logger.debug("Taxonomy stats unavailable", exc_info=True)

    # ── Inbox Zero progress bar ───────────────────────────────────────
    if pending > 0 or today > 0:
        progress_frame = ctk.CTkFrame(body, fg_color="transparent")
        progress_frame.pack(fill="x", padx=24, pady=4)
        processed = today - pending if today > pending else today
        ratio = max(0.0, min(1.0, processed / max(today, 1)))
        ctk.CTkLabel(
            progress_frame,
            text=f"Inbox Zero: {int(ratio * 100)}%",
            font=ctk.CTkFont(size=10),
            text_color=theme["success"],
        ).pack(anchor="w")
        pbar = ctk.CTkProgressBar(progress_frame, width=540, progress_color=theme["success"])
        pbar.set(ratio)
        pbar.pack(anchor="w", pady=(2, 0))

    # ── Activity heatmap (last 84 days = 12 weeks) ────────────────────
    heatmap_frame = ctk.CTkFrame(body, corner_radius=10)
    heatmap_frame.pack(fill="x", padx=24, pady=8)
    ctk.CTkLabel(
        heatmap_frame, text="Activity — last 12 weeks",
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=theme["accent"],
    ).pack(anchor="w", padx=16, pady=(10, 4))

    day_counts: dict[int, int] = {}
    try:
        for timestamp in history.all_timestamps():
            day = int(timestamp // 86400)
            day_counts[day] = day_counts.get(day, 0) + 1
    except Exception:
        pass

    cell_size = 13
    gap = 2
    weeks = 12
    days_per_week = 7
    hm_w = cell_size * weeks + gap * (weeks - 1) + 4
    hm_h = cell_size * days_per_week + gap * (days_per_week - 1)
    hm_canvas = tk.Canvas(
        heatmap_frame, width=hm_w, height=hm_h,
        bg=theme["bg"], highlightthickness=0,
    )
    hm_canvas.pack(anchor="w", padx=16, pady=(0, 10))

    today_day = int(time.time() // 86400)
    total_cells = weeks * days_per_week
    for cell_idx in range(total_cells):
        day_offset = total_cells - 1 - cell_idx
        day_key = today_day - day_offset
        count = day_counts.get(day_key, 0)
        col = cell_idx // days_per_week
        row = cell_idx % days_per_week
        x0 = col * (cell_size + gap)
        y0 = row * (cell_size + gap)
        x1 = x0 + cell_size
        y1 = y0 + cell_size
        if count == 0:
            color = _HEATMAP_COLORS["none"]
        elif count <= 2:
            color = _HEATMAP_COLORS["low"]
        elif count <= 5:
            color = _HEATMAP_COLORS["mid"]
        else:
            color = _HEATMAP_COLORS["high"]
        hm_canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline="")

    # ── Achievements ──────────────────────────────────────────────────
    try:
        from iconic_filer.achievements import Achievements

        ach_db = os.path.join(os.path.dirname(config.path), "achievements.db")
        achs = Achievements(ach_db)
        all_achs = achs.all_status()
        achs.close()

        ach_frame = ctk.CTkFrame(body, corner_radius=10)
        ach_frame.pack(fill="x", padx=24, pady=4)
        ctk.CTkLabel(
            ach_frame, text="🏆 Achievements",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=theme["accent"],
        ).pack(anchor="w", padx=16, pady=(10, 4))

        ach_list = ctk.CTkScrollableFrame(ach_frame, height=140, fg_color="transparent")
        ach_list.pack(padx=16, pady=(0, 10), fill="x")
        for ach in all_achs:
            color = theme["success"] if ach.unlocked else theme["muted"]
            row = ctk.CTkFrame(ach_list, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=f"{ach.emoji} {ach.name}",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                row,
                text=ach.description,
                font=ctk.CTkFont(size=9),
                text_color=theme["muted"],
                anchor="w",
                justify="left",
                wraplength=520,
            ).pack(anchor="w")
    except Exception:
        logger.debug("Achievements panel unavailable", exc_info=True)

    # ── Rules summary ─────────────────────────────────────────────────
    rules_count = 0
    try:
        from iconic_filer.rules import Rules

        rules_path = os.path.join(os.path.dirname(config.path), "rules.json")
        if os.path.exists(rules_path):
            tmp_rules = Rules(rules_path)
            rules_count = len(tmp_rules.extension_map)
    except (OSError, AttributeError):
        pass

    ctk.CTkLabel(
        body,
        text=f"Active rules: {rules_count}",
        font=ctk.CTkFont(size=10),
    ).pack(padx=24, anchor="w", pady=(4, 4))

    # ── Undo history ──────────────────────────────────────────────────
    ctk.CTkLabel(
        body,
        text="Recent Actions (select to undo back to that point):",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=theme["accent"],
    ).pack(pady=(8, 4), padx=24, anchor="w")

    history_frame = ctk.CTkFrame(body, fg_color="transparent")
    history_frame.pack(fill="both", expand=True, padx=24, pady=4)

    # Use tk.Listbox (no CTk equivalent) styled to match the theme
    scrollbar = tk.Scrollbar(history_frame)
    scrollbar.pack(side="right", fill="y")

    history_list = tk.Listbox(
        history_frame,
        bg=theme["list_bg"], fg=theme["list_fg"],
        selectbackground=theme["list_select_bg"],
        selectforeground=theme["list_select_fg"],
        font=("TkDefaultFont", 9), relief="flat",
        yscrollcommand=scrollbar.set,
    )
    history_list.pack(fill="both", expand=True)
    scrollbar.config(command=history_list.yview)

    recent = history.recent(50)
    for action in recent:
        status = "[undone]" if action["undone"] else "[done]"
        src_name = os.path.basename(action["src_path"])
        dst_name = os.path.basename(os.path.dirname(action["dst_path"]))
        history_list.insert("end", f"{status}  {src_name}  →  {dst_name}")

    def _undo_to_selected() -> None:
        sel = history_list.curselection()
        if not sel:
            return
        idx = sel[0]
        actions_to_undo = recent[: idx + 1]
        undone_count = 0
        for action in actions_to_undo:
            if not action["undone"]:
                result = history.undo_by_id(action["id"])
                if result:
                    watcher.mark_self_moved(result[1])
                    undone_count += 1
        if undone_count:
            logger.info("Bulk undone %d action(s).", undone_count)
        history_list.delete(0, "end")
        for action in history.recent(50):
            status = "[undone]" if action["undone"] else "[done]"
            src_name = os.path.basename(action["src_path"])
            dst_name = os.path.basename(os.path.dirname(action["dst_path"]))
            history_list.insert("end", f"{status}  {src_name}  →  {dst_name}")

    btn_frame = ctk.CTkFrame(body, fg_color="transparent")
    btn_frame.pack(pady=10)
    ctk.CTkButton(
        btn_frame, text="Undo to selected",
        fg_color=theme["accent"], text_color="#1e1e2e",
        hover_color=theme["btn_active"],
        font=ctk.CTkFont(size=10, weight="bold"),
        corner_radius=8,
        command=_undo_to_selected,
    ).pack(side="left", padx=6)
    ctk.CTkButton(
        btn_frame, text="Close",
        fg_color=theme["btn_bg"], text_color=theme["btn_fg"],
        hover_color=theme["muted"],
        font=ctk.CTkFont(size=10),
        corner_radius=8,
        command=root.destroy,
    ).pack(side="left", padx=6)

    root.mainloop()


def show_batch_list(
    config: Any,
    rules: Any,
    watcher: Any,
    queue: list[str],
    theme_name: str,
    move_file_fn: Callable[[str, str], None],
    on_whitelist: Callable[[str], None] | None = None,
    on_snooze: Callable[[str], None] | None = None,
    on_defer: Callable[[list[str]], None] | None = None,
) -> None:
    """Show a batch processing window listing all pending files."""
    theme = get_theme(theme_name)
    apply_ctk_appearance(theme_name)

    root = ctk.CTk()
    root.title("Iconic File Filer — Batch Processing")
    root.geometry("640x480")

    ctk.CTkLabel(
        root,
        text=(
            f"Detected files: {len(queue)} pending "
            f"{'action' if len(queue) == 1 else 'actions'}"
        ),
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color=theme["accent"],
    ).pack(pady=(20, 10))
    ctk.CTkLabel(
        root,
        text=(
            "This is the batch sorting window. New items detected while this window is open "
            "stay queued in the tray and appear in the next batch."
        ),
        font=ctk.CTkFont(size=10),
        text_color=theme["muted"],
        wraplength=560,
        justify="center",
    ).pack(pady=(0, 4))
    ctk.CTkLabel(
        root,
        text=(
            "Tip: For the step-by-step sorting prompt, open Settings → System and set "
            'Pending review style to "one-by-one".'
        ),
        font=ctk.CTkFont(size=10),
        text_color=theme["muted"],
        wraplength=560,
        justify="center",
    ).pack(pady=(0, 10))

    scroll = ctk.CTkScrollableFrame(root, height=330)
    scroll.pack(fill="x", padx=24, pady=4)
    scroll.grid_columnconfigure(0, weight=3)
    scroll.grid_columnconfigure(1, weight=2)
    scroll.grid_columnconfigure(2, weight=1)

    all_dests: list[str] = []
    for folder in config.monitored_folders:
        for d in config.get_folder_destinations(folder):
            if d not in all_dests:
                all_dests.append(d)

    if not all_dests:
        ctk.CTkLabel(
            scroll,
            text="No destinations configured. Add folders in Settings.",
            text_color=theme["danger"],
        ).pack(pady=8)

    ctk.CTkLabel(
        scroll,
        text="File",
        text_color=theme["muted"],
        anchor="w",
    ).grid(row=0, column=0, sticky="w", pady=(0, 4))
    ctk.CTkLabel(
        scroll,
        text="Destination",
        text_color=theme["muted"],
        anchor="w",
    ).grid(row=0, column=1, sticky="w", pady=(0, 4))
    ctk.CTkLabel(
        scroll,
        text="Action",
        text_color=theme["muted"],
        anchor="w",
    ).grid(row=0, column=2, sticky="w", pady=(0, 4))

    rows: list[tuple[str, tk.StringVar, tk.StringVar]] = []
    for row_idx, filepath in enumerate(queue):
        if not os.path.exists(filepath):
            continue
        ui_row = row_idx + 1
        ctk.CTkLabel(
            scroll,
            text=os.path.basename(filepath),
            font=ctk.CTkFont(size=10),
            anchor="w",
        ).grid(row=ui_row, column=0, sticky="ew", pady=3, padx=(4, 8))

        dest_var = tk.StringVar(value=all_dests[0] if all_dests else "")
        if all_dests:
            ctk.CTkOptionMenu(
                scroll,
                variable=dest_var,
                values=all_dests,
                font=ctk.CTkFont(size=10),
            ).grid(row=ui_row, column=1, sticky="ew", pady=3)
        else:
            ctk.CTkLabel(
                scroll,
                text="(none)",
                text_color=theme["muted"],
            ).grid(row=ui_row, column=1, sticky="w", pady=3)

        action_var = tk.StringVar(value="Move")
        ctk.CTkOptionMenu(
            scroll,
            variable=action_var,
            values=["Move", "Skip", "Whitelist", "Snooze"],
            font=ctk.CTkFont(size=10),
            width=110,
        ).grid(row=ui_row, column=2, sticky="ew", pady=3, padx=(8, 0))
        rows.append((filepath, dest_var, action_var))

    status_var = tk.StringVar(
        value="Select destinations and actions, then click Apply actions."
    )
    ctk.CTkLabel(
        root,
        textvariable=status_var,
        font=ctk.CTkFont(size=10),
        text_color=theme["muted"],
        wraplength=560,
        justify="center",
    ).pack(pady=(8, 2))

    def _apply_actions() -> None:
        if not rows:
            messagebox.showinfo(
                "Nothing to process",
                "There are no files left in this batch.",
                parent=root,
            )
            root.destroy()
            return
        apply_btn.configure(state="disabled")
        later_btn.configure(state="disabled")
        status_var.set("Applying actions...")
        root.update_idletasks()
        counters = {"moved": 0, "whitelisted": 0, "snoozed": 0, "skipped": 0}
        errors = 0
        for filepath, dest_var, action_var in rows:
            if not os.path.exists(filepath):
                counters["skipped"] += 1
                continue
            action = action_var.get()
            try:
                if action == "Move":
                    dest = dest_var.get()
                    if dest:
                        move_file_fn(filepath, dest)
                        rules.record_action(filepath, dest)
                        counters["moved"] += 1
                    else:
                        counters["skipped"] += 1
                elif action == "Whitelist":
                    if on_whitelist is not None:
                        on_whitelist(os.path.basename(filepath))
                    counters["whitelisted"] += 1
                elif action == "Snooze":
                    if on_snooze is not None:
                        on_snooze(filepath)
                    counters["snoozed"] += 1
                else:
                    counters["skipped"] += 1
            except (OSError, shutil.Error, RuntimeError, ValueError) as exc:
                errors += 1
                counters["skipped"] += 1
                logger.error(
                    "Batch action failed for %s: %s",
                    filepath,
                    exc,
                    exc_info=True,
                )
        summary = (
            f"Moved {counters['moved']}, "
            f"whitelisted {counters['whitelisted']}, "
            f"snoozed {counters['snoozed']}, "
            f"skipped {counters['skipped']}"
        )
        if errors:
            summary = f"{summary}, errors {errors}"
        status_var.set(f"Batch complete. {summary}.")
        root.update_idletasks()
        logger.info(
            "Batch applied: moved=%d, whitelisted=%d, snoozed=%d, skipped=%d, errors=%d",
            counters["moved"],
            counters["whitelisted"],
            counters["snoozed"],
            counters["skipped"],
            errors,
        )
        if config.get_setting("native_notifications", True):
            fallback = config.get_setting("notification_fallback", "log-only")
            notify(
                "Batch actions applied",
                summary,
                fallback_strategy=fallback,
            )
        total_actions = (
            counters["moved"] + counters["whitelisted"] + counters["snoozed"]
        )
        if errors:
            messagebox.showwarning(
                "Batch completed with errors",
                f"{summary}.\n\nSome actions failed. Check the log for details.",
                parent=root,
            )
        elif total_actions == 0:
            messagebox.showwarning(
                "No actions applied",
                "No actions were applied. Check that destinations are set and files still exist.",
                parent=root,
            )
        root.destroy()

    def _later() -> None:
        if on_defer is not None:
            on_defer([path for path, _, _ in rows if os.path.exists(path)])
        root.destroy()

    btn_frame = ctk.CTkFrame(root, fg_color="transparent")
    btn_frame.pack(pady=12)
    apply_btn = ctk.CTkButton(
        btn_frame, text="Apply actions",
        fg_color=theme["accent"], text_color="#1e1e2e",
        hover_color=theme["btn_active"],
        font=ctk.CTkFont(size=11, weight="bold"),
        corner_radius=8,
        command=_apply_actions,
    )
    apply_btn.pack(side="left", padx=6)
    later_btn = ctk.CTkButton(
        btn_frame, text="Later",
        fg_color=theme["btn_bg"], text_color=theme["btn_fg"],
        hover_color=theme["muted"],
        font=ctk.CTkFont(size=11),
        corner_radius=8,
        command=_later,
    )
    later_btn.pack(side="left", padx=6)

    root.mainloop()


def show_file_list(
    queue: list[str],
    theme_name: str,
    on_process: Callable[[list[str]], None],
    on_defer: Callable[[list[str]], None] | None = None,
) -> None:
    """Show a sortable, filterable list of pending files."""
    theme = get_theme(theme_name)
    apply_ctk_appearance(theme_name)

    root = ctk.CTk()
    root.title("Iconic File Filer — File List")
    root.geometry("760x520")
    root.minsize(640, 420)

    ctk.CTkLabel(
        root,
        text="🗂 Pending Files",
        font=ctk.CTkFont(size=18, weight="bold"),
        text_color=theme["accent"],
    ).pack(pady=(18, 4))
    ctk.CTkLabel(
        root,
        text="Select one or more files and send them to the main prompt.",
        font=ctk.CTkFont(size=10),
        text_color=theme["muted"],
    ).pack(pady=(0, 8))

    filter_frame = ctk.CTkFrame(root, fg_color="transparent")
    filter_frame.pack(fill="x", padx=18, pady=(0, 6))
    ctk.CTkLabel(
        filter_frame,
        text="Filter:",
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=theme["muted"],
    ).pack(side="left")
    filter_var = tk.StringVar(value="")
    filter_entry = ctk.CTkEntry(filter_frame, textvariable=filter_var, height=28)
    filter_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

    list_frame = ctk.CTkFrame(root, corner_radius=10)
    list_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))

    style = ttk.Style()
    try:
        style.theme_use("default")
    except tk.TclError:
        pass
    style.configure(
        "Treeview",
        background=theme["list_bg"],
        fieldbackground=theme["list_bg"],
        foreground=theme["list_fg"],
        rowheight=24,
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", theme["list_select_bg"])],
        foreground=[("selected", theme["list_select_fg"])],
    )

    columns = ("name", "folder", "modified", "size")
    tree = ttk.Treeview(
        list_frame,
        columns=columns,
        show="headings",
        selectmode="extended",
    )
    tree.heading("name", text="Name")
    tree.heading("folder", text="Folder")
    tree.heading("modified", text="Modified")
    tree.heading("size", text="Size")
    tree.column("name", width=220, anchor="w")
    tree.column("folder", width=260, anchor="w")
    tree.column("modified", width=140, anchor="w")
    tree.column("size", width=80, anchor="e")

    scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

    all_items: list[dict[str, Any]] = []
    for path in queue:
        if not os.path.exists(path):
            continue
        try:
            stat = os.stat(path)
        except OSError:
            continue
        all_items.append(
            {
                "path": path,
                "name": os.path.basename(path) or path,
                "folder": os.path.basename(os.path.dirname(path)) or os.path.dirname(path),
                "folder_full": os.path.dirname(path),
                "modified_ts": stat.st_mtime,
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
                "size_bytes": stat.st_size if os.path.isfile(path) else 0,
                "size": _format_size(stat.st_size) if os.path.isfile(path) else "—",
            }
        )

    sort_column: list[str] = ["modified_ts"]
    sort_reverse: list[bool] = [True]

    def _matches_filter(item: dict[str, Any]) -> bool:
        raw = filter_var.get().strip().lower()
        if not raw:
            return True
        tokens = [t for t in raw.replace(",", " ").split() if t]
        haystack = f"{item['name']} {item['folder_full']}".lower()
        return all(token in haystack for token in tokens)

    def _render() -> None:
        tree.delete(*tree.get_children())
        visible = [item for item in all_items if _matches_filter(item)]
        key = sort_column[0]
        reverse = sort_reverse[0]
        visible.sort(key=lambda item: item.get(key, ""), reverse=reverse)
        for item in visible:
            tree.insert(
                "",
                "end",
                iid=item["path"],
                values=(item["name"], item["folder"], item["modified"], item["size"]),
            )

    def _set_sort(column: str) -> None:
        if sort_column[0] == column:
            sort_reverse[0] = not sort_reverse[0]
        else:
            sort_column[0] = column
            sort_reverse[0] = False
        _render()

    tree.heading("name", command=lambda: _set_sort("name"))
    tree.heading("folder", command=lambda: _set_sort("folder"))
    tree.heading("modified", command=lambda: _set_sort("modified_ts"))
    tree.heading("size", command=lambda: _set_sort("size_bytes"))

    def _process_paths(paths: list[str]) -> None:
        if not paths:
            return
        on_process(paths)
        remaining = [item for item in all_items if item["path"] not in paths]
        all_items.clear()
        all_items.extend(remaining)
        _render()

    def _open_selected(_event: object | None = None) -> None:
        selection = list(tree.selection())
        _process_paths(selection)

    def _open_all() -> None:
        _process_paths([item["path"] for item in all_items])
        root.destroy()

    tree.bind("<Double-1>", _open_selected)
    tree.bind("<Return>", _open_selected)
    filter_entry.bind("<KeyRelease>", lambda _event: _render())

    action_frame = ctk.CTkFrame(root, fg_color="transparent")
    action_frame.pack(pady=(0, 14))
    ctk.CTkButton(
        action_frame,
        text="Open selected",
        fg_color=theme["accent"],
        text_color="#1e1e2e",
        hover_color=theme["btn_active"],
        font=ctk.CTkFont(size=10, weight="bold"),
        corner_radius=8,
        command=_open_selected,
    ).pack(side="left", padx=6)
    ctk.CTkButton(
        action_frame,
        text="Open all",
        fg_color=theme["btn_bg"],
        text_color=theme["btn_fg"],
        hover_color=theme["muted"],
        font=ctk.CTkFont(size=10),
        corner_radius=8,
        command=_open_all,
    ).pack(side="left", padx=6)
    ctk.CTkButton(
        action_frame,
        text="Close",
        fg_color=theme["btn_bg"],
        text_color=theme["btn_fg"],
        hover_color=theme["muted"],
        font=ctk.CTkFont(size=10),
        corner_radius=8,
        command=lambda: _on_close(),
    ).pack(side="left", padx=6)

    def _on_close() -> None:
        if on_defer is not None:
            on_defer([item["path"] for item in all_items])
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)
    _render()
    root.mainloop()
