import { OpenAPI } from "@/client"
import { request as __request } from "@/client/core/request"
import type {
  BilibiliAccount,
  BilibiliAccountCreate,
  BilibiliAccountUpdate,
  BilibiliResource,
  BilibiliResourceQuery,
  BilibiliSubscription,
  BilibiliSubscriptionCreate,
  BilibiliSubscriptionUpdate,
  QRCodeCheckResponse,
  QRCodeGenerateResponse,
  RetryFailedResponse,
  SyncLog,
  SyncResponse,
} from "@/types/bilibili"

export const bilibiliApi = {
  proxiedImageUrl: (url: string) =>
    `${OpenAPI.BASE}/api/v1/bilibili/image-proxy?url=${encodeURIComponent(url)}`,
  getAccounts: () =>
    __request<BilibiliAccount[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/bilibili/accounts",
    }),
  createAccount: (requestBody: BilibiliAccountCreate) =>
    __request<BilibiliAccount>(OpenAPI, {
      method: "POST",
      url: "/api/v1/bilibili/accounts",
      body: requestBody,
      mediaType: "application/json",
    }),
  updateAccount: (accountId: string, requestBody: BilibiliAccountUpdate) =>
    __request<BilibiliAccount>(OpenAPI, {
      method: "PUT",
      url: "/api/v1/bilibili/accounts/{account_id}",
      path: { account_id: accountId },
      body: requestBody,
      mediaType: "application/json",
    }),
  deleteAccount: (accountId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/bilibili/accounts/{account_id}",
      path: { account_id: accountId },
    }),
  generateQRCode: () =>
    __request<QRCodeGenerateResponse>(OpenAPI, {
      method: "POST",
      url: "/api/v1/bilibili/accounts/qrcode/generate",
    }),
  checkQRCode: (qrcodeKey: string) =>
    __request<QRCodeCheckResponse>(OpenAPI, {
      method: "POST",
      url: "/api/v1/bilibili/accounts/qrcode/check",
      body: { qrcode_key: qrcodeKey },
      mediaType: "application/json",
    }),

  getSubscriptions: () =>
    __request<BilibiliSubscription[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/bilibili/subscriptions",
    }),
  createSubscription: (requestBody: BilibiliSubscriptionCreate) =>
    __request<BilibiliSubscription>(OpenAPI, {
      method: "POST",
      url: "/api/v1/bilibili/subscriptions",
      body: requestBody,
      mediaType: "application/json",
    }),
  getSubscription: (subscriptionId: string) =>
    __request<BilibiliSubscription>(OpenAPI, {
      method: "GET",
      url: "/api/v1/bilibili/subscriptions/{sub_id}",
      path: { sub_id: subscriptionId },
    }),
  updateSubscription: (
    subscriptionId: string,
    requestBody: BilibiliSubscriptionUpdate,
  ) =>
    __request<BilibiliSubscription>(OpenAPI, {
      method: "PUT",
      url: "/api/v1/bilibili/subscriptions/{sub_id}",
      path: { sub_id: subscriptionId },
      body: requestBody,
      mediaType: "application/json",
    }),
  deleteSubscription: (subscriptionId: string) =>
    __request<{ message: string }>(OpenAPI, {
      method: "DELETE",
      url: "/api/v1/bilibili/subscriptions/{sub_id}",
      path: { sub_id: subscriptionId },
    }),
  pauseSubscription: (subscriptionId: string) =>
    __request<{ is_paused: boolean }>(OpenAPI, {
      method: "PATCH",
      url: "/api/v1/bilibili/subscriptions/{sub_id}/pause",
      path: { sub_id: subscriptionId },
    }),
  syncSubscription: (subscriptionId: string) =>
    __request<SyncResponse>(OpenAPI, {
      method: "POST",
      url: "/api/v1/bilibili/subscriptions/{sub_id}/sync",
      path: { sub_id: subscriptionId },
    }),
  retryFailedResources: (subscriptionId: string) =>
    __request<RetryFailedResponse>(OpenAPI, {
      method: "POST",
      url: "/api/v1/bilibili/subscriptions/{sub_id}/retry-failed",
      path: { sub_id: subscriptionId },
    }),

  getResources: (query: BilibiliResourceQuery = {}) =>
    __request<BilibiliResource[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/bilibili/resources",
      query: { ...query },
    }),

  getSyncLogs: (subscriptionId: string) =>
    __request<SyncLog[]>(OpenAPI, {
      method: "GET",
      url: "/api/v1/bilibili/sync-logs",
      query: { subscription_id: subscriptionId },
    }),
  getSyncLog: (logId: string) =>
    __request<SyncLog>(OpenAPI, {
      method: "GET",
      url: "/api/v1/bilibili/sync-logs/{log_id}",
      path: { log_id: logId },
    }),
}
