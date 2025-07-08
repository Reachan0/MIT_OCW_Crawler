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

# 分布式抓取配置
DISTRIBUTED_SCRAPING_ENABLED = False  # 是否启用分布式抓取
DISTRIBUTED_NODE_ID = 1  # 当前节点ID，每个设备应不同
DISTRIBUTED_TOTAL_NODES = 1  # 总节点数
DISTRIBUTED_DB_PATH = "distributed_db.json"  # 用于存储已抓取课程的数据库路径
DISTRIBUTED_SYNC_INTERVAL = 300  # 同步间隔（秒）

# 学科分类URL列表，可根据不同学科分配给不同节点
SUBJECT_CATEGORIES = {
    "cs": [
        "https://ocw.mit.edu/search/?d=Electrical%20Engineering%20and%20Computer%20Science",
        "https://ocw.mit.edu/search/?t=Computer%20Science"
    ],
    "math": [
        "https://ocw.mit.edu/search/?d=Mathematics"
    ],
    "physics": [
        "https://ocw.mit.edu/search/?d=Physics"
    ],
    "biology": [
        "https://ocw.mit.edu/search/?d=Biology"
    ],
    "chemistry": [
        "https://ocw.mit.edu/search/?d=Chemistry"
    ],
    "economics": [
        "https://ocw.mit.edu/search/?d=Economics"
    ],
    "humanities": [
        "https://ocw.mit.edu/search/?d=Humanities"
    ],
    "management": [
        "https://ocw.mit.edu/search/?d=Sloan%20School%20of%20Management"
    ]
}
