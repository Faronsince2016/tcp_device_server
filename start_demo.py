#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动作执行客户端功能演示启动脚本
自动启动服务器和客户端进行演示
"""

import asyncio
import subprocess
import time
import sys
import os
import signal
from typing import List


class DemoManager:
    """演示管理器"""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.running = True
        
    def start_process(self, command: List[str], name: str):
        """启动一个进程"""
        try:
            print(f"启动 {name}...")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            self.processes.append(process)
            print(f"✓ {name} 已启动 (PID: {process.pid})")
            return process
        except Exception as e:
            print(f"✗ 启动 {name} 失败: {e}")
            return None
            
    def cleanup(self):
        """清理所有进程"""
        print("\n正在关闭所有进程...")
        for process in self.processes:
            try:
                if process.poll() is None:  # 进程仍在运行
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    print(f"✓ 进程 {process.pid} 已关闭")
            except Exception as e:
                print(f"✗ 关闭进程时出错: {e}")
        
        self.processes.clear()
        print("所有进程已关闭")
        
    def wait_for_startup(self, seconds: int = 3):
        """等待服务启动"""
        print(f"等待 {seconds} 秒让服务启动...")
        time.sleep(seconds)
        
    def check_redis(self):
        """检查Redis是否可用"""
        try:
            import aioredis
            print("✓ aioredis 模块可用")
            return True
        except ImportError:
            print("✗ 缺少 aioredis 模块，请运行: pip install aioredis")
            return False
            
    def run_demo(self):
        """运行演示"""
        print("=== 动作执行客户端功能演示 ===\n")
        
        # 检查依赖
        if not self.check_redis():
            return
            
        try:
            # 启动TCP服务器
            server_process = self.start_process(
                [sys.executable, "tcp_device_server.py"],
                "TCP服务器"
            )
            if not server_process:
                return
                
            self.wait_for_startup(3)
            
            # 启动第一个动作执行客户端
            client1_process = self.start_process(
                [sys.executable, "action_client_simulator.py", "--client-id", "5"],
                "动作执行客户端-5"
            )
            
            self.wait_for_startup(2)
            
            # 启动第二个动作执行客户端
            client2_process = self.start_process(
                [sys.executable, "action_client_simulator.py", "--client-id", "6"],
                "动作执行客户端-6"
            )
            
            self.wait_for_startup(2)
            
            print("\n=== 演示环境启动完成 ===")
            print("现在您可以:")
            print("1. 观察各个终端的日志输出")
            print("2. 在新终端中运行测试: python test_result_sender.py --mode test")
            print("3. 或者交互测试: python test_result_sender.py --mode interactive")
            print("4. 按 Ctrl+C 停止演示\n")
            
            # 保持运行直到用户中断
            while self.running:
                time.sleep(1)
                
                # 检查进程是否意外退出
                for process in self.processes[:]:
                    if process.poll() is not None:
                        print(f"⚠ 进程 {process.pid} 意外退出")
                        self.processes.remove(process)
                        
        except KeyboardInterrupt:
            print("\n收到中断信号，正在停止演示...")
            self.running = False
        except Exception as e:
            print(f"演示运行时发生错误: {e}")
        finally:
            self.cleanup()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='动作执行客户端功能演示')
    parser.add_argument('--quick-test', action='store_true', 
                       help='快速测试模式（自动发送测试消息）')
    
    args = parser.parse_args()
    
    demo = DemoManager()
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}")
        demo.running = False
        demo.cleanup()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        demo.run_demo()
        
        if args.quick_test:
            print("\n执行快速测试...")
            time.sleep(2)
            test_process = demo.start_process(
                [sys.executable, "test_result_sender.py", "--mode", "test"],
                "测试发送器"
            )
            if test_process:
                test_process.wait()
                
    except Exception as e:
        print(f"程序发生错误: {e}")
    finally:
        demo.cleanup()


if __name__ == "__main__":
    main() 