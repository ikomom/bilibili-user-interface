import {
  Briefcase,
  Home,
  KeyRound,
  RadioTower,
  ShieldCheck,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "Dashboard", path: "/" },
  { icon: Briefcase, title: "Items", path: "/items" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const permissions = currentUser?.permissions ?? []
  const hasBilibiliAccess =
    currentUser?.is_superuser ||
    permissions.includes("*") ||
    permissions.some((permission) => permission.startsWith("bilibili:"))
  const visibleBaseItems = hasBilibiliAccess
    ? [...baseItems, { icon: RadioTower, title: "Bilibili", path: "/bilibili" }]
    : baseItems

  const items = currentUser?.is_superuser
    ? [
        ...visibleBaseItems,
        { icon: Users, title: "Users", path: "/admin/users" },
        { icon: ShieldCheck, title: "Roles", path: "/admin/roles" },
        { icon: KeyRound, title: "Permissions", path: "/admin/permissions" },
      ]
    : visibleBaseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
