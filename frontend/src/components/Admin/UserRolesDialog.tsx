import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import type { UserPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { adminApi } from "@/lib/api/admin"
import { handleError } from "@/utils"

interface UserRolesDialogProps {
  user: UserPublic
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function UserRolesDialog({
  user,
  open,
  onOpenChange,
}: UserRolesDialogProps) {
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { data: roles = [] } = useQuery({
    queryFn: adminApi.getRoles,
    queryKey: ["rbac-roles"],
    enabled: open,
  })
  const { data: userRoles = [] } = useQuery({
    queryFn: () => adminApi.getUserRoles(user.id),
    queryKey: ["rbac-user-roles", user.id],
    enabled: open,
  })
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["rbac-user-roles", user.id] })
  const assignRole = useMutation({
    mutationFn: (roleId: string) => adminApi.assignRoleToUser(user.id, roleId),
    onSuccess: invalidate,
    onError: handleError.bind(showErrorToast),
  })
  const removeRole = useMutation({
    mutationFn: (roleId: string) =>
      adminApi.removeRoleFromUser(user.id, roleId),
    onSuccess: invalidate,
    onError: handleError.bind(showErrorToast),
  })
  const selectedIds = new Set(userRoles.map((role) => role.id))
  const permissions = userRoles.flatMap((role) => role.permissions ?? [])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>管理用户角色：{user.email}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2">
            {roles.map((role) => (
              <div
                key={role.id}
                className="flex items-start gap-3 rounded-md border p-3 text-sm"
              >
                <Checkbox
                  checked={selectedIds.has(role.id)}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      assignRole.mutate(role.id)
                    } else {
                      removeRole.mutate(role.id)
                    }
                  }}
                />
                <span>
                  <span className="font-medium">{role.name}</span>
                  <span className="block text-xs text-muted-foreground">
                    {role.description ?? "无描述"}
                  </span>
                </span>
              </div>
            ))}
          </div>
          <div className="space-y-2 rounded-lg border p-4">
            <h3 className="text-sm font-medium">当前权限预览</h3>
            <div className="flex flex-wrap gap-2">
              {permissions.length ? (
                permissions.map((permission) => (
                  <Badge key={permission.code} variant="secondary">
                    {permission.name}
                  </Badge>
                ))
              ) : (
                <span className="text-sm text-muted-foreground">暂无权限</span>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
