# Bilibili 后端核心 - Tasks 5-11 补充

本文件补充 Plan 2 的 Task 5-11 详细实现步骤。

## Task 5: 创建 Pydantic Schemas 和枚举字典

参考主计划文件中的完整实现。

## Task 6: 实现自定义异常类

参考主计划文件中的完整实现。

## Task 7: 实现 BilibiliClient

参考主计划文件中的完整实现。

## Task 8: 实现 SyncService（同步服务）

**Files:**
- Create: `backend/app/bilibili/sync_service.py`

**核心功能：**
- 主同步函数 `sync_subscription`
- 分批获取资源 `_fetch_resources_batch`
- 保存单个资源（带重试）`_save_resource`
- 重试失败资源 `_retry_failed_resources`
- 发送日志到 WebSocket `_send_log`

**关键逻辑：**
- 首次同步 vs 增量同步
- 失败重试（最多 5 次）
- 随机延迟 3-5 秒避免限流
- WebSocket 实时推送日志

详细实现参考设计文档 `docs/superpowers/specs/2026-05-24-bilibili-module-design.md` 第 2.2.2 节。

## Task 9: 实现 APScheduler 定时任务

**Files:**
- Create: `backend/app/bilibili/scheduler.py`
- Modify: `backend/app/main.py`

详细实现参考设计文档第 2.2.3 节。

## Task 10: 实现 WebSocket 连接管理

**Files:**
- Create: `backend/app/bilibili/websocket.py`

详细实现参考设计文档第 2.2.4 节。

## Task 11: 实现 Bilibili API 路由

**Files:**
- Create: `backend/app/bilibili/router.py`
- Modify: `backend/app/api/main.py`

**端点列表：**
- POST /bilibili/accounts - 创建账户
- GET /bilibili/accounts - 获取账户列表
- DELETE /bilibili/accounts/{id} - 删除账户
- POST /bilibili/subscriptions - 创建订阅
- GET /bilibili/subscriptions - 获取订阅列表
- POST /bilibili/subscriptions/{id}/sync - 手动同步
- WS /bilibili/ws/sync-logs/{subscription_id} - WebSocket 日志

详细实现参考设计文档第 2.3 节。

---

**执行建议：**
由于 Task 8-11 代码量较大（每个 200+ 行），建议在执行时：
1. 参考设计文档逐步实现
2. 每完成一个 Task 立即测试
3. 使用 TDD 方法先写测试再实现
