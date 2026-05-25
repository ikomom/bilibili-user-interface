import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { BilibiliSubscription } from "@/types/bilibili"
import { handleError } from "@/utils"

const formSchema = z.object({
  account_id: z.string().min(1, "请选择账户"),
  uploader_uid: z.string().min(1, "请输入 UP 主 UID"),
  resource_video: z.boolean(),
  resource_dynamic: z.boolean(),
  resource_article: z.boolean(),
  sync_frequency: z.enum(["1h", "6h", "1d", "1w", "manual"]),
  history_mode: z.enum(["none", "recent", "all"]),
  history_limit: z.string(),
  batch_size: z.string().min(1, "请输入批大小"),
})

type FormData = z.infer<typeof formSchema>

interface SubscriptionFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  subscription?: BilibiliSubscription | null
}

export function SubscriptionForm({
  open,
  onOpenChange,
  subscription,
}: SubscriptionFormProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: accounts = [] } = useQuery({
    queryFn: bilibiliApi.getAccounts,
    queryKey: ["bilibili-accounts"],
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      account_id: "",
      uploader_uid: "",
      resource_video: true,
      resource_dynamic: true,
      resource_article: true,
      sync_frequency: "6h",
      history_mode: "recent",
      history_limit: "50",
      batch_size: "50",
    },
  })
  const historyMode = form.watch("history_mode")

  useEffect(() => {
    if (!open) return

    const historyLimit = subscription?.sync_config.history_limit
    form.reset({
      account_id: subscription?.account_id ?? "",
      uploader_uid: subscription?.uploader_uid ?? "",
      resource_video:
        subscription?.sync_config.resource_types.includes("video") ?? true,
      resource_dynamic:
        subscription?.sync_config.resource_types.includes("dynamic") ?? true,
      resource_article:
        subscription?.sync_config.resource_types.includes("article") ?? true,
      sync_frequency: subscription?.sync_config.sync_frequency ?? "6h",
      history_mode:
        historyLimit === null ? "all" : historyLimit === 0 ? "none" : "recent",
      history_limit: String(
        historyLimit && historyLimit > 0 ? historyLimit : 50,
      ),
      batch_size: String(subscription?.sync_config.batch_size ?? 50),
    })
  }, [form, open, subscription])

  const createSubscription = useMutation({
    mutationFn: bilibiliApi.createSubscription,
    onSuccess: () => {
      showSuccessToast("订阅已创建")
      form.reset()
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["bilibili-subscriptions"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const updateSubscription = useMutation({
    mutationFn: (data: {
      id: string
      body: Parameters<typeof bilibiliApi.updateSubscription>[1]
    }) => bilibiliApi.updateSubscription(data.id, data.body),
    onSuccess: (updated) => {
      showSuccessToast("订阅已更新")
      form.reset()
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["bilibili-subscriptions"] })
      queryClient.invalidateQueries({
        queryKey: ["bilibili-subscription", updated.id],
      })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = (data: FormData) => {
    const historyLimit = Number(data.history_limit)
    const batchSize = Number(data.batch_size)
    const resourceTypes = [
      data.resource_video ? "video" : null,
      data.resource_dynamic ? "dynamic" : null,
      data.resource_article ? "article" : null,
    ].filter(Boolean) as Array<"video" | "dynamic" | "article">

    if (resourceTypes.length === 0) {
      form.setError("resource_video", { message: "至少选择一种资源类型" })
      return
    }

    if (
      data.history_mode === "recent" &&
      (!Number.isInteger(historyLimit) ||
        historyLimit < 1 ||
        historyLimit > 500)
    ) {
      form.setError("history_limit", { message: "历史数量必须是 1-500 的整数" })
      return
    }

    if (!Number.isInteger(batchSize) || batchSize < 1 || batchSize > 100) {
      form.setError("batch_size", { message: "批大小必须是 1-100 的整数" })
      return
    }

    const syncConfig = {
      resource_types: resourceTypes,
      sync_frequency: data.sync_frequency,
      history_limit:
        data.history_mode === "all"
          ? null
          : data.history_mode === "none"
            ? 0
            : historyLimit,
      batch_size: batchSize,
    }

    if (subscription) {
      updateSubscription.mutate({
        id: subscription.id,
        body: {
          account_id: data.account_id,
          sync_config: syncConfig,
        },
      })
    } else {
      createSubscription.mutate({
        account_id: data.account_id,
        uploader_uid: data.uploader_uid,
        sync_config: syncConfig,
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {subscription ? "编辑 UP 主订阅" : "添加 UP 主订阅"}
          </DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="account_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>B站账户</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="选择用于同步的账户" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {accounts.map((account) => (
                        <SelectItem key={account.id} value={account.id}>
                          {account.account_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="uploader_uid"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>UP 主 UID</FormLabel>
                  <FormControl>
                    <Input
                      disabled={Boolean(subscription)}
                      placeholder="例如：123456"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2 sm:col-span-3">
                <FormLabel>资源类型</FormLabel>
                <div className="flex flex-wrap gap-4 rounded-md border p-3 text-sm">
                  <FormField
                    control={form.control}
                    name="resource_video"
                    render={({ field }) => (
                      <FormItem className="flex items-center gap-2 space-y-0">
                        <FormControl>
                          <Input
                            checked={field.value}
                            className="size-4"
                            onChange={(event) =>
                              field.onChange(event.target.checked)
                            }
                            type="checkbox"
                          />
                        </FormControl>
                        <FormLabel className="font-normal">视频</FormLabel>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="resource_dynamic"
                    render={({ field }) => (
                      <FormItem className="flex items-center gap-2 space-y-0">
                        <FormControl>
                          <Input
                            checked={field.value}
                            className="size-4"
                            onChange={(event) =>
                              field.onChange(event.target.checked)
                            }
                            type="checkbox"
                          />
                        </FormControl>
                        <FormLabel className="font-normal">动态</FormLabel>
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="resource_article"
                    render={({ field }) => (
                      <FormItem className="flex items-center gap-2 space-y-0">
                        <FormControl>
                          <Input
                            checked={field.value}
                            className="size-4"
                            onChange={(event) =>
                              field.onChange(event.target.checked)
                            }
                            type="checkbox"
                          />
                        </FormControl>
                        <FormLabel className="font-normal">专栏</FormLabel>
                      </FormItem>
                    )}
                  />
                </div>
                <FormMessage />
              </div>
              <FormField
                control={form.control}
                name="sync_frequency"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>同步频率</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="1h">每小时</SelectItem>
                        <SelectItem value="6h">每 6 小时</SelectItem>
                        <SelectItem value="1d">每天</SelectItem>
                        <SelectItem value="1w">每周</SelectItem>
                        <SelectItem value="manual">手动</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="history_mode"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>首次同步</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="none">不同步历史</SelectItem>
                        <SelectItem value="recent">最近 N 条</SelectItem>
                        <SelectItem value="all">全量同步</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="history_limit"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>历史数量</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        disabled={historyMode !== "recent"}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="batch_size"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>批大小</FormLabel>
                    <FormControl>
                      <Input type="number" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
            {historyMode === "all" ? (
              <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700">
                全量同步可能耗时较长，并触发较多 B站接口请求，请确认后再提交。
              </p>
            ) : null}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                取消
              </Button>
              <LoadingButton
                type="submit"
                loading={
                  createSubscription.isPending || updateSubscription.isPending
                }
              >
                {subscription ? "保存修改" : "创建订阅"}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
