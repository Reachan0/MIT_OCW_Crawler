import argparse
import os
from src.content_scrapper import ContentScraper
from constants import (
    DEFAULT_DOWNLOAD_DIR,
    DEFAULT_SUBJECT_URLS,
    DEFAULT_QUERY_URL,
    DEFAULT_MAX_COURSES_PER_SUBJECT,
    DEFAULT_MAX_TOTAL_COURSES,
    DEFAULT_COURSE_URL
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
    
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Create download directory if it doesn't exist
    os.makedirs(args.download_dir, exist_ok=True)
    
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
        # Multiple courses mode
        from src.content_scrapper import CourseScraper
        scraper = CourseScraper(
            subject_urls=args.subject_urls,
            download_dir=args.download_dir,
            query_url=args.query_url,
            max_courses_per_subject=args.max_courses_per_subject
        )
        result = scraper.run(max_total_courses=args.max_total_courses)
        if result:
            print(f"Total courses discovered: {result['total_discovered']}")
            print(f"Successfully processed: {result['total_processed']}")
            print(f"Failed: {result['total_failed']}")

if __name__ == "__main__":
    main()
