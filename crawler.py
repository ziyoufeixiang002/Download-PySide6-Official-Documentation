import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time
import json
from collections import deque
import re
import os

class KotlinDocsCrawler:
    def __init__(self, base_urls, max_concurrent=10):
        self.base_urls = base_urls
        self.visited = set()
        self.to_visit = deque(base_urls)
        self.all_links = set(base_urls)
        self.max_concurrent = max_concurrent
        self.session = None
        
        # 媒体文件扩展名过滤
        self.media_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
            '.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mov', '.webm',
            '.pdf', '.zip', '.tar', '.gz'
        }
        
    async def init_session(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close_session(self):
        if self.session:
            await self.session.close()
    
    def is_valid_url(self, url):
        """检查URL是否符合要求"""
        if not url.startswith('https://kotlinlang.org/'):
            return False
        
        # 只保留docs和api路径
        if not (url.startswith('https://kotlinlang.org/docs') or 
                url.startswith('https://kotlinlang.org/api')):
            return False
        
        # 过滤媒体文件
        parsed = urlparse(url)
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in self.media_extensions):
            return False
        
        # 过滤锚点链接
        if '#' in url:
            url = url.split('#')[0]
        
        return url
    
    async def fetch_page(self, url):
        """异步获取页面内容"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'text/html' in content_type:
                        return await response.text()
                    else:
                        print(f"跳过非HTML内容: {url} - {content_type}")
                else:
                    print(f"HTTP {response.status}: {url}")
        except Exception as e:
            print(f"请求失败 {url}: {e}")
        return None
    
    def extract_links(self, html, base_url):
        """从HTML中提取链接"""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            valid_url = self.is_valid_url(full_url)
            if valid_url and valid_url not in self.visited:
                links.add(valid_url)
        
        return links
    
    async def crawl(self):
        """主爬取函数"""
        await self.init_session()
        start_time = time.time()
        
        while self.to_visit and time.time() - start_time < 21000:  # 5.8小时安全边界
            batch_urls = []
            while self.to_visit and len(batch_urls) < self.max_concurrent:
                url = self.to_visit.popleft()
                if url not in self.visited:
                    self.visited.add(url)
                    batch_urls.append(url)
            
            if not batch_urls:
                break
            
            # 并发处理批次URL
            tasks = [self.process_url(url) for url in batch_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for result in results:
                if isinstance(result, Exception):
                    print(f"处理URL时出错: {result}")
                    continue
                
                if result and isinstance(result, set):
                    new_links = result - self.all_links
                    self.all_links.update(new_links)
                    self.to_visit.extend(new_links)
            
            print(f"已爬取: {len(self.visited)}, 待爬取: {len(self.to_visit)}, 总链接: {len(self.all_links)}")
            
            # 礼貌延迟
            await asyncio.sleep(0.1)
        
        await self.close_session()
        return self.all_links
    
    async def process_url(self, url):
        """处理单个URL"""
        html = await self.fetch_page(url)
        if html:
            return self.extract_links(html, url)
        return set()

async def main():
    base_urls = [
        "https://kotlinlang.org/docs/",
        "https://kotlinlang.org/api/"
    ]
    
    crawler = KotlinDocsCrawler(base_urls, max_concurrent=20)
    links = await crawler.crawl()
    
    # 保存结果
    with open('kotlin_links.json', 'w', encoding='utf-8') as f:
        json.dump(sorted(list(links)), f, indent=2)
    
    print(f"爬取完成! 总共找到 {len(links)} 个链接")
    
    # 也保存为文本文件
    with open('kotlin_links.txt', 'w', encoding='utf-8') as f:
        for link in sorted(links):
            f.write(link + '\n')

if __name__ == "__main__":
    asyncio.run(main())
