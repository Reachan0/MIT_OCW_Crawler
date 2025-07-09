#!/usr/bin/env python3
"""
Test script to check course limit issues
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.course_scrapper import CourseScraper

def test_course_limit():
    """Test if there's a course limit issue"""
    print("=" * 60)
    print("Testing Course Limit Issues")
    print("=" * 60)
    
    # Test with a large subject like Computer Science
    test_urls = [
        "https://ocw.mit.edu/search/?d=Electrical%20Engineering%20and%20Computer%20Science",
        "https://ocw.mit.edu/search/?t=Computer%20Science"
    ]
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        print("-" * 40)
        
        scraper = CourseScraper(
            subject_urls=[url],
            download_dir="test_limit",
            max_courses_per_subject=None  # No limit
        )
        
        try:
            courses = scraper.discover_courses()
            print(f"✓ Found {len(courses)} courses")
            
            # Check if we hit the 1010 limit
            if len(courses) == 1010:
                print("⚠️  Hit 1010 course limit! This suggests the max_scroll_attempts was the issue.")
            elif len(courses) > 1010:
                print(f"✓ Successfully exceeded 1010 courses: {len(courses)}")
            else:
                print(f"✓ Found {len(courses)} courses (less than 1010)")
                
        except Exception as e:
            print(f"✗ Error: {e}")
        
        finally:
            # Clean up
            if hasattr(scraper, 'driver') and scraper.driver:
                scraper.driver.quit()

if __name__ == "__main__":
    test_course_limit()