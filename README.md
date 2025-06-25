# TCP 工业设备管理服务

基于 Python asyncio 的高性能 TCP 工业设备管理服务，支持设备心跳检测、动作执行客户端管理、Redis 消息转发和大规模并发连接。

## 项目特性

### 🚀 核心功能
- **异步高并发** - 基于 asyncio 架构，支持数千台设备同时连接
- **双重客户端管理** - 支持普通设备和动作执行客户端两种模式
- **智能心跳检测** - 普通设备 1 秒超时检测，动作执行客户端无超时限制
- **Redis 消息路由** - 智能解析和转发 result 消息到指定动作执行客户端

### 📡 通信协议
- **灵活消息格式** - 兼容有/无换行符的消息格式
- **设备 ID 自动提取** - 从消息中智能提取数字作为设备编号
- **动作客户端标记** - 以 'A' 开头的消息自动标记为动作执行客户端
- **Result 消息解析** - 支持标准 B\r\n 格式的坐标指令消息

### 🔧 运维特性
- **日志系统** - 每日切割日志，保留 3 天历史记录
- **状态监控** - 实时显示设备连接状态和动作客户端列表
- **自动重连** - 客户端支持断线自动重连机制
- **优雅关闭** - 支持信号处理和资源清理

## 系统要求

- Python 3.8+
- Redis 服务器
- aioredis 2.0.0+

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
# 启动 TCP 服务器（默认端口 8888）
python tcp_device_server.py

# 启动设备模拟器
python device_simulator.py --device-count 3

# 启动动作执行客户端
python action_client_simulator.py --client-id 5
```

### 3. 快速演示

```bash
# 运行完整演示
python run_demo.py

# 动作执行客户端演示
python start_demo.py
```

## 详细使用说明

### TCP 服务器配置

服务器默认配置：
- **TCP 端口**: 8888
- **Redis 地址**: localhost:6379
- **日志文件**: device_server.log

修改服务器配置：
```python
device_manager = DeviceManager(
    server_host="0.0.0.0",    # 监听地址
    server_port=8888,         # 监听端口  
    redis_host="localhost",   # Redis 地址
    redis_port=6379           # Redis 端口
)
```

### 设备模拟器

#### 单设备模拟
```bash
# 模拟设备 DEV001
python device_simulator.py --device-id DEV001

# 自定义服务器地址
python device_simulator.py --device-id DEV001 --host 192.168.1.100 --port 8888
```

#### 批量设备模拟
```bash
# 模拟 5 个设备 (DEV001-DEV005)
python device_simulator.py --device-count 5

# 自定义设备前缀
python device_simulator.py --device-count 10 --device-prefix SENSOR
```

### 动作执行客户端

```bash
# 启动默认客户端（ID: 5）
python action_client_simulator.py

# 指定客户端 ID
python action_client_simulator.py --client-id 7

# 连接远程服务器
python action_client_simulator.py --host 192.168.1.100 --port 8888 --client-id 3
```

### Redis 消息测试

#### 发送标准格式消息
```bash
# 发送到客户端 3
python redis_test_sender.py --mode standard --client 3

# 发送测试序列
python redis_test_sender.py --mode test

# 交互模式
python redis_test_sender.py --mode interactive
```

#### 自定义消息发送
```bash
# 发送自定义坐标
python redis_test_sender.py --mode custom --client 5 --x 1500.5 --y 800.3 --angle 45.0
```

## 协议规范

### 设备心跳协议

#### 普通设备心跳
```
格式: [设备编号]\n
示例: DEV001\n
      123\n
```

#### 动作执行客户端标记
```
格式: A[编号]\r\n
示例: A5\r\n  (标记为动作执行客户端 5)
      A\r\n   (使用 IP 末位作为编号)
```

**特点**：
- 支持有/无换行符格式
- 自动提取数字作为设备 ID
- 普通设备 1 秒超时断开
- 动作执行客户端无超时限制

### Redis Result 消息格式

```
格式: B\r\n[坐标数] [目标客户端ID] [预留1] [预留2] [X坐标] [Y坐标] [角度]\r\n
示例: B\r\n1 5 0 0 1597.9013671875 603.8568115234375 -0.589322\r\n
```

**字段说明**：
- **B**: 消息类型标识
- **坐标数**: 坐标点数量（通常为 1）
- **目标客户端ID**: 动作执行客户端编号
- **预留字段**: 扩展用途（设为 0）
- **X,Y坐标**: 目标位置坐标
- **角度**: 旋转角度（弧度制）

### 消息路由规则

1. **精确匹配**: 优先发送给指定 ID 的动作执行客户端
2. **奇偶备选**: 目标不可用时，选择相同奇偶性的客户端
3. **通用备选**: 无相同奇偶性时，选择任意可用客户端
4. **消息确认**: 日志记录发送状态和目标客户端

## 文件结构

```
tcp_device_server/
├── tcp_device_server.py      # 主服务器
├── device_simulator.py       # 设备模拟器
├── action_client_simulator.py # 动作客户端模拟器
├── redis_test_sender.py      # Redis 消息测试器
├── run_demo.py              # 完整演示脚本
├── start_demo.py            # 动作客户端演示
├── server.json              # PM2 配置文件
├── requirements.txt         # 依赖包列表
├── README.md               # 项目说明
├── ACTION_CLIENT_README.md  # 动作客户端详细说明
└── CHANGELOG.md            # 版本更新日志
```

## 配置选项

### 服务器参数
- `server_host`: 监听地址（默认 "0.0.0.0"）
- `server_port`: 监听端口（默认 8888）
- `redis_host`: Redis 地址（默认 "localhost"）
- `redis_port`: Redis 端口（默认 6379）

### 设备参数
- `heartbeat_interval`: 心跳间隔（默认 0.5 秒）
- `heartbeat_timeout`: 普通设备超时时间（1 秒）
- `max_buffer_size`: 缓冲区大小（1MB）

### 日志配置
- **日志文件**: device_server.log
- **切割方式**: 每日午夜切割
- **保留天数**: 3 天
- **日志级别**: DEBUG/INFO/WARNING/ERROR

## 状态监控

### 实时状态
服务器每 30 秒输出状态信息：
```
设备状态 - 在线: 5, 动作执行客户端: 2
在线设备: ['1', '2', '3', '4', '5']
动作执行客户端: ['3', '5']
```

### 日志查看
```bash
# 实时查看日志
tail -f device_server.log

# 过滤错误信息
grep "ERROR" device_server.log

# 查看特定设备日志
grep "设备 DEV001" device_server.log
```

## 测试流程

### 基础功能测试

1. **启动服务环境**
```bash
# 确保 Redis 运行
redis-server

# 启动 TCP 服务器
python tcp_device_server.py
```

2. **测试设备连接**
```bash
# 新终端：启动设备模拟器
python device_simulator.py --device-count 3
```

3. **测试动作客户端**
```bash
# 新终端：启动动作执行客户端
python action_client_simulator.py --client-id 5
```

4. **测试消息转发**
```bash
# 新终端：发送 Redis 消息
python redis_test_sender.py --mode test
```

### 高级功能测试

#### 测试无换行符消息
```bash
# 测试兼容性
python -c "
import socket
s = socket.socket()
s.connect(('localhost', 8888))
s.send(b'123')  # 无换行符
s.close()
"
```

#### 测试自动重连
```bash
# 启动客户端后关闭服务器，再重启观察重连
```

#### 测试消息路由
```bash
# 启动多个动作客户端测试路由选择
python action_client_simulator.py --client-id 3 &
python action_client_simulator.py --client-id 5 &
python redis_test_sender.py --mode test
```

## 性能特点

- **并发能力**: 支持数千台设备同时连接
- **内存效率**: 异步 I/O 减少线程开销  
- **响应速度**: 心跳检测间隔 0.5 秒，消息转发实时
- **资源控制**: 1MB 缓冲区限制，防止内存泄漏

## 故障排除

### 常见问题

#### 1. Redis 连接失败
**现象**: `连接 Redis 失败: [Errno 111] Connection refused`
**解决**: 
- 检查 Redis 服务: `redis-cli ping`
- 启动 Redis: `redis-server`
- 检查端口占用: `netstat -an | grep 6379`

#### 2. TCP 端口被占用
**现象**: `[Errno 98] Address already in use`
**解决**:
- 查找占用进程: `lsof -i :8888`
- 终止进程: `kill -9 <PID>`
- 更换端口: 修改 `server_port` 参数

#### 3. 设备连接超时
**现象**: 设备频繁断开重连
**解决**:
- 检查网络稳定性
- 调整心跳间隔: `heartbeat_interval=1.0`
- 查看设备日志排查具体原因

#### 4. 消息路由失败
**现象**: Redis 消息发送但客户端未收到
**解决**:
- 确认动作客户端已连接并标记
- 检查消息格式是否正确
- 查看服务器日志的路由信息

### 调试技巧

1. **开启详细日志**: 设置日志级别为 DEBUG
2. **监控 Redis**: 使用 `redis-cli monitor` 查看消息
3. **网络抓包**: 使用 tcpdump 分析 TCP 通信
4. **性能分析**: 使用 top/htop 监控资源使用

## 扩展开发

### 添加新消息类型

```python
# 在 process_redis_message 方法中添加
if message.startswith('C'):
    # 处理 C 类型消息
    await self.handle_c_message(message)
```

### 自定义客户端类型

```python
# 在 process_message 方法中添加标记逻辑
if 'B' in message_str:
    # B 类型客户端处理
    self.b_clients.add(device_id_str)
```

### 集成外部系统

```python
# 添加数据库存储
async def save_to_database(self, device_data):
    # 实现数据库存储逻辑
    pass
```

## 许可证

本项目采用 MIT 许可证。

## 支持

如有问题或建议，请查看：
- [更新日志](CHANGELOG.md)
- [动作客户端详细说明](ACTION_CLIENT_README.md)

---

**注意**: 生产环境部署时请注意网络安全配置，建议使用防火墙限制访问范围。 