import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { UsersPage } from "./admin/users"

export const Route = createFileRoute("/_layout/admin")({
  component: AdminLayout,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user?.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "Admin - FastAPI Template",
      },
    ],
  }),
})

function AdminLayout() {
  return <Outlet />
}

export function AdminIndexPage() {
  return <UsersPage />
}
