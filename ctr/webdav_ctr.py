from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass

from ..core.media_scanner import WebDAVScanner, FileInfo
from astrbot import logger


@dataclass
class WebDAVConfig:
    """WebDAV配置数据类"""
    id: Optional[int] = None
    name: str = ""
    url: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"
    host: str = ""
    port: int = 80
    path: str = "/"
    is_selected: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_url(cls, name: str, url: str, username: Optional[str] = None,
                 password: Optional[str] = None) -> 'WebDAVConfig':
        """从URL创建配置对象"""
        config = cls(name=name, username=username, password=password)

        # 解析URL
        if url.startswith('https://'):
            config.protocol = 'https'
            url_without_proto = url[8:]
        elif url.startswith('http://'):
            config.protocol = 'http'
            url_without_proto = url[7:]
        else:
            config.protocol = 'http'
            url_without_proto = url

        # 分离host和path
        if '/' in url_without_proto:
            config.host, config.path = url_without_proto.split('/', 1)
            config.path = '/' + config.path
        else:
            config.host = url_without_proto
            config.path = '/'

        # 分离host和port
        if ':' in config.host:
            config.host, port_str = config.host.split(':', 1)
            config.port = int(port_str)
        else:
            config.port = 80 if config.protocol == 'http' else 443

        config.url = url
        return config

    def to_scanner_config(self):
        """转换为media_scanner所需的配置对象格式"""

        class ScannerConfig:
            pass

        config = ScannerConfig()
        config.name = self.name
        config.path = self.path
        config.protocol = self.protocol
        config.host = self.host
        config.port = self.port
        config.username = self.username
        config.password = self.password

        return config


class WebDAVManager:
    """WebDAV管理类 - 处理所有业务逻辑"""

    def __init__(self, db):
        self.db = db

    # ========== 数据库操作 ==========

    def _get_all_configs(self) -> List[Dict[str, Any]]:
        """获取所有配置"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, url, username, protocol, host, port, path, is_selected
                    FROM webdav_config 
                    ORDER BY created_at DESC
                ''')
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取WebDAV配置失败: {e}")
            return []

    def _get_config_by_id(self, config_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取配置"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, url, username, protocol, host, port, path, is_selected
                    FROM webdav_config 
                    WHERE id = ?
                ''', (config_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取WebDAV配置失败: {e}")
            return None

    def _get_config_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """根据索引获取配置（从1开始）"""
        configs = self._get_all_configs()
        if 1 <= index <= len(configs):
            return configs[index - 1]
        return None

    def _get_selected_config(self) -> Optional[Dict[str, Any]]:
        """获取当前选中的配置"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, url, username, protocol, host, port, path, is_selected
                    FROM webdav_config 
                    WHERE is_selected = 1
                    LIMIT 1
                ''')
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"获取选中配置失败: {e}")
            return None

    def _get_config_password(self, config_id: int) -> Optional[str]:
        """获取配置的密码"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT password FROM webdav_config WHERE id = ?', (config_id,))
                row = cursor.fetchone()
                return row['password'] if row else None
        except Exception as e:
            logger.error(f"获取密码失败: {e}")
            return None

    def _set_config_selected(self, config_id: int) -> bool:
        """设置选中的配置"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                # 先清除所有选中
                cursor.execute('UPDATE webdav_config SET is_selected = 0')
                # 设置新的选中
                cursor.execute('UPDATE webdav_config SET is_selected = 1 WHERE id = ?', (config_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置选中配置失败: {e}")
            return False

    def _delete_config(self, config_id: int) -> bool:
        """删除配置"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM webdav_config WHERE id = ?', (config_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"删除配置失败: {e}")
            return False

    def _count_configs(self) -> int:
        """统计配置数量"""
        try:
            with self.db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM webdav_config')
                row = cursor.fetchone()
                return row['count'] if row else 0
        except Exception as e:
            logger.error(f"统计配置失败: {e}")
            return 0

    # ========== 业务逻辑 ==========

    def test_connection(self, config: WebDAVConfig) -> Tuple[bool, str]:
        """
        测试WebDAV连接

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

    def add_config(self, config: WebDAVConfig) -> Tuple[bool, str, Optional[WebDAVConfig]]:
        """
        添加WebDAV配置

        Returns:
            (是否成功, 消息, 配置对象)
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

                # 判断是否是第一个配置
                is_first = self._count_configs() == 0

                cursor.execute('''
                    INSERT INTO webdav_config 
                    (name, url, username, password, protocol, host, port, path, is_selected, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config.name,
                    config.url,
                    config.username,
                    config.password,
                    config.protocol,
                    config.host,
                    config.port,
                    config.path,
                    1 if is_first else 0,  # 第一个配置自动选中
                    datetime.now(),
                    datetime.now()
                ))

                config.id = cursor.lastrowid
                config.is_selected = is_first

                return True, "配置添加成功", config

        except Exception as e:
            return False, f"保存失败: {str(e)}", None

    def get_configs_list(self) -> Tuple[bool, str, List[Dict[str, Any]]]:
        """
        获取配置列表

        Returns:
            (是否成功, 消息, 配置列表)
        """
        try:
            configs = self._get_all_configs()
            if not configs:
                return True, "暂无WebDAV服务器配置", []
            return True, "获取成功", configs
        except Exception as e:
            return False, f"获取列表失败: {str(e)}", []

    def select_config(self, index: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        选中配置

        Returns:
            (是否成功, 消息, 选中的配置)
        """
        try:
            config = self._get_config_by_index(index)
            if not config:
                configs = self._get_all_configs()
                if configs:
                    return False, f"未找到序号为 {index} 的WebDAV服务器配置", None
                else:
                    return False, "当前没有任何WebDAV服务器配置", None

            # 设置选中
            if self._set_config_selected(config['id']):
                config['is_selected'] = True
                return True, f"已选中WebDAV服务器：【{config['name']}】", config
            else:
                return False, "设置选中状态失败", None

        except Exception as e:
            return False, f"选中操作失败: {str(e)}", None

    def delete_config(self, index: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        删除配置

        Returns:
            (是否成功, 消息, 被删除的配置)
        """
        try:
            config = self._get_config_by_index(index)
            if not config:
                configs = self._get_all_configs()
                if configs:
                    return False, f"未找到序号为 {index} 的WebDAV服务器配置", None
                else:
                    return False, "当前没有任何WebDAV服务器配置", None

            # 检查是否是选中的配置
            was_selected = config['is_selected']

            # 删除配置
            if self._delete_config(config['id']):
                # 如果删除的是选中的配置，且有其他配置存在，自动选中第一个
                if was_selected:
                    remaining = self._get_all_configs()
                    if remaining:
                        self._set_config_selected(remaining[0]['id'])

                return True, f"已删除WebDAV服务器：【{config['name']}】", config
            else:
                return False, "删除失败", None

        except Exception as e:
            return False, f"删除操作失败: {str(e)}", None

    def browse_path(self, path: str = "/") -> Tuple[bool, str, Optional[List[FileInfo]], Optional[Dict[str, Any]]]:
        """
        浏览路径

        Returns:
            (是否成功, 消息, 文件列表, 当前选中的配置)
        """
        try:
            # 获取当前选中的配置
            config_dict = self._get_selected_config()
            if not config_dict:
                return False, "请先使用 /dlna-cast webdav select <序号> 选中一个服务器", None, None

            # 创建配置对象
            config = WebDAVConfig(
                id=config_dict['id'],
                name=config_dict['name'],
                url=config_dict['url'],
                username=config_dict.get('username'),
                protocol=config_dict['protocol'],
                host=config_dict['host'],
                port=config_dict['port'],
                path=config_dict['path']
            )

            # 获取密码
            password = self._get_config_password(config_dict['id'])
            if password:
                config.password = password

            # 创建扫描器
            scanner = WebDAVScanner(config.to_scanner_config())

            # 浏览目录
            items = scanner.list_directory(path)

            return True, "浏览成功", items, config_dict

        except Exception as e:
            return False, f"浏览失败: {str(e)}", None, None

    def get_current_selected(self) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        获取当前选中的配置

        Returns:
            (是否成功, 消息, 选中的配置)
        """
        try:
            config = self._get_selected_config()
            if not config:
                return False, "当前没有选中的WebDAV服务器", None
            return True, "获取成功", config
        except Exception as e:
            return False, f"获取失败: {str(e)}", None

    def format_config_list(self, configs: List[Dict[str, Any]], show_selected: bool = True) -> str:
        """格式化配置列表显示"""
        if not configs:
            return "暂无WebDAV服务器配置"

        lines = ["📁 WebDAV服务器列表："]
        for i, config in enumerate(configs, 1):
            name = config['name']
            url = config['url']
            username = config.get('username', '无')
            selected = config.get('is_selected', False)

            selected_mark = "✅ " if selected and show_selected else ""
            lines.append(f"{i}. {selected_mark}{name}")
            lines.append(f"   ├─ URL: {url}")
            lines.append(f"   └─ 用户名: {username}")

        return "\n".join(lines)