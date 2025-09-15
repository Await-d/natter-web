# Natter Web MCP服务使用指南

## 概述

Natter Web的MCP (Model Context Protocol) 服务为外部工具和AI系统提供了标准化的编程接口，允许通过HTTP API访问和控制Natter网络隧道服务。

## 功能特性

- 🔐 **安全认证** - 支持管理员和访客两种角色认证
- 🛠️ **服务管理** - 列出、查询、启动、停止、重启Natter服务
- 📡 **实时通知** - 支持服务状态变更的实时推送
- 🔌 **标准协议** - 完全兼容MCP 1.0规范
- 📋 **权限控制** - 基于角色的工具访问控制
- 🌐 **多协议支持** - HTTP、WebSocket、TCP、stdio、SSE传输协议

## 快速开始

### 1. 启动Natter Web服务器

```bash
cd web
python3 server.py
```

### 2. 配置环境变量 (可选)

```bash
export MCP_ENABLED=true
export MCP_MAX_CONNECTIONS=10
export MCP_TIMEOUT=30

# 多协议配置
export MCP_WEBSOCKET_ENABLED=true
export MCP_WEBSOCKET_PORT=8081
export MCP_TCP_ENABLED=true
export MCP_TCP_PORT=8082
export MCP_STDIO_ENABLED=true
export MCP_SSE_ENABLED=true
```

### 3. 运行示例客户端

```bash
python3 mcp_examples/mcp_client_example.py
```

## 支持的传输协议

### 1. HTTP/HTTPS (默认)
- **端点**: `POST /api/mcp`
- **端口**: 8080 (默认Web端口)
- **认证**: 支持Header和Body认证

### 2. WebSocket
- **端点**: `ws://localhost:8081`
- **特性**: 全双工实时通信，支持推送通知
- **认证**: 连接建立时认证

### 3. TCP直连
- **端点**: `tcp://localhost:8082`
- **特性**: 原生TCP协议，高性能
- **格式**: 长度前缀 + JSON消息

### 4. Server-Sent Events (SSE)
- **端点**: `GET /api/mcp/sse`
- **特性**: 单向实时推送，基于HTTP
- **用途**: 主要用于接收通知

### 5. stdio
- **启动**: `python3 server.py --mcp-stdio`
- **特性**: 标准输入输出，适合命令行工具
- **格式**: 每行一个JSON消息

## API端点

### HTTP端点
- **URL**: `POST /api/mcp`
- **Content-Type**: `application/json`

### 认证方式

#### 1. HTTP认证头
```bash
# Basic认证 (管理员)
Authorization: Basic base64(username:admin_password)

# Bearer Token
Authorization: Bearer your_token_here
```

#### 2. 请求体认证
```json
{
  "auth": {
    "password": "your_password"
  },
  "message": {...}
}
```

## 可用工具

### 1. natter/list_services
列出当前所有服务及其状态信息

**参数：**
```json
{
  "filter": "all|running|stopped",  // 可选，默认"all"
  "group": "group_id"              // 可选，访客用户组过滤
}
```

### 2. natter/get_service_status
获取指定服务的详细状态信息

**参数：**
```json
{
  "service_id": "service_id"  // 必需
}
```

### 3. natter/start_service (仅管理员)
启动一个新的Natter服务

**参数：**
```json
{
  "local_port": 8080,    // 必需，本地端口号
  "keep_alive": 30,      // 可选，保持连接时间(秒)，默认30
  "remark": "备注信息"    // 可选，服务备注
}
```

### 4. natter/stop_service (仅管理员)
停止指定的Natter服务

**参数：**
```json
{
  "service_id": "service_id"  // 必需
}
```

### 5. natter/restart_service (仅管理员)
重启指定的Natter服务

**参数：**
```json
{
  "service_id": "service_id"  // 必需
}
```

## MCP消息示例

### 初始化连接
```json
{
  "jsonrpc": "2.0",
  "id": "init",
  "method": "initialize",
  "params": {
    "clientInfo": {
      "name": "my-mcp-client",
      "version": "1.0.0"
    },
    "protocolVersion": "2024-11-05"
  }
}
```

### 获取工具列表
```json
{
  "jsonrpc": "2.0",
  "id": "tools",
  "method": "tools/list"
}
```

### 调用工具
```json
{
  "jsonrpc": "2.0",
  "id": "call",
  "method": "tools/call",
  "params": {
    "name": "natter/list_services",
    "arguments": {
      "filter": "running"
    }
  }
}
```

### 订阅通知
```json
{
  "jsonrpc": "2.0",
  "id": "sub",
  "method": "notifications/subscribe",
  "params": {
    "type": "service_status"
  }
}
```

## 错误码说明

| 错误码 | 说明 |
|--------|------|
| -32700 | Parse error - JSON解析错误 |
| -32600 | Invalid Request - 无效请求 |
| -32601 | Method not found - 方法不存在 |
| -32602 | Invalid params - 参数无效 |
| -32603 | Internal error - 内部错误 |
| -32002 | Unauthorized - 认证失败 |
| -32003 | Forbidden - 权限不足 |

## 使用示例

### Python客户端示例

参考 `mcp_client_example.py` 文件，包含完整的连接、认证、工具调用示例。

### curl示例

```bash
# 认证请求
curl -X POST http://localhost:8080/api/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "authenticate": true,
    "auth": {"password": "zd2580"}
  }'

# 获取服务列表
curl -X POST http://localhost:8080/api/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "auth": {"password": "zd2580"},
    "message": {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "tools/call",
      "params": {
        "name": "natter/list_services",
        "arguments": {"filter": "all"}
      }
    }
  }'
```

## 权限说明

### 管理员权限
- 可以访问所有工具
- 可以启动、停止、重启服务
- 可以查看所有服务状态

### 访客权限
- 只能查看服务信息
- 不能执行管理操作
- 只能访问分配给其组的服务

## 故障排除

### 常见问题

1. **MCP服务未启用**
   ```
   Error: MCP service is disabled
   ```
   解决：设置环境变量 `MCP_ENABLED=true`

2. **认证失败**
   ```
   Error: Authentication required
   ```
   解决：检查密码是否正确，确保使用正确的认证方式

3. **连接数限制**
   ```
   Error: MCP connection limit exceeded
   ```
   解决：增加 `MCP_MAX_CONNECTIONS` 环境变量值

4. **工具不可用**
   ```
   Error: Unknown tool: tool_name
   ```
   解决：检查工具名称是否正确，确认用户权限

### 调试技巧

1. 查看服务器日志输出
2. 使用ping方法测试连接
3. 先获取工具列表确认可用功能
4. 检查错误响应中的详细信息

## 配置选项

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MCP_ENABLED | true | 是否启用MCP服务 |
| MCP_TIMEOUT | 30 | MCP请求超时时间(秒) |
| MCP_MAX_CONNECTIONS | 10 | 最大并发连接数 |
| MCP_WEBSOCKET_ENABLED | true | 是否启用WebSocket协议 |
| MCP_WEBSOCKET_PORT | 8081 | WebSocket服务器端口 |
| MCP_TCP_ENABLED | true | 是否启用TCP直连协议 |
| MCP_TCP_PORT | 8082 | TCP服务器端口 |
| MCP_STDIO_ENABLED | true | 是否启用stdio协议 |
| MCP_SSE_ENABLED | true | 是否启用SSE协议 |
| ADMIN_PASSWORD | zd2580 | 管理员密码 |

### 配置文件

MCP服务复用现有的Natter Web配置：
- `web/data/services.json` - 服务数据
- `web/data/service_groups.json` - 用户组配置
- `web/data/iyuu_config.json` - 推送配置

## 开发指南

### 添加新工具

1. 在 `MCPServiceTools` 类中添加新的工具处理方法
2. 使用 `MCPToolRegistry.register_tool()` 注册工具
3. 在 `initialize()` 方法中调用注册

示例：
```python
@staticmethod
def _handle_my_tool(arguments, user_role, connection_id):
    # 工具处理逻辑
    return {
        "content": [{"type": "text", "text": "结果"}]
    }

# 在initialize()中注册
MCPToolRegistry.register_tool(
    name="natter/my_tool",
    description="我的工具",
    input_schema={"type": "object", "properties": {...}},
    handler=MCPServiceTools._handle_my_tool,
    required_role="admin"
)
```

### 扩展通知类型

在 `MCPNotificationManager` 中添加新的通知类型和处理逻辑。

## 更多资源

- [MCP协议规范](https://spec.modelcontextprotocol.io/)
- [Natter项目](https://github.com/MikeWang000000/Natter)
- [项目文档](../CLAUDE.md)