#!/bin/bash
###
 # @Author: Await
 # @Date: 2025-04-12 15:27:12
 # @LastEditors: Await
 # @LastEditTime: 2025-04-12 16:41:48
 # @Description: 请填写简介
### 

# 确保目录结构正确
mkdir -p /app/data

echo "开始启动Natter Web管理工具..."
echo "如果需要持久化数据，请确保挂载了/app/data目录"

# 设置环境变量，确保Web管理工具能找到natter.py
export NATTER_PATH=/app/natter/natter.py
export DATA_DIR=/app/data

# 调试信息
echo "NATTER_PATH设置为: $NATTER_PATH"
echo "DATA_DIR设置为: $DATA_DIR"
echo "当前目录: $(pwd)"
echo "文件权限:"
ls -la /app/web/server.py

# 修复文件权限问题
echo "修复文件权限..."
chmod +x /app/web/server.py
chmod -R 755 /app/web

# 启动Web管理服务
echo "切换到web目录并启动服务..."
cd /app/web
python3 -u server.py 8080 