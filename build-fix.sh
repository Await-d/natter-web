#!/bin/bash
###
 # @Author: Await
 # @Date: 2025-05-29 10:40:48
 # @LastEditors: Await
 # @LastEditTime: 2025-05-29 10:47:53
 # @Description: 请填写简介
### 
# Natter Web Docker构建修复脚本
# 解决Python镜像digest不匹配问题

echo "🔧 Natter Web Docker构建修复工具"
echo "=================================="

# 设置错误时退出
set -e

echo "📋 第1步：清理Docker环境"
echo "清理所有无用的Docker资源..."
docker system prune -af --volumes || true
docker builder prune -af || true

echo "📋 第2步：强制拉取最新基础镜像"
echo "拉取Python 3.11-slim-bullseye镜像..."
docker pull python:3.11-slim-bullseye

echo "📋 第3步：构建Natter Web镜像"
echo "使用BuildKit构建，避免缓存问题..."
cd "$(dirname "$0")"

# 设置BuildKit环境变量
export DOCKER_BUILDKIT=1

# 构建镜像
docker build \
    --no-cache \
    --pull \
    --progress=plain \
    --platform=linux/amd64 \
    -t natter-web:latest \
    ./web

echo "📋 第4步：清理旧容器"
echo "停止并删除旧的容器..."
docker stop natter-web-container 2>/dev/null || true
docker rm natter-web-container 2>/dev/null || true

echo "📋 第5步：启动新容器"
echo "启动Natter Web容器..."
docker run -d \
    --name natter-web-container \
    --network host \
    -v /volume1/docker/1panel/apps/www/natter-web/data:/app/data \
    -v /volume1/docker/1panel/apps/www/natter-web/logs:/app/logs \
    --cap-add NET_ADMIN \
    --restart always \
    -e TZ=Asia/Shanghai \
    -e PYTHONUNBUFFERED=1 \
    -e NATTER_PATH=/app/natter/natter.py \
    -e DATA_DIR=/app/data \
    -e LOGS_DIR=/app/logs \
    -e WEB_PORT=7111 \
    -e WEB_PASSWORD=zd2580 \
    natter-web:latest

echo "✅ 构建和部署完成！"
echo "🌐 访问地址: http://localhost:7111"
echo "🔑 访问密码: zd2580"

# 显示容器状态
echo ""
echo "📊 容器状态:"
docker ps | grep natter-web-container || echo "❌ 容器未运行"

echo ""
echo "📝 查看日志: docker logs -f natter-web-container" 