from datetime import datetime
from typing import Optional, Tuple, Dict, Any

from ..core.media_scanner import WebDAVScanner


class WebDAVConfig:
    """WebDAV配置类"""

    def __init__(self, name: str, url: str, username: Optional[str] = None,
                 password: Optional[str] = None, host: Optional[str] = None,
                 port: Optional[int] = None, path: Optional[str] = None):
        self.name = name
        self.url = url
        self.username = username
        self.password = password

        # 解析URL获取host、port、path
        if url and not host:
            self._parse_url(url)
        else:
            self.host = host
            self.port = port
            self.path = path

    def _parse_url(self, url: str):
        """解析WebDAV URL"""
        # 移除协议部分
        if url.startswith(('http://', 'https://')):
            protocol_end = url.find('://') + 3
            rest = url[protocol_end:]

            # 分离host和path
            if '/' in rest:
                self.host, self.path = rest.split('/', 1)
                self.path = '/' + self.path
            else:
                self.host = rest
                self.path = '/'

            # 分离host和port
            if ':' in self.host:
                self.host, port_str = self.host.split(':', 1)
                self.port = int(port_str)
            else:
                self.port = 80 if url.startswith('http://') else 443
        else:
            # 默认添加http://
            self._parse_url('http://' + url)

    def to_scanner_config(self):
        """转换为media_scanner所需的配置对象格式"""

        # 创建一个简单的配置对象，包含WebDAVScanner需要的属性
        class ScannerConfig:
            pass

        config = ScannerConfig()
        config.name = self.name
        config.host = self.host
        config.port = self.port
        config.path = self.path
        config.username = self.username
        config.password = self.password

        return config


class WebDAVManager:
    """WebDAV管理类"""

    def __init__(self, db):
        self.db = db
        # 表初始化已在 db_utils 中完成，这里不再需要 _init_table

    def test_connection(self, config: WebDAVConfig) -> Tuple[bool, str]:
        """
        测试WebDAV连接（复用media_scanner的test_connection）

        Returns:
            (是否成功, 消息)
        """
        try:
            scanner = WebDAVScanner(config.to_scanner_config())
            success = scanner.test_connection()

            if success:
                return True, "连接成功"
            else:
                return False, "连接失败"

        except Exception as e:
            return False, f"连接异常: {str(e)}"

    def add_config(self, config: WebDAVConfig) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        添加WebDAV配置

        Returns:
            (是否成功, 消息, 配置信息)
        """
        try:
            # 先测试连接
            success, message = self.test_connection(config)
            if not success:
                return False, message, None

            # 保存到数据库
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()

                # 检查是否已存在同名配置
                cursor.execute('SELECT id FROM webdav_config WHERE name = ?', (config.name,))
                if cursor.fetchone():
                    return False, f"配置名 '{config.name}' 已存在", None

                cursor.execute('''
                    INSERT INTO webdav_config 
                    (name, url, username, password, host, port, path, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config.name,
                    config.url,
                    config.username,
                    config.password,
                    config.host,
                    config.port,
                    config.path,
                    datetime.now(),
                    datetime.now()
                ))
                conn.commit()
                return True, "配置添加成功"

        except Exception as e:
            return False, f"保存失败: {str(e)}", None