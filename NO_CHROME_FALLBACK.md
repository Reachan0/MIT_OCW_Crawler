# No-Chrome Fallback Implementation

## 问题描述
在没有Chrome浏览器的服务器环境中，原始代码会崩溃并显示错误：
```
Message: unknown error: cannot find Chrome binary
```

## 解决方案

### 1. 修改 `_setup_selenium()` 方法
- 当Chrome初始化失败时，返回 `None` 而不是抛出异常
- 添加了适当的日志记录

### 2. 添加 `_discover_courses_with_requests()` 方法
- 使用 `requests` 和 `BeautifulSoup` 作为fallback
- 可以从静态HTML中提取基本课程信息
- 支持多种CSS选择器模式

### 3. 修改 `discover_courses()` 方法
- 检查 `self.driver` 是否为 `None`
- 如果为 `None`，使用requests-based fallback
- 如果不为 `None`，使用原始的Selenium逻辑

### 4. 修改清理逻辑
- 在 `finally` 块中检查 `driver` 是否为 `None`
- 避免在没有driver时尝试关闭浏览器

## 使用方法

### 有Chrome的环境（正常模式）
```bash
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?l=Graduate" --download-dir "courses"
```

### 没有Chrome的环境（fallback模式）
```bash
python main.py --multi --subject-urls "https://ocw.mit.edu/search/?l=Graduate" --download-dir "courses"
```

程序会自动检测Chrome是否可用，并相应地使用fallback机制。

## 限制

**MIT OCW使用JavaScript动态加载内容**，这意味着：

1. **Requests fallback** 只能获取静态HTML中的课程
2. **无法实现无限滚动**分页（需要JavaScript）
3. **课程数量会受限**于第一页的内容

## 建议

对于服务器环境，建议：

1. **安装Chrome/Chromium**：
   ```bash
   # Ubuntu/Debian
   sudo apt-get install chromium-browser
   
   # CentOS/RHEL
   sudo yum install chromium
   ```

2. **使用Docker**：
   ```dockerfile
   FROM python:3.9
   RUN apt-get update && apt-get install -y chromium-browser
   ```

3. **如果必须使用fallback**：
   - 接受有限的课程数量
   - 考虑使用多个不同的搜索URL来增加覆盖范围

## 测试

运行测试脚本验证fallback机制：
```bash
python test_fallback_demo.py
```

## 代码修改摘要

1. **src/course_scrapper.py**:
   - `_setup_selenium()`: 添加Chrome检测
   - `_discover_courses_with_requests()`: 新增fallback方法
   - `discover_courses()`: 添加driver=None处理
   - `finally` 块: 修改清理逻辑

2. **新增功能**:
   - 自动Chrome检测
   - 无缝fallback机制
   - 改进的错误处理
   - 更好的日志记录