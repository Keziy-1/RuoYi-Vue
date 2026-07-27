# -*- coding: utf-8 -*-
"""
pytest conftest：全局 fixture 共享
===============================
- req_client：统一 Session 级别客户端，所有用例共享同一个 Token 注入的连接
- login_token：前置登录 fixture，scope=session，一次会话只登录 1 次，节省登录开销
"""

import sys
import os
from pathlib import Path

# 确保 pytest 根目录在 sys.path 第 0 位，避免跨文件 import 报 ModuleNotFoundError
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest  # noqa: E402

from common.request_util import req_client  # noqa: E402
from config import settings  # noqa: E402


def _do_admin_login() -> str:
    """执行 admin 登录并返回 token；失败抛出异常，阻断后续用例执行"""
    body = {
        "username": settings.ADMIN_USERNAME,
        "password": settings.ADMIN_PASSWORD,
        "code": "",
        "uuid": "",
    }
    resp = req_client.post(settings.API_LOGIN, json=body)
    assert resp.status_code == 200, f"登录 HTTP 状态码异常：{resp.status_code}，响应={resp.text[:300]}"
    code, data, msg = req_client.parse_json(resp)
    assert code == 200, f"登录业务 code≠200，code={code}，msg={msg}，响应={resp.text[:300]}"
    token = data.get("token") or resp.json().get("token")
    assert token, f"登录响应中未找到 token 字段：{resp.text[:300]}"
    return token


@pytest.fixture(scope="session")
def client():
    """
    会话级共享 HTTP 客户端 fixture
    scope=session：所有测试用例共用同一个 RequestClient 实例，连接池与 Token 复用
    """
    # 注册 401 自动重登回调：token 过期时重登并返回新 token
    req_client.set_relogin_callback(_do_admin_login)
    yield req_client
    # 会话结束钩子：可在这里执行清理动作，例如删除临时数据


@pytest.fixture(scope="session")
def login_token(client):
    """
    会话级登录 fixture：一次运行只登录 1 次
    返回值: (token:str, client:RequestClient) 方便用例层双解包使用
    """
    token = _do_admin_login()
    client.set_token(token)
    return token, client
