import { AlertCircle, RotateCcw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { FailedResourcePublic } from "@/types/bilibili"

const resourceTypeText: Record<string, string> = {
  video: "视频",
  dynamic: "动态",
  article: "专栏",
}

interface FailedResourceCardProps {
  resource: FailedResourcePublic
  onRetry?: (resourceId: string) => void
  isRetrying?: boolean
}

export function FailedResourceCard({
  resource,
  onRetry,
  isRetrying,
}: FailedResourceCardProps) {
  const title = resource.resource_meta?.title || resource.resource_id
  const publishedAt = resource.resource_meta?.published_at
    ? new Date(resource.resource_meta.published_at).toLocaleString()
    : null

  return (
    <Card className="overflow-hidden border-destructive/50">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Badge variant="destructive">
              {resourceTypeText[resource.resource_type] || resource.resource_type}
            </Badge>
            <Badge variant="outline" className="text-xs">
              重试 {resource.retry_count} 次
            </Badge>
          </div>
          {publishedAt ? (
            <span className="text-xs text-muted-foreground">{publishedAt}</span>
          ) : null}
        </div>
        <CardTitle className="line-clamp-2 leading-snug">{title}</CardTitle>
        {resource.last_error ? (
          <CardDescription className="line-clamp-2 text-destructive">
            <AlertCircle className="mr-1 inline size-3" />
            {resource.last_error}
          </CardDescription>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={isRetrying}
          onClick={() => onRetry?.(resource.resource_id)}
        >
          <RotateCcw className="mr-2 size-4" />
          单独重试
        </Button>
        <div className="text-xs text-muted-foreground">
          失败时间: {new Date(resource.failed_at).toLocaleString()}
        </div>
      </CardContent>
    </Card>
  )
}
