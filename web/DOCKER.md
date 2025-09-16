# Natter Web管理工具 - Docker部署指南

本文档介绍如何使用Docker来部署和运行Natter Web管理工具。我们提供官方Docker镜像，支持多架构（amd64/arm64），可快速部署到各种环境。

## 系统要求

- Docker 19.03或更高版本
- Docker Compose 1.27.0或更高版本
- 互联网连接（用于拉取镜像和Natter最新代码）
- 支持host网络模式的系统（Linux效果最佳）

## 🚀 快速开始

### 方法一：使用官方镜像（推荐）

**快速启动：**

```bash
# 使用官方镜像快速部署
docker run -d --name natter-web \
  --network host \
  --cap-add NET_ADMIN \
  -v "$(pwd)/data:/app/data" \
  await2719/natter-web:latest

# 访问Web界面
echo "🌐 访问地址: http://localhost:8080"
echo "🔐 默认密码: zd2580"
```

**使用Docker Compose：**

创建 `docker-compose.yml` 文件：

```yaml
version: '3'
services:
  natter-web:
    image: await2719/natter-web:latest
    container_name: natter-web
    network_mode: host
    cap_add:
      - NET_ADMIN
    environment:
      - WEB_PORT=8080
      - ADMIN_PASSWORD=zd2580
      - GUEST_ENABLED=true
      - IYUU_ENABLED=true
    volumes:
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/version"]
      interval: 30s
      timeout: 10s
      retries: 3
```

然后运行：

```bash
docker-compose up -d
```

### 方法二：从源码构建

如果您需要修改代码或使用特定版本：

1. 构建Docker镜像：

```bash
docker build -t natter-web .
```

2. 运行容器：

```bash
docker run -d --name natter-web \
  --network host \
  --cap-add NET_ADMIN \
  -v "$(pwd)/data:/app/data" \
  natter-web
```

### 可用的镜像标签

```bash
# 最新稳定版
await2719/natter-web:latest

# 特定版本
await2719/natter-web:v1.0.8
await2719/natter-web:1.0.8

# 开发版本
await2719/natter-web:dev
```

## 持久化数据

**重要提示：一定要正确映射数据目录，否则每次重启容器数据将丢失**

Docker镜像会将数据（如服务配置和模板）存储在`/app/data`目录中。为了保持数据持久化，您必须将此目录挂载到主机上的目录。

### 使用docker-compose（推荐）

在docker-compose.yml文件中已配置数据映射：
```yaml
volumes:
  - ./data:/app/data  # 数据持久化：将容器内的/app/data目录映射到宿主机的./data目录
```

这会将数据存储在当前目录下的`data`文件夹中。确保该目录在宿主机上具有适当的权限。

### 使用docker run命令

如果直接使用docker run，确保添加卷映射参数：
```bash
docker run -d --name natter-web \
  --network host \
  --cap-add NET_ADMIN \
  -v "$(pwd)/data:/app/data" \
  -p 8080:8080 \
  natter-web
```

### 验证数据持久化

1. 首次启动容器后，会在数据目录中创建一个`.data_test`文件
2. 重启容器后，如果该文件仍然存在，说明数据目录映射正确
3. 如果服务配置和模板在重启后丢失，检查：
   - 数据目录映射是否正确
   - 宿主机目录权限是否正确
   - 启动命令中是否包含了卷映射参数

## 网络配置说明

### 网络模式

容器使用`host`网络模式，这对于Natter工具非常重要，因为它需要直接访问主机网络接口才能正确检测和使用NAT穿透功能。

### 权限

容器需要`NET_ADMIN`权限才能使用iptables等网络管理工具。这是Natter的某些转发功能（如iptables、nftables）所必需的。

## 访问控制

默认情况下，Web界面可以通过`http://localhost:8080`访问。如果您需要从外部网络访问，请确保在防火墙中开放8080端口，并注意添加适当的访问控制措施，因为Natter工具可能会控制您的网络设置。

## 常见问题

### 容器无法启动

- 检查是否有其他程序占用了8080端口
- 确保Docker服务正常运行
- 查看Docker日志：`docker logs natter-web`

### 无法使用iptables等转发方法

- 确保使用了`--cap-add NET_ADMIN`参数启动容器
- 如果使用Windows或macOS，host网络模式和网络管理工具可能不完全支持

### 容器中的Natter无法检测到网络接口

- 确保使用`--network host`参数启动容器
- 在非Linux系统上，host网络模式有限制，某些功能可能无法正常工作

## 自定义和高级配置

### 使用特定版本的Natter

如果需要使用特定版本的Natter而不是最新版，可以修改Dockerfile：

```dockerfile
# 将克隆命令修改为特定版本或分支
RUN git clone -b v2.1.1 https://github.com/MikeWang000000/Natter.git /app/natter-repo
```

### 自定义端口

有三种方式可以自定义Web管理界面的端口：

1. 使用环境变量（推荐）：

```yaml
# 在docker-compose.yml中
environment:
  - WEB_PORT=9090  # 将8080修改为任意端口
```

或者在命令行中：

```bash
WEB_PORT=9090 docker-compose up -d
```

2. 在docker run命令中指定环境变量：

```bash
docker run -d --name natter-web \
  --network host \
  --cap-add NET_ADMIN \
  -e WEB_PORT=9090 \
  -v $(pwd)/data:/app/data \
  natter-web
```

3. 通过命令行参数直接传递给容器：

```bash
docker run -d --name natter-web \
  --network host \
  --cap-add NET_ADMIN \
  -v $(pwd)/data:/app/data \
  natter-web 9090
```

4. 对于使用端口映射（非host网络模式）的配置，需要同时修改端口映射：

```yaml
# 在docker-compose.yml中
ports:
  - "9090:9090"  # 修改为相同的自定义端口
environment:
  - WEB_PORT=9090
```

### 使用已有的Natter安装

如果您想使用已有的Natter安装而不是在容器中克隆最新版，可以将Natter目录挂载到容器中：

```yaml
volumes:
  - ./data:/app/data
  - /path/to/your/natter:/app/natter
```

## 安全注意事项

- 容器需要较高的系统权限才能正常工作，请确保在可信环境中使用
- 使用防火墙限制对Web管理界面的访问
- 定期更新Docker镜像以获取最新的安全补丁
