import json
import os
import sqlite3
import threading
import traceback
from contextlib import contextmanager
from datetime import datetime
from queue import Queue

import requests
from astrbot import logger


class ConnectionPool:
    """SQLite 连接池"""

    def __init__(self, db_path, max_connections=10, timeout=30):
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self._connections = Queue(maxsize=max_connections)
        self._lock = threading.Lock()
        self._total_connections = 0

        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 初始化连接池
        self._init_pool()

    def _init_pool(self):
        """初始化连接池，创建表结构"""
        conn = self._create_connection()
        try:
            self._init_db(conn)
        finally:
            self._return_connection(conn)

    def _create_connection(self):
        """创建新的数据库连接"""
        conn = sqlite3.connect(self.db_path, timeout=self.timeout, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self, conn):
        """初始化数据库表"""
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS session_message (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                function_name TEXT NOT NULL,
                event_info TEXT,
                params TEXT,
                reply_content TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON session_message(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON session_message(timestamp)')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webdav_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                username TEXT,
                password TEXT,
                protocol TEXT NOT NULL DEFAULT 'http',
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                path TEXT NOT NULL,
                is_selected BOOLEAN DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        ''')

        # 确保is_selected字段只有一个为True
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS ensure_single_selected
            AFTER UPDATE OF is_selected ON webdav_config
            BEGIN
                UPDATE webdav_config SET is_selected = 0 
                WHERE id != NEW.id AND is_selected = 1;
            END;
        ''')

        conn.commit()

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self._return_connection(conn)

    def _get_connection(self):
        """从连接池获取连接"""
        try:
            conn = self._connections.get_nowait()
        except:
            with self._lock:
                if self._total_connections < self.max_connections:
                    conn = self._create_connection()
                    self._total_connections += 1
                else:
                    conn = self._connections.get(timeout=self.timeout)
        return conn

    def _return_connection(self, conn):
        """归还连接到连接池"""
        try:
            self._connections.put_nowait(conn)
        except:
            conn.close()
            with self._lock:
                self._total_connections -= 1

    def close_all(self):
        """关闭所有连接"""
        while not self._connections.empty():
            try:
                conn = self._connections.get_nowait()
                conn.close()
                with self._lock:
                    self._total_connections -= 1
            except:
                pass


class DatabaseManager:
    """数据库管理类"""

    def __init__(self, db_path='data/messages.db', max_connections=10):
        self.pool = ConnectionPool(db_path, max_connections)

    def get_shanghai_time(self):
        """获取本地时间（代替上海时区）"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _extract_event_info(self, event):
        """从事件对象中提取基本信息"""
        try:
            return {
                'message_str': event.message_str if hasattr(event, 'message_str') else None,
                'sender_id': event.get_sender_id() if hasattr(event, 'get_sender_id') else None,
                'session_id': event.session_id if hasattr(event, 'session_id') else None,
            }
        except:
            return None

    def _safe_json_dumps(self, data):
        """安全地将数据转为JSON字符串"""
        if data is None:
            return None
        try:
            return json.dumps(data, ensure_ascii=False)
        except:
            return json.dumps({"error": "无法序列化的数据"})

    def log_message(self, event, function_name, params=None, reply_content=None):
        """
        记录消息到数据库

        Args:
            event: AstrMessageEvent 对象
            function_name: 函数名称
            params: 接收的参数 (dict)
            reply_content: 回复内容 (str)

        Returns:
            int: 插入的记录ID，失败返回 None
        """
        try:
            session_id = event.session_id if hasattr(event, 'session_id') else 'unknown'
            event_info = self._extract_event_info(event)

            # 对参数进行脱敏处理
            params = self._mask_sensitive_params(params)
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                timestamp = self.get_shanghai_time()

                cursor.execute('''
                    INSERT INTO session_message 
                    (session_id, timestamp, function_name, event_info, params, reply_content)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    timestamp,
                    function_name,
                    self._safe_json_dumps(event_info),
                    self._safe_json_dumps(params),
                    reply_content
                ))
                logger.info(
                    f"log_message: function_name={function_name}, params={params} reply_content={reply_content}")
                return cursor.lastrowid
        except Exception as e:
            # 打印错误但不要抛出，避免影响主流程
            print(f"记录消息失败: {e}")
            print(traceback.format_exc())
            return None

    def _mask_sensitive_params(self, params):
        """对敏感参数进行脱敏处理"""
        if not params or not isinstance(params, dict):
            return params

        sensitive_fields = {'password', 'token', 'secret', 'key', 'auth'}
        masked_params = {}

        for key, value in params.items():
            key_lower = key.lower()
            is_sensitive = any(sensitive in key_lower for sensitive in sensitive_fields)
            if is_sensitive and value is not None:
                masked_params[key] = '******'
            else:
                masked_params[key] = value

        return masked_params

    # ========== 查询方法 ==========

    def get_session_messages(self, session_id, limit=50):
        """获取会话的历史消息"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM session_message 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))

            rows = cursor.fetchall()
            messages = []
            for row in rows:
                message = dict(row)
                # 解析JSON字段
                if message['event_info']:
                    message['event_info'] = json.loads(message['event_info'])
                if message['params']:
                    message['params'] = json.loads(message['params'])
                messages.append(message)

            return messages

    def get_last_scan_result(self, session_id):
        """获取最后一次扫描结果"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT reply_content FROM session_message 
                WHERE session_id = ? AND function_name = 'dlan_scan'
                ORDER BY timestamp DESC 
                LIMIT 1
            ''', (session_id,))

            row = cursor.fetchone()
            return row['reply_content'] if row else None

    def get_function_messages(self, function_name, session_id=None, limit=100):
        """获取指定函数的所有调用记录"""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM session_message 
                WHERE function_name = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (function_name, limit))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def close(self):
        """关闭数据库连接池"""
        self.pool.close_all()