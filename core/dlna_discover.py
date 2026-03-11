#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
DLNA设备发现模块
完全参考原app.py的解析方式
"""

import socket
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from urllib.parse import urlparse, urljoin

import requests


@dataclass
class DLNADevice:
    """DLNA设备信息"""
    name: str
    description_url: str
    ip: str
    port: int
    udn: str = ""
    manufacturer: str = ""
    model_name: str = ""
    services: List[Dict] = field(default_factory=list)
    auto_discovered: bool = True


class DLNADiscover:
    """DLNA设备发现器"""

    def __init__(self, timeout: int = 3):
        self.timeout = timeout
        self.ssdp_addr = ("239.255.255.250", 1900)

    def discover(self, search_target: str = "ssdp:all") -> List[DLNADevice]:
        """
        发现DLNA设备

        Args:
            search_target: 搜索目标，默认搜索所有设备

        Returns:
            DLNA设备列表
        """
        devices = []
        seen_locations = set()

        # SSDP搜索请求
        ssdp_request = (
            f"M-SEARCH * HTTP/1.1\r\n"
            f"HOST: 239.255.255.250:1900\r\n"
            f"MAN: \"ssdp:discover\"\r\n"
            f"MX: {self.timeout}\r\n"
            f"ST: {search_target}\r\n"
            f"\r\n"
        )

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(self.timeout)

            # 发送搜索请求
            sock.sendto(ssdp_request.encode(), self.ssdp_addr)
            print(f"已发送SSDP搜索请求，等待响应...")

            # 接收响应
            start_time = time.time()
            while time.time() - start_time < self.timeout + 2:
                try:
                    data, addr = sock.recvfrom(8192)
                    response = data.decode('utf-8', errors='ignore')

                    # 解析响应
                    device_info = self._parse_ssdp_response(response, addr)

                    if device_info and 'location' in device_info:
                        location = device_info['location']

                        # 去重
                        if location in seen_locations:
                            continue

                        seen_locations.add(location)
                        print(f"发现设备: {location}")

                        # 获取详细信息
                        details = self._get_device_details(location)
                        if details:
                            device = DLNADevice(
                                name=details.get('friendly_name', '未知设备'),
                                description_url=location,
                                ip=addr[0],
                                port=addr[1],
                                udn=details.get('udn', ''),
                                manufacturer=details.get('manufacturer', ''),
                                model_name=details.get('model_name', ''),
                                services=details.get('services', []),
                                auto_discovered=True
                            )
                            devices.append(device)
                            print(f"设备名称: {device.name}")

                except socket.timeout:
                    continue
                except Exception as e:
                    continue

            sock.close()

        except Exception as e:
            print(f"SSDP搜索错误: {e}")

        return devices

    def _parse_ssdp_response(self, response: str, addr) -> Dict:
        """解析SSDP响应"""
        device_info = {"ip": addr[0], "port": addr[1]}

        for line in response.split('\r\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                device_info[key] = value

        return device_info

    def _get_device_details(self, location: str) -> Optional[Dict]:
        """获取设备详细信息 - 完全参考原app.py的实现"""
        try:
            headers = {
                'User-Agent': 'DLNA-Controller/1.0',
                'Accept': 'text/xml'
            }
            response = requests.get(location, timeout=5, headers=headers)

            if response.status_code == 200:
                return self._parse_device_xml(response.text, location)
            else:
                print(f"获取设备详情失败: {response.status_code}")

        except Exception as e:
            print(f"获取设备详情错误: {e}")

        return None

    def _parse_device_xml(self, xml_text: str, base_url: str) -> Dict:
        """解析设备描述XML - 完全参考原app.py的解析方式"""
        details = {
            'friendly_name': '未知',
            'manufacturer': '未知',
            'model_name': '未知',
            'device_type': '未知',
            'udn': '',
            'services': []
        }

        try:
            root = ET.fromstring(xml_text)

            # 使用命名空间 - 完全按照原app.py的方式
            ns = {'ns': 'urn:schemas-upnp-org:device-1-0'}

            # 获取设备信息
            device = root.find('.//ns:device', ns)
            if device is None:
                device = root.find('.//device')

            if device is not None:

                # 基本设备信息
                friendly_name = device.findtext('ns:friendlyName', '', ns) or device.findtext('friendlyName', '')
                if friendly_name:
                    details['friendly_name'] = friendly_name

                manufacturer = device.findtext('ns:manufacturer', '', ns) or device.findtext('manufacturer', '')
                if manufacturer:
                    details['manufacturer'] = manufacturer

                model_name = device.findtext('ns:modelName', '', ns) or device.findtext('modelName', '')
                if model_name:
                    details['model_name'] = model_name

                udn = device.findtext('ns:UDN', '', ns) or device.findtext('UDN', '')
                if udn:
                    details['udn'] = udn

                # 获取服务列表 - 关键部分，完全按照原app.py的方式
                service_list = device.find('ns:serviceList', ns) or device.find('serviceList')
                if service_list is not None:
                    # 构建基础URL
                    base_path = '/'.join(base_url.split('/')[:-2])  # 原app.py中的方式

                    # 查找所有service
                    services = service_list.findall('ns:service', ns) or service_list.findall('service')
                    for service in services:
                        service_info = {}

                        # 服务类型
                        service_type = service.findtext('ns:serviceType', '', ns) or service.findtext('serviceType', '')
                        if service_type:
                            service_info['type'] = service_type

                        # 服务ID
                        service_id = service.findtext('ns:serviceId', '', ns) or service.findtext('serviceId', '')
                        if service_id:
                            service_info['id'] = service_id

                        # 控制URL - 原app.py中是这样构建的
                        control_url = service.findtext('ns:controlURL', '', ns) or service.findtext('controlURL', '')
                        if control_url:
                            if control_url.startswith('http'):
                                service_info['control_url'] = control_url
                            else:
                                service_info['control_url'] = urljoin(base_path, control_url)

                        # 事件URL
                        event_url = service.findtext('ns:eventSubURL', '', ns) or service.findtext('eventSubURL', '')
                        if event_url:
                            if event_url.startswith('http'):
                                service_info['event_url'] = event_url
                            else:
                                service_info['event_url'] = urljoin(base_path, event_url)

                        # SCPD URL
                        scpd_url = service.findtext('ns:SCPDURL', '', ns) or service.findtext('SCPDURL', '')
                        if scpd_url:
                            if scpd_url.startswith('http'):
                                service_info['scpd_url'] = scpd_url
                            else:
                                service_info['scpd_url'] = urljoin(base_path, scpd_url)

                        if service_info and 'type' in service_info:
                            details['services'].append(service_info)

        except Exception as e:
            print(f"XML解析错误: {e}")
            import traceback
            traceback.print_exc()

        return details

    def verify_device(self, description_url: str) -> Optional[DLNADevice]:
        """
        验证手动配置的设备是否可用

        Args:
            description_url: 设备描述URL

        Returns:
            验证通过的设备信息，失败返回None
        """
        try:
            parsed = urlparse(description_url)
            ip = parsed.hostname

            print(f"验证设备: {description_url}")
            details = self._get_device_details(description_url)
            if details and details.get('services'):  # 确保有服务
                device = DLNADevice(
                    name=details.get('friendly_name', '手动设备'),
                    description_url=description_url,
                    ip=ip,
                    port=parsed.port or 80,
                    udn=details.get('udn', ''),
                    manufacturer=details.get('manufacturer', ''),
                    model_name=details.get('model_name', ''),
                    services=details.get('services', []),
                    auto_discovered=False
                )
                print(f"设备验证成功: {device.name}")
                return device
        except Exception as e:
            print(f"设备验证失败: {e}")

        return None
   