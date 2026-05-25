import type { ColumnDef } from "@tanstack/react-table"

import type { UserPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserPublic & {
  isCurrentUser: boolean
}

export const columns: ColumnDef<UserTableData>[] = [
  {
    accessorKey: "full_name",
    header: "Full Name",
    cell: ({ row }) => {
      const fullName = row.original.full_name
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn("font-medium", !fullName && "text-muted-foreground")}
          >
            {fullName || "N/A"}
          </span>
          {row.original.isCurrentUser && (
            <Badge variant="outline" className="text-xs">
              You
            </Badge>
          )}
        </div>
      )
    },
  },
  {
    accessorKey: "email",
    header: "Email",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.email}</span>
    ),
  },
  {
    accessorKey: "is_superuser",
    header: "Role",
    cell: ({ row }) => (
      <Badge variant={row.original.is_superuser ? "default" : "secondary"}>
        {row.original.is_superuser ? "Superuser" : "User"}
      </Badge>
    ),
  },
  {
    accessorKey: "permissions",
    header: "Permissions",
    cell: ({ row }) => {
      const permissions = row.original.permissions ?? []
      if (row.original.is_superuser || permissions.includes("*")) {
        return <Badge variant="default">All permissions</Badge>
      }

      return (
        <div className="flex max-w-xs flex-wrap gap-1">
          {permissions.length ? (
            permissions.slice(0, 3).map((permission) => (
              <Badge key={permission} variant="outline" className="text-xs">
                {permission}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground">No roles</span>
          )}
          {permissions.length > 3 ? (
            <Badge variant="secondary" className="text-xs">
              +{permissions.length - 3}
            </Badge>
          ) : null}
        </div>
      )
    },
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 rounded-full",
            row.original.is_active ? "bg-green-500" : "bg-gray-400",
          )}
        />
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
          {row.original.is_active ? "Active" : "Inactive"}
        </span>
      </div>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]
