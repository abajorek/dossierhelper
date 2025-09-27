"""Tkinter desktop UI for dossierhelper."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import platform
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from rich.console import Console

from .config import AppConfig, DEFAULT_CONFIG
from .pipeline import DossierPipeline

console = Console()


class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dossier Helper")
        self.geometry("640x320")
        self.config = DEFAULT_CONFIG
        self.pipeline = DossierPipeline(self.config)
        self.selected_year: Optional[int] = None
        self._build_widgets()

    def _build_widgets(self) -> None:
        self.columnconfigure(1, weight=1)

        tk.Label(self, text="Configuration file (optional)").grid(row=0, column=0, padx=8, pady=8, sticky="w")
        self.config_entry = tk.Entry(self)
        self.config_entry.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Browse", command=self._choose_config).grid(row=0, column=2, padx=8, pady=8)

        tk.Label(self, text="Limit to calendar year").grid(row=1, column=0, padx=8, pady=8, sticky="w")
        self.year_var = tk.StringVar()
        self.year_entry = tk.Entry(self, textvariable=self.year_var)
        self.year_entry.grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        tk.Button(self, text="Run Pass 1", command=self._run_pass_one).grid(row=2, column=0, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run Pass 2", command=self._run_pass_two).grid(row=2, column=1, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run Pass 3", command=self._run_pass_three).grid(row=2, column=2, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run All", command=self._run_all).grid(row=3, column=0, columnspan=3, padx=8, pady=16, sticky="ew")

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor="w").grid(row=4, column=0, columnspan=3, padx=8, pady=8, sticky="ew")

    def _choose_config(self) -> None:
        selected = filedialog.askopenfilename(title="Select configuration", filetypes=[("YAML", "*.yaml"), ("YML", "*.yml")])
        if selected:
            self.config_entry.delete(0, tk.END)
            self.config_entry.insert(0, selected)
            self.config = AppConfig.from_yaml(selected)
            self.pipeline = DossierPipeline(self.config)
            self.status_var.set(f"Loaded configuration from {selected}")

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
        self._run_async(lambda: self.pipeline.pass_one_surface_scan(year=self._resolve_year()), stage="pass1")

    def _run_pass_two(self) -> None:
        if not hasattr(self, "_pass_one_results"):
            messagebox.showwarning("Run pass one first", "Please run pass one before pass two.")
            return
        self._run_async(lambda: self.pipeline.pass_two_deep_analysis(self._pass_one_results), stage="pass2")

    def _run_pass_three(self) -> None:
        if not hasattr(self, "_pass_two_results"):
            messagebox.showwarning("Run pass two first", "Please run pass two before pass three.")
            return
        self._run_async(lambda: self.pipeline.pass_three_report(self._pass_two_results), stage="pass3")

    def _run_all(self) -> None:
        self._run_async(lambda: self.pipeline.run_all(year=self._resolve_year()), stage="all")

    def _run_async(self, func, *, stage: str) -> None:
        def worker() -> None:
            try:
                result = func()
                if stage == "pass1" and isinstance(result, list):
                    self._pass_one_results = result  # type: ignore[attr-defined]
                    messagebox.showinfo("Pass 1 complete", f"Identified {len(result)} candidate artifacts.")
                elif stage == "pass2" and isinstance(result, list):
                    self._pass_two_results = result  # type: ignore[attr-defined]
                    messagebox.showinfo("Pass 2 complete", f"Analyzed {len(result)} artifacts.")
                elif stage in {"pass3", "all"} and isinstance(result, Path):
                    messagebox.showinfo("Report generated", f"Report saved to {result}")
            except Exception as exc:  # noqa: BLE001
                console.log(f"[red]Error running pipeline: {exc}")
                messagebox.showerror("Pipeline error", str(exc))
            finally:
                self.status_var.set("Ready")

        self.status_var.set(f"Running {stage}...")
        threading.Thread(target=worker, daemon=True).start()


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
