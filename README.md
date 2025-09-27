# dossierhelper

A macOS-focused helper application to discover, classify, and report on tenure and promotion dossier artifacts.

## Features

* **Three-pass discovery pipeline** that starts with a fast surface scan, performs deeper metadata and text extraction, and culminates in a detailed reporting pass.
* **Rule-based classification** driven by the unit-provided tenure & promotion matrix for Teaching, Service, Advising, Forms, and Scholarly/Creative artifacts.
* **macOS Finder tag integration** to apply consistent color/label tags that mirror dossier destinations.
* **Tkinter desktop UI** that allows you to choose search roots, limit scans by calendar year, and launch each pass individually or in sequence.
* **Extensible metadata extraction** with hooks for Spotlight (`mdls`) data, PDF text parsing, and custom author-hour annotations.

## Getting Started

1. Install Python 3.10+ on macOS.
2. Clone this repository and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   # If you use zsh, remember to quote the extras specifier to avoid globbing.
   python3 -m pip install -e '.[mac]'
   ```

3. Launch the GUI:

   ```bash
   dossierhelper
   ```

## Configuration

The application loads optional YAML configuration files that define search roots, ignored directories, and author metadata. See [`example_config.yaml`](example_config.yaml) for a template.

## Development Notes

* The GUI and pipeline code were designed for macOS Monterey and newer.
* Text extraction relies on `pdfminer.six` when available; additional extractors can be registered in `dossierhelper/text.py`.
* Finder tag updates require `pyobjc` so the tool can call the Cocoa APIs for tagging. When tags cannot be written, the pipeline logs a warning and continues.

## License

MIT
