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

import psutil

# 版本号定义
VERSION = "1.0.5"

# 确保能够访问到natter.py，优先使用环境变量定义的路径
NATTER_PATH = os.environ.get('NATTER_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "natter", "natter.py")

# 数据存储目录，优先使用环境变量定义的路径
DATA_DIR = os.environ.get('DATA_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
# 日志存储目录，优先使用环境变量定义的路径
LOGS_DIR = os.environ.get('LOGS_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
SERVICES_DB_FILE = os.path.join(DATA_DIR, "services.json")
IYUU_CONFIG_FILE = os.path.join(DATA_DIR, "iyuu_config.json")  # IYUU配置文件

# 确保数据目录和日志目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# 存储运行中的Natter服务进程
running_services = {}
service_lock = threading.RLock()

# IYUU配置
iyuu_config = {
    "tokens": [],  # IYUU令牌列表
    "enabled": True,  # 是否启用IYUU推送
    "schedule": {
        "enabled": False,  # 是否启用定时推送
        "times": ["08:00"],   # 定时推送时间数组，支持多个时间段
        "message": "Natter服务状态日报"  # 定时推送消息
    }
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

# 新增：映射地址检测正则表达式
MAPPED_ADDRESS_PATTERN = re.compile(r"tcp://([^:]+):(\d+)")

# 默认密码为None，表示不启用验证
PASSWORD = None

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
        message_queue.append({
            "category": category,  # 消息类别: 启动, 停止, 地址变更, 错误等
            "title": title,        # 消息标题
            "content": content,    # 消息内容
            "time": time.time(),   # 消息生成时间
            "important": important # 是否为重要消息
        })

        # 如果消息标记为重要，或满足特定条件，考虑立即发送
        should_send_now = important or len(message_queue) >= 10

        # 检查距离上次发送是否已超过最小间隔
        global last_send_time
        current_time = time.time()
        time_since_last_send = current_time - last_send_time

        if should_send_now and time_since_last_send >= MIN_SEND_INTERVAL:
            # 立即发送
            print(f"触发立即发送: {'重要消息' if important else '消息队列已满'}, 距上次发送已过{time_since_last_send:.1f}秒")
            send_batch_messages()
        else:
            # 否则，设置或重置定时器
            global message_batch_timer
            if message_batch_timer is None or not message_batch_timer.is_alive():
                # 计算下次发送时间：确保至少间隔MIN_SEND_INTERVAL
                next_send_delay = max(MIN_SEND_INTERVAL - time_since_last_send, 5)  # 至少等待5秒，原来是60秒

                # 如果消息是重要的但未达到发送间隔，使用较短的延迟
                if important and next_send_delay > 5:
                    next_send_delay = 5  # 重要消息使用5秒延迟，原来是60秒

                message_batch_timer = threading.Timer(next_send_delay, send_batch_messages)
                message_batch_timer.daemon = True
                message_batch_timer.start()
                print(f"消息整合推送定时器已启动，将在{next_send_delay:.1f}秒后发送批量消息")

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
        message_title = f"🔔 Natter服务通知 ({total_unique_messages}条)"
        
        # 使用全新的美观布局
        message_content = create_beautiful_notification_layout(categories, total_unique_messages)

        # 直接发送整合后的消息
        _send_iyuu_message_direct(message_title, message_content)

        # 清空消息队列
        queue_len = len(message_queue)
        message_queue.clear()
        print(f"已整合发送 {queue_len} 条服务状态消息")

def create_beautiful_notification_layout(categories, total_messages):
    """创建美观的通知布局"""
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 消息头部 - 使用视觉分隔符
    content = f"""╭─────────── 🔔 Natter 服务通知 ───────────╮
│                                          │
│  📅 时间：{current_time}      │
│  📊 消息：{total_messages} 条更新                        │
│                                          │
╰──────────────────────────────────────────╯

"""

    # 服务状态汇总部分 - 收集所有服务信息
    services_summary = collect_services_summary(categories)
    
    if services_summary["mappings"]:
        content += """🎯 **服务映射概览**
┌─────────────────────────────────────────┐
"""
        for service_name, mapping in services_summary["mappings"].items():
            status_icon = "🟢" if service_name in services_summary["running"] else "🔴"
            content += f"│ {status_icon} **{service_name}**\n"
            content += f"│   🔗 `{mapping}`\n"
            content += f"│\n"
        
        content += "└─────────────────────────────────────────┘\n\n"

    # 按优先级处理消息类别
    priority_cats = ["错误", "服务状态", "定时报告"]
    other_cats = [cat for cat in categories.keys() if cat not in priority_cats]
    sorted_cats = [cat for cat in priority_cats if cat in categories] + sorted(other_cats)

    # 处理每个类别的消息
    for cat in sorted_cats:
        messages = categories[cat]
        
        # 获取类别图标和样式
        cat_info = get_category_style(cat)
        
        content += f"""🔸 **{cat_info['icon']} {cat}** ({len(messages)}条)
{cat_info['separator']}
"""
        
        # 根据类别使用不同的格式化方法
        if cat == "定时报告":
            content += format_scheduled_report(messages)
        elif cat in ["错误", "服务状态"]:
            content += format_important_messages(messages)
        else:
            content += format_regular_messages(messages)
        
        content += "\n"

    # 消息尾部
    content += """┌─────────────────────────────────────────┐
│  💡 通过 Natter 管理界面可以管理服务    │
│  🌐 访问地址：http://localhost:8080     │
└─────────────────────────────────────────┘"""

    return content

def collect_services_summary(categories):
    """收集服务摘要信息"""
        running_services = []
        services_with_mappings = {}

        for cat, messages in categories.items():
            for msg in messages:
                content = msg["content"]
            service_name = extract_service_name(msg["title"])

                # 提取服务的运行状态
            if cat == "启动" or "启动" in msg["title"]:
                    running_services.append(service_name)

                # 提取映射地址
            mapping = extract_mapping_address(content)
            if mapping:
                        services_with_mappings[service_name] = mapping

    return {
        "running": running_services,
        "mappings": services_with_mappings
    }

def extract_service_name(title):
    """从消息标题中提取服务名称"""
    if ']' in title:
        return title.split(']')[-1].strip()
    return title

def extract_mapping_address(content):
    """从消息内容中提取映射地址"""
    # 尝试多种模式匹配映射地址
    patterns = [
        r"映射地址[：:]\s*([^\n]+)",
        r"新地址[：:]\s*([^\n]+)",
        r"映射[：:]\s*`([^`]+)`"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            mapping = match.group(1).strip()
            if mapping and mapping not in ["无", "无映射", "等待映射..."]:
                return mapping
    return None

def get_category_style(category):
    """获取类别的样式信息"""
    styles = {
        "错误": {
            "icon": "⚠️",
            "separator": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        },
        "启动": {
            "icon": "🚀",
            "separator": "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
        },
        "停止": {
            "icon": "⏹️",
            "separator": "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"
        },
        "地址变更": {
            "icon": "🔄",
            "separator": "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░"
        },
        "地址分配": {
            "icon": "🆕",
            "separator": "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░"
        },
        "定时报告": {
            "icon": "📊",
            "separator": "═══════════════════════════════════════════"
        },
        "服务状态": {
            "icon": "📋",
            "separator": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        }
    }
    
    return styles.get(category, {
        "icon": "📌", 
        "separator": "─────────────────────────────────────────"
    })

def format_scheduled_report(messages):
    """格式化定时报告消息"""
    if not messages:
        return ""
    
    msg = messages[0]  # 使用第一条消息作为代表
                    content = msg["content"]
                    
    result = ""
    
    # 提取服务概况
    summary_match = re.search(r"总服务数.*?运行中.*?已停止.*?", content, re.DOTALL)
    if summary_match:
        summary = summary_match.group(0).strip()
        result += f"""┌─ 📈 服务概况 ─┐
│ {summary.replace('总服务数', '📦 总数').replace('运行中', '🟢 运行').replace('已停止', '🔴 停止')} │
└─────────────────┘

"""
                    
    # 提取并美化服务详情
                    services_section = re.search(r"服务详情\*\*\n(.*?)(?=\n\s*━━━|\Z)", content, re.DOTALL)
                    if services_section:
                        services_text = services_section.group(1)
                        service_blocks = re.findall(r"([🟢⚪].*?\n(?:.*?─.*?\n)*)", services_text, re.DOTALL)
        
        if service_blocks:
            result += "🎯 **服务详情列表**\n"
            for i, block in enumerate(service_blocks, 1):
                lines = block.strip().split('\n')
                if lines:
                                # 提取服务名称和状态
                    service_line = lines[0]
                    status_emoji = "🟢" if "🟢" in service_line else "🔴"
                    
                    # 提取服务名称
                    name_match = re.search(r'\*\*(.*?)\*\*', service_line)
                    service_name = name_match.group(1) if name_match else f"服务 {i}"
                    
                                # 提取映射地址
                    mapping_line = next((line for line in lines if "映射" in line), None)
                    mapping = "无映射"
                                if mapping_line:
                        mapping_match = re.search(r'`(.*?)`', mapping_line)
                        if mapping_match:
                            mapping = mapping_match.group(1)
                    
                    result += f"""
  {status_emoji} **{service_name}**
     🔗 {mapping}
"""
    
    return result

def format_important_messages(messages):
    """格式化重要消息（错误、服务状态）"""
    result = ""
    
    for i, msg in enumerate(messages, 1):
        service_name = extract_service_name(msg["title"])
                    content = msg["content"]

        result += f"""
🔹 **任务 {i}：{service_name}**
```
{format_content_as_code_block(content)}
```
"""
    
    return result

def format_regular_messages(messages):
    """格式化常规消息"""
    result = ""
    
    for i, msg in enumerate(messages, 1):
        service_name = extract_service_name(msg["title"])
        content = msg["content"]
        
        # 提取关键信息
        key_info = extract_key_info_from_content(content)
        
        result += f"""
🔸 **{service_name}**
   {key_info}
"""
    
    return result

def extract_key_info_from_content(content):
    """从消息内容中提取关键信息"""
    # 检查消息类型并提取相应信息
                    if "服务已成功启动" in content:
        return "✅ 服务已成功启动"
                    elif "服务已停止" in content:
        return "⏹️ 服务已停止运行"
                    elif "映射地址已变更" in content:
        old_addr = re.search(r"旧地址[：:]\s*([^\n]+)", content)
        new_addr = re.search(r"新地址[：:]\s*([^\n]+)", content)
        if old_addr and new_addr:
            return f"🔄 地址变更：`{old_addr.group(1)}` → `{new_addr.group(1)}`"
        return "🔄 映射地址已变更"
                    elif "服务获取到映射地址" in content:
        mapping = extract_mapping_address(content)
        if mapping:
            return f"🆕 获取新地址：`{mapping}`"
        return "🆕 获取到映射地址"
    else:
        # 返回第一行作为摘要
                        first_line = content.split('\n', 1)[0] if '\n' in content else content
        return first_line[:50] + ("..." if len(first_line) > 50 else "")

def format_content_as_code_block(content):
    """将内容格式化为代码块内容"""
    # 简化内容，只保留关键信息
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if line and not line.startswith("━"):
            # 替换一些标识符使其更简洁
            line = line.replace("服务ID:", "ID:")
            line = line.replace("服务备注:", "备注:")
            line = line.replace("本地端口:", "端口:")
            line = line.replace("映射地址:", "映射:")
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines[:5])  # 最多显示5行

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
            payload = {
                "text": text,
                "desp": desp
            }
            headers = {
                "Content-Type": "application/json; charset=UTF-8"
            }

            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    success = True
                else:
                    errors.append(f"令牌 {token[:5]}...: {result.get('errmsg', '未知错误')}")
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
                running_count = sum(1 for s in services_info if s.get("status") == "运行中")
                stopped_count = sum(1 for s in services_info if s.get("status") == "已停止")

                message = f"📊 Natter服务日报 ({len(services_info)}个服务)"
                detail = create_daily_report_layout(services_info, running_count, stopped_count)

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

    notification_thread = threading.Thread(target=check_and_send_notification, daemon=True)
    notification_thread.start()

def create_daily_report_layout(services_info, running_count, stopped_count):
    """创建美观的日报布局"""
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    report_date = time.strftime('%Y年%m月%d日')
    
    content = f"""╭─────────── 📊 Natter 服务日报 ───────────╮
│                                          │
│  📅 日期：{report_date}            │
│  ⏰ 时间：{current_time}      │
│                                          │
╰──────────────────────────────────────────╯

🎯 **服务概览** 
┌─────────────────────────────────────────┐
│  📦 总服务数：{len(services_info):>2} 个                        │
│  🟢 运行中　：{running_count:>2} 个                        │
│  🔴 已停止　：{stopped_count:>2} 个                        │
└─────────────────────────────────────────┘

"""

                if services_info:
        content += """🔸 **服务详情**
═══════════════════════════════════════════
"""
        for i, service in enumerate(services_info, 1):
                        service_id = service.get("id", "未知")
                        remark = service.get("remark") or f"服务 {service_id}"
                        status = service.get("status", "未知")
                        mapped_address = service.get("mapped_address", "无映射")
                        lan_status = service.get("lan_status", "未知")
                        wan_status = service.get("wan_status", "未知")
                        nat_type = service.get("nat_type", "未知")

            # 根据状态选择图标
            status_emoji = "🟢" if status == "运行中" else "🔴"

            content += f"""
🔹 **{i:02d}. {remark}**
   ├─ 状态：{status_emoji} {status}
   ├─ 映射：🔗 `{mapped_address}`
   ├─ LAN： {"🟢" if lan_status == "OPEN" else "🔴"} {lan_status}
   ├─ WAN： {"🟢" if wan_status == "OPEN" else "🔴"} {wan_status}
   └─ NAT： 🔍 {nat_type}
"""
                else:
        content += """❗ **暂无服务运行**
───────────────────────────────────────────
   目前没有配置任何 Natter 服务
   
"""

    content += f"""┌─────────────────────────────────────────┐
│  💡 访问管理界面：http://localhost:8080  │
│  📱 通过界面可以实时管理所有服务        │
└─────────────────────────────────────────┘"""

    return content

def create_test_message_layout():
    """创建美观的测试消息布局"""
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 获取所有服务数量
    services_info = NatterManager.list_services()
    running_count = sum(1 for s in services_info if s.get("status") == "运行中")
    stopped_count = sum(1 for s in services_info if s.get("status") == "已停止")
    
    content = f"""╭─────────── 🔔 Natter 测试通知 ───────────╮
│                                          │
│  ✅ IYUU 推送功能测试                   │
│  ⏰ 测试时间：{current_time}      │
│                                          │
╰──────────────────────────────────────────╯

🎯 **系统状态检查**
┌─────────────────────────────────────────┐
│  🖥️  运行环境：{'🐳 Docker容器' if os.path.exists('/.dockerenv') else '💻 主机系统'}              │
│  🐍 Python版本：{sys.version.split()[0]}                 │
│  💿 操作系统　：{sys.platform}                      │
└─────────────────────────────────────────┘

🔸 **服务概况**
═══════════════════════════════════════════
   📦 总服务数：{len(services_info):>2} 个
   🟢 运行中　：{running_count:>2} 个  
   🔴 已停止　：{stopped_count:>2} 个

┌─────────────────────────────────────────┐
│  ✨ 推送功能正常运行！                  │
│  💌 您已成功接收到此测试通知            │
│  🔧 可以通过管理界面配置更多服务        │
└─────────────────────────────────────────┘"""

    return content

def create_startup_notification_layout(port, services, services_count):
    """创建美观的启动通知布局"""
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    content = f"""╭─────────── 🚀 Natter 管理服务 ───────────╮
│                                          │
│  ✅ 服务启动成功                        │
│  ⏰ 启动时间：{current_time}      │
│                                          │
╰──────────────────────────────────────────╯

🔧 **服务配置**
┌─────────────────────────────────────────┐
│  🌐 访问地址：http://0.0.0.0:{port}           │
│  📨 IYUU推送：{'✅ 已启用' if iyuu_config.get('enabled', True) else '❌ 已禁用'}              │
│  ⏰ 定时推送：{'✅ 已启用' if iyuu_config.get('schedule', {}).get('enabled', False) else '❌ 已禁用'}              │
└─────────────────────────────────────────┘

"""

    if services_count > 0:
        running_count = sum(1 for s in services if s.get("running", False))
        
        content += f"""🎯 **已加载服务映射** ({services_count}个服务)
═══════════════════════════════════════════
   📦 总数：{services_count} 个
   🟢 运行：{running_count} 个
   🔴 停止：{services_count - running_count} 个

"""
        
        for i, service in enumerate(services, 1):
            service_id = service.get("id", "未知")
            remark = service.get("remark") or f"服务 {service_id}"
            mapped_address = service.get("mapped_address", "无映射")
            running = service.get("running", False)

            # 服务状态图标
            status_icon = "🟢" if running else "🔴"
            
            # 映射地址处理
            if mapped_address and mapped_address not in ["无", "无映射", "等待映射..."]:
                address_display = f"🔗 `{mapped_address}`"
            else:
                address_display = "⏳ 等待分配映射地址"

            content += f"""🔹 **{i:02d}. {remark}**
   └─ {status_icon} {address_display}

"""
    else:
        content += """❗ **暂无加载的服务**
═══════════════════════════════════════════
   目前没有配置任何 Natter 服务
   请通过管理界面添加新的服务

"""

    content += """┌─────────────────────────────────────────┐
│  🎉 Natter 管理服务已就绪！            │
│  📱 现在可以通过界面管理所有服务        │
│  💡 支持实时状态监控和推送通知          │
└─────────────────────────────────────────┘"""

    return content

def create_instant_push_layout(services_info, running_count, stopped_count, service_id=None):
    """创建美观的即时推送布局"""
    current_time = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 判断是单个服务还是全部服务
    is_single_service = service_id is not None
    title = "单服务状态" if is_single_service else "全部服务状态"
    
    content = f"""╭─────────── 📊 Natter {title} ───────────╮
│                                          │
│  📋 即时状态查询                        │
│  ⏰ 查询时间：{current_time}      │
│                                          │
╰──────────────────────────────────────────╯

🎯 **状态概览**
┌─────────────────────────────────────────┐
│  📦 查询服务：{len(services_info):>2} 个                        │
│  🟢 运行中　：{running_count:>2} 个                        │
│  🔴 已停止　：{stopped_count:>2} 个                        │
└─────────────────────────────────────────┘

"""

    if services_info:
        content += """🔸 **服务详情**
═══════════════════════════════════════════
"""
        for i, service in enumerate(services_info, 1):
            service_id = service.get("id", "未知")
            remark = service.get("remark") or f"服务 {service_id}"
            status = service.get("status", "未知")
            mapped_address = service.get("mapped_address", "无映射")
            lan_status = service.get("lan_status", "未知")
            wan_status = service.get("wan_status", "未知")
            nat_type = service.get("nat_type", "未知")

            # 根据状态选择图标
            status_emoji = "🟢" if status == "运行中" else "🔴"
            lan_emoji = "🟢" if lan_status == "OPEN" else "🔴" if lan_status == "CLOSED" else "⚪"
            wan_emoji = "🟢" if wan_status == "OPEN" else "🔴" if wan_status == "CLOSED" else "⚪"
            
            content += f"""
🔹 **{i:02d}. {remark}**
   ├─ 运行：{status_emoji} {status}
   ├─ 映射：🔗 `{mapped_address}`
   ├─ LAN ：{lan_emoji} {lan_status}
   ├─ WAN ：{wan_emoji} {wan_status}
   └─ NAT ：🔍 {nat_type}
"""
    else:
        content += """❗ **查询结果为空**
═══════════════════════════════════════════
   没有找到符合条件的服务
   
"""

    content += f"""┌─────────────────────────────────────────┐
│  💡 通过管理界面可以实时查看服务状态    │
│  🔄 状态信息每30秒自动更新              │
└─────────────────────────────────────────┘"""

    return content

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
        self.local_port = None   # 添加本地端口属性
        self.remote_port = None  # 添加远程端口属性
        self.remark = remark     # 添加备注属性
        self.last_mapped_address = None  # 记录上一次的映射地址，用于检测变更
        
        # 日志文件路径
        self.log_file = os.path.join(LOGS_DIR, f"service_{service_id}.log")

        # 尝试从命令参数中解析端口信息
        self._parse_ports_from_args()
        
        # 加载历史日志
        self._load_logs()

    def _parse_ports_from_args(self):
        """从命令参数中解析端口信息"""
        try:
            # 查找 -p 参数后面的端口号
            for i, arg in enumerate(self.cmd_args):
                if arg == '-p' and i + 1 < len(self.cmd_args):
                    self.local_port = int(self.cmd_args[i + 1])
                    break

            # 在映射地址中寻找远程端口
            if self.mapped_address and ':' in self.mapped_address:
                parts = self.mapped_address.split(':')
                if len(parts) >= 2:
                    try:
                        self.remote_port = int(parts[-1])
                    except ValueError:
                        pass
        except Exception as e:
            print(f"解析端口信息出错: {e}")

    def start(self):
        """启动Natter服务"""
        # 检查服务是否已经在运行
        if self.process and self.process.poll() is None:
            # 进程仍在运行，不能重复启动
            return False

        # 如果进程已停止，清理process对象以允许重新启动
        if self.process and self.process.poll() is not None:
            self.process = None

        # 重置服务状态
        self.status = "启动中"
        self.mapped_address = None
        self.lan_status = "未知"
        self.wan_status = "未知" 
        self.nat_type = "未知"

        # 检查Docker环境下是否尝试使用nftables
        if os.path.exists('/.dockerenv') and any(arg == '-m' and i+1 < len(self.cmd_args) and self.cmd_args[i+1] == 'nftables' for i, arg in enumerate(self.cmd_args)):
            print("错误: 在Docker环境中尝试使用nftables转发方法，此方法在Docker中不可用")
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
                f"服务启动失败\n错误原因: {error_msg}\n\n请停止此服务，然后使用其他转发方法重新创建服务"
            )

            return False

        cmd = [sys.executable, NATTER_PATH] + self.cmd_args

        # 如果没有指定keepalive间隔，添加默认值
        if not any(arg == '-k' for arg in self.cmd_args):
            cmd.extend(['-k', '30'])
            print(f"自动添加保活间隔: 30秒")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.start_time = time.time()
        self.status = "运行中"

        # 启动线程捕获输出
        t = threading.Thread(target=self._capture_output)
        t.daemon = True
        t.start()

        # 发送启动推送 - 使用消息队列
        service_name = self.remark or f"服务 {self.service_id}"
        local_port = self.local_port or "未知"
        queue_message(
            "启动",
            f"[启动] {service_name}",
            f"服务已成功启动\n服务ID: {self.service_id}\n本地端口: {local_port}\n启动时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return True

    def _capture_output(self):
        """捕获并解析Natter输出"""
        nftables_error_detected = False

        for line in self.process.stdout:
            self.output_lines.append(line.strip())
            # 限制保存的日志行数为100行
            if len(self.output_lines) > 100:
                self.output_lines.pop(0)
            
            # 保存日志到文件
            self._save_logs()

            # 尝试提取映射地址
            if '<--Natter-->' in line:
                parts = line.split('<--Natter-->')
                if len(parts) == 2:
                    new_mapped_address = parts[1].strip()

                    # 检查映射地址是否变更
                    if self.mapped_address != new_mapped_address:
                        # 记录旧地址用于推送消息
                        old_address = self.mapped_address or "无"

                        # 更新地址
                        self.mapped_address = new_mapped_address

                        # 解析远程端口
                        try:
                            if self.mapped_address and ':' in self.mapped_address:
                                addr_parts = self.mapped_address.split(':')
                                if len(addr_parts) >= 2:
                                    self.remote_port = int(addr_parts[-1])
                        except Exception as e:
                            print(f"解析远程端口出错: {e}")

                        # 触发NAT类型推断
                        self._update_nat_type_inference()

                        # 发送映射地址变更推送 - 使用消息队列
                        service_name = self.remark or f"服务 {self.service_id}"
                        local_port = self.local_port or "未知"

                        # 仅在非首次获取地址时发送变更消息
                        if old_address != "无":
                            queue_message(
                                "地址变更",
                                f"[地址变更] {service_name}",
                                f"服务映射地址已变更\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n\n旧地址: {old_address}\n新地址: {self.mapped_address}\n变更时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                            )
                        else:
                            # 首次获取地址时发送通知
                            queue_message(
                                "地址分配",
                                f"[地址分配] {service_name}",
                                f"服务获取到映射地址\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n映射地址: {self.mapped_address}\n获取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
                            )

            # 检测nftables错误
            if "nftables" in line and "not available" in line:
                nftables_error_detected = True
                self.output_lines.append("⚠️ 检测到nftables不可用错误！Docker容器可能缺少所需权限或内核支持。")
                self.output_lines.append("💡 建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。")
                self.output_lines.append("📋 步骤：停止此服务，重新创建服务并在'转发方法'中选择'socket'或'iptables'。")
                
                # 保存错误信息到日志
                self._save_logs()

                # 发送错误推送 - 使用消息队列
                service_name = self.remark or f"服务 {self.service_id}"
                queue_message(
                    "错误",
                    f"[错误] {service_name}",
                    f"服务出现错误\n错误类型: nftables不可用\n服务ID: {self.service_id}\n\n建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。\n步骤：停止此服务，重新创建服务并在'转发方法'中选择'socket'或'iptables'。"
                )

            # 检测pcap初始化错误
            if "pcap initialization failed" in line:
                self.output_lines.append("⚠️ 检测到pcap初始化错误！这通常与nftables功能有关。")
                self.output_lines.append("💡 建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。")
                
                # 保存错误信息到日志
                self._save_logs()

                # 发送错误推送 - 使用消息队列
                service_name = self.remark or f"服务 {self.service_id}"
                queue_message(
                    "错误",
                    f"[错误] {service_name}",
                    f"服务出现错误\n错误类型: pcap初始化失败\n服务ID: {self.service_id}\n\n建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。"
                )

            # 提取NAT类型
            nat_match = NAT_TYPE_PATTERN.search(line)
            if nat_match:
                self.nat_type = nat_match.group(1).strip()

            # 提取LAN状态
            lan_match = LAN_STATUS_PATTERN.search(line)
            if lan_match:
                old_lan_status = self.lan_status
                self.lan_status = lan_match.group(2).strip()
                
                # 如果LAN状态变化，更新NAT类型推断
                if old_lan_status != self.lan_status:
                    self._update_nat_type_inference()

            # 提取WAN状态
            wan_match = WAN_STATUS_PATTERN.search(line)
            if wan_match:
                old_wan_status = self.wan_status
                self.wan_status = wan_match.group(2).strip()

                # 如果WAN状态变化，更新NAT类型推断
                if old_wan_status != self.wan_status:
                    self._update_nat_type_inference()

        # 进程结束后更新状态并保存日志
        self.status = "已停止"
        self._save_logs()

        # 发送服务停止推送 - 使用消息队列
        service_name = self.remark or f"服务 {self.service_id}"
        local_port = self.local_port or "未知"
        mapped_address = self.mapped_address or "无"

        # 发送服务停止通知
        queue_message(
            "停止",
            f"[停止] {service_name}",
            f"服务已停止运行\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n映射地址: {mapped_address}\n停止时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # 如果启用了自动重启，且不是由于nftables错误导致的退出，则重新启动服务
        if self.auto_restart and not nftables_error_detected:
            # 使用新线程进行重启，避免阻塞当前线程
            self.restart_thread = threading.Thread(target=self._restart_service)
            self.restart_thread.daemon = True
            self.restart_thread.start()
        elif nftables_error_detected:
            self.output_lines.append("🔄 因nftables错误，已禁用自动重启。请使用其他转发方法重新配置。")
            self._save_logs()

    def _restart_service(self):
        """自动重启服务"""
        time.sleep(1)  # 等待一秒钟后重启
        self.start()

    def _update_nat_type_inference(self):
        """基于当前状态智能推断NAT类型"""
        # 检查是否有映射地址且映射成功
        has_mapping_success = bool(self.mapped_address and self.mapped_address != "等待映射...")
        
        # 使用智能推断函数
        inferred_type = infer_nat_type_from_status(
            self.lan_status, 
            self.wan_status, 
            self.mapped_address, 
            has_mapping_success
        )
        
        # 更新NAT类型
        if inferred_type != self.nat_type:
            old_nat_type = self.nat_type
            self.nat_type = inferred_type
            
            # 记录NAT类型变化
            if old_nat_type != "未知":
                self.output_lines.append(f"🔍 NAT类型推断: {old_nat_type} → {self.nat_type}")
            else:
                self.output_lines.append(f"🔍 NAT类型推断: {self.nat_type}")

    def set_auto_restart(self, enabled):
        """设置是否自动重启"""
        self.auto_restart = enabled

    def stop(self):
        """停止Natter服务"""
        # 如果没有进程或进程已经停止，更新状态并返回成功
        if not self.process or self.process.poll() is not None:
            self.status = "已停止"
            return True
            
        try:
            # 禁用自动重启
            self.auto_restart = False

            # 尝试优雅地终止进程
            try:
                parent = psutil.Process(self.process.pid)
                for child in parent.children(recursive=True):
                    child.terminate()
                parent.terminate()

                # 给进程一些时间来终止
                time.sleep(1)

                # 如果进程仍在运行，强制终止
                if self.process.poll() is None:
                    parent = psutil.Process(self.process.pid)
                    for child in parent.children(recursive=True):
                        try:
                            child.kill()
                        except:
                            pass
                    parent.kill()
            except:
                # 如果psutil不可用，使用常规方法
                self.process.terminate()
                time.sleep(1)
                if self.process.poll() is None:
                    self.process.kill()

            self.status = "已停止"

            # 发送手动停止推送 - 使用消息队列
            service_name = self.remark or f"服务 {self.service_id}"
            local_port = self.local_port or "未知"
            mapped_address = self.mapped_address or "无"

            queue_message(
                "手动停止",
                f"[手动停止] {service_name}",
                f"服务已被手动停止\n服务ID: {self.service_id}\n服务备注: {self.remark or '无'}\n本地端口: {local_port}\n映射地址: {mapped_address}\n停止时间: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            return True
            
        except Exception as e:
            print(f"停止服务 {self.service_id} 时发生错误: {e}")
            # 即使出错，也将状态设置为已停止
            self.status = "已停止"
            return True

    def restart(self):
        """重启Natter服务"""
        try:
            # 记录重启尝试
            self.output_lines.append(f"🔄 尝试重启服务 {self.service_id}...")
            
            # 如果服务正在运行，先停止它
            if self.process and self.process.poll() is None:
                if not self.stop():
                    self.output_lines.append("❌ 停止服务失败，重启中止")
                    return False
                self.output_lines.append("✅ 服务已停止，准备重新启动")
            else:
                self.output_lines.append("ℹ️ 服务已停止，直接启动")
            
            # 等待进程完全结束
            time.sleep(2)  # 增加等待时间，确保进程完全结束
            
            # 启动服务
            if self.start():
                self.output_lines.append("✅ 服务重启成功")
                return True
            else:
                self.output_lines.append("❌ 服务启动失败")
                return False
                
        except Exception as e:
            error_msg = f"重启过程中发生错误: {str(e)}"
            self.output_lines.append(f"❌ {error_msg}")
            print(f"Service {self.service_id} restart error: {e}")
        return False

    def clear_logs(self):
        """清空日志"""
        self.output_lines = []
        # 清空日志文件
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write('')
        except Exception as e:
            print(f"清空日志文件出错: {e}")
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
            "remark": self.remark
        }

    def to_dict(self):
        """获取服务配置，用于持久化存储"""
        return {
            "id": self.service_id,
            "cmd_args": self.cmd_args,
            "auto_restart": self.auto_restart,
            "created_at": self.start_time or time.time(),
            "remark": self.remark
        }

    def _load_logs(self):
        """加载历史日志"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.output_lines = [line.strip() for line in f.readlines()]
            else:
                self.output_lines = []
        except Exception as e:
            print(f"加载历史日志出错: {e}")
            self.output_lines = []

    def _save_logs(self):
        """保存日志到文件"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                for line in self.output_lines:
                    f.write(line + '\n')
        except Exception as e:
            print(f"保存日志文件出错: {e}")

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
            with open(TEMPLATES_FILE, 'r') as f:
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
            "created_at": time.time()
        }

        # 添加到模板列表
        templates.append(new_template)

        # 保存到文件
        try:
            with open(TEMPLATES_FILE, 'w') as f:
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
            with open(TEMPLATES_FILE, 'w') as f:
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
                
                # 删除日志文件
                try:
                    if os.path.exists(service.log_file):
                        os.remove(service.log_file)
                        print(f"已删除服务 {service_id} 的日志文件")
                except Exception as e:
                    print(f"删除日志文件出错: {e}")
                
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
                return running_services[service_id].get_info()
        return None

    @staticmethod
    def list_services():
        """列出所有服务"""
        services = []
        with service_lock:
            for service_id in running_services:
                services.append(running_services[service_id].get_info())
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
                    if hasattr(service, 'mapped_address') and service.mapped_address and not service.remote_port and ':' in service.mapped_address:
                        try:
                            addr_parts = service.mapped_address.split(':')
                            if len(addr_parts) >= 2:
                                service.remote_port = int(addr_parts[-1])
                        except:
                            pass

                    # 创建配置对象，只包含一定存在的属性
                    service_data = {
                        'args': service.cmd_args,
                        'status': service.status,
                        'auto_restart': service.auto_restart,
                        'start_time': service.start_time,
                        'remark': service.remark if hasattr(service, 'remark') else ""
                    }

                    # 添加可能不存在的属性
                    if hasattr(service, 'local_port') and service.local_port is not None:
                        service_data['local_port'] = service.local_port

                    if hasattr(service, 'remote_port') and service.remote_port is not None:
                        service_data['remote_port'] = service.remote_port

                    services_config[service_id] = service_data

            with open(SERVICES_DB_FILE, 'w', encoding='utf-8') as f:
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
            with open(SERVICES_DB_FILE, 'r', encoding='utf-8') as f:
                services_config = json.load(f)

            with service_lock:
                for service_id, config in services_config.items():
                    # 检查服务是否已运行
                    if service_id in running_services:
                        continue

                    args = config.get('args')
                    auto_restart = config.get('auto_restart', False)
                    remark = config.get('remark', "")

                    if args:
                        # 创建并启动服务
                        service = NatterService(service_id, args, remark)
                        service.auto_restart = auto_restart

                        # 设置可能存在的端口信息
                        if 'local_port' in config:
                            service.local_port = config['local_port']
                        if 'remote_port' in config:
                            service.remote_port = config['remote_port']

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
        self.end_headers()

    def _authenticate(self):
        """验证请求中的密码"""
        # 如果未设置密码，则允许所有访问
        if PASSWORD is None:
            return True

        # 检查Authorization头
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Basic '):
            # 解析Basic认证头
            try:
                auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = auth_decoded.split(':', 1)
                # 检查密码是否匹配
                if password == PASSWORD:
                    return True
            except Exception as e:
                print(f"认证解析出错: {e}")

        # 如果是API请求，返回JSON格式的401错误
        # 但不发送WWW-Authenticate头，避免触发浏览器内置认证弹窗
        self.send_response(401)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": "需要认证", "auth_required": True}).encode())
        return False

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        try:
            # 解析路径和查询参数
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)

            # 如果访问的是版本号API
            if path == '/api/version':
                self._set_headers(200)
                response = {'version': VERSION}
                self.wfile.write(json.dumps(response).encode())
                return

            # 总是允许访问登录页和静态资源
            if path == "/" or path == "" or path.endswith('.html') or path.endswith('.css') or path.endswith('.js'):
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

            # API请求需要验证
            if not self._authenticate():
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
                # 检查密码是否已设置
                self._set_headers()
                self.wfile.write(json.dumps({"auth_required": PASSWORD is not None}).encode())
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
                test_message = create_test_message_layout()

                success, errors = _send_iyuu_message_direct(
                    "🔔 Natter测试通知",
                    test_message
                )
                self._set_headers()
                self.wfile.write(json.dumps({
                    "success": success,
                    "errors": errors
                }).encode())
            else:
                self._error(404, "Not found")
        except Exception as e:
            self._error(500, f"服务器内部错误: {e}")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # API请求需要验证，除了密码验证API
        if path != "/api/auth/login" and not self._authenticate():
            return

        # 读取请求体
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(post_data)
        except:
            self._error(400, "Invalid JSON")
            return

        # 密码验证API
        if path == "/api/auth/login":
            if "password" in data:
                if data["password"] == PASSWORD:
                    self._set_headers()
                    # 返回base64编码的认证信息
                    auth_string = f"user:{PASSWORD}"
                    auth_token = base64.b64encode(auth_string.encode()).decode()
                    self.wfile.write(json.dumps({"success": True, "token": auth_token}).encode())
                else:
                    self._error(401, "密码错误")
            else:
                self._error(400, "缺少密码参数")
            return

        if path == "/api/services/start":
            if "args" in data:
                args = data["args"]
                auto_restart = data.get("auto_restart", False)
                remark = data.get("remark", "")
                service_id = NatterManager.start_service(args, auto_restart, remark)
                if service_id:
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
            self.wfile.write(json.dumps({"success": True, "stopped_count": count}).encode())
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
                            matching_tokens = [t for t in iyuu_config.get("tokens", [])
                                            if t.startswith(token[:5]) and t.endswith(token[-5:])]
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
                self.wfile.write(json.dumps({
                    "success": save_result,
                    "config": iyuu_config
                }).encode())
            except Exception as e:
                self._error(500, f"更新IYUU配置失败: {e}")
        elif path == "/api/iyuu/add_token":
            # 添加新的IYUU令牌
            if "token" in data and isinstance(data["token"], str) and data["token"].strip():
                token = data["token"].strip()

                # 验证令牌是否有效
                test_url = f"https://iyuu.cn/{token}.send"
                try:
                    test_payload = {
                        "text": "Natter令牌验证",
                        "desp": "这是一条验证IYUU令牌有效性的测试消息"
                    }
                    headers = {
                        "Content-Type": "application/json; charset=UTF-8"
                    }

                    response = requests.post(test_url, json=test_payload, headers=headers, timeout=10)

                    if response.status_code == 200:
                        result = response.json()
                        if result.get("errcode") == 0:
                            # 令牌有效，添加到配置
                            if token not in iyuu_config.get("tokens", []):
                                iyuu_config.setdefault("tokens", []).append(token)
                                save_iyuu_config()

                            self._set_headers()
                            self.wfile.write(json.dumps({
                                "success": True,
                                "message": "令牌已添加并验证成功"
                            }).encode())
                        else:
                            self._error(400, f"令牌验证失败: {result.get('errmsg', '未知错误')}")
                    else:
                        self._error(400, f"令牌验证失败: HTTP错误 {response.status_code}")
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
                    matched_tokens = [t for t in original_tokens
                                     if t.startswith(token[:5]) and t.endswith(token[-5:])]

                    if matched_tokens:
                        iyuu_config["tokens"] = [t for t in original_tokens if t not in matched_tokens]
                        save_iyuu_config()

                        self._set_headers()
                        self.wfile.write(json.dumps({
                            "success": True,
                            "message": "令牌已删除"
                        }).encode())
                    else:
                        self._error(404, "未找到匹配的令牌")
                else:
                    # 直接匹配完整令牌
                    if token in iyuu_config.get("tokens", []):
                        iyuu_config["tokens"].remove(token)
                        save_iyuu_config()

                        self._set_headers()
                        self.wfile.write(json.dumps({
                            "success": True,
                            "message": "令牌已删除"
                        }).encode())
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
                running_count = sum(1 for s in services_info if s.get("status") == "运行中")
                stopped_count = sum(1 for s in services_info if s.get("status") == "已停止")
                
                message = f"📊 Natter即时状态 ({len(services_info)}个服务)"
                detail = create_instant_push_layout(services_info, running_count, stopped_count, service_id)
                
                # 发送推送
                success, errors = _send_iyuu_message_direct(message, detail)
                
                self._set_headers()
                self.wfile.write(json.dumps({
                    "success": success,
                    "errors": errors
                }).encode())
            except Exception as e:
                self._error(500, f"推送服务状态失败: {e}")
        else:
            self._error(404, "Not found")

    def _serve_file(self, filename, content_type):
        """提供静态文件服务"""
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename), "rb") as f:
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
                result = subprocess.run(["apt-get", "install", "-y", "socat"], capture_output=True, text=True)
                success = result.returncode == 0
                return {
                    "success": success,
                    "message": "socat安装成功" if success else f"安装失败: {result.stderr}"
                }
            elif tool == "gost":
                # 安装gost
                result = subprocess.run([
                    "bash", "-c",
                    "wget -qO- https://github.com/ginuerzh/gost/releases/download/v2.11.2/gost-linux-amd64-2.11.2.gz | gunzip > /usr/local/bin/gost && chmod +x /usr/local/bin/gost"
                ], capture_output=True, text=True)
                success = result.returncode == 0
                return {
                    "success": success,
                    "message": "gost安装成功" if success else f"安装失败: {result.stderr}"
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
                result = subprocess.run(["which", "socat"], capture_output=True, text=True)
                installed = result.returncode == 0
                return {"installed": installed}
            elif tool == "gost":
                # 检查gost是否已安装
                result = subprocess.run(["which", "gost"], capture_output=True, text=True)
                installed = result.returncode == 0
                return {"installed": installed}
            else:
                return {"installed": False, "error": f"未知工具: {tool}"}
        except Exception as e:
            return {"installed": False, "error": f"检查过程出错: {str(e)}"}

def get_free_port():
    """获取可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def run_server(port=8080, password=None):
    """运行Web服务器"""
    global PASSWORD
    PASSWORD = password

    try:
        # 在Docker环境中自动安装nftables和gost
        if os.path.exists('/.dockerenv'):
            print("检测到Docker环境，正在自动安装需要的工具...")
            try:
                # 尝试安装nftables
                subprocess.run(["apt-get", "update"], check=False)
                subprocess.run(["apt-get", "install", "-y", "nftables"], check=False)
                print("nftables安装完成")

                # 尝试安装gost
                subprocess.run(["bash", "-c",
                    "wget -qO- https://github.com/ginuerzh/gost/releases/download/v2.11.2/gost-linux-amd64-2.11.2.gz | gunzip > /usr/local/bin/gost && chmod +x /usr/local/bin/gost"
                ], check=False)
                print("gost安装完成")
            except Exception as e:
                print(f"工具安装过程出错: {e}")

        # 加载IYUU配置
        print("加载IYUU推送配置...")
        load_iyuu_config()

        # 如果启用了定时推送，启动定时任务
        if iyuu_config.get("schedule", {}).get("enabled", False):
            print(f"启用IYUU定时推送，每天 {iyuu_config.get('schedule', {}).get('times', ['08:00'])} 发送服务状态摘要")
            schedule_daily_notification()

        server_address = ('0.0.0.0', port)  # 修改为明确绑定0.0.0.0，确保监听所有网络接口
        httpd = HTTPServer(server_address, NatterHttpHandler)
        print(f"Natter管理界面已启动: http://0.0.0.0:{port}")
        print(f"使用的Natter路径: {NATTER_PATH}")
        print(f"数据存储目录: {DATA_DIR}")

        if PASSWORD:
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
            message_title = "🚀 Natter管理服务已启动"
            message_content = create_startup_notification_layout(port, services, services_count)

            # 直接发送整合消息，不经过队列
            _send_iyuu_message_direct(message_title, message_content)
            print("已发送启动通知和服务信息")

        httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"端口 {port} 已被占用，尝试其他端口...")
            new_port = get_free_port()
            run_server(new_port, password)
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
                f"服务器即将关闭，所有运行中的服务已停止。"
            )
            message_queue.clear()

    print(f"已停止 {stopped_count} 个服务")

# 添加IYUU消息推送相关函数
def load_iyuu_config():
    """加载IYUU配置"""
    global iyuu_config
    try:
        if os.path.exists(IYUU_CONFIG_FILE):
            with open(IYUU_CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                iyuu_config.update(loaded_config)
    except Exception as e:
        print(f"加载IYUU配置失败: {e}")
        # 确保写入默认配置
        save_iyuu_config()

def save_iyuu_config():
    """保存IYUU配置"""
    try:
        with open(IYUU_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(iyuu_config, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存IYUU配置失败: {e}")
        return False

# 智能NAT类型推断
def infer_nat_type_from_status(lan_status, wan_status, mapped_address, has_mapping_success):
    """基于LAN/WAN状态和映射情况智能推断NAT类型"""
    if mapped_address and has_mapping_success:
        if lan_status == "OPEN" and wan_status == "OPEN":
            return "Full Cone NAT (完全锥形)"
        elif lan_status == "CLOSED" and wan_status == "OPEN":
            return "Symmetric NAT (对称型)"
        elif wan_status == "CLOSED":
            return "Port Restricted NAT (端口受限)"
        else:
            return "Address Restricted NAT (地址受限)"
    elif mapped_address:
        return "NAT检测中..."
    else:
        return "无映射地址"

if __name__ == "__main__":
    # 注册清理函数
    signal.signal(signal.SIGINT, lambda sig, frame: (cleanup(), sys.exit(0)))

    # 显示系统信息
    print(f"Python版本: {sys.version}")
    print(f"操作系统: {os.name}, {sys.platform}")

    # 检查natter.py是否存在
    if not os.path.exists(NATTER_PATH):
        print(f"错误: 找不到Natter程序 '{NATTER_PATH}'")
        print(f"当前工作目录: {os.getcwd()}")
        print(f"目录内容:")
        for path, dirs, files in os.walk("..", topdown=False):
            for name in files:
                if "natter.py" in name:
                    print(os.path.join(path, name))
        sys.exit(1)
    else:
        print(f"找到Natter程序: {NATTER_PATH}")

    # 检查数据目录
    if not os.path.exists(DATA_DIR):
        print(f"注意: 数据目录 '{DATA_DIR}' 不存在，将创建")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            print(f"数据目录已创建: {DATA_DIR}")
        except Exception as e:
            print(f"创建数据目录时发生错误: {e}")
            sys.exit(1)

    # 默认使用8080端口，可通过命令行参数修改
    port = 8080
    password = None

    # 处理命令行参数
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的端口号 '{sys.argv[1]}'，使用默认端口 8080")

    # 获取密码
    if len(sys.argv) > 2:
        password = sys.argv[2]
        print("已设置访问密码")

    print(f"尝试在端口 {port} 启动Web服务器...")
    run_server(port, password)
