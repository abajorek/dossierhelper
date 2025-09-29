"""Tkinter desktop UI for dossierhelper."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

import platform
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from rich.console import Console

from .config import AppConfig, DEFAULT_CONFIG, DEFAULT_CONFIG_PATH
from .pipeline import DossierPipeline, ProgressEvent, RunAllResult

console = Console()


class OverallProgressMeter(tk.Frame):
    """Canvas-based overall progress meter with Strong Bad-approved theming."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.columnconfigure(0, weight=1)

        self._load_images()

        self.canvas = tk.Canvas(self, height=150, width=620, bg="#fff9ec", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="ew")

        self.status_var = tk.StringVar(value="🍋 Lemonade stand is open for business!")
        self.status_label = tk.Label(self, textvariable=self.status_var, font=('Monaco', 10), justify='center')
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        self._track_start = 110
        self._track_end = 510
        self._track_y = 95

        self._draw_static_elements()
        self.reset()

    def _load_images(self) -> None:
        """Load lemonade stand, duck frames, and grape images from assets."""

        def load_asset(filename: str, subsample: int = 2) -> tk.PhotoImage:
            asset = resources.files("dossierhelper.assets") / filename
            with resources.as_file(asset) as path:
                image = tk.PhotoImage(file=str(path))
            if subsample > 1:
                image = image.subsample(subsample, subsample)
            return image

        self.lemonade_image = load_asset("lemonade_stand.ppm", subsample=2)
        self.grapes_image = load_asset("grapes.ppm", subsample=2)

        duck_frames = [
            "duck_left.ppm",
            "duck_left2.ppm",
            "duck_mid.ppm",
            "duck_right.ppm",
            "duck_right2.ppm",
            "duck_right.ppm",
            "duck_mid.ppm",
            "duck_left2.ppm",
        ]
        self.duck_frames = [load_asset(name, subsample=2) for name in duck_frames]

    def _draw_static_elements(self) -> None:
        """Create the static canvas elements for the progress meter."""

        self.canvas.delete("all")
        # Track and decorations
        self.canvas.create_line(
            self._track_start,
            self._track_y,
            self._track_end,
            self._track_y,
            width=14,
            fill="#d9a066",
            capstyle=tk.ROUND,
        )
        self.canvas.create_line(
            self._track_start,
            self._track_y + 12,
            self._track_end,
            self._track_y + 12,
            width=4,
            fill="#f7d7a2",
            capstyle=tk.ROUND,
        )

        # Start and finish images
        self.canvas.create_image(self._track_start - 70, self._track_y - 10, image=self.lemonade_image)
        self.canvas.create_text(
            self._track_start - 70,
            self._track_y + 45,
            text="0%",
            font=('TkDefaultFont', 10, 'bold'),
            fill="#3b2e1a",
        )
        self.canvas.create_image(self._track_end + 70, self._track_y - 10, image=self.grapes_image)
        self.canvas.create_text(
            self._track_end + 70,
            self._track_y + 45,
            text="100%",
            font=('TkDefaultFont', 10, 'bold'),
            fill="#3b2e1a",
        )

        self.percentage_text_id = self.canvas.create_text(
            (self._track_start + self._track_end) / 2,
            28,
            text="0%",
            font=('Helvetica', 18, 'bold'),
            fill="#3b2e1a",
        )

        self.canvas.create_text(
            (self._track_start + self._track_end) / 2,
            52,
            text="Duck Progress Patrol",
            font=('TkDefaultFont', 10, 'bold'),
            fill="#7f5f2a",
        )

        self.duck_id = self.canvas.create_image(self._track_start, self._track_y - 22, image=self.duck_frames[0])

    def reset(self) -> None:
        """Return the duck to the lemonade stand and reset text."""

        self.update_meter(0.0)

    def update_meter(self, percentage: float) -> None:
        """Move the duck along the track and update the status messaging."""

        clamped = max(0.0, min(100.0, percentage))
        duck_x = self._track_start + ((self._track_end - self._track_start) * (clamped / 100.0))
        self.canvas.coords(self.duck_id, duck_x, self._track_y - 22)

        frame_index = int(clamped / 5) % len(self.duck_frames)
        self.canvas.itemconfigure(self.duck_id, image=self.duck_frames[frame_index])

        if clamped.is_integer():
            pct_label = f"{int(clamped)}%"
        else:
            pct_label = f"{clamped:4.1f}%"
        self.canvas.itemconfigure(self.percentage_text_id, text=pct_label)

        if clamped <= 0.5:
            self.status_var.set("🍋 Lemonade stand is open for business!")
        elif clamped >= 100:
            self.status_var.set("🍇 Grape victory! JORB WELL DONE!")
        elif clamped < 50:
            self.status_var.set("🦆 Waddling through the quad like Strong Bad ordered!")
        elif clamped < 90:
            self.status_var.set("🦆 Duck wobble intensifies – academic glory ahead!")
        else:
            self.status_var.set("🍇 Almost grape time! Prep the celebration confetti!")

class Application(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Dossier Helper - Deluxe Academic Paper Shuffling Station")
        self.geometry("900x650")
        self.config = DEFAULT_CONFIG
        self.pipeline = DossierPipeline(self.config)
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

        tk.Label(self, text="Limit to calendar years").grid(row=2, column=0, padx=8, pady=8, sticky="w")
        self.year_vars: dict[int, tk.BooleanVar] = {}
        year_frame = tk.Frame(self)
        year_frame.grid(row=2, column=1, columnspan=2, padx=8, pady=8, sticky="w")
        for idx, year in enumerate(range(2021, 2026)):
            var = tk.BooleanVar(value=False)
            chk = tk.Checkbutton(year_frame, text=str(year), variable=var)
            chk.grid(row=0, column=idx, padx=(0 if idx == 0 else 6, 0))
            self.year_vars[year] = var

        tk.Button(self, text="Run Pass 1", command=self._run_pass_one).grid(row=3, column=0, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run Pass 2", command=self._run_pass_two).grid(row=3, column=1, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run Pass 3", command=self._run_pass_three).grid(row=3, column=2, padx=8, pady=8, sticky="ew")
        tk.Button(self, text="Run All", command=self._run_all).grid(row=4, column=0, columnspan=3, padx=8, pady=12, sticky="ew")

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self.status_var, anchor="w").grid(row=5, column=0, columnspan=3, padx=8, pady=(4, 0), sticky="ew")

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=6, column=0, columnspan=3, padx=8, pady=(4, 2), sticky="ew")
        
        # Deluxe graphical progress display
        self.overall_progress_meter = OverallProgressMeter(self)
        self.overall_progress_meter.grid(row=7, column=0, columnspan=3, padx=8, pady=(2, 6), sticky="ew")
        
        # Per-file progress bar
        tk.Label(self, text="Current File Progress:", font=('TkDefaultFont', 9)).grid(row=8, column=0, sticky="w", padx=8)
        self.file_progress_var = tk.DoubleVar()
        self.file_progress_bar = ttk.Progressbar(self, variable=self.file_progress_var, maximum=100, mode="determinate")
        self.file_progress_bar.grid(row=8, column=1, columnspan=2, padx=8, pady=(2, 2), sticky="ew")
        
        # Current file label
        self.current_file_var = tk.StringVar(value="")
        self.current_file_label = tk.Label(self, textvariable=self.current_file_var, anchor="w", font=('TkDefaultFont', 9))
        self.current_file_label.grid(row=9, column=0, columnspan=3, padx=8, pady=(0, 4), sticky="ew")

        self.progress_output = scrolledtext.ScrolledText(self, height=8, state="disabled", wrap="word")
        self.progress_output.grid(row=10, column=0, columnspan=3, padx=8, pady=(4, 8), sticky="nsew")
        self.rowconfigure(10, weight=1)

        if DEFAULT_CONFIG_PATH:
            self.config_entry.insert(0, str(DEFAULT_CONFIG_PATH))
            self.status_var.set("Loaded bundled example configuration.")
            self._queue_log("🎮 DOSSIER HELPER ACTIVATED! Verbose mode engaged - prepare for deluxe paper shuffling action!")
            self._queue_log("💪 Strong Bad would be proud of this academic document classification system!")
            self._queue_log("🎬 RedLetterMedia commentary mode: ON. Expect quality burns for unclassified files!")
            self._queue_log("🔥 Ready to scan, classify, and tag your academic artifacts like a true champion!")
        else:
            self._queue_log("🎯 Dossier Helper ready for action! Configure and let's get this academic party started!")

    def _choose_config(self) -> None:
        selected = filedialog.askopenfilename(title="Select configuration", filetypes=[("YAML", "*.yaml"), ("YML", "*.yml")])
        if selected:
            self.config_entry.delete(0, tk.END)
            self.config_entry.insert(0, selected)
            self.config = AppConfig.from_yaml(selected)
            self.pipeline = DossierPipeline(self.config)
            self.status_var.set(f"Loaded configuration from {selected}")
            self._queue_log(f"🚀 Configuration tuned up from {Path(selected).name}! Time to blow the dust off this 80s boombox and scan like it's 1986!")
            self._queue_log("🎹 Custom config loaded - The Cheat is definitely not involved in this operation!")
            self._queue_log("🔧 All systems go for premium academic document detection and classification!")
            self._queue_log("🎯 Ready to unleash the power of organized scholarship upon your file system!")

    def _resolve_years(self) -> Optional[set[int]]:
        selected = {year for year, var in self.year_vars.items() if var.get()}
        return selected or None

    def _run_pass_one(self) -> None:
        self._run_async(
            lambda: self.pipeline.pass_one_surface_scan(
                years=self._resolve_years(),
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
                years=self._resolve_years(),
                progress_callback=self._queue_progress,
            ),
            stage="all",
        )

    def _run_async(self, func, *, stage: str) -> None:
        def worker() -> None:
            try:
                result = func()
            except Exception as exc:  # noqa: BLE001
                console.log(f"[red]Error running pipeline: {exc}")

                def handle_error() -> None:
                    messagebox.showerror("Pipeline error", str(exc))
                    self.status_var.set("Ready")
                    self.progress_var.set(0)
                    self.overall_progress_meter.reset()
                    self.file_progress_var.set(0)
                    self.current_file_var.set("")

                self.after(0, handle_error)
                return

            def handle_success() -> None:
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
                self.status_var.set("Ready")
                self.progress_var.set(100)  # Show completion
                self.overall_progress_meter.update_meter(100)
                self.file_progress_var.set(100)
                self.current_file_var.set("🎉 Operation completed successfully!")

            self.after(0, handle_success)

        self.status_var.set(f"Running {stage}...")
        
        # Stage-specific startup messages
        if stage == "pass1":
            self._queue_log("🔍 PASS 1 SURFACE SCAN INITIATED! Strong Bad's filing system would be jealous!")
            self._queue_log("🎵 Cue the keytar solo! Scanning for academic artifacts across your digital domain...")
            self._queue_log("🔎 Seeking out teaching materials, research docs, and service records with laser precision!")
            if self.config.google_drives:
                enabled_drives = [d.name for d in self.config.google_drives if d.enabled]
                if enabled_drives:
                    self._queue_log(f"☁️ Google Drive integration enabled for: {', '.join(enabled_drives)}")
                    self._queue_log("🚀 Preparing to scan both local files AND cloud storage - oh, seriously!")
        elif stage == "pass2":
            self._queue_log("🧠 PASS 2 DEEP ANALYSIS ENGAGED! Time for some serious document classification action!")
            self._queue_log("🎬 Mike Stoklasa is watching - better classify these files correctly or face the embarrassment!")
            self._queue_log("🏷️ Applying Finder tags like a champion - Teaching (Green), Scholarship (Blue), Service (Yellow)!")
            self._queue_log("📊 Per-file progress tracking activated - watch each document get processed step by step!")
        elif stage == "pass3":
            self._queue_log("📄 PASS 3 REPORT GENERATION ACTIVATED! Generating the ultimate academic dossier summary!")
            self._queue_log("📊 Creating a report so good, it'll make your tenure committee weep tears of joy!")
        elif stage == "all":
            self._queue_log("💥 RUN ALL PASSES INITIATED! The full academic document classification experience!")
            self._queue_log("🎆 Prepare for the complete Strong Bad-approved paper shuffling extravaganza!")
            self._queue_log("🏆 Three passes of pure academic organizational excellence coming right up!")
            if self.config.google_drives:
                enabled_drives = [d.name for d in self.config.google_drives if d.enabled]
                if enabled_drives:
                    self._queue_log(f"☁️ Google Drive scanning enabled for: {', '.join(enabled_drives)}")
        
        self.progress_var.set(0)
        self.overall_progress_meter.reset()
        self.file_progress_var.set(0)
        self.current_file_var.set("⏳ Initializing...")
        threading.Thread(target=worker, daemon=True).start()
    
    def _get_file_size_taunt(self, file_path: Path) -> str:
        """Get size-based RedLetterMedia/Homestar Runner taunts."""
        import random
        
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
        except:
            size_mb = 0
        
        if size_mb > 50:  # Large files
            large_file_taunts = [
                "How embarrassing! That's a chunky file!",
                "OH MY GAAAWD! What a units of file!",
                "That's a big file... that's a big file.",
                "Very cool, very large file size!",
                "I clapped when I saw the file size!",
                "It's like poetry, it's so dense!",
                "Sweet genius! That file's HUGE!",
                "That file's bigger than The Cheat!"
            ]
            return random.choice(large_file_taunts)
        elif size_mb < 0.1:  # Tiny files
            tiny_file_taunts = [
                "That's a tiny file! What is this, amateur hour?",
                "Oh, seriously? That's it? That's the file?",
                "Small file alert! The Cheat could do better!",
                "It broke new ground... in being small!",
                "Very cool, very small file!",
                "That file's smaller than Strong Sad's ego!"
            ]
            return random.choice(tiny_file_taunts)
        else:
            return ""  # No taunt for normal-sized files
    
    def _get_random_processing_taunt(self) -> str:
        """Get random processing taunts."""
        import random
        
        rlm_taunts = [
            "How embarrassing!",
            "What's wrong with your FACE?!",
            "Very cool, very cool!",
            "OH MY GAAAWD!",
            "It broke new ground!",
            "I clapped! I clapped when I saw it!",
            "It's like poetry, it rhymes!",
            "AT-ST! AT-ST!",
            "Rich Evans wheeze*",
            "Mike Stoklasa would not approve!"
        ]
        
        homestar_taunts = [
            "Oh, seriously!",
            "That's some deluxe paper shuffling!",
            "The Cheat is grounded!",
            "Holy crap on a cracker!",
            "Check it out! No, seriously, check it out!",
            "Oh, for serious?",
            "Sweet genius!",
            "Seriously, seriously?",
            "Well, that's a load of bull!",
            "Jorb well done!",
            "The system is down! Wait, no it's not.",
            "Strong Bad would be proud!"
        ]
        
        all_taunts = rlm_taunts + homestar_taunts
        return random.choice(all_taunts)
    
    def _get_tagging_confirmation(self, tagged: bool, category: str) -> str:
        """Get clear tagging confirmation message."""
        if tagged:
            tag_colors = {
                "Teaching": "🟢 GREEN",
                "Scholarship": "🔵 BLUE", 
                "Service": "🟡 YELLOW",
                "Research": "🟣 PURPLE",
                "Administration": "🟠 ORANGE"
            }
            color = tag_colors.get(category, "⚪ WHITE")
            return f"✅ FINDER TAG APPLIED: {color} '{category}' tag locked and loaded!"
        else:
            return "❌ FINDER TAG SKIPPED (no category match or tagging disabled)"
    
    def _update_file_progress(self, percentage: float, step: str) -> None:
        """Update the per-file progress bar with real progress."""
        self.file_progress_var.set(percentage)
        
        # Update file progress label with current step
        step_emoji = {
            "Loading file": "📂",
            "Downloading from Google Drive": "☁️",
            "File loaded": "✓",
            "Reading metadata": "📋",
            "Metadata extracted": "✓",
            "Extracting text content": "📄",
            "Text extracted": "✓",
            "Classifying document": "🔍",
            "Classification complete": "✓",
            "Estimating effort": "⏱️",
            "Effort estimated": "✓",
            "Applying Finder tags": "🏷️",
            "Finder tags applied": "✓",
            "Complete": "🎉",
            "Error": "❌"
        }
        
        emoji = step_emoji.get(step.split(" (")[0], "⚙️")  # Handle steps with extra info in parens
        if "Downloading" in step:
            emoji = "☁️"
        
        step_display = f"{emoji} {step} ({percentage:.0f}%)"
        self.current_file_var.set(step_display)
    
    def _queue_progress(self, event: ProgressEvent) -> None:
        import random
        from pathlib import Path
        
        # Calculate and display overall percentage
        percentage = 0.0
        if event.scanned_count is not None and event.total_candidates:
            completed_items = float(event.scanned_count)
            if event.file_progress_percentage is not None:
                completed_items = max(0.0, float(event.scanned_count - 1))
                completed_items += max(0.0, min(100.0, event.file_progress_percentage)) / 100.0
            percentage = min(100.0, (completed_items / event.total_candidates) * 100)

            # Update overall progress visuals
            self.progress_var.set(percentage)
            self.overall_progress_meter.update_meter(percentage)
        
        # Update per-file progress (now using real progress data!)
        if event.file_progress_percentage is not None and event.file_progress_step:
            self._update_file_progress(event.file_progress_percentage, event.file_progress_step)
        elif event.file_progress_percentage == 0:  # Reset on error
            self.file_progress_var.set(0)
            if event.file_progress_step:
                self.current_file_var.set(f"❌ {event.file_progress_step}")
        
        # Build detailed progress message with MORE OBVIOUS taunts
        details = f"🔍 {event.message}"
        
        # Add percentage info
        if event.scanned_count is not None and event.total_candidates is not None:
            details += f" | 📊 {percentage:.1f}% ({event.scanned_count}/{event.total_candidates})"
            
            # Add milestone celebrations with OBVIOUS taunts
            if percentage >= 100:
                celebration = random.choice([
                    "🎉 JORB WELL DONE! The Cheat is definitely not involved!",
                    "🎆 Victory! Like in that movie! What movie? Any movie!",
                    "🏆 The system worked! Strong Bad would be so proud!",
                    "🎇 It broke new ground... in file classification!"
                ])
                details += f" | {celebration}"
            elif percentage >= 90:
                details += f" | 🏁 {random.choice(['Almost there! The end is in sight!', 'In the home stretch! Like a marathon, but for files!', 'OH MY GAAAWD! So close!'])}"
            elif percentage >= 75:
                details += f" | 💪 {random.choice(['Three quarters done! Very cool, very cool!', 'Making excellent progress! How embarrassing for slow computers!', 'Sweet genius! This is working!'])}"
            elif percentage >= 50:
                details += f" | 🏃 {random.choice(['Halfway there! Living on a prayer!', 'Half done! Like the Death Star, but functional!', 'Seriously, seriously? Already halfway!'])}"
            elif percentage >= 25:
                details += f" | 🚀 {random.choice(['Quarter done! Getting warmed up!', 'Rolling now! The Cheat is impressed!', 'Check it out! Progress is happening!'])}"
        
        # Current file processing with size-based taunts
        if hasattr(event, 'current_file') and event.current_file:
            file_path = Path(event.current_file)
            size_taunt = self._get_file_size_taunt(file_path)
            if size_taunt:
                details += f" | 💭 {size_taunt}"
        
        # ETA with OBVIOUS commentary
        if event.eta_seconds is not None:
            minutes, seconds = divmod(int(max(event.eta_seconds, 0)), 60)
            if minutes > 60:
                hours = minutes // 60
                minutes = minutes % 60
                details += f" | ⏰ ETA: {hours}h {minutes:02d}m {seconds:02d}s"
                # Long time taunts
                long_taunts = [
                    "Time for a Sbarro break!",
                    "Grab a Diet Coke and some Free Country USAs!",
                    "Perfect time to check your email! Or watch Best of the Worst!",
                    "This is taking longer than a Rich Evans story!"
                ]
                details += f" | 🍕 {random.choice(long_taunts)}"
            else:
                details += f" | ⏰ ETA: {minutes:02d}:{seconds:02d}"
                if event.eta_seconds < 30:
                    quick_taunts = [
                        "Almost done! Any second now!",
                        "Hold onto your butts! We're almost there!",
                        "OH MY GAAAWD! So fast!",
                        "Very cool! Very quick!"
                    ]
                    details += f" | ⚡ {random.choice(quick_taunts)}"
        
        # VERY OBVIOUS Finder tagging confirmation
        if event.finder_tagged is not None:
            tag_message = self._get_tagging_confirmation(event.finder_tagged, event.bucket or "Unknown")
            details += f" | {tag_message}"
            
            # Add extra tagging commentary
            if event.finder_tagged:
                tagging_celebrations = [
                    "macOS Finder tag SUCCESS! File organization level: MAXIMUM!",
                    "Finder tagging complete! The file has been marked for academic glory!",
                    "Tag applied! Your file is now properly categorized, unlike Mike Stoklasa's VHS collection!",
                    "Boom! Tagged! Strong Bad would approve of this organizational excellence!"
                ]
                details += f" | 🎉 {random.choice(tagging_celebrations)}"
            else:
                tagging_failures = [
                    "No tag applied! How embarrassing! File remains organizationally challenged!",
                    "Tagging failed! What's wrong with your file?!",
                    "No category match! This file is more mysterious than a Rich Evans laugh!",
                    "Tag skipped! Oh, seriously? What is this file even for?"
                ]
                details += f" | 😬 {random.choice(tagging_failures)}"
        
        # Bucket analysis with OBVIOUS commentary
        if event.bucket_totals:
            bucket_summary = ", ".join(f"{bucket}: {count}" for bucket, count in sorted(event.bucket_totals.items()))
            details += f" | 🗂️ Categories: {bucket_summary}"
            
            # Add bucket-specific OBVIOUS commentary
            for bucket, count in event.bucket_totals.items():
                if bucket == "Teaching" and count > 0:
                    details += f" | 🍎 {count} teaching docs found - The Cheat would definitely be proud of this education!"
                elif bucket == "Scholarship" and count > 0:
                    details += f" | 📚 {count} scholarship items - Very cool research! It broke new ground!"
                elif bucket == "Service" and count > 0:
                    details += f" | 🤝 {count} service docs - Serving the community like a true champion of helping!"
                elif bucket == "Unclassified" and count > 0:
                    unclassified_burns = [
                        "How embarrassing! These files couldn't be classified!",
                        "OH MY GAAAWD! What are these mystery files?!",
                        "Unclassified files detected! Mike Stoklasa would not approve!",
                        "Sweet genius! Some files are too weird to categorize!"
                    ]
                    details += f" | 🤷 {count} unclassified files! {random.choice(unclassified_burns)}"
        
        # Random OBVIOUS motivational/sarcastic comments (higher chance)
        if random.random() < 0.25:  # 25% chance for OBVIOUS random comment
            random_taunt = self._get_random_processing_taunt()
            details += f" | 🗣️ {random_taunt}"
        
        # Stage-specific OBVIOUS Strong Bad commentary
        if hasattr(event, 'stage_progress') and event.stage_progress:
            if event.stage == "pass1":
                details += f" | 🔍 Pass 1 Status: {event.stage_progress} - Surface scanning like a champ!"
            elif event.stage == "pass2":
                details += f" | 🧠 Pass 2 Status: {event.stage_progress} - Deep analysis mode engaged!"
            elif event.stage == "pass3":
                details += f" | 📄 Pass 3 Status: {event.stage_progress} - Report generation in progress!"
        
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
