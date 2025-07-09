#!/usr/bin/env python3
"""
验证脚本：检查Non-Credit课程数量的准确性
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.course_scrapper import CourseScraper
import json

def test_non_credit_courses():
    """测试Non-Credit课程的抓取准确性"""
    print("="*60)
    print("验证 Non-Credit 课程数量")
    print("="*60)
    
    url = "https://ocw.mit.edu/search/?l=Non-Credit"
    
    # 创建scraper实例
    scraper = CourseScraper(
        subject_urls=[url],
        download_dir="test_non_credit",
        max_courses_per_subject=500  # 设置足够大的限制
    )
    
    print(f"目标URL: {url}")
    print(f"你观察到的网页显示: 64门课程")
    print(f"让我们看看脚本实际抓取了什么...\n")
    
    # 运行课程发现
    try:
        courses = scraper.discover_courses()
        
        print(f"脚本抓取到的课程数量: {len(courses)}")
        print("\n前10门课程:")
        print("-" * 40)
        
        for i, course in enumerate(courses[:10]):
            print(f"{i+1}. {course['title']}")
            print(f"   URL: {course['url']}")
            print(f"   信息: {course['info']}")
            print()
        
        # 检查是否有重复
        urls = [course['url'] for course in courses]
        unique_urls = set(urls)
        
        print(f"去重后的课程数量: {len(unique_urls)}")
        if len(urls) != len(unique_urls):
            print(f"⚠️  发现 {len(urls) - len(unique_urls)} 个重复课程")
            
            # 显示重复的课程
            from collections import Counter
            duplicates = [url for url, count in Counter(urls).items() if count > 1]
            print("重复的课程URL:")
            for dup_url in duplicates[:5]:  # 显示前5个重复
                print(f"  - {dup_url}")
        
        # 检查课程类型
        print(f"\n课程信息分析:")
        print("-" * 40)
        
        # 按信息字段分类
        info_types = {}
        for course in courses:
            info = course.get('info', 'Unknown')
            if info not in info_types:
                info_types[info] = 0
            info_types[info] += 1
        
        for info_type, count in sorted(info_types.items()):
            print(f"{info_type}: {count}门课程")
        
        # 保存详细结果用于人工检查
        output_file = "non_credit_courses_analysis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total_courses": len(courses),
                "unique_courses": len(unique_urls),
                "duplicates": len(urls) - len(unique_urls),
                "info_types": info_types,
                "courses": courses
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n详细分析已保存到: {output_file}")
        
        return courses
        
    except Exception as e:
        print(f"错误: {e}")
        return []
    
    finally:
        # 清理
        if hasattr(scraper, 'driver') and scraper.driver:
            scraper.driver.quit()

def manual_check():
    """手动检查网页内容"""
    print("\n" + "="*60)
    print("手动验证建议")
    print("="*60)
    print("1. 打开浏览器访问: https://ocw.mit.edu/search/?l=Non-Credit")
    print("2. 手动滚动到页面底部，观察是否有更多课程加载")
    print("3. 检查是否有'加载更多'按钮或分页")
    print("4. 计算实际显示的课程数量")
    print("5. 查看浏览器开发者工具的Network标签，看AJAX请求")

if __name__ == "__main__":
    courses = test_non_credit_courses()
    manual_check()
    
    print(f"\n" + "="*60)
    print("总结")
    print("="*60)
    print(f"脚本抓取: {len(courses)}门课程")
    print(f"网页显示: 64门课程")
    print(f"差异: {len(courses) - 64}门课程")
    
    if len(courses) > 64:
        print("\n可能的原因:")
        print("1. 网页有显示限制，但实际数据更多")
        print("2. 脚本抓取了重复内容")
        print("3. 脚本抓取了其他类型的内容")
        print("4. 网站的无限滚动机制与预期不同")
    
    print(f"\n请检查生成的 'non_credit_courses_analysis.json' 文件")
    print("来确认抓取的课程是否正确。")