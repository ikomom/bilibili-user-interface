import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { adminApi } from "@/lib/api/admin"
import { handleError } from "@/utils"

export function CreateRoleDialog() {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const createRole = useMutation({
    mutationFn: adminApi.createRole,
    onSuccess: () => {
      showSuccessToast("角色已创建")
      queryClient.invalidateQueries({ queryKey: ["rbac-roles"] })
      setName("")
      setDescription("")
      setOpen(false)
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 size-4" />
          创建角色
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>创建角色</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <Input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="角色名称"
          />
          <Input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="描述（可选）"
          />
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
          >
            取消
          </Button>
          <LoadingButton
            loading={createRole.isPending}
            onClick={() =>
              createRole.mutate({
                name: name.trim(),
                description: description.trim() || undefined,
              })
            }
            disabled={!name.trim()}
          >
            创建
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
