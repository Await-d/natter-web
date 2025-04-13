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
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import psutil

# 确保能够访问到natter.py，优先使用环境变量定义的路径
NATTER_PATH = os.environ.get('NATTER_PATH') or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "natter", "natter.py")

# 数据存储目录，优先使用环境变量定义的路径
DATA_DIR = os.environ.get('DATA_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TEMPLATES_FILE = os.path.join(DATA_DIR, "templates.json")
SERVICES_DB_FILE = os.path.join(DATA_DIR, "services.json")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 存储运行中的Natter服务进程
running_services = {}
service_lock = threading.RLock()

# NAT类型和端口状态的正则表达式
NAT_TYPE_PATTERN = re.compile(r"NAT type: ([^\n]+)")
LAN_STATUS_PATTERN = re.compile(r"LAN > ([^\[]+)\[ ([^\]]+) \]")
WAN_STATUS_PATTERN = re.compile(r"WAN > ([^\[]+)\[ ([^\]]+) \]")

# 默认密码为None，表示不启用验证
PASSWORD = None

class NatterService:
    def __init__(self, service_id, cmd_args):
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
        
    def start(self):
        """启动Natter服务"""
        if self.process and self.process.poll() is None:
            return False
        
        # 检查Docker环境下是否尝试使用nftables
        if os.path.exists('/.dockerenv') and any(arg == '-m' and i+1 < len(self.cmd_args) and self.cmd_args[i+1] == 'nftables' for i, arg in enumerate(self.cmd_args)):
            print("错误: 在Docker环境中尝试使用nftables转发方法，此方法在Docker中不可用")
            self.output_lines.append("❌ 错误: nftables在Docker容器中不可用")
            self.output_lines.append("💡 请使用socket或iptables转发方法")
            self.output_lines.append("➡️ 请停止此服务，然后使用其他转发方法重新创建服务")
            self.status = "已停止"
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
        return True
    
    def _capture_output(self):
        """捕获并解析Natter输出"""
        nftables_error_detected = False
        
        for line in self.process.stdout:
            self.output_lines.append(line.strip())
            # 限制保存的日志行数为100行
            if len(self.output_lines) > 100:
                self.output_lines.pop(0)
            
            # 尝试提取映射地址
            if '<--Natter-->' in line:
                parts = line.split('<--Natter-->')
                if len(parts) == 2:
                    self.mapped_address = parts[1].strip()
            
            # 检测nftables错误
            if "nftables" in line and "not available" in line:
                nftables_error_detected = True
                self.output_lines.append("⚠️ 检测到nftables不可用错误！Docker容器可能缺少所需权限或内核支持。")
                self.output_lines.append("💡 建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。")
                self.output_lines.append("📋 步骤：停止此服务，重新创建服务并在'转发方法'中选择'socket'或'iptables'。")
            
            # 检测pcap初始化错误
            if "pcap initialization failed" in line:
                self.output_lines.append("⚠️ 检测到pcap初始化错误！这通常与nftables功能有关。")
                self.output_lines.append("💡 建议：尝试使用其他转发方法，如'socket'（内置）或'iptables'。")
            
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
        
        # 进程结束后更新状态
        self.status = "已停止"
        
        # 如果启用了自动重启，且不是由于nftables错误导致的退出，则重新启动服务
        if self.auto_restart and not nftables_error_detected:
            # 使用新线程进行重启，避免阻塞当前线程
            self.restart_thread = threading.Thread(target=self._restart_service)
            self.restart_thread.daemon = True
            self.restart_thread.start()
        elif nftables_error_detected:
            self.output_lines.append("🔄 因nftables错误，已禁用自动重启。请使用其他转发方法重新配置。")
    
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
            "auto_restart": self.auto_restart
        }
    
    def to_dict(self):
        """获取服务配置，用于持久化存储"""
        return {
            "id": self.service_id,
            "cmd_args": self.cmd_args,
            "auto_restart": self.auto_restart,
            "created_at": self.start_time or time.time()
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
    def start_service(args, auto_restart=False):
        """启动一个新的Natter服务"""
        service_id = generate_service_id()
        
        with service_lock:
            service = NatterService(service_id, args)
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
                    services_config[service_id] = {
                        'args': service.cmd_args,
                        'status': service.status,
                        'auto_restart': service.auto_restart,
                        'start_time': service.start_time,
                        'local_port': service.local_port,
                        'remote_port': service.remote_port
                    }
            
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
                    
                    if args:
                        # 创建并启动服务
                        service = NatterService(service_id, args)
                        service.auto_restart = auto_restart
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
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
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
            if "id" in query:
                service_id = query["id"][0]
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
            if "tool" in query:
                tool = query["tool"][0]
                result = self._check_tool_installed(tool)
                self._set_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self._error(400, "Missing tool parameter")
        elif path == "/api/auth/check":
            # 检查密码是否已设置
            self._set_headers()
            self.wfile.write(json.dumps({"auth_required": PASSWORD is not None}).encode())
        else:
            self._error(404, "Not found")
    
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
                service_id = NatterManager.start_service(args, auto_restart)
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
    NatterManager.stop_all_services()

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