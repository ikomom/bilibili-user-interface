import { createFileRoute } from "@tanstack/react-router"

import { AdminIndexPage } from "../admin"

export const Route = createFileRoute("/_layout/admin/")({
  component: AdminIndexPage,
})
