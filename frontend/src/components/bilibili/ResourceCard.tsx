import { BookOpen, ExternalLink } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
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
  const hasSyncedContent =
    Boolean(resource.full_content?.trim()) &&
    resource.full_content?.trim() !== resource.summary?.trim()

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
      {url || hasSyncedContent ? (
        <CardContent className="flex flex-wrap gap-2">
          {hasSyncedContent ? (
            <Dialog>
              <DialogTrigger asChild>
                <Button size="sm">
                  <BookOpen className="mr-2 size-4" />
                  查看已同步内容
                </Button>
              </DialogTrigger>
              <DialogContent className="max-h-[86vh] max-w-[calc(100%-2rem)] overflow-y-auto sm:max-w-4xl">
                <DialogHeader>
                  <DialogTitle>{resource.title}</DialogTitle>
                </DialogHeader>
                <article className="prose prose-sm max-w-none whitespace-pre-wrap rounded-lg border bg-muted/20 p-4 text-sm leading-7 dark:prose-invert">
                  {resource.full_content}
                </article>
              </DialogContent>
            </Dialog>
          ) : null}
          {url ? (
            <Button variant="outline" size="sm" asChild>
              <a href={url} target="_blank" rel="noreferrer">
                <ExternalLink className="mr-2 size-4" />
                打开原文
              </a>
            </Button>
          ) : null}
        </CardContent>
      ) : null}
    </Card>
  )
}
