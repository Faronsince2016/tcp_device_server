#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工业设备模拟器
模拟设备连接到TCP服务器并定期发送心跳
"""

import asyncio
import random
import sys
import argparse
import logging
from typing import Optional


class DeviceSimulator:
    """设备模拟器"""
    
    def __init__(self, device_id: str, server_host: str = "localhost", 
                 server_port: int = 8889, heartbeat_interval: float = 0.5):
        self.device_id = device_id
        self.server_host = server_host
        self.server_port = server_port
        self.heartbeat_interval = heartbeat_interval
        
        # 连接对象
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.running = False
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(f"Device-{device_id}")
        
    async def connect_to_server(self):
        """连接到服务器"""
        try:
            self.logger.info(f"连接到服务器 {self.server_host}:{self.server_port}")
            self.reader, self.writer = await asyncio.open_connection(
                self.server_host, self.server_port
            )
            self.logger.info("连接成功")
            return True
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            return False
            
    async def send_heartbeat(self):
        """发送心跳包"""
        try:
            if self.writer and not self.writer.is_closing():
                heartbeat_data = f"{self.device_id}\n".encode('ascii')
                self.writer.write(heartbeat_data)
                await self.writer.drain()
                self.logger.debug(f"发送心跳: {self.device_id}")
                return True
        except Exception as e:
            self.logger.error(f"发送心跳失败: {e}")
            return False
        return False
        
    async def receive_messages(self):
        """接收服务器消息"""
        try:
            while self.running and self.reader:
                try:
                    data = await asyncio.wait_for(self.reader.readline(), timeout=1.0)
                    if not data:
                        self.logger.warning("服务器关闭连接")
                        break
                        
                    message = data.decode('utf-8').strip()
                    if message:
                        self.logger.info(f"收到服务器消息: {message}")
                        
                except asyncio.TimeoutError:
                    # 超时是正常的，继续等待
                    continue
                    
        except Exception as e:
            self.logger.error(f"接收消息时发生错误: {e}")
            
    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            success = await self.send_heartbeat()
            if not success:
                self.logger.error("心跳发送失败，尝试重连")
                await self.reconnect()
                
            await asyncio.sleep(self.heartbeat_interval)
            
    async def reconnect(self):
        """重连逻辑"""
        await self.disconnect()
        await asyncio.sleep(2)  # 等待2秒后重连
        
        max_retries = 5
        for attempt in range(max_retries):
            self.logger.info(f"重连尝试 {attempt + 1}/{max_retries}")
            if await self.connect_to_server():
                break
            await asyncio.sleep(5)  # 重连失败等待5秒
        else:
            self.logger.error("重连失败次数过多，停止运行")
            self.running = False
            
    async def disconnect(self):
        """断开连接"""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None
            
    async def run(self):
        """运行设备模拟器"""
        self.running = True
        
        # 连接到服务器
        if not await self.connect_to_server():
            self.logger.error("初始连接失败")
            return
            
        try:
            # 启动心跳和消息接收任务
            heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            receive_task = asyncio.create_task(self.receive_messages())
            
            # 等待任务完成或被取消
            await asyncio.gather(heartbeat_task, receive_task, return_exceptions=True)
            
        except KeyboardInterrupt:
            self.logger.info("收到中断信号")
        except Exception as e:
            self.logger.error(f"运行时发生错误: {e}")
        finally:
            self.running = False
            await self.disconnect()
            self.logger.info("设备模拟器已停止")


class MultiDeviceSimulator:
    """多设备模拟器"""
    
    def __init__(self, device_count: int, device_prefix: str = "DEV", 
                 server_host: str = "localhost", server_port: int = 8889):
        self.device_count = device_count
        self.device_prefix = device_prefix
        self.server_host = server_host
        self.server_port = server_port
        self.simulators = []
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger("MultiDeviceSimulator")
        
    async def run(self):
        """运行多个设备模拟器"""
        # 创建设备模拟器
        tasks = []
        
        for i in range(self.device_count):
            device_id = f"{self.device_prefix}{i+1:03d}"  # DEV001, DEV002, ...
            
            # 添加一些随机延迟，避免所有设备同时连接
            heartbeat_interval = 0.5 + random.uniform(-0.05, 0.05)
            
            simulator = DeviceSimulator(
                device_id=device_id,
                server_host=self.server_host,
                server_port=self.server_port,
                heartbeat_interval=heartbeat_interval
            )
            
            self.simulators.append(simulator)
            
            # 创建设备运行任务
            task = asyncio.create_task(simulator.run())
            tasks.append(task)
            
            # 错开连接时间，避免同时连接造成压力
            await asyncio.sleep(0.1)
            
        self.logger.info(f"启动了 {self.device_count} 个设备模拟器")
        
        try:
            # 等待所有设备任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，停止所有设备模拟器")
        finally:
            # 停止所有设备
            for simulator in self.simulators:
                simulator.running = False
                await simulator.disconnect()


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="工业设备模拟器")
    parser.add_argument("--device-id", type=str, help="单个设备ID")
    parser.add_argument("--device-count", type=int, default=1, help="模拟设备数量 (默认: 1)")
    parser.add_argument("--device-prefix", type=str, default="DEV", help="设备ID前缀 (默认: DEV)")
    parser.add_argument("--host", type=str, default="localhost", help="服务器地址 (默认: localhost)")
    parser.add_argument("--port", type=int, default=8889, help="服务器端口 (默认: 8889)")
    parser.add_argument("--interval", type=float, default=0.5, help="心跳间隔(秒) (默认: 0.5)")
    
    args = parser.parse_args()
    
    try:
        if args.device_id:
            # 单设备模式
            simulator = DeviceSimulator(
                device_id=args.device_id,
                server_host=args.host,
                server_port=args.port,
                heartbeat_interval=args.interval
            )
            await simulator.run()
        else:
            # 多设备模式
            multi_simulator = MultiDeviceSimulator(
                device_count=args.device_count,
                device_prefix=args.device_prefix,
                server_host=args.host,
                server_port=args.port
            )
            await multi_simulator.run()
            
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序发生未处理错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 