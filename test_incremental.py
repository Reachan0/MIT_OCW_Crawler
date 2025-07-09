#!/usr/bin/env python3
"""
Test script to verify incremental crawling functionality
"""
import sys
import os
import json
import shutil
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.course_scrapper import CourseScraper

def test_incremental_crawling():
    """Test incremental crawling functionality"""
    print("=" * 60)
    print("Testing Incremental Crawling Functionality")
    print("=" * 60)
    
    test_dir = "test_incremental"
    test_url = "https://ocw.mit.edu/search/?l=Non-Credit"
    
    # Clean up any existing test data
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    print("\n1. First run - Normal mode (should discover all courses)")
    print("-" * 50)
    
    # First run - normal mode
    scraper1 = CourseScraper(
        subject_urls=[test_url],
        download_dir=test_dir,
        max_courses_per_subject=10,  # Limit to 10 for testing
        incremental=False
    )
    
    try:
        courses1 = scraper1.discover_courses()
        print(f"✓ First run found {len(courses1)} courses")
        
        # Save course URLs for comparison
        first_run_urls = {course['url'] for course in courses1}
        
    except Exception as e:
        print(f"✗ Error in first run: {e}")
        return
    finally:
        if hasattr(scraper1, 'driver') and scraper1.driver:
            scraper1.driver.quit()
    
    print("\n2. Second run - Incremental mode (should find 0 new courses)")
    print("-" * 50)
    
    # Second run - incremental mode with same URL
    scraper2 = CourseScraper(
        subject_urls=[test_url],
        download_dir=test_dir,
        max_courses_per_subject=10,  # Same limit
        incremental=True
    )
    
    try:
        courses2 = scraper2.discover_courses()
        print(f"✓ Second run found {len(courses2)} new courses")
        
        if len(courses2) == 0:
            print("✓ Incremental mode working correctly - no new courses found")
        else:
            print(f"⚠️  Expected 0 new courses, but found {len(courses2)}")
            
    except Exception as e:
        print(f"✗ Error in second run: {e}")
        return
    finally:
        if hasattr(scraper2, 'driver') and scraper2.driver:
            scraper2.driver.quit()
    
    print("\n3. Third run - Incremental mode with higher limit (should find new courses)")
    print("-" * 50)
    
    # Third run - incremental mode with higher limit
    scraper3 = CourseScraper(
        subject_urls=[test_url],
        download_dir=test_dir,
        max_courses_per_subject=20,  # Higher limit
        incremental=True
    )
    
    try:
        courses3 = scraper3.discover_courses()
        print(f"✓ Third run found {len(courses3)} new courses")
        
        if len(courses3) > 0:
            print("✓ Incremental mode working correctly - found new courses with higher limit")
        else:
            print("ℹ️  No new courses found even with higher limit (might be at max for this subject)")
            
    except Exception as e:
        print(f"✗ Error in third run: {e}")
        return
    finally:
        if hasattr(scraper3, 'driver') and scraper3.driver:
            scraper3.driver.quit()
    
    print("\n4. Check saved course files")
    print("-" * 50)
    
    # Check if the courses_found file exists and has correct structure
    courses_found_files = [f for f in os.listdir(test_dir) if f.startswith('courses_found_')]
    if courses_found_files:
        courses_found_file = os.path.join(test_dir, courses_found_files[0])
        try:
            with open(courses_found_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                total_saved = len(data.get('courses', []))
                print(f"✓ Saved courses file contains {total_saved} courses")
                
                # Verify that all courses from first run are in the saved file
                saved_urls = {course['url'] for course in data.get('courses', [])}
                if first_run_urls.issubset(saved_urls):
                    print("✓ All courses from first run are preserved in saved file")
                else:
                    print("⚠️  Some courses from first run are missing in saved file")
                    
        except Exception as e:
            print(f"✗ Error reading saved courses file: {e}")
    else:
        print("✗ No courses_found file found")
    
    print("\n" + "=" * 60)
    print("Incremental crawling test completed")
    print("=" * 60)
    
    # Clean up test directory
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    test_incremental_crawling()