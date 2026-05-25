import { ExternalLink } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { BilibiliResource } from "@/types/bilibili"

const resourceTypeText: Record<BilibiliResource["resource_type"], string> = {
  video: "视频",
  dynamic: "动态",
  article: "专栏",
}

export function ResourceCard({ resource }: { resource: BilibiliResource }) {
  const url =
    typeof resource.resource_meta.url === "string"
      ? resource.resource_meta.url
      : null

  return (
    <Card className="overflow-hidden">
      {resource.cover_url ? (
        <div className="aspect-video overflow-hidden bg-muted">
          <img
            src={bilibiliApi.proxiedImageUrl(resource.cover_url)}
            alt={resource.title}
            className="h-full w-full object-cover transition-transform duration-300 hover:scale-105"
          />
        </div>
      ) : null}
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <Badge variant="secondary">
            {resourceTypeText[resource.resource_type]}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {new Date(resource.published_at).toLocaleString()}
          </span>
        </div>
        <CardTitle className="line-clamp-2 leading-snug">
          {resource.title}
        </CardTitle>
        {resource.summary ? (
          <CardDescription className="line-clamp-3">
            {resource.summary}
          </CardDescription>
        ) : null}
      </CardHeader>
      {url ? (
        <CardContent>
          <Button variant="outline" size="sm" asChild>
            <a href={url} target="_blank" rel="noreferrer">
              <ExternalLink className="mr-2 size-4" />
              打开原文
            </a>
          </Button>
        </CardContent>
      ) : null}
    </Card>
  )
}
