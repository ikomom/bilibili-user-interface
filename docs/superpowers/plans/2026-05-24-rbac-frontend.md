# RBAC 前端管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 RBAC 权限管理的前端界面，包括用户角色管理、角色权限管理、权限列表展示。

**Architecture:** 扩展现有的 Admin 页面，添加角色管理和权限管理功能。使用 TanStack Query 管理状态，shadcn/ui 组件库构建界面。

**Tech Stack:** React, TypeScript, TanStack Query, shadcn/ui

**Prerequisites:** Plan 1 (RBAC 权限系统) 必须先完成

---

## File Structure

**Frontend files to create:**
- `frontend/src/pages/admin/RolesPage.tsx` - 角色管理页面
- `frontend/src/pages/admin/PermissionsPage.tsx` - 权限列表页面
- `frontend/src/components/admin/UserRolesDialog.tsx` - 用户角色管理弹窗
- `frontend/src/components/admin/RolePermissionsDialog.tsx` - 角色权限管理弹窗
- `frontend/src/components/admin/CreateRoleDialog.tsx` - 创建角色弹窗
- `frontend/src/lib/api/admin.ts` - Admin API 客户端扩展
- `frontend/src/types/rbac.ts` - RBAC 类型定义

**Frontend files to modify:**
- `frontend/src/pages/admin/UsersPage.tsx` - 添加"管理角色"功能
- `frontend/src/components/AppSidebar.tsx` - 添加角色和权限菜单
- `frontend/src/App.tsx` - 添加路由
- `frontend/src/types/user.ts` - 添加 permissions 字段

---

### Task 1: 添加 RBAC 类型定义

**Files:**
- Create: `frontend/src/types/rbac.ts`
- Modify: `frontend/src/types/user.ts`

- [ ] **Step 1: 创建 RBAC 类型**

```typescript
// frontend/src/types/rbac.ts
export interface Permission {
  id: string
  code: string
  name: string
  module: string
  description: string | null
  created_at: string
}

export interface Role {
  id: string
  name: string
  description: string | null
  is_system: boolean
  created_at: string
  permissions?: Permission[]
}

export interface RoleWithPermissions extends Role {
  permissions: Permission[]
}
```

- [ ] **Step 2: 更新 User 类型**

```typescript
// frontend/src/types/user.ts
export interface User {
  id: string
  email: string
  full_name: string
  is_superuser: boolean
  permissions: string[]  // 新增：权限代码列表
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/rbac.ts frontend/src/types/user.ts
git commit -m "feat(rbac): add RBAC TypeScript types

- Add Permission and Role interfaces
- Add permissions field to User type
- Support role-permission relationships

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 扩展 Admin API 客户端

**Files:**
- Create: `frontend/src/lib/api/admin.ts`

- [ ] **Step 1: 实现 RBAC API 客户端**

```typescript
import { api } from './client'
import type { Role, Permission } from '@/types/rbac'

export const adminApi = {
  // 角色管理
  getRoles: () => api.get<Role[]>('/admin/roles'),
  createRole: (data: { name: string; description?: string }) => 
    api.post('/admin/roles', data),
  getRole: (id: string) => api.get<Role>(`/admin/roles/${id}`),
  updateRole: (id: string, data: any) => api.put(`/admin/roles/${id}`, data),
  deleteRole: (id: string) => api.delete(`/admin/roles/${id}`),
  
  // 角色-权限关联
  getRolePermissions: (roleId: string) => 
    api.get<Permission[]>(`/admin/roles/${roleId}/permissions`),
  assignPermissionToRole: (roleId: string, permissionId: string) =>
    api.post(`/admin/roles/${roleId}/permissions`, { permission_id: permissionId }),
  removePermissionFromRole: (roleId: string, permissionId: string) =>
    api.delete(`/admin/roles/${roleId}/permissions/${permissionId}`),
  
  // 用户-角色关联
  getUserRoles: (userId: string) => 
    api.get<Role[]>(`/admin/users/${userId}/roles`),
  assignRoleToUser: (userId: string, roleId: string) =>
    api.post(`/admin/users/${userId}/roles`, { role_id: roleId }),
  removeRoleFromUser: (userId: string, roleId: string) =>
    api.delete(`/admin/users/${userId}/roles/${roleId}`),
  
  // 权限查询
  getPermissions: (module?: string) => 
    api.get<Permission[]>('/admin/permissions', { params: { module } }),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api/admin.ts
git commit -m "feat(rbac): add admin API client for RBAC

- Implement role CRUD APIs
- Implement role-permission association APIs
- Implement user-role association APIs
- Add permission query API

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 实现角色管理页面

**Files:**
- Create: `frontend/src/pages/admin/RolesPage.tsx`
- Create: `frontend/src/components/admin/CreateRoleDialog.tsx`
- Create: `frontend/src/components/admin/RolePermissionsDialog.tsx`

- [ ] **Step 1: 实现 RolesPage 组件**

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '@/lib/api/admin'
import { Button } from '@/components/ui/button'
import { Table } from '@/components/ui/table'
import { CreateRoleDialog } from '@/components/admin/CreateRoleDialog'
import { RolePermissionsDialog } from '@/components/admin/RolePermissionsDialog'

export function RolesPage() {
  const queryClient = useQueryClient()
  const { data: roles } = useQuery({
    queryKey: ['roles'],
    queryFn: adminApi.getRoles
  })
  
  const deleteRole = useMutation({
    mutationFn: adminApi.deleteRole,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['roles'] })
  })
  
  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">角色管理</h1>
        <CreateRoleDialog />
      </div>
      
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>角色名</TableHead>
            <TableHead>描述</TableHead>
            <TableHead>权限数量</TableHead>
            <TableHead>系统角色</TableHead>
            <TableHead>操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {roles?.map(role => (
            <TableRow key={role.id}>
              <TableCell>{role.name}</TableCell>
              <TableCell>{role.description}</TableCell>
              <TableCell>{role.permissions?.length || 0}</TableCell>
              <TableCell>
                {role.is_system ? <Badge>系统</Badge> : null}
              </TableCell>
              <TableCell>
                <RolePermissionsDialog roleId={role.id} />
                {!role.is_system && (
                  <Button 
                    variant="destructive" 
                    size="sm"
                    onClick={() => deleteRole.mutate(role.id)}
                  >
                    删除
                  </Button>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 2: 实现 CreateRoleDialog 组件**

```typescript
export function CreateRoleDialog() {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  
  const createRole = useMutation({
    mutationFn: adminApi.createRole,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] })
      setOpen(false)
    }
  })
  
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>创建角色</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>创建新角色</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <Input name="name" placeholder="角色名称" required />
          <Textarea name="description" placeholder="描述" />
          <Button type="submit">创建</Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: 实现 RolePermissionsDialog 组件**

```typescript
export function RolePermissionsDialog({ roleId }: { roleId: string }) {
  const [open, setOpen] = useState(false)
  
  const { data: role } = useQuery({
    queryKey: ['role', roleId],
    queryFn: () => adminApi.getRole(roleId),
    enabled: open
  })
  
  const { data: allPermissions } = useQuery({
    queryKey: ['permissions'],
    queryFn: () => adminApi.getPermissions(),
    enabled: open
  })
  
  // 按模块分组
  const permissionsByModule = groupBy(allPermissions, 'module')
  
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">管理权限</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[600px] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>管理角色权限 - {role?.name}</DialogTitle>
        </DialogHeader>
        
        {Object.entries(permissionsByModule).map(([module, permissions]) => (
          <div key={module} className="mb-4">
            <h4 className="font-medium mb-2">{module} 模块</h4>
            <div className="space-y-2 pl-4">
              {permissions.map(permission => (
                <div key={permission.id} className="flex items-center space-x-2">
                  <Checkbox
                    checked={role?.permissions?.some(p => p.id === permission.id)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        assignPermission.mutate(permission.id)
                      } else {
                        removePermission.mutate(permission.id)
                      }
                    }}
                  />
                  <Label>
                    {permission.name}
                    <span className="text-xs text-muted-foreground ml-2">
                      ({permission.code})
                    </span>
                  </Label>
                </div>
              ))}
            </div>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin/RolesPage.tsx frontend/src/components/admin/
git commit -m "feat(rbac): implement role management page

- Add RolesPage with role CRUD
- Add CreateRoleDialog for creating roles
- Add RolePermissionsDialog for managing role permissions
- Group permissions by module for better UX
- Prevent deletion of system roles

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 实现权限列表页面

**Files:**
- Create: `frontend/src/pages/admin/PermissionsPage.tsx`

- [ ] **Step 1: 实现 PermissionsPage 组件**

```typescript
export function PermissionsPage() {
  const [selectedModule, setSelectedModule] = useState<string | undefined>()
  
  const { data: permissions } = useQuery({
    queryKey: ['permissions', selectedModule],
    queryFn: () => adminApi.getPermissions(selectedModule)
  })
  
  // 获取所有模块
  const modules = [...new Set(permissions?.map(p => p.module))]
  
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">权限列表</h1>
      
      <Tabs value={selectedModule} onValueChange={setSelectedModule}>
        <TabsList>
          <TabsTrigger value={undefined}>全部</TabsTrigger>
          {modules.map(module => (
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
          </TableRow>
        </TableHeader>
        <TableBody>
          {permissions?.map(permission => (
            <TableRow key={permission.id}>
              <TableCell><code>{permission.code}</code></TableCell>
              <TableCell>{permission.name}</TableCell>
              <TableCell><Badge>{permission.module}</Badge></TableCell>
              <TableCell>{permission.description}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/admin/PermissionsPage.tsx
git commit -m "feat(rbac): implement permissions list page

- Add PermissionsPage with module filter
- Display all permissions in read-only table
- Support filtering by module via tabs

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 扩展用户管理页面

**Files:**
- Modify: `frontend/src/pages/admin/UsersPage.tsx`
- Create: `frontend/src/components/admin/UserRolesDialog.tsx`

- [ ] **Step 1: 在 UsersPage 添加"管理角色"按钮**

在用户表格的操作列添加：

```typescript
<Button 
  variant="outline" 
  size="sm"
  onClick={() => setSelectedUserId(user.id)}
>
  管理角色
</Button>

{selectedUserId && (
  <UserRolesDialog 
    userId={selectedUserId} 
    onClose={() => setSelectedUserId(null)} 
  />
)}
```

- [ ] **Step 2: 实现 UserRolesDialog 组件**

```typescript
export function UserRolesDialog({ userId, onClose }: Props) {
  const { data: userRoles } = useQuery({
    queryKey: ['user-roles', userId],
    queryFn: () => adminApi.getUserRoles(userId)
  })
  
  const { data: allRoles } = useQuery({
    queryKey: ['roles'],
    queryFn: adminApi.getRoles
  })
  
  const assignRole = useMutation({
    mutationFn: (roleId: string) => adminApi.assignRoleToUser(userId, roleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['user-roles', userId] })
  })
  
  const removeRole = useMutation({
    mutationFn: (roleId: string) => adminApi.removeRoleFromUser(userId, roleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['user-roles', userId] })
  })
  
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>管理用户角色</DialogTitle>
        </DialogHeader>
        
        <div className="space-y-2">
          {allRoles?.map(role => (
            <div key={role.id} className="flex items-center space-x-2">
              <Checkbox
                checked={userRoles?.some(r => r.id === role.id)}
                onCheckedChange={(checked) => {
                  if (checked) {
                    assignRole.mutate(role.id)
                  } else {
                    removeRole.mutate(role.id)
                  }
                }}
              />
              <Label>
                {role.name}
                <span className="text-sm text-muted-foreground ml-2">
                  {role.description}
                </span>
              </Label>
            </div>
          ))}
        </div>
        
        {/* 权限预览 */}
        <div className="mt-4">
          <h4 className="text-sm font-medium mb-2">当前权限：</h4>
          <div className="flex flex-wrap gap-1">
            {userRoles?.flatMap(r => r.permissions || []).map(p => (
              <Badge key={p.code} variant="secondary">
                {p.name}
              </Badge>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/admin/UsersPage.tsx frontend/src/components/admin/UserRolesDialog.tsx
git commit -m "feat(rbac): add user role management to UsersPage

- Add 'Manage Roles' button to user table
- Implement UserRolesDialog with role assignment
- Show permission preview based on assigned roles
- Support adding/removing roles via checkboxes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 更新菜单和路由

**Files:**
- Modify: `frontend/src/components/AppSidebar.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 在 AppSidebar 添加菜单项**

```typescript
const items = [
  ...baseItems,
  ...(hasBilibiliAccess ? [bilibiliMenu] : []),
  ...(currentUser?.is_superuser ? [{
    icon: Users,
    title: "Admin",
    children: [
      { title: "用户管理", path: "/admin/users" },
      { title: "角色管理", path: "/admin/roles" },      // 新增
      { title: "权限列表", path: "/admin/permissions" }  // 新增
    ]
  }] : [])
]
```

- [ ] **Step 2: 在 App.tsx 添加路由**

```typescript
<Route path="/admin/roles" element={<RolesPage />} />
<Route path="/admin/permissions" element={<PermissionsPage />} />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AppSidebar.tsx frontend/src/App.tsx
git commit -m "feat(rbac): add RBAC menu items and routes

- Add 'Role Management' and 'Permissions List' to Admin menu
- Add routes for RolesPage and PermissionsPage
- Only visible to superusers

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Plan 4 Complete

**Total Tasks:** 6
**Estimated Time:** 6-8 hours

**Self-Review:**
- ✅ RBAC 类型定义完整
- ✅ Admin API 客户端扩展
- ✅ 角色管理页面（CRUD + 权限分配）
- ✅ 权限列表页面（只读 + 模块筛选）
- ✅ 用户角色管理（扩展现有页面）
- ✅ 菜单和路由集成

**All 4 Plans Complete!** 
Ready for execution.
