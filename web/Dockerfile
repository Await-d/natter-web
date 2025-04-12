FROM python:3.9-slim

WORKDIR /app

# 安装依赖
RUN apt-get update && apt-get install -y \
    git \
    procps \
    iptables \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
RUN pip install --no-cache-dir psutil

# 克隆最新版Natter
RUN git clone https://github.com/MikeWang000000/Natter.git /app/natter-repo

# 创建目录结构
RUN mkdir -p /app/natter
RUN mkdir -p /app/web
RUN mkdir -p /app/data

# 复制Natter文件
RUN cp -r /app/natter-repo/* /app/natter/

# 复制Web管理工具文件
COPY . /app/web/

# 创建数据目录
VOLUME ["/app/data"]

# 暴露端口
EXPOSE 8080

# 添加启动脚本
COPY start.sh /app/
RUN chmod +x /app/start.sh

# 设置启动命令
CMD ["/app/start.sh"] 