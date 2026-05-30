import { useQuery } from "@tanstack/react-query"
import { AlertTriangle } from "lucide-react"

import { FailedResourceCard } from "@/components/bilibili/FailedResourceCard"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { FailedResourcePublic } from "@/types/bilibili"

interface FailedResourceListProps {
  subscriptionId: string
}

export function FailedResourceList({
  subscriptionId,
}: FailedResourceListProps) {
  const { data: failedResources = [], isPending } = useQuery({
    queryFn: () => bilibiliApi.getFailedResources(subscriptionId),
    queryKey: ["bilibili-failed-resources", subscriptionId],
  })

  if (isPending) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-muted-foreground">加载中...</div>
      </div>
    )
  }

  if (failedResources.length === 0) {
    return (
      <Alert>
        <AlertTriangle className="size-4" />
        <AlertTitle>暂无失败资源</AlertTitle>
        <AlertDescription>
          所有资源都已成功同步，没有失败的记录。
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <Alert variant="destructive">
        <AlertTriangle className="size-4" />
        <AlertTitle>共 {failedResources.length} 个资源同步失败</AlertTitle>
        <AlertDescription>
          这些资源在同步时遇到错误，您可以点击"重试失败资源"按钮批量重试，或单独重试某个资源。
        </AlertDescription>
      </Alert>

      <div className="grid gap-4 md:grid-cols-2">
        {failedResources.map((resource: FailedResourcePublic) => (
          <FailedResourceCard key={resource.id} resource={resource} />
        ))}
      </div>
    </div>
  )
}
