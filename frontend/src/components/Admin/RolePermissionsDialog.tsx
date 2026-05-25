import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ShieldCheck } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import useCustomToast from "@/hooks/useCustomToast"
import { adminApi } from "@/lib/api/admin"
import type { Permission } from "@/types/rbac"
import { handleError } from "@/utils"

interface RolePermissionsDialogProps {
  roleId: string
}

function groupPermissions(permissions: Permission[]) {
  return permissions.reduce<Record<string, Permission[]>>(
    (groups, permission) => {
      groups[permission.module] = [
        ...(groups[permission.module] ?? []),
        permission,
      ]
      return groups
    },
    {},
  )
}

export function RolePermissionsDialog({ roleId }: RolePermissionsDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()
  const { data: role } = useQuery({
    queryFn: () => adminApi.getRole(roleId),
    queryKey: ["rbac-role", roleId],
    enabled: open,
  })
  const { data: permissions = [] } = useQuery({
    queryFn: () => adminApi.getPermissions(),
    queryKey: ["rbac-permissions"],
    enabled: open,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["rbac-role", roleId] })
    queryClient.invalidateQueries({ queryKey: ["rbac-roles"] })
  }
  const assignPermission = useMutation({
    mutationFn: (permissionId: string) =>
      adminApi.assignPermissionToRole(roleId, permissionId),
    onSuccess: invalidate,
    onError: handleError.bind(showErrorToast),
  })
  const removePermission = useMutation({
    mutationFn: (permissionId: string) =>
      adminApi.removePermissionFromRole(roleId, permissionId),
    onSuccess: invalidate,
    onError: handleError.bind(showErrorToast),
  })
  const selectedIds = new Set(
    role?.permissions?.map((permission) => permission.id),
  )
  const permissionsByModule = groupPermissions(permissions)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <ShieldCheck className="mr-2 size-4" />
          管理权限
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>管理角色权限：{role?.name ?? "加载中"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-5">
          {Object.entries(permissionsByModule).map(
            ([module, modulePermissions]) => (
              <section key={module} className="space-y-3 rounded-lg border p-4">
                <Badge variant="secondary">{module}</Badge>
                <div className="grid gap-3 md:grid-cols-2">
                  {modulePermissions.map((permission) => (
                    <div
                      key={permission.id}
                      className="flex items-start gap-3 rounded-md border p-3 text-sm"
                    >
                      <Checkbox
                        checked={selectedIds.has(permission.id)}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            assignPermission.mutate(permission.id)
                          } else {
                            removePermission.mutate(permission.id)
                          }
                        }}
                      />
                      <span>
                        <span className="font-medium">{permission.name}</span>
                        <code className="mt-1 block text-xs text-muted-foreground">
                          {permission.code}
                        </code>
                      </span>
                    </div>
                  ))}
                </div>
              </section>
            ),
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
