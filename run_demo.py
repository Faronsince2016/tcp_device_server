#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
演示脚本 - 快速启动和测试 TCP 工业设备管理服务
"""

import asyncio
import subprocess
import sys
import time
import signal
import os
from pathlib import Path


class DemoRunner:
    """演示运行器"""
    
    def __init__(self):
        self.processes = []
        self.running = False
        
    def start_process(self, command: list, name: str, delay: float = 0):
        """启动子进程"""
        try:
            if delay > 0:
                time.sleep(delay)
                
            print(f"启动 {name}...")
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            self.processes.append((process, name))
            print(f"{name} 已启动 (PID: {process.pid})")
            return process
            
        except Exception as e:
            print(f"启动 {name} 失败: {e}")
            return None
            
    def stop_all_processes(self):
        """停止所有子进程"""
        print("\n正在停止所有进程...")
        
        for process, name in self.processes:
            try:
                if process.poll() is None:  # 进程仍在运行
                    print(f"停止 {name} (PID: {process.pid})")
                    process.terminate()
                    
                    # 等待进程结束
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"强制结束 {name}")
                        process.kill()
                        
            except Exception as e:
                print(f"停止 {name} 时出错: {e}")
                
        self.processes.clear()
        print("所有进程已停止")
        
    def check_dependencies(self):
        """检查依赖"""
        print("检查依赖文件...")
        
        required_files = [
            "tcp_device_server.py",
            "device_simulator.py", 
            "redis_test_sender.py",
            "requirements.txt"
        ]
        
        missing_files = []
        for file in required_files:
            if not Path(file).exists():
                missing_files.append(file)
                
        if missing_files:
            print(f"错误: 以下文件缺失: {missing_files}")
            return False
            
        print("依赖检查通过")
        return True
        
    def wait_for_services(self):
        """等待服务启动"""
        print("等待服务启动...")
        time.sleep(3)  # 等待服务器完全启动
        
    def run_demo(self):
        """运行完整演示"""
        if not self.check_dependencies():
            return
            
        self.running = True
        
        try:
            print("=" * 60)
            print("TCP 工业设备管理服务演示")
            print("=" * 60)
            
            # 1. 启动 TCP 服务器
            server_process = self.start_process(
                [sys.executable, "tcp_device_server.py"],
                "TCP 设备管理服务器"
            )
            
            if not server_process:
                return
                
            # 2. 等待服务器启动
            self.wait_for_services()
            
            # 3. 启动设备模拟器
            simulator_process = self.start_process(
                [sys.executable, "device_simulator.py", "--device-count", "3"],
                "设备模拟器 (3台设备)",
                delay=1
            )
            
            if not simulator_process:
                return
                
            # 4. 等待设备连接
            print("等待设备连接...")
            time.sleep(2)
            
            # 5. 发送测试消息
            print("\n发送测试消息...")
            test_process = self.start_process(
                [sys.executable, "redis_test_sender.py", 
                 "--mode", "multiple", 
                 "--devices", "DEV001", "DEV002", "DEV003",
                 "--interval", "3"],
                "Redis 消息测试器",
                delay=1
            )
            
            print("\n" + "=" * 60)
            print("演示正在运行...")
            print("观察点:")
            print("1. 服务器日志显示设备连接信息")
            print("2. 设备模拟器显示心跳发送和消息接收")
            print("3. Redis 消息被转发到对应设备")
            print("4. 日志文件 device_server.log 记录详细信息")
            print("\n按 Ctrl+C 停止演示")
            print("=" * 60)
            
            # 监控进程状态
            while self.running:
                # 检查进程是否还在运行
                running_processes = []
                for process, name in self.processes:
                    if process.poll() is None:
                        running_processes.append((process, name))
                    else:
                        print(f"{name} 已退出")
                        
                self.processes = running_processes
                
                if not self.processes:
                    print("所有进程已退出")
                    break
                    
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n收到中断信号")
        except Exception as e:
            print(f"演示过程中发生错误: {e}")
        finally:
            self.running = False
            self.stop_all_processes()
            
    def run_simple_test(self):
        """运行简单测试"""
        if not self.check_dependencies():
            return
            
        print("运行简单功能测试...")
        
        try:
            # 启动服务器
            print("启动服务器...")
            server_process = self.start_process(
                [sys.executable, "tcp_device_server.py"],
                "TCP 服务器"
            )
            
            time.sleep(2)
            
            # 启动单个设备
            print("启动测试设备...")
            device_process = self.start_process(
                [sys.executable, "device_simulator.py", "--device-id", "TEST001"],
                "测试设备"
            )
            
            time.sleep(2)
            
            # 发送单条测试消息
            print("发送测试消息...")
            subprocess.run([
                sys.executable, "redis_test_sender.py",
                "--device", "TEST001",
                "--message", "test_command"
            ], timeout=10)
            
            print("简单测试完成，等待 5 秒后自动停止...")
            time.sleep(5)
            
        except Exception as e:
            print(f"测试过程中发生错误: {e}")
        finally:
            self.stop_all_processes()


def signal_handler(signum, frame):
    """信号处理"""
    print(f"\n收到信号 {signum}")
    sys.exit(0)


def main():
    """主函数"""
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--simple":
        print("运行简单测试模式")
        runner = DemoRunner()
        runner.run_simple_test()
    else:
        print("运行完整演示模式")
        print("提示: 使用 --simple 参数运行简单测试")
        runner = DemoRunner()
        runner.run_demo()


if __name__ == "__main__":
    main() 