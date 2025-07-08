# Natter Web管理工具 - Docker部署指南

## 🚀 统一登录功能

本版本引入了全新的统一登录功能，支持管理员和访客两种用户类型，通过一个登录页面实现智能的用户类型识别和跳转。

## 🔧 快速部署

### 使用 Docker Compose（推荐）

1. **克隆项目**
   ```bash
   git clone https://github.com/Await-d/natter-web.git
   cd natter-web/web
   ```

2. **配置环境变量**
   
   编辑 `docker-compose.yml` 文件中的环境变量：
   
   ```yaml
   environment:
     - ADMIN_PASSWORD=your_strong_password    # 管理员密码，必须设置强密码
     - WEB_PORT=8080                         # Web服务端口
     - GUEST_ENABLED=true                    # 是否启用访客功能
     - IYUU_ENABLED=true                     # 是否启用IYUU推送
   ```

3. **启动服务**
   ```bash
   docker-compose up -d
   ```

4. **访问管理界面**
   
   打开浏览器访问：`http://localhost:8080`

### 手动Docker部署

```bash
# 构建镜像
docker build -t natter-web .

# 运行容器
docker run -d \
  --name natter-web \
  --network host \
  -v ./data:/app/data \
  -e ADMIN_PASSWORD=your_strong_password \
  -e WEB_PORT=8080 \
  -e GUEST_ENABLED=true \
  -e IYUU_ENABLED=true \
  --cap-add NET_ADMIN \
  natter-web
```

## 🔐 登录系统

### 统一登录页面

- **访问地址**: `http://localhost:8080/login.html`
- **智能识别**: 系统会根据输入的密码自动判断用户类型
- **自动跳转**: 管理员跳转到完整管理界面，访客跳转到只读服务列表

### 管理员登录

- **密码**: 使用环境变量 `ADMIN_PASSWORD` 设置的密码
- **权限**: 完整的系统管理权限
  - 创建、启动、停止、删除服务
  - 配置模板管理
  - IYUU推送配置
  - 访客组管理

### 访客登录

- **密码**: 在管理界面中创建服务组时设置的密码
- **权限**: 只读权限
  - 查看指定服务组的服务列表
  - 查看服务状态和映射地址
  - 复制访问地址

## 👥 访客组管理

管理员可以创建多个访客组，每个组有独立的密码和服务列表：

1. **创建访客组**
   - 在管理界面点击"服务组管理"
   - 填写组名、密码和描述
   - 保存后即可使用

2. **添加服务到组**
   - 在服务列表中选择要分享的服务
   - 将服务添加到指定的访客组
   - 访客使用组密码登录后可以看到这些服务

## 📱 IYUU推送配置

支持服务状态变更的实时推送通知：

- **令牌配置**: 在管理界面的IYUU设置中添加推送令牌
- **定时推送**: 支持设置每日定时发送服务状态摘要
- **实时通知**: 服务启动、停止、地址变更等事件自动推送

## 🔧 环境变量说明

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `ADMIN_PASSWORD` | `""` | 管理员密码，**强烈建议设置** |
| `WEB_PORT` | `8080` | Web服务端口 |
| `GUEST_ENABLED` | `true` | 是否启用访客功能 |
| `IYUU_ENABLED` | `true` | 是否启用IYUU推送 |
| `NATTER_PATH` | `/app/natter/natter.py` | Natter程序路径 |
| `DATA_DIR` | `/app/data` | 数据存储目录 |

## 🚨 安全建议

1. **设置强密码**: 必须为 `ADMIN_PASSWORD` 设置强密码
2. **访问控制**: 建议使用反向代理（如Nginx）添加额外的访问控制
3. **HTTPS**: 生产环境建议启用HTTPS
4. **防火墙**: 确保只开放必要的端口

## 📂 数据持久化

容器中的 `/app/data` 目录包含：
- 服务配置文件
- 访客组配置
- IYUU推送配置
- 模板配置

建议将此目录映射到宿主机以实现数据持久化：

```yaml
volumes:
  - ./data:/app/data
```

## 🔄 升级说明

### 从旧版本升级

如果您之前使用的是 `WEB_PASSWORD` 环境变量：

1. 将 `WEB_PASSWORD` 改为 `ADMIN_PASSWORD`
2. 重新启动容器
3. 使用新的统一登录页面访问系统

### 配置迁移

旧版本的配置文件会自动兼容，无需手动迁移。

## 🐛 故障排除

### 常见问题

1. **无法访问管理界面**
   - 检查端口是否正确映射
   - 确认防火墙设置
   - 查看容器日志：`docker logs natter-web`

2. **密码登录失败**
   - 确认 `ADMIN_PASSWORD` 环境变量已正确设置
   - 检查密码是否包含特殊字符需要转义

3. **访客功能不可用**
   - 确认 `GUEST_ENABLED=true`
   - 检查是否已创建访客组
   - 验证访客组密码设置

### 日志查看

```bash
# 查看容器日志
docker logs natter-web

# 实时查看日志
docker logs -f natter-web
```

## 📞 技术支持

- **GitHub**: https://github.com/Await-d/natter-web
- **Gitee**: https://gitee.com/await29/natter-web
- **文档**: 查看项目README获取更多信息

## 📄 许可证

本项目基于开源许可证发布，详情请查看 LICENSE 文件。 