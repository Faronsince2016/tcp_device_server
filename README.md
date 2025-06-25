# TCP 工业设备管理服务

基于 Python asyncio 的高性能 TCP 工业设备管理服务，支持设备心跳检测、Redis 消息转发和大规模并发连接。

## 特性

- 🚀 **100% 异步处理** - 基于 asyncio，支持数千台设备并发连接
- 💓 **智能心跳检测** - 设备每 500ms 发送心跳，1秒超时自动断开
- 📡 **Redis 消息转发** - 自动订阅 Redis 频道并转发消息到指定设备
- 📝 **完善日志系统** - 日志同时输出到文件和控制台，便于监控和调试
- 🔄 **自动重连机制** - 网络中断时自动重连，保证服务稳定性
- 🛡️ **异常处理** - 全面的异常捕获和处理，确保服务长期稳定运行

## 系统要求

- Python 3.8+
- Redis 服务器

## 安装

1. 克隆或下载项目文件
2. 安装依赖包：

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 启动 TCP 服务器

```bash
python tcp_device_server.py
```

服务器默认配置：
- TCP 端口: 8889
- Redis 地址: localhost:6379
- 日志文件: device_server.log

### 2. 运行设备模拟器

#### 单个设备模拟
```bash
# 模拟设备 DEV001
python device_simulator.py --device-id DEV001

# 自定义服务器地址
python device_simulator.py --device-id DEV001 --host 192.168.1.100 --port 8889
```

#### 多设备模拟
```bash
# 模拟 5 个设备 (DEV001-DEV005)
python device_simulator.py --device-count 5

# 自定义设备前缀
python device_simulator.py --device-count 10 --device-prefix SENSOR
```

### 3. 发送 Redis 测试消息

#### 发送单条消息
```bash
# 发送消息到设备 DEV001
python redis_test_sender.py --device DEV001 --message "start_operation"

# 完整示例
python redis_test_sender.py --host localhost --port 6379 --device DEV001 --message "get_status"
```

#### 批量发送消息
```bash
# 向多个设备发送测试消息
python redis_test_sender.py --mode multiple --devices DEV001 DEV002 DEV003
```

#### 交互式发送
```bash
# 进入交互模式，手动输入消息
python redis_test_sender.py --mode interactive
```

## 协议说明

### 设备心跳协议

设备连接到服务器后，需要每 500ms 发送一次心跳包：

```
格式: 设备编号\n
示例: DEV001\n
```

- 使用 ASCII 编码
- 以换行符 `\n` 结尾
- 服务器 1 秒内未收到心跳则判定设备掉线

### Redis 消息格式

Redis 频道 `result` 中的消息格式：

```
格式: command,device_id,additional_data
示例: start_operation,DEV001,param1=value1,param2=value2
```

- 使用英文逗号 `,` 分割字段
- 第二个字段为目标设备编号
- 消息会原样转发给对应设备

## 配置选项

### TCP 服务器配置

可以通过修改 `tcp_device_server.py` 中的 `DeviceManager` 初始化参数：

```python
device_manager = DeviceManager(
    server_host="0.0.0.0",    # 监听地址
    server_port=8889,         # 监听端口
    redis_host="localhost",   # Redis 地址
    redis_port=6379          # Redis 端口
)
```

### 日志配置

日志文件位置：`device_server.log`

日志级别可通过修改 `logging.basicConfig` 的 `level` 参数调整：
- `logging.DEBUG` - 详细调试信息
- `logging.INFO` - 常规信息（默认）
- `logging.WARNING` - 警告信息
- `logging.ERROR` - 错误信息

## 测试流程

### 完整测试示例

1. **启动 Redis 服务器**（如果还没有运行）
```bash
redis-server
```

2. **启动 TCP 设备管理服务**
```bash
python tcp_device_server.py
```

3. **启动设备模拟器**（新终端）
```bash
python device_simulator.py --device-count 3
```

4. **发送测试消息**（新终端）
```bash
python redis_test_sender.py --mode multiple --devices DEV001 DEV002 DEV003
```

### 预期结果

- 服务器日志显示设备连接和心跳信息
- 设备模拟器显示接收到的服务器消息
- Redis 消息被正确转发到目标设备

## 性能特点

- **高并发**: 支持数千台设备同时连接
- **低延迟**: 心跳检测间隔 200ms，消息转发实时
- **内存效率**: 异步 I/O 减少线程开销
- **网络优化**: 自动处理连接中断和重连

## 故障排除

### 常见问题

1. **Redis 连接失败**
   - 检查 Redis 服务是否启动
   - 确认 Redis 地址和端口配置正确

2. **设备连接失败**
   - 检查 TCP 服务器是否正常启动
   - 确认防火墙设置允许相应端口

3. **心跳超时**
   - 检查网络连接稳定性
   - 调整心跳间隔设置

### 日志分析

查看 `device_server.log` 文件了解详细运行状态：

```bash
# 实时查看日志
tail -f device_server.log

# 过滤错误信息
grep "ERROR" device_server.log

# 过滤设备连接信息
grep "设备.*连接" device_server.log
```

## 扩展开发

### 添加新功能

1. **自定义消息处理**: 修改 `process_redis_message` 方法
2. **设备状态监控**: 扩展 `get_device_status` 方法
3. **数据持久化**: 添加数据库存储功能
4. **Web 管理界面**: 集成 Web 框架提供管理界面

### 性能优化

1. **连接池管理**: 优化 Redis 连接池配置
2. **消息缓冲**: 添加消息队列缓冲机制
3. **负载均衡**: 多实例部署和负载分担

## 许可证

MIT License 