#!/usr/bin/env python3
"""
MCP功能单元测试
"""

import unittest
import json
import time
import threading
from unittest.mock import Mock, patch

# 导入要测试的类
import sys
import os
sys.path.append(os.path.dirname(__file__))

# 模拟全局变量以避免导入错误
running_services = {}
service_lock = threading.RLock()
service_groups = {"groups": {}}
mcp_connections = {}
mcp_subscriptions = {}
mcp_connection_lock = threading.RLock()
MCP_ENABLED = True
MCP_MAX_CONNECTIONS = 10
ADMIN_PASSWORD = "test_admin"


class TestMCPProtocol(unittest.TestCase):
    """MCPProtocol类测试"""

    def setUp(self):
        """测试前置条件"""
        from server import MCPProtocol
        self.protocol = MCPProtocol()

    def test_create_success_response(self):
        """测试创建成功响应"""
        result = {"test": "data"}
        response = self.protocol._create_success_response("test_id", result)

        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], "test_id")
        self.assertEqual(response["result"], result)

    def test_create_error_response(self):
        """测试创建错误响应"""
        response = self.protocol._create_error_response("test_id", -32600, "Invalid Request")

        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], "test_id")
        self.assertIn("error", response)
        self.assertEqual(response["error"]["code"], -32600)
        self.assertEqual(response["error"]["message"], "Invalid Request")

    def test_handle_ping(self):
        """测试ping处理"""
        response = self.protocol._handle_ping("ping_id")

        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], "ping_id")
        self.assertTrue(response["result"]["pong"])
        self.assertIn("timestamp", response["result"])

    def test_invalid_json_handling(self):
        """测试无效JSON处理"""
        response = self.protocol.handle_message("invalid json")

        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["error"]["code"], -32700)
        self.assertIn("Parse error", response["error"]["message"])


class TestMCPToolRegistry(unittest.TestCase):
    """MCPToolRegistry类测试"""

    def setUp(self):
        """测试前置条件"""
        from server import MCPToolRegistry
        self.registry = MCPToolRegistry
        # 清空工具注册表
        self.registry._tools = {}
        self.registry._handlers = {}
        self.registry._permissions = {}

    def test_register_tool(self):
        """测试工具注册"""
        def test_handler(args, user_role, connection_id):
            return "test_result"

        self.registry.register_tool(
            "test_tool",
            "测试工具",
            {"type": "object"},
            test_handler,
            "admin"
        )

        self.assertIn("test_tool", self.registry._tools)
        self.assertIn("test_tool", self.registry._handlers)
        self.assertEqual(self.registry._permissions["test_tool"], "admin")

    def test_permission_check(self):
        """测试权限检查"""
        # 测试admin用户访问admin工具
        self.assertTrue(self.registry._check_permission("admin", "admin"))

        # 测试guest用户访问guest工具
        self.assertTrue(self.registry._check_permission("guest", "guest"))

        # 测试guest用户访问admin工具 (应该失败)
        self.assertFalse(self.registry._check_permission("guest", "admin"))

        # 测试admin用户访问guest工具 (应该成功)
        self.assertTrue(self.registry._check_permission("admin", "guest"))

    def test_get_available_tools(self):
        """测试获取可用工具列表"""
        def dummy_handler(args, user_role, connection_id):
            return "result"

        # 注册admin工具
        self.registry.register_tool("admin_tool", "管理员工具", {}, dummy_handler, "admin")

        # 注册guest工具
        self.registry.register_tool("guest_tool", "访客工具", {}, dummy_handler, "guest")

        # 测试admin用户能看到所有工具
        admin_tools = self.registry.get_available_tools("admin")
        self.assertEqual(len(admin_tools), 2)

        # 测试guest用户只能看到guest工具
        guest_tools = self.registry.get_available_tools("guest")
        self.assertEqual(len(guest_tools), 1)
        self.assertEqual(guest_tools[0]["name"], "guest_tool")


class TestMCPServiceTools(unittest.TestCase):
    """MCPServiceTools类测试"""

    def setUp(self):
        """测试前置条件"""
        from server import MCPServiceTools
        self.service_tools = MCPServiceTools

    @patch('server.running_services', {})
    @patch('server.service_lock', threading.RLock())
    def test_handle_list_services_empty(self):
        """测试空服务列表"""
        result = self.service_tools._handle_list_services({}, "admin", "test_conn")

        self.assertIn("content", result)
        self.assertIn("services", result)
        self.assertEqual(len(result["services"]), 0)
        self.assertIn("找到 0 个服务", result["content"][0]["text"])

    def test_handle_get_service_status_missing_id(self):
        """测试缺少服务ID的状态查询"""
        with self.assertRaises(Exception) as context:
            self.service_tools._handle_get_service_status({}, "admin", "test_conn")

        self.assertIn("服务ID不能为空", str(context.exception))

    def test_handle_start_service_missing_port(self):
        """测试缺少端口的服务启动"""
        with self.assertRaises(Exception) as context:
            self.service_tools._handle_start_service({}, "admin", "test_conn")

        self.assertIn("本地端口号不能为空", str(context.exception))


class TestMCPNotificationManager(unittest.TestCase):
    """MCPNotificationManager类测试"""

    def setUp(self):
        """测试前置条件"""
        from server import MCPNotificationManager
        self.notification_manager = MCPNotificationManager
        # 清空订阅
        global mcp_subscriptions
        mcp_subscriptions.clear()

    @patch('server.mcp_subscriptions', {"conn1": ["service_status"], "conn2": ["all"]})
    def test_notify_subscribers(self):
        """测试通知订阅者"""
        test_data = {"test": "notification"}

        # 这个测试主要验证函数不会抛出异常
        try:
            self.notification_manager.notify_subscribers("service_status", test_data)
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"notify_subscribers raised an exception: {e}")


class TestMCPIntegration(unittest.TestCase):
    """MCP集成测试"""

    def test_mcp_message_flow(self):
        """测试MCP消息处理流程"""
        from server import MCPProtocol, MCPToolRegistry, MCPServiceTools

        # 初始化
        protocol = MCPProtocol()
        MCPServiceTools.initialize()

        # 测试初始化请求
        init_message = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "test_client", "version": "1.0"},
                "protocolVersion": "2024-11-05"
            }
        }

        response = protocol.handle_message(init_message, "test_conn")

        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], "1")
        self.assertIn("result", response)
        self.assertIn("protocolVersion", response["result"])

    def test_authentication_integration(self):
        """测试认证集成"""
        # 这里可以添加更复杂的认证流程测试
        pass


class TestMCPMultiProtocol(unittest.TestCase):
    """MCP多协议支持测试"""

    def test_websocket_handler_creation(self):
        """测试WebSocket处理器创建"""
        from server import MCPWebSocketHandler
        import socket

        # 创建模拟socket
        mock_socket = socket.socket()
        mock_address = ("127.0.0.1", 12345)

        handler = MCPWebSocketHandler(mock_socket, mock_address)

        self.assertIsNotNone(handler.connection_id)
        self.assertEqual(handler.address, mock_address)
        self.assertFalse(handler.authenticated)
        self.assertIsNone(handler.user_role)

    def test_websocket_key_generation(self):
        """测试WebSocket key生成"""
        from server import MCPWebSocketHandler
        import socket

        mock_socket = socket.socket()
        mock_address = ("127.0.0.1", 12345)
        handler = MCPWebSocketHandler(mock_socket, mock_address)

        test_key = "test_websocket_key"
        generated_key = handler.generate_websocket_key(test_key)

        self.assertIsInstance(generated_key, str)
        self.assertTrue(len(generated_key) > 0)

    def test_tcp_server_configuration(self):
        """测试TCP服务器配置"""
        from server import MCPTCPServer, MCP_TCP_PORT

        server = MCPTCPServer()
        self.assertEqual(server.port, MCP_TCP_PORT)

    def test_stdio_handler_creation(self):
        """测试stdio处理器创建"""
        from server import MCPStdioHandler

        handler = MCPStdioHandler()

        self.assertIsNotNone(handler.connection_id)
        self.assertFalse(handler.authenticated)
        self.assertIsNone(handler.user_role)
        self.assertIsNotNone(handler.protocol)

    def test_websocket_server_creation(self):
        """测试WebSocket服务器创建"""
        from server import MCPWebSocketServer, MCP_WEBSOCKET_PORT

        server = MCPWebSocketServer()
        self.assertEqual(server.port, MCP_WEBSOCKET_PORT)
        self.assertFalse(server.running)
        self.assertIsNone(server.server_socket)


def run_tests():
    """运行所有测试"""
    print("开始运行MCP功能单元测试...")

    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    suite.addTests(loader.loadTestsFromTestCase(TestMCPProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPToolRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPServiceTools))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPNotificationManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPMultiProtocol))

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试结果
    print(f"\n测试完成:")
    print(f"运行测试: {result.testsRun}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.failures:
        print("\n失败的测试:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")

    if result.errors:
        print("\n错误的测试:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)