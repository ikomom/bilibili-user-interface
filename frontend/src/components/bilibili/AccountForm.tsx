import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { BilibiliAccount } from "@/types/bilibili"
import { handleError } from "@/utils"
import { QRCodeDisplay } from "./QRCodeDisplay"

const formSchema = z.object({
  account_name: z.string().min(1, "请输入账户名称"),
  cookie: z.string().optional(),
  sessdata: z.string().optional(),
  bili_jct: z.string().optional(),
  buvid3: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

interface AccountFormProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  account?: BilibiliAccount | null
}

export function AccountForm({ open, onOpenChange, account }: AccountFormProps) {
  const [authType, setAuthType] = useState<"cookie" | "sessdata" | "qrcode">(
    "cookie",
  )
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      account_name: "",
      cookie: "",
      sessdata: "",
      bili_jct: "",
      buvid3: "",
    },
  })

  const createAccount = useMutation({
    mutationFn: bilibiliApi.createAccount,
    onSuccess: () => {
      showSuccessToast("B站账户已添加")
      form.reset()
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["bilibili-accounts"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const updateAccount = useMutation({
    mutationFn: (data: {
      id: string
      body: Parameters<typeof bilibiliApi.updateAccount>[1]
    }) => bilibiliApi.updateAccount(data.id, data.body),
    onSuccess: () => {
      showSuccessToast("B站账户已更新")
      form.reset()
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["bilibili-accounts"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  useEffect(() => {
    if (!open) return
    form.reset({
      account_name: account?.account_name ?? "",
      cookie: "",
      sessdata: "",
      bili_jct: "",
      buvid3: "",
    })
    setAuthType(account?.auth_type ?? "cookie")
  }, [account, form, open])

  const onSubmit = (data: FormData) => {
    if (!account && authType === "cookie" && !data.cookie?.trim()) {
      form.setError("cookie", { message: "请输入 Cookie" })
      return
    }

    if (!account && authType === "sessdata" && !data.sessdata?.trim()) {
      form.setError("sessdata", { message: "请输入 SESSDATA" })
      return
    }

    if (!account && authType === "sessdata" && !data.bili_jct?.trim()) {
      form.setError("bili_jct", { message: "请输入 bili_jct" })
      return
    }

    const credentials =
      authType === "cookie"
        ? { cookie: data.cookie?.trim() }
        : {
            sessdata: data.sessdata?.trim(),
            bili_jct: data.bili_jct?.trim(),
            buvid3: data.buvid3?.trim(),
          }

    if (account) {
      updateAccount.mutate({
        id: account.id,
        body: {
          account_name: data.account_name,
          auth_type: authType,
          ...(data.cookie || data.sessdata ? { credentials } : {}),
        },
      })
    } else {
      createAccount.mutate({
        account_name: data.account_name,
        auth_type: authType,
        credentials,
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{account ? "编辑 B站账户" : "添加 B站账户"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <FormField
              control={form.control}
              name="account_name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>账户名称</FormLabel>
                  <FormControl>
                    <Input placeholder="例如：主账号" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Tabs
              value={authType}
              onValueChange={(value) => setAuthType(value as typeof authType)}
            >
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="cookie">Cookie</TabsTrigger>
                <TabsTrigger value="sessdata">SESSDATA</TabsTrigger>
                <TabsTrigger value="qrcode">扫码登录</TabsTrigger>
              </TabsList>
              <TabsContent value="cookie" className="mt-4">
                <FormField
                  control={form.control}
                  name="cookie"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Cookie 字符串</FormLabel>
                      <FormControl>
                        <textarea
                          className="min-h-28 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
                          placeholder="粘贴完整 Cookie"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>
              <TabsContent value="sessdata" className="mt-4 space-y-4">
                <FormField
                  control={form.control}
                  name="sessdata"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>SESSDATA</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="bili_jct"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>bili_jct</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="buvid3"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>buvid3</FormLabel>
                      <FormControl>
                        <Input {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </TabsContent>
              <TabsContent value="qrcode" className="mt-4">
                <QRCodeDisplay onSuccess={() => onOpenChange(false)} />
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                取消
              </Button>
              {authType !== "qrcode" ? (
                <LoadingButton
                  type="submit"
                  loading={createAccount.isPending || updateAccount.isPending}
                >
                  {account ? "保存修改" : "保存账户"}
                </LoadingButton>
              ) : null}
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
