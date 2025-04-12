#!/usr/bin/env python3

import os
import sys
import json
import time
import subprocess
import threading
import signal
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket

# 确保能够访问到natter.py
NATTER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "natter", "natter.py")

# 存储运行中的Natter服务进程
running_services = {}
service_lock = threading.Lock()

class NatterService:
    def __init__(self, service_id, cmd_args):
        self.service_id = service_id
        self.cmd_args = cmd_args
        self.process = None
        self.start_time = None
        self.output_lines = []
        self.mapped_address = None
        self.status = "初始化中"
        
    def start(self):
        """启动Natter服务"""
        if self.process and self.process.poll() is None:
            return False
        
        cmd = [sys.executable, NATTER_PATH] + self.cmd_args
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
        for line in self.process.stdout:
            self.output_lines.append(line.strip())
            # 限制保存的日志行数
            if len(self.output_lines) > 1000:
                self.output_lines.pop(0)
            
            # 尝试提取映射地址
            if '<--Natter-->' in line:
                parts = line.split('<--Natter-->')
                if len(parts) == 2:
                    self.mapped_address = parts[1].strip()
        
        # 进程结束后更新状态
        self.status = "已停止"
    
    def stop(self):
        """停止Natter服务"""
        if self.process and self.process.poll() is None:
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
            "last_output": self.output_lines[-10:] if self.output_lines else []
        }

def generate_service_id():
    """生成唯一的服务ID"""
    return str(int(time.time() * 1000))

class NatterManager:
    @staticmethod
    def start_service(args):
        """启动新的Natter服务"""
        service_id = generate_service_id()
        
        with service_lock:
            service = NatterService(service_id, args)
            if service.start():
                running_services[service_id] = service
                return service_id
        return None
    
    @staticmethod
    def stop_service(service_id):
        """停止指定的Natter服务"""
        with service_lock:
            if service_id in running_services:
                service = running_services[service_id]
                if service.stop():
                    return True
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

class NatterHttpHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_OPTIONS(self):
        self._set_headers()
    
    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
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
        else:
            self._error(404, "Not found")
    
    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # 读取请求体
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(post_data)
        except:
            self._error(400, "Invalid JSON")
            return
        
        if path == "/api/services/start":
            if "args" in data:
                args = data["args"]
                service_id = NatterManager.start_service(args)
                if service_id:
                    self._set_headers()
                    self.wfile.write(json.dumps({"service_id": service_id}).encode())
                else:
                    self._error(500, "Failed to start service")
            else:
                self._error(400, "Missing args")
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

def get_free_port():
    """获取可用端口"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def run_server(port=8080):
    """运行Web服务器"""
    try:
        server_address = ('', port)
        httpd = HTTPServer(server_address, NatterHttpHandler)
        print(f"Natter管理界面已启动: http://localhost:{port}")
        httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"端口 {port} 已被占用，尝试其他端口...")
            new_port = get_free_port()
            run_server(new_port)
        else:
            raise

if __name__ == "__main__":
    # 检查natter.py是否存在
    if not os.path.exists(NATTER_PATH):
        print(f"错误: 找不到Natter程序 '{NATTER_PATH}'")
        sys.exit(1)
    
    # 默认使用8080端口，可通过命令行参数修改
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的端口号 '{sys.argv[1]}'，使用默认端口 8080")
    
    run_server(port)