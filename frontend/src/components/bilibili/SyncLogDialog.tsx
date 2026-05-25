import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useRef, useState } from "react"
import useWebSocket, { ReadyState } from "react-use-websocket"
import { OpenAPI } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { LogEntry, SyncLog } from "@/types/bilibili"

function getWsBaseUrl() {
  const configuredBase = OpenAPI.BASE || import.meta.env.VITE_API_URL
  if (configuredBase) {
    return configuredBase.replace(/^http/, "ws")
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws"
  return `${protocol}://${window.location.host}/backend`
}

const resourceTypeText = {
  article: "专栏",
  dynamic: "动态",
  video: "视频",
}

const levelClassName = {
  ERROR:
    "border-red-200 bg-red-50 text-red-700 dark:border-red-950 dark:bg-red-950/40 dark:text-red-300",
  INFO: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-950 dark:bg-blue-950/40 dark:text-blue-300",
  WARN: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-950 dark:bg-amber-950/40 dark:text-amber-300",
}

function statusIcon(status?: LogEntry["status"]) {
  if (status === "success") return "✓"
  if (status === "failed") return "✗"
  if (status === "skipped") return "⊙"
  return null
}

function LogEntryItem({ log }: { log: LogEntry }) {
  const [stackOpen, setStackOpen] = useState(false)
  const icon = statusIcon(log.status)

  return (
    <div className="rounded-md bg-background p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={levelClassName[log.level]} variant="outline">
          {log.level}
        </Badge>
        {log.type ? (
          <Badge variant="secondary">{resourceTypeText[log.type]}</Badge>
        ) : null}
        {icon ? <span className="font-semibold">{icon}</span> : null}
        {log.resource_id ? (
          <span className="text-xs text-muted-foreground">
            {log.resource_id}
          </span>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground">
          {new Date(log.timestamp).toLocaleTimeString()}
        </span>
      </div>
      <p className="mt-2 font-medium">{log.message}</p>
      {log.title ? (
        <p className="mt-1 text-xs text-muted-foreground">
          {log.title.length > 60 ? `${log.title.slice(0, 60)}...` : log.title}
        </p>
      ) : null}
      {log.error ? (
        <p className="mt-1 text-xs text-destructive">{log.error}</p>
      ) : null}
      {log.stack_trace ? (
        <div className="mt-2">
          <button
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => setStackOpen((current) => !current)}
            type="button"
          >
            {stackOpen ? "收起错误堆栈" : "查看错误堆栈"}
          </button>
          {stackOpen ? (
            <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded border bg-muted p-2 text-xs text-destructive">
              {log.stack_trace}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

interface SyncLogDialogProps {
  subscriptionId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SyncLogDialog({
  subscriptionId,
  open,
  onOpenChange,
}: SyncLogDialogProps) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [selectedLogId, setSelectedLogId] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const { data: syncLogs = [] } = useQuery({
    queryFn: () => bilibiliApi.getSyncLogs(subscriptionId),
    queryKey: ["bilibili-sync-logs", subscriptionId],
    enabled: open,
  })
  const latestLog = syncLogs[0]
  const selectedSyncLog =
    syncLogs.find((log) => log.id === selectedLogId) ?? latestLog
  const selectedDetails =
    selectedSyncLog?.id === latestLog?.id
      ? logs
      : (selectedSyncLog?.details ?? [])
  const wsUrl = useMemo(() => {
    const token = localStorage.getItem("access_token")
    return `${getWsBaseUrl()}/api/v1/bilibili/ws/sync-logs/${subscriptionId}?token=${token}`
  }, [subscriptionId])

  const { lastJsonMessage, readyState } = useWebSocket<LogEntry>(
    open ? wsUrl : null,
    {
      shouldReconnect: (event) => open && ![4001, 4003].includes(event.code),
    },
  )

  useEffect(() => {
    if (open) {
      setLogs(latestLog?.details ?? [])
      setSelectedLogId((current) => current ?? latestLog?.id ?? null)
    } else {
      setLogs([])
      setSelectedLogId(null)
    }
  }, [open, latestLog])

  useEffect(() => {
    if (lastJsonMessage) {
      setLogs((current) => {
        const exists = current.some(
          (log) =>
            log.timestamp === lastJsonMessage.timestamp &&
            log.message === lastJsonMessage.message,
        )
        return exists ? current : [...current, lastJsonMessage]
      })
    }
  }, [lastJsonMessage])

  useEffect(() => {
    if (open && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [open])

  const statusText: Record<SyncLog["status"], string> = {
    failed: "失败",
    running: "运行中",
    success: "成功",
  }

  const statusVariant = (status: SyncLog["status"]) => {
    if (status === "failed") return "destructive"
    if (status === "running") return "secondary"
    return "default"
  }

  const statusClassName = (status: SyncLog["status"]) => {
    if (status === "success")
      return "bg-emerald-600 text-white hover:bg-emerald-600"
    return undefined
  }

  const connectionText = {
    [ReadyState.CONNECTING]: "连接中",
    [ReadyState.OPEN]: "已连接",
    [ReadyState.CLOSING]: "关闭中",
    [ReadyState.CLOSED]: "已断开",
    [ReadyState.UNINSTANTIATED]: "未连接",
  }[readyState]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-[calc(100%-2rem)] sm:max-w-6xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            同步日志
            <Badge variant="secondary">{connectionText}</Badge>
          </DialogTitle>
        </DialogHeader>
        <div className="grid min-h-0 gap-4 md:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="max-h-[68vh] overflow-y-auto rounded-lg border bg-muted/20 p-2">
            {syncLogs.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                暂无运行记录
              </p>
            ) : (
              <div className="space-y-2">
                {syncLogs.map((syncLog) => (
                  <button
                    className={`w-full rounded-md border p-3 text-left transition-colors hover:bg-muted ${
                      selectedSyncLog?.id === syncLog.id
                        ? "border-primary bg-background shadow-sm"
                        : "bg-background/60"
                    }`}
                    key={syncLog.id}
                    onClick={() => setSelectedLogId(syncLog.id)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">
                        {new Date(syncLog.start_time).toLocaleString()}
                      </span>
                      <Badge
                        className={statusClassName(syncLog.status)}
                        variant={statusVariant(syncLog.status)}
                      >
                        {statusText[syncLog.status]}
                      </Badge>
                    </div>
                    <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                      <span>成功 {syncLog.success_count}</span>
                      <span>跳过 {syncLog.skipped_count}</span>
                      <span>失败 {syncLog.failed_count}</span>
                    </div>
                    {syncLog.error_message ? (
                      <p className="mt-2 truncate text-xs text-destructive">
                        {syncLog.error_message}
                      </p>
                    ) : null}
                  </button>
                ))}
              </div>
            )}
          </aside>
          <div
            ref={scrollRef}
            className="max-h-[68vh] overflow-y-auto rounded-lg border bg-muted/20 p-3"
          >
            {selectedDetails.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                {readyState === ReadyState.CLOSED
                  ? "连接已断开，暂无日志"
                  : "等待同步日志..."}
              </p>
            ) : (
              <div className="space-y-2 font-mono text-sm">
                {selectedDetails.map((log, index) => (
                  <LogEntryItem key={`${log.timestamp}-${index}`} log={log} />
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
