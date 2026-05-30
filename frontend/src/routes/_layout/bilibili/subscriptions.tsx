import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, Outlet } from "@tanstack/react-router"
import {
  MoreVertical,
  Pause,
  Play,
  Plus,
  Radio,
  RotateCw,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { PaginationBar } from "@/components/ui/pagination-bar"
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
  const [syncConfirmId, setSyncConfirmId] = useState<string | null>(null)
  const [pauseConfirmId, setPauseConfirmId] = useState<string | null>(null)
  const [pauseSyncCancelled, setPauseSyncCancelled] = useState<
    Record<string, boolean>
  >({})
  const [syncCounter, setSyncCounter] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: subsData, isPending } = useQuery({
    queryFn: () => bilibiliApi.getSubscriptions(page, pageSize),
    queryKey: ["bilibili-subscriptions", page],
  })
  const subscriptions = subsData?.subscriptions ?? []
  const totalSubscriptions = subsData?.total ?? 0
  const totalPages = Math.ceil(totalSubscriptions / pageSize)

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
      setSyncCounter((c) => c + 1)
      invalidate()
    },
    onError: handleError.bind(showErrorToast),
  })
  const pauseSubscription = useMutation({
    mutationFn: bilibiliApi.pauseSubscription,
    onSuccess: (result, subscriptionId) => {
      invalidate()
      if (result.is_paused) {
        setPauseSyncCancelled((prev) => ({
          ...prev,
          [subscriptionId]: result.sync_cancelled,
        }))
        showSuccessToast("订阅已暂停")
      } else {
        showSuccessToast("订阅已恢复")
        if (pauseSyncCancelled[subscriptionId]) {
          setPauseSyncCancelled((prev) => {
            const next = { ...prev }
            delete next[subscriptionId]
            return next
          })
          syncSubscription.mutate(subscriptionId)
        }
      }
    },
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
        onCreated={(id) => setLogSubscriptionId(id)}
      />
      {logSubscriptionId ? (
        <SyncLogDialog
          subscriptionId={logSubscriptionId}
          open={Boolean(logSubscriptionId)}
          onOpenChange={closeSyncLogDialog}
          syncCounter={syncCounter}
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

      <Dialog
        open={Boolean(syncConfirmId)}
        onOpenChange={(open) => {
          if (!open) setSyncConfirmId(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认同步</DialogTitle>
            <DialogDescription>
              确定要手动同步此订阅吗？同步过程可能需要一些时间。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button
              disabled={syncSubscription.isPending}
              onClick={() => {
                if (syncConfirmId) {
                  syncSubscription.mutate(syncConfirmId)
                  setSyncConfirmId(null)
                }
              }}
            >
              确认同步
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(pauseConfirmId)}
        onOpenChange={(open) => {
          if (!open) setPauseConfirmId(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>暂停订阅</DialogTitle>
            <DialogDescription>
              当前有同步正在运行，暂停将中止本次同步，恢复时将自动重新同步。确定要暂停吗？
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">取消</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={pauseSubscription.isPending}
              onClick={() => {
                if (pauseConfirmId) {
                  pauseSubscription.mutate(pauseConfirmId)
                  setPauseConfirmId(null)
                }
              }}
            >
              确认暂停
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

      <div className="grid gap-3">
        {subscriptions.map((subscription) => (
          <Card key={subscription.id} className="py-0">
            <CardContent className="flex items-center justify-between gap-3 px-4 py-2.5">
              <div className="flex min-w-0 items-center gap-3">
                {subscription.uploader_avatar ? (
                  <img
                    src={bilibiliApi.proxiedImageUrl(
                      subscription.uploader_avatar,
                    )}
                    alt={subscription.uploader_name}
                    className="size-8 shrink-0 rounded-full object-cover"
                  />
                ) : (
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-muted">
                    <Radio className="size-4 text-muted-foreground" />
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Link
                      className="truncate font-medium underline-offset-4 hover:underline"
                      params={{ subscriptionId: subscription.id }}
                      to="/bilibili/subscriptions/$subscriptionId"
                      search={{ type: "video", page: 1 }}
                    >
                      {subscription.uploader_name}
                    </Link>
                    {subscription.is_paused ? (
                      <Badge variant="secondary" className="shrink-0 text-[10px]">
                        已暂停
                      </Badge>
                    ) : subscription.latest_sync_status ? (
                      <SyncStatusBadge
                        status={subscription.latest_sync_status}
                      />
                    ) : (
                      <Badge className="shrink-0 bg-emerald-600 text-[10px] text-white">
                        正常
                      </Badge>
                    )}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    UID {subscription.uploader_uid} ·{" "}
                    {frequencyText[subscription.sync_config.sync_frequency]}
                    {subscription.last_sync_at
                      ? ` · ${new Date(subscription.last_sync_at).toLocaleString()}`
                      : " · 暂无同步"}
                  </p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (
                      !subscription.is_paused &&
                      subscription.latest_sync_status === "running"
                    ) {
                      setPauseConfirmId(subscription.id)
                    } else {
                      pauseSubscription.mutate(subscription.id)
                    }
                  }}
                  disabled={pauseSubscription.isPending}
                >
                  {subscription.is_paused ? (
                    <Play className="mr-1.5 size-3.5" />
                  ) : (
                    <Pause className="mr-1.5 size-3.5" />
                  )}
                  {subscription.is_paused ? "恢复" : "暂停"}
                </Button>
                <Button
                  size="sm"
                  onClick={() => setSyncConfirmId(subscription.id)}
                  disabled={syncSubscription.isPending || subscription.is_paused}
                >
                  <RotateCw className="mr-1.5 size-3.5" />
                  同步
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button size="icon" variant="ghost" className="size-8">
                      <MoreVertical className="size-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-28">
                    <DropdownMenuItem asChild>
                      <Link
                        to="/bilibili/subscriptions/$subscriptionId"
                        params={{ subscriptionId: subscription.id }}
                        search={{ type: "video", page: 1 }}
                      >
                        详情
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => setLogSubscriptionId(subscription.id)}
                    >
                      查看日志
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => {
                        setEditingSubscription(subscription)
                        setFormOpen(true)
                      }}
                    >
                      编辑订阅
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeletingSubscription(subscription)}
                    >
                      删除
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      <PaginationBar
        page={page}
        totalPages={totalPages}
        total={totalSubscriptions}
        onPageChange={setPage}
      />
    </div>
  )
}
