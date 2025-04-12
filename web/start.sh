#!/bin/bash

# 确保目录结构正确
mkdir -p /app/data

echo "开始启动Natter Web管理工具..."
echo "如果需要持久化数据，请确保挂载了/app/data目录"

# 设置环境变量，确保Web管理工具能找到natter.py
export NATTER_PATH=/app/natter/natter.py

# 启动Web管理服务
cd /app/web
python server.py 8080 