export type BilibiliAuthType = "cookie" | "sessdata" | "qrcode"
export type BilibiliResourceType = "video" | "dynamic" | "article"
export type SyncFrequency = "1h" | "6h" | "1d" | "1w" | "manual"
export type SyncStatus = "running" | "success" | "failed" | "cancelled"

export interface SyncConfig {
  resource_types: BilibiliResourceType[]
  sync_frequency: SyncFrequency
  history_limit: number | null
}

export interface FailedResourcePublic {
  id: string
  subscription_id: string
  resource_id: string
  resource_type: string
  failed_at: string
  retry_count: number
  last_error: string | null
  resource_meta: Record<string, unknown> | null
}

export interface BilibiliAccount {
  id: string
  user_id: string
  account_name: string
  auth_type: BilibiliAuthType
  bilibili_uid: string | null
  display_name: string | null
  avatar_url: string | null
  profile_info: Record<string, unknown>
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface BilibiliAccountCreate {
  account_name: string
  auth_type: BilibiliAuthType
  credentials: Record<string, unknown>
}

export interface BilibiliAccountUpdate {
  account_name?: string
  auth_type?: BilibiliAuthType
  credentials?: Record<string, unknown>
}

export interface BilibiliSubscription {
  id: string
  user_id: string
  account_id: string
  uploader_uid: string
  uploader_name: string
  uploader_avatar: string | null
  uploader_info: Record<string, unknown>
  sync_config: SyncConfig
  is_paused: boolean
  last_sync_at: string | null
  latest_sync_status: SyncStatus | null
  latest_sync_log_id: string | null
  created_at: string | null
  updated_at: string | null
}

export interface BilibiliSubscriptionCreate {
  account_id: string
  uploader_uid: string
  sync_config: SyncConfig
}

export interface BilibiliSubscriptionUpdate {
  account_id?: string
  sync_config?: SyncConfig
}

export interface BilibiliResource {
  id: string
  subscription_id: string
  resource_type: BilibiliResourceType
  resource_id: string
  title: string
  cover_url: string | null
  summary: string | null
  full_content: string | null
  attachments: Record<string, unknown> | null
  resource_meta: Record<string, unknown>
  published_at: string
  created_at: string | null
}

export interface BilibiliResourceQuery {
  subscription_id?: string
  resource_type?: BilibiliResourceType
  start_date?: string
  end_date?: string
  keyword?: string
  page?: number
  page_size?: number
}

export interface PaginatedResources {
  resources: BilibiliResource[]
  total: number
  page: number
  page_size: number
}

export interface PaginatedSyncLogs {
  logs: SyncLog[]
  total: number
  page: number
  page_size: number
}

export interface PaginatedSubscriptions {
  subscriptions: BilibiliSubscription[]
  total: number
  page: number
  page_size: number
}

export interface BilibiliResourceCounts {
  video: number
  dynamic: number
  article: number
}

export interface SyncLog {
  id: string
  subscription_id: string
  sync_type: "manual" | "scheduled"
  status: SyncStatus
  start_time: string
  end_time: string | null
  total_count: number
  success_count: number
  failed_count: number
  skipped_count: number
  error_message: string | null
  details: LogEntry[] | null
}

export interface LogEntry {
  timestamp: string
  level: "INFO" | "WARN" | "ERROR"
  message: string
  type?: BilibiliResourceType
  resource_id?: string
  title?: string
  status?: "success" | "failed" | "skipped"
  error?: string
  stack_trace?: string
}

export interface SyncResponse {
  sync_log_id: string
  message: string
}

export interface RetryFailedResponse {
  total: number
  success: number
  failed: number
}

export interface QRCodeGenerateResponse {
  qrcode_key: string
  qrcode_url: string
  expires_at: string
}

export interface QRCodeCheckResponse {
  status: "pending" | "scanned" | "confirmed" | "expired"
  account: BilibiliAccount | null
}
