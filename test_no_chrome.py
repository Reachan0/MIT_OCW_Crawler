#!/usr/bin/env python3
"""
Test script to verify the no-Chrome fallback functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.course_scrapper import CourseScraper

def test_requests_fallback():
    """Test the requests-based fallback for course discovery"""
    print("Testing requests-based fallback...")
    
    # Create scraper instance
    scraper = CourseScraper(
        subject_urls=["https://ocw.mit.edu/search/?l=Undergraduate"],
        download_dir="test_no_chrome",
        max_courses_per_subject=5
    )
    
    # Test the requests fallback method directly
    url = "https://ocw.mit.edu/search/?l=Undergraduate"
    subject_name = "Undergraduate"
    
    courses = scraper._discover_courses_with_requests(url, subject_name)
    
    print(f"Found {len(courses)} courses using requests fallback:")
    for i, course in enumerate(courses[:3]):  # Show first 3
        print(f"{i+1}. {course['title']}")
        print(f"   URL: {course['url']}")
        print(f"   Info: {course['info']}")
        print()
    
    return len(courses) > 0

if __name__ == "__main__":
    success = test_requests_fallback()
    print(f"Test {'PASSED' if success else 'FAILED'}")