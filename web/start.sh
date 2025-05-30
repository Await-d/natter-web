#!/bin/bash
###
 # @Author: Await
 # @Date: 2025-04-12 15:27:12
 # @LastEditors: Await
 # @LastEditTime: 2025-04-14 09:46:10
 # @Description: Natter Web管理工具启动脚本 - 支持统一登录
### 

# 确保目录结构正确
mkdir -p /app/data
chmod -R 777 /app/data

echo "开始启动Natter Web管理工具..."
echo "数据目录: ${DATA_DIR:-/app/data}"
echo "确保此目录已正确映射到宿主机以实现数据持久化"

# 检查数据目录映射是否正确
if [ -f "${DATA_DIR:-/app/data}/.data_test" ]; then
  echo "✅ 数据目录映射正常，数据将被持久化"
else
  touch "${DATA_DIR:-/app/data}/.data_test"
  echo "⚠️ 首次运行：创建了数据目录测试文件，重启后检查此文件是否存在以确认持久化正常"
fi

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

# 尝试不同的方法确保nftables工作
if command -v nft &> /dev/null; then
  echo "nftables已安装，尝试初始化..."
  
  # 尝试加载内核模块 - 在某些容器环境中可能会失败
  modprobe nf_tables &>/dev/null || echo "无法加载nf_tables模块 (在容器中这是正常的)"
  
  # 手动创建nftables配置目录
  mkdir -p /etc/nftables
  touch /etc/nftables/nftables.conf
  
  # 尝试不同的方法启动nftables
  systemctl start nftables &>/dev/null || \
  service nftables start &>/dev/null || \
  nft -f /etc/nftables/nftables.conf &>/dev/null || \
  echo "无法启动nftables服务 (在容器中这是正常的)"
  
  # 测试nftables是否可用
  echo "测试nftables功能..."
  if nft list tables &>/dev/null; then
    echo "✅ nftables功能正常"
  else
    echo "⚠️ nftables不可用。这可能是由于容器限制，请尝试使用其他转发方法。"
    echo "   推荐使用 socket 或 iptables 方法替代。"
  fi
else
  echo "未找到nftables命令，尝试安装..."
  apt-get update && apt-get install -y nftables libpcap-dev
  
  # 安装后再次测试
  if command -v nft &> /dev/null; then
    echo "nftables已安装，尝试测试功能..."
    if nft list tables &>/dev/null; then
      echo "✅ nftables功能已成功安装"
    else
      echo "⚠️ nftables安装成功但不可用。请使用其他转发方法。"
      echo "   推荐使用 socket 或 iptables 方法替代。"
    fi
  else
    echo "⚠️ nftables安装失败，请使用其他转发方法。"
  fi
fi

# 尝试安装socat
if ! command -v socat &> /dev/null; then
  echo "尝试安装socat工具..."
  apt-get update && apt-get install -y socat && echo "✅ socat安装成功" || echo "⚠️ socat安装失败"
fi

# 尝试安装gost
if ! command -v gost &> /dev/null; then
  echo "尝试安装gost工具..."
  wget -qO- https://github.com/ginuerzh/gost/releases/download/v2.11.2/gost-linux-amd64-2.11.2.gz 2>/dev/null | gunzip > /usr/local/bin/gost 2>/dev/null && \
  chmod +x /usr/local/bin/gost && echo "✅ gost安装成功" || echo "⚠️ gost安装失败"
fi

# 设置应用路径变量
APP_DIR=$(dirname "$0")
APP_PARENT_DIR=$(dirname "$APP_DIR")

# 获取环境变量或使用默认值
NATTER_PATH=${NATTER_PATH:-"$APP_PARENT_DIR/natter/natter.py"}
DATA_DIR=${DATA_DIR:-"$APP_DIR/data"}
WEB_PORT=${WEB_PORT:-8080}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-""}
GUEST_ENABLED=${GUEST_ENABLED:-"true"}
IYUU_ENABLED=${IYUU_ENABLED:-"true"}

# 调试信息
echo "NATTER_PATH设置为: $NATTER_PATH"
echo "DATA_DIR设置为: $DATA_DIR"
echo "当前目录: $(pwd)"
echo "文件权限:"
ls -la /app/web/server.py
ls -la ${DATA_DIR}

# 修复文件权限问题
echo "修复文件权限..."
chmod +x /app/web/server.py
chmod -R 755 /app/web
chmod -R 777 ${DATA_DIR}

# 检查并安装Python依赖
echo "检查Python依赖..."
if ! python3 -c "import requests" 2>/dev/null; then
  echo "安装requests模块..."
  pip install requests --no-cache-dir || apt-get update && apt-get install -y python3-requests
  echo "requests模块安装完成"
else
  echo "✅ requests模块已安装"
fi

# 显示启动配置信息
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Natter Web管理界面配置信息"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 使用的Natter路径: $NATTER_PATH"
echo "💾 数据存储目录: $DATA_DIR"
echo "🌐 Web服务端口: $WEB_PORT"
echo "🔐 管理员密码: ${ADMIN_PASSWORD:+已设置} ${ADMIN_PASSWORD:-未设置（开放访问）}"
echo "👥 访客功能: ${GUEST_ENABLED}"
echo "📢 IYUU推送: ${IYUU_ENABLED}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 启动Web管理服务
echo "切换到web目录并启动服务..."
cd /app/web

echo "🚀 启动Natter Web管理界面"
echo "📍 访问地址: http://localhost:$WEB_PORT"

if [ -n "$ADMIN_PASSWORD" ]; then
    echo "🔐 统一登录已启用 - 管理员和访客将使用统一的登录页面"
    echo "   - 管理员密码: 使用环境变量ADMIN_PASSWORD设置的密码"
    echo "   - 访客密码: 在管理界面中创建服务组时设置"
    # 设置全局变量供server.py使用
    export ADMIN_PASSWORD="$ADMIN_PASSWORD"
    python3 -u "$APP_DIR/server.py" "$WEB_PORT"
else
    echo "⚠️  未设置管理员密码，系统将开放访问（不推荐用于生产环境）"
    echo "   建议设置环境变量 ADMIN_PASSWORD 来启用密码保护"
    python3 -u "$APP_DIR/server.py" "$WEB_PORT" 
fi 