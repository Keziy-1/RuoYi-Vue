# -*- coding: utf-8 -*-
"""
全局配置文件
集中管理 base_url、测试账号、超时、开关项等可配置内容
修改环境时只需修改本文件，无需改动用例代码
"""

import os


# ==================== 服务地址 ====================
# 后端服务基础地址，优先读取环境变量，便于 CI/多环境切换
BASE_URL = os.environ.get("RY_BASE_URL", "http://localhost:8080")

# 各接口路径前缀（与 RuoYi-Vue v3.9.2 保持一致）
API_CAPTCHA = "/captchaImage"      # 获取验证码
API_LOGIN = "/login"               # 用户登录
API_LOGOUT = "/logout"             # 退出登录
API_GETINFO = "/getInfo"           # 获取用户信息
API_USER_LIST = "/system/user/list"   # 用户列表查询
API_USER = "/system/user"          # 用户新增/修改/删除
API_USER_RESET_PWD = "/system/user/resetPwd"  # 重置密码
API_ROLE_LIST = "/system/role/list"   # 角色列表查询
API_ROLE = "/system/role"          # 角色新增/修改/删除


# ==================== 测试账号 ====================
# 管理员账号（默认 RuoYi 初始化账号，生产环境请改密并通过环境变量注入）
ADMIN_USERNAME = os.environ.get("RY_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("RY_ADMIN_PWD", "admin123")

# 测试环境是否关闭验证码（sys_config: sys.account.captchaEnabled）
# true=关闭验证码，code/uuid 可传空；false=需先请求验证码接口获取
CAPTCHA_DISABLED = True


# ==================== 请求配置 ====================
# HTTP 请求全局超时（秒）：(连接超时, 读取超时)
REQUEST_TIMEOUT = (5, 15)

# 401 自动重登次数（token 过期时自动重新登录并携带新 token 重试）
AUTO_RELOGIN_RETRY = 1

# 全局请求头（除 Authorization 外的固定头）
DEFAULT_HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "User-Agent": "RyPytestAuto/1.0 (pytest + requests)",
}


# ==================== 数据清理 ====================
# 用例结束后是否清理以 auto_ 前缀创建的测试数据
AUTO_CLEANUP = True
