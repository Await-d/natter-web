# GitHub Actions 工作流说明

本项目包含两个主要的 GitHub Actions 工作流：

## 🚀 自动发布流水线 (auto-release-pipeline.yml)

### 触发条件
- 推送到 `master` 分支
- 跳过文档和配置文件的更改

### 主要功能
1. **自动版本管理** - 基于 `VERSION` 文件和 Git 标签智能计算下一个版本
2. **变更检测** - 只在有实质性代码更改时触发版本发布
3. **自动更新** - 同步更新 `VERSION` 文件和 `web/server.py` 中的版本号
4. **生成更新日志** - 使用 git-cliff 自动生成结构化的更新日志
5. **Docker 构建** - 构建多架构 (amd64/arm64) Docker 镜像并推送到 Docker Hub
6. **GitHub 发布** - 自动创建 GitHub Release 并附上更新日志
7. **版本清理** - 自动清理旧版本，保持最近 50 个标签
8. **通知发送** - 可选的 Telegram 通知

### 所需的 Secrets
在 GitHub 仓库设置中添加以下 Secrets：

```
DOCKERHUB_USERNAME=await2719  # Docker Hub 用户名
DOCKERHUB_TOKEN=xxxxx         # Docker Hub 访问令牌
```

可选的 Telegram 通知：
```
TELEGRAM_BOT_TOKEN=xxxxx      # Telegram Bot Token
TELEGRAM_CHAT_ID=xxxxx        # Telegram Chat ID
```

### Docker 镜像
发布后的 Docker 镜像地址：
```bash
docker pull await2719/natter-web:latest
docker pull await2719/natter-web:v1.0.8
```

## 🔍 PR 代码质量检查 (pr-lint-check.yml)

### 触发条件
- 创建、更新或重新打开 Pull Request
- 包含 Python、配置文件或文档的更改

### 检查内容
1. **Black 格式化** - 检查 Python 代码格式是否符合 Black 标准
2. **isort 导入排序** - 检查 Python 导入语句排序
3. **Flake8 代码质量** - 检查代码质量和风格问题

### 修复建议
本地安装工具并修复问题：
```bash
# 安装代码质量工具
pip install black isort flake8

# 自动修复格式问题
black .          # 修复代码格式
isort .          # 修复import排序
flake8 .         # 检查代码质量
```

## 📋 文件结构

```
.github/
├── workflows/
│   ├── auto-release-pipeline.yml  # 自动发布流水线
│   └── pr-lint-check.yml         # PR代码质量检查
├── cliff.toml                     # git-cliff配置文件
└── README.md                      # 本说明文件
```

## 🔧 版本管理

项目使用语义化版本控制：
- `MAJOR.MINOR.PATCH` (例如：1.0.8)
- `VERSION` 文件存储当前版本
- `web/server.py` 中的 `VERSION` 变量自动同步

## 📝 提交消息规范

建议使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
feat: 添加新功能
fix: 修复bug
docs: 更新文档
style: 代码格式化
refactor: 代码重构
test: 添加测试
chore: 维护性更改
```

这样可以让 git-cliff 自动生成更好的更新日志。