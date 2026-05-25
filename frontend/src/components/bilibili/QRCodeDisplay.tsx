import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Loader2, QrCode, RefreshCcw } from "lucide-react"
import { useEffect, useState } from "react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { bilibiliApi } from "@/lib/api/bilibili"
import { handleError } from "@/utils"

interface QRCodeDisplayProps {
  onSuccess: () => void
}

export function QRCodeDisplay({ onSuccess }: QRCodeDisplayProps) {
  const [qrData, setQrData] = useState<{
    qrcode_key: string
    qrcode_url: string
  } | null>(null)
  const [statusText, setStatusText] = useState("正在生成二维码...")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const generateQR = useMutation({
    mutationFn: bilibiliApi.generateQRCode,
    onSuccess: (data) => {
      setQrData(data)
      setStatusText("请使用 B站 App 扫描二维码")
    },
    onError: (error) => {
      setStatusText("扫码登录配置异常，请检查后端配置后重试")
      showErrorToast(error.message)
    },
  })

  const checkQR = useMutation({
    mutationFn: bilibiliApi.checkQRCode,
    onSuccess: (data) => {
      if (data.status === "pending") {
        setStatusText("请使用 B站 App 扫描二维码")
        return
      }
      if (data.status === "scanned") {
        setStatusText("已扫描，请在手机上确认登录")
        return
      }
      if (data.status === "expired") {
        setStatusText("二维码已过期，请重新生成")
        return
      }
      showSuccessToast("B站账户已添加")
      queryClient.invalidateQueries({ queryKey: ["bilibili-accounts"] })
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
  })

  useEffect(() => {
    if (!qrData || statusText.includes("过期") || statusText.includes("异常")) {
      return
    }

    const timer = window.setInterval(() => {
      checkQR.mutate(qrData.qrcode_key)
    }, 2000)

    return () => window.clearInterval(timer)
  }, [qrData, statusText, checkQR.mutate, checkQR])

  const regenerate = () => {
    setQrData(null)
    setStatusText("正在生成二维码...")
    generateQR.mutate()
  }

  const isExpired = statusText.includes("过期")

  if (!qrData) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-12 text-muted-foreground">
        {generateQR.isPending ? (
          <Loader2 className="size-5 animate-spin" />
        ) : null}
        <span>
          {generateQR.isPending
            ? "正在生成二维码..."
            : "点击生成扫码登录二维码"}
        </span>
        <Button type="button" onClick={() => generateQR.mutate()}>
          生成二维码
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <Alert>
        <QrCode />
        <AlertTitle>扫码登录</AlertTitle>
        <AlertDescription>{statusText}</AlertDescription>
      </Alert>

      <div className="relative flex justify-center">
        <img
          src={qrData.qrcode_url}
          alt="B站扫码登录二维码"
          className="size-64 rounded-lg border bg-white p-3"
        />
        {isExpired ? (
          <div className="absolute inset-0 mx-auto flex size-64 items-center justify-center rounded-lg bg-background/80 backdrop-blur-sm">
            <Button type="button" onClick={regenerate}>
              <RefreshCcw className="mr-2 size-4" />
              重新生成
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
