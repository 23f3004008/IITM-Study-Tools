# IITM-Study-Tools

# Lecture Transcript Downloader

A CLI tool to download YouTube lecture transcripts, process them into Markdown, and optionally convert to PDF or TXT formats with master file generation.

## Features

- Download transcripts from YouTube videos using yt-dlp
- Clean and deduplicate transcript text
- Create individual Markdown files for each lecture
- Generate weekly and/or all-course master Markdown files
- Convert Markdown files to PDF (using WeasyPrint) or TXT formats
- Parallel processing for conversions to maximize speed
- Support for multiple output formats simultaneously
- Organized folder structure with optional subfolders per week

## Requirements

- Python 3.14+
- uv (for dependency management)
- pandoc (for potential fallback, but not required as WeasyPrint is used)

## Installation

1. Clone or download the repository
2. Install dependencies using uv:
   ```bash
   uv sync
   ```

## Usage

```bash
uv run lecture_dl.py [OPTIONS]
```

### Options

- `--folders`: Create subfolders for each week
- `--master-weekly`: Create master Markdown files for each week
- `--master-all`: Create a master Markdown file for the entire course
- `--md`: Keep Markdown files (default if no formats specified)
- `--pdf`: Create PDF files
- `--txt`: Create TXT files
- `--verbose`: Enable verbose output
- `--help`: Show help message

### Examples

Download transcripts and keep as Markdown:
```bash
uv run lecture_dl.py
```

Create PDFs with weekly masters:
```bash
uv run lecture_dl.py --master-weekly --pdf
```

Create all formats with subfolders:
```bash
uv run lecture_dl.py --folders --master-weekly --master-all --md --pdf --txt
```

### Input

The tool expects a `data.json` file in the current directory with the following structure:

```json
{
  "namespace": "ns_course_name",
  "outline": [
    {
      "title": "Week 1",
      "children": [
        {
          "title": "Lecture Title",
          "video": "YOUTUBE_VIDEO_ID",
          "type": "L",
          "video_type": "youtube"
        }
      ]
    }
  ]
}
```

### Output

- `course_name/` directory with transcripts
- `youtube_links.json` with lecture metadata and file paths
- Individual files: `Week1_1_Lecture_Title.md/pdf/txt`
- Master files: `Week_1_master.md/pdf/txt`, `all_master.md/pdf/txt`

## Processing Details

- Transcripts are downloaded sequentially to respect YouTube rate limits
- Conversions happen in parallel using multiprocessing (8 workers)
- PDF generation uses WeasyPrint for high-quality output
- Transcript text is cleaned of duplicates and formatting artifacts
- Masters concatenate all lecture content with separators

## Notes

- Downloads respect YouTube's terms and rate limits
- Requires internet connection for transcript downloads
- PDF conversion may take time for long transcripts
- Verbose mode provides detailed logging of operations
