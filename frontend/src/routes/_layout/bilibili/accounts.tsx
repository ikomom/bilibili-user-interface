import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Plus, Trash2 } from "lucide-react"
import { useState } from "react"

import { AccountForm } from "@/components/bilibili/AccountForm"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"
import { bilibiliApi } from "@/lib/api/bilibili"
import type { BilibiliAccount } from "@/types/bilibili"
import { handleError } from "@/utils"

const authTypeText = {
  cookie: "Cookie",
  qrcode: "扫码登录",
  sessdata: "SESSDATA",
}

export const Route = createFileRoute("/_layout/bilibili/accounts")({
  component: AccountsPage,
  head: () => ({
    meta: [{ title: "Bilibili Accounts - FastAPI Template" }],
  }),
})

function AccountsPage() {
  const [formOpen, setFormOpen] = useState(false)
  const [editingAccount, setEditingAccount] = useState<BilibiliAccount | null>(
    null,
  )
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: accounts = [], isPending } = useQuery({
    queryFn: bilibiliApi.getAccounts,
    queryKey: ["bilibili-accounts"],
  })

  const deleteAccount = useMutation({
    mutationFn: bilibiliApi.deleteAccount,
    onSuccess: () => {
      showSuccessToast("账户已删除")
      queryClient.invalidateQueries({ queryKey: ["bilibili-accounts"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">B站账户</h1>
          <p className="text-muted-foreground">管理用于同步的 B站登录凭证。</p>
        </div>
        <Button
          onClick={() => {
            setEditingAccount(null)
            setFormOpen(true)
          }}
        >
          <Plus className="mr-2 size-4" />
          添加账户
        </Button>
      </div>

      <AccountForm
        account={editingAccount}
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open)
          if (!open) setEditingAccount(null)
        }}
      />

      {isPending ? (
        <p className="text-muted-foreground">加载账户中...</p>
      ) : null}

      {!isPending && accounts.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>暂无账户</CardTitle>
            <CardDescription>
              添加一个 B站账户后即可创建 UP 主订阅。
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {accounts.map((account) => (
          <Card key={account.id}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>{account.account_name}</CardTitle>
                  <CardDescription>
                    认证方式：{authTypeText[account.auth_type]}
                  </CardDescription>
                </div>
                <Badge variant={account.is_active ? "default" : "secondary"}>
                  {account.is_active ? "可用" : "停用"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex items-center justify-between gap-3">
              <span className="text-sm text-muted-foreground">
                创建于{" "}
                {account.created_at
                  ? new Date(account.created_at).toLocaleDateString()
                  : "未知"}
              </span>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setEditingAccount(account)
                    setFormOpen(true)
                  }}
                >
                  <Pencil className="mr-2 size-4" />
                  编辑
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  disabled={deleteAccount.isPending}
                  onClick={() => {
                    if (
                      window.confirm(
                        `确定删除账户「${account.account_name}」吗？`,
                      )
                    ) {
                      deleteAccount.mutate(account.id)
                    }
                  }}
                >
                  <Trash2 className="mr-2 size-4" />
                  删除
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
