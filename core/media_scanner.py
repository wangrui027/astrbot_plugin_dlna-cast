#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
媒体文件扫描器
支持WebDAV和SMB协议的目录浏览和文件过滤
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Optional
from urllib.parse import quote, unquote

import requests
from requests.auth import HTTPBasicAuth


@dataclass
class FileInfo:
    """文件/目录信息"""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified_time: Optional[str] = None
    server_name: str = ""  # 所属服务器名称
    server_type: str = ""  # 'webdav' 或 'smb'


class WebDAVScanner:
    """WebDAV文件扫描器"""

    def __init__(self, config, extensions: List[str] = None):
        """
        初始化WebDAV扫描器
        """
        self.config = config
        self.extensions = extensions or ['.mp4', '.mkv', '.avi', '.mov', '.iso']
        self.base_url = f"http://{config.host}:{config.port}{config.path}"
        self.base_path = config.path.rstrip('/')
        self.auth = HTTPBasicAuth(config.username, config.password) if config.username else None

        # 缓存当前路径内容
        self.current_path = "/"
        self.current_items = []

    def test_connection(self) -> bool:
        """测试WebDAV连接"""
        try:
            response = requests.request(
                'PROPFIND',
                self.base_url,
                auth=self.auth,
                headers={'Depth': '0'},
                timeout=5
            )
            return response.status_code in [200, 207, 401, 403]
        except:
            return False

    def list_directory(self, path: str = "/") -> List[FileInfo]:
        """
        列出目录内容

        Args:
            path: 相对路径

        Returns:
            文件和目录列表
        """
        full_url = f"{self.base_url}{path}"
        if not full_url.endswith('/'):
            full_url += '/'

        try:
            # WebDAV PROPFIND请求
            headers = {
                'Depth': '1',
                'Content-Type': 'application/xml'
            }

            response = requests.request(
                'PROPFIND',
                full_url,
                auth=self.auth,
                headers=headers,
                timeout=10
            )

            if response.status_code in [200, 207]:
                return self._parse_webdav_response(response.text, path)
            else:
                print(f"WebDAV列表失败: {response.status_code}")
                return []

        except Exception as e:
            print(f"WebDAV扫描错误: {e}")
            return []

    def _parse_webdav_response(self, xml_text: str, base_path: str) -> List[FileInfo]:
        """解析WebDAV响应"""
        import xml.etree.ElementTree as ET

        items = []
        try:
            # 简单的XML解析（实际应处理命名空间）
            root = ET.fromstring(xml_text)

            for response in root.findall('.//{DAV:}response'):
                href = response.findtext('.//{DAV:}href', '')
                if not href:
                    continue

                # 解码URL并获取文件名
                decoded_href = unquote(href)
                name = os.path.basename(decoded_href.rstrip('/'))
                if not name:  # 根目录
                    continue

                # 判断是否是目录
                is_dir = False
                if response.find('.//{DAV:}collection') is not None:
                    is_dir = True
                elif href.endswith('/'):
                    is_dir = True

                # 获取文件大小
                size = 0
                if not is_dir:
                    size_elem = response.find('.//{DAV:}getcontentlength')
                    if size_elem is not None and size_elem.text:
                        size = int(size_elem.text)

                # 如果是文件，检查扩展名
                if not is_dir:
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in self.extensions:
                        continue

                # 构建相对路径
                if self.base_path in decoded_href:
                    rel_path = decoded_href.split(self.base_path, 1)[-1].lstrip('/')
                else:
                    rel_path = href.lstrip('/')

                items.append(FileInfo(
                    name=name,
                    path=rel_path,
                    is_dir=is_dir,
                    size=size,
                    server_name=self.config.name,
                    server_type='webdav'
                ))

            # 过滤掉当前目录
            items = [item for item in items if item.name]

            # 排序：目录在前，文件在后
            items.sort(key=lambda x: (not x.is_dir, x.name.lower()))

        except Exception as e:
            print(f"解析WebDAV响应错误: {e}")

        return items

    def get_file_url(self, file_path: str) -> str:
        """获取文件的完整URL（带认证）"""
        encoded_path = quote(file_path)
        return f"http://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}{self.config.path}/{encoded_path}"
