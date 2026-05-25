import { Badge } from "@/components/ui/badge"
import type { SyncStatus } from "@/types/bilibili"

const statusText: Record<SyncStatus, string> = {
  running: "同步中",
  success: "成功",
  failed: "失败",
}

export function SyncStatusBadge({ status }: { status: SyncStatus }) {
  if (status === "failed") {
    return <Badge variant="destructive">{statusText[status]}</Badge>
  }

  if (status === "success") {
    return (
      <Badge className="bg-emerald-600 text-white">{statusText[status]}</Badge>
    )
  }

  return (
    <Badge className="animate-pulse bg-blue-600 text-white">
      {statusText[status]}
    </Badge>
  )
}
