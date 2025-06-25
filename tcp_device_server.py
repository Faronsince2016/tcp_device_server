#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP 工业设备管理服务
支持设备心跳检测、Redis消息转发、异步并发处理、动作执行客户端管理
"""

import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler
import time
import json
import re
from datetime import datetime
from typing import Dict, Optional, Set
from collections import defaultdict
import aioredis
import signal
import sys


class DeviceManager:
    """设备管理器 - 处理设备连接、心跳检测和消息转发"""
    
    def __init__(self, server_host: str = "0.0.0.0", server_port: int = 8888, 
                 redis_host: str = "localhost", redis_port: int = 6379):
        self.server_host = server_host
        self.server_port = server_port
        self.redis_host = redis_host
        self.redis_port = redis_port
        
        # 设备连接字典: device_id -> (transport, writer, last_heartbeat_time)
        self.devices: Dict[str, tuple] = {}
        self.devices_lock = asyncio.Lock()
        
        # 动作执行客户端集合: 存储标记为动作执行的客户端ID
        self.action_clients: Set[str] = set()
        self.action_clients_lock = asyncio.Lock()
        
        # Redis 连接
        self.redis_client: Optional[aioredis.Redis] = None
        self.redis_subscriber: Optional[aioredis.client.PubSub] = None
        
        # 服务器状态
        self.server = None
        self.running = False
        
        # 配置日志
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
    def setup_logging(self):
        """配置日志系统 - 支持每天切割，只保留3天"""
        # 创建日志格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # 创建定时轮转文件处理器 - 每天切割一次，保留3个备份（总共4天）
        file_handler = TimedRotatingFileHandler(
            filename='device_server.log',
            when='midnight',  # 每天午夜切割
            interval=1,       # 每1天
            backupCount=3,    # 保留3个备份文件
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        
        # 配置根日志器 - 设置为DEBUG级别以便查看所有日志
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[file_handler, console_handler]
        )
        
        # 设置第三方库日志级别
        logging.getLogger('aioredis').setLevel(logging.WARNING)
        
    async def start_server(self):
        """启动 TCP 服务器"""
        try:
            self.logger.info(f"启动 TCP 服务器 {self.server_host}:{self.server_port}")
            self.server = await asyncio.start_server(
                self.handle_client_connection,
                self.server_host,
                self.server_port
            )
            self.running = True
            
            # 启动心跳检查任务
            asyncio.create_task(self.heartbeat_checker())
            
            # 启动 Redis 订阅任务
            asyncio.create_task(self.redis_subscriber_task())
            
            self.logger.info("TCP 服务器启动成功")
            
        except Exception as e:
            self.logger.error(f"启动 TCP 服务器失败: {e}")
            raise
    
    def extract_device_id(self, message_str: str, client_addr: tuple) -> str:
        """从消息中提取设备ID，只保留数字"""
        try:
            # 使用正则表达式提取所有数字
            numbers = re.findall(r'\d+', message_str)
            if numbers:
                # 将所有数字连接起来作为设备ID
                device_id = ''.join(numbers)
                return device_id
            else:
                # 如果没有数字，使用客户端IP的最后一位作为设备ID
                device_id = f"{client_addr[0].split('.')[-1]}"
                return device_id
        except Exception as e:
            self.logger.error(f"提取设备ID时发生错误: {e}, 消息: {message_str}")
            # 发生错误时使用客户端IP的最后一位作为设备ID
            return f"{client_addr[0].split('.')[-1]}"

    async def process_message(self, message_str: str, client_addr: tuple, writer: asyncio.StreamWriter, device_id_container: list):
        """处理接收到的消息内容"""
        try:
            # self.logger.info(f"收到消息: {message_str}")
            if not message_str:
                self.logger.info(f"消息内容为空，跳过处理")
                return
            
            # 检查消息长度，如果超过16个字符则断开客户端
            if len(message_str) > 16:
                self.logger.warning(f"客户端 {client_addr} 发送的消息长度超过16个字符({len(message_str)}个字符)，断开连接: {repr(message_str)}")
                # 关闭客户端连接
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception as e:
                    self.logger.error(f"断开客户端 {client_addr} 连接时出错: {e}")
                return
            
            # 检查是否以'A'开头，标记为动作执行客户端
            if 'A' in message_str:
                # self.logger.info(f"检测到动作执行客户端标识 'A' in '{message_str}'")
                # 提取设备ID（去掉'A'前缀后，只保留数字）
                if len(message_str) > 1:
                    # 从整个消息中提取数字作为设备ID
                    device_id_str = self.extract_device_id(message_str, client_addr)
                    if not device_id_str:
                        # 如果没有数字，使用客户端ip的最后一位作为设备ID
                        device_id_str = f"{client_addr[0].split('.')[-1]}"
                        self.logger.info(f"A后没有数字，使用IP生成设备ID: {device_id_str}")
                else:
                    # 如果只有'A'，使用连接地址作为ID
                    device_id_str = f"{client_addr[0].split('.')[-1]}"
                    self.logger.info(f"只有A，使用IP生成设备ID: {device_id_str}")
                
                # 标记为动作执行客户端
                async with self.action_clients_lock:
                    if device_id_str not in self.action_clients:
                        self.action_clients.add(device_id_str)
                        self.logger.info(f"设备 {device_id_str} 被标记为动作执行客户端")
                    else:
                        self.logger.info(f"设备 {device_id_str} 就绪确认")
            else:
                # 普通心跳消息，只保留数字作为设备ID
                device_id_str = self.extract_device_id(message_str, client_addr)
                # self.logger.info(f"普通心跳设备ID: {device_id_str}")
                
            current_time = time.time()
            
            # 更新设备信息（所有连接的客户端都被认为发送了心跳）
            async with self.devices_lock:
                is_new_device = device_id_str not in self.devices
                self.devices[device_id_str] = (writer.transport, writer, current_time)
            
            if is_new_device:
                self.logger.info(f"设备 {device_id_str} 首次连接 - 地址: {client_addr}, 原始消息: {repr(message_str)}")
            else:
                pass
                # self.logger.info(f"设备 {device_id_str} 更新心跳时间")
            
            device_id_container[0] = device_id_str  # 更新当前设备ID
            
        except UnicodeDecodeError as e:
            self.logger.warning(f"收到无效编码数据 from {client_addr}: {repr(message_str)}, 错误: {e}")
        except Exception as e:
            self.logger.error(f"解析设备编号时发生错误 from {client_addr}: {e}, 数据: {repr(message_str)}")

    async def handle_client_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        client_addr = writer.get_extra_info('peername')
        self.logger.info(f"新客户端连接: {client_addr}")
        
        device_id_container = [None]  # 使用列表来存储设备ID，方便在process_message中修改
        buffer = b''  # 用于累积不完整的数据
        last_data_time = time.time()  # 记录最后一次收到数据的时间
        
        try:
            while True:
                # 读取数据，设置超时
                try:
                    # 每次读取小块数据，避免大数据包问题
                    chunk = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                    if not chunk:
                        # 连接关闭
                        self.logger.info(f"客户端 {client_addr} 连接关闭（收到空数据）")
                        break
                    
                    # 添加详细的数据接收日志
                    # self.logger.info(f"从客户端 {client_addr} 收到原始数据: {repr(chunk)}")
                    buffer += chunk
                    last_data_time = time.time()  # 更新最后数据接收时间
                    # self.logger.info(f"当前缓冲区内容: {repr(buffer)}")
                    
                    # 查找换行符
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        # self.logger.info(f"处理分割后的行: {repr(line)}, 剩余缓冲区: {repr(buffer)}")
                        
                        # 检查行的大小，防止过大的数据包
                        if len(line) > 1024 * 1024:  # 1MB限制
                            self.logger.error(f"客户端 {client_addr} 发送的单行数据过大: {len(line)} bytes")
                            continue
                        
                        if not line.strip():
                            self.logger.info(f"跳过空行数据")
                            continue
                        
                        # 解析设备编号和消息内容
                        try:
                            message_str = line.decode('ascii').strip()
                            # 使用 create_task 进行非阻塞处理，避免阻塞客户端后续消息发送
                            asyncio.create_task(self.process_message(message_str, client_addr, writer, device_id_container))
                        except Exception as e:
                            self.logger.error(f"处理消息时发生错误 from {client_addr}: {e}, 数据: {repr(line)}")
                    
                    # 防止缓冲区无限增长
                    if len(buffer) > 1024 * 1024:  # 1MB限制
                        self.logger.error(f"客户端 {client_addr} 缓冲区过大，清空缓冲区")
                        buffer = b''
                        
                except asyncio.TimeoutError:
                    # 读取超时，检查缓冲区是否有未处理的数据（没有换行符）
                    current_time = time.time()
                    
                    # 如果缓冲区有数据且距离最后一次接收数据超过0.5秒，则处理缓冲区内容
                    if buffer and (current_time - last_data_time) >= 0.5:
                        # self.logger.info(f"检测到无换行符的消息，处理缓冲区内容: {repr(buffer)}")
                        
                        # 检查数据大小
                        if len(buffer) > 1024 * 1024:  # 1MB限制
                            self.logger.error(f"客户端 {client_addr} 缓冲区数据过大: {len(buffer)} bytes")
                            buffer = b''
                            continue
                        
                        try:
                            message_str = buffer.decode('ascii').strip()
                            if message_str:
                                # 使用 create_task 进行非阻塞处理，避免阻塞客户端后续消息发送
                                asyncio.create_task(self.process_message(message_str, client_addr, writer, device_id_container))
                            buffer = b''  # 清空缓冲区
                        except UnicodeDecodeError as e:
                            self.logger.warning(f"缓冲区包含无效编码数据 from {client_addr}: {repr(buffer)}, 错误: {e}")
                            buffer = b''  # 清空缓冲区
                        except Exception as e:
                            self.logger.error(f"处理缓冲区数据时发生错误 from {client_addr}: {e}, 数据: {repr(buffer)}")
                            buffer = b''  # 清空缓冲区
                    else:
                        # 继续等待数据
                        pass
                        # self.logger.debug(f"客户端 {client_addr} 读取超时，继续等待")
                    continue
                    
        except Exception as e:
            self.logger.error(f"处理客户端 {client_addr} 连接时发生错误: {e}")
        finally:
            # 在连接关闭前，检查缓冲区是否还有未处理的数据
            if buffer:
                self.logger.info(f"连接关闭前处理剩余缓冲区内容: {repr(buffer)}")
                try:
                    message_str = buffer.decode('ascii').strip()
                    if message_str:
                        # 使用 create_task 进行非阻塞处理，避免阻塞客户端后续消息发送
                        asyncio.create_task(self.process_message(message_str, client_addr, writer, device_id_container))
                except UnicodeDecodeError as e:
                    self.logger.warning(f"缓冲区包含无效编码数据 from {client_addr}: {repr(buffer)}, 错误: {e}")
                except Exception as e:
                    self.logger.error(f"处理关闭前缓冲区数据时发生错误 from {client_addr}: {e}, 数据: {repr(buffer)}")
            
            # 清理连接
            device_id = device_id_container[0]
            if device_id:
                async with self.devices_lock:
                    if device_id in self.devices:
                        del self.devices[device_id]
                
                # 从动作执行客户端列表中移除
                async with self.action_clients_lock:
                    if device_id in self.action_clients:
                        self.action_clients.remove(device_id)
                        self.logger.info(f"动作执行客户端 {device_id} 已移除")
                
                self.logger.info(f"设备 {device_id} 断开连接 - 地址: {client_addr}")
            else:
                self.logger.info(f"未知设备断开连接 - 地址: {client_addr}")
                
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
    
    async def heartbeat_checker(self):
        """心跳检查协程 - 每1s检查一次设备超时"""
        self.logger.info("启动心跳检查器")
        
        while self.running:
            try:
                current_time = time.time()
                timeout_devices = []
                
                async with self.devices_lock:
                    # 获取动作执行客户端列表的副本
                    async with self.action_clients_lock:
                        action_clients_copy = set(self.action_clients)
                    
                    for device_id, (transport, writer, last_heartbeat) in list(self.devices.items()):
                        # 动作执行客户端不设置超时，跳过超时检查
                        if device_id in action_clients_copy:
                            continue
                            
                        # 只对普通设备检查是否超过1秒未收到心跳
                        if current_time - last_heartbeat > 1.5:
                            timeout_devices.append((device_id, transport, writer))
                            del self.devices[device_id]
                
                # 处理超时设备
                for device_id, transport, writer in timeout_devices:
                    self.logger.warning(f"普通设备 {device_id} 心跳超时，强制断开连接")
                    
                    try:
                        if not transport.is_closing():
                            transport.close()
                        writer.close()
                        await writer.wait_closed()
                    except Exception as e:
                        self.logger.error(f"关闭超时设备 {device_id} 连接时出错: {e}")
                
                await asyncio.sleep(0.5)  # 500ms 检查间隔
                
            except Exception as e:
                self.logger.error(f"心跳检查器发生错误: {e}")
                await asyncio.sleep(1.0)
                
    async def setup_redis_connection(self):
        """建立 Redis 连接"""
        try:
            self.logger.info(f"连接 Redis {self.redis_host}:{self.redis_port}")
            self.redis_client = aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}",
                encoding="utf-8",
                decode_responses=True
            )
            
            # 测试连接
            await self.redis_client.ping()
            self.logger.info("Redis 连接成功")
            
            # 创建订阅者
            self.redis_subscriber = self.redis_client.pubsub()
            await self.redis_subscriber.subscribe("result")
            self.logger.info("订阅 Redis 频道 'result' 成功")
            
        except Exception as e:
            self.logger.error(f"Redis 连接失败: {e}")
            raise
            
    async def redis_subscriber_task(self):
        """Redis 订阅处理任务"""
        self.logger.info("启动 Redis 订阅任务")
        
        # 重试连接 Redis
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries and self.running:
            try:
                await self.setup_redis_connection()
                break
            except Exception as e:
                retry_count += 1
                self.logger.error(f"Redis 连接失败 (尝试 {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(5)  # 等待5秒后重试
                else:
                    self.logger.error("Redis 连接重试次数已达上限，停止尝试")
                    return
        
        if not self.redis_subscriber:
            return
            
        try:
            async for message in self.redis_subscriber.listen():
                if not self.running:
                    break
                    
                if message['type'] == 'message':
                    await self.process_redis_message(message['data'])
                    
        except Exception as e:
            self.logger.error(f"Redis 订阅任务发生错误: {e}")
        finally:
            await self.cleanup_redis()
    
    async def parse_result_message(self, message: str):
        """解析result消息格式: B\r\n1 5 0 0 x y 角度\r\n"""
        try:
            # 移除可能的\r\n并分割
            message = message.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
            parts = message.split()
            
            if len(parts) < 7:
                self.logger.warning(f"Result消息格式不完整，期望至少7个字段，实际收到: {len(parts)} - {message}")
                return None
            
            # 解析各字段
            if parts[0] != 'B':
                self.logger.warning(f"Result消息必须以'B'开头，实际收到: {parts[0]}")
                return None
            
            coord_count = parts[1]  # 坐标个数
            target_client_id = parts[2]  # 目标动作执行客户端ID
            reserve1 = parts[3]  # 预留标志1
            reserve2 = parts[4]  # 预留标志2
            x = parts[5]  # X坐标
            y = parts[6]  # Y坐标
            angle = parts[7] if len(parts) > 7 else "0"  # 角度
            
            return {
                'coord_count': coord_count,
                'target_client_id': target_client_id,
                'reserve1': reserve1,
                'reserve2': reserve2,
                'x': x,
                'y': y,
                'angle': angle,
                'original_message': message
            }
            
        except Exception as e:
            self.logger.error(f"解析result消息时发生错误: {e}, 消息: {message}")
            return None
            
    def get_client_number(self, client_id: str) -> int:
        """从客户端ID中提取数字编号"""
        try:
            # 使用正则表达式提取数字
            numbers = re.findall(r'\d+', client_id)
            if numbers:
                return int(numbers[-1])  # 取最后一个数字作为编号
            else:
                # 如果没有数字，使用字符串哈希的绝对值
                return abs(hash(client_id)) % 1000
        except Exception:
            return abs(hash(client_id)) % 1000

    async def process_redis_message(self, message: str):
        """处理 Redis 消息 - 将消息原样转发给动作执行客户端"""
        try:
            # 检查消息是否为空
            if not message or not message.strip():
                self.logger.warning(f"收到空的Redis消息，已忽略")
                return
            
            self.logger.info(f"收到Redis消息: {repr(message)}")
            
            # 解析result消息以获取目标客户端ID
            result_info = await self.parse_result_message(message)
            if not result_info:
                self.logger.warning(f"无法解析Redis消息，将广播给所有动作执行客户端: {message}")
                target_client_id = None
            else:
                target_client_id = result_info['target_client_id']
                self.logger.info(f"处理result消息 - 目标动作执行客户端: {target_client_id}")
            
            # 原样转发消息（确保消息格式正确）
            if not message.endswith('\r\n'):
                # 如果消息不以\r\n结尾，添加它
                forwarded_message = message + '\r\n'
            else:
                forwarded_message = message
            
            message_bytes = forwarded_message.encode('utf-8')
            
            self.logger.info(f"准备原样转发消息: {repr(forwarded_message)}")
            
            # 查找对应的动作执行客户端
            async with self.action_clients_lock:
                action_clients_copy = set(self.action_clients)
            
            async with self.devices_lock:
                devices_copy = dict(self.devices)
            
            # 如果有指定的目标客户端，优先发送给该客户端
            target_found = False
            if target_client_id and target_client_id in action_clients_copy and target_client_id in devices_copy:
                transport, writer, last_heartbeat = devices_copy[target_client_id]
                try:
                    writer.write(message_bytes)
                    await writer.drain()
                    self.logger.info(f"成功原样转发消息到目标动作执行客户端 {target_client_id}")
                    target_found = True
                except Exception as e:
                    self.logger.error(f"向目标动作执行客户端 {target_client_id} 发送消息失败: {e}")
            
            # 如果目标客户端不可用或没有指定目标，根据奇偶性选择备用客户端
            if not target_found:
                available_action_clients = []
                for client_id in action_clients_copy:
                    if client_id in devices_copy:
                        available_action_clients.append(client_id)
                
                if available_action_clients:
                    sent_count = 0
                    selected_clients = []
                    
                    # 如果有目标客户端ID，根据奇偶性选择备用客户端
                    if target_client_id:
                        target_number = self.get_client_number(target_client_id)
                        target_parity = target_number % 2  # 0为偶数，1为奇数
                        
                        self.logger.info(f"目标客户端 {target_client_id} 编号: {target_number}, 奇偶性: {'奇数' if target_parity else '偶数'}")
                        
                        # 找到与目标客户端奇偶性相同的客户端
                        same_parity_clients = []
                        for client_id in available_action_clients:
                            client_number = self.get_client_number(client_id)
                            client_parity = client_number % 2
                            if client_parity == target_parity:
                                same_parity_clients.append(client_id)
                        
                        if same_parity_clients:
                            # 选择第一个奇偶性相同的客户端
                            selected_clients = [same_parity_clients[0]]
                            self.logger.info(f"找到 {len(same_parity_clients)} 个奇偶性相同的客户端，选择: {selected_clients[0]}")
                        else:
                            # 如果没有奇偶性相同的客户端，选择第一个可用的客户端
                            selected_clients = [available_action_clients[0]]
                            self.logger.warning(f"没有找到奇偶性相同的客户端，选择第一个可用客户端: {selected_clients[0]}")
                    else:
                        # 如果没有指定目标客户端，选择第一个可用的客户端
                        selected_clients = [available_action_clients[0]]
                        self.logger.info(f"没有指定目标客户端，选择第一个可用客户端: {selected_clients[0]}")
                    
                    # 发送消息到选中的客户端
                    for backup_client_id in selected_clients:
                        transport, writer, last_heartbeat = devices_copy[backup_client_id]
                        try:
                            writer.write(message_bytes)
                            await writer.drain()
                            sent_count += 1
                            self.logger.info(f"成功原样转发消息到动作执行客户端 {backup_client_id}")
                        except Exception as e:
                            self.logger.error(f"向动作执行客户端 {backup_client_id} 发送消息失败: {e}")
                    
                    if target_client_id and not target_found:
                        self.logger.warning(f"目标动作执行客户端 {target_client_id} 不可用，消息已发送到 {sent_count} 个奇偶性相同的客户端")
                    else:
                        self.logger.info(f"消息已发送到 {sent_count} 个动作执行客户端")
                else:
                    if target_client_id:
                        self.logger.warning(f"没有可用的动作执行客户端，无法发送消息 - 目标: {target_client_id}")
                    else:
                        self.logger.warning(f"没有可用的动作执行客户端，无法发送消息")
                
        except Exception as e:
            self.logger.error(f"处理 Redis 消息时发生错误，消息内容: '{message}', 错误: {e}")
            
    async def cleanup_redis(self):
        """清理 Redis 连接"""
        try:
            if self.redis_subscriber:
                await self.redis_subscriber.unsubscribe("result")
                await self.redis_subscriber.close()
                
            if self.redis_client:
                await self.redis_client.close()
                
            self.logger.info("Redis 连接已清理")
        except Exception as e:
            self.logger.error(f"清理 Redis 连接时出错: {e}")
            
    async def get_device_status(self):
        """获取设备状态统计"""
        async with self.devices_lock:
            device_count = len(self.devices)
            device_list = list(self.devices.keys())
            
        async with self.action_clients_lock:
            action_client_count = len(self.action_clients)
            action_client_list = list(self.action_clients)
            
        return {
            "online_devices": device_count,
            "device_list": device_list,
            "action_clients": action_client_count,
            "action_client_list": action_client_list,
            "timestamp": datetime.now().isoformat()
        }
        
    async def shutdown(self):
        """优雅关闭服务"""
        self.logger.info("开始关闭服务...")
        self.running = False
        
        # 关闭所有设备连接
        async with self.devices_lock:
            for device_id, (transport, writer, _) in self.devices.items():
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass
            self.devices.clear()
            
        # 清空动作执行客户端列表
        async with self.action_clients_lock:
            self.action_clients.clear()
            
        # 关闭服务器
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        # 清理 Redis 连接
        await self.cleanup_redis()
        
        self.logger.info("服务已关闭")
        
    async def run(self):
        """运行服务器"""
        try:
            await self.start_server()
            
            # 监听服务器
            async with self.server:
                await self.server.serve_forever()
                
        except KeyboardInterrupt:
            self.logger.info("收到中断信号")
        except Exception as e:
            self.logger.error(f"服务器运行时发生错误: {e}")
        finally:
            await self.shutdown()


async def status_monitor(device_manager: DeviceManager):
    """状态监控协程 - 定期打印设备状态"""
    while device_manager.running:
        try:
            status = await device_manager.get_device_status()
            device_manager.logger.info(f"当前在线设备数量: {status['online_devices']}")
            if status['device_list']:
                device_manager.logger.info(f"在线设备列表: {status['device_list']}")
            device_manager.logger.info(f"当前动作执行客户端数量: {status['action_clients']}")
            if status['action_client_list']:
                device_manager.logger.info(f"动作执行客户端列表: {status['action_client_list']}")
        except Exception as e:
            device_manager.logger.error(f"状态监控发生错误: {e}")
            
        await asyncio.sleep(30)  # 每30秒打印一次状态


def signal_handler(device_manager: DeviceManager):
    """信号处理器"""
    def handler(signum, frame):
        print(f"\n收到信号 {signum}，准备优雅关闭...")
        asyncio.create_task(device_manager.shutdown())
        
    return handler


async def main():
    """主函数"""
    # 创建设备管理器
    device_manager = DeviceManager(
        server_host="0.0.0.0",
        server_port=8889,
        redis_host="localhost",
        redis_port=6379
    )
    
    # 设置信号处理
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, signal_handler(device_manager))
    
    # 启动状态监控
    asyncio.create_task(status_monitor(device_manager))
    
    # 运行服务器
    await device_manager.run()


if __name__ == "__main__":
    asyncio.run(main()) 