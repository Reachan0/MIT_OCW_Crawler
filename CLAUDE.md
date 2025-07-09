# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MITCrawlerX is a powerful web scraper for downloading MIT OpenCourseWare (OCW) course materials. The system is designed to extract and organize educational content from MIT's online course catalog with support for both single-course and multi-course scraping modes.

## Core Architecture

### Main Components

1. **Entry Point** (`main.py`): Command-line interface and argument parsing
2. **Course Discovery** (`src/course_scrapper.py`): Discovers courses from MIT OCW search pages using Selenium
3. **Content Extraction** (`src/content_scrapper.py`): Downloads and extracts content from individual courses
4. **Distributed Processing** (`src/utils/distributed.py`): Coordinates multi-device scraping to avoid duplicates
5. **Logging** (`src/utils/logger.py`): Centralized logging with file and console output

### Scraping Modes

- **Single Course Mode**: Downloads materials from a specific course URL
- **Multi Course Mode**: Discovers and downloads multiple courses from subject URLs or search queries
- **Distributed Mode**: Enables coordination across multiple devices/nodes
- **Incremental Mode**: Only crawls new courses not found in previous runs

### Data Flow

1. Course URLs are discovered via Selenium-driven web scraping
2. Each course's content is extracted using requests and BeautifulSoup
3. Content from PDFs, DOCX files, and Python files is extracted and stored
4. Results are saved as JSON files organized by subject category
5. Progress tracking allows for resuming interrupted scraping sessions

## Common Commands

### Installation
```bash
pip install -r requirements.txt
```

### Testing
```bash
# Test incremental crawling functionality
python test_incremental.py

# Test course limit fixes
python test_course_limit.py

# Test Chrome fallback behavior
python test_no_chrome.py

# Verify specific course counts
python verify_non_credit.py
```

### Single Course Scraping
```bash
python main.py --single --course-url "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/"
```

### Multi-Course Scraping
```bash
# Scrape multiple subjects
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?d=Computer%20Science" "https://ocw.mit.edu/search/?d=Mathematics"

# Use predefined subject categories
python main.py --multi --subject-category cs --max-courses-per-subject 5

# Custom search query
python main.py --multi --query-url "https://ocw.mit.edu/search/?q=python" --max-total-courses 10
```

### Distributed Scraping
```bash
# Node 1 of 3
python main.py --multi --distributed --node-id 1 --total-nodes 3 --subject-category cs

# Node 2 of 3  
python main.py --multi --distributed --node-id 2 --total-nodes 3 --subject-category math
```

### Force Refresh (Clear All Data)
```bash
python main.py --multi --force-refresh --subject-category cs
```

### Incremental Crawling
```bash
# Initial crawl
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?l=Non-Credit" --max-courses-per-subject 10

# Incremental crawl (only new courses)
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?l=Non-Credit" --max-courses-per-subject 20 --incremental
```

## Configuration

### Key Constants (`constants.py`)

- **Rate Limiting**: `COURSE_DELAY_SECONDS`, `PAGE_DELAY_SECONDS`, `REQUEST_DELAY_MIN/MAX`
- **Subject Categories**: Predefined URL lists for different academic subjects (cs, math, physics, etc.)
- **Distributed Settings**: Node configuration and database paths
- **Output Paths**: Download directories and file naming conventions

### Environment Variables
- `ENV`: Set to "development" to enable logging (default behavior)

## Output Structure

```
downloads/
├── Computer Science/
│   ├── Course1.json
│   └── Course2.json
├── Mathematics/
│   ├── Course1.json  
│   └── Course2.json
├── scraped_content_[task_id].json     # Combined content from all courses
├── scraper_progress_[task_id].json    # Progress tracking for resuming
└── scraping_summary_[task_id].json    # Statistics and metadata
```

## Development Notes

### Content Extraction
The system extracts text content from:
- PDF files using PyMuPDF (fitz)
- DOCX files using python-docx
- Python source files directly
- HTML pages using BeautifulSoup

### Progress Tracking
- Each scraping session generates a unique task ID based on input URLs
- Progress files allow resuming interrupted sessions
- Distributed database prevents duplicate processing across nodes
- Incremental mode filters out previously discovered courses

### Task ID System
The system generates unique task IDs (8-character MD5 hash) based on the input URLs to:
- Distinguish between different scraping sessions
- Enable proper progress tracking and resumption
- Support incremental crawling by comparing against previous runs

### Error Handling
- Comprehensive logging to `logs/` directory
- Graceful handling of network timeouts and parsing errors
- Skip already-processed content when resuming

### Rate Limiting
Built-in delays prevent overwhelming MIT's servers:
- 20 seconds between courses
- 10 seconds between search result pages  
- 1-3 seconds between individual requests

### Chrome WebDriver Fallback
The system automatically falls back to requests-based scraping when Chrome WebDriver is unavailable:
- Selenium WebDriver is preferred for JavaScript-heavy pages
- Requests + BeautifulSoup fallback for environments without Chrome
- Automatic detection and graceful degradation

### Course Discovery Architecture
- **Infinite Scroll Handling**: Automatically scrolls through paginated results
- **Deduplication**: Prevents duplicate course entries during discovery
- **Incremental Discovery**: Compares against previous runs to identify new courses
- **Subject-based Organization**: Organizes courses by academic subject/department