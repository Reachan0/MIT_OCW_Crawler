import argparse
import os
import shutil
from src.content_scrapper import ContentScraper
from constants import (
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_SUBJECT_URLS,
    DEFAULT_QUERY_URL,
    DEFAULT_MAX_COURSES_PER_SUBJECT,
    DEFAULT_MAX_TOTAL_COURSES,
    DEFAULT_COURSE_URL,
    SUBJECT_CATEGORIES,
    DISTRIBUTED_SCRAPING_ENABLED,
    DISTRIBUTED_NODE_ID,
    DISTRIBUTED_TOTAL_NODES,
    DISTRIBUTED_DB_PATH
)

def parse_args():
    parser = argparse.ArgumentParser(description='MIT OCW Course Scraper')
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--single', action='store_true', help='Scrape a single course')
    mode_group.add_argument('--multi', action='store_true', help='Scrape multiple courses')
    
    # Single course mode arguments
    single_group = parser.add_argument_group('Single Course Options')
    single_group.add_argument('--course-url', type=str, default=DEFAULT_COURSE_URL,
                            help=f'URL of the course to scrape (default: {DEFAULT_COURSE_URL})')
    
    # Multiple courses mode arguments
    multi_group = parser.add_argument_group('Multiple Courses Options')
    multi_group.add_argument('--subject-urls', type=str, nargs='+', default=DEFAULT_SUBJECT_URLS,
                           help='List of subject URLs to scrape')
    multi_group.add_argument('--subject-category', type=str, choices=SUBJECT_CATEGORIES.keys(),
                           help='使用预定义的学科类别，如：cs、math、physics等')
    multi_group.add_argument('--query-url', type=str, default=DEFAULT_QUERY_URL,
                           help=f'Search query URL (default: {DEFAULT_QUERY_URL})')
    multi_group.add_argument('--max-courses-per-subject', type=int, 
                           default=DEFAULT_MAX_COURSES_PER_SUBJECT,
                           help=f'Maximum number of courses to scrape per subject (default: {DEFAULT_MAX_COURSES_PER_SUBJECT})')
    multi_group.add_argument('--max-total-courses', type=int, 
                           default=DEFAULT_MAX_TOTAL_COURSES,
                           help=f'Maximum total number of courses to scrape (default: {DEFAULT_MAX_TOTAL_COURSES})')
    
    # Common arguments
    parser.add_argument('--download-dir', type=str, default=DEFAULT_DOWNLOAD_DIR,
                       help=f'Directory to save downloaded content (default: {DEFAULT_DOWNLOAD_DIR})')
    parser.add_argument('--force-refresh', action='store_true',
                       help='Force refresh all content - deletes existing downloaded data and progress files')
    
    # 分布式抓取选项
    distributed_group = parser.add_argument_group('Distributed Scraping Options')
    distributed_group.add_argument('--distributed', action='store_true', 
                                 help='启用分布式抓取模式')
    distributed_group.add_argument('--node-id', type=int, default=DISTRIBUTED_NODE_ID,
                                 help=f'当前节点ID (default: {DISTRIBUTED_NODE_ID})')
    distributed_group.add_argument('--total-nodes', type=int, default=DISTRIBUTED_TOTAL_NODES,
                                 help=f'总节点数 (default: {DISTRIBUTED_TOTAL_NODES})')
    distributed_group.add_argument('--db-path', type=str, default=DISTRIBUTED_DB_PATH,
                                 help=f'分布式数据库路径 (default: {DISTRIBUTED_DB_PATH})')
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 处理force-refresh选项 - 删除现有数据
    if args.force_refresh:
        print("Force refresh requested. Clearing existing data...")
        # 删除下载目录
        if os.path.exists(args.download_dir):
            shutil.rmtree(args.download_dir)
            print(f"Removed download directory: {args.download_dir}")
        
        # 删除分布式数据库
        if os.path.exists(DISTRIBUTED_DB_PATH):
            os.remove(DISTRIBUTED_DB_PATH)
            print(f"Removed distributed database: {DISTRIBUTED_DB_PATH}")
    
    # 设置分布式抓取配置
    if args.distributed:
        # 这些值会影响constants中的值，从而影响分布式抓取器的行为
        import constants
        constants.DISTRIBUTED_SCRAPING_ENABLED = True
        constants.DISTRIBUTED_NODE_ID = args.node_id
        constants.DISTRIBUTED_TOTAL_NODES = args.total_nodes
        constants.DISTRIBUTED_DB_PATH = args.db_path
    
    # Create download directory if it doesn't exist
    os.makedirs(args.download_dir, exist_ok=True)
    
    # 处理特殊的数值限制参数
    max_total_courses = args.max_total_courses
    if max_total_courses is not None and max_total_courses <= 0:
        max_total_courses = None  # 0或负数表示不限制
        
    max_courses_per_subject = args.max_courses_per_subject
    if max_courses_per_subject is not None and max_courses_per_subject <= 0:
        max_courses_per_subject = None  # 0或负数表示不限制
    
    if args.single:
        # Single course mode
        scraper = ContentScraper(
            course_url=args.course_url,
            download_dir=args.download_dir
        )
        result_path = scraper.run()
        if result_path:
            print(f"Successfully scraped course. Output saved to: {result_path}")
        else:
            print("Failed to scrape course.")
    
    else:  # args.multi
        # 如果指定了学科类别，使用预定义的URL
        subject_urls = args.subject_urls
        if args.subject_category:
            subject_urls = SUBJECT_CATEGORIES[args.subject_category]
            print(f"Using predefined {args.subject_category} URLs: {len(subject_urls)} URLs")

        # 调试打印
        print("Debug - Subject URLs to be passed to CourseScraper:")
        for url in subject_urls:
            print(f"  - {url}")
        print(f"Debug - Query URL: {args.query_url}")

        # Multiple courses mode
        from src.course_scrapper import CourseScraper
        scraper = CourseScraper(
            subject_urls=subject_urls,
            download_dir=args.download_dir,
            query_url=args.query_url,
            max_courses_per_subject=max_courses_per_subject
        )
        result = scraper.run(max_total_courses=max_total_courses)
        if result:
            print(f"Total courses discovered: {result['total_discovered']}")
            print(f"Successfully processed: {result['total_processed']}")
            print(f"Failed: {result['total_failed']}")

if __name__ == "__main__":
    main()
