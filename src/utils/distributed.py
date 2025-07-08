"""
分布式抓取工具模块，用于多设备协同爬取MIT OCW课程内容
"""

import os
import json
import time
import logging
import requests
from threading import Thread, Lock
from constants import (
    DISTRIBUTED_SCRAPING_ENABLED, 
    DISTRIBUTED_NODE_ID, 
    DISTRIBUTED_TOTAL_NODES, 
    DISTRIBUTED_DB_PATH,
    DISTRIBUTED_SYNC_INTERVAL
)

# 创建一个锁用于线程安全操作
db_lock = Lock()

class DistributedScraper:
    """分布式抓取协调器，负责协调多设备抓取过程，避免重复或遗漏"""
    
    def __init__(self, logger=None):
        """初始化分布式抓取协调器"""
        self.node_id = DISTRIBUTED_NODE_ID
        self.total_nodes = DISTRIBUTED_TOTAL_NODES
        self.db_path = DISTRIBUTED_DB_PATH
        self.sync_interval = DISTRIBUTED_SYNC_INTERVAL
        self.logger = logger or logging.getLogger(__name__)
        self.sync_running = False
        self.sync_thread = None
        
        # 初始化或加载数据库
        self._init_db()
        
    def _init_db(self):
        """初始化或加载分布式数据库"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
                self.logger.log_message(f"加载分布式数据库，共有 {len(self.db.get('processed_courses', []))} 条已处理课程记录")
            except Exception as e:
                self.logger.log_message(f"加载分布式数据库失败: {e}", level=logging.ERROR)
                self._create_new_db()
        else:
            self._create_new_db()
            
    def _create_new_db(self):
        """创建新的分布式数据库"""
        self.db = {
            "last_updated": time.time(),
            "nodes": {str(DISTRIBUTED_NODE_ID): {"last_active": time.time()}},
            "processed_courses": [],  # 已处理的课程URL列表
            "failed_courses": [],     # 处理失败的课程URL列表
            "in_progress_courses": {} # 正在处理的课程 {url: {"node_id": id, "start_time": time}}
        }
        self._save_db()
        self.logger.log_message("创建新的分布式数据库")
            
    def _save_db(self):
        """保存分布式数据库到文件"""
        with db_lock:
            try:
                with open(self.db_path, 'w', encoding='utf-8') as f:
                    json.dump(self.db, f, indent=2, ensure_ascii=False)
                self.logger.log_message("分布式数据库已保存", level=logging.DEBUG)
            except Exception as e:
                self.logger.log_message(f"保存分布式数据库失败: {e}", level=logging.ERROR)
                
    def start_sync(self):
        """启动后台同步线程"""
        if not DISTRIBUTED_SCRAPING_ENABLED:
            return
            
        if self.sync_thread is None or not self.sync_thread.is_alive():
            self.sync_running = True
            self.sync_thread = Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            self.logger.log_message("后台同步线程已启动")
            
    def stop_sync(self):
        """停止后台同步线程"""
        self.sync_running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5.0)
            self.logger.log_message("后台同步线程已停止")
            
    def _sync_loop(self):
        """后台同步循环"""
        while self.sync_running:
            try:
                self._heartbeat()
                time.sleep(self.sync_interval)
            except Exception as e:
                self.logger.log_message(f"同步过程出错: {e}", level=logging.ERROR)
                time.sleep(30)  # 出错后等待较短时间再重试
                
    def _heartbeat(self):
        """更新节点心跳并清理过期任务"""
        with db_lock:
            # 更新当前节点的活跃时间
            self.db["nodes"][str(self.node_id)] = {"last_active": time.time()}
            
            # 检查其他节点是否还活跃，如果超过2个同步间隔没有心跳，则认为节点已离线
            offline_threshold = time.time() - (self.sync_interval * 2)
            offline_nodes = []
            for node_id, info in self.db["nodes"].items():
                if info["last_active"] < offline_threshold:
                    offline_nodes.append(node_id)
                    
            # 处理离线节点正在处理的课程
            for url, info in list(self.db["in_progress_courses"].items()):
                node_id = str(info["node_id"])
                if node_id in offline_nodes or time.time() - info["start_time"] > 3600:  # 1小时超时
                    del self.db["in_progress_courses"][url]
                    self.logger.log_message(f"释放被离线节点 {node_id} 或超时任务占用的课程: {url}", level=logging.WARNING)
                    
            # 清理离线节点
            for node_id in offline_nodes:
                if node_id in self.db["nodes"]:
                    del self.db["nodes"][node_id]
                    self.logger.log_message(f"节点 {node_id} 已离线，从活跃节点列表中移除")
                    
            # 更新时间戳
            self.db["last_updated"] = time.time()
            
            # 保存更新后的数据库
            self._save_db()
            
    def should_process_url(self, course_url):
        """判断是否应该处理指定URL的课程
        
        Args:
            course_url: 课程URL
            
        Returns:
            bool: 如果该URL应该由当前节点处理，返回True；否则返回False
        """
        if not DISTRIBUTED_SCRAPING_ENABLED:
            return True
            
        with db_lock:
            # 如果URL已经被处理或正在处理，则跳过
            if course_url in self.db["processed_courses"]:
                self.logger.log_message(f"课程 {course_url} 已被处理，跳过", level=logging.DEBUG)
                return False
                
            if course_url in self.db["in_progress_courses"]:
                # 检查是否是由当前节点处理的
                info = self.db["in_progress_courses"][course_url]
                if info["node_id"] == self.node_id:
                    # 这是当前节点的任务，可能是重启后继续
                    return True
                    
                # 检查是否任务已超时
                if time.time() - info["start_time"] > 3600:  # 1小时超时
                    self.logger.log_message(f"课程 {course_url} 处理超时，重新分配", level=logging.WARNING)
                    del self.db["in_progress_courses"][course_url]
                else:
                    # 其他节点正在处理
                    self.logger.log_message(f"课程 {course_url} 正在被节点 {info['node_id']} 处理，跳过", level=logging.DEBUG)
                    return False
            
            # 使用URL的哈希值决定由哪个节点处理
            url_hash = hash(course_url) % self.total_nodes + 1
            if url_hash == self.node_id:
                # 标记为正在处理
                self.db["in_progress_courses"][course_url] = {
                    "node_id": self.node_id,
                    "start_time": time.time()
                }
                self._save_db()
                return True
            else:
                self.logger.log_message(f"课程 {course_url} 分配给节点 {url_hash}，当前节点 {self.node_id} 跳过", level=logging.DEBUG)
                return False
                
    def mark_as_processed(self, course_url, success=True):
        """标记课程为已处理状态
        
        Args:
            course_url: 课程URL
            success: 处理是否成功
        """
        if not DISTRIBUTED_SCRAPING_ENABLED:
            return
            
        with db_lock:
            # 从正在处理列表中移除
            if course_url in self.db["in_progress_courses"]:
                del self.db["in_progress_courses"][course_url]
                
            # 添加到已处理或失败列表
            if success:
                if course_url not in self.db["processed_courses"]:
                    self.db["processed_courses"].append(course_url)
                    self.logger.log_message(f"课程 {course_url} 已成功处理")
            else:
                if course_url not in self.db["failed_courses"]:
                    self.db["failed_courses"].append(course_url)
                    self.logger.log_message(f"课程 {course_url} 处理失败", level=logging.WARNING)
                    
            self._save_db()
            
    def get_subject_urls_for_node(self, all_subject_urls):
        """根据节点ID筛选该节点应处理的学科URL
        
        Args:
            all_subject_urls: 所有学科URL列表
            
        Returns:
            list: 当前节点应处理的学科URL列表
        """
        print("Debug - Inside distributed.py, received URLs:")
        for i, url in enumerate(all_subject_urls):
            print(f"  - [{i}] {url}")
            
        if not DISTRIBUTED_SCRAPING_ENABLED or self.total_nodes <= 1:
            print(f"Debug - Distributed mode not enabled or total_nodes={self.total_nodes}, returning all URLs")
            return all_subject_urls
            
        # 按节点ID均匀分配学科
        node_urls = []
        for i, url in enumerate(all_subject_urls):
            if (i % self.total_nodes) + 1 == self.node_id:
                node_urls.append(url)
                
        print(f"Debug - Distributed mode: node {self.node_id}/{self.total_nodes}, returning filtered URLs:")
        for url in node_urls:
            print(f"  - {url}")
                
        self.logger.log_message(f"节点 {self.node_id}/{self.total_nodes} 分配到 {len(node_urls)}/{len(all_subject_urls)} 个学科")
        return node_urls
        
    def get_stats(self):
        """获取分布式抓取统计数据
        
        Returns:
            dict: 统计数据
        """
        with db_lock:
            active_nodes = len(self.db["nodes"])
            processed = len(self.db["processed_courses"])
            failed = len(self.db["failed_courses"])
            in_progress = len(self.db["in_progress_courses"])
            
            return {
                "active_nodes": active_nodes,
                "processed_courses": processed,
                "failed_courses": failed,
                "in_progress_courses": in_progress,
                "last_updated": self.db["last_updated"]
            } 