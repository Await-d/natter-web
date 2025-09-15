#!/usr/bin/env python3
"""
MCP客户端示例代码
演示如何连接到Natter Web的MCP服务并执行操作
"""

import json
import requests
import time


class NatterMCPClient:
    """Natter Web MCP客户端"""

    def __init__(self, base_url="http://localhost:8080", password=None):
        self.base_url = base_url.rstrip("/")
        self.mcp_url = f"{self.base_url}/api/mcp"
        self.password = password
        self.connection_id = None
        self.user_role = None

    def authenticate(self):
        """认证并建立MCP连接"""
        try:
            auth_data = {
                "authenticate": True,
                "auth": {
                    "password": self.password
                }
            }

            response = requests.post(self.mcp_url, json=auth_data)
            response.raise_for_status()

            result = response.json()
            if result.get("success"):
                self.connection_id = result.get("connection_id")
                self.user_role = result.get("user_role")
                print(f"✅ 认证成功: {self.user_role} ({self.connection_id})")
                return True
            else:
                print(f"❌ 认证失败: {result}")
                return False

        except Exception as e:
            print(f"❌ 认证错误: {e}")
            return False

    def send_mcp_message(self, message):
        """发送MCP消息"""
        try:
            data = {
                "message": message,
                "auth": {"password": self.password} if self.password else None
            }

            response = requests.post(self.mcp_url, json=data)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            print(f"❌ MCP消息发送失败: {e}")
            return None

    def initialize_mcp(self):
        """初始化MCP连接"""
        init_message = {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "natter-mcp-client",
                    "version": "1.0.0"
                },
                "protocolVersion": "2024-11-05"
            }
        }

        response = self.send_mcp_message(init_message)
        if response and "result" in response:
            print("✅ MCP连接初始化成功")
            return True
        else:
            print(f"❌ MCP初始化失败: {response}")
            return False

    def get_available_tools(self):
        """获取可用工具列表"""
        tools_message = {
            "jsonrpc": "2.0",
            "id": "tools_list",
            "method": "tools/list"
        }

        response = self.send_mcp_message(tools_message)
        if response and "result" in response:
            tools = response["result"].get("tools", [])
            print(f"✅ 可用工具 ({len(tools)} 个):")
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
            return tools
        else:
            print(f"❌ 获取工具列表失败: {response}")
            return []

    def list_services(self, filter_type="all"):
        """列出服务"""
        call_message = {
            "jsonrpc": "2.0",
            "id": "list_services",
            "method": "tools/call",
            "params": {
                "name": "natter/list_services",
                "arguments": {
                    "filter": filter_type
                }
            }
        }

        response = self.send_mcp_message(call_message)
        if response and "result" in response:
            content = response["result"].get("content", [])
            if content:
                print(f"✅ 服务列表:")
                print(content[0]["text"])
            return response["result"]
        else:
            print(f"❌ 获取服务列表失败: {response}")
            return None

    def get_service_status(self, service_id):
        """获取服务状态"""
        call_message = {
            "jsonrpc": "2.0",
            "id": "get_status",
            "method": "tools/call",
            "params": {
                "name": "natter/get_service_status",
                "arguments": {
                    "service_id": service_id
                }
            }
        }

        response = self.send_mcp_message(call_message)
        if response and "result" in response:
            content = response["result"].get("content", [])
            if content:
                print(f"✅ 服务 {service_id} 状态:")
                print(content[0]["text"])
            return response["result"]
        else:
            print(f"❌ 获取服务状态失败: {response}")
            return None

    def start_service(self, local_port, keep_alive=30, remark=""):
        """启动服务 (仅管理员)"""
        if self.user_role != "admin":
            print("❌ 启动服务需要管理员权限")
            return None

        call_message = {
            "jsonrpc": "2.0",
            "id": "start_service",
            "method": "tools/call",
            "params": {
                "name": "natter/start_service",
                "arguments": {
                    "local_port": local_port,
                    "keep_alive": keep_alive,
                    "remark": remark
                }
            }
        }

        response = self.send_mcp_message(call_message)
        if response and "result" in response:
            content = response["result"].get("content", [])
            if content:
                print(f"✅ 服务启动:")
                print(content[0]["text"])
            return response["result"]
        else:
            print(f"❌ 启动服务失败: {response}")
            return None

    def stop_service(self, service_id):
        """停止服务 (仅管理员)"""
        if self.user_role != "admin":
            print("❌ 停止服务需要管理员权限")
            return None

        call_message = {
            "jsonrpc": "2.0",
            "id": "stop_service",
            "method": "tools/call",
            "params": {
                "name": "natter/stop_service",
                "arguments": {
                    "service_id": service_id
                }
            }
        }

        response = self.send_mcp_message(call_message)
        if response and "result" in response:
            content = response["result"].get("content", [])
            if content:
                print(f"✅ 服务停止:")
                print(content[0]["text"])
            return response["result"]
        else:
            print(f"❌ 停止服务失败: {response}")
            return None

    def ping(self):
        """测试连接"""
        ping_message = {
            "jsonrpc": "2.0",
            "id": "ping",
            "method": "ping"
        }

        response = self.send_mcp_message(ping_message)
        if response and "result" in response:
            pong = response["result"].get("pong")
            if pong:
                print("✅ 连接正常 (pong收到)")
                return True

        print("❌ 连接异常")
        return False


def main():
    """示例主函数"""
    print("🚀 Natter Web MCP客户端示例")
    print("=" * 50)

    # 创建客户端 (使用默认管理员密码)
    client = NatterMCPClient(password="zd2580")

    # 1. 认证
    print("\n1. 认证...")
    if not client.authenticate():
        return

    # 2. 初始化MCP连接
    print("\n2. 初始化MCP连接...")
    if not client.initialize_mcp():
        return

    # 3. 测试连接
    print("\n3. 测试连接...")
    client.ping()

    # 4. 获取可用工具
    print("\n4. 获取可用工具...")
    tools = client.get_available_tools()

    # 5. 列出所有服务
    print("\n5. 列出所有服务...")
    client.list_services()

    # 6. 如果是管理员，演示启动服务
    if client.user_role == "admin":
        print("\n6. 管理员操作示例...")
        print("注意: 以下操作仅作演示，请根据实际情况调整端口号")

        # 示例：启动一个测试服务 (请根据实际情况修改端口)
        # result = client.start_service(8888, 30, "MCP测试服务")

        # 如果启动成功，获取服务状态
        # if result:
        #     service_id = result.get("service_id")
        #     if service_id:
        #         client.get_service_status(service_id)
        #         # 停止服务
        #         client.stop_service(service_id)

        print("  (管理员操作已注释，取消注释以测试)")
    else:
        print("\n6. 访客用户 - 只能查看服务信息")

    print("\n✅ 示例完成!")


if __name__ == "__main__":
    main()