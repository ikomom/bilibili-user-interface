import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { adminApi } from "@/lib/api/admin"

export const Route = createFileRoute("/_layout/admin/permissions")({
  component: PermissionsPage,
  head: () => ({
    meta: [{ title: "Admin Permissions - FastAPI Template" }],
  }),
})

function PermissionsPage() {
  const [selectedModule, setSelectedModule] = useState("all")
  const { data: allPermissions = [] } = useQuery({
    queryFn: () => adminApi.getPermissions(),
    queryKey: ["rbac-permissions"],
  })
  const modules = Array.from(
    new Set(allPermissions.map((permission) => permission.module)),
  )
  const permissions =
    selectedModule === "all"
      ? allPermissions
      : allPermissions.filter(
          (permission) => permission.module === selectedModule,
        )

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">权限列表</h1>
        <p className="text-muted-foreground">查看系统中所有权限代码。</p>
      </div>

      <Tabs value={selectedModule} onValueChange={setSelectedModule}>
        <TabsList>
          <TabsTrigger value="all">全部</TabsTrigger>
          {modules.map((module) => (
            <TabsTrigger key={module} value={module}>
              {module}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>权限代码</TableHead>
            <TableHead>名称</TableHead>
            <TableHead>模块</TableHead>
            <TableHead>描述</TableHead>
            <TableHead>关联角色</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {permissions.map((permission) => (
            <TableRow key={permission.id}>
              <TableCell>
                <code className="rounded bg-muted px-2 py-1 text-xs">
                  {permission.code}
                </code>
              </TableCell>
              <TableCell className="font-medium">{permission.name}</TableCell>
              <TableCell>
                <Badge variant="secondary">{permission.module}</Badge>
              </TableCell>
              <TableCell>{permission.description ?? "-"}</TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-1">
                  {permission.roles?.length ? (
                    permission.roles.map((role) => (
                      <Badge key={role.id} variant="outline">
                        {role.name}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
