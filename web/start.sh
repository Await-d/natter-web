#!/bin/bash
###
 # @Author: Await
 # @Date: 2025-04-12 15:27:12
 # @LastEditors: Await
 # @LastEditTime: 2025-04-13 15:54:15
 # @Description: 请填写简介
### 

# 确保目录结构正确
mkdir -p /app/data

echo "开始启动Natter Web管理工具..."
echo "如果需要持久化数据，请确保挂载了/app/data目录"

# 确保使用iptables-legacy
echo "配置iptables-legacy为默认..."
if command -v update-alternatives &> /dev/null; then
  update-alternatives --set iptables /usr/sbin/iptables-legacy
  update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
  echo "iptables-legacy配置完成"
else
  echo "警告：无法设置iptables-legacy，某些转发方法可能无法正常工作"
fi

# 确保nftables正常工作
echo "检查nftables..."
if command -v nft &> /dev/null; then
  # 尝试一个简单的nftables命令，检查是否能正常工作
  if ! nft list tables &> /dev/null; then
    echo "尝试修复nftables..."
    apt-get update && apt-get install -y nftables
    systemctl restart nftables || true
  fi
  echo "nftables检查完成"
else
  echo "未找到nftables命令，尝试安装..."
  apt-get update && apt-get install -y nftables
fi

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

# 获取Web端口号
# 如果传入了命令行参数，则使用命令行参数作为端口号
# 否则使用环境变量WEB_PORT，如果未设置则默认使用8080
WEB_PORT=${WEB_PORT:-8080}
if [ $# -gt 0 ]; then
  WEB_PORT=$1
fi

echo "Web服务将使用端口: $WEB_PORT"
python3 -u server.py $WEB_PORT 