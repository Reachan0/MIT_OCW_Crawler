#!/usr/bin/env python3
"""
Test script to analyze MIT OCW pagination structure
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

def setup_driver():
    """Setup Chrome driver with same options as course scraper"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in background
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def analyze_pagination(driver, url):
    """Analyze pagination structure on MIT OCW search page"""
    print(f"Analyzing pagination for: {url}")
    
    try:
        # Navigate to the page
        driver.get(url)
        
        # Wait for content to load
        print("Waiting for page to load...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article"))
        )
        time.sleep(5)  # Extra time for dynamic content
        
        # Check page source for pagination-related elements
        page_source = driver.page_source
        
        # Look for various pagination patterns
        pagination_patterns = [
            ".pager",
            ".pagination", 
            "nav[aria-label*='pagination']",
            "button[aria-label*='next']",
            "button[aria-label*='previous']",
            "a[aria-label*='next']",
            "a[aria-label*='previous']",
            ".next-page-button",
            ".previous-page-button",
            "button.next-page",
            "a.next-page",
            ".page-next",
            ".page-previous",
            "[data-testid*='pagination']",
            "[data-testid*='next']",
            "[data-testid*='previous']",
            ".load-more",
            "[data-page]",
            ".page-link",
            ".page-item"
        ]
        
        found_elements = []
        for pattern in pagination_patterns:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, pattern)
                if elements:
                    found_elements.append({
                        "pattern": pattern,
                        "count": len(elements),
                        "elements": [{"tag": e.tag_name, "text": e.text.strip(), "aria_label": e.get_attribute("aria-label")} for e in elements[:3]]
                    })
            except Exception as e:
                print(f"Error checking pattern {pattern}: {e}")
        
        # Check for infinite scroll or dynamic loading
        initial_articles = len(driver.find_elements(By.CSS_SELECTOR, "article"))
        print(f"Found {initial_articles} articles initially")
        
        # Try scrolling to see if more content loads
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        
        after_scroll_articles = len(driver.find_elements(By.CSS_SELECTOR, "article"))
        print(f"Found {after_scroll_articles} articles after scrolling")
        
        # Look for URL-based pagination
        current_url = driver.current_url
        print(f"Current URL: {current_url}")
        
        # Check if there are any buttons or links that might be pagination
        all_buttons = driver.find_elements(By.CSS_SELECTOR, "button")
        all_links = driver.find_elements(By.CSS_SELECTOR, "a")
        
        print(f"Total buttons found: {len(all_buttons)}")
        print(f"Total links found: {len(all_links)}")
        
        # Look for buttons/links with pagination-related text
        pagination_text_patterns = ["next", "previous", "more", "load", "page"]
        potential_pagination = []
        
        for button in all_buttons:
            text = button.text.lower()
            aria_label = (button.get_attribute("aria-label") or "").lower()
            for pattern in pagination_text_patterns:
                if pattern in text or pattern in aria_label:
                    potential_pagination.append({
                        "type": "button",
                        "text": button.text,
                        "aria_label": button.get_attribute("aria-label"),
                        "class": button.get_attribute("class"),
                        "id": button.get_attribute("id")
                    })
                    break
        
        for link in all_links:
            text = link.text.lower()
            aria_label = (link.get_attribute("aria-label") or "").lower()
            href = link.get_attribute("href") or ""
            for pattern in pagination_text_patterns:
                if pattern in text or pattern in aria_label or "page=" in href:
                    potential_pagination.append({
                        "type": "link",
                        "text": link.text,
                        "aria_label": link.get_attribute("aria-label"),
                        "href": href,
                        "class": link.get_attribute("class"),
                        "id": link.get_attribute("id")
                    })
                    break
        
        results = {
            "url": url,
            "initial_articles": initial_articles,
            "after_scroll_articles": after_scroll_articles,
            "found_pagination_elements": found_elements,
            "potential_pagination_elements": potential_pagination,
            "has_infinite_scroll": after_scroll_articles > initial_articles
        }
        
        return results
        
    except Exception as e:
        print(f"Error analyzing pagination: {e}")
        return {"error": str(e)}

def main():
    """Main function to test pagination"""
    test_urls = [
        "https://ocw.mit.edu/search/?d=Mathematics",
        "https://ocw.mit.edu/search/?q=python",
        "https://ocw.mit.edu/search/?d=Computer%20Science"
    ]
    
    driver = setup_driver()
    
    try:
        for url in test_urls:
            print(f"\n{'='*80}")
            results = analyze_pagination(driver, url)
            print(json.dumps(results, indent=2))
            print(f"{'='*80}\n")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()