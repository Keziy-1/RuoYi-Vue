# -*- coding: utf-8 -*-
"""
HTTP 请求工具封装
================
功能说明：
1. 基于 requests.Session 实现连接复用，减少 TCP/SSL 握手开销
2. 统一 JWT Bearer Token 注入：调用 set_token() 后，后续请求自动携带 Authorization 头
3. 401 自动重登：返回 401 时自动调用 login 回调（若配置）刷新 token 并重试 1 次
4. 统一日志打印：请求/响应摘要输出，便于失败后排查
5. get/post/put/delete 统一入口，返回 requests.Response 原始对象供用例层灵活断言
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests

from config import settings

logger = logging.getLogger(__name__)


class RequestClient:
    """统一 HTTP 请求客户端"""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.BASE_URL
        # Session 复用连接池 + Cookie 自动管理
        self.session = requests.Session()
        self.session.headers.update(settings.DEFAULT_HEADERS)
        # JWT Token 存储，登录成功后通过 set_token 写入
        self._token: Optional[str] = None
        # 401 重登回调：Callable[[], str]，返回新 token；不配置时仅提示不会自动重登
        self._relogin_callback = None

    # ==================== Token 管理 ====================
    def set_token(self, token: str) -> None:
        """登录成功后调用，自动注入所有后续请求的 Authorization 头"""
        self._token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    def get_token(self) -> Optional[str]:
        return self._token

    def set_relogin_callback(self, callback) -> None:
        """
        注册 401 自动重登回调函数
        回调函数签名: def callback() -> str: ...  返回新 token 字符串
        """
        self._relogin_callback = callback

    # ==================== 内部核心请求 ====================
    def _build_url(self, path: str) -> str:
        """拼接完整 URL：支持 path 直接传完整 URL 或相对路径"""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return self.base_url.rstrip("/") + path

    @staticmethod
    def _log_request(method: str, url: str, kwargs: Dict[str, Any]) -> None:
        body = kwargs.get("json") or kwargs.get("data")
        body_snippet = ""
        if body is not None:
            try:
                if isinstance(body, (dict, list)):
                    body_snippet = json.dumps(body, ensure_ascii=False)[:300]
                else:
                    body_snippet = str(body)[:300]
            except Exception:
                body_snippet = "<body-serialization-failed>"
        logger.info(
            "[REQ] %s %s | params=%s | body=%s",
            method, url,
            kwargs.get("params"),
            body_snippet,
        )

    @staticmethod
    def _log_response(resp: requests.Response) -> None:
        text_snippet = resp.text[:500].replace("\n", " ")
        logger.info(
            "[RES] %s %s | HTTP=%s | cost=%.2fs | body(前500)=%s",
            resp.request.method, resp.url,
            resp.status_code,
            resp.elapsed.total_seconds(),
            text_snippet,
        )

    def _request_with_retry(
        self,
        method: str,
        path: str,
        retry_on_401: int = settings.AUTO_RELOGIN_RETRY,
        **kwargs,
    ) -> requests.Response:
        url = self._build_url(path)
        # 超时兜底：用例没传就用全局默认
        kwargs.setdefault("timeout", settings.REQUEST_TIMEOUT)

        self._log_request(method, url, kwargs)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.RequestException as e:
            logger.exception("[REQ-EXC] %s %s 连接异常: %s", method, url, e)
            raise

        self._log_response(resp)

        # 401 自动重登 + 重试（仅 1 次，避免死循环）
        if resp.status_code == 401 and retry_on_401 > 0 and callable(self._relogin_callback):
            logger.warning("[401] 请求返回 401，触发自动重登后重试 1 次 ...")
            try:
                new_token = self._relogin_callback()
                self.set_token(new_token)
            except Exception as e:
                logger.exception("自动重登失败: %s", e)
                return resp  # 重登失败则返回原始 401 响应
            # 重试：retry_on_401 - 1
            return self._request_with_retry(method, path, retry_on_401=retry_on_401 - 1, **kwargs)

        return resp

    # ==================== 对外统一方法 ====================
    def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """GET 请求；params 传 dict 自动拼 query"""
        return self._request_with_retry("GET", path, params=params, headers=headers, **kwargs)

    def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """POST 请求；优先 json 参数传 dict（application/json）；表单用 data"""
        return self._request_with_retry(
            "POST", path, json=json, data=data, params=params, headers=headers, **kwargs
        )

    def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Any = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """PUT 请求：修改类接口常用"""
        return self._request_with_retry(
            "PUT", path, json=json, data=data, params=params, headers=headers, **kwargs
        )

    def delete(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> requests.Response:
        """DELETE 请求"""
        return self._request_with_retry(
            "DELETE", path, json=json, params=params, headers=headers, **kwargs
        )

    # ==================== 响应体解析辅助 ====================
    @staticmethod
    def parse_json(resp: requests.Response) -> Tuple[int, Dict[str, Any], str]:
        """
        统一解析 RuoYi 返回结构 R<T>
        返回 (业务 code:int, data:dict, msg:str)
        解析失败返回 (-9999, {}, raw_text)
        """
        try:
            body = resp.json()
            return int(body.get("code", -9999)), body.get("data") or {}, str(body.get("msg", ""))
        except Exception:
            return -9999, {}, resp.text[:300]


# ==================== 全局单例 ====================
# 用例层直接 from common.request_util import req_client 使用
req_client = RequestClient()
