#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动作执行客户端模拟器
每5秒向TCP服务器发送A\r\n，标记自己为动作执行客户端
"""

import asyncio
import logging
import sys
import signal
import time
from datetime import datetime


class ActionClientSimulator:
    """动作执行客户端模拟器"""
    
    def __init__(self, server_host: str = "localhost", server_port: int = 8889, 
                 client_id: str = "5"):
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = client_id
        self.running = False
        self.reader = None
        self.writer = None
        
        # 配置日志
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
    def setup_logging(self):
        """配置日志系统"""
        log_format = '%(asctime)s - ActionClient-%(name)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt=date_format,
            handlers=[
                logging.FileHandler(f'action_client_{self.client_id}.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
    async def connect_to_server(self):
        """连接到TCP服务器"""
        try:
            self.logger.info(f"正在连接到服务器 {self.server_host}:{self.server_port}")
            self.reader, self.writer = await asyncio.open_connection(
                self.server_host, self.server_port
            )
            self.logger.info("成功连接到服务器")
            return True
        except Exception as e:
            self.logger.error(f"连接服务器失败: {e}")
            return False
            
    async def send_heartbeat(self):
        """发送心跳消息（A\r\n）"""
        try:
            if self.writer and not self.writer.is_closing():
                # 发送A + 客户端ID + \r\n
                heartbeat_message = f"A\r\n"
                self.writer.write(heartbeat_message.encode('utf-8'))
                await self.writer.drain()
                self.logger.info(f"发送心跳消息: {heartbeat_message.strip()}")
                return True
            else:
                self.logger.warning("连接已断开，无法发送心跳")
                return False
        except Exception as e:
            self.logger.error(f"发送心跳消息失败: {e}")
            return False
            
    async def receive_messages(self):
        """接收服务器消息"""
        try:
            while self.running and self.reader:
                try:
                    data = await asyncio.wait_for(self.reader.read(1024), timeout=1.0)
                    if not data:
                        self.logger.warning("服务器连接已断开")
                        break
                    
                    # 原样打印接收到的数据
                    self.logger.info(f"收到服务器数据: {data.decode('utf-8', errors='ignore')}")
                    self.logger.info(f"原始字节数据: {data!r}")
                    
                except asyncio.TimeoutError:
                    continue  # 超时继续
                except Exception as e:
                    self.logger.error(f"接收消息时发生错误: {e}")
                    break
                    
        except Exception as e:
            self.logger.error(f"消息接收协程发生错误: {e}")
        finally:
            self.logger.info("消息接收协程结束")
            
    async def heartbeat_loop(self):
        """心跳循环 - 每2秒发送一次心跳"""
        while self.running:
            success = await self.send_heartbeat()
            if not success:
                self.logger.error("心跳发送失败，尝试重新连接")
                await self.reconnect()
            
            await asyncio.sleep(2)  # 每2秒发送一次心跳
            
    async def reconnect(self):
        """重新连接到服务器"""
        self.logger.info("尝试重新连接...")
        
        # 清理现有连接
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        
        # 尝试重新连接
        max_retries = 5
        for retry in range(max_retries):
            await asyncio.sleep(2)  # 等待2秒后重试
            if await self.connect_to_server():
                self.logger.info("重新连接成功")
                return True
            else:
                self.logger.warning(f"重新连接失败 ({retry + 1}/{max_retries})")
        
        self.logger.error("重新连接失败，停止客户端")
        self.running = False
        return False
        
    async def shutdown(self):
        """优雅关闭客户端"""
        self.logger.info("开始关闭动作执行客户端...")
        self.running = False
        
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
                
        self.logger.info("动作执行客户端已关闭")
        
    async def run(self):
        """运行客户端"""
        self.running = True
        
        try:
            # 连接到服务器
            if not await self.connect_to_server():
                self.logger.error("无法连接到服务器，退出")
                return
            
            # 立即发送一次心跳，标记为动作执行客户端
            await self.send_heartbeat()
            
            # 启动消息接收协程
            receive_task = asyncio.create_task(self.receive_messages())
            
            # 启动心跳循环
            heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            
            # 等待任务完成
            await asyncio.gather(receive_task, heartbeat_task, return_exceptions=True)
            
        except KeyboardInterrupt:
            self.logger.info("收到中断信号")
        except Exception as e:
            self.logger.error(f"客户端运行时发生错误: {e}")
        finally:
            await self.shutdown()


def signal_handler(client):
    """信号处理器"""
    def handler(signum, frame):
        print(f"\n收到信号 {signum}，准备关闭客户端...")
        asyncio.create_task(client.shutdown())
    return handler


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='动作执行客户端模拟器')
    parser.add_argument('--host', default='localhost', help='服务器地址 (默认: localhost)')
    parser.add_argument('--port', type=int, default=8889, help='服务器端口 (默认: 8889)')
    parser.add_argument('--client-id', default='5', help='客户端ID (默认: 5)')
    
    args = parser.parse_args()
    
    # 创建动作执行客户端
    client = ActionClientSimulator(
        server_host=args.host,
        server_port=args.port,
        client_id=args.client_id
    )
    
    # 设置信号处理
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, signal_handler(client))
    
    # 运行客户端
    await client.run()


if __name__ == "__main__":
    asyncio.run(main()) 