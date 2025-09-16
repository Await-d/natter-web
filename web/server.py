#!/usr/bin/env python3

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import requests  # 添加requests模块用于HTTP请求
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import deque  # 添加队列用于消息批量发送
import hashlib  # 用于WebSocket握手
import struct  # 用于WebSocket帧处理
import select  # 用于stdio协议
import socketserver  # 用于TCP服务器

import psutil
import secrets

# 版本号定义
VERSION = "1.0.10"

# 确保能够访问到natter.py，优先使用环境变量定义的路径
NATTER_PATH = os.environ.get("NATTER_PATH") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "natter", "natter.py"
)

# 数据存储目录，优先使用环境变量定义的路径
DATA_DIR = os.environ.get("DATA_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data"
)
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
SERVICES_DB_FILE = os.path.join(DATA_DIR, "services.json")
IYUU_CONFIG_FILE = os.path.join(DATA_DIR, "iyuu_config.json")  # IYUU配置文件
SERVICE_GROUPS_FILE = os.path.join(DATA_DIR, "service_groups.json")  # 服务组配置文件

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 存储运行中的Natter服务进程
running_services = {}
service_lock = threading.RLock()

# 服务组配置
service_groups = {
    "groups": {},  # 组ID -> {name, password, services}
    "default_group": None,  # 默认组ID
}

# IYUU配置
iyuu_config = {
    "tokens": [],  # IYUU令牌列表
    "enabled": True,  # 是否启用IYUU推送
    "schedule": {
        "enabled": False,  # 是否启用定时推送
        "times": ["08:00"],  # 定时推送时间数组，支持多个时间段
        "message": "Natter服务状态日报",  # 定时推送消息
    },
}

# 消息队列用于事件整合推送
message_queue = deque(maxlen=50)  # 增大队列容量到50条
message_lock = threading.RLock()
message_batch_timer = None  # 批量发送定时器
last_send_time = 0  # 上次发送时间
MIN_SEND_INTERVAL = 300  # 最小发送间隔(秒)，5分钟

# NAT类型和端口状态的正则表达式
NAT_TYPE_PATTERN = re.compile(r"NAT type: ([^\n]+)")
LAN_STATUS_PATTERN = re.compile(r"LAN > ([^\[]+)\[ ([^\]]+) \]")
WAN_STATUS_PATTERN = re.compile(r"WAN > ([^\[]+)\[ ([^\]]+) \]")

# 默认密码为None，表示不启用验证
PASSWORD = None

# 获取环境变量中的管理员密码
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "zd2580"  # 默认密码zd2580

# 认证token管理
auth_tokens = {}  # token -> 过期时间戳
AUTH_TOKEN_EXPIRE = 24 * 60 * 60  # token有效期24小时

# MCP服务配置
MCP_ENABLED = os.environ.get("MCP_ENABLED", "true").lower() == "true"
MCP_TIMEOUT = int(os.environ.get("MCP_TIMEOUT", "30"))  # MCP请求超时时间(秒)
MCP_MAX_CONNECTIONS = int(os.environ.get("MCP_MAX_CONNECTIONS", "10"))  # 最大并发连接数

# MCP协议配置
MCP_WEBSOCKET_ENABLED = os.environ.get("MCP_WEBSOCKET_ENABLED", "true").lower() == "true"
MCP_WEBSOCKET_PORT = int(os.environ.get("MCP_WEBSOCKET_PORT", "8081"))
MCP_STDIO_ENABLED = os.environ.get("MCP_STDIO_ENABLED", "true").lower() == "true"
MCP_TCP_ENABLED = os.environ.get("MCP_TCP_ENABLED", "true").lower() == "true"
MCP_TCP_PORT = int(os.environ.get("MCP_TCP_PORT", "8082"))
MCP_SSE_ENABLED = os.environ.get("MCP_SSE_ENABLED", "true").lower() == "true"

# MCP客户端连接管理
mcp_connections = {}  # connection_id -> connection_info
mcp_subscriptions = {}  # connection_id -> subscription_list
mcp_connection_lock = threading.RLock()


# 修改添加消息到推送队列函数
def queue_message(category, title, content, important=False):
    """添加消息到队列，等待批量推送

    Args:
        category: 消息类别
        title: 消息标题
        content: 消息内容
        important: 是否为重要消息，影响发送策略
    """
    if not iyuu_config.get("enabled", True) or not iyuu_config.get("tokens"):
        return

    with message_lock:
        message_queue.append(
            {
                "category": category,  # 消息类别: 启动, 停止, 地址变更, 错误等
                "title": title,  # 消息标题
                "content": content,  # 消息内容
                "time": time.time(),  # 消息生成时间
                "important": important,  # 是否为重要消息
            }
        )

        # 同时向MCP客户端发送通知
        if MCP_ENABLED:
            try:
                MCPNotificationManager.notify_subscribers("service_status", {
                    "category": category,
                    "title": title,
                    "content": content,
                    "important": important
                })
            except Exception as e:
                print(f"MCP通知发送失败: {e}")

        # 如果消息标记为重要，或满足特定条件，考虑立即发送
        should_send_now = important or len(message_queue) >= 10

        # 检查距离上次发送是否已超过最小间隔
        global last_send_time
        current_time = time.time()
        time_since_last_send = current_time - last_send_time

        if should_send_now and time_since_last_send >= MIN_SEND_INTERVAL:
            # 立即发送
            print(
                f"触发立即发送: {'重要消息' if important else '消息队列已满'}, 距上次发送已过{time_since_last_send:.1f}秒"
            )
            send_batch_messages()
        else:
            # 否则，设置或重置定时器
            global message_batch_timer
            if message_batch_timer is None or not message_batch_timer.is_alive():
                # 计算下次发送时间：确保至少间隔MIN_SEND_INTERVAL
                next_send_delay = max(
                    MIN_SEND_INTERVAL - time_since_last_send, 5
                )  # 至少等待5秒，原来是60秒

                # 如果消息是重要的但未达到发送间隔，使用较短的延迟
                if important and next_send_delay > 5:
                    next_send_delay = 5  # 重要消息使用5秒延迟，原来是60秒

                message_batch_timer = threading.Timer(
                    next_send_delay, send_batch_messages
                )
                message_batch_timer.daemon = True
                message_batch_timer.start()
                print(
                    f"消息整合推送定时器已启动，将在{next_send_delay:.1f}秒后发送批量消息"
                )


# 修改批量发送消息队列中的所有消息函数
def send_batch_messages():
    """批量发送队列中的所有消息"""
    global message_batch_timer, last_send_time
    message_batch_timer = None

    with message_lock:
        if not message_queue:
            return

        # 更新上次发送时间
        last_send_time = time.time()

        # 按类别整理消息并去重
        categories = {}
        for msg in message_queue:
            cat = msg["category"]

            # 处理定时报告类别的消息去重
            if cat == "定时报告":
                # 如果该类别已存在消息，检查内容是否重复
                if cat in categories:
                    # 检查是否有内容相同的消息已存在
                    is_duplicate = False
                    for existing_msg in categories[cat]:
                        if existing_msg["content"] == msg["content"]:
                            is_duplicate = True
                            break

                    # 如果是重复消息，跳过添加
                    if is_duplicate:
                        continue

            # 添加消息到对应类别
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(msg)

        # 构建整合后的消息内容
        total_unique_messages = sum(len(msgs) for msgs in categories.values())
        message_title = f"Natter服务状态更新 [{total_unique_messages}条]"
        message_content = f"## 📣 服务状态整合通知 ##\n\n"
        message_content += f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        message_content += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 服务状态汇总部分 - 新增服务整体状态小结
        running_services = []
        services_with_mappings = {}

        # 收集所有服务信息和映射地址
        for cat, messages in categories.items():
            for msg in messages:
                # 尝试从消息内容中提取服务ID和映射地址
                content = msg["content"]
                service_name = (
                    msg["title"].split("]")[-1].strip()
                    if "]" in msg["title"]
                    else msg["title"]
                )

                # 提取服务的运行状态
                if cat == "启动":
                    running_services.append(service_name)

                # 提取映射地址
                mapping_match = re.search(r"映射地址[：:]\s*([^\n]+)", content)
                if mapping_match:
                    mapping = mapping_match.group(1).strip()
                    if mapping and mapping != "无" and mapping != "无映射":
                        services_with_mappings[service_name] = mapping

                # 也从消息标题中提取服务名称（针对地址变更消息）
                if cat == "地址变更" or cat == "地址分配":
                    # 提取新地址
                    new_addr_match = re.search(r"新地址[：:]\s*([^\n]+)", content)
                    if new_addr_match:
                        new_addr = new_addr_match.group(1).strip()
                        if new_addr and new_addr != "无" and new_addr != "无映射":
                            services_with_mappings[service_name] = new_addr

        # 添加服务映射地址汇总部分（如果有）
        if services_with_mappings:
            message_content += "📌 **服务映射地址汇总**\n"
            for service_name, mapping in services_with_mappings.items():
                running_status = "🟢" if service_name in running_services else "⚪"
                message_content += f"{running_status} **{service_name}**: `{mapping}`\n"
            message_content += "\n"

        # 优先处理错误和重要类别
        priority_cats = ["错误", "服务状态", "定时报告"]
        sorted_cats = sorted(
            categories.keys(), key=lambda x: (0 if x in priority_cats else 1, x)
        )

        # 按类别添加消息
        for cat in sorted_cats:
            messages = categories[cat]
            # 添加类别图标
            cat_icon = (
                "⚠️"
                if cat == "错误"
                else (
                    "📊"
                    if cat == "定时报告"
                    else (
                        "🔄"
                        if cat == "地址变更"
                        else "▶️" if cat == "启动" else "⏹️" if cat == "停止" else "📋"
                    )
                )
            )
            message_content += f"📌 **{cat_icon} {cat} ({len(messages)}条)**\n"
            message_content += f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"

            # 对错误和重要消息，提供更详细的信息
            if cat in ["错误", "服务状态"]:
                for msg in messages:
                    # 提取消息标题中服务名称部分
                    service_name = (
                        msg["title"].split("]")[-1].strip()
                        if "]" in msg["title"]
                        else msg["title"]
                    )
                    # 使用完整内容，但进行格式优化
                    formatted_content = msg["content"].replace("\n", "\n  ")
                    message_content += (
                        f"➤ **{service_name}**:\n  {formatted_content}\n\n"
                    )
            # 定时报告特殊处理，提取并高亮显示服务状态
            elif cat == "定时报告":
                # 只显示一次定时报告的整体摘要，避免冗余
                if messages:
                    # 使用第一条消息作为代表
                    msg = messages[0]
                    content = msg["content"]

                    # 提取服务总数等信息的更好方法
                    summary_sections = re.findall(
                        r"总服务数.*?运行中.*?已停止.*?", content, re.DOTALL
                    )
                    if summary_sections:
                        summary = summary_sections[0].strip()
                        # 美化格式
                        summary = (
                            summary.replace("总服务数", "总服务数")
                            .replace("运行中", "🟢 运行中")
                            .replace("已停止", "⚪ 已停止")
                        )
                        message_content += f"➤ **服务概况**:\n  {summary}\n\n"

                    # 提取服务列表并美化展示
                    message_content += f"➤ **服务详情**:\n"

                    # 使用正则表达式提取服务信息，支持树形格式的匹配
                    services_section = re.search(
                        r"服务详情\*\*\n(.*?)(?=\n\s*━━━|\Z)", content, re.DOTALL
                    )
                    if services_section:
                        services_text = services_section.group(1)
                        # 按服务分块提取
                        service_blocks = re.findall(
                            r"([🟢⚪].*?\n(?:.*?─.*?\n)*)", services_text, re.DOTALL
                        )
                        for block in service_blocks:
                            service_lines = block.strip().split("\n")
                            if service_lines:
                                # 提取服务名称和状态
                                service_info = service_lines[
                                    0
                                ]  # 第一行包含服务名和状态emoji
                                # 提取映射地址
                                mapping_line = next(
                                    (line for line in service_lines if "映射" in line),
                                    None,
                                )
                                if mapping_line:
                                    mapping_address = re.search(
                                        r"`(.*?)`", mapping_line
                                    )
                                    if mapping_address:
                                        # 重构服务显示行，保持简洁
                                        emoji = "🟢" if "🟢" in service_info else "⚪"
                                        name = re.search(r"\*\*(.*?)\*\*", service_info)
                                        if name:
                                            message_content += f"  {emoji} **{name.group(1)}**: `{mapping_address.group(1)}`\n"
                    else:
                        # 尝试备用方法提取服务信息 - 兼容旧格式
                        services_details = re.findall(
                            r"\[(运行中|已停止)\](.*?)-(.*?)(?=\n\[|\n\n|\Z)",
                            content,
                            re.DOTALL,
                        )
                        for status, name, address in services_details:
                            status_emoji = "🟢" if status == "运行中" else "⚪"
                            message_content += f"  {status_emoji} **{name.strip()}**: `{address.strip()}`\n"

                    message_content += "\n"
            # 普通消息类别
            else:
                for msg in messages:
                    service_name = (
                        msg["title"].split("]")[-1].strip()
                        if "]" in msg["title"]
                        else msg["title"]
                    )
                    content = msg["content"]

                    # 尝试提取并突出显示映射地址（如果有）
                    mapping_info = ""
                    mapping_match = re.search(r"映射地址[：:]\s*([^\n]+)", content)
                    if mapping_match:
                        mapping = mapping_match.group(1).strip()
                        if mapping and mapping != "无" and mapping != "无映射":
                            mapping_info = f" | 映射: `{mapping}`"

                    # 提取服务ID和本地端口（如果有）
                    service_id_match = re.search(r"服务ID[：:]\s*([^\n]+)", content)
                    local_port_match = re.search(r"本地端口[：:]\s*([^\n]+)", content)

                    service_info = ""
                    if service_id_match:
                        service_id = service_id_match.group(1).strip()
                        service_info += f"ID: {service_id}"

                    if local_port_match:
                        local_port = local_port_match.group(1).strip()
                        if service_info:
                            service_info += f" | "
                        service_info += f"端口: {local_port}"

                    if service_info:
                        service_info = f" ({service_info})"

                    # 美化消息显示
                    message_content += f"➤ **{service_name}**{service_info}:\n"

                    # 提取重要信息并格式化展示
                    important_items = []
                    if "服务已成功启动" in content:
                        important_items.append("✅ 服务已成功启动")
                    elif "服务已停止" in content:
                        important_items.append("⏹️ 服务已停止运行")
                    elif "服务已被手动停止" in content:
                        important_items.append("⏹️ 服务已被手动停止")
                    elif "映射地址已变更" in content:
                        old_addr_match = re.search(r"旧地址[：:]\s*([^\n]+)", content)
                        new_addr_match = re.search(r"新地址[：:]\s*([^\n]+)", content)
                        if old_addr_match and new_addr_match:
                            old_addr = old_addr_match.group(1).strip()
                            new_addr = new_addr_match.group(1).strip()
                            important_items.append(
                                f"🔄 映射地址变更: `{old_addr}` → `{new_addr}`"
                            )
                    elif "服务获取到映射地址" in content:
                        important_items.append(f"🆕 获取新映射地址{mapping_info}")

                    # 如果没有提取到特定信息，展示第一行
                    if not important_items:
                        first_line = (
                            content.split("\n", 1)[0] if "\n" in content else content
                        )
                        important_items.append(first_line)

                    # 显示提取的重要信息
                    for item in important_items:
                        message_content += f"  {item}\n"

                    message_content += "\n"

        message_content += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message_content += f"💡 通过Natter管理界面可以管理服务"

        # 直接发送整合后的消息
        _send_iyuu_message_direct(message_title, message_content)

        # 清空消息队列
        queue_len = len(message_queue)
        message_queue.clear()
        print(f"已整合发送 {queue_len} 条服务状态消息")


# 修改直接发送IYUU消息的内部函数
def _send_iyuu_message_direct(text, desp):
    """直接发送IYUU消息，不经过队列

    内部使用，不应该被外部直接调用
    """
    if not iyuu_config.get("enabled", True) or not iyuu_config.get("tokens"):
        return False, ["IYUU推送已禁用或未配置令牌"]

    success = False
    errors = []

    for token in iyuu_config.get("tokens", []):
        if not token.strip():
            continue

        try:
            url = f"https://iyuu.cn/{token}.send"
            payload = {"text": text, "desp": desp}
            headers = {"Content-Type": "application/json; charset=UTF-8"}

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    success = True
                else:
                    errors.append(
                        f"令牌 {token[:5]}...: {result.get('errmsg', '未知错误')}"
                    )
            else:
                errors.append(f"令牌 {token[:5]}...: HTTP错误 {response.status_code}")
        except Exception as e:
            errors.append(f"令牌 {token[:5]}...: {str(e)}")

    if success:
        return True, errors
    else:
        return False, errors


# 修改公开的IYUU消息发送函数
def send_iyuu_message(text, desp, force_send=False):
    """发送IYUU消息推送

    Args:
        text: 消息标题
        desp: 消息内容
        force_send: 废弃参数，保留为兼容性，实际使用important参数

    Returns:
        (success, errors) 元组，表示是否成功发送和错误信息列表
    """
    # 判断消息类型和重要性
    is_important = False
    category = "通知"

    # 根据消息标题识别类别
    if "[错误]" in text or "错误" in text:
        category = "错误"
        is_important = True
    elif "[启动]" in text:
        category = "启动"
    elif "[停止]" in text or "[手动停止]" in text:
        category = "停止"
    elif "[地址变更]" in text or "[地址分配]" in text:
        category = "地址变更"
    elif "日报" in text or "服务状态" in text:
        category = "定时报告"
        is_important = True
    elif "管理服务已启动" in text:
        category = "服务状态"
        is_important = True
    elif "管理服务已关闭" in text:
        category = "服务状态"
        is_important = True

    # 将消息加入队列
    queue_message(category, text, desp, important=is_important)
    return True, []


# 修改定时推送函数
def schedule_daily_notification():
    """设置每日定时推送任务"""
    if not iyuu_config.get("schedule", {}).get("enabled", False):
        return

    def check_and_send_notification():
        # 使用集合记录已处理的时间点，避免重复推送
        processed_times = set()
        # 记录上次检查的时间，防止短时间内多次触发
        last_check_time = ""

        while True:
            now = time.localtime()
            current_time = f"{now.tm_hour:02d}:{now.tm_min:02d}"

            # 如果当前分钟已经检查过，则跳过
            if current_time == last_check_time:
                time.sleep(1)  # 短暂休眠后再次检查
                continue

            # 更新上次检查的时间
            last_check_time = current_time

            schedule_times = iyuu_config.get("schedule", {}).get("times", ["08:00"])

            # 检查当前时间是否在推送时间列表中，且尚未处理过
            if current_time in schedule_times and current_time not in processed_times:
                # 将当前时间添加到已处理集合中
                processed_times.add(current_time)
                print(f"触发定时推送: {current_time}")

                # 获取所有服务状态用于日报
                services_info = NatterManager.list_services()
                running_count = sum(
                    1 for s in services_info if s.get("status") == "运行中"
                )
                stopped_count = sum(
                    1 for s in services_info if s.get("status") == "已停止"
                )

                message = iyuu_config.get("schedule", {}).get(
                    "message", "Natter服务状态日报"
                )
                detail = f"## 📊 Natter服务状态日报 ##\n\n"
                detail += f"⏰ 报告时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                detail += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                detail += f"📌 **服务概况**\n"
                detail += f"➤ 总服务数: {len(services_info)}\n"
                detail += f"➤ 🟢 运行中: {running_count}\n"
                detail += f"➤ ⚪ 已停止: {stopped_count}\n\n"

                if services_info:
                    detail += f"📌 **服务详情**\n"
                    for service in services_info:
                        service_id = service.get("id", "未知")
                        remark = service.get("remark") or f"服务 {service_id}"
                        status = service.get("status", "未知")
                        mapped_address = service.get("mapped_address", "无映射")
                        lan_status = service.get("lan_status", "未知")
                        wan_status = service.get("wan_status", "未知")
                        nat_type = service.get("nat_type", "未知")

                        # 根据状态添加emoji
                        status_emoji = "🟢" if status == "运行中" else "⚪"

                        detail += f"{status_emoji} **{remark}**\n"
                        detail += f"  ├─ 状态: {status}\n"
                        detail += f"  ├─ 映射: `{mapped_address}`\n"
                        detail += f"  ├─ LAN状态: {lan_status}\n"
                        detail += f"  ├─ WAN状态: {wan_status}\n"
                        detail += f"  └─ NAT类型: {nat_type}\n\n"
                else:
                    detail += "❗ 当前无服务运行\n\n"

                detail += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                detail += f"💡 通过Natter管理界面可以管理服务"

                # 使用消息队列处理定时推送，标记为重要消息
                send_iyuu_message(message, detail)

                # 日志记录推送时间
                print(f"已在 {current_time} 将定时推送加入消息队列")

            # 每天 00:00 重置已处理时间集合，便于第二天重新推送
            if current_time == "00:00" and "00:00" not in processed_times:
                processed_times.clear()
                processed_times.add("00:00")  # 添加00:00防止当天重复处理

            # 休眠5秒再检查
            time.sleep(5)

    notification_thread = threading.Thread(
        target=check_and_send_notification, daemon=True
    )
    notification_thread.start()


# WebSocket协议处理类
class MCPWebSocketHandler:
    """WebSocket协议的MCP处理器"""

    def __init__(self, socket, address):
        self.socket = socket
        self.address = address
        self.connection_id = secrets.token_hex(8)
        self.authenticated = False
        self.user_role = None
        self.protocol = MCPProtocol()

    def generate_websocket_key(self, key):
        """生成WebSocket接受key"""
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        combined = key + magic
        return base64.b64encode(hashlib.sha1(combined.encode()).digest()).decode()

    def send_frame(self, data):
        """发送WebSocket帧"""
        if isinstance(data, str):
            data = data.encode('utf-8')

        payload_length = len(data)

        # 构建帧头
        frame = bytearray()
        frame.append(0x81)  # FIN=1, opcode=text

        if payload_length < 126:
            frame.append(payload_length)
        elif payload_length < 65536:
            frame.append(126)
            frame.extend(struct.pack('>H', payload_length))
        else:
            frame.append(127)
            frame.extend(struct.pack('>Q', payload_length))

        frame.extend(data)

        try:
            self.socket.send(frame)
            return True
        except Exception as e:
            print(f"WebSocket发送失败 {self.connection_id}: {e}")
            return False

    def receive_frame(self):
        """接收WebSocket帧"""
        try:
            # 读取帧头
            frame_start = self.socket.recv(2)
            if len(frame_start) != 2:
                return None

            fin = (frame_start[0] & 0x80) != 0
            opcode = frame_start[0] & 0x0F
            masked = (frame_start[1] & 0x80) != 0
            payload_length = frame_start[1] & 0x7F

            # 读取扩展长度
            if payload_length == 126:
                length_data = self.socket.recv(2)
                payload_length = struct.unpack('>H', length_data)[0]
            elif payload_length == 127:
                length_data = self.socket.recv(8)
                payload_length = struct.unpack('>Q', length_data)[0]

            # 读取掩码
            mask = None
            if masked:
                mask = self.socket.recv(4)

            # 读取载荷数据
            payload = self.socket.recv(payload_length)

            # 解掩码
            if masked and mask:
                payload = bytearray(payload)
                for i in range(len(payload)):
                    payload[i] ^= mask[i % 4]
                payload = bytes(payload)

            if opcode == 0x8:  # 关闭帧
                return None
            elif opcode == 0x1:  # 文本帧
                return payload.decode('utf-8')

            return None

        except Exception as e:
            print(f"WebSocket接收失败 {self.connection_id}: {e}")
            return None

    def handle_websocket_handshake(self, request_data):
        """处理WebSocket握手"""
        lines = request_data.decode('utf-8').split('\r\n')
        headers = {}

        for line in lines[1:]:
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()

        websocket_key = headers.get('sec-websocket-key')
        if not websocket_key:
            return False

        accept_key = self.generate_websocket_key(websocket_key)

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            "\r\n"
        ).encode('utf-8')

        try:
            self.socket.send(response)
            return True
        except Exception as e:
            print(f"WebSocket握手失败 {self.connection_id}: {e}")
            return False

    def authenticate_websocket_message(self, message_data):
        """认证WebSocket消息"""
        try:
            data = json.loads(message_data)

            # 检查是否包含认证信息
            auth = data.get('auth', {})
            password = auth.get('password')

            if not password:
                return False, "guest"  # 默认guest权限

            # 验证密码
            if password == ADMIN_PASSWORD:
                return True, "admin"
            else:
                # 检查是否是guest组密码
                for group_id, group_info in service_groups.get("groups", {}).items():
                    if group_info.get("password") == password:
                        return True, "guest"

                return False, None

        except Exception as e:
            print(f"WebSocket认证解析失败 {self.connection_id}: {e}")
            return False, None

    def handle_connection(self):
        """处理WebSocket连接"""
        try:
            # 接收握手请求
            request_data = self.socket.recv(4096)
            if not self.handle_websocket_handshake(request_data):
                return

            print(f"WebSocket连接建立: {self.connection_id} from {self.address}")

            # 注册连接
            with mcp_connection_lock:
                mcp_connections[self.connection_id] = {
                    "type": "websocket",
                    "handler": self,
                    "created": time.time(),
                    "authenticated": False,
                    "user_role": None
                }

            # 处理消息循环
            while True:
                message = self.receive_frame()
                if message is None:
                    break

                try:
                    # 解析消息
                    data = json.loads(message)

                    # 如果未认证，先进行认证
                    if not self.authenticated:
                        success, role = self.authenticate_websocket_message(message)
                        if success:
                            self.authenticated = True
                            self.user_role = role

                            with mcp_connection_lock:
                                mcp_connections[self.connection_id]["authenticated"] = True
                                mcp_connections[self.connection_id]["user_role"] = role

                            # 发送认证成功响应
                            auth_response = {
                                "success": True,
                                "connection_id": self.connection_id,
                                "user_role": role,
                                "message": "WebSocket认证成功"
                            }
                            self.send_frame(json.dumps(auth_response))
                            continue
                        else:
                            # 认证失败
                            auth_response = {
                                "success": False,
                                "error": "认证失败",
                                "message": "密码无效"
                            }
                            self.send_frame(json.dumps(auth_response))
                            break

                    # 处理MCP消息
                    if 'message' in data:
                        mcp_message = data['message']
                        response = self.protocol.handle_message(mcp_message, self.connection_id, self.user_role)
                        self.send_frame(json.dumps(response))
                    else:
                        # 直接的MCP消息
                        response = self.protocol.handle_message(data, self.connection_id, self.user_role)
                        self.send_frame(json.dumps(response))

                except json.JSONDecodeError:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None
                    }
                    self.send_frame(json.dumps(error_response))
                except Exception as e:
                    print(f"WebSocket消息处理错误 {self.connection_id}: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                        "id": None
                    }
                    self.send_frame(json.dumps(error_response))

        except Exception as e:
            print(f"WebSocket连接错误 {self.connection_id}: {e}")
        finally:
            # 清理连接
            with mcp_connection_lock:
                mcp_connections.pop(self.connection_id, None)
                mcp_subscriptions.pop(self.connection_id, None)

            try:
                self.socket.close()
            except:
                pass

            print(f"WebSocket连接关闭: {self.connection_id}")


# MCP协议处理核心类
class MCPProtocol:
    """MCP (Model Context Protocol) 协议处理器"""

    def __init__(self):
        self.version = "2024-11-05"
        self.protocol_version = "2024-11-05"
        self.implementation = {
            "name": "natter-web-mcp",
            "version": "1.0.0"
        }

    def handle_message(self, message, connection_id=None):
        """处理MCP消息"""
        try:
            if not isinstance(message, dict):
                message = json.loads(message) if isinstance(message, str) else message

            # 验证MCP消息基本结构
            if "jsonrpc" not in message or message["jsonrpc"] != "2.0":
                return self._create_error_response(
                    message.get("id"), -32600, "Invalid Request", "Missing or invalid jsonrpc version"
                )

            method = message.get("method")
            request_id = message.get("id")
            params = message.get("params", {})

            # 处理不同的MCP方法
            if method == "initialize":
                return self._handle_initialize(request_id, params, connection_id)
            elif method == "notifications/initialized":
                return self._handle_initialized(connection_id)
            elif method == "tools/list":
                return self._handle_tools_list(request_id, params, connection_id)
            elif method == "tools/call":
                return self._handle_tools_call(request_id, params, connection_id)
            elif method == "notifications/subscribe":
                return self._handle_subscribe(request_id, params, connection_id)
            elif method == "ping":
                return self._handle_ping(request_id)
            else:
                return self._create_error_response(
                    request_id, -32601, "Method not found", f"Unknown method: {method}"
                )

        except json.JSONDecodeError as e:
            return self._create_error_response(
                None, -32700, "Parse error", f"Invalid JSON: {str(e)}"
            )
        except Exception as e:
            print(f"MCP协议处理错误: {e}")
            return self._create_error_response(
                message.get("id") if isinstance(message, dict) else None,
                -32603, "Internal error", str(e)
            )

    def _handle_initialize(self, request_id, params, connection_id):
        """处理初始化握手"""
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "2024-11-05")

        # 记录连接信息
        if connection_id:
            with mcp_connection_lock:
                mcp_connections[connection_id] = {
                    "client_info": client_info,
                    "protocol_version": protocol_version,
                    "authenticated": False,
                    "user_role": None,
                    "connected_at": time.time()
                }

        return self._create_success_response(request_id, {
            "protocolVersion": self.protocol_version,
            "serverInfo": self.implementation,
            "capabilities": {
                "tools": {
                    "listChanged": True
                },
                "notifications": {
                    "subscribe": True
                }
            }
        })

    def _handle_initialized(self, connection_id):
        """处理初始化完成通知"""
        print(f"MCP客户端 {connection_id} 初始化完成")
        return None  # 不需要响应

    def _handle_tools_list(self, request_id, params, connection_id):
        """处理工具列表请求"""
        user_role = self._get_user_role(connection_id)
        if not user_role:
            return self._create_error_response(
                request_id, -32002, "Unauthorized", "Authentication required"
            )

        # 获取可用工具列表
        tools = MCPToolRegistry.get_available_tools(user_role)

        return self._create_success_response(request_id, {
            "tools": tools
        })

    def _handle_tools_call(self, request_id, params, connection_id):
        """处理工具调用请求"""
        user_role = self._get_user_role(connection_id)
        if not user_role:
            return self._create_error_response(
                request_id, -32002, "Unauthorized", "Authentication required"
            )

        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._create_error_response(
                request_id, -32602, "Invalid params", "Missing tool name"
            )

        # 执行工具调用
        try:
            result = MCPToolRegistry.execute_tool(tool_name, arguments, user_role, connection_id)
            return self._create_success_response(request_id, result)
        except Exception as e:
            return self._create_error_response(
                request_id, -32603, "Tool execution error", str(e)
            )

    def _handle_subscribe(self, request_id, params, connection_id):
        """处理订阅请求"""
        if not connection_id:
            return self._create_error_response(
                request_id, -32602, "Invalid params", "Connection ID required"
            )

        subscription_type = params.get("type", "service_status")

        with mcp_connection_lock:
            if connection_id not in mcp_subscriptions:
                mcp_subscriptions[connection_id] = []
            if subscription_type not in mcp_subscriptions[connection_id]:
                mcp_subscriptions[connection_id].append(subscription_type)

        return self._create_success_response(request_id, {
            "subscribed": subscription_type
        })

    def _handle_ping(self, request_id):
        """处理ping请求"""
        return self._create_success_response(request_id, {
            "pong": True,
            "timestamp": time.time()
        })

    def _get_user_role(self, connection_id):
        """获取用户角色"""
        if not connection_id:
            return None

        with mcp_connection_lock:
            conn_info = mcp_connections.get(connection_id)
            if conn_info and conn_info.get("authenticated"):
                return conn_info.get("user_role")

        return None

    def _create_success_response(self, request_id, result):
        """创建成功响应"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }

    def _create_error_response(self, request_id, code, message, data=None):
        """创建错误响应"""
        error = {
            "code": code,
            "message": message
        }
        if data:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error
        }


# MCP工具注册和管理系统
class MCPToolRegistry:
    """MCP工具注册表和管理器"""

    _tools = {}  # 工具名称 -> 工具信息
    _handlers = {}  # 工具名称 -> 处理函数
    _permissions = {}  # 工具名称 -> 所需权限

    @classmethod
    def register_tool(cls, name, description, input_schema, handler, required_role="guest"):
        """注册MCP工具"""
        cls._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema
        }
        cls._handlers[name] = handler
        cls._permissions[name] = required_role
        print(f"注册MCP工具: {name}")

    @classmethod
    def get_available_tools(cls, user_role):
        """获取用户可用的工具列表"""
        available_tools = []

        for tool_name, tool_info in cls._tools.items():
            required_role = cls._permissions.get(tool_name, "guest")

            # 检查用户权限
            if cls._check_permission(user_role, required_role):
                available_tools.append(tool_info)

        return available_tools

    @classmethod
    def execute_tool(cls, tool_name, arguments, user_role, connection_id):
        """执行工具调用"""
        if tool_name not in cls._tools:
            raise Exception(f"Unknown tool: {tool_name}")

        # 检查权限
        required_role = cls._permissions.get(tool_name, "guest")
        if not cls._check_permission(user_role, required_role):
            raise Exception(f"Insufficient permissions for tool: {tool_name}")

        # 获取处理函数
        handler = cls._handlers.get(tool_name)
        if not handler:
            raise Exception(f"No handler for tool: {tool_name}")

        # 执行工具
        try:
            result = handler(arguments, user_role, connection_id)

            # 记录工具调用
            print(f"MCP工具调用: {tool_name} by {user_role} from {connection_id}")

            # 格式化MCP响应
            if isinstance(result, dict) and "content" in result:
                return result
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result) if result is not None else "操作完成"
                        }
                    ]
                }
        except Exception as e:
            print(f"MCP工具执行错误 {tool_name}: {e}")
            raise

    @classmethod
    def _check_permission(cls, user_role, required_role):
        """检查用户权限"""
        if required_role == "guest":
            return user_role in ["admin", "guest"]
        elif required_role == "admin":
            return user_role == "admin"
        return False

    @classmethod
    def initialize_tools(cls):
        """初始化所有工具"""
        # 这个方法将在稍后由MCPServiceTools调用来注册具体工具
        print("MCP工具注册表已初始化")


# MCP通知管理器
class MCPNotificationManager:
    """MCP客户端通知管理器"""

    @staticmethod
    def notify_subscribers(event_type, data):
        """向订阅的MCP客户端发送通知"""
        try:
            with mcp_connection_lock:
                if not mcp_subscriptions:
                    return

                # 构建通知消息
                notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/message",
                    "params": {
                        "type": event_type,
                        "data": data,
                        "timestamp": time.time()
                    }
                }

                # 发送给所有订阅此类型事件的客户端
                for connection_id, subscription_types in mcp_subscriptions.items():
                    if event_type in subscription_types or "all" in subscription_types:
                        # 获取连接信息
                        connection_info = mcp_connections.get(connection_id)
                        if not connection_info:
                            continue

                        connection_type = connection_info.get("type")
                        handler = connection_info.get("handler")

                        try:
                            # 根据连接类型发送通知
                            if connection_type == "websocket" and handler:
                                # WebSocket通知
                                handler.send_frame(json.dumps(notification))
                                print(f"MCP WebSocket通知发送到 {connection_id}: {event_type}")

                            elif connection_type == "tcp" and handler:
                                # TCP通知
                                handler.send_message(json.dumps(notification))
                                print(f"MCP TCP通知发送到 {connection_id}: {event_type}")

                            elif connection_type == "sse" and handler:
                                # SSE通知
                                handler._send_sse_event("notification", {
                                    "type": event_type,
                                    "data": data,
                                    "timestamp": time.time()
                                })
                                print(f"MCP SSE通知发送到 {connection_id}: {event_type}")

                            elif connection_type == "stdio":
                                # stdio通知（输出到stdout）
                                print(json.dumps(notification), flush=True)
                                print(f"MCP stdio通知发送到 {connection_id}: {event_type}")

                            else:
                                print(f"MCP未知连接类型 {connection_id}: {connection_type}")

                        except Exception as e:
                            print(f"MCP通知发送失败 {connection_id}: {e}")
                            # 如果发送失败，可能连接已断开，清理连接
                            mcp_connections.pop(connection_id, None)
                            mcp_subscriptions.pop(connection_id, None)

        except Exception as e:
            print(f"MCP通知发送失败: {e}")

    @staticmethod
    def integrate_with_existing_notifications():
        """集成到现有的通知系统中"""
        # 这个方法会修改现有的queue_message函数以支持MCP通知
        pass


# WebSocket服务器
class MCPWebSocketServer:
    """MCP WebSocket服务器"""

    def __init__(self, port=MCP_WEBSOCKET_PORT):
        self.port = port
        self.server_socket = None
        self.running = False

    def start_server(self):
        """启动WebSocket服务器"""
        if not MCP_WEBSOCKET_ENABLED:
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.running = True

            print(f"MCP WebSocket服务器启动在端口 {self.port}")

            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    handler = MCPWebSocketHandler(client_socket, address)

                    # 在新线程中处理连接
                    thread = threading.Thread(target=handler.handle_connection, daemon=True)
                    thread.start()

                except Exception as e:
                    if self.running:
                        print(f"WebSocket连接处理错误: {e}")

        except Exception as e:
            print(f"WebSocket服务器启动失败: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def stop_server(self):
        """停止WebSocket服务器"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


# TCP直连协议处理器
class MCPTCPHandler(socketserver.BaseRequestHandler):
    """MCP TCP协议处理器"""

    def handle(self):
        connection_id = secrets.token_hex(8)
        client_address = self.client_address
        authenticated = False
        user_role = None
        protocol = MCPProtocol()

        print(f"MCP TCP连接建立: {connection_id} from {client_address}")

        try:
            # 注册连接
            with mcp_connection_lock:
                mcp_connections[connection_id] = {
                    "type": "tcp",
                    "handler": self,
                    "created": time.time(),
                    "authenticated": False,
                    "user_role": None
                }

            while True:
                try:
                    # 接收消息长度
                    length_data = self.request.recv(4)
                    if not length_data:
                        break

                    message_length = struct.unpack('>I', length_data)[0]

                    # 接收消息内容
                    message_data = b''
                    while len(message_data) < message_length:
                        chunk = self.request.recv(message_length - len(message_data))
                        if not chunk:
                            break
                        message_data += chunk

                    if len(message_data) != message_length:
                        break

                    message = message_data.decode('utf-8')
                    data = json.loads(message)

                    # 如果未认证，先进行认证
                    if not authenticated:
                        auth = data.get('auth', {})
                        password = auth.get('password')

                        if password == ADMIN_PASSWORD:
                            authenticated = True
                            user_role = "admin"
                        elif password:
                            # 检查guest组密码
                            for group_id, group_info in service_groups.get("groups", {}).items():
                                if group_info.get("password") == password:
                                    authenticated = True
                                    user_role = "guest"
                                    break

                        if authenticated:
                            with mcp_connection_lock:
                                mcp_connections[connection_id]["authenticated"] = True
                                mcp_connections[connection_id]["user_role"] = user_role

                            auth_response = {
                                "success": True,
                                "connection_id": connection_id,
                                "user_role": user_role
                            }
                            self.send_message(json.dumps(auth_response))
                            continue
                        else:
                            auth_response = {"success": False, "error": "认证失败"}
                            self.send_message(json.dumps(auth_response))
                            break

                    # 处理MCP消息
                    if 'message' in data:
                        mcp_message = data['message']
                        response = protocol.handle_message(mcp_message, connection_id, user_role)
                        self.send_message(json.dumps(response))
                    else:
                        response = protocol.handle_message(data, connection_id, user_role)
                        self.send_message(json.dumps(response))

                except json.JSONDecodeError:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None
                    }
                    self.send_message(json.dumps(error_response))
                except Exception as e:
                    print(f"TCP消息处理错误 {connection_id}: {e}")
                    break

        except Exception as e:
            print(f"TCP连接错误 {connection_id}: {e}")
        finally:
            # 清理连接
            with mcp_connection_lock:
                mcp_connections.pop(connection_id, None)
                mcp_subscriptions.pop(connection_id, None)

            print(f"MCP TCP连接关闭: {connection_id}")

    def send_message(self, message):
        """发送TCP消息"""
        try:
            message_bytes = message.encode('utf-8')
            length = struct.pack('>I', len(message_bytes))
            self.request.send(length + message_bytes)
        except Exception as e:
            print(f"TCP消息发送失败: {e}")


# TCP服务器
class MCPTCPServer:
    """MCP TCP服务器"""

    def __init__(self, port=MCP_TCP_PORT):
        self.port = port
        self.server = None

    def start_server(self):
        """启动TCP服务器"""
        if not MCP_TCP_ENABLED:
            return

        try:
            self.server = socketserver.ThreadingTCPServer(('0.0.0.0', self.port), MCPTCPHandler)
            print(f"MCP TCP服务器启动在端口 {self.port}")
            self.server.serve_forever()
        except Exception as e:
            print(f"TCP服务器启动失败: {e}")

    def stop_server(self):
        """停止TCP服务器"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()


# stdio协议处理器
class MCPStdioHandler:
    """MCP stdio协议处理器"""

    def __init__(self):
        self.protocol = MCPProtocol()
        self.authenticated = False
        self.user_role = None
        self.connection_id = secrets.token_hex(8)

    def start_stdio_server(self):
        """启动stdio服务器模式"""
        if not MCP_STDIO_ENABLED:
            return

        print(f"MCP stdio服务器启动，连接ID: {self.connection_id}")

        # 注册连接
        with mcp_connection_lock:
            mcp_connections[self.connection_id] = {
                "type": "stdio",
                "handler": self,
                "created": time.time(),
                "authenticated": False,
                "user_role": None
            }

        try:
            while True:
                try:
                    # 从stdin读取一行
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        line = sys.stdin.readline().strip()
                        if not line:
                            break

                        # 解析JSON消息
                        data = json.loads(line)

                        # 如果未认证，先进行认证
                        if not self.authenticated:
                            auth = data.get('auth', {})
                            password = auth.get('password')

                            if password == ADMIN_PASSWORD:
                                self.authenticated = True
                                self.user_role = "admin"
                            elif password:
                                # 检查guest组密码
                                for group_id, group_info in service_groups.get("groups", {}).items():
                                    if group_info.get("password") == password:
                                        self.authenticated = True
                                        self.user_role = "guest"
                                        break

                            if self.authenticated:
                                with mcp_connection_lock:
                                    mcp_connections[self.connection_id]["authenticated"] = True
                                    mcp_connections[self.connection_id]["user_role"] = self.user_role

                                auth_response = {
                                    "success": True,
                                    "connection_id": self.connection_id,
                                    "user_role": self.user_role
                                }
                                print(json.dumps(auth_response), flush=True)
                                continue
                            else:
                                auth_response = {"success": False, "error": "认证失败"}
                                print(json.dumps(auth_response), flush=True)
                                break

                        # 处理MCP消息
                        if 'message' in data:
                            mcp_message = data['message']
                            response = self.protocol.handle_message(mcp_message, self.connection_id, self.user_role)
                            print(json.dumps(response), flush=True)
                        else:
                            response = self.protocol.handle_message(data, self.connection_id, self.user_role)
                            print(json.dumps(response), flush=True)

                except json.JSONDecodeError:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None
                    }
                    print(json.dumps(error_response), flush=True)
                except Exception as e:
                    print(f"stdio消息处理错误: {e}", file=sys.stderr)

        except Exception as e:
            print(f"stdio服务器错误: {e}", file=sys.stderr)
        finally:
            # 清理连接
            with mcp_connection_lock:
                mcp_connections.pop(self.connection_id, None)
                mcp_subscriptions.pop(self.connection_id, None)


class NatterService:
    def __init__(self, service_id, cmd_args, remark=""):
        self.service_id = service_id
        self.cmd_args = cmd_args
        self.process = None
        self.start_time = None
        self.output_lines = []
        self.mapped_address = None
        self.status = "初始化中"
        self.lan_status = "未知"
        self.wan_status = "未知"
        self.nat_type = "未知"
        self.auto_restart = False
        self.restart_thread = None
        self.output_thread = None  # 添加输出线程引用
        self.local_port = None  # 添加本地端口属性
        self.remote_port = None  # 添加远程端口属性
        self.bind_interface = "0.0.0.0"  # 绑定接口，默认为所有接口
        self.bind_port = 0  # 绑定端口，默认为0（自动分配）
        self.remark = remark  # 添加备注属性
        self.last_mapped_address = None  # 记录上一次的映射地址，用于检测变更

        # 尝试从命令参数中解析端口信息
        self._parse_ports_from_args()

    def _parse_ports_from_args(self):
        """从命令参数中解析端口信息"""
        try:
            # 查找 -p 参数后面的端口号
            for i, arg in enumerate(self.cmd_args):
                if arg == "-p" and i + 1 < len(self.cmd_args):
                    self.local_port = int(self.cmd_args[i + 1])
                    break

            # 查找 -i 参数后面的绑定接口
            for i, arg in enumerate(self.cmd_args):
                if arg == "-i" and i + 1 < len(self.cmd_args):
                    self.bind_interface = self.cmd_args[i + 1]
                    break

            # 查找 -b 参数后面的绑定端口
            for i, arg in enumerate(self.cmd_args):
                if arg == "-b" and i + 1 < len(self.cmd_args):
                    self.bind_port = int(self.cmd_args[i + 1])
                    break

            # 在映射地址中寻找远程端口
            if self.mapped_address and ":" in self.mapped_address:
                parts = self.mapped_address.split(":")
                if len(parts) >= 2:
                    try:
                        self.remote_port = int(parts[-1])
                    except ValueError:
                        pass
        except Exception as e:
            print(f"解析端口信息出错: {e}")

    def start(self):
        """启动Natter服务"""
        if self.process and self.process.poll() is None:
            return False

        # 检查Docker环境下是否尝试使用nftables
        if os.path.exists("/.dockerenv") and any(
            arg == "-m"
            and i + 1 < len(self.cmd_args)
            and self.cmd_args[i + 1] == "nftables"
            for i, arg in enumerate(self.cmd_args)
        ):
            print(
                "错误: 在Docker环境中尝试使用nftables转发方法，此方法在Docker中不可用"
            )
            self.output_lines.append("❌ 错误: nftables在Docker容器中不可用")
            self.output_lines.append("💡 请使用socket或iptables转发方法")
            self.output_lines.append("➡️ 请停止此服务，然后使用其他转发方法重新创建服务")
            self.status = "已停止"

            # 发送错误推送 - 使用消息队列
            service_name = self.remark or f"服务 {self.service_id}"
            error_msg = "nftables在Docker容器中不可用，请使用socket或iptables转发方法"
            queue_message(
                "错误",
                f"[错误] {service_name}",
                f"服务启动失败\n错误原因: {error_msg}\n\n请停止此服务，然后使用其他转发方法重新创建服务",
            )

            return False

        cmd = [sys.executable, NATTER_PATH] + self.cmd_args

        # 如果没有指定keepalive间隔，添加默认值
        if not any(arg == "-k" for arg in self.cmd_args):
            cmd.extend(["-k", "30"])
            print(f"自动添加保活间隔: 30秒")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        self.start_time = time.time()
        self.status = "运行中"

        # 启动线程捕获输出，并保存线程引用
        self.output_thread = threading.Thread(target=self._capture_output)
        self.output_thread.daemon = True
        self.output_thread.start()

        # 发送启动推送 - 使用消息队列
        service_name = self.remark or f"服务 {self.service_id}"
        local_port = self.local_port or "未知"
        queue_message(
            "启动",
            f"[启动] {service_name}",
            f"服务已成功启动\n服务ID: {self.service_id}\n本地端口: {local_port}\n启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        )

        return True

    def _capture_output(self):
        """捕获并解析Natter输出"""
        nftables_error_detected = False
        line_count = 0
        max_lines = 10000  # 增加限制以防止无限累积

        try:
            for line in self.process.stdout:
                # 检查进程状态，如果已停止则退出
                if self.process.poll() is not None:
                    break

                self.output_lines.append(line.strip())
                line_count += 1

                # 限制保存的日志行数，防止内存泄漏
                if len(self.output_lines) > 100:
                    self.output_lines.pop(0)

                # 防止无限循环，限制处理的总行数
                if line_count > max_lines:
                    print(f"服务 {self.service_id} 输出行数过多，停止捕获")
                    break

                # 尝试提取映射地址 - 支持Natter v2.1.1的新格式
                if "<--Natter-->" in line:
                    parts = line.split("<--Natter-->")
                    if len(parts) == 2:
                        left_part = parts[0].strip()  # 包含目标地址和绑定地址
                        new_mapped_address = parts[1].strip()  # 映射的外网地址

                        # 解析绑定地址信息 - 支持新的三段式格式
                        try:
                            # 查找是否有转发方法标识符（如 <--socket--> 或 <--iptables-->）
                            if "-->" in left_part and "<--" in left_part:
                                # 新格式：tcp://目标地址 <--转发方法--> tcp://绑定地址
                                # 找到最后一个转发标识符的位置
                                last_arrow_end = left_part.rfind("-->")
                                if last_arrow_end != -1:
                                    # 提取绑定地址部分（在最后一个箭头之后）
                                    bind_address_part = left_part[
                                        last_arrow_end + 3 :
                                    ].strip()
                                    if "://" in bind_address_part:
                                        # 去掉协议前缀 (tcp:// 或 udp://)
                                        local_addr_part = bind_address_part.split(
                                            "://", 1
                                        )[1]
                                        if ":" in local_addr_part:
                                            bind_ip, bind_port_str = (
                                                local_addr_part.rsplit(":", 1)
                                            )
                                            self.bind_interface = bind_ip
                                            self.bind_port = int(bind_port_str)
                                            print(
                                                f"解析到绑定地址: {bind_ip}:{bind_port_str}"
                                            )
                            else:
                                # 旧格式：直接从left_part解析
                                if "://" in left_part:
                                    local_addr_part = left_part.split("://", 1)[1]
                                    if ":" in local_addr_part:
                                        bind_ip, bind_port_str = local_addr_part.rsplit(
                                            ":", 1
                                        )
                                        self.bind_interface = bind_ip
                                        self.bind_port = int(bind_port_str)
                        except Exception as e:
                            print(f"解析本地绑定地址出错: {e}")

                        # 检查映射地址是否变更
                        if self.mapped_address != new_mapped_address:
                            # 记录旧地址用于推送消息
                            old_address = self.mapped_address or "无"

                            # 更新地址 - 去掉协议前缀，只保存IP:Port格式
                            if "://" in new_mapped_address:
                                self.mapped_address = new_mapped_address.split(
                                    "://", 1
                                )[1]
                            else:
                                self.mapped_address = new_mapped_address

                            # 解析远程端口
                            try:
                                if self.mapped_address and ":" in self.mapped_address:
                                    # 去掉协议前缀
                                    addr_to_parse = self.mapped_address
                                    if "://" in addr_to_parse:
                                        addr_to_parse = addr_to_parse.split("://", 1)[1]

                                    addr_parts = addr_to_parse.split(":")
                                    if len(addr_parts) >= 2:
                                        self.remote_port = int(addr_parts[-1])
                                        print(
                                            f"解析到映射地址: {addr_to_parse}, 远程端口: {self.remote_port}"
                                        )
                            except Exception as e:
                                print(f"解析远程端口出错: {e}")

                            # 发送映射地址变更推送 - 使用消息队列
                            service_name = self.remark or f"服务 {self.service_id}"
                            local_port = self.local_port or "未知"

                            # 仅在非首次获取地址时发送变更消息
                            if old_address != "无":
                                queue_message(
                                    "地址变更",
                                    f"[地址变更] {service_name}",
                                    f"服务映射地址已变更\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n\n旧地址: {old_address}\n新地址: {self.mapped_address}\n变更时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                                )
                            else:
                                # 首次获取地址时发送通知
                                queue_message(
                                    "地址分配",
                                    f"[地址分配] {service_name}",
                                    f"服务获取到映射地址\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n映射地址: {self.mapped_address}\n获取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                                )

                # 检测nftables错误
                if "nftables" in line and "not available" in line:
                    nftables_error_detected = True
                    self.output_lines.append(
                        "⚠️ 检测到nftables不可用错误！Docker容器可能缺少所需权限或内核支持。"
                    )
                    self.output_lines.append(
                        "💡 建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。"
                    )
                    self.output_lines.append(
                        "📋 步骤：停止此服务，重新创建服务并在'转发方法'中选择'socket'或'iptables'。"
                    )

                    # 发送错误推送 - 使用消息队列
                    service_name = self.remark or f"服务 {self.service_id}"
                    queue_message(
                        "错误",
                        f"[错误] {service_name}",
                        f"服务出现错误\n错误类型: nftables不可用\n服务ID: {self.service_id}\n\n建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。\n步骤：停止此服务，重新创建服务并在'转发方法'中选择'socket'或'iptables'。",
                    )

                # 检测pcap初始化错误
                if "pcap initialization failed" in line:
                    self.output_lines.append(
                        "⚠️ 检测到pcap初始化错误！这通常与nftables功能有关。"
                    )
                    self.output_lines.append(
                        "💡 建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。"
                    )

                    # 发送错误推送 - 使用消息队列
                    service_name = self.remark or f"服务 {self.service_id}"
                    queue_message(
                        "错误",
                        f"[错误] {service_name}",
                        f"服务出现错误\n错误类型: pcap初始化失败\n服务ID: {self.service_id}\n\n建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。",
                    )

                # 提取NAT类型
                nat_match = NAT_TYPE_PATTERN.search(line)
                if nat_match:
                    self.nat_type = nat_match.group(1).strip()

                # 提取LAN状态
                lan_match = LAN_STATUS_PATTERN.search(line)
                if lan_match:
                    self.lan_status = lan_match.group(2).strip()

                # 提取WAN状态
                wan_match = WAN_STATUS_PATTERN.search(line)
                if wan_match:
                    self.wan_status = wan_match.group(2).strip()

        except Exception as e:
            print(f"捕获输出时出错: {e}")
            self.output_lines.append(f"输出捕获异常: {str(e)}")
        finally:
            # 确保stdout被正确关闭
            try:
                if self.process and self.process.stdout:
                    self.process.stdout.close()
            except:
                pass

        # 进程结束后更新状态
        self.status = "已停止"

        # 发送服务停止推送 - 使用消息队列
        service_name = self.remark or f"服务 {self.service_id}"
        local_port = self.local_port or "未知"
        mapped_address = self.mapped_address or "无"

        queue_message(
            "停止",
            f"[停止] {service_name}",
            f"服务已停止运行\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n映射地址: {mapped_address}\n停止时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        )

        # 如果启用了自动重启，且不是由于nftables错误导致的退出，则重新启动服务
        if self.auto_restart and not nftables_error_detected:
            # 清理旧的重启线程
            if self.restart_thread and self.restart_thread.is_alive():
                print(f"等待旧的重启线程结束...")
                try:
                    self.restart_thread.join(timeout=2)  # 等待最多2秒
                except:
                    pass

            # 使用新线程进行重启，避免阻塞当前线程
            self.restart_thread = threading.Thread(target=self._restart_service)
            self.restart_thread.daemon = True
            self.restart_thread.start()
        elif nftables_error_detected:
            self.output_lines.append(
                "🔄 因nftables错误，已禁用自动重启。请使用其他转发方法重新配置。"
            )

    def _restart_service(self):
        """自动重启服务"""
        time.sleep(1)  # 等待一秒钟后重启
        self.start()

    def set_auto_restart(self, enabled):
        """设置是否自动重启"""
        self.auto_restart = enabled

    def stop(self):
        """停止Natter服务"""
        if self.process and self.process.poll() is None:
            # 禁用自动重启
            self.auto_restart = False

            # 尝试优雅地终止进程
            try:
                parent = psutil.Process(self.process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()

                # 给进程一些时间来终止
                time.sleep(2)  # 增加等待时间

                # 如果进程仍在运行，强制终止
                if self.process.poll() is None:
                    parent = psutil.Process(self.process.pid)
                    for child in parent.children(recursive=True):
                        try:
                            child.kill()
                        except Exception as e:
                            print(f"强制终止子进程失败: {e}")
                    parent.kill()

                # 再次等待确保进程完全结束
                time.sleep(1)

            except Exception as e:
                print(f"使用psutil终止进程失败: {e}")
                # 如果psutil不可用，使用常规方法
                try:
                    self.process.terminate()
                    time.sleep(2)
                    if self.process.poll() is None:
                        self.process.kill()
                        time.sleep(1)
                except Exception as e2:
                    print(f"常规方法终止进程失败: {e2}")

            # 清理输出流
            try:
                if self.process.stdout:
                    self.process.stdout.close()
            except:
                pass

            # 等待并清理线程
            if self.restart_thread and self.restart_thread.is_alive():
                try:
                    self.restart_thread.join(timeout=2)
                except:
                    pass

            if self.output_thread and self.output_thread.is_alive():
                try:
                    self.output_thread.join(timeout=2)
                except:
                    pass

            self.status = "已停止"

            # 发送手动停止推送 - 使用消息队列
            service_name = self.remark or f"服务 {self.service_id}"
            local_port = self.local_port or "未知"
            mapped_address = self.mapped_address or "无"

            queue_message(
                "手动停止",
                f"[手动停止] {service_name}",
                f"服务已被手动停止\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n映射地址: {mapped_address}\n停止时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            )

            return True
        return False

    def restart(self):
        """重启Natter服务"""
        if self.stop():
            time.sleep(1)  # 等待一秒再启动
            return self.start()
        return False

    def clear_logs(self):
        """清空日志"""
        self.output_lines = []
        return True

    def get_info(self):
        """获取服务信息"""
        running = self.process and self.process.poll() is None
        runtime = time.time() - self.start_time if self.start_time else 0

        return {
            "id": self.service_id,
            "cmd_args": self.cmd_args,
            "running": running,
            "status": self.status,
            "start_time": self.start_time,
            "runtime": runtime,
            "mapped_address": self.mapped_address,
            "last_output": self.output_lines,
            "lan_status": self.lan_status,
            "wan_status": self.wan_status,
            "nat_type": self.nat_type,
            "auto_restart": self.auto_restart,
            "remark": self.remark,
            "local_port": self.local_port,
            "remote_port": self.remote_port,
            "bind_interface": self.bind_interface,
            "bind_port": self.bind_port,
        }

    def to_dict(self):
        """获取服务配置，用于持久化存储"""
        return {
            "id": self.service_id,
            "cmd_args": self.cmd_args,
            "auto_restart": self.auto_restart,
            "created_at": self.start_time or time.time(),
            "remark": self.remark,
        }


def generate_service_id():
    """生成唯一的服务ID"""
    return str(int(time.time() * 1000))


class TemplateManager:
    @staticmethod
    def load_templates():
        """加载所有配置模板"""
        if not os.path.exists(TEMPLATES_FILE):
            return []

        try:
            with open(TEMPLATES_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载模板文件出错: {e}")
            return []

    @staticmethod
    def save_template(name, description, cmd_args):
        """保存新模板"""
        templates = TemplateManager.load_templates()

        # 生成唯一ID
        template_id = generate_service_id()

        # 创建新模板
        new_template = {
            "id": template_id,
            "name": name,
            "description": description,
            "cmd_args": cmd_args,
            "created_at": time.time(),
        }

        # 添加到模板列表
        templates.append(new_template)

        # 保存到文件
        try:
            with open(TEMPLATES_FILE, "w") as f:
                json.dump(templates, f, indent=2)
            return template_id
        except Exception as e:
            print(f"保存模板出错: {e}")
            return None

    @staticmethod
    def delete_template(template_id):
        """删除指定模板"""
        templates = TemplateManager.load_templates()

        # 过滤出除了要删除的模板之外的所有模板
        filtered_templates = [t for t in templates if t.get("id") != template_id]

        # 如果模板数量没变，说明未找到要删除的模板
        if len(templates) == len(filtered_templates):
            return False

        # 保存更新后的模板列表
        try:
            with open(TEMPLATES_FILE, "w") as f:
                json.dump(filtered_templates, f, indent=2)
            return True
        except Exception as e:
            print(f"删除模板出错: {e}")
            return False


class NatterManager:
    @staticmethod
    def start_service(args, auto_restart=False, remark=""):
        """启动一个新的Natter服务"""
        service_id = generate_service_id()

        with service_lock:
            service = NatterService(service_id, args, remark)
            service.set_auto_restart(auto_restart)
            if service.start():
                running_services[service_id] = service
                # 保存服务配置
                NatterManager.save_services()
                return service_id
        return None

    @staticmethod
    def stop_service(service_id):
        """停止指定的Natter服务"""
        with service_lock:
            if service_id in running_services:
                service = running_services[service_id]
                if service.stop():
                    # 保存服务配置（移除服务后）
                    NatterManager.save_services()
                    return True
        return False

    @staticmethod
    def delete_service(service_id):
        """删除指定的Natter服务"""
        with service_lock:
            if service_id in running_services:
                service = running_services[service_id]
                # 确保服务已停止
                service.stop()
                # 从字典中删除服务
                del running_services[service_id]
                # 保存服务配置（移除服务后）
                NatterManager.save_services()
                return True
        return False

    @staticmethod
    def restart_service(service_id):
        """重启指定的Natter服务"""
        with service_lock:
            if service_id in running_services:
                service = running_services[service_id]
                if service.restart():
                    # 保存服务配置（移除服务后）
                    NatterManager.save_services()
                    return True
        return False

    @staticmethod
    def set_auto_restart(service_id, enabled):
        """设置服务自动重启"""
        with service_lock:
            if service_id in running_services:
                service = running_services[service_id]
                service.set_auto_restart(enabled)
                # 保存服务配置
                NatterManager.save_services()
                return True
        return False

    @staticmethod
    def clear_service_logs(service_id):
        """清空服务日志"""
        with service_lock:
            if service_id in running_services:
                service = running_services[service_id]
                return service.clear_logs()
        return False

    @staticmethod
    def get_service(service_id):
        """获取指定服务的信息"""
        with service_lock:
            if service_id in running_services:
                service_info = running_services[service_id].get_info()

                # 添加分组信息（和list_services方法保持一致）
                group_id, group_info = ServiceGroupManager.get_group_by_service(
                    service_id
                )
                service_info["group_id"] = group_id
                service_info["group_name"] = (
                    group_info.get("name") if group_info else "默认分组"
                )

                return service_info
        return None

    @staticmethod
    def list_services():
        """列出所有服务"""
        services = []
        with service_lock:
            for service_id in running_services:
                service_info = running_services[service_id].get_info()

                # 添加分组信息
                group_id, group_info = ServiceGroupManager.get_group_by_service(
                    service_id
                )
                service_info["group_id"] = group_id
                service_info["group_name"] = (
                    group_info.get("name") if group_info else "默认分组"
                )

                services.append(service_info)
        return services

    @staticmethod
    def stop_all_services():
        """停止所有服务"""
        stopped_count = 0
        with service_lock:
            for service_id in list(running_services.keys()):
                if running_services[service_id].stop():
                    stopped_count += 1
        return stopped_count

    @staticmethod
    def save_services():
        """保存当前运行的服务到数据库文件"""
        try:
            with service_lock:
                services_config = {}
                for service_id, service in running_services.items():
                    # 确保获取端口信息
                    if (
                        hasattr(service, "mapped_address")
                        and service.mapped_address
                        and not service.remote_port
                        and ":" in service.mapped_address
                    ):
                        try:
                            addr_parts = service.mapped_address.split(":")
                            if len(addr_parts) >= 2:
                                service.remote_port = int(addr_parts[-1])
                        except:
                            pass

                    # 创建配置对象，只包含一定存在的属性
                    service_data = {
                        "args": service.cmd_args,
                        "status": service.status,
                        "auto_restart": service.auto_restart,
                        "start_time": service.start_time,
                        "remark": service.remark if hasattr(service, "remark") else "",
                    }

                    # 添加可能不存在的属性
                    if (
                        hasattr(service, "local_port")
                        and service.local_port is not None
                    ):
                        service_data["local_port"] = service.local_port

                    if (
                        hasattr(service, "remote_port")
                        and service.remote_port is not None
                    ):
                        service_data["remote_port"] = service.remote_port

                    services_config[service_id] = service_data

            with open(SERVICES_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(services_config, f, indent=2, ensure_ascii=False)
            print(f"服务配置已保存到 {SERVICES_DB_FILE}")
        except Exception as e:
            print(f"保存服务配置失败: {str(e)}")

    @staticmethod
    def load_services():
        """从数据库文件加载服务配置"""
        if not os.path.exists(SERVICES_DB_FILE):
            print(f"服务配置文件不存在: {SERVICES_DB_FILE}")
            return

        try:
            with open(SERVICES_DB_FILE, "r", encoding="utf-8") as f:
                services_config = json.load(f)

            with service_lock:
                for service_id, config in services_config.items():
                    # 检查服务是否已运行
                    if service_id in running_services:
                        continue

                    args = config.get("args")
                    auto_restart = config.get("auto_restart", False)
                    remark = config.get("remark", "")

                    if args:
                        # 创建并启动服务
                        service = NatterService(service_id, args, remark)
                        service.auto_restart = auto_restart

                        # 设置可能存在的端口信息
                        if "local_port" in config:
                            service.local_port = config["local_port"]
                        if "remote_port" in config:
                            service.remote_port = config["remote_port"]

                        if service.start():
                            running_services[service_id] = service
                            print(f"服务 {service_id} 已从配置文件加载并启动")

            print(f"成功从 {SERVICES_DB_FILE} 加载服务配置")
        except Exception as e:
            print(f"加载服务配置失败: {str(e)}")


class NatterHttpHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        # 对JavaScript文件添加缓存控制
        if content_type == "application/javascript":
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

        self.end_headers()

    def _authenticate_token(self):
        """验证token认证"""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # 移除"Bearer "前缀
            if token in auth_tokens:
                # 检查token是否过期
                if time.time() - auth_tokens[token] < AUTH_TOKEN_EXPIRE:
                    return True
                else:
                    # token过期，清理
                    del auth_tokens[token]
        return False

    def _authenticate(self):
        """验证请求中的密码"""
        # 如果未设置密码，则允许所有访问
        if ADMIN_PASSWORD is None:
            return True

        # 检查Authorization头
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            # 解析Basic认证头
            try:
                auth_decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = auth_decoded.split(":", 1)
                # 检查密码是否匹配
                if password == ADMIN_PASSWORD:
                    return True
            except Exception as e:
                print(f"认证解析出错: {e}")

        # Basic认证失败，返回False让token认证有机会执行
        return False

    def _handle_mcp_sse(self, data):
        """处理MCP Server-Sent Events连接"""
        try:
            # 验证认证
            auth_result = self._authenticate_mcp_request(data)
            if not auth_result["success"]:
                self._error(401, auth_result["message"])
                return

            connection_id = auth_result["connection_id"]
            user_role = auth_result["user_role"]

            # 设置SSE响应头
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Cache-Control")
            self.end_headers()

            # 注册SSE连接
            with mcp_connection_lock:
                mcp_connections[connection_id] = {
                    "type": "sse",
                    "handler": self,
                    "created": time.time(),
                    "authenticated": True,
                    "user_role": user_role
                }

            # 发送初始连接成功事件
            self._send_sse_event("connected", {
                "connection_id": connection_id,
                "user_role": user_role,
                "message": "SSE连接建立成功"
            })

            # 订阅所有事件（SSE通常用于接收实时通知）
            with mcp_connection_lock:
                mcp_subscriptions[connection_id] = ["all"]

            print(f"MCP SSE连接建立: {connection_id} ({user_role})")

            # 保持连接活跃
            try:
                while True:
                    # 每30秒发送心跳
                    time.sleep(30)

                    # 检查连接是否仍然存在
                    with mcp_connection_lock:
                        if connection_id not in mcp_connections:
                            break

                    # 发送心跳事件
                    self._send_sse_event("heartbeat", {"timestamp": int(time.time())})

            except Exception as e:
                print(f"SSE连接维护错误 {connection_id}: {e}")

        except Exception as e:
            print(f"SSE连接处理错误: {e}")
            self._error(500, f"SSE connection error: {str(e)}")
        finally:
            # 清理连接
            with mcp_connection_lock:
                mcp_connections.pop(connection_id, None)
                mcp_subscriptions.pop(connection_id, None)

            print(f"MCP SSE连接关闭: {connection_id}")

    def _send_sse_event(self, event_type, data):
        """发送SSE事件"""
        try:
            event_data = f"event: {event_type}\n"
            event_data += f"data: {json.dumps(data)}\n\n"
            self.wfile.write(event_data.encode('utf-8'))
            self.wfile.flush()
        except Exception as e:
            print(f"SSE事件发送失败: {e}")

    def _authenticate_mcp_request(self, data):
        """验证MCP请求的认证信息"""
        try:
            # 检查连接数限制
            with mcp_connection_lock:
                if len(mcp_connections) >= MCP_MAX_CONNECTIONS:
                    return {"success": False, "message": "MCP connection limit exceeded"}

            # 优先检查Authorization头中的token
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                if token in auth_tokens:
                    if time.time() - auth_tokens[token] < AUTH_TOKEN_EXPIRE:
                        return {
                            "success": True,
                            "user_role": "admin",  # token用户默认为admin
                            "connection_id": f"token_{token[:8]}"
                        }
                    else:
                        del auth_tokens[token]

            # 检查Basic认证
            if auth_header.startswith("Basic "):
                try:
                    auth_decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                    username, password = auth_decoded.split(":", 1)

                    if password == ADMIN_PASSWORD:
                        return {
                            "success": True,
                            "user_role": "admin",
                            "connection_id": f"basic_admin_{int(time.time())}"
                        }

                    # 检查是否是访客组密码
                    for group_id, group_info in service_groups.get("groups", {}).items():
                        if group_info.get("password") == password:
                            return {
                                "success": True,
                                "user_role": "guest",
                                "connection_id": f"guest_{group_id}_{int(time.time())}",
                                "group_id": group_id
                            }
                except Exception as e:
                    print(f"MCP认证解析错误: {e}")

            # 检查请求数据中的认证信息
            auth_info = data.get("auth")
            if auth_info:
                password = auth_info.get("password")
                if password == ADMIN_PASSWORD:
                    return {
                        "success": True,
                        "user_role": "admin",
                        "connection_id": f"data_admin_{int(time.time())}"
                    }

                # 检查访客组密码
                for group_id, group_info in service_groups.get("groups", {}).items():
                    if group_info.get("password") == password:
                        return {
                            "success": True,
                            "user_role": "guest",
                            "connection_id": f"data_guest_{group_id}_{int(time.time())}",
                            "group_id": group_id
                        }

            return {"success": False, "message": "Authentication required"}

        except Exception as e:
            print(f"MCP认证处理错误: {e}")
            return {"success": False, "message": "Authentication error"}

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        try:
            # 解析路径和查询参数
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)

            # 如果访问的是版本号API
            if path == "/api/version":
                self._set_headers(200)
                response = {"version": VERSION}
                self.wfile.write(json.dumps(response).encode())
                return

            if path == "/api/mcp/status":
                self._set_headers(200)
                # 构建MCP状态信息
                mcp_status = {
                    "enabled": MCP_ENABLED,
                    "protocols": [],
                    "connections": {
                        "active": len(mcp_connections),
                        "max": MCP_MAX_CONNECTIONS
                    },
                    "tools": {
                        "total": len(MCPToolRegistry._tools) if MCP_ENABLED else 0,
                        "available": list(MCPToolRegistry._tools.keys()) if MCP_ENABLED else []
                    }
                }

                # 添加协议信息
                if MCP_ENABLED:
                    mcp_status["protocols"].append({
                        "name": "HTTP",
                        "enabled": True,
                        "endpoint": "/api/mcp"
                    })

                    if MCP_WEBSOCKET_ENABLED:
                        mcp_status["protocols"].append({
                            "name": "WebSocket",
                            "enabled": True,
                            "port": MCP_WEBSOCKET_PORT,
                            "endpoint": f"ws://localhost:{MCP_WEBSOCKET_PORT}"
                        })

                    if MCP_TCP_ENABLED:
                        mcp_status["protocols"].append({
                            "name": "TCP",
                            "enabled": True,
                            "port": MCP_TCP_PORT,
                            "endpoint": f"tcp://localhost:{MCP_TCP_PORT}"
                        })

                    if MCP_SSE_ENABLED:
                        mcp_status["protocols"].append({
                            "name": "SSE",
                            "enabled": True,
                            "endpoint": "/api/mcp/sse"
                        })

                    if MCP_STDIO_ENABLED:
                        mcp_status["protocols"].append({
                            "name": "stdio",
                            "enabled": True,
                            "endpoint": "stdin/stdout"
                        })

                # 添加连接详情
                with mcp_connection_lock:
                    mcp_status["connection_details"] = []
                    for conn_id, conn_info in mcp_connections.items():
                        mcp_status["connection_details"].append({
                            "id": conn_id,
                            "type": conn_info.get("type", "unknown"),
                            "authenticated": conn_info.get("authenticated", False),
                            "user_role": conn_info.get("user_role"),
                            "created": conn_info.get("created", 0)
                        })

                self.wfile.write(json.dumps(mcp_status).encode())
                return

            # 访客模式API - 不需要管理员认证
            if path == "/api/guest/auth":
                # 访客密码验证
                if "password" in query_params:
                    password = query_params["password"][0]
                    group_id, group = ServiceGroupManager.get_group_by_password(
                        password
                    )
                    if group:
                        self._set_headers()
                        self.wfile.write(
                            json.dumps(
                                {
                                    "success": True,
                                    "group_id": group_id,
                                    "group_name": group["name"],
                                    "group_description": group.get("description", ""),
                                }
                            ).encode()
                        )
                    else:
                        self._error(401, "访客密码错误")
                else:
                    self._error(400, "缺少密码参数")
                return
            elif path == "/api/guest/services":
                # 访客获取服务列表
                if "group_id" in query_params:
                    group_id = query_params["group_id"][0]
                    services = ServiceGroupManager.get_services_by_group(group_id)
                    self._set_headers()
                    self.wfile.write(json.dumps({"services": services}).encode())
                else:
                    self._error(400, "缺少group_id参数")
                return
            elif path == "/api/guest/check":
                # 检查是否有配置的访客组
                self._set_headers()
                groups = ServiceGroupManager.list_groups()
                has_groups = len(groups) > 0
                self.wfile.write(json.dumps({"guest_available": has_groups}).encode())
                return

            # 总是允许访问登录页和静态资源
            if (
                path == "/"
                or path == ""
                or path.endswith(".html")
                or path.endswith(".css")
                or path.endswith(".js")
                or path.endswith(".svg")
                or path.endswith(".png")
                or path.endswith(".jpg")
                or path.endswith(".jpeg")
                or path.endswith(".gif")
                or path.endswith(".ico")
                or path.endswith(".woff")
                or path.endswith(".woff2")
                or path.endswith(".ttf")
                or path.startswith("/mcp_examples/")
                or path.endswith(".md")
                or path.endswith(".py")
            ):
                # 为前端文件提供静态服务
                if path == "/" or path == "":
                    self._serve_file("index.html", "text/html")
                    return
                elif path.endswith(".html"):
                    self._serve_file(path[1:], "text/html")
                    return
                elif path.endswith(".css"):
                    self._serve_file(path[1:], "text/css")
                    return
                elif path.endswith(".js"):
                    self._serve_file(path[1:], "application/javascript")
                    return
                elif path.endswith(".svg"):
                    self._serve_file(path[1:], "image/svg+xml")
                    return
                elif path.endswith(".png"):
                    self._serve_file(path[1:], "image/png")
                    return
                elif path.endswith((".jpg", ".jpeg")):
                    self._serve_file(path[1:], "image/jpeg")
                    return
                elif path.endswith(".gif"):
                    self._serve_file(path[1:], "image/gif")
                    return
                elif path.endswith(".ico"):
                    self._serve_file(path[1:], "image/x-icon")
                    return
                elif path.endswith((".woff", ".woff2")):
                    self._serve_file(path[1:], "font/woff")
                    return
                elif path.endswith(".ttf"):
                    self._serve_file(path[1:], "font/ttf")
                    return
                elif path.startswith("/mcp_examples/"):
                    # 处理MCP示例文档访问
                    if path == "/mcp_examples/" or path == "/mcp_examples":
                        # 重定向到README.md
                        self._serve_file("mcp_examples/README.md", "text/markdown; charset=utf-8")
                        return
                    else:
                        # 提供mcp_examples目录下的文件
                        file_path = path[1:]  # 移除开头的'/'
                        try:
                            with open(
                                os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path), "rb"
                            ) as f:
                                if file_path.endswith('.md'):
                                    content_type = "text/markdown; charset=utf-8"
                                elif file_path.endswith('.py'):
                                    content_type = "text/plain; charset=utf-8"
                                elif file_path.endswith('.json'):
                                    content_type = "application/json; charset=utf-8"
                                else:
                                    content_type = "text/plain; charset=utf-8"

                                self._set_headers(content_type)
                                self.wfile.write(f.read())
                                return
                        except FileNotFoundError:
                            self._error(404, "File not found in mcp_examples")
                            return
                elif path.endswith(".md"):
                    self._serve_file(path[1:], "text/markdown; charset=utf-8")
                    return
                elif path.endswith(".py"):
                    self._serve_file(path[1:], "text/plain; charset=utf-8")
                    return

            # API请求需要验证（排除静态文件和公开路径）
            if (path not in ["/api/auth/login", "/api/auth/unified-login"]
                and not path.startswith("/mcp_examples/")
                and not path.endswith(".md")
                and not path.endswith(".py")):
                if not (self._authenticate() or self._authenticate_token()):
                    # 认证失败，发送401响应
                    self.send_response(401)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(
                            {"error": "需要认证", "auth_required": True}
                        ).encode()
                    )
                    return

            # API端点
            if path == "/api/services":
                self._set_headers()
                services = NatterManager.list_services()
                self.wfile.write(json.dumps({"services": services}).encode())
            elif path == "/api/service":
                if "id" in query_params:
                    service_id = query_params["id"][0]
                    service = NatterManager.get_service(service_id)
                    if service:
                        self._set_headers()
                        self.wfile.write(json.dumps({"service": service}).encode())
                    else:
                        self._error(404, "Service not found")
                else:
                    self._error(400, "Missing service id")
            elif path == "/api/templates":
                self._set_headers()
                templates = TemplateManager.load_templates()
                self.wfile.write(json.dumps({"templates": templates}).encode())
            elif path == "/api/tools/check":
                if "tool" in query_params:
                    tool = query_params["tool"][0]
                    result = self._check_tool_installed(tool)
                    self._set_headers()
                    self.wfile.write(json.dumps(result).encode())
                else:
                    self._error(400, "Missing tool parameter")
            elif path == "/api/auth/check":
                # 检查认证状态
                if self._authenticate_token():
                    self._set_headers()
                    self.wfile.write(
                        json.dumps(
                            {
                                "authenticated": True,
                                "auth_required": ADMIN_PASSWORD is not None,
                            }
                        ).encode()
                    )
                elif ADMIN_PASSWORD is not None:
                    self._set_headers()
                    self.wfile.write(
                        json.dumps(
                            {"authenticated": False, "auth_required": True}
                        ).encode()
                    )
                else:
                    self._set_headers()
                    self.wfile.write(
                        json.dumps(
                            {"authenticated": True, "auth_required": False}
                        ).encode()
                    )
            elif path == "/api/iyuu/config":
                # 获取IYUU配置
                self._set_headers()
                # 去除令牌中间部分，保留安全性
                safe_config = dict(iyuu_config)
                tokens = safe_config.get("tokens", [])
                safe_tokens = []

                for token in tokens:
                    if token and len(token) > 10:
                        # 只显示令牌的前5位和后5位
                        masked_token = token[:5] + "*****" + token[-5:]
                        safe_tokens.append(masked_token)
                    else:
                        safe_tokens.append(token)

                safe_config["tokens"] = safe_tokens
                safe_config["token_count"] = len(tokens)

                self.wfile.write(json.dumps({"config": safe_config}).encode())
            elif path == "/api/iyuu/test":
                # 测试IYUU推送
                # 直接使用_send_iyuu_message_direct函数，跳过消息队列，立即发送
                test_message = f"## 🔔 Natter测试消息 ##\n\n"
                test_message += f"⏰ 发送时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                test_message += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                test_message += f"✅ 通知测试成功\n\n"
                test_message += f"📌 **系统信息**\n"
                test_message += f"➤ 运行环境: {'Docker容器内' if os.path.exists('/.dockerenv') else '主机系统'}\n"
                test_message += f"➤ Python版本: {sys.version.split()[0]}\n"
                test_message += f"➤ 操作系统: {sys.platform}\n\n"

                # 获取所有服务数量
                services_info = NatterManager.list_services()
                running_count = sum(
                    1 for s in services_info if s.get("status") == "运行中"
                )
                stopped_count = sum(
                    1 for s in services_info if s.get("status") == "已停止"
                )

                test_message += f"📌 **服务概况**\n"
                test_message += f"➤ 总服务数: {len(services_info)}\n"
                test_message += f"➤ 🟢 运行中: {running_count}\n"
                test_message += f"➤ ⚪ 已停止: {stopped_count}\n\n"

                test_message += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                test_message += f"💡 IYUU推送功能正常"

                success, errors = _send_iyuu_message_direct(
                    "Natter测试消息", test_message
                )
                self._set_headers()
                self.wfile.write(
                    json.dumps({"success": success, "errors": errors}).encode()
                )
            elif path == "/api/groups":
                # 获取服务组列表
                self._set_headers()

                # 检查是否为已认证用户（包括token和基本认证）
                is_authenticated = self._authenticate() or self._authenticate_token()

                if is_authenticated:
                    # 已认证用户可以看到包含密码的完整分组信息
                    groups = ServiceGroupManager.list_groups()
                else:
                    # 未认证用户只能看到基本分组信息（不含密码）
                    groups = ServiceGroupManager.list_groups_without_password()

                self.wfile.write(json.dumps({"groups": groups}).encode())
            elif path == "/api/groups/services":
                # 根据组ID获取服务列表
                group_id = query_params.get("group_id", [""])[
                    0
                ]  # 默认为空字符串（默认分组）
                services = ServiceGroupManager.get_services_by_group(group_id)
                self._set_headers()
                self.wfile.write(json.dumps({"services": services}).encode())
            elif path == "/api/groups/move-service":
                # 移动服务到指定分组
                if "service_id" in query_params:
                    service_id = query_params["service_id"][0]
                    new_group_id = query_params.get(
                        "group_id", ""
                    )  # 空字符串表示默认分组

                    # 首先从当前分组中移除服务
                    ServiceGroupManager.remove_service_from_all_groups(service_id)

                    # 如果目标分组不是默认分组，则添加到新分组
                    if new_group_id:
                        if ServiceGroupManager.add_service_to_group(
                            new_group_id, service_id
                        ):
                            self._set_headers()
                            self.wfile.write(json.dumps({"success": True}).encode())
                        else:
                            self._error(500, "移动服务到新分组失败")
                    else:
                        # 移动到默认分组，只需要从所有分组中移除即可
                        self._set_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(400, "缺少service_id参数")
            elif path == "/api/groups/batch-move":
                # 批量移动服务
                if (
                    "source_group_id" in query_params
                    and "target_group_id" in query_params
                ):
                    source_group_id = (
                        query_params["source_group_id"][0] or ""
                    )  # 空字符串表示默认分组
                    target_group_id = query_params["target_group_id"][0] or ""

                    # 获取源分组中的所有服务
                    services = ServiceGroupManager.get_services_in_group(
                        source_group_id
                    )
                    moved_count = 0

                    for service in services:
                        service_id = service.get("id")
                        if service_id:
                            # 从源分组中移除
                            if source_group_id:
                                ServiceGroupManager.remove_service_from_group(
                                    source_group_id, service_id
                                )

                            # 添加到目标分组
                            if target_group_id:
                                ServiceGroupManager.add_service_to_group(
                                    target_group_id, service_id
                                )

                            moved_count += 1

                    self._set_headers()
                    self.wfile.write(
                        json.dumps(
                            {"success": True, "moved_count": moved_count}
                        ).encode()
                    )
                else:
                    self._error(400, "缺少必要参数")
            elif path == "/api/auth/unified-login":
                # 统一登录验证API
                password = None

                # 首先尝试从JSON body获取密码（POST请求）
                if self.command == "POST":
                    try:
                        content_length = int(self.headers.get("Content-Length", 0))
                        if content_length > 0:
                            post_data = self.rfile.read(content_length)
                            data = json.loads(post_data.decode("utf-8"))
                            password = data.get("password")
                    except Exception as e:
                        print(f"解析POST数据出错: {e}")

                # 如果POST没有获取到密码，尝试从查询参数获取（GET请求）
                if not password and "password" in query_params:
                    password = query_params["password"][0]

                if password:
                    # 首先检查是否是管理员密码
                    if ADMIN_PASSWORD and password == ADMIN_PASSWORD:
                        # 管理员登录
                        token = secrets.token_urlsafe(32)
                        auth_tokens[token] = time.time()
                        self._set_headers()
                        self.wfile.write(
                            json.dumps(
                                {"success": True, "user_type": "admin", "token": token}
                            ).encode()
                        )
                        return

                    # 检查是否是访客组密码
                    group_id, group = ServiceGroupManager.get_group_by_password(
                        password
                    )
                    if group:
                        # 访客登录
                        self._set_headers()
                        self.wfile.write(
                            json.dumps(
                                {
                                    "success": True,
                                    "user_type": "guest",
                                    "group_id": group_id,
                                    "group_name": group["name"],
                                    "group_description": group.get("description", ""),
                                }
                            ).encode()
                        )
                        return

                    # 密码不匹配
                    self._error(401, "密码错误")
                else:
                    self._error(400, "缺少密码参数")
            else:
                self._error(404, "Not found")
        except Exception as e:
            self._error(500, f"服务器内部错误: {e}")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # API请求需要验证，除了登录相关API
        if path not in ["/api/auth/login", "/api/auth/unified-login"]:
            if not (self._authenticate() or self._authenticate_token()):
                # 认证失败，发送401响应
                self.send_response(401)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"error": "需要认证", "auth_required": True}).encode()
                )
                return

        # 读取请求体
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(post_data)
        except:
            self._error(400, "Invalid JSON")
            return

        # 密码验证API
        if path == "/api/auth/login":
            if "password" in data:
                if data["password"] == ADMIN_PASSWORD:
                    # 生成新的Bearer token并存储在auth_tokens中
                    token = secrets.token_urlsafe(32)
                    auth_tokens[token] = time.time()

                    self._set_headers()
                    # 为了向后兼容，同时返回Bearer token和旧的base64 token
                    auth_string = f"user:{ADMIN_PASSWORD}"
                    auth_token_legacy = base64.b64encode(auth_string.encode()).decode()

                    self.wfile.write(
                        json.dumps(
                            {
                                "success": True,
                                "token": token,  # 新的Bearer token
                                "legacy_token": auth_token_legacy,  # 旧的base64 token（向后兼容）
                            }
                        ).encode()
                    )
                else:
                    self._error(401, "密码错误")
            else:
                self._error(400, "缺少密码参数")
            return

        # 统一登录验证API（POST版本）
        elif path == "/api/auth/unified-login":
            if "password" in data:
                password = data["password"]

                # 首先检查是否是管理员密码
                if ADMIN_PASSWORD and password == ADMIN_PASSWORD:
                    # 管理员登录
                    token = secrets.token_urlsafe(32)
                    auth_tokens[token] = time.time()
                    self._set_headers()
                    self.wfile.write(
                        json.dumps(
                            {"success": True, "user_type": "admin", "token": token}
                        ).encode()
                    )
                    return

                # 检查是否是访客组密码
                group_id, group = ServiceGroupManager.get_group_by_password(password)
                if group:
                    # 访客登录
                    self._set_headers()
                    self.wfile.write(
                        json.dumps(
                            {
                                "success": True,
                                "user_type": "guest",
                                "group_id": group_id,
                                "group_name": group["name"],
                                "group_description": group.get("description", ""),
                            }
                        ).encode()
                    )
                    return

                # 密码不匹配
                self._error(401, "密码错误")
            else:
                self._error(400, "缺少密码参数")
            return

        if path == "/api/services/start":
            if "args" in data:
                args = data["args"]
                auto_restart = data.get("auto_restart", False)
                remark = data.get("remark", "")
                group_id = data.get("group_id", "")  # 获取分组ID

                service_id = NatterManager.start_service(args, auto_restart, remark)
                if service_id:
                    # 如果指定了分组，将服务添加到该分组
                    if group_id:
                        ServiceGroupManager.add_service_to_group(group_id, service_id)

                    self._set_headers()
                    self.wfile.write(json.dumps({"service_id": service_id}).encode())
                else:
                    self._error(500, "Failed to start service")
            else:
                self._error(400, "Missing args")
        elif path == "/api/tools/install":
            if "tool" in data:
                tool = data["tool"]
                result = self._install_tool(tool)
                self._set_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self._error(400, "Missing tool parameter")
        elif path == "/api/services/stop":
            if "id" in data:
                service_id = data["id"]
                if NatterManager.stop_service(service_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "Failed to stop service")
            else:
                self._error(400, "Missing service id")
        elif path == "/api/services/delete":
            if "id" in data:
                service_id = data["id"]
                if NatterManager.delete_service(service_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "Failed to delete service")
            else:
                self._error(400, "Missing service id")
        elif path == "/api/services/restart":
            if "id" in data:
                service_id = data["id"]
                if NatterManager.restart_service(service_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "Failed to restart service")
            else:
                self._error(400, "Missing service id")
        elif path == "/api/services/stop-all":
            count = NatterManager.stop_all_services()
            self._set_headers()
            self.wfile.write(
                json.dumps({"success": True, "stopped_count": count}).encode()
            )
        elif path == "/api/services/auto-restart":
            if "id" in data and "enabled" in data:
                service_id = data["id"]
                enabled = data["enabled"]
                if NatterManager.set_auto_restart(service_id, enabled):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "Failed to set auto-restart")
            else:
                self._error(400, "Missing parameters")
        elif path == "/api/services/clear-logs":
            if "id" in data:
                service_id = data["id"]
                if NatterManager.clear_service_logs(service_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "Failed to clear logs")
            else:
                self._error(400, "Missing service id")
        elif path == "/api/templates/save":
            if "name" in data and "cmd_args" in data:
                name = data["name"]
                description = data.get("description", "")
                cmd_args = data["cmd_args"]
                template_id = TemplateManager.save_template(name, description, cmd_args)
                if template_id:
                    self._set_headers()
                    self.wfile.write(json.dumps({"template_id": template_id}).encode())
                else:
                    self._error(500, "Failed to save template")
            else:
                self._error(400, "Missing required parameters")
        elif path == "/api/templates/delete":
            if "id" in data:
                template_id = data["id"]
                if TemplateManager.delete_template(template_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "Failed to delete template")
            else:
                self._error(400, "Missing template id")
        elif path == "/api/services/set-remark":
            if "id" in data and "remark" in data:
                service_id = data["id"]
                remark = data["remark"]
                with service_lock:
                    if service_id in running_services:
                        service = running_services[service_id]
                        service.remark = remark
                        NatterManager.save_services()
                        self._set_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                    else:
                        self._error(404, "Service not found")
            else:
                self._error(400, "Missing id or remark parameter")
        elif path == "/api/iyuu/update":
            # 更新IYUU配置
            global iyuu_config
            try:
                if "enabled" in data:
                    iyuu_config["enabled"] = bool(data["enabled"])

                if "tokens" in data and isinstance(data["tokens"], list):
                    # 检查是否有令牌变更
                    new_tokens = data["tokens"]
                    # 检查令牌是否被加了星号掩码
                    clean_tokens = []
                    for token in new_tokens:
                        if token and "*" in token and len(token) > 10:
                            # 这是一个被掩码的令牌，保留原令牌
                            matching_tokens = [
                                t
                                for t in iyuu_config.get("tokens", [])
                                if t.startswith(token[:5]) and t.endswith(token[-5:])
                            ]
                            if matching_tokens:
                                clean_tokens.append(matching_tokens[0])
                        else:
                            # 这是一个新令牌
                            clean_tokens.append(token)

                    iyuu_config["tokens"] = clean_tokens

                if "schedule" in data and isinstance(data["schedule"], dict):
                    schedule = data["schedule"]
                    if "enabled" in schedule:
                        iyuu_config["schedule"]["enabled"] = bool(schedule["enabled"])
                    if "times" in schedule:
                        iyuu_config["schedule"]["times"] = schedule["times"]
                    if "message" in schedule:
                        iyuu_config["schedule"]["message"] = schedule["message"]

                # 保存配置到文件
                save_result = save_iyuu_config()

                # 如果定时推送设置变更，重新设置定时任务
                if "schedule" in data:
                    schedule_daily_notification()

                self._set_headers()
                self.wfile.write(
                    json.dumps({"success": save_result, "config": iyuu_config}).encode()
                )
            except Exception as e:
                self._error(500, f"更新IYUU配置失败: {e}")
        elif path == "/api/iyuu/add_token":
            # 添加新的IYUU令牌
            if (
                "token" in data
                and isinstance(data["token"], str)
                and data["token"].strip()
            ):
                token = data["token"].strip()

                # 验证令牌是否有效
                test_url = f"https://iyuu.cn/{token}.send"
                try:
                    test_payload = {
                        "text": "Natter令牌验证",
                        "desp": "这是一条验证IYUU令牌有效性的测试消息",
                    }
                    headers = {"Content-Type": "application/json; charset=UTF-8"}

                    response = requests.post(
                        test_url, json=test_payload, headers=headers, timeout=10
                    )

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("errcode") == 0:
                            # 令牌有效，添加到配置
                            if token not in iyuu_config.get("tokens", []):
                                iyuu_config.setdefault("tokens", []).append(token)
                                save_iyuu_config()

                            self._set_headers()
                            self.wfile.write(
                                json.dumps(
                                    {"success": True, "message": "令牌已添加并验证成功"}
                                ).encode()
                            )
                        else:
                            self._error(
                                400, f"令牌验证失败: {result.get('errmsg', '未知错误')}"
                            )
                    else:
                        self._error(
                            400, f"令牌验证失败: HTTP错误 {response.status_code}"
                        )
                except Exception as e:
                    self._error(500, f"令牌验证过程出错: {e}")
            else:
                self._error(400, "缺少有效的token参数")
        elif path == "/api/iyuu/delete_token":
            # 删除IYUU令牌
            if "token" in data and isinstance(data["token"], str):
                token = data["token"]

                # 如果是加星号的格式，查找匹配的令牌
                if "*" in token and len(token) > 10:
                    original_tokens = iyuu_config.get("tokens", [])
                    matched_tokens = [
                        t
                        for t in original_tokens
                        if t.startswith(token[:5]) and t.endswith(token[-5:])
                    ]

                    if matched_tokens:
                        iyuu_config["tokens"] = [
                            t for t in original_tokens if t not in matched_tokens
                        ]
                        save_iyuu_config()

                        self._set_headers()
                        self.wfile.write(
                            json.dumps(
                                {"success": True, "message": "令牌已删除"}
                            ).encode()
                        )
                    else:
                        self._error(404, "未找到匹配的令牌")
                else:
                    # 直接匹配完整令牌
                    if token in iyuu_config.get("tokens", []):
                        iyuu_config["tokens"].remove(token)
                        save_iyuu_config()

                        self._set_headers()
                        self.wfile.write(
                            json.dumps(
                                {"success": True, "message": "令牌已删除"}
                            ).encode()
                        )
                    else:
                        self._error(404, "未找到指定令牌")
            else:
                self._error(400, "缺少token参数")
        elif path == "/api/iyuu/push_now":
            # 立即推送当前服务状态
            try:
                service_id = None
                if "service_id" in data:
                    service_id = data["service_id"]

                # 获取服务状态
                services_info = []
                if service_id:
                    # 只推送指定服务
                    service = NatterManager.get_service(service_id)
                    if service:
                        services_info = [service]
                    else:
                        self._error(404, "未找到指定服务")
                        return
                else:
                    # 推送所有服务
                    services_info = NatterManager.list_services()

                # 生成推送内容
                running_count = sum(
                    1 for s in services_info if s.get("status") == "运行中"
                )
                stopped_count = sum(
                    1 for s in services_info if s.get("status") == "已停止"
                )

                message = "Natter服务状态即时报告"
                detail = f"## 📊 Natter服务状态报告 ##\n\n"
                detail += f"⏰ 报告时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                detail += f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                detail += f"📌 **服务概况**\n"
                detail += f"➤ 总服务数: {len(services_info)}\n"
                detail += f"➤ 🟢 运行中: {running_count}\n"
                detail += f"➤ ⚪ 已停止: {stopped_count}\n\n"

                if services_info:
                    detail += f"📌 **服务详情**\n"
                    for service in services_info:
                        service_id = service.get("id", "未知")
                        remark = service.get("remark") or f"服务 {service_id}"
                        status = service.get("status", "未知")
                        mapped_address = service.get("mapped_address", "无映射")
                        lan_status = service.get("lan_status", "未知")
                        wan_status = service.get("wan_status", "未知")
                        nat_type = service.get("nat_type", "未知")

                        # 根据状态添加emoji
                        status_emoji = "🟢" if status == "运行中" else "⚪"

                        detail += f"{status_emoji} **{remark}**\n"
                        detail += f"  ├─ 状态: {status}\n"
                        detail += f"  ├─ 映射: `{mapped_address}`\n"
                        detail += f"  ├─ LAN状态: {lan_status}\n"
                        detail += f"  ├─ WAN状态: {wan_status}\n"
                        detail += f"  └─ NAT类型: {nat_type}\n\n"
                else:
                    detail += "❗ 当前无服务运行\n\n"

                detail += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                detail += f"💡 通过Natter管理界面可以管理服务"

                # 发送推送
                success, errors = _send_iyuu_message_direct(message, detail)

                self._set_headers()
                self.wfile.write(
                    json.dumps({"success": success, "errors": errors}).encode()
                )
            except Exception as e:
                self._error(500, f"推送服务状态失败: {e}")
        elif path == "/api/groups/create":
            # 创建服务组
            if "name" in data and "password" in data:
                name = data["name"]
                password = data["password"]
                description = data.get("description", "")
                group_id = ServiceGroupManager.create_group(name, password, description)
                if group_id:
                    self._set_headers()
                    self.wfile.write(json.dumps({"group_id": group_id}).encode())
                else:
                    self._error(500, "创建服务组失败")
            else:
                self._error(400, "缺少必要参数")
        elif path == "/api/groups/update":
            # 更新服务组
            if "group_id" in data:
                group_id = data["group_id"]
                name = data.get("name")
                password = data.get("password")
                description = data.get("description")
                if ServiceGroupManager.update_group(
                    group_id, name, password, description
                ):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "更新服务组失败")
            else:
                self._error(400, "缺少group_id参数")
        elif path == "/api/groups/delete":
            # 删除服务组
            if "group_id" in data:
                group_id = data["group_id"]
                if ServiceGroupManager.delete_group(group_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "删除服务组失败")
            else:
                self._error(400, "缺少group_id参数")
        elif path == "/api/groups/add-service":
            # 将服务添加到组
            if "group_id" in data and "service_id" in data:
                group_id = data["group_id"]
                service_id = data["service_id"]
                if ServiceGroupManager.add_service_to_group(group_id, service_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "添加服务到组失败")
            else:
                self._error(400, "缺少必要参数")
        elif path == "/api/groups/remove-service":
            # 从组中移除服务
            if "group_id" in data and "service_id" in data:
                group_id = data["group_id"]
                service_id = data["service_id"]
                if ServiceGroupManager.remove_service_from_group(group_id, service_id):
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                else:
                    self._error(500, "从组中移除服务失败")
            else:
                self._error(400, "缺少必要参数")
        elif path == "/api/groups/move-service":
            # 移动服务到指定分组
            if "service_id" in data:
                service_id = data["service_id"]
                new_group_id = data.get("group_id", "")  # 空字符串表示默认分组

                # 首先从当前分组中移除服务
                ServiceGroupManager.remove_service_from_all_groups(service_id)

                # 如果目标分组不是默认分组，则添加到新分组
                if new_group_id:
                    if ServiceGroupManager.add_service_to_group(
                        new_group_id, service_id
                    ):
                        self._set_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                    else:
                        self._error(500, "移动服务到新分组失败")
                else:
                    # 移动到默认分组，只需要从所有分组中移除即可
                    self._set_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self._error(400, "缺少service_id参数")
        elif path == "/api/groups/batch-move":
            # 批量移动服务
            if "source_group_id" in data and "target_group_id" in data:
                source_group_id = data.get(
                    "source_group_id", ""
                )  # 空字符串表示默认分组
                target_group_id = data.get("target_group_id", "")

                # 获取源分组中的所有服务
                services = ServiceGroupManager.get_services_in_group(source_group_id)
                moved_count = 0

                for service in services:
                    service_id = service.get("id")
                    if service_id:
                        # 从源分组中移除
                        if source_group_id:
                            ServiceGroupManager.remove_service_from_group(
                                source_group_id, service_id
                            )
                        else:
                            # 从默认分组移动，需要先从所有分组中移除
                            ServiceGroupManager.remove_service_from_all_groups(
                                service_id
                            )

                        # 添加到目标分组
                        if target_group_id:
                            ServiceGroupManager.add_service_to_group(
                                target_group_id, service_id
                            )

                        moved_count += 1

                self._set_headers()
                self.wfile.write(
                    json.dumps({"success": True, "moved_count": moved_count}).encode()
                )
            else:
                self._error(400, "缺少必要参数")
        elif path == "/api/mcp":
            # MCP协议端点处理
            if not MCP_ENABLED:
                self._error(503, "MCP service is disabled")
                return

            try:
                # 验证认证
                auth_result = self._authenticate_mcp_request(data)
                if not auth_result["success"]:
                    self._error(401, auth_result["message"])
                    return

                user_role = auth_result["user_role"]
                connection_id = auth_result.get("connection_id", f"conn_{int(time.time())}")

                # 如果是认证请求，处理认证逻辑
                if "authenticate" in data:
                    # 更新连接信息中的认证状态
                    with mcp_connection_lock:
                        if connection_id in mcp_connections:
                            mcp_connections[connection_id]["authenticated"] = True
                            mcp_connections[connection_id]["user_role"] = user_role

                    self._set_headers()
                    self.wfile.write(json.dumps({
                        "success": True,
                        "user_role": user_role,
                        "connection_id": connection_id
                    }).encode())
                    return

                # 处理MCP协议消息
                mcp_message = data.get("message")
                if not mcp_message:
                    self._error(400, "Missing MCP message")
                    return

                # 创建MCP协议处理器并处理消息
                mcp_protocol = MCPProtocol()
                response = mcp_protocol.handle_message(mcp_message, connection_id)

                if response:
                    self._set_headers()
                    self.wfile.write(json.dumps(response).encode())
                else:
                    # 某些通知消息可能不需要响应
                    self._set_headers()
                    self.wfile.write(json.dumps({"acknowledged": True}).encode())

            except Exception as e:
                print(f"MCP端点处理错误: {e}")
                self._error(500, f"MCP processing error: {str(e)}")
        elif path == "/api/mcp/sse":
            # MCP Server-Sent Events端点
            if not MCP_ENABLED or not MCP_SSE_ENABLED:
                self._error(503, "MCP SSE service is disabled")
                return

            self._handle_mcp_sse(data)
        elif path.startswith("/mcp_examples/"):
            # 处理MCP示例文档访问
            if path == "/mcp_examples/" or path == "/mcp_examples":
                # 重定向到README.md
                self._serve_file("mcp_examples/README.md", "text/markdown")
            else:
                # 提供mcp_examples目录下的文件
                file_path = path[1:]  # 移除开头的'/'
                try:
                    with open(
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), file_path), "rb"
                    ) as f:
                        if file_path.endswith('.md'):
                            content_type = "text/markdown"
                        elif file_path.endswith('.py'):
                            content_type = "text/plain"
                        elif file_path.endswith('.json'):
                            content_type = "application/json"
                        else:
                            content_type = "text/plain"

                        self._set_headers(content_type)
                        self.wfile.write(f.read())
                except FileNotFoundError:
                    self._error(404, "File not found in mcp_examples")
        else:
            # 尝试提供其他静态文件
            if path == "/":
                # 主页面
                self._serve_file("index.html", "text/html")
            elif path == "/login.html":
                self._serve_file("login.html", "text/html")
            elif path == "/guest.html":
                self._serve_file("guest.html", "text/html")
            elif path == "/script.js":
                self._serve_file("script.js", "application/javascript")
            elif path == "/style.css":
                self._serve_file("style.css", "text/css")
            elif path == "/await-logo.svg":
                self._serve_file("await-logo.svg", "image/svg+xml")
            elif path == "/favicon.svg":
                self._serve_file("favicon.svg", "image/svg+xml")
            else:
                self._error(404, "Not found")

    def _serve_file(self, filename, content_type):
        """提供静态文件服务"""
        try:
            with open(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), "rb"
            ) as f:
                self._set_headers(content_type)
                self.wfile.write(f.read())
        except FileNotFoundError:
            self._error(404, "File not found")

    def _error(self, code, message):
        """返回错误响应"""
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def _install_tool(self, tool):
        """安装指定的工具"""
        try:
            if tool == "socat":
                # 安装socat
                subprocess.run(["apt-get", "update"], check=True)
                result = subprocess.run(
                    ["apt-get", "install", "-y", "socat"],
                    capture_output=True,
                    text=True,
                )
                success = result.returncode == 0
                return {
                    "success": success,
                    "message": (
                        "socat安装成功" if success else f"安装失败: {result.stderr}"
                    ),
                }
            elif tool == "gost":
                # 安装gost
                result = subprocess.run(
                    [
                        "bash",
                        "-c",
                        "wget -qO- https://github.com/ginuerzh/gost/releases/download/v2.11.2/gost-linux-amd64-2.11.2.gz | gunzip > /usr/local/bin/gost && chmod +x /usr/local/bin/gost",
                    ],
                    capture_output=True,
                    text=True,
                )
                success = result.returncode == 0
                return {
                    "success": success,
                    "message": (
                        "gost安装成功" if success else f"安装失败: {result.stderr}"
                    ),
                }
            else:
                return {"success": False, "message": f"未知工具: {tool}"}
        except Exception as e:
            return {"success": False, "message": f"安装过程出错: {str(e)}"}

    def _check_tool_installed(self, tool):
        """检查指定的工具是否已安装"""
        try:
            if tool == "socat":
                # 检查socat是否已安装
                result = subprocess.run(
                    ["which", "socat"], capture_output=True, text=True
                )
                installed = result.returncode == 0
                return {"installed": installed}
            elif tool == "gost":
                # 检查gost是否已安装
                result = subprocess.run(
                    ["which", "gost"], capture_output=True, text=True
                )
                installed = result.returncode == 0
                return {"installed": installed}
            else:
                return {"installed": False, "error": f"未知工具: {tool}"}
        except Exception as e:
            return {"installed": False, "error": f"检查过程出错: {str(e)}"}


def get_free_port():
    """获取可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def run_server(port=8080):
    """运行Web服务器"""
    # 不再需要设置全局PASSWORD变量，直接使用ADMIN_PASSWORD

    try:
        # 在Docker环境中自动安装nftables和gost
        if os.path.exists("/.dockerenv"):
            print("检测到Docker环境，正在自动安装需要的工具...")
            try:
                # 尝试安装nftables
                subprocess.run(["apt-get", "update"], check=False)
                subprocess.run(["apt-get", "install", "-y", "nftables"], check=False)
                print("nftables安装完成")

                # 尝试安装gost
                subprocess.run(
                    [
                        "bash",
                        "-c",
                        "wget -qO- https://github.com/ginuerzh/gost/releases/download/v2.11.2/gost-linux-amd64-2.11.2.gz | gunzip > /usr/local/bin/gost && chmod +x /usr/local/bin/gost",
                    ],
                    check=False,
                )
                print("gost安装完成")
            except Exception as e:
                print(f"工具安装过程出错: {e}")

        # 加载IYUU配置
        print("加载IYUU推送配置...")
        load_iyuu_config()

        # 如果启用了定时推送，启动定时任务
        if iyuu_config.get("schedule", {}).get("enabled", False):
            print(
                f"启用IYUU定时推送，每天 {iyuu_config.get('schedule', {}).get('times', ['08:00'])} 发送服务状态摘要"
            )
            schedule_daily_notification()

        server_address = (
            "0.0.0.0",
            port,
        )  # 修改为明确绑定0.0.0.0，确保监听所有网络接口
        httpd = HTTPServer(server_address, NatterHttpHandler)
        print(f"Natter管理界面已启动: http://0.0.0.0:{port}")
        print(f"使用的Natter路径: {NATTER_PATH}")
        print(f"数据存储目录: {DATA_DIR}")

        if ADMIN_PASSWORD:
            print("已启用密码保护")
        else:
            print("未设置密码，所有人均可访问")

        # 加载已保存的服务配置
        NatterManager.load_services()

        # 整合发送服务器启动通知和服务映射信息
        if iyuu_config.get("enabled", True) and iyuu_config.get("tokens"):
            services = NatterManager.list_services()
            services_count = len(services)

            # 构建启动消息
            message_title = "Natter管理服务已启动"
            message_content = f"【Natter管理服务启动通知】\n\n"
            message_content += f"📅 启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message_content += f"🔗 服务地址: http://0.0.0.0:{port}\n"
            message_content += f"📊 服务数量: {services_count}\n"
            message_content += f"📨 IYUU推送: {'已启用' if iyuu_config.get('enabled', True) else '已禁用'}\n"
            message_content += f"⏰ 定时推送: {'已启用' if iyuu_config.get('schedule', {}).get('enabled', False) else '已禁用'}\n\n"

            # 添加服务映射地址部分
            if services_count > 0:
                message_content += "## 已加载服务映射地址\n"
                running_count = 0
                for service in services:
                    service_id = service.get("id", "未知")
                    remark = service.get("remark") or f"服务 {service_id}"
                    status = service.get("status", "未知")
                    mapped_address = service.get("mapped_address", "无映射")
                    running = service.get("running", False)

                    # 服务状态图标
                    status_icon = "🟢" if running else "⚪"
                    if running:
                        running_count += 1

                    # 添加服务信息
                    if (
                        mapped_address
                        and mapped_address != "无"
                        and mapped_address != "无映射"
                    ):
                        message_content += (
                            f"{status_icon} {remark}: `{mapped_address}`\n"
                        )
                    else:
                        message_content += f"{status_icon} {remark}: 等待分配映射地址\n"

                message_content += (
                    f"\n共 {services_count} 个服务，{running_count} 个运行中"
                )
            else:
                message_content += "暂无加载的服务\n"

            # 直接发送整合消息，不经过队列
            _send_iyuu_message_direct(message_title, message_content)
            print("已发送启动通知和服务信息")

        httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"端口 {port} 已被占用，尝试其他端口...")
            new_port = get_free_port()
            run_server(new_port)
        else:
            print(f"启动服务器时发生错误: {e}")
            raise
    except Exception as e:
        print(f"启动服务器时发生未知错误: {e}")
        raise


def cleanup():
    """清理资源，停止所有运行中的服务"""
    print("正在停止所有Natter服务...")
    stopped_count = NatterManager.stop_all_services()

    # 确保所有待发消息都已发送
    with message_lock:
        if len(message_queue) > 0:
            # 强制直接发送所有剩余消息，不进队列
            _send_iyuu_message_direct(
                "Natter服务状态更新 [关闭前最后通知]",
                f"【服务关闭前最后通知】\n\n"
                f"- 停止时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- 已停止服务数: {stopped_count}\n\n"
                f"服务器即将关闭，所有运行中的服务已停止。",
            )
            message_queue.clear()

    print(f"已停止 {stopped_count} 个服务")


# 添加IYUU消息推送相关函数
def load_iyuu_config():
    """加载IYUU配置"""
    global iyuu_config
    try:
        if os.path.exists(IYUU_CONFIG_FILE):
            with open(IYUU_CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
                iyuu_config.update(loaded_config)
    except Exception as e:
        print(f"加载IYUU配置失败: {e}")
        # 确保写入默认配置
        save_iyuu_config()


def save_iyuu_config():
    """保存IYUU配置"""
    try:
        with open(IYUU_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(iyuu_config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存IYUU配置失败: {e}")
        return False


# MCP服务管理工具类
class MCPServiceTools:
    """MCP服务管理相关工具实现"""

    @staticmethod
    def initialize():
        """注册所有服务管理工具"""
        # 注册服务列表工具
        MCPToolRegistry.register_tool(
            name="natter/list_services",
            description="获取当前所有Natter服务的列表和状态信息",
            input_schema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "enum": ["all", "running", "stopped"],
                        "description": "过滤服务状态",
                        "default": "all"
                    },
                    "group": {
                        "type": "string",
                        "description": "服务组过滤（仅访客用户需要）"
                    }
                }
            },
            handler=MCPServiceTools._handle_list_services,
            required_role="guest"
        )

        # 注册服务状态查询工具
        MCPToolRegistry.register_tool(
            name="natter/get_service_status",
            description="获取指定服务的详细状态信息",
            input_schema={
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "服务ID"
                    }
                },
                "required": ["service_id"]
            },
            handler=MCPServiceTools._handle_get_service_status,
            required_role="guest"
        )

        # 注册启动服务工具
        MCPToolRegistry.register_tool(
            name="natter/start_service",
            description="启动一个新的Natter服务",
            input_schema={
                "type": "object",
                "properties": {
                    "local_port": {
                        "type": "integer",
                        "description": "本地端口号"
                    },
                    "keep_alive": {
                        "type": "integer",
                        "description": "保持连接时间（秒）",
                        "default": 30
                    },
                    "remark": {
                        "type": "string",
                        "description": "服务备注"
                    }
                },
                "required": ["local_port"]
            },
            handler=MCPServiceTools._handle_start_service,
            required_role="admin"
        )

        # 注册停止服务工具
        MCPToolRegistry.register_tool(
            name="natter/stop_service",
            description="停止指定的Natter服务",
            input_schema={
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "要停止的服务ID"
                    }
                },
                "required": ["service_id"]
            },
            handler=MCPServiceTools._handle_stop_service,
            required_role="admin"
        )

        # 注册重启服务工具
        MCPToolRegistry.register_tool(
            name="natter/restart_service",
            description="重启指定的Natter服务",
            input_schema={
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "要重启的服务ID"
                    }
                },
                "required": ["service_id"]
            },
            handler=MCPServiceTools._handle_restart_service,
            required_role="admin"
        )

        print("MCP服务管理工具已注册")

    @staticmethod
    def _handle_list_services(arguments, user_role, connection_id):
        """处理服务列表请求"""
        try:
            filter_type = arguments.get("filter", "all")
            group_filter = arguments.get("group")

            with service_lock:
                services_list = []
                for service_id, service in running_services.items():
                    # 获取服务状态
                    status_info = service.get_status()

                    # 应用状态过滤
                    if filter_type == "running" and not status_info.get("is_running", False):
                        continue
                    elif filter_type == "stopped" and status_info.get("is_running", False):
                        continue

                    # 应用组过滤（访客用户）
                    if user_role == "guest" and group_filter:
                        # 这里可以集成ServiceGroupManager的权限检查
                        # 暂时简化处理
                        pass

                    service_info = {
                        "id": service_id,
                        "status": "running" if status_info.get("is_running") else "stopped",
                        "mapped_address": status_info.get("mapped_address", ""),
                        "local_port": status_info.get("local_port", 0),
                        "remark": status_info.get("remark", ""),
                        "start_time": status_info.get("start_time", ""),
                        "cpu_percent": status_info.get("cpu_percent", 0),
                        "memory_mb": status_info.get("memory_mb", 0)
                    }
                    services_list.append(service_info)

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"找到 {len(services_list)} 个服务:\n" +
                                   "\n".join([f"- {s['id']}: {s['status']} ({s['mapped_address']})"
                                            for s in services_list])
                        }
                    ],
                    "services": services_list
                }

        except Exception as e:
            raise Exception(f"获取服务列表失败: {str(e)}")

    @staticmethod
    def _handle_get_service_status(arguments, user_role, connection_id):
        """处理服务状态查询请求"""
        try:
            service_id = arguments.get("service_id")
            if not service_id:
                raise Exception("服务ID不能为空")

            with service_lock:
                service = running_services.get(service_id)
                if not service:
                    raise Exception(f"服务 {service_id} 不存在")

                status_info = service.get_status()

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"服务 {service_id} 状态信息:\n" +
                                   f"状态: {('运行中' if status_info.get('is_running') else '已停止')}\n" +
                                   f"映射地址: {status_info.get('mapped_address', '无')}\n" +
                                   f"本地端口: {status_info.get('local_port', 0)}\n" +
                                   f"CPU使用率: {status_info.get('cpu_percent', 0):.1f}%\n" +
                                   f"内存使用: {status_info.get('memory_mb', 0):.1f}MB"
                        }
                    ],
                    "service_status": status_info
                }

        except Exception as e:
            raise Exception(f"获取服务状态失败: {str(e)}")

    @staticmethod
    def _handle_start_service(arguments, user_role, connection_id):
        """处理启动服务请求"""
        try:
            local_port = arguments.get("local_port")
            keep_alive = arguments.get("keep_alive", 30)
            remark = arguments.get("remark", "")

            if not local_port:
                raise Exception("本地端口号不能为空")

            # 构建启动参数
            cmd_args = ["-k", str(keep_alive), "-p", str(local_port)]

            # 生成服务ID
            service_id = f"service_{local_port}_{int(time.time())}"

            # 创建并启动服务
            service = NatterService(service_id, cmd_args, remark)

            with service_lock:
                running_services[service_id] = service

            # 启动服务
            result = service.start()

            if result.get("success", False):
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"服务 {service_id} 启动成功\n" +
                                   f"本地端口: {local_port}\n" +
                                   f"保持连接: {keep_alive}秒"
                        }
                    ],
                    "service_id": service_id,
                    "result": result
                }
            else:
                raise Exception(result.get("message", "启动失败"))

        except Exception as e:
            raise Exception(f"启动服务失败: {str(e)}")

    @staticmethod
    def _handle_stop_service(arguments, user_role, connection_id):
        """处理停止服务请求"""
        try:
            service_id = arguments.get("service_id")
            if not service_id:
                raise Exception("服务ID不能为空")

            with service_lock:
                service = running_services.get(service_id)
                if not service:
                    raise Exception(f"服务 {service_id} 不存在")

                # 停止服务
                result = service.stop()

                # 从运行列表中移除
                if result.get("success", False):
                    del running_services[service_id]

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"服务 {service_id} " +
                                   ("停止成功" if result.get("success", False) else "停止失败")
                        }
                    ],
                    "result": result
                }

        except Exception as e:
            raise Exception(f"停止服务失败: {str(e)}")

    @staticmethod
    def _handle_restart_service(arguments, user_role, connection_id):
        """处理重启服务请求"""
        try:
            service_id = arguments.get("service_id")
            if not service_id:
                raise Exception("服务ID不能为空")

            with service_lock:
                service = running_services.get(service_id)
                if not service:
                    raise Exception(f"服务 {service_id} 不存在")

                # 重启服务
                result = service.restart()

                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"服务 {service_id} " +
                                   ("重启成功" if result.get("success", False) else "重启失败")
                        }
                    ],
                    "result": result
                }

        except Exception as e:
            raise Exception(f"重启服务失败: {str(e)}")


class ServiceGroupManager:
    @staticmethod
    def load_service_groups():
        """加载服务组配置"""
        global service_groups
        if not os.path.exists(SERVICE_GROUPS_FILE):
            # 创建默认配置
            service_groups = {"groups": {}, "default_group": None}
            ServiceGroupManager.save_service_groups()
            return service_groups

        try:
            with open(SERVICE_GROUPS_FILE, "r", encoding="utf-8") as f:
                service_groups = json.load(f)
            return service_groups
        except Exception as e:
            print(f"加载服务组配置出错: {e}")
            service_groups = {"groups": {}, "default_group": None}
            return service_groups

    @staticmethod
    def save_service_groups():
        """保存服务组配置"""
        try:
            with open(SERVICE_GROUPS_FILE, "w", encoding="utf-8") as f:
                json.dump(service_groups, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存服务组配置出错: {e}")
            return False

    @staticmethod
    def create_group(name, password, description=""):
        """创建新服务组"""
        group_id = generate_service_id()
        service_groups["groups"][group_id] = {
            "id": group_id,
            "name": name,
            "password": password,
            "description": description,
            "services": [],  # 包含的服务ID列表
            "created_at": time.time(),
        }

        # 如果是第一个组，设为默认组
        if not service_groups["default_group"]:
            service_groups["default_group"] = group_id

        ServiceGroupManager.save_service_groups()
        return group_id

    @staticmethod
    def update_group(group_id, name=None, password=None, description=None):
        """更新服务组"""
        if group_id not in service_groups["groups"]:
            return False

        group = service_groups["groups"][group_id]
        if name is not None:
            group["name"] = name
        if password is not None:
            group["password"] = password
        if description is not None:
            group["description"] = description

        ServiceGroupManager.save_service_groups()
        return True

    @staticmethod
    def delete_group(group_id):
        """删除服务组"""
        if group_id not in service_groups["groups"]:
            return False

        # 如果删除的是默认组，需要设置新的默认组
        if service_groups["default_group"] == group_id:
            remaining_groups = [
                gid for gid in service_groups["groups"].keys() if gid != group_id
            ]
            service_groups["default_group"] = (
                remaining_groups[0] if remaining_groups else None
            )

        del service_groups["groups"][group_id]
        ServiceGroupManager.save_service_groups()
        return True

    @staticmethod
    def add_service_to_group(group_id, service_id):
        """将服务添加到组"""
        if group_id not in service_groups["groups"]:
            return False

        group = service_groups["groups"][group_id]
        if service_id not in group["services"]:
            group["services"].append(service_id)
            ServiceGroupManager.save_service_groups()
        return True

    @staticmethod
    def remove_service_from_group(group_id, service_id):
        """从组中移除服务"""
        if group_id not in service_groups["groups"]:
            return False

        group = service_groups["groups"][group_id]
        if service_id in group["services"]:
            group["services"].remove(service_id)
            ServiceGroupManager.save_service_groups()
        return True

    @staticmethod
    def get_group_by_password(password):
        """根据密码获取访客组"""
        for group_id, group in service_groups["groups"].items():
            if group.get("password") == password:
                return group_id, group
        return None, None

    @staticmethod
    def get_services_by_group(group_id):
        """获取指定组的服务列表"""
        services = []

        if group_id == "":
            # 默认分组：返回所有不在任何具名分组中的服务
            all_grouped_services = set()
            for group in service_groups["groups"].values():
                all_grouped_services.update(group["services"])

            for service_id in running_services:
                if service_id not in all_grouped_services:
                    service_info = running_services[service_id].get_info()
                    guest_service_info = {
                        "id": service_info["id"],
                        "remark": service_info.get("remark", ""),
                        "status": service_info["status"],
                        "target_port": service_info.get("target_port", ""),
                        "target_ip": service_info.get("target_ip", "127.0.0.1"),
                        "mapped_address": service_info.get("mapped_address", ""),
                        "start_time": service_info.get("start_time", 0),
                        "lan_status": service_info.get("lan_status", ""),
                        "wan_status": service_info.get("wan_status", ""),
                        "nat_type": service_info.get("nat_type", ""),
                    }
                    services.append(guest_service_info)
        else:
            # 具名分组
            if group_id not in service_groups["groups"]:
                return []

            group = service_groups["groups"][group_id]
            for service_id in group["services"]:
                if service_id in running_services:
                    service_info = running_services[service_id].get_info()
                    guest_service_info = {
                        "id": service_info["id"],
                        "remark": service_info.get("remark", ""),
                        "status": service_info["status"],
                        "target_port": service_info.get("target_port", ""),
                        "target_ip": service_info.get("target_ip", "127.0.0.1"),
                        "mapped_address": service_info.get("mapped_address", ""),
                        "start_time": service_info.get("start_time", 0),
                        "lan_status": service_info.get("lan_status", ""),
                        "wan_status": service_info.get("wan_status", ""),
                        "nat_type": service_info.get("nat_type", ""),
                    }
                    services.append(guest_service_info)
        return services

    @staticmethod
    def list_groups():
        """列出所有服务组"""
        groups = []
        for group_id, group in service_groups["groups"].items():
            group_info = {
                "id": group_id,
                "name": group["name"],
                "description": group.get("description", ""),
                "password": group.get("password", ""),  # 添加密码信息（仅管理员可见）
                "service_count": len(group["services"]),
                "created_at": group.get("created_at", 0),
                "is_default": group_id == service_groups["default_group"],
            }
            groups.append(group_info)
        return groups

    @staticmethod
    def list_groups_without_password():
        """列出所有服务组（不含密码信息，供访客使用）"""
        groups = []
        for group_id, group in service_groups["groups"].items():
            group_info = {
                "id": group_id,
                "name": group["name"],
                "description": group.get("description", ""),
                "service_count": len(group["services"]),
                "created_at": group.get("created_at", 0),
                "is_default": group_id == service_groups["default_group"],
            }
            groups.append(group_info)
        return groups

    @staticmethod
    def get_services_in_group(group_id):
        """获取指定组的服务列表"""
        services = []

        if group_id == "":
            # 默认分组：返回所有不在任何具名分组中的服务
            all_grouped_services = set()
            for group in service_groups["groups"].values():
                all_grouped_services.update(group["services"])

            for service_id in running_services:
                if service_id not in all_grouped_services:
                    service_info = running_services[service_id].get_info()
                    guest_service_info = {
                        "id": service_info["id"],
                        "remark": service_info.get("remark", ""),
                        "status": service_info["status"],
                        "target_port": service_info.get("target_port", ""),
                        "target_ip": service_info.get("target_ip", "127.0.0.1"),
                        "mapped_address": service_info.get("mapped_address", ""),
                        "start_time": service_info.get("start_time", 0),
                        "lan_status": service_info.get("lan_status", ""),
                        "wan_status": service_info.get("wan_status", ""),
                        "nat_type": service_info.get("nat_type", ""),
                    }
                    services.append(guest_service_info)
        else:
            # 具名分组
            if group_id not in service_groups["groups"]:
                return []

            group = service_groups["groups"][group_id]
            for service_id in group["services"]:
                if service_id in running_services:
                    service_info = running_services[service_id].get_info()
                    guest_service_info = {
                        "id": service_info["id"],
                        "remark": service_info.get("remark", ""),
                        "status": service_info["status"],
                        "target_port": service_info.get("target_port", ""),
                        "target_ip": service_info.get("target_ip", "127.0.0.1"),
                        "mapped_address": service_info.get("mapped_address", ""),
                        "start_time": service_info.get("start_time", 0),
                        "lan_status": service_info.get("lan_status", ""),
                        "wan_status": service_info.get("wan_status", ""),
                        "nat_type": service_info.get("nat_type", ""),
                    }
                    services.append(guest_service_info)
        return services

    @staticmethod
    def remove_service_from_all_groups(service_id):
        """从所有分组中移除服务"""
        for group_id in service_groups["groups"]:
            if service_id in service_groups["groups"][group_id]["services"]:
                service_groups["groups"][group_id]["services"].remove(service_id)
                ServiceGroupManager.save_service_groups()

    @staticmethod
    def get_group_by_service(service_id):
        """根据服务ID查找其所属的分组"""
        for group_id, group in service_groups["groups"].items():
            if service_id in group["services"]:
                return group_id, group
        return None, None


# 资源清理和监控功能
def periodic_cleanup():
    """定期清理资源，防止泄漏"""

    def cleanup_worker():
        while True:
            try:
                time.sleep(3600)  # 每小时执行一次清理

                # 清理死掉的服务
                dead_services = []
                for service_id, service in services.items():
                    if service.process and service.process.poll() is not None:
                        # 进程已结束但状态未更新
                        if service.status == "运行中":
                            print(f"发现死掉的服务 {service_id}，清理中...")
                            service.status = "已停止"
                            dead_services.append(service_id)

                # 执行垃圾回收
                import gc

                collected = gc.collect()
                print(f"垃圾回收清理了 {collected} 个对象")

                # 清理消息队列过多的消息
                with message_lock:
                    if len(message_queue) > 100:
                        # 保留最新的50条消息
                        message_queue[:] = message_queue[-50:]
                        print(f"清理消息队列，保留最新50条消息")

                # 输出资源使用情况
                thread_count = threading.active_count()
                active_services = len(
                    [s for s in services.values() if s.status == "运行中"]
                )
                print(
                    f"资源监控 - 活跃线程数: {thread_count}, 活跃服务数: {active_services}"
                )

                # 如果有psutil，显示更详细的资源信息
                try:
                    import psutil

                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                    fd_count = (
                        process.num_fds() if hasattr(process, "num_fds") else "N/A"
                    )
                    print(f"内存使用: {memory_mb:.1f}MB, 文件描述符: {fd_count}")
                except:
                    pass

            except Exception as e:
                print(f"定期清理出错: {e}")

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()


# 改进信号处理
def signal_handler(signum, frame):
    print(f"\n收到信号 {signum}，开始优雅关闭...")
    cleanup()
    import sys

    sys.exit(0)


if __name__ == "__main__":
    # 注册改进的信号处理函数
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 启动定期清理
    periodic_cleanup()

    # 显示系统信息
    print(f"Natter Web管理工具 v{VERSION} 正在启动...")
    print(f"Python版本: {sys.version}")
    print(f"Natter路径: {NATTER_PATH}")
    print(f"数据目录: {DATA_DIR}")
    print("自动添加保活间隔: 30秒")

    # 加载IYUU配置
    load_iyuu_config()

    # 加载服务组配置
    ServiceGroupManager.load_service_groups()

    # 启动定时推送检查
    if iyuu_config.get("enabled", True) and iyuu_config.get("schedule", {}).get(
        "enabled", False
    ):
        schedule_daily_notification()

    # 处理命令行参数
    port = 8080

    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("端口号必须是数字")
            sys.exit(1)

    # 从环境变量读取Web端口
    web_port = os.environ.get("WEB_PORT")
    if web_port:
        try:
            port = int(web_port)
        except ValueError:
            print(f"环境变量WEB_PORT的值无效: {web_port}")

    # 恢复之前运行的服务
    NatterManager.load_services()

    # 初始化MCP服务
    if MCP_ENABLED:
        print(f"MCP服务: 启用 (最大连接数: {MCP_MAX_CONNECTIONS})")
        MCPToolRegistry.initialize_tools()
        MCPServiceTools.initialize()

        # 启动多协议服务器
        mcp_servers = []

        # 启动WebSocket服务器
        if MCP_WEBSOCKET_ENABLED:
            websocket_server = MCPWebSocketServer(MCP_WEBSOCKET_PORT)
            websocket_thread = threading.Thread(target=websocket_server.start_server, daemon=True)
            websocket_thread.start()
            mcp_servers.append(("WebSocket", MCP_WEBSOCKET_PORT))
            print(f"MCP WebSocket服务器: 启用 (端口: {MCP_WEBSOCKET_PORT})")

        # 启动TCP服务器
        if MCP_TCP_ENABLED:
            tcp_server = MCPTCPServer(MCP_TCP_PORT)
            tcp_thread = threading.Thread(target=tcp_server.start_server, daemon=True)
            tcp_thread.start()
            mcp_servers.append(("TCP", MCP_TCP_PORT))
            print(f"MCP TCP服务器: 启用 (端口: {MCP_TCP_PORT})")

        # stdio服务器（仅在特定模式下启动）
        if MCP_STDIO_ENABLED and "--mcp-stdio" in sys.argv:
            print("MCP stdio服务器: 启用")
            stdio_handler = MCPStdioHandler()
            stdio_thread = threading.Thread(target=stdio_handler.start_stdio_server, daemon=True)
            stdio_thread.start()
            mcp_servers.append(("stdio", "stdin/stdout"))

        # SSE通过HTTP服务器处理，无需单独启动
        if MCP_SSE_ENABLED:
            print(f"MCP SSE服务器: 启用 (路径: /api/mcp/sse)")
            mcp_servers.append(("SSE", "/api/mcp/sse"))

        print(f"MCP协议支持: HTTP, {', '.join([s[0] for s in mcp_servers])}")

    else:
        print("MCP服务: 禁用")

    # 启动Web服务器
    run_server(port)
