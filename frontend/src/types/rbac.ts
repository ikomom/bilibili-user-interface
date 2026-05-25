export interface Permission {
  id: string
  code: string
  name: string
  module: string
  description: string | null
  created_at: string
  roles?: Role[]
}

export interface Role {
  id: string
  name: string
  description: string | null
  is_system: boolean
  created_at: string
  permission_count?: number
  permissions?: Permission[]
}

export interface RoleCreate {
  name: string
  description?: string
}

export interface RoleUpdate {
  name?: string
  description?: string
}
