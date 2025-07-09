# Standard library imports
import json
import logging
import os
import re
import time
import hashlib
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
from selenium.webdriver.common.action_chains import ActionChains

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
        
        # 生成基于URL的唯一标识符，用于区分不同的爬取任务
        self.task_id = self._generate_task_id(subject_urls, query_url)
        
        # Path for the combined content file
        self.combined_content_path = os.path.join(download_dir, f"scraped_content_{self.task_id}.json")
        
        # 添加进度文件路径
        self.progress_file = os.path.join(download_dir, f"scraper_progress_{self.task_id}.json")
        self.courses_found_file = os.path.join(download_dir, f"courses_found_{self.task_id}.json")
        
        # 调试打印：初始传入的URLs
        print("Debug - Original subject_urls received by CourseScraper:")
        for url in subject_urls:
            print(f"  - {url}")
        
        # 初始化分布式抓取器
        self.distributed = DistributedScraper(logger=self.logger)
        
        # 根据分布式配置决定要处理的学科URL
        self.subject_urls = self.distributed.get_subject_urls_for_node(subject_urls)
        
        # 调试打印：分布式处理后的URLs
        print("Debug - After distributed processing, subject_urls:")
        for url in self.subject_urls:
            print(f"  - {url}")
        
        # Prepare the final list of URLs to process
        self._urls_to_scrape = []
        
        # 检查是否使用自定义subject_urls（非默认值）
        using_custom_urls = subject_urls != DEFAULT_SUBJECT_URLS
        
        # 只有在使用默认subject_urls时，才添加query_url
        if not using_custom_urls and self.query_url:
            self._urls_to_scrape.append(self.query_url)
            
        self._urls_to_scrape.extend(self.subject_urls)
        self.logger.log_message(f"URLs to scrape: {self._urls_to_scrape}")
        self.logger.log_message(f"Task ID: {self.task_id}")

        # Initialize the browser
        self.driver = self._setup_selenium()
        
        # Check if WebDriver initialization was successful
        if self.driver is None:
            self.logger.log_message("Chrome WebDriver not available. Will use requests-based fallback for course discovery.", level=logging.WARNING)
        else:
            self.logger.log_message("Chrome WebDriver initialized successfully.")
        
        # 启动分布式同步线程（如果启用）
        if DISTRIBUTED_SCRAPING_ENABLED:
            self.distributed.start_sync()
            self.logger.log_message("分布式抓取模式已启用，节点ID: " + str(DISTRIBUTED_NODE_ID))
            
        # 加载已发现的课程（如果有）
        self._load_found_courses()
    
    def _generate_task_id(self, subject_urls, query_url):
        """根据URLs生成任务的唯一标识符"""
        # 将所有URL排序并连接起来
        all_urls = sorted(subject_urls)
        if query_url:
            all_urls.append(query_url)
        
        # 使用MD5生成一个短的哈希值作为任务ID
        url_string = "".join(all_urls)
        return hashlib.md5(url_string.encode('utf-8')).hexdigest()[:8]
    
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
                self.logger.log_message("Chrome not available. Will use requests-based fallback method.", level=logging.WARNING)
                return None  # Return None to indicate no WebDriver available
    
    def _discover_courses_with_requests(self, url, subject_name):
        """Fallback method to discover courses using requests when Chrome is not available."""
        import requests
        from bs4 import BeautifulSoup
        
        self.logger.log_message(f"Using requests-based fallback for course discovery from: {url}")
        courses = []
        
        try:
            # Make initial request
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Debug: Print page structure
            self.logger.log_message(f"Page title: {soup.title.string if soup.title else 'No title'}")
            
            # Look for different possible selectors
            selectors_to_try = [
                "article",
                ".course-item",
                ".course-card", 
                ".course-result",
                "div[class*='course']",
                "li[class*='course']",
                ".search-result",
                "div[class*='result']"
            ]
            
            for selector in selectors_to_try:
                elements = soup.select(selector)
                if elements:
                    self.logger.log_message(f"Found {len(elements)} elements with selector '{selector}'")
                    
                    # Try to extract courses using this selector
                    for element in elements:
                        course_info = self._extract_course_from_article(element)
                        if course_info:
                            course_info["subject"] = subject_name
                            course_info["subject_url"] = url
                            courses.append(course_info)
                            
                            # Also add to the global courses_found list
                            self.courses_found.append(course_info)
                            self._save_found_courses()
                            
                            # 打印实时进度
                            print(f"\r发现课程: {len(self.courses_found)} | 当前: {course_info['title']}", end="")
                    
                    if courses:
                        break
                else:
                    self.logger.log_message(f"No elements found with selector '{selector}'")
            
            self.logger.log_message(f"Successfully extracted {len(courses)} courses using requests fallback.")
            print()  # 换行
            return courses
            
        except Exception as e:
            self.logger.log_message(f"Error in requests-based course discovery: {e}", level=logging.ERROR)
            return []
    
    def _extract_course_from_article(self, article):
        """Extract course information from a single article element."""
        try:
            # Find the course title and URL
            title_link = article.find("a", href=True)
            if not title_link:
                return None
                
            title = title_link.get_text(strip=True)
            url = title_link["href"]
            
            # Make URL absolute if needed
            if url.startswith("/"):
                url = f"https://ocw.mit.edu{url}"
            
            # Find course info (level, department, etc.)
            info_text = "No info available"
            
            # Try multiple selectors for course info
            selectors = [
                "span.course-info",
                "div.course-info", 
                ".course-info",
                "p.course-info",
                ".course-level",
                ".course-department"
            ]
            
            for selector in selectors:
                info_elements = article.select(selector)
                if info_elements:
                    info_text = " | ".join([elem.get_text(strip=True) for elem in info_elements])
                    break
            
            # If no specific info found, try to extract from the article text
            if info_text == "No info available":
                # Look for common patterns
                article_text = article.get_text()
                
                # Look for course codes (e.g., "6.001", "18.01")
                import re
                course_code_match = re.search(r'(\d+\.\d+[A-Z]*)', article_text)
                if course_code_match:
                    info_text = course_code_match.group(1)
                
                # Look for level indicators
                if "Graduate" in article_text:
                    info_text += " | Graduate"
                elif "Undergraduate" in article_text:
                    info_text += " | Undergraduate"
            
            return {
                "title": title,
                "url": url,
                "info": info_text
            }
            
        except Exception as e:
            self.logger.log_message(f"Error extracting course from article: {e}", level=logging.WARNING)
            return None
    
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
                        
            except Exception as e:
                self.logger.log_message(f"Error extracting course data from article: {e}", level=logging.WARNING)
                continue
        
        return courses
    
    def _save_found_courses(self):
        """实时保存发现的课程列表到文件"""
        try:
            with open(self.courses_found_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "task_id": self.task_id,
                    "urls": self._urls_to_scrape,
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
                    # 检查任务ID是否匹配
                    saved_task_id = data.get('task_id')
                    saved_urls = data.get('urls', [])
                    
                    if saved_task_id == self.task_id and set(saved_urls) == set(self._urls_to_scrape):
                        self.courses_found = data.get('courses', [])
                        self.logger.log_message(f"加载已发现的课程: {len(self.courses_found)} 个")
                    else:
                        self.logger.log_message(f"URL集合已更改，将重新爬取课程列表")
                        self.courses_found = []
            except Exception as e:
                self.logger.log_message(f"加载已发现的课程失败: {e}", level=logging.ERROR)
                self.courses_found = []
    
    def _update_progress(self, stage, detail=None):
        """更新并保存进度信息"""
        progress = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task_id": self.task_id,
            "urls": self._urls_to_scrape,
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
        
        # 如果已经有发现的课程，检查是否为相同的URL集合
        if self.courses_found:
            self.logger.log_message(f"已发现 {len(self.courses_found)} 个课程。")
            self._update_progress("discovery", f"使用已有的 {len(self.courses_found)} 个课程")
            return self.courses_found

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
                # Check if we have a working driver
                if self.driver is None:
                    # Use requests-based fallback
                    self.logger.log_message(f"Using requests-based fallback for {subject_name}")
                    courses_from_requests = self._discover_courses_with_requests(current_url, subject_name)
                    
                    # Count courses found for this subject
                    for course in courses_from_requests:
                        if self.max_courses_per_subject is not None and courses_found_this_subject >= self.max_courses_per_subject:
                            self.logger.log_message(f"Reached max_courses_per_subject ({self.max_courses_per_subject}) for {subject_name}. Moving to next URL.", level=logging.INFO)
                            break
                        # Add to global courses list (courses are already processed in _discover_courses_with_requests)
                        courses_found_this_subject += 1
                    
                    self.logger.log_message(f"Extracted {len(courses_from_requests)} courses using requests fallback for {subject_name}.")
                    
                else:
                    # Use Selenium-based scraping (original logic)
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
                    
                    # Add subject info and add to global courses list
                    for course in courses_on_page:
                        if self.max_courses_per_subject is not None and courses_found_this_subject >= self.max_courses_per_subject:
                            self.logger.log_message(f"Reached max_courses_per_subject ({self.max_courses_per_subject}) for {subject_name}. Moving to next URL.", level=logging.INFO)
                            break # Stop adding courses from this page
                        course["subject"] = subject_name
                        course["subject_url"] = current_url
                        
                        # Add to global courses list
                        self.courses_found.append(course)
                        self._save_found_courses()
                        
                        courses_found_this_subject += 1
                        
                        # 打印实时进度
                        print(f"\r发现课程: {len(self.courses_found)} | 当前: {course['title']}", end="")
                    
                    print()  # 换行
                    
                    self.logger.log_message(f"Extracted {len(courses_on_page)} courses from initial page for {subject_name} (Total for this subject: {courses_found_this_subject}).")

                    # Check if we already hit the limit before trying pagination
                    if self.max_courses_per_subject is not None and courses_found_this_subject >= self.max_courses_per_subject:
                        continue # Move to the next subject/query URL

                    # 更新进度
                    self._update_progress("discovery", f"已抓取 {subject_name} 第1页，发现 {courses_found_this_subject} 个课程")

                    # Handle infinite scroll pagination
                    scroll_attempt = 1
                    max_scroll_attempts = 100  # Prevent infinite loops
                    courses_before_scroll = courses_found_this_subject
                    
                    while scroll_attempt <= max_scroll_attempts:
                        try:
                            # Scroll to bottom to trigger infinite scroll
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            
                            # Wait for potential new content to load
                            time.sleep(3)
                            
                            # Check if new content loaded by comparing course count
                            current_courses = self._extract_courses_from_page(self.driver.page_source)
                            
                            # If no new courses loaded, we've reached the end
                            if len(current_courses) <= courses_before_scroll:
                                self.logger.log_message(f"No new courses loaded after scrolling for {subject_name}. Reached end of results.")
                                break
                                
                            # Extract only the new courses (beyond what we already have)
                            new_courses = current_courses[courses_before_scroll:]
                            
                            # Add new courses and check limit
                            courses_added_this_scroll = 0
                            for course in new_courses:
                                if self.max_courses_per_subject is not None and courses_found_this_subject >= self.max_courses_per_subject:
                                    self.logger.log_message(f"Reached max_courses_per_subject ({self.max_courses_per_subject}) for {subject_name} after scroll {scroll_attempt}. Moving to next URL.", level=logging.INFO)
                                    break
                                course["subject"] = subject_name
                                course["subject_url"] = current_url
                                
                                # Add to global courses list  
                                self.courses_found.append(course)
                                self._save_found_courses()
                                
                                courses_found_this_subject += 1
                                courses_added_this_scroll += 1
                                
                                # 打印实时进度
                                print(f"\r发现课程: {len(self.courses_found)} | 当前: {course['title']}", end="")
                            
                            print()  # 换行
                            
                            self.logger.log_message(f"Scroll {scroll_attempt}: Found {courses_added_this_scroll} new courses for {subject_name} (Total: {courses_found_this_subject}).")
                            self._update_progress("discovery", f"已滚动 {subject_name} {scroll_attempt} 次，发现 {courses_found_this_subject} 个课程")
                            
                            # Update courses count for next iteration
                            courses_before_scroll = courses_found_this_subject
                            
                            # Break if limit reached
                            if self.max_courses_per_subject is not None and courses_found_this_subject >= self.max_courses_per_subject:
                                break
                                
                            scroll_attempt += 1
                            
                        except Exception as e:
                            self.logger.log_message(f"Error during infinite scroll for {subject_name}: {e}", level=logging.WARNING)
                            break
                        
            except Exception as e:
                self.logger.log_message(f"Error processing URL {current_url} ({subject_name}): {e}", level=logging.ERROR)
            
            # Add a delay before moving to the next subject/query
            self.logger.log_message(f"Finished processing URL: {current_url}")
            time.sleep(COURSE_DELAY_SECONDS)
        
        # Log final results
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
        
        # Limit the total number of courses to process if specified and not None
        courses_to_process = self.courses_found
        if max_total_courses is not None:
            courses_to_process = self.courses_found[:max_total_courses]
        
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
                try:
                    result = scraper.run()
                finally:
                    # Always cleanup resources
                    scraper.cleanup()
                
                if result:
                    # 检查是否有新内容被处理
                    result_path = result if isinstance(result, str) else result.get('path')
                    content_processed = result.get('content_processed', False) if isinstance(result, dict) else False
                    
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
                    
                    # 只有当实际处理了新内容时才等待
                    if content_processed:
                        # Add a significant delay between courses
                        self.logger.log_message(f"Waiting {COURSE_DELAY_SECONDS} seconds before next course...")
                        time.sleep(COURSE_DELAY_SECONDS)
                    else:
                        self.logger.log_message("Content already exists, skipping delay.")
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
                    
                    # 处理失败时也等待一段时间
                    self.logger.log_message(f"Waiting {COURSE_DELAY_SECONDS} seconds before next course...")
                    time.sleep(COURSE_DELAY_SECONDS)
            
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
                
                # 处理失败时也等待一段时间
                self.logger.log_message(f"Waiting {COURSE_DELAY_SECONDS} seconds before next course...")
                time.sleep(COURSE_DELAY_SECONDS)
            
            # 更新进度
            self._update_progress("processing")
        
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
            "task_id": self.task_id,
            "subject_urls": self.subject_urls,
            "total_courses_found": len(self.courses_found),
            "total_courses_processed": len(self.courses_processed),
            "total_courses_failed": len(self.courses_failed),
            "courses_processed": self.courses_processed,
            "courses_failed": self.courses_failed
        }
        
        report_path = os.path.join(self.download_dir, f"scraping_summary_{self.task_id}.json")
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
                "task_id": self.task_id,
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
        # 使用任务ID来区分不同URL的爬取结果
        combined_content_path = os.path.join(self.download_dir, f"scraped_content_{self.task_id}.json")
        try:
            with open(combined_content_path, "w", encoding="utf-8") as f:
                json.dump(combined_data, f, indent=2, ensure_ascii=False)
            self.logger.log_message(f"Successfully saved combined data to {combined_content_path}")
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
            
            # 更新combined_content_path为带有任务ID的路径
            combined_content_path = os.path.join(self.download_dir, f"scraped_content_{self.task_id}.json")
            
            # Remove empty files and folders
            self.remove_empty_files_and_folders()
            
            self.logger.log_message("=== MIT OCW Course Scraper Complete ===")
            self._update_progress("complete", "爬虫完成")
            
            if result: # Check if result is not None
                self.logger.log_message(f"Total discovered: {result['total_discovered']}")
                self.logger.log_message(f"Successfully processed: {result['total_processed']}")
                self.logger.log_message(f"Failed: {result['total_failed']}")
            if combined_success:
                self.logger.log_message(f"All content combined in: {combined_content_path}")
            
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
            if hasattr(self, 'driver') and self.driver is not None:
                try:
                    self.driver.quit()
                    self.logger.log_message("Browser closed.")
                except:
                    pass
            
            # Cleanup logger resources
            if hasattr(self, 'logger'):
                self.logger.cleanup()

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
