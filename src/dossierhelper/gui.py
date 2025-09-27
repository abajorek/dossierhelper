"""Tkinter desktop UI for dossierhelper."""

from __future__ import annotations

from pathlib import Path
from queue import Queue, Empty
from typing import Optional

import platform
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from rich.console import Console

from .config import AppConfig, DEFAULT_CONFIG, DEFAULT_CONFIG_PATH
from .pipeline import DossierPipeline, ProgressEvent, RunAllResult

console = Console()


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dossier Helper")
        self.geometry("640x320")
        self.config = DEFAULT_CONFIG
        self.pipeline = DossierPipeline(self.config)
        self.selected_year: Optional[int] = None
        self.log_queue: "Queue[str]" = Queue()
        self._build_widgets()
        self._poll_log_queue()

    def _build_widgets(self) -> None:
        self.columnconfigure(1, weight=1)

        tk.Label(self, text="Configuration file (optional)").grid(row=0, column=0, padx=8, pady=2, sticky="w")
        self.config_entry = tk.Entry(self)
        self.config_entry.grid(row=0, column=1, padx=8, pady=2, sticky="ew")
        tk.Button(self, text="Browse", command=self._choose_config).grid(row=0, column=2, padx=8, pady=8)
        tk.Label(
            self,
            text=(
                "Leave blank to use the built-in example_config.yaml, which searches "
                "Documents/Desktop and mirrors the dossier rules."
            ),
            wraplength=460,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, padx=8, pady=(0, 8), sticky="w")

        tk.Label(self, text="Limit to calendar year").grid(row=2, column=0, padx=8, pady=8, sticky="w")
        self.year_var = tk.StringVar()
        self.year_entry = tk.Entry(self, textvariable=self.year_var)
        self.year_entry.grid(row=2, column=1, padx=8, pady=8, sticky="ew")

        tk.Button(self, text="Run Pass 1", command=self._run_pass_one).grid(row=3, column=0, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run Pass 2", command=self._run_pass_two).grid(row=3, column=1, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run Pass 3", command=self._run_pass_three).grid(row=3, column=2, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run All", command=self._run_all).grid(row=4, column=0, columnspan=3, padx=8, pady=12, sticky="ew")

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor="w").grid(row=5, column=0, columnspan=3, padx=8, pady=(4, 0), sticky="ew")

        self.progress_output = scrolledtext.ScrolledText(self, height=8, state="disabled", wrap="word")
        self.progress_output.grid(row=6, column=0, columnspan=3, padx=8, pady=(4, 8), sticky="nsew")
        self.rowconfigure(6, weight=1)

        if DEFAULT_CONFIG_PATH:
            self.config_entry.insert(0, str(DEFAULT_CONFIG_PATH))
            self.status_var.set("Loaded bundled example configuration.")

    def _choose_config(self) -> None:
        selected = filedialog.askopenfilename(title="Select configuration", filetypes=[("YAML", "*.yaml"), ("YML", "*.yml")])
        if selected:
            self.config_entry.delete(0, tk.END)
            self.config_entry.insert(0, selected)
            self.config = AppConfig.from_yaml(selected)
            self.pipeline = DossierPipeline(self.config)
            self.status_var.set(f"Loaded configuration from {selected}")
            self._queue_log("Configuration tuned up. Time to blow the dust off this 80s boombox and scan like it's 1986!")

    def _resolve_year(self) -> Optional[int]:
        value = self.year_var.get().strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            messagebox.showerror("Invalid year", "Please enter a valid year (e.g., 2023)")
            return None

    def _run_pass_one(self) -> None:
        self._run_async(
            lambda: self.pipeline.pass_one_surface_scan(
                year=self._resolve_year(),
                progress_callback=self._queue_progress,
            ),
            stage="pass1",
        )

    def _run_pass_two(self) -> None:
        if not hasattr(self, "_pass_one_results"):
            messagebox.showwarning("Run pass one first", "Please run pass one before pass two.")
            return
        self._run_async(
            lambda: self.pipeline.pass_two_deep_analysis(
                self._pass_one_results,
                progress_callback=self._queue_progress,
            ),
            stage="pass2",
        )

    def _run_pass_three(self) -> None:
        if not hasattr(self, "_pass_two_results"):
            messagebox.showwarning("Run pass two first", "Please run pass two before pass three.")
            return
        self._run_async(
            lambda: self.pipeline.pass_three_report(
                self._pass_two_results,
                progress_callback=self._queue_progress,
            ),
            stage="pass3",
        )

    def _run_all(self) -> None:
        self._run_async(
            lambda: self.pipeline.run_all(
                year=self._resolve_year(),
                progress_callback=self._queue_progress,
            ),
            stage="all",
        )

    def _run_async(self, func, *, stage: str) -> None:
        def worker() -> None:
            try:
                result = func()
                if stage == "pass1" and isinstance(result, list):
                    self._pass_one_results = result  # type: ignore[attr-defined]
                    messagebox.showinfo(
                        "Pass 1 complete",
                        f"Identified {len(result)} candidate artifacts. As Strong Bad would say, that's some deluxe paper shuffling!",
                    )
                elif stage == "pass2" and isinstance(result, list):
                    self._pass_two_results = result  # type: ignore[attr-defined]
                    messagebox.showinfo(
                        "Pass 2 complete",
                        f"Analyzed {len(result)} artifacts. Cue the RedLetterMedia 'How embarrassing!' stinger for every misfiled folder.",
                    )
                elif stage == "all" and isinstance(result, RunAllResult):
                    messagebox.showinfo(
                        "Pass 1 complete",
                        f"Identified {result.pass_one_count} candidate artifacts. Strong Bad approves this deluxe paper shuffling session!",
                    )
                    messagebox.showinfo(
                        "Pass 2 complete",
                        f"Analyzed {result.pass_two_count} artifacts. Cue the RedLetterMedia 'How embarrassing!' sting for every misfiled folder.",
                    )
                    messagebox.showinfo(
                        "Report generated",
                        f"Report saved to {result.report_path}. It's like a VHS training tape come to life, but with way better metadata.",
                    )
                elif stage == "pass3" and isinstance(result, Path):
                    messagebox.showinfo(
                        "Report generated",
                        f"Report saved to {result}. It's like a VHS training tape come to life, but with way better metadata.",
                    )
            except Exception as exc:  # noqa: BLE001
                console.log(f"[red]Error running pipeline: {exc}")
                messagebox.showerror("Pipeline error", str(exc))
            finally:
                self.status_var.set("Ready")

        self.status_var.set(f"Running {stage}...")
        self._queue_log(f"{stage.upper()} engaged. Cue the keytar solo!")
        threading.Thread(target=worker, daemon=True).start()

    def _queue_progress(self, event: ProgressEvent) -> None:
        details = event.message
        if event.scanned_count is not None and event.total_candidates is not None:
            details += f" | Progress: {event.scanned_count}/{event.total_candidates}"
        elif event.scanned_count is not None:
            details += f" | Processed: {event.scanned_count}"
        if event.eta_seconds is not None:
            minutes, seconds = divmod(int(max(event.eta_seconds, 0)), 60)
            details += f" | ETA: {minutes:02d}:{seconds:02d}"
        if event.bucket_totals:
            bucket_summary = ", ".join(f"{bucket}: {count}" for bucket, count in sorted(event.bucket_totals.items()))
            details += f" | Buckets => {bucket_summary}"
        if event.finder_tagged is not None:
            tag_status = "Finder tag locked in" if event.finder_tagged else "Finder tag skipped"
            details += f" | {tag_status}"
        elif event.stage == "pass2" and event.finder_tagged is None:
            details += " | Finder tagging disabled"
        if event.stage == "pass2" and event.bucket == "Unclassified":
            details += " | Whoops! Somebody call Mike Stoklasa because that one's getting the 'How embarrassing!' cut."
        self._queue_log(details)

    def _queue_log(self, message: str) -> None:
        self.log_queue.put(message)

    def _poll_log_queue(self) -> None:
        try:
            while True:
                entry = self.log_queue.get_nowait()
                self._append_log(entry)
        except Empty:
            pass
        finally:
            self.after(200, self._poll_log_queue)

    def _append_log(self, message: str) -> None:
        self.progress_output.configure(state="normal")
        self.progress_output.insert(tk.END, message + "\n")
        self.progress_output.see(tk.END)
        self.progress_output.configure(state="disabled")


def _ensure_supported_environment() -> None:
    """Validate that the application is running on a supported platform."""

    if sys.version_info < (3, 10):
        raise SystemExit(
            "Dossier Helper requires Python 3.10 or newer. Please upgrade Python before launching the app."
        )

    if platform.system() != "Darwin":
        console.log(
            "[yellow]Dossier Helper is optimized for macOS. Some functionality, such as Finder tag integration, may be unavailable on this platform."
        )


def main() -> None:
    _ensure_supported_environment()
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
