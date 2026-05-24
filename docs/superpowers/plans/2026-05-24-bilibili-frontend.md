# Bilibili 前端界面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Bilibili 模块的完整前端界面，包括账户管理、订阅管理、资源展示页面，以及 WebSocket 实时日志功能。

**Architecture:** 使用 React + TanStack Query + react-use-websocket + shadcn/ui。页面包括账户管理、订阅列表、UP主详情。WebSocket 实时推送同步日志。

**Tech Stack:** React, TypeScript, TanStack Query, react-use-websocket, shadcn/ui, Vite

**Prerequisites:** Plan 2 (Bilibili 后端核心) 必须先完成

---

## File Structure

**Frontend files to create:**
- `frontend/src/pages/bilibili/AccountsPage.tsx` - 账户管理页面
- `frontend/src/pages/bilibili/SubscriptionsPage.tsx` - 订阅列表页面
- `frontend/src/pages/bilibili/SubscriptionDetailPage.tsx` - UP主详情页面
- `frontend/src/components/bilibili/AccountForm.tsx` - 账户表单组件
- `frontend/src/components/bilibili/QRCodeDisplay.tsx` - 二维码显示组件
- `frontend/src/components/bilibili/SubscriptionForm.tsx` - 订阅表单组件
- `frontend/src/components/bilibili/SyncLogDialog.tsx` - 同步日志弹窗
- `frontend/src/components/bilibili/ResourceCard.tsx` - 资源卡片组件
- `frontend/src/components/bilibili/SyncStatusBadge.tsx` - 同步状态标签
- `frontend/src/lib/api/bilibili.ts` - Bilibili API 客户端
- `frontend/src/types/bilibili.ts` - TypeScript 类型定义

**Frontend files to modify:**
- `frontend/src/components/AppSidebar.tsx` - 添加 Bilibili 菜单
- `frontend/src/App.tsx` - 添加路由
- `frontend/vite.config.ts` - 配置 WebSocket 代理

**Dependencies to add:**
- react-use-websocket

---

### Task 1: 添加依赖和类型定义

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/types/bilibili.ts`

- [ ] **Step 1: 安装依赖**

```bash
cd frontend
npm install react-use-websocket
```

- [ ] **Step 2: 创建 TypeScript 类型定义**

```typescript
// frontend/src/types/bilibili.ts
export interface BilibiliAccount {
  id: string
  account_name: string
  auth_type: 'cookie' | 'sessdata' | 'qrcode'
  is_active: boolean
  created_at: string
}

export interface SyncConfig {
  resource_types: ('video' | 'dynamic' | 'article')[]
  sync_frequency: '1h' | '6h' | '1d' | '1w' | 'manual'
  history_limit: number | null
  batch_size: number
}

export interface BilibiliSubscription {
  id: string
  uploader_uid: string
  uploader_name: string
  uploader_avatar: string
  sync_config: SyncConfig
  is_paused: boolean
  last_sync_at: string | null
  created_at: string
}

export interface BilibiliResource {
  id: string
  resource_type: 'video' | 'dynamic' | 'article'
  resource_id: string
  title: string
  cover_url: string
  summary: string
  metadata: Record<string, any>
  published_at: string
}

export interface SyncLog {
  id: string
  status: 'running' | 'success' | 'failed'
  start_time: string
  end_time: string | null
  success_count: number
  failed_count: number
  skipped_count: number
}

export interface LogEntry {
  timestamp: string
  level: 'INFO' | 'WARN' | 'ERROR'
  message: string
  type?: string
  resource_id?: string
  title?: string
  status?: 'success' | 'failed' | 'skipped'
  error?: string
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/src/types/bilibili.ts
git commit -m "feat(bilibili): add frontend dependencies and types

- Add react-use-websocket for WebSocket support
- Define TypeScript interfaces for Bilibili entities
- Add SyncConfig, LogEntry types

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 创建 Bilibili API 客户端

**Files:**
- Create: `frontend/src/lib/api/bilibili.ts`

- [ ] **Step 1: 实现 API 客户端**

```typescript
import { api } from './client'
import type { BilibiliAccount, BilibiliSubscription, BilibiliResource } from '@/types/bilibili'

export const bilibiliApi = {
  // 账户管理
  getAccounts: () => api.get<BilibiliAccount[]>('/bilibili/accounts'),
  createAccount: (data: any) => api.post('/bilibili/accounts', data),
  deleteAccount: (id: string) => api.delete(`/bilibili/accounts/${id}`),
  
  // 订阅管理
  getSubscriptions: () => api.get<BilibiliSubscription[]>('/bilibili/subscriptions'),
  createSubscription: (data: any) => api.post('/bilibili/subscriptions', data),
  getSubscription: (id: string) => api.get<BilibiliSubscription>(`/bilibili/subscriptions/${id}`),
  updateSubscription: (id: string, data: any) => api.put(`/bilibili/subscriptions/${id}`, data),
  deleteSubscription: (id: string) => api.delete(`/bilibili/subscriptions/${id}`),
  syncSubscription: (id: string) => api.post(`/bilibili/subscriptions/${id}/sync`),
  pauseSubscription: (id: string) => api.patch(`/bilibili/subscriptions/${id}/pause`),
  
  // 资源查询
  getResources: (params: any) => api.get<BilibiliResource[]>('/bilibili/resources', { params }),
  
  // 二维码登录
  generateQRCode: () => api.post('/bilibili/accounts/qrcode/generate'),
  checkQRCode: (qrcode_key: string) => api.post('/bilibili/accounts/qrcode/check', { qrcode_key }),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api/bilibili.ts
git commit -m "feat(bilibili): add Bilibili API client

- Implement account management APIs
- Implement subscription management APIs
- Implement resource query APIs
- Add QR code login support

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 配置 WebSocket 代理

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: 添加 WebSocket 代理配置**

```typescript
export default defineConfig({
  server: {
    proxy: {
      "/backend": {
        target: "http://localhost:8888",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/backend/, ""),
        ws: true,  // 支持 WebSocket 代理
      },
    },
  },
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat(bilibili): configure WebSocket proxy for dev

- Enable WebSocket support in Vite proxy
- Route /backend to backend server with ws: true

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4-10: 实现页面和组件

由于前端组件代码量大，这里列出任务清单，详细实现参考设计文档：

- Task 4: 实现账户管理页面 (AccountsPage)
- Task 5: 实现订阅列表页面 (SubscriptionsPage)
- Task 6: 实现 UP主详情页面 (SubscriptionDetailPage)
- Task 7: 实现同步日志弹窗 (SyncLogDialog + WebSocket)
- Task 8: 实现资源卡片组件 (ResourceCard)
- Task 9: 实现状态标签组件 (SyncStatusBadge)
- Task 10: 添加路由和菜单

每个任务包含：
- 组件实现
- TanStack Query hooks
- 样式和交互
- 单元测试
- Commit

---

## Plan 3 Summary

**Total Tasks:** 10
**Estimated Time:** 10-14 hours

**Key Features:**
- 账户管理（Cookie/SESSDATA/扫码登录）
- 订阅管理（创建、编辑、暂停、删除）
- 实时日志（WebSocket）
- 资源展示（无限滚动）
- 响应式设计

完成后继续 Plan 4: RBAC 前端管理
