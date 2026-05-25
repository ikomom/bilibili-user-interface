import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Pencil, Trash2 } from "lucide-react"
import { useState } from "react"

import { CreateRoleDialog } from "@/components/Admin/CreateRoleDialog"
import { RolePermissionsDialog } from "@/components/Admin/RolePermissionsDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import useCustomToast from "@/hooks/useCustomToast"
import { adminApi } from "@/lib/api/admin"
import type { Role } from "@/types/rbac"
import { handleError } from "@/utils"

export const Route = createFileRoute("/_layout/admin/roles")({
  component: RolesPage,
  head: () => ({
    meta: [{ title: "Admin Roles - FastAPI Template" }],
  }),
})

function RolesPage() {
  const [editingRole, setEditingRole] = useState<Role | null>(null)
  const [roleName, setRoleName] = useState("")
  const [roleDescription, setRoleDescription] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: roles = [], isPending } = useQuery({
    queryFn: adminApi.getRoles,
    queryKey: ["rbac-roles"],
  })
  const deleteRole = useMutation({
    mutationFn: adminApi.deleteRole,
    onSuccess: () => {
      showSuccessToast("角色已删除")
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] })
    },
    onError: handleError.bind(showErrorToast),
  })
  const updateRole = useMutation({
    mutationFn: (data: { id: string; name: string; description: string }) =>
      adminApi.updateRole(data.id, {
        name: data.name,
        description: data.description,
      }),
    onSuccess: () => {
      showSuccessToast("角色已更新")
      setEditingRole(null)
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">角色管理</h1>
          <p className="text-muted-foreground">创建角色并分配权限。</p>
        </div>
        <CreateRoleDialog />
      </div>

      <Dialog
        open={Boolean(editingRole)}
        onOpenChange={(open) => !open && setEditingRole(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑角色</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Input
              placeholder="角色名"
              value={roleName}
              onChange={(event) => setRoleName(event.target.value)}
            />
            <Input
              placeholder="描述"
              value={roleDescription}
              onChange={(event) => setRoleDescription(event.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingRole(null)}>
              取消
            </Button>
            <Button
              disabled={!roleName.trim() || updateRole.isPending}
              onClick={() =>
                editingRole &&
                updateRole.mutate({
                  id: editingRole.id,
                  name: roleName.trim(),
                  description: roleDescription.trim(),
                })
              }
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {isPending ? (
        <p className="text-muted-foreground">加载角色中...</p>
      ) : null}

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>角色名</TableHead>
            <TableHead>描述</TableHead>
            <TableHead>权限数量</TableHead>
            <TableHead>类型</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {roles.map((role) => (
            <TableRow key={role.id}>
              <TableCell className="font-medium">{role.name}</TableCell>
              <TableCell>{role.description ?? "-"}</TableCell>
              <TableCell>
                {role.permission_count ?? role.permissions?.length ?? 0}
              </TableCell>
              <TableCell>
                <Badge variant={role.is_system ? "default" : "secondary"}>
                  {role.is_system ? "系统" : "自定义"}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="flex gap-2">
                  <RolePermissionsDialog roleId={role.id} />
                  {!role.is_system ? (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingRole(role)
                          setRoleName(role.name)
                          setRoleDescription(role.description ?? "")
                        }}
                      >
                        <Pencil className="mr-2 size-4" />
                        编辑
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => deleteRole.mutate(role.id)}
                      >
                        <Trash2 className="mr-2 size-4" />
                        删除
                      </Button>
                    </>
                  ) : null}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
