# 项目结构

## 目录组织

```
natteer-web/
├── natter/                      # 核心网络隧道工具
│   ├── natter.py               # 主要隧道实现
│   ├── docs/                   # Natter文档
│   ├── natter-check/           # 健康检查工具
│   └── natter-docker/          # Docker集成示例
│       ├── nginx/              # Nginx集成
│       ├── nginx-cloudflare/   # Nginx + Cloudflare集成
│       ├── transmission/       # BT下载集成
│       ├── qbittorrent/       # qBittorrent集成
│       ├── minecraft/         # 我的世界服务器集成
│       └── v2fly-nginx-cloudflare/ # V2Ray集成
├── web/                        # Web管理界面 (主要开发区域)
│   ├── server.py              # 后端HTTP服务器 (单一入口)
│   ├── index.html             # 管理员界面
│   ├── guest.html             # 访客界面
│   ├── login.html             # 统一登录页面
│   ├── script.js              # 前端交互逻辑
│   ├── style.css              # 界面样式 (未使用)
│   ├── data/                  # JSON数据存储
│   │   ├── services.json      # 服务实例配置
│   │   ├── service_groups.json # 用户组权限
│   │   ├── iyuu_config.json   # 推送通知配置
│   │   └── templates.json     # 配置模板
│   ├── Dockerfile             # 容器构建定义
│   ├── docker-compose.yml     # 容器编排配置
│   └── start.sh               # 容器启动脚本
├── .spec-workflow/            # 规范工作流 (项目指导文档)
│   ├── steering/              # 项目导向文档
│   │   ├── product.md         # 产品愿景
│   │   ├── tech.md            # 技术架构
│   │   └── structure.md       # 代码结构 (本文档)
│   └── templates/             # 规范模板
└── 配置文件
    ├── CLAUDE.md              # Claude Code 使用指南
    ├── push_all.sh            # 多仓库推送脚本
    └── README.md              # 项目说明
```

## 命名约定

### 文件命名
- **Python模块**: `snake_case.py` (如 `server.py`, `natter.py`)
- **HTML页面**: `kebab-case.html` (如 `login.html`, `guest.html`)
- **配置文件**: `snake_case.json` (如 `service_groups.json`)
- **脚本文件**: `snake_case.sh` (如 `start.sh`, `push_all.sh`)
- **文档文件**: `UPPER_CASE.md` (如 `README.md`, `CLAUDE.md`)

### 代码命名
- **类名**: `PascalCase` (如 `NatterService`, `ServiceGroupManager`)
- **函数/方法**: `snake_case` (如 `start_service`, `get_status`)
- **常量**: `UPPER_SNAKE_CASE` (如 `DATA_DIR`, `NATTER_PATH`, `VERSION`)
- **变量**: `snake_case` (如 `running_services`, `service_lock`)

## 导入模式

### 导入顺序
1. **标准库模块** (如 `import os`, `import json`, `import threading`)
2. **第三方依赖** (如 `import psutil`, `import requests`)
3. **项目内部模块** (目前为单文件架构，较少使用)

### 模块组织
- **绝对导入**: 优先使用标准库模块
- **最小依赖**: 仅使用必要的外部依赖 (`psutil`, `requests`)
- **单文件架构**: 核心功能集中在 `web/server.py` 中，减少模块间复杂性

## 代码结构模式

### 模块组织 (server.py)
```python
1. 导入语句和依赖项
2. 版本号和全局常量定义
3. 路径配置和环境变量
4. 全局变量和锁对象
5. 数据结构和配置加载函数
6. 核心类定义 (NatterService, ServiceGroupManager)
7. HTTP请求处理器类
8. 工具函数和辅助方法
9. 主程序入口点
```

### 类组织原则
```python
class NatterService:
    1. 初始化方法 (__init__)
    2. 核心功能方法 (start, stop, restart)
    3. 状态查询方法 (get_status, is_running)
    4. 内部辅助方法 (_parse_*, _handle_*)
    5. 清理和销毁方法
```

### 函数组织
- **输入验证**: 方法开始时验证参数
- **核心逻辑**: 主要处理流程
- **错误处理**: 异常捕获和错误响应
- **返回清理**: 明确的返回点和资源清理

## 代码组织原则

1. **单一职责**: 每个类和函数都有明确的单一职责
2. **模块化**: 通过类和函数实现功能模块化，便于测试和维护
3. **可测试性**: 方法设计便于单元测试 (尽管目前缺少测试)
4. **一致性**: 整个项目遵循统一的编码风格和模式

## 模块边界

### 核心模块边界
- **Natter核心 vs Web管理**: Natter工具作为独立子进程，Web界面通过命令行接口交互
- **前端 vs 后端**: 严格的API边界，前端通过HTTP API与后端通信
- **数据存储 vs 业务逻辑**: JSON文件作为数据层，业务逻辑在内存中处理
- **用户界面分离**: 管理员界面、访客界面、登录界面各自独立

### 依赖方向
```
前端界面 → HTTP API → 业务逻辑 → 进程管理 → Natter工具
    ↓         ↓          ↓
JSON存储 ← 数据持久化 ← 配置管理
```

### 平台特定边界
- **Docker vs 本地**: 通过环境变量和路径配置分离部署环境
- **网络工具依赖**: nftables/iptables/socket等网络工具的抽象化

## 代码规模指南

建议的规模限制：
- **文件大小**: 单个Python文件 < 3000行 (当前server.py约2600+行，接近上限)
- **函数大小**: 单个函数/方法 < 100行，复杂方法可适当放宽
- **类复杂度**: 单个类 < 50个方法，当前NatterService约30个方法
- **嵌套深度**: 最大嵌套级别 ≤ 4层，特殊情况可适当放宽

## Web界面结构

### 前端组织
```
web/
├── index.html          # 管理员界面 (完整功能)
├── guest.html          # 访客界面 (只读权限)
├── login.html          # 统一认证入口
├── script.js           # 共享JavaScript逻辑
└── style.css           # 样式文件 (当前未使用)
```

### 关注点分离
- **界面逻辑分离**: 不同用户角色使用独立的HTML文件
- **API统一**: 所有界面通过相同的RESTful API与后端通信
- **无框架依赖**: 使用原生HTML/CSS/JavaScript，避免外部依赖
- **响应式设计**: CSS样式直接嵌入HTML中，支持移动端访问

## 数据组织

### JSON数据结构
```
web/data/
├── services.json       # 服务实例数据
│   └── {service_id: {config, status, metadata}}
├── service_groups.json # 用户组和权限
│   └── {groups: {group_id: {name, password, services}}}
├── iyuu_config.json   # 通知推送配置
│   └── {tokens: [], enabled: bool, schedule: {}}
└── templates.json     # 配置模板
    └── {template_id: {name, args, description}}
```

### 数据访问模式
- **读取**: 应用启动时加载到内存，运行时从内存读取
- **写入**: 状态变更时同步写入JSON文件
- **并发控制**: 使用threading.RLock()保护共享数据结构
- **数据验证**: JSON schema验证和类型检查

## 文档标准

- **公开API**: 所有HTTP端点都有对应的内联注释说明
- **复杂逻辑**: 关键算法和业务逻辑包含详细注释
- **模块README**: 主要功能模块包含README.md文件
- **遵循约定**: 使用Python docstring约定和中文注释

## 未来结构演进

### 扩展性考虑
- **模块分离**: 当server.py超过3000行时，考虑按功能拆分为多个模块
- **插件系统**: 为不同网络工具和集成建立插件架构
- **API版本化**: 当功能复杂时引入API版本控制
- **测试框架**: 添加单元测试和集成测试结构

### 性能优化结构
- **缓存层**: 引入Redis或内存缓存减少文件I/O
- **异步处理**: 考虑引入asyncio提升并发处理能力
- **数据库迁移**: 大规模部署时迁移到关系型数据库
- **微服务分离**: 根据负载情况考虑服务拆分