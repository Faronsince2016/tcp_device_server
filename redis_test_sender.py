#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Redis 消息发送测试脚本
用于向 result 频道发送标准格式的测试消息
格式: 'B\r\n1 3 0 0 1597.9013671875 603.8568115234375 -0.589322\r\n'
"""

import asyncio
import aioredis
import sys
import argparse
import time
import random


async def send_standard_message(redis_host: str = "localhost", redis_port: int = 6379, 
                               target_client: str = "3"):
    """发送标准格式的测试消息到 Redis"""
    try:
        # 连接 Redis
        redis_client = aioredis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
        
        # 测试连接
        await redis_client.ping()
        print(f"成功连接到 Redis {redis_host}:{redis_port}")
        
        # 构造标准格式消息: B\r\n坐标数 客户端ID 预留1 预留2 x y 角度\r\n
        message = f"B\r\n1 {target_client} 0 0 1597.9013671875 603.8568115234375 -0.589322\r\n"
        
        # 发送消息到 result 频道
        result = await redis_client.publish("result", message)
        print(f"消息发送成功，订阅者数量: {result}")
        print(f"发送的消息: {repr(message)}")
        
        await redis_client.close()
        
    except Exception as e:
        print(f"发送消息时发生错误: {e}")
        sys.exit(1)


async def send_custom_message(redis_host: str = "localhost", redis_port: int = 6379,
                             target_client: str = "3", x: float = 1597.9, y: float = 603.9, 
                             angle: float = -0.589):
    """发送自定义参数的消息"""
    try:
        # 连接 Redis
        redis_client = aioredis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
        
        await redis_client.ping()
        print(f"成功连接到 Redis {redis_host}:{redis_port}")
        
        # 构造消息
        message = f"B\r\n1 {target_client} 0 0 {x} {y} {angle}\r\n"
        
        # 发送消息
        result = await redis_client.publish("result", message)
        print(f"自定义消息发送成功，订阅者数量: {result}")
        print(f"发送的消息: {repr(message)}")
        
        await redis_client.close()
        
    except Exception as e:
        print(f"发送消息时发生错误: {e}")
        sys.exit(1)


async def send_test_sequence(redis_host: str = "localhost", redis_port: int = 6379,
                            client_list: list = None, interval: float = 2.0):
    """发送测试序列消息"""
    if client_list is None:
        client_list = ["3", "5", "7"]
        
    try:
        # 连接 Redis
        redis_client = aioredis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
        
        await redis_client.ping()
        print(f"成功连接到 Redis {redis_host}:{redis_port}")
        print(f"开始发送测试序列，目标客户端: {client_list}")
        
        for i in range(5):  # 发送5轮消息
            for client_id in client_list:
                # 生成随机坐标和角度
                x = random.uniform(1000, 2000)
                y = random.uniform(500, 800) 
                angle = random.uniform(-1, 1)
                
                # 构造消息
                message = f"B\r\n1 {client_id} 0 0 {x:.10f} {y:.10f} {angle:.6f}\r\n"
                
                # 发送消息
                result = await redis_client.publish("result", message)
                print(f"[轮次 {i+1}] 发送到客户端 {client_id}: 坐标({x:.2f}, {y:.2f}) 角度{angle:.3f} (订阅者: {result})")
                
                await asyncio.sleep(0.5)  # 客户端间间隔
                
            print(f"轮次 {i+1} 完成，等待 {interval} 秒...")
            await asyncio.sleep(interval)
            
        await redis_client.close()
        print("测试序列发送完成")
        
    except Exception as e:
        print(f"发送测试序列时发生错误: {e}")
        sys.exit(1)


async def interactive_sender(redis_host: str = "localhost", redis_port: int = 6379):
    """交互式消息发送"""
    try:
        # 连接 Redis
        redis_client = aioredis.from_url(
            f"redis://{redis_host}:{redis_port}",
            encoding="utf-8",
            decode_responses=True
        )
        
        await redis_client.ping()
        print(f"成功连接到 Redis {redis_host}:{redis_port}")
        print("进入交互模式，输入 'quit' 退出")
        print("可用命令:")
        print("1. 'std' - 发送标准测试消息")
        print("2. 'custom <client_id> <x> <y> <angle>' - 发送自定义消息")
        print("3. 'B\\r\\n1 3 0 0 1597.9 603.9 -0.589\\r\\n' - 直接输入完整消息")
        
        while True:
            try:
                user_input = input("\n请输入命令或消息: ").strip()
                
                if user_input.lower() == 'quit':
                    break
                    
                if not user_input:
                    continue
                
                message = None
                
                if user_input.lower() == 'std':
                    # 标准消息
                    message = "B\r\n1 3 0 0 1597.9013671875 603.8568115234375 -0.589322\r\n"
                elif user_input.startswith('custom '):
                    # 自定义消息
                    try:
                        parts = user_input.split()
                        if len(parts) >= 5:
                            client_id = parts[1]
                            x = float(parts[2])
                            y = float(parts[3])
                            angle = float(parts[4])
                            message = f"B\r\n1 {client_id} 0 0 {x} {y} {angle}\r\n"
                        else:
                            print("错误: custom 命令格式为 'custom <client_id> <x> <y> <angle>'")
                            continue
                    except ValueError:
                        print("错误: x, y, angle 必须为数字")
                        continue
                elif user_input.startswith('B'):
                    # 直接输入的消息
                    # 处理转义字符
                    message = user_input.replace('\\r', '\r').replace('\\n', '\n')
                else:
                    print("未识别的命令，请重新输入")
                    continue
                
                if message:
                    # 发送消息
                    result = await redis_client.publish("result", message)
                    print(f"消息发送成功: {repr(message)} (订阅者: {result})")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"发送消息出错: {e}")
                
        await redis_client.close()
        print("已退出交互模式")
        
    except Exception as e:
        print(f"连接 Redis 时发生错误: {e}")
        sys.exit(1)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Redis Result消息发送测试工具")
    parser.add_argument("--host", type=str, default="localhost", help="Redis 服务器地址")
    parser.add_argument("--port", type=int, default=6379, help="Redis 服务器端口")
    parser.add_argument("--client", type=str, default="3", help="目标动作执行客户端ID")
    parser.add_argument("--mode", type=str, choices=["standard", "custom", "sequence", "interactive"], 
                       default="standard", help="运行模式")
    parser.add_argument("--clients", type=str, nargs="+", 
                       default=["3", "5", "7"], help="序列模式的客户端ID列表")
    parser.add_argument("--interval", type=float, default=2.0, help="序列模式的轮次间隔")
    parser.add_argument("--x", type=float, default=1597.9013671875, help="X坐标")
    parser.add_argument("--y", type=float, default=603.8568115234375, help="Y坐标")
    parser.add_argument("--angle", type=float, default=-0.589322, help="角度")
    
    args = parser.parse_args()
    
    print("=== Redis Result消息发送测试工具 ===")
    print("标准消息格式: B\\r\\n1 <client_id> 0 0 <x> <y> <angle>\\r\\n")
    print(f"使用模式: {args.mode}")
    print()
    
    try:
        if args.mode == "standard":
            await send_standard_message(args.host, args.port, args.client)
        elif args.mode == "custom":
            await send_custom_message(args.host, args.port, args.client, args.x, args.y, args.angle)
        elif args.mode == "sequence":
            await send_test_sequence(args.host, args.port, args.clients, args.interval)
        elif args.mode == "interactive":
            await interactive_sender(args.host, args.port)
            
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序发生未处理错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 