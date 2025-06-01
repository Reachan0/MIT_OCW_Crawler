# MITCrawlerX 🎓

A powerful and friendly tool for downloading and organizing MIT OpenCourseWare (OCW) course materials. MITCrawlerX helps you access high-quality educational content from MIT's extensive course catalog, making it easy to download and organize course materials for offline usage, training LLMs or building your Educational RAG Applications.

## 🌟 Features

- **Single Course Download**: Download all materials from a specific MIT OCW course
- **Multi-Course Download**: Download materials from multiple courses across different subjects
- **Smart Organization**: Organizes downloaded content by course and subject
- **Content Extraction**: Extracts text content from various file formats (PDF, DOCX, PY)
- **Progress Tracking**: Shows progress and provides detailed download summaries
- **Resume Capability**: Can resume interrupted downloads and skip already downloaded content

## 📋 Requirements

- Python 3.6 or higher
- Internet connection
- Required Python packages (automatically installed):
  - requests
  - beautifulsoup4
  - PyMuPDF (fitz)
  - python-docx

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/Ashad001/MITCrawlerX.git
cd MITCrawlerX
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## 💻 Usage

### Common Commands

Here are some common and helpful commands to run the script:

1. **Download a single course with default settings:**
```bash
python main.py --single --course-url "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/"
```

2. **Download a single course to a custom directory:**
```bash
python main.py --single --course-url "https://ocw.mit.edu/courses/your-course-url/" --download-dir "my_courses"
```

3. **Download multiple courses from specific subjects:**
```bash
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?d=Computer%20Science" "https://ocw.mit.edu/search/?d=Mathematics"
```

4. **Limit the number of courses per subject:**
```bash
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?d=Computer%20Science" --max-courses-per-subject 3
```

5. **Set a maximum total number of courses:**
```bash
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?d=Computer%20Science" "https://ocw.mit.edu/search/?d=Mathematics" --max-total-courses 5
```

6. **Use a custom search query:**
```bash
python main.py --multi --query-url "https://ocw.mit.edu/search/?q=python"
```

### Command Line Options

#### Common Options
- `--download-dir`: Specify download directory (default: "downloads")

#### Single Course Mode
- `--single`: Enable single course mode
- `--course-url`: URL of the course to download

#### Multiple Courses Mode
- `--multi`: Enable multiple courses mode
- `--subject-urls`: List of subject URLs to scrape
- `--query-url`: Search query URL
- `--max-courses-per-subject`: Maximum courses per subject
- `--max-total-courses`: Maximum total courses to download

## 📁 Output Structure

The downloaded content is organized as follows:

```
downloads/
├── Computer Science/
│   ├── Course1.json
│   └── Course2.json
├── Mathematics/
│   ├── Course1.json
│   └── Course2.json
├── scraped_content.json
└── scraping_summary.json
```

Each course is saved as a JSON file containing:
- Course metadata (name, description, topics)
- Course materials (lectures, assignments, exams)
- Extracted text content from various file formats

## 🔍 Example Output

The scraper generates two main JSON files:

1. `scraping_summary.json`: Contains overall statistics and course list
```json
{
  "timestamp": "2025-06-01 12:43:58",
  "total_courses_found": 15,
  "total_courses_processed": 10,
  "total_courses_failed": 0,
  "courses_processed": [...]
}
```

2. `scraped_content.json`: Contains detailed course content
```json
{
  "metadata": {...},
  "courses": [
    {
      "course_name": "Introduction to Computer Science",
      "course_description": "...",
      "topics": ["Computer Science", "Programming"],
      "files": [...]
    }
  ]
}
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.


## ⚠️ Disclaimer

This tool is for educational purposes only. Please respect MIT's terms of use and copyright policies when using downloaded materials.
