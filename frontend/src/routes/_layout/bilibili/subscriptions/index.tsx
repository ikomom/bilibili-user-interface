import { createFileRoute } from "@tanstack/react-router"

import { SubscriptionsPage } from "@/routes/_layout/bilibili/subscriptions"

export const Route = createFileRoute("/_layout/bilibili/subscriptions/")({
  component: SubscriptionsPage,
  head: () => ({
    meta: [{ title: "Bilibili Subscriptions - FastAPI Template" }],
  }),
})
