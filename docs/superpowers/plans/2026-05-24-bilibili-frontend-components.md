# Bilibili 前端界面 - 核心组件补充

本文件补充 Plan 3 的核心组件实现示例。

## Task 4: 实现账户管理页面 (AccountsPage)

**Files:**
- Create: `frontend/src/pages/bilibili/AccountsPage.tsx`
- Create: `frontend/src/components/bilibili/AccountForm.tsx`
- Create: `frontend/src/components/bilibili/QRCodeDisplay.tsx`

### AccountsPage.tsx 完整实现

```typescript
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { bilibiliApi } from '@/lib/api/bilibili'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Trash2, Plus } from 'lucide-react'
import { AccountForm } from '@/components/bilibili/AccountForm'
import type { BilibiliAccount } from '@/types/bilibili'

export function AccountsPage() {
  const [showForm, setShowForm] = useState(false)
  const queryClient = useQueryClient()
  
  const { data: accounts, isLoading } = useQuery({
    queryKey: ['bilibili-accounts'],
    queryFn: bilibiliApi.getAccounts
  })
  
  const deleteAccount = useMutation({
    mutationFn: bilibiliApi.deleteAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bilibili-accounts'] })
    }
  })
  
  if (isLoading) return <div>加载中...</div>
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">B站账户管理</h1>
        <Button onClick={() => setShowForm(true)}>
          <Plus className="mr-2 h-4 w-4" />
          添加账户
        </Button>
      </div>
      
      {showForm && (
        <AccountForm onClose={() => setShowForm(false)} />
      )}
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {accounts?.map((account: BilibiliAccount) => (
          <Card key={account.id}>
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                <span>{account.account_name}</span>
                <Badge variant={account.is_active ? "default" : "secondary"}>
                  {account.is_active ? "活跃" : "已停用"}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">
                  认证方式: {account.auth_type}
                </div>
                <div className="text-sm text-muted-foreground">
                  创建时间: {new Date(account.created_at).toLocaleDateString()}
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  className="w-full mt-4"
                  onClick={() => {
                    if (confirm('确定删除此账户？')) {
                      deleteAccount.mutate(account.id)
                    }
                  }}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  删除账户
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      
      {accounts?.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          暂无账户，点击右上角添加
        </div>
      )}
    </div>
  )
}
```

### AccountForm.tsx 完整实现

```typescript
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { bilibiliApi } from '@/lib/api/bilibili'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { QRCodeDisplay } from './QRCodeDisplay'

export function AccountForm({ onClose }: { onClose: () => void }) {
  const [authType, setAuthType] = useState<'cookie' | 'sessdata' | 'qrcode'>('cookie')
  const queryClient = useQueryClient()
  
  const createAccount = useMutation({
    mutationFn: bilibiliApi.createAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bilibili-accounts'] })
      onClose()
    }
  })
  
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    
    let credentials = {}
    if (authType === 'cookie') {
      credentials = { cookie: formData.get('cookie') }
    } else if (authType === 'sessdata') {
      credentials = {
        sessdata: formData.get('sessdata'),
        bili_jct: formData.get('bili_jct'),
        buvid3: formData.get('buvid3')
      }
    }
    
    createAccount.mutate({
      account_name: formData.get('account_name') as string,
      auth_type: authType,
      credentials
    })
  }
  
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>添加 B站账户</DialogTitle>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="account_name">账户名称</Label>
            <Input
              id="account_name"
              name="account_name"
              placeholder="给这个账户起个名字"
              required
            />
          </div>
          
          <Tabs value={authType} onValueChange={(v) => setAuthType(v as any)}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="cookie">Cookie</TabsTrigger>
              <TabsTrigger value="sessdata">SESSDATA</TabsTrigger>
              <TabsTrigger value="qrcode">扫码登录</TabsTrigger>
            </TabsList>
            
            <TabsContent value="cookie" className="space-y-4">
              <div>
                <Label htmlFor="cookie">Cookie 字符串</Label>
                <Textarea
                  id="cookie"
                  name="cookie"
                  placeholder="粘贴完整的 Cookie 字符串"
                  rows={4}
                  required
                />
                <p className="text-sm text-muted-foreground mt-1">
                  从浏览器开发者工具中复制 Cookie
                </p>
              </div>
            </TabsContent>
            
            <TabsContent value="sessdata" className="space-y-4">
              <div>
                <Label htmlFor="sessdata">SESSDATA</Label>
                <Input id="sessdata" name="sessdata" required />
              </div>
              <div>
                <Label htmlFor="bili_jct">bili_jct</Label>
                <Input id="bili_jct" name="bili_jct" required />
              </div>
              <div>
                <Label htmlFor="buvid3">buvid3 (可选)</Label>
                <Input id="buvid3" name="buvid3" />
              </div>
            </TabsContent>
            
            <TabsContent value="qrcode">
              <QRCodeDisplay onSuccess={onClose} />
            </TabsContent>
          </Tabs>
          
          {authType !== 'qrcode' && (
            <div className="flex justify-end space-x-2">
              <Button type="button" variant="outline" onClick={onClose}>
                取消
              </Button>
              <Button type="submit" disabled={createAccount.isPending}>
                {createAccount.isPending ? '添加中...' : '添加账户'}
              </Button>
            </div>
          )}
        </form>
      </DialogContent>
    </Dialog>
  )
}
```

### QRCodeDisplay.tsx 完整实现

```typescript
import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { bilibiliApi } from '@/lib/api/bilibili'
import { Button } from '@/components/ui/button'
import { Loader2 } from 'lucide-react'

export function QRCodeDisplay({ onSuccess }: { onSuccess: () => void }) {
  const [qrData, setQrData] = useState<{ url: string; qrcode_key: string } | null>(null)
  const [status, setStatus] = useState<'pending' | 'scanned' | 'success' | 'expired'>('pending')
  const queryClient = useQueryClient()
  
  const generateQR = useMutation({
    mutationFn: bilibiliApi.generateQRCode,
    onSuccess: (data) => {
      setQrData(data)
      setStatus('pending')
    }
  })
  
  const checkQR = useMutation({
    mutationFn: bilibiliApi.checkQRCode,
    onSuccess: (data) => {
      if (data.status === 'success') {
        setStatus('success')
        queryClient.invalidateQueries({ queryKey: ['bilibili-accounts'] })
        setTimeout(onSuccess, 1000)
      } else if (data.status === 'scanned') {
        setStatus('scanned')
      } else if (data.status === 'expired') {
        setStatus('expired')
      }
    }
  })
  
  useEffect(() => {
    generateQR.mutate()
  }, [])
  
  useEffect(() => {
    if (!qrData || status === 'success' || status === 'expired') return
    
    const interval = setInterval(() => {
      checkQR.mutate(qrData.qrcode_key)
    }, 2000)
    
    return () => clearInterval(interval)
  }, [qrData, status])
  
  if (!qrData) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }
  
  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <img src={qrData.url} alt="扫码登录" className="w-64 h-64" />
      </div>
      
      <div className="text-center">
        {status === 'pending' && (
          <p className="text-muted-foreground">请使用 B站 APP 扫描二维码</p>
        )}
        {status === 'scanned' && (
          <p className="text-blue-600">已扫描，请在手机上确认</p>
        )}
        {status === 'success' && (
          <p className="text-green-600">登录成功！</p>
        )}
        {status === 'expired' && (
          <div className="space-y-2">
            <p className="text-red-600">二维码已过期</p>
            <Button onClick={() => generateQR.mutate()}>
              重新生成
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
```

---

## Task 7: 实现同步日志弹窗 (SyncLogDialog + WebSocket)

**Files:**
- Create: `frontend/src/components/bilibili/SyncLogDialog.tsx`

### SyncLogDialog.tsx 完整实现

```typescript
import { useEffect, useRef, useState } from 'react'
import useWebSocket from 'react-use-websocket'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CheckCircle2, XCircle, AlertCircle, Loader2 } from 'lucide-react'
import type { LogEntry } from '@/types/bilibili'

interface Props {
  subscriptionId: string
  open: boolean
  onClose: () => void
}

export function SyncLogDialog({ subscriptionId, open, onClose }: Props) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [status, setStatus] = useState<'running' | 'success' | 'failed'>('running')
  const scrollRef = useRef<HTMLDivElement>(null)
  
  const token = localStorage.getItem('access_token')
  const wsUrl = `ws://localhost:8000/api/v1/bilibili/ws/sync-logs/${subscriptionId}?token=${token}`
  
  const { lastMessage, readyState } = useWebSocket(
    open ? wsUrl : null,
    {
      shouldReconnect: () => false,
      onMessage: (event) => {
        const data = JSON.parse(event.data)
        
        if (data.type === 'log') {
          setLogs(prev => [...prev, data])
        } else if (data.type === 'complete') {
          setStatus(data.status)
        }
      }
    }
  )
  
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs])
  
  const getLogIcon = (level: string, logStatus?: string) => {
    if (logStatus === 'success') return <CheckCircle2 className="h-4 w-4 text-green-600" />
    if (logStatus === 'failed') return <XCircle className="h-4 w-4 text-red-600" />
    if (logStatus === 'skipped') return <AlertCircle className="h-4 w-4 text-yellow-600" />
    if (level === 'ERROR') return <XCircle className="h-4 w-4 text-red-600" />
    if (level === 'WARN') return <AlertCircle className="h-4 w-4 text-yellow-600" />
    return <CheckCircle2 className="h-4 w-4 text-blue-600" />
  }
  
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <span>同步日志</span>
            {status === 'running' && (
              <Badge variant="default" className="ml-2">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                同步中
              </Badge>
            )}
            {status === 'success' && (
              <Badge variant="default" className="ml-2 bg-green-600">
                同步成功
              </Badge>
            )}
            {status === 'failed' && (
              <Badge variant="destructive" className="ml-2">
                同步失败
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>
        
        <ScrollArea className="h-[500px]" ref={scrollRef}>
          <div className="space-y-2 pr-4">
            {logs.map((log, index) => (
              <div
                key={index}
                className="flex items-start space-x-2 text-sm font-mono p-2 rounded hover:bg-muted"
              >
                {getLogIcon(log.level, log.status)}
                <div className="flex-1">
                  <span className="text-muted-foreground text-xs">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="ml-2">{log.message}</span>
                  {log.title && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {log.title}
                    </div>
                  )}
                  {log.error && (
                    <div className="text-xs text-red-600 mt-1">
                      错误: {log.error}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}
```

---

## 其他组件

**Task 5-6, 8-10** 的组件实现相对简单，参考以下模式：

- **SubscriptionsPage**: 类似 AccountsPage，使用 Table 展示订阅列表
- **SubscriptionDetailPage**: 使用 Tabs 切换视频/动态/专栏，InfiniteScroll 加载更多
- **ResourceCard**: 展示资源卡片，包含封面、标题、元数据
- **SyncStatusBadge**: 根据状态显示不同颜色的 Badge

详细实现参考设计文档第 3 节。

---

**执行建议：**
1. 先实现 AccountsPage 和 SyncLogDialog（核心功能）
2. 测试 WebSocket 连接和实时日志
3. 再实现其他页面和组件
