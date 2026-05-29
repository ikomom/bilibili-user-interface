import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, Outlet } from "@tanstack/react-router"
import {
  Eye,
  FileText,
  Pause,
  Pencil,
  Play,
  Plus,
  Radio,
  RotateCw,
  Trash2,
} from "lucide-react"
import { useCallback, useState } from "react"

import { SubscriptionForm } from "@/components/bilibili/SubscriptionForm"
import { SyncLogDialog } from "@/components/bilibili/SyncLogDialog"
import { SyncStatusBadge } from "@/components/bilibili/SyncStatusBadge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { BilibiliSubscription } from "@/types/bilibili"
import { handleError } from "@/utils"

const frequencyText = {
  "1d": "每天",
  "1h": "每小时",
  "1w": "每周",
  "6h": "每 6 小时",
  manual: "手动",
}

export const Route = createFileRoute("/_layout/bilibili/subscriptions")({
  component: Outlet,
  head: () => ({
    meta: [{ title: "Bilibili Subscriptions - FastAPI Template" }],
  }),
})

export function SubscriptionsPage() {
  const [formOpen, setFormOpen] = useState(false)
  const [editingSubscription, setEditingSubscription] =
    useState<BilibiliSubscription | null>(null)
  const [deletingSubscription, setDeletingSubscription] =
    useState<BilibiliSubscription | null>(null)
  const [logSubscriptionId, setLogSubscriptionId] = useState<string | null>(
    null,
  )
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: subscriptions = [], isPending } = useQuery({
    queryFn: bilibiliApi.getSubscriptions,
    queryKey: ["bilibili-subscriptions"],
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["bilibili-subscriptions"] })
  const closeSyncLogDialog = useCallback((open: boolean) => {
    if (!open) {
      setLogSubscriptionId(null)
    }
  }, [])
  const syncSubscription = useMutation({
    mutationFn: bilibiliApi.syncSubscription,
    onSuccess: (_, subscriptionId) => {
      showSuccessToast("同步已启动")
      setLogSubscriptionId(subscriptionId)
      invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })
  const pauseSubscription = useMutation({
    mutationFn: bilibiliApi.pauseSubscription,
    onSuccess: invalidate,
    onError: handleError.bind(showErrorToast),
  })
  const deleteSubscription = useMutation({
    mutationFn: bilibiliApi.deleteSubscription,
    onSuccess: () => {
      showSuccessToast("订阅已删除")
      invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">UP 主订阅</h1>
          <p className="text-muted-foreground">创建订阅并同步 UP 主内容。</p>
        </div>
        <Button
          onClick={() => {
            setEditingSubscription(null)
            setFormOpen(true)
          }}
        >
          <Plus className="mr-2 size-4" />
          添加订阅
        </Button>
      </div>

      <SubscriptionForm
        open={formOpen}
        subscription={editingSubscription}
        onOpenChange={(open) => {
          setFormOpen(open)
          if (!open) setEditingSubscription(null)
        }}
      />
      {logSubscriptionId ? (
        <SyncLogDialog
          subscriptionId={logSubscriptionId}
          open={Boolean(logSubscriptionId)}
          onOpenChange={closeSyncLogDialog}
        />
      ) : null}

      <Dialog
        open={Boolean(deletingSubscription)}
        onOpenChange={(open) => {
          if (!open) setDeletingSubscription(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除订阅「{deletingSubscription?.uploader_name}」吗？此操作无法撤销，已同步的资源也会一并删除。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={deleteSubscription.isPending}
              onClick={() => {
                if (deletingSubscription) {
                  deleteSubscription.mutate(deletingSubscription.id)
                  setDeletingSubscription(null)
                }
              }}
            >
              确认删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isPending ? (
        <p className="text-muted-foreground">加载订阅中...</p>
      ) : null}

      {!isPending && subscriptions.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>暂无订阅</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            添加 B站账户后，可以订阅 UP 主并同步视频、动态和专栏。
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4">
        {subscriptions.map((subscription) => (
          <Card key={subscription.id}>
            <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-4">
                {subscription.uploader_avatar ? (
                  <img
                    src={bilibiliApi.proxiedImageUrl(
                      subscription.uploader_avatar,
                    )}
                    alt={subscription.uploader_name}
                    className="size-12 rounded-full object-cover"
                  />
                ) : (
                  <div className="flex size-12 items-center justify-center rounded-full bg-muted">
                    <Radio className="size-5 text-muted-foreground" />
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <Link
                      className="font-semibold underline-offset-4 hover:underline"
                      params={{ subscriptionId: subscription.id }}
                      to="/bilibili/subscriptions/$subscriptionId"
                    >
                      {subscription.uploader_name}
                    </Link>
                    {subscription.is_paused ? (
                      <Badge variant="secondary">已暂停</Badge>
                    ) : subscription.latest_sync_status ? (
                      <SyncStatusBadge
                        status={subscription.latest_sync_status}
                      />
                    ) : (
                      <Badge className="bg-emerald-600 text-white">正常</Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    UID {subscription.uploader_uid} ·{" "}
                    {frequencyText[subscription.sync_config.sync_frequency]}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    上次同步成功：{" "}
                    {subscription.last_sync_at
                      ? new Date(subscription.last_sync_at).toLocaleString()
                      : "暂无"}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" asChild>
                  <Link
                    to="/bilibili/subscriptions/$subscriptionId"
                    params={{ subscriptionId: subscription.id }}
                  >
                    <Eye className="mr-2 size-4" />
                    详情
                  </Link>
                </Button>
                <Button
                  size="sm"
                  onClick={() => syncSubscription.mutate(subscription.id)}
                  disabled={syncSubscription.isPending}
                >
                  <RotateCw className="mr-2 size-4" />
                  同步
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setLogSubscriptionId(subscription.id)}
                >
                  <FileText className="mr-2 size-4" />
                  查看日志
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditingSubscription(subscription)
                    setFormOpen(true)
                  }}
                >
                  <Pencil className="mr-2 size-4" />
                  编辑
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => pauseSubscription.mutate(subscription.id)}
                >
                  {subscription.is_paused ? (
                    <Play className="mr-2 size-4" />
                  ) : (
                    <Pause className="mr-2 size-4" />
                  )}
                  {subscription.is_paused ? "恢复" : "暂停"}
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => setDeletingSubscription(subscription)}
                >
                  <Trash2 className="mr-2 size-4" />
                  删除
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
