#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DLNA控制器模块
基于之前的app.py重构，适配新的设备模型
"""

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from threading import Event
from typing import Optional, Dict

import requests


@dataclass
class PlaybackStatus:
    """播放状态"""
    state: str  # STOPPED, PLAYING, PAUSED_PLAYBACK
    duration: str = "00:00:00"
    position: str = "00:00:00"
    uri: str = ""
    volume: int = 50
    position_seconds: int = 0  # 转换为秒的进度
    duration_seconds: int = 0  # 转换为秒的总时长


class DLNAController:
    """DLNA控制器"""

    def __init__(self, device):
        """
        初始化控制器

        Args:
            device: DLNADevice对象
        """
        self.device = device
        self.current_instance = 0
        self.current_uri = None
        self.current_metadata = ""

        # 服务URL映射
        self.services = {}
        self._build_service_map()

        # 播放状态监控
        self._monitor_thread = None
        self._stop_monitor = Event()
        self._status_callbacks = []
        self._last_status = None

    def _build_service_map(self):
        """从设备服务列表构建服务URL映射"""
        for service in self.device.services:
            service_type = service.get('type', '')
            control_url = service.get('control_url', '')

            if 'AVTransport' in service_type:
                self.services['avtransport'] = control_url
            elif 'RenderingControl' in service_type:
                self.services['renderingcontrol'] = control_url
            elif 'NirvanaControl' in service_type:
                self.services['nirvanacontrol'] = control_url

    def _send_upnp_request(self, service: str, action: str, arguments: Dict = None) -> Optional[ET.Element]:
        """
        发送UPnP SOAP请求

        Args:
            service: 服务类型 ('avtransport', 'renderingcontrol', 'nirvanacontrol')
            action: 动作名称
            arguments: 参数字典

        Returns:
            响应XML的根元素
        """
        if service not in self.services:
            print(f"❌ 未找到服务: {service}")
            return None

        control_url = self.services[service]

        # 确定服务类型URN
        service_urns = {
            'avtransport': 'urn:schemas-upnp-org:service:AVTransport:1',
            'renderingcontrol': 'urn:schemas-upnp-org:service:RenderingControl:1',
            'nirvanacontrol': 'urn:app-bilibili-com:service:NirvanaControl:3'
        }
        service_urn = service_urns.get(service, service)

        # 构建SOAP请求
        soap_body = f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="{service_urn}">'''

        if arguments:
            for key, value in arguments.items():
                soap_body += f'\n      <{key}>{value}</{key}>'

        soap_body += f'''
    </u:{action}>
  </s:Body>
</s:Envelope>'''

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': f'"{service_urn}#{action}"',
            'User-Agent': 'DLNA-Push/1.0'
        }

        try:
            response = requests.post(control_url, data=soap_body.encode('utf-8'),
                                     headers=headers, timeout=10)

            if response.status_code == 200:
                return ET.fromstring(response.text)
            else:
                print(f"❌ UPnP请求失败: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ UPnP请求异常: {e}")
            return None

    def set_uri(self, uri: str, metadata: str = "") -> bool:
        """设置媒体URI"""
        args = {
            'InstanceID': self.current_instance,
            'CurrentURI': uri,
            'CurrentURIMetaData': metadata
        }

        response = self._send_upnp_request('avtransport', 'SetAVTransportURI', args)
        if response is not None:
            self.current_uri = uri
            self.current_metadata = metadata
            return True
        return False

    def play(self) -> bool:
        """开始播放"""
        # 检查状态，必要时重新设置URI
        status = self.get_status()
        if status and status.state in ['STOPPED', 'NO_MEDIA_PRESENT'] and self.current_uri:
            print("🔄 重新设置URI...")
            if not self.set_uri(self.current_uri, self.current_metadata):
                return False
            time.sleep(1)

        args = {'InstanceID': self.current_instance, 'Speed': '1'}
        response = self._send_upnp_request('avtransport', 'Play', args)
        return response is not None

    def pause(self) -> bool:
        """暂停"""
        args = {'InstanceID': self.current_instance}
        response = self._send_upnp_request('avtransport', 'Pause', args)
        return response is not None

    def stop(self) -> bool:
        """停止"""
        args = {'InstanceID': self.current_instance}
        response = self._send_upnp_request('avtransport', 'Stop', args)
        return response is not None

    def seek(self, target, unit: str = "REL_TIME") -> bool:
        """跳转"""
        # 转换秒数为时间格式
        if isinstance(target, (int, float)) or (isinstance(target, str) and target.isdigit()):
            seconds = int(target)
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            target = f"{hours:02d}:{minutes:02d}:{secs:02d}"

        args = {
            'InstanceID': self.current_instance,
            'Unit': unit,
            'Target': target
        }
        response = self._send_upnp_request('avtransport', 'Seek', args)
        return response is not None

    def _time_to_seconds(self, time_str: str) -> int:
        """将时间字符串转换为秒数，支持多种格式"""
        try:
            if not time_str or time_str == "NOT_IMPLEMENTED":
                return 0

            # 移除可能的引号
            time_str = time_str.strip('"\'')

            # 处理各种时间格式
            parts = time_str.split(':')

            if len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 1:  # 纯秒数
                return int(parts[0])
            else:
                # 尝试直接转换为整数
                return int(time_str)
        except (ValueError, AttributeError) as e:
            print(f"时间解析错误: {time_str} -> {e}")
            return 0

    def get_status(self) -> Optional[PlaybackStatus]:
        """获取播放状态"""
        # 获取传输信息
        trans_args = {'InstanceID': self.current_instance}
        trans_response = self._send_upnp_request('avtransport', 'GetTransportInfo', trans_args)

        if trans_response is None:
            return None

        state = "STOPPED"
        for elem in trans_response.iter():
            if elem.tag.endswith('CurrentTransportState'):
                state = elem.text or "STOPPED"
                break

        # 获取位置信息
        pos_args = {'InstanceID': self.current_instance}
        pos_response = self._send_upnp_request('avtransport', 'GetPositionInfo', pos_args)

        duration = "00:00:00"
        position = "00:00:00"
        uri = ""

        if pos_response:
            for elem in pos_response.iter():
                if elem.tag.endswith('TrackDuration'):
                    duration = elem.text or "00:00:00"
                elif elem.tag.endswith('RelTime'):
                    position = elem.text or "00:00:00"
                elif elem.tag.endswith('TrackURI'):
                    uri = elem.text or ""

        # 转换为秒数
        duration_seconds = self._time_to_seconds(duration)
        position_seconds = self._time_to_seconds(position)

        # 调试输出
        print(f"🎯 获取状态: position={position} ({position_seconds}s), duration={duration} ({duration_seconds}s)")

        status = PlaybackStatus(
            state=state,
            duration=duration,
            position=position,
            uri=uri,
            duration_seconds=duration_seconds,
            position_seconds=position_seconds
        )

        self._last_status = status
        return status

    def set_volume(self, volume: int) -> bool:
        """设置音量"""
        if 'renderingcontrol' not in self.services:
            print("❌ 设备不支持音量控制")
            return False

        args = {
            'InstanceID': self.current_instance,
            'Channel': 'Master',
            'DesiredVolume': volume
        }
        response = self._send_upnp_request('renderingcontrol', 'SetVolume', args)
        if response is not None:
            print(f"🔊 音量设置为: {volume}")
            return True
        return False
