<!--
 * @Author: Await
 * @Date: 2025-04-12 15:31:13
 * @LastEditors: Await
 * @LastEditTime: 2025-04-12 15:31:21
 * @Description: 请填写简介
-->
# 将Natter Web管理工具与已有Natter集成

本文档介绍如何将Natter Web管理工具集成到已有的Natter项目中。

## 方法一：复制文件（简单方式）

最简单的方法是将Web管理工具的文件复制到Natter项目目录中：

1. 在Natter项目根目录创建web文件夹：

```bash
mkdir -p /path/to/your/natter/web
```

2. 复制Web管理工具的所有文件到该目录：

```bash
cp -r /path/to/natter-web-manager/* /path/to/your/natter/web/
```

3. 进入web目录启动服务：

```bash
cd /path/to/your/natter/web
python server.py
```

## 方法二：环境变量指定Natter路径

如果您不想将Web管理工具放在Natter项目目录中，可以通过环境变量指定Natter路径：

1. 设置环境变量指向您的natter.py文件：

```bash
# Linux/macOS
export NATTER_PATH=/path/to/your/natter/natter.py

# Windows (CMD)
set NATTER_PATH=C:\path\to\your\natter\natter.py

# Windows (PowerShell)
$env:NATTER_PATH="C:\path\to\your\natter\natter.py"
```

2. 启动Web管理服务：

```bash
python server.py
```

## 方法三：Docker挂载方式（推荐）

如果您使用Docker，可以将现有的Natter目录挂载到容器中：

1. 修改docker-compose.yml文件：

```yaml
volumes:
  - ./data:/app/data
  - /absolute/path/to/your/natter:/app/natter  # 添加这一行
```

2. 启动容器：

```bash
docker-compose up -d
```

这样，容器会使用您本地的Natter安装，而不是从GitHub克隆最新版本。

## 验证集成

无论使用哪种方法，启动成功后，请确认：

1. Web界面可以正常访问
2. 创建新服务时能够找到并运行natter.py
3. Natter服务能够正常启动和运行

## 可能出现的问题

### 找不到natter.py

确保NATTER_PATH环境变量或集成路径指向了有效的natter.py文件。服务启动时会输出它尝试使用的Natter路径，请检查该路径是否正确。

### 权限问题

确保Web服务有足够的权限运行Natter。特别是在使用iptables等需要root权限的功能时，可能需要使用sudo运行Web服务。

### 目录结构问题

如果您的Natter项目结构与标准不同，可能需要调整路径。您可以直接编辑server.py文件中的NATTER_PATH变量来固定指向正确的位置。
