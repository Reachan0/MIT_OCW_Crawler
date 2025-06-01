import os

BASE_URL = "https://ocw.mit.edu"
DEFAULT_COURSE_URL = "https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/"
DEFAULT_DOWNLOAD_DIR = "downloads"
HEADERS = {"User-Agent": "Mozilla/5.0"}
DEFAULT_OUTPUT_FILENAME = "course_metadata.json"
DEFAULT_SUBJECT_URLS = [
    "https://ocw.mit.edu/search/?q=python"
    "https://ocw.mit.edu/search/?t=Computer%20Science"
    "https://ocw.mit.edu/search/?d=Electrical%20Engineering%20and%20Computer%20Science",
    "https://ocw.mit.edu/search/?d=Mathematics",
]
DEFAULT_SUBJECT_URLS = [
    "https://ocw.mit.edu/search/?d=Electrical%20Engineering%20and%20Computer%20Science",
    "https://ocw.mit.edu/search/?d=Mathematics"
]


DEFAULT_QUERY_URL = "https://ocw.mit.edu/search/?q=python"
DEFAULT_MAX_COURSES_PER_SUBJECT = 5
DEFAULT_MAX_TOTAL_COURSES = 10
MAX_PAGES_PER_SUBJECT = 3  # Limit pages per subject for responsible scraping
COURSE_DELAY_SECONDS = 20  # Delay between processing courses
PAGE_DELAY_SECONDS = 10  # Delay between pages
REQUEST_DELAY_MIN = 1.0  # Minimum delay between requests
REQUEST_DELAY_MAX = 3.0  # Maximum delay between requests

DEFAULT_NUM_STUDENTS = 50
