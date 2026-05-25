import { createFileRoute, Link } from "@tanstack/react-router"
import { RadioTower, UserRoundCog } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export const Route = createFileRoute("/_layout/bilibili/")({
  component: BilibiliHome,
  head: () => ({
    meta: [{ title: "Bilibili - FastAPI Template" }],
  }),
})

function BilibiliHome() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Bilibili 内容同步</h1>
        <p className="text-muted-foreground">
          管理 B站账户、UP 主订阅和同步资源。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-blue-500/20 bg-blue-500/5">
          <CardHeader>
            <UserRoundCog className="size-8 text-blue-500" />
            <CardTitle>账户管理</CardTitle>
            <CardDescription>
              添加 Cookie 或 SESSDATA 凭证，用于访问 B站接口。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to="/bilibili/accounts">管理账户</Link>
            </Button>
          </CardContent>
        </Card>

        <Card className="border-pink-500/20 bg-pink-500/5">
          <CardHeader>
            <RadioTower className="size-8 text-pink-500" />
            <CardTitle>UP 主订阅</CardTitle>
            <CardDescription>
              订阅 UP 主并手动或定时同步视频、动态和专栏。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="secondary">
              <Link to="/bilibili/subscriptions">管理订阅</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
