import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"

export const Route = createFileRoute("/_layout/bilibili")({
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    const permissions = user.permissions ?? []
    const canAccess =
      user.is_superuser ||
      permissions.includes("*") ||
      permissions.some((permission) => permission.startsWith("bilibili:"))

    if (!canAccess) {
      throw redirect({ to: "/" })
    }
  },
  component: Outlet,
  head: () => ({
    meta: [{ title: "Bilibili - FastAPI Template" }],
  }),
})
