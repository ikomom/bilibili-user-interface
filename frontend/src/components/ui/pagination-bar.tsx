import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"

interface PaginationBarProps {
  page: number
  totalPages: number
  total: number
  onPageChange: (page: number) => void
}

export function PaginationBar({ page, totalPages, total, onPageChange }: PaginationBarProps) {
  if (totalPages < 1) return null

  return (
    <div className="mt-6 flex flex-col items-center gap-2">
      <p className="text-sm text-muted-foreground">
        第 {page} / {totalPages} 页，共 {total} 条
      </p>
      {totalPages > 1 ? (
        <Pagination>
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  onPageChange(Math.max(1, page - 1))
                }}
              />
            </PaginationItem>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => {
              if (p === 1 || p === totalPages || Math.abs(p - page) <= 2) {
                return (
                  <PaginationItem key={p}>
                    <PaginationLink
                      href="#"
                      isActive={p === page}
                      onClick={(e) => {
                        e.preventDefault()
                        onPageChange(p)
                      }}
                    >
                      {p}
                    </PaginationLink>
                  </PaginationItem>
                )
              }
              if (p === 2 && page > 4 || p === totalPages - 1 && page < totalPages - 3) {
                return (
                  <PaginationItem key={p}>
                    <PaginationEllipsis />
                  </PaginationItem>
                )
              }
              return null
            })}
            <PaginationItem>
              <PaginationNext
                href="#"
                onClick={(e) => {
                  e.preventDefault()
                  onPageChange(Math.min(totalPages, page + 1))
                }}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      ) : null}
    </div>
  )
}
