# Duolingo Guidebook Converters

This repository contains two Python scripts to extract and convert Duolingo guidebook pages into Markdown output.

- `duolingo_to_markdown.py` — a single-page converter that fetches one Duolingo guidebook page and converts it to Markdown.
- `batch_convert_duolingo.py` — an asynchronous batch converter that fetches many guidebook pages concurrently and combines them into one Markdown file.

Requirements:
- Python 3.8+
- See `requirements.txt` for required packages.

Installation:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Usage:

- Single page conversion:
```bash
python duolingo_to_markdown.py
# or import main() in Python and call:
# from duolingo_to_markdown import main
# main("https://duome.eu/guidebook/en/de/10")
```

- Batch conversion:
```bash
python batch_convert_duolingo.py
# or import main() and call:
# from batch_convert_duolingo import main
# main(start=1, end=156, output_file="all_duolingo_guidebooks.md")
```

Notes:
- The scripts use web requests to duome.eu guidebook pages and rely on the page structure at the time of writing. If Duome changes its HTML structure the extractors may need adjustments.
- The batch script uses `aiohttp` to fetch pages concurrently. Respect remote server load and adjust concurrency/timeouts if necessary.
