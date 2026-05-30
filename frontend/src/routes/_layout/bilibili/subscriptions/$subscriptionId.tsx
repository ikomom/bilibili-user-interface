import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { ArrowLeft, ExternalLink, LayoutGrid, List, RotateCcw } from "lucide-react"
import { useState } from "react"
import { z } from "zod"

import { FailedResourceList } from "@/components/bilibili/FailedResourceList"
import { ResourceCard } from "@/components/bilibili/ResourceCard"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { PaginationBar } from "@/components/ui/pagination-bar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"
import { bilibiliApi } from "@/lib/api/bilibili"
import { handleError } from "@/utils"

const searchSchema = z.object({
  type: z.enum(["video", "dynamic", "article", "failed"]).catch("video"),
  page: z.coerce.number().int().min(1).catch(1),
})

export const Route = createFileRoute(
  "/_layout/bilibili/subscriptions/$subscriptionId",
)({
  component: SubscriptionDetailPage,
  validateSearch: searchSchema,
  head: () => ({
    meta: [{ title: "Bilibili Subscription - FastAPI Template" }],
  }),
})

function SubscriptionDetailPage() {
  const { subscriptionId } = Route.useParams()
  const { type: resourceType, page } = Route.useSearch()
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid")
  const pageSize = 20

  const updateSearch = (patch: Partial<z.infer<typeof searchSchema>>) => {
    navigate({ search: (prev) => ({ ...prev, ...patch }) })
  }
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: subscription } = useQuery({
    queryFn: () => bilibiliApi.getSubscription(subscriptionId),
    queryKey: ["bilibili-subscription", subscriptionId],
  })
  const retryFailed = useMutation({
    mutationFn: bilibiliApi.retryFailedResources,
    onError: handleError.bind(showErrorToast),
    onSuccess: (result) => {
      showSuccessToast(
        `重试完成：成功 ${result.success}，失败 ${result.failed}`,
      )
      queryClient.invalidateQueries({
        queryKey: ["bilibili-sync-logs", subscriptionId],
      })
      queryClient.invalidateQueries({
        queryKey: ["bilibili-resource-counts", subscriptionId],
      })
      queryClient.invalidateQueries({
        queryKey: ["bilibili-failed-resources", subscriptionId],
      })
    },
  })
  const { data: resourcesData, isPending } = useQuery({
    queryFn: () =>
      bilibiliApi.getResources({
        subscription_id: subscriptionId,
        resource_type: resourceType === "failed" ? undefined : resourceType,
        keyword: keyword || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        page,
        page_size: pageSize,
      }),
    queryKey: [
      "bilibili-resources",
      subscriptionId,
      resourceType,
      keyword,
      startDate,
      endDate,
      page,
    ],
    enabled: resourceType !== "failed",
  })

  const resources = resourcesData?.resources ?? []
  const total = resourcesData?.total ?? 0

  const { data: resourceCounts = { article: 0, dynamic: 0, video: 0 } } =
    useQuery({
      queryFn: () => bilibiliApi.getResourceCounts(subscriptionId),
      queryKey: ["bilibili-resource-counts", subscriptionId],
    })

  const { data: failedResources = [] } = useQuery({
    queryFn: () => bilibiliApi.getFailedResources(subscriptionId),
    queryKey: ["bilibili-failed-resources", subscriptionId],
  })

  // 搜索时重置到第一页
  const handleSearch = (value: string) => {
    setKeyword(value)
    updateSearch({ page: 1 })
  }

  // 计算总页数
  const totalPages = Math.ceil(total / pageSize)

  // 切换标签时重置页码
  const handleTabChange = (value: string) => {
    updateSearch({ type: value as "video" | "dynamic" | "article" | "failed", page: 1 })
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" asChild className="mb-2 px-0">
            <Link to="/bilibili/subscriptions">
              <ArrowLeft className="mr-2 size-4" />
              返回订阅
            </Link>
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">
            {subscription?.uploader_name ?? "订阅详情"}
          </h1>
          <p className="text-muted-foreground">
            UID {subscription?.uploader_uid ?? subscriptionId}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>UP 主信息</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-4">
                {subscription?.uploader_avatar ? (
                  <img
                    alt={subscription.uploader_name}
                    className="size-16 rounded-full object-cover"
                    src={bilibiliApi.proxiedImageUrl(
                      subscription.uploader_avatar,
                    )}
                  />
                ) : null}
                <div>
                  <a
                    className="font-semibold underline-offset-4 hover:underline"
                    href={`https://space.bilibili.com/${subscription?.uploader_uid}`}
                    rel="noreferrer"
                    target="_blank"
                  >
                    {subscription?.uploader_name ?? "UP 主"}
                  </a>
                  <p className="text-sm text-muted-foreground">
                    UID {subscription?.uploader_uid}
                  </p>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                {typeof subscription?.uploader_info.description === "string"
                  ? subscription.uploader_info.description
                  : "暂无简介"}
              </p>
              <Button variant="outline" size="sm" asChild>
                <a
                  href={`https://space.bilibili.com/${subscription?.uploader_uid}`}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink className="mr-2 size-4" />
                  打开 B站主页
                </a>
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>同步配置</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex flex-wrap gap-2">
                {subscription?.sync_config.resource_types.map((type) => (
                  <Badge key={type} variant="secondary">
                    {type === "video"
                      ? "视频"
                      : type === "dynamic"
                        ? "动态"
                        : "专栏"}
                  </Badge>
                ))}
              </div>
              <p>频率：{subscription?.sync_config.sync_frequency}</p>
              <p>批大小：{subscription?.sync_config.batch_size}</p>
              <p>
                上次同步成功：
                {subscription?.last_sync_at
                  ? new Date(subscription.last_sync_at).toLocaleString()
                  : "暂无"}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>统计</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-4 gap-2 text-center text-sm">
              <div className="rounded-md bg-muted p-3">
                <p className="text-lg font-semibold">{resourceCounts.video}</p>
                <p className="text-muted-foreground">视频</p>
              </div>
              <div className="rounded-md bg-muted p-3">
                <p className="text-lg font-semibold">
                  {resourceCounts.dynamic}
                </p>
                <p className="text-muted-foreground">动态</p>
              </div>
              <div className="rounded-md bg-muted p-3">
                <p className="text-lg font-semibold">
                  {resourceCounts.article}
                </p>
                <p className="text-muted-foreground">专栏</p>
              </div>
              <div className="rounded-md bg-muted p-3">
                <p className="text-lg font-semibold">
                  {failedResources.length}
                </p>
                <p className="text-muted-foreground">失败</p>
              </div>
              <Button
                className="col-span-4"
                disabled={retryFailed.isPending || failedResources.length === 0}
                onClick={() => retryFailed.mutate(subscriptionId)}
                variant="outline"
              >
                <RotateCcw className="mr-2 size-4" />
                重试失败资源 {failedResources.length > 0 ? `(${failedResources.length})` : ""}
              </Button>
            </CardContent>
          </Card>
        </div>

        <div>
          <div className="mb-4 grid gap-3 md:grid-cols-3">
            <Input
              placeholder="搜索标题和内容"
              value={keyword}
              onChange={(event) => handleSearch(event.target.value)}
            />
            <Input
              type="date"
              value={startDate}
              onChange={(event) => {
                setStartDate(event.target.value)
                updateSearch({ page: 1 })
              }}
            />
            <Input
              type="date"
              value={endDate}
              onChange={(event) => {
                setEndDate(event.target.value)
                updateSearch({ page: 1 })
              }}
            />
          </div>
          <Tabs
            value={resourceType}
            onValueChange={handleTabChange}
          >
            <div className="mb-4 flex items-center justify-between">
              <TabsList>
                <TabsTrigger value="video">
                  视频 ({resourceCounts.video})
                </TabsTrigger>
                <TabsTrigger value="dynamic">
                  动态 ({resourceCounts.dynamic})
                </TabsTrigger>
                <TabsTrigger value="article">
                  专栏 ({resourceCounts.article})
                </TabsTrigger>
                <TabsTrigger value="failed">
                  失败 ({failedResources.length})
                </TabsTrigger>
              </TabsList>
              {resourceType !== "failed" ? (
                <div className="flex items-center gap-1 rounded-lg border p-1">
                  <Button
                    size="sm"
                    variant={viewMode === "grid" ? "default" : "ghost"}
                    className="size-8 p-0"
                    onClick={() => setViewMode("grid")}
                  >
                    <LayoutGrid className="size-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant={viewMode === "list" ? "default" : "ghost"}
                    className="size-8 p-0"
                    onClick={() => setViewMode("list")}
                  >
                    <List className="size-4" />
                  </Button>
                </div>
              ) : null}
            </div>
            <TabsContent value={resourceType} className="mt-4">
              {resourceType === "failed" ? (
                <FailedResourceList subscriptionId={subscriptionId} />
              ) : (
                <>
                  {isPending ? (
                    <p className="text-muted-foreground">加载资源中...</p>
                  ) : null}
                  {!isPending && resources.length === 0 ? (
                    <p className="rounded-lg border py-12 text-center text-sm text-muted-foreground">
                      暂无资源
                    </p>
                  ) : null}
                  {resources.length > 0 ? (
                    viewMode === "grid" ? (
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {resources.map((resource) => (
                          <ResourceCard key={resource.id} resource={resource} />
                        ))}
                      </div>
                    ) : (
                      <div className="divide-y rounded-lg border">
                        {resources.map((resource) => {
                          const url =
                            typeof resource.resource_meta?.url === "string"
                              ? resource.resource_meta.url
                              : null
                          return (
                            <a
                              key={resource.id}
                              href={url ?? undefined}
                              target="_blank"
                              rel="noreferrer"
                              className={`flex items-center gap-4 px-4 py-3 hover:bg-muted/50 ${url ? "cursor-pointer" : "pointer-events-none"}`}
                            >
                              {resource.cover_url ? (
                                <img
                                  src={bilibiliApi.proxiedImageUrl(resource.cover_url)}
                                  alt={resource.title}
                                  className="size-12 flex-shrink-0 rounded object-cover"
                                />
                              ) : (
                                <div className="size-12 flex-shrink-0 rounded bg-muted" />
                              )}
                              <div className="min-w-0 flex-1">
                                <p className="truncate font-medium">
                                  {resource.title}
                                </p>
                                <p className="truncate text-xs text-muted-foreground">
                                  {resource.summary}
                                </p>
                              </div>
                              <Badge variant="secondary" className="flex-shrink-0">
                                {resource.resource_type === "video"
                                  ? "视频"
                                  : resource.resource_type === "dynamic"
                                    ? "动态"
                                    : "专栏"}
                              </Badge>
                              <span className="flex-shrink-0 text-xs text-muted-foreground">
                                {new Date(resource.published_at).toLocaleString()}
                              </span>
                              {url ? (
                                <ExternalLink className="size-4 flex-shrink-0 text-muted-foreground" />
                              ) : null}
                            </a>
                          )
                        })}
                      </div>
                    )
                  ) : null}
                  {resources.length > 0 && totalPages >= 1 ? (
                    <PaginationBar
                      page={page}
                      totalPages={totalPages}
                      total={total}
                      onPageChange={(p) => updateSearch({ page: p })}
                    />
                  ) : null}
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  )
}
