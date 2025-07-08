# Standard library imports
import json
import logging
import os
import re
import time
from urllib.parse import parse_qs, urljoin, urlparse

# Third-party imports
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Local imports
from constants import *
from src.content_scrapper import ContentScraper
from src.utils.logger import Logger
from src.utils.distributed import DistributedScraper


class CourseScraper:
    """Scraper that discovers and processes multiple courses."""
    
    def __init__(self, subject_urls=DEFAULT_SUBJECT_URLS, download_dir=DEFAULT_DOWNLOAD_DIR, query_url=DEFAULT_QUERY_URL, max_courses_per_subject=None):
        self.query_url = query_url
        self.max_courses_per_subject = max_courses_per_subject # Limit courses discovered per subject/query
        self.download_dir = download_dir
        self.logger = Logger("CourseScraperScraper", see_time=True, console_log=True)
        self._ensure_dir_exists(download_dir)
        
        # Keep track of courses we've found and processed
        self.courses_found = []
        self.courses_processed = []
        self.courses_failed = []
        
        # Path for the combined content file
        self.combined_content_path = os.path.join(download_dir, "scraped_content.json")
        
        # 添加进度文件路径
        self.progress_file = os.path.join(download_dir, "scraper_progress.json")
        self.courses_found_file = os.path.join(download_dir, "courses_found.json")
        
        # 初始化分布式抓取器
        self.distributed = DistributedScraper(logger=self.logger)
        
        # 根据分布式配置决定要处理的学科URL
        self.subject_urls = self.distributed.get_subject_urls_for_node(subject_urls)
        
        # Prepare the final list of URLs to process
        self._urls_to_scrape = []
        if self.query_url:
            self._urls_to_scrape.append(self.query_url)
        self._urls_to_scrape.extend(self.subject_urls)
        self.logger.log_message(f"URLs to scrape: {self._urls_to_scrape}")

        # Initialize the browser
        self.driver = self._setup_selenium()
        
        # 启动分布式同步线程（如果启用）
        if DISTRIBUTED_SCRAPING_ENABLED:
            self.distributed.start_sync()
            self.logger.log_message("分布式抓取模式已启用，节点ID: " + str(DISTRIBUTED_NODE_ID))
            
        # 加载已发现的课程（如果有）
        self._load_found_courses()
    
    def _extract_subject_from_url(self, subject_url):
        """Extract subject name from URL, handling d=, t=, and q= parameters."""
        try:
            parsed_url = urlparse(subject_url)
            query_params = parse_qs(parsed_url.query)
            
            # Check for d=, t=, or q= parameters
            subject = None
            subject_prefix = "Subject" # Default prefix
            if 'd' in query_params:
                subject = query_params['d'][0]
                subject_prefix = "Department"
            elif 't' in query_params:
                subject = query_params['t'][0]
                subject_prefix = "Topic"
            elif 'q' in query_params:
                subject = query_params['q'][0]
                subject_prefix = "Search"

            if subject:
                # Clean the subject name - remove URL encoding and special characters
                subject = subject.replace('%20', ' ')
                subject = re.sub(r'[<>:"/\\|?*]', '', subject).strip()

                # Specific logic for known subjects (optional simplification)
                if "Computer Science" in subject and subject_prefix != "Search":
                    return "Computer Science"
                elif "Mathematics" in subject and subject_prefix != "Search":
                    return "Mathematics"
                
                # For searches or other departments/topics, create a unique name
                if subject_prefix == "Search":
                     # Limit length for directory names
                    safe_query = re.sub(r'\W+', '_', subject) # Replace non-alphanumeric with underscore
                    return f"Search_{safe_query[:30]}" # Truncate long queries
                elif subject_prefix == "Department" or subject_prefix == "Topic":
                     # Use the first part for multi-part names if needed
                    return subject.split(" and ")[0]

            return "General"  # Default if no relevant parameter found
        except Exception as e:
            self.logger.log_message(f"Error extracting subject from {subject_url}: {e}", level=logging.WARNING)
            return "General"  # Fallback in case of any error
    
    def _create_subject_directories(self):
        """Create directories for each subject."""
        subject_dirs = {}
        for subject_url in self.subject_urls:
            subject_name = self._extract_subject_from_url(subject_url)
            subject_dir = os.path.join(self.download_dir, subject_name)
            self._ensure_dir_exists(subject_dir)
            subject_dirs[subject_url] = subject_dir
        return subject_dirs
        
    def _ensure_dir_exists(self, directory):
        """Ensures the specified directory exists."""
        os.makedirs(directory, exist_ok=True)
        
    def _setup_selenium(self):
        """Sets up the Selenium WebDriver for browsing course pages."""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in background
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            self.logger.log_message("Successfully initialized Chrome WebDriver.")
            return driver
        except Exception as e:
            self.logger.log_message(f"Error setting up Chrome WebDriver: {e}", level=logging.ERROR)
            try:
                # Fallback to direct instantiation
                driver = webdriver.Chrome(options=options)
                self.logger.log_message("Successfully initialized Chrome WebDriver with fallback method.")
                return driver
            except Exception as e2:
                self.logger.log_message(f"Failed to initialize Chrome WebDriver with fallback: {e2}", level=logging.ERROR)
                raise RuntimeError("Could not initialize WebDriver. Please ensure Chrome and ChromeDriver are installed.")
    
    def _extract_courses_from_page(self, html_content):
        """Extracts course information from the page HTML."""
        soup = BeautifulSoup(html_content, "html.parser")
        courses = []
        
        # Using the selector pattern from get_pages.py
        course_articles = soup.find_all("article")
        self.logger.log_message(f"Found {len(course_articles)} course articles on this page.")
        
        for article in course_articles:
            try:
                # Extract title
                title_span = article.find("span", id=lambda x: x and x.startswith("search-result-"))
                if title_span:
                    title = title_span.text.strip()
                    
                    # Get URL
                    link = article.find("a", href=True)
                    url = urljoin(BASE_URL, link['href']) if link else None
                    
                    if url:  # Only add if we have a valid URL
                        # Get course number and department info if available
                        header = article.find("div", class_="resource-type")
                        course_info = header.text.strip() if header else "Unknown Course Info"
                        
                        courses.append({
                            "title": title,
                            "url": url,
                            "info": course_info
                        })
                        
                        # 实时保存发现的课程
                        self.courses_found.append({
                            "title": title,
                            "url": url,
                            "info": course_info
                        })
                        self._save_found_courses()
                        
                        # 打印实时进度
                        print(f"\r发现课程: {len(self.courses_found)} | 当前: {title}", end="")
            except Exception as e:
                self.logger.log_message(f"Error extracting course data from article: {e}", level=logging.WARNING)
                continue
        
        print()  # 换行
        return courses
    
    def _save_found_courses(self):
        """实时保存发现的课程列表到文件"""
        try:
            with open(self.courses_found_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_courses_found": len(self.courses_found),
                    "courses": self.courses_found
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.log_message(f"保存发现的课程失败: {e}", level=logging.ERROR)
    
    def _load_found_courses(self):
        """加载之前发现的课程列表"""
        if os.path.exists(self.courses_found_file):
            try:
                with open(self.courses_found_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.courses_found = data.get('courses', [])
                    self.logger.log_message(f"加载已发现的课程: {len(self.courses_found)} 个")
            except Exception as e:
                self.logger.log_message(f"加载已发现的课程失败: {e}", level=logging.ERROR)
                self.courses_found = []
    
    def _update_progress(self, stage, detail=None):
        """更新并保存进度信息"""
        progress = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "detail": detail,
            "total_courses_found": len(self.courses_found),
            "total_courses_processed": len(self.courses_processed),
            "total_courses_failed": len(self.courses_failed)
        }
        
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.log_message(f"保存进度信息失败: {e}", level=logging.ERROR)
        
        # 打印进度条
        processed = len(self.courses_processed)
        failed = len(self.courses_failed)
        total = len(self.courses_found) or 1  # 避免除以零
        progress_percent = (processed + failed) / total * 100
        
        bar_length = 30
        filled_length = int(bar_length * progress_percent / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        print(f"\r进度: [{bar}] {progress_percent:.1f}% | 发现: {total} | 成功: {processed} | 失败: {failed}", end="")
        if stage != "processing":
            print()  # 只有在处理阶段结束时换行

    def discover_courses(self):
        """Discovers courses from the query URL and subject URLs, respecting limits."""
        self._update_progress("discovery", "开始发现课程")
        
        # 如果已经有发现的课程，询问是否继续
        if self.courses_found:
            self.logger.log_message(f"已发现 {len(self.courses_found)} 个课程。跳过发现阶段。")
            self._update_progress("discovery", f"跳过发现阶段，使用已有的 {len(self.courses_found)} 个课程")
            return self.courses_found

        all_courses = []

        # Use the prepared list of URLs
        for url_index, current_url in enumerate(self._urls_to_scrape):
            subject_name = self._extract_subject_from_url(current_url)
            self.logger.log_message(f"Discovering courses for: {subject_name} ({current_url})")
            self._update_progress("discovery", f"正在抓取 {subject_name} ({url_index+1}/{len(self._urls_to_scrape)})")

            # Create directory for this subject/query
            subject_dir = os.path.join(self.download_dir, subject_name)
            self._ensure_dir_exists(subject_dir)

            courses_found_this_subject = 0 # Counter for this specific URL

            try:
                # Navigate to the subject/query page
                self.driver.get(current_url)

                # Wait for the course articles to load
                wait_time = 20  # Seconds to wait for page load
                try:
                    WebDriverWait(self.driver, wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
                    )
                    self.logger.log_message(f"Course content loaded on initial page for {subject_name}.")
                    time.sleep(3)  # Small delay for render completion
                except TimeoutException:
                    self.logger.log_message(f"Timed out waiting for course content on initial page for {subject_name}. Skipping.", level=logging.WARNING)
                    continue

                # Process the first page
                courses_on_page = self._extract_courses_from_page(self.driver.page_source)
                
                # Add subject info and check limit
                for course in courses_on_page:
                    if self.max_courses_per_subject and courses_found_this_subject >= self.max_courses_per_subject:
                        self.logger.log_message(f"Reached max_courses_per_subject ({self.max_courses_per_subject}) for {subject_name}. Moving to next URL.", level=logging.INFO)
                        break # Stop adding courses from this page
                    course["subject"] = subject_name
                    course["subject_url"] = current_url
                    all_courses.append(course)
                    courses_found_this_subject += 1
                
                self.logger.log_message(f"Extracted {len(courses_on_page)} courses from initial page for {subject_name} (Total for this subject: {courses_found_this_subject}).")

                # Check if we already hit the limit before trying pagination
                if self.max_courses_per_subject and courses_found_this_subject >= self.max_courses_per_subject:
                    continue # Move to the next subject/query URL

                # 更新进度
                self._update_progress("discovery", f"已抓取 {subject_name} 第1页，发现 {courses_found_this_subject} 个课程")

                # Navigate through additional pages (up to MAX_PAGES_PER_SUBJECT)
                current_page = 1
                for page_num in range(2, MAX_PAGES_PER_SUBJECT + 1):
                    current_page = page_num

                    # Try to find and click the next page button
                    try:
                        next_button = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.next-page-button, a.next-page"))
                        )
                        next_button.click()
                        self.logger.log_message(f"Navigating to page {current_page} for {subject_name}")
                        self._update_progress("discovery", f"正在抓取 {subject_name} 第{current_page}页")

                        # Wait for the new page to load
                        time.sleep(PAGE_DELAY_SECONDS)  # Reasonable delay between page loads

                        # Wait for content on the new page
                        WebDriverWait(self.driver, wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
                        )

                        # Process this page
                        courses_on_page = self._extract_courses_from_page(self.driver.page_source)
                        
                        # Add subject info and check limit
                        courses_added_this_page = 0
                        for course in courses_on_page:
                            if self.max_courses_per_subject and courses_found_this_subject >= self.max_courses_per_subject:
                                self.logger.log_message(f"Reached max_courses_per_subject ({self.max_courses_per_subject}) for {subject_name} on page {current_page}. Moving to next URL.", level=logging.INFO)
                                break # Stop adding courses from this page
                            course["subject"] = subject_name
                            course["subject_url"] = current_url
                            all_courses.append(course)
                            courses_found_this_subject += 1
                            courses_added_this_page += 1
                        
                        self.logger.log_message(f"Extracted {courses_added_this_page} courses from page {current_page} for {subject_name} (Total for this subject: {courses_found_this_subject}).")
                        self._update_progress("discovery", f"已抓取 {subject_name} 第{current_page}页，发现 {courses_found_this_subject} 个课程")
                        
                        # Break outer loop (subjects) if limit reached
                        if self.max_courses_per_subject and courses_found_this_subject >= self.max_courses_per_subject:
                           break # Stop paginating for this subject
                           
                    except (TimeoutException, NoSuchElementException) as e:
                        self.logger.log_message(f"Could not navigate to page {current_page} for {subject_name}: {e}", level=logging.WARNING)
                        self.logger.log_message(f"Either reached the last page or navigation element not found for {subject_name}.")
                        break # Stop paginating for this subject
            
            except Exception as e:
                self.logger.log_message(f"Error processing URL {current_url} ({subject_name}): {e}", level=logging.ERROR)
            
            # Add a delay before moving to the next subject/query
            self.logger.log_message(f"Finished processing URL: {current_url}")
            time.sleep(COURSE_DELAY_SECONDS)
        
        # Update our discovered courses list and return it
        # 注意：我们已经在extract_courses_from_page中实时更新courses_found了
        # self.courses_found = all_courses
        self.logger.log_message(f"Total courses discovered across all URLs: {len(self.courses_found)}")
        self._update_progress("discovery", f"发现阶段完成，共发现 {len(self.courses_found)} 个课程")
        return self.courses_found
    
    def process_courses(self, max_total_courses=None):
        """Processes the discovered courses using ContentScraper, up to max_total_courses."""
        if not self.courses_found:
            self.logger.log_message("No courses to process. Run discover_courses() first.", level=logging.ERROR)
            return
        
        self._update_progress("processing", "开始处理课程")
        
        # Create subject directories (ensure they exist based on discovered courses)
        discovered_subjects = {c['subject'] for c in self.courses_found if 'subject' in c}
        for subject_name in discovered_subjects:
             subject_dir = os.path.join(self.download_dir, subject_name)
             self._ensure_dir_exists(subject_dir)
        # subject_dirs = self._create_subject_directories() # Can remove this if dirs created based on discovered
        
        # Limit the total number of courses to process if specified
        courses_to_process = self.courses_found[:max_total_courses] if max_total_courses else self.courses_found
        total_to_process = len(courses_to_process)
        
        self.logger.log_message(f"Starting to process {total_to_process} courses (out of {len(self.courses_found)} discovered).")
        
        for index, course in enumerate(courses_to_process):
            course_url = course.get('url')
            course_title = course.get('title')
            course_info = course.get('info')
            subject = course.get('subject', 'General')
            
            if not course_url:
                self.logger.log_message(f"Skipping course at index {index}: Missing URL", level=logging.WARNING)
                continue
            
            # 检查此URL是否应该由当前节点处理
            if not self.distributed.should_process_url(course_url):
                self.logger.log_message(f"跳过课程 {course_title}：由其他节点处理")
                continue
            
            self.logger.log_message(f"Processing course {index+1}/{total_to_process}: {course_title}")
            self._update_progress("processing", f"正在处理 {index+1}/{total_to_process}: {course_title}")
            
            try:
                # Determine the appropriate subject directory
                subject_dir = os.path.join(self.download_dir, subject)
                self._ensure_dir_exists(subject_dir)
                
                # Create and run a ContentScraper for this course
                scraper = ContentScraper(course_url=course_url, download_dir=subject_dir)
                result_path = scraper.run()
                
                if result_path:
                    self.courses_processed.append({
                        "title": course_title,
                        "url": course_url,
                        "info": course_info,
                        "subject": subject,
                        "output_path": result_path
                    })
                    self.logger.log_message(f"Successfully processed course: {course_title}")
                    # 标记为已处理成功
                    self.distributed.mark_as_processed(course_url, success=True)
                else:
                    self.courses_failed.append({
                        "title": course_title,
                        "url": course_url,
                        "info": course_info,
                        "subject": subject,
                        "reason": "ContentScraper returned None"
                    })
                    self.logger.log_message(f"Failed to process course: {course_title}", level=logging.ERROR)
                    # 标记为处理失败
                    self.distributed.mark_as_processed(course_url, success=False)
            
            except Exception as e:
                self.courses_failed.append({
                    "title": course_title,
                    "url": course_url,
                    "info": course_info,
                    "subject": subject,
                    "reason": str(e)
                })
                self.logger.log_message(f"Error processing course {course_title}: {e}", level=logging.ERROR)
                # 标记为处理失败
                self.distributed.mark_as_processed(course_url, success=False)
            
            # 更新进度
            self._update_progress("processing")
            
            # Add a significant delay between courses
            self.logger.log_message(f"Waiting {COURSE_DELAY_SECONDS} seconds before next course...")
            time.sleep(COURSE_DELAY_SECONDS)
        
        # Save a summary report
        self._save_summary_report()
        self._update_progress("complete", "处理完成")
        
        return {
            "total_discovered": len(self.courses_found),
            "total_processed": len(self.courses_processed),
            "total_failed": len(self.courses_failed)
        }
    
    def _save_summary_report(self):
        """Saves a summary report of the scraping process."""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "subject_urls": self.subject_urls,
            "total_courses_found": len(self.courses_found),
            "total_courses_processed": len(self.courses_processed),
            "total_courses_failed": len(self.courses_failed),
            "courses_processed": self.courses_processed,
            "courses_failed": self.courses_failed
        }
        
        report_path = os.path.join(self.download_dir, "scraping_summary.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.log_message(f"Saved scraping summary to {report_path}")
        except Exception as e:
            self.logger.log_message(f"Failed to save scraping summary: {e}", level=logging.ERROR)
    
    def _save_combined_content(self):
        """Loads all processed course files and combines them into a single scraped_content.json file."""
        self.logger.log_message("Combining all course data into a single file...")
        
        # Create the combined data structure
        combined_data = {
            "metadata": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_courses": len(self.courses_processed),
                "subjects": [
                    {
                        "url": url,
                        "name": self._extract_subject_from_url(url)
                    } for url in self.subject_urls
                ]
            },
            "courses": []
        }
        
        # Load and combine each successfully processed course
        for course_info in self.courses_processed:
            output_path = course_info.get("output_path")
            if output_path and os.path.exists(output_path):
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        course_data = json.load(f)
                        # Add source information to the course data
                        course_data["source_url"] = course_info.get("url")
                        course_data["course_info"] = course_info.get("info")
                        course_data["subject"] = course_info.get("subject", "General")
                        combined_data["courses"].append(course_data)
                        self.logger.log_message(f"Added course: {course_data.get('course_name')}")
                except Exception as e:
                    self.logger.log_message(f"Error loading course data from {output_path}: {e}", level=logging.ERROR)
        
        # Save the combined data to the main directory (not in a subject folder)
        try:
            with open(self.combined_content_path, "w", encoding="utf-8") as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)
            self.logger.log_message(f"Successfully saved combined data to {self.combined_content_path}")
            return True
        except Exception as e:
            self.logger.log_message(f"Failed to save combined data: {e}", level=logging.ERROR)
            return False
    
    def run(self, max_total_courses=None):
        """Runs the complete course discovery and processing workflow."""
        # Note: max_courses_per_subject is set during __init__
        try:
            self.logger.log_message("=== Starting MIT OCW Course Scraper ===")
            self._update_progress("start", "爬虫启动")
            
            # 打印分布式抓取信息
            if DISTRIBUTED_SCRAPING_ENABLED:
                stats = self.distributed.get_stats()
                self.logger.log_message(f"分布式抓取状态: 活跃节点 {stats['active_nodes']}，已处理 {stats['processed_courses']}，失败 {stats['failed_courses']}，进行中 {stats['in_progress_courses']}")
            
            # Discover courses (respecting max_courses_per_subject)
            self.discover_courses()
            
            # Process discovered courses (respecting max_total_courses)
            result = self.process_courses(max_total_courses=max_total_courses)
            
            # Combine all course data into a single file
            combined_success = self._save_combined_content()
            
            # Remove empty files and folders
            self.remove_empty_files_and_folders()
            
            self.logger.log_message("=== MIT OCW Course Scraper Complete ===")
            self._update_progress("complete", "爬虫完成")
            
            if result: # Check if result is not None
                self.logger.log_message(f"Total discovered: {result['total_discovered']}")
                self.logger.log_message(f"Successfully processed: {result['total_processed']}")
                self.logger.log_message(f"Failed: {result['total_failed']}")
            if combined_success:
                self.logger.log_message(f"All content combined in: {self.combined_content_path}")
            
            # 再次打印分布式抓取信息
            if DISTRIBUTED_SCRAPING_ENABLED:
                stats = self.distributed.get_stats()
                self.logger.log_message(f"分布式抓取最终状态: 活跃节点 {stats['active_nodes']}，已处理 {stats['processed_courses']}，失败 {stats['failed_courses']}，进行中 {stats['in_progress_courses']}")
            
            return result
        
        finally:
            # 停止分布式同步
            if DISTRIBUTED_SCRAPING_ENABLED:
                self.distributed.stop_sync()
                
            # Always close the browser
            if hasattr(self, 'driver'):
                try:
                    self.driver.quit()
                    self.logger.log_message("Browser closed.")
                except:
                    pass

    def remove_empty_files_and_folders(self):
        """Removes empty files and folders in the download directory."""
        for root, dirs, files in os.walk(self.download_dir):
            for file in files:
                if os.path.getsize(os.path.join(root, file)) == 0:
                    os.remove(os.path.join(root, file))
            for dir in dirs:
                if not os.listdir(os.path.join(root, dir)):
                    os.rmdir(os.path.join(root, dir))

if __name__ == "__main__":
    # For single course:
    # scraper = ContentScraper(course_url="https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/")
    # scraper.run()
    
    # For multiple courses: Search for 'python', then check default CS/Math subjects
    # Limit discovery to 5 courses per URL, and process a maximum total of 10 courses.
    scraper = CourseScraper(
        subject_urls=DEFAULT_SUBJECT_URLS,
        download_dir=DEFAULT_DOWNLOAD_DIR,
        query_url=DEFAULT_QUERY_URL,
        max_courses_per_subject=DEFAULT_MAX_COURSES_PER_SUBJECT
    )
    scraper.run(max_total_courses=DEFAULT_MAX_TOTAL_COURSES) # Process up to 10 courses overall
