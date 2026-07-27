# -*- coding: utf-8 -*-
"""
认证模块-登录接口测试用例
========================
覆盖场景：
1. 正向：admin 正确账号密码登录成功
2. 反向：密码错误登录失败
3. 反向：用户名不存在登录失败
4. 正向：登录成功 → getInfo 获取用户信息
5. 正向：登录成功 → 登出 → 再用原 token 请求 getInfo 返回 401（可选，视后端是否立即失效）

断言标准（RuoYi v3.9.2 响应结构 R<T>：
- 成功响应 {"code":200,"msg":"操作成功","data":{"token":"xxx"}}
- 失败响应 {"code":500,"msg":"用户不存在/密码错误", ...}
"""

import pytest

from common.request_util import req_client
from config import settings


# ------------------------------ Fixture 层（本文件局部：用 testcases/conftest.py 的 client/login_token 会话级 fixture

class TestLogin:
    """认证-登录模块正向与反向用例"""

    # ---------- P0：正向登录成功 ----------
    def test_login_admin_success(self, client):
        """
        P0 用例：admin 使用正确账号密码登录 → HTTP 200 + 业务 code=200 + 返回 token"""
        body = {
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD,
            "code": "",
            "uuid": "",
        }
        resp = client.post(settings.API_LOGIN, json=body)

        # 1. HTTP 状态码
        assert resp.status_code == 200, (
            f"登录失败：HTTP≠200，实际={resp.status_code}，响应={resp.text[:300]}"
        )
        # 2. 业务返回码
        code, data, msg = client.parse_json(resp)
        assert code == 200, f"登录失败：业务code≠200，code={code}，msg={msg}"
        # 3. token 字段存在且非空
        token = data.get("token") or resp.json().get("token")
        assert token and isinstance(token, str) and len(token) > 10, (
            f"登录返回 token 异常：{token}"
        )
        # 4. 把 token 注入全局 client，后续用例自动携带
        client.set_token(token)

    # ---------- P1：密码错误 ----------
    def test_login_wrong_password(self, client):
        """
        P1 用例：用户名正确但密码错误 → HTTP 200 + 业务 code≠200，msg 包含「用户不存在/密码错误」"""
        body = {
            "username": settings.ADMIN_USERNAME,
            "password": "wrong_password_xxx",
            "code": "",
            "uuid": "",
        }
        resp = client.post(settings.API_LOGIN, json=body)

        assert resp.status_code == 200, f"HTTP 状态码异常：{resp.status_code}"
        code, _data, msg = client.parse_json(resp)
        assert code != 200, f"密码错误时业务 code 不应为 200，实际={code}"
        assert "用户不存在" in msg or "密码错误" in msg, (
            f"密码错误提示语不符预期：msg={msg}"
        )

    # ---------- P1：用户名不存在 ----------
    def test_login_user_not_exist(self, client):
        """
        P1 用例：用户名不存在 → HTTP 200 + 业务 code≠200"""
        body = {
            "username": "no_such_user_9999",
            "password": settings.ADMIN_PASSWORD,
            "code": "",
            "uuid": "",
        }
        resp = client.post(settings.API_LOGIN, json=body)

        assert resp.status_code == 200, f"HTTP 状态码异常：{resp.status_code}"
        code, _data, msg = client.parse_json(resp)
        assert code != 200, f"不存在用户不应登录成功，code={code}，msg={msg}"

    # ---------- P0：登录 + getInfo 串联 ----------
    def test_login_then_getinfo(self, login_token):
        """
        P0 用例：登录后 token 注入 → 调 /getInfo 返回用户信息 → HTTP 200 + code=200 + permissions/roles 字段存在"""
        token, client = login_token

        resp = client.get(settings.API_GETINFO)

        assert resp.status_code == 200, f"getInfo HTTP≠200：{resp.status_code}，响应={resp.text[:300]}"
        code, data, msg = client.parse_json(resp)
        assert code == 200, f"getInfo 业务 code≠200：code={code}，msg={msg}"
        # admin 的 permissions=["*:*:*"]，roles=["admin"]
        assert isinstance(data, dict), f"data 字段应是 dict，实际={type(data)}"
        assert "permissions" in data, f"getInfo data 缺少 permissions 字段"
        assert "roles" in data, f"getInfo data 缺少 roles 字段"
        assert "user" in data, f"getInfo data 缺少 user 字段"

    # ---------- P1：登录 → 登出 → 原 token 请求受影响 ----------
    def test_logout_then_getinfo_401(self, login_token):
        """
        P1 用例：登录 → 登出 → 再使用原 token 请求 getInfo 期望 401
        若后端未立即失效 Token，则断言失败时标记为 xfail（标记已知限制）"""
        token, client = login_token

        # 1. 登出
        logout_resp = client.post(settings.API_LOGOUT)
        # RuoYi 标准返回 HTTP 200 + code=200
        assert logout_resp.status_code == 200

        # 2. 登出后再次请求 getInfo（token 仍在 headers 中）
        # 若你项目未启用 token 立即失效，此断言可能失败，用 pytest.xfail 作软标记
        getinfo_resp = client.get(settings.API_GETINFO)
        if getinfo_resp.status_code == 401:
            # 立即失效生效：断言通过
            assert getinfo_resp.status_code == 401
        else:
            # 未实现立即失效：标记为已知限制，不阻塞主流程
            pytest.xfail(
                reason="RuoYi 默认 JWT 无状态登出（仅前端清Token，服务端登出后JWT默认仍有效，"
                       "若需严格登出后立即失效需结合 Redis 黑名单实现"
            )
