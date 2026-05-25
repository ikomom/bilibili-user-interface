import { OpenAPI } from "@/client"
import { request as __request } from "@/client/core/request"
import type { Permission, Role, RoleCreate, RoleUpdate } from "@/types/rbac"

export const adminApi = {
  getPermissions: (module?: string) =>
    __request<Permission[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/admin/permissions",
      query: module ? { module } : undefined,
    }),
  getRoles: () =>
    __request<Role[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/admin/roles",
    }),
  createRole: (requestBody: RoleCreate) =>
    __request<Role>(OpenAPI, {
      method: "POST",
      url: "/api/v1/admin/roles",
      body: requestBody,
      mediaType: "application/json",
    }),
  getRole: (roleId: string) =>
    __request<Role>(OpenAPI, {
      method: "GET",
      url: "/api/v1/admin/roles/{role_id}",
      path: { role_id: roleId },
    }),
  updateRole: (roleId: string, requestBody: RoleUpdate) =>
    __request<Role>(OpenAPI, {
      method: "PUT",
      url: "/api/v1/admin/roles/{role_id}",
      path: { role_id: roleId },
      body: requestBody,
      mediaType: "application/json",
    }),
  deleteRole: (roleId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/admin/roles/{role_id}",
      path: { role_id: roleId },
    }),
  assignPermissionToRole: (roleId: string, permissionId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "POST",
      url: "/api/v1/admin/roles/{role_id}/permissions",
      path: { role_id: roleId },
      body: { permission_id: permissionId },
      mediaType: "application/json",
    }),
  removePermissionFromRole: (roleId: string, permissionId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/admin/roles/{role_id}/permissions/{permission_id}",
      path: { role_id: roleId, permission_id: permissionId },
    }),
  getUserRoles: (userId: string) =>
    __request<Role[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/admin/users/{user_id}/roles",
      path: { user_id: userId },
    }),
  assignRoleToUser: (userId: string, roleId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "POST",
      url: "/api/v1/admin/users/{user_id}/roles",
      path: { user_id: userId },
      body: { role_id: roleId },
      mediaType: "application/json",
    }),
  removeRoleFromUser: (userId: string, roleId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/admin/users/{user_id}/roles/{role_id}",
      path: { user_id: userId, role_id: roleId },
    }),
}
