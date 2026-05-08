import { useQuery } from "@tanstack/react-query"
import { Download } from "lucide-react"
import { useState } from "react"
import { OpenAPI } from "@/client"
import { Button } from "@/components/ui/button"

function getSavedReportsQueryOptions() {
  return {
    queryKey: ["savedReports"],
    queryFn: async () => {
      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${OpenAPI.BASE}/api/v1/reports/saved-reports`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )
      if (!response.ok) {
        throw new Error("Failed to fetch saved reports")
      }
      return response.json() as Promise<string[]>
    },
  }
}

function Reports() {
  const [isDownloading, setIsDownloading] = useState(false)
  const [isDownloadingCsv, setIsDownloadingCsv] = useState(false)
  const { data: savedReports, isLoading: isLoadingSavedReports } = useQuery(
    getSavedReportsQueryOptions(),
  )

  const handleDownloadPdf = async () => {
    setIsDownloading(true)
    try {
      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${OpenAPI.BASE}/api/v1/reports/download-pdf`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )

      if (!response.ok) {
        throw new Error("Failed to download PDF")
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `System_Report_${new Date().toISOString().split("T")[0]}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } finally {
      setIsDownloading(false)
    }
  }

  const handleDownloadCsv = async () => {
    setIsDownloadingCsv(true)
    try {
      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${OpenAPI.BASE}/api/v1/reports/download-csv`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )
      if (!response.ok) {
        throw new Error("Failed to download CSV")
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `System_Report_${new Date().toISOString().split("T")[0]}.csv`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } finally {
      setIsDownloadingCsv(false)
    }
  }

  const handleDownloadSavedReport = async (filename: string) => {
    const token = localStorage.getItem("access_token")
    const url = `${OpenAPI.BASE}/api/v1/reports/saved-reports/${filename}`
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = downloadUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(downloadUrl)
  }

  return (
    <div className="grid gap-6 mt-4">
      <div className="rounded-xl border border-white/10 bg-black p-5">
        <h3 className="font-semibold">Archived Weekly Reports</h3>
        <p className="text-sm text-muted-foreground">
          Weekly reports are generated automatically every Monday.
        </p>
        {isLoadingSavedReports ? (
          <p className="mt-4 text-muted-foreground">
            Loading archived reports...
          </p>
        ) : savedReports && savedReports.length > 0 ? (
          <ul className="mt-4 space-y-2">
            {savedReports.map((filename) => (
              <li key={filename} className="flex justify-between items-center">
                <span className="font-mono">{filename}</span>
                <Button
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
                  onClick={() => handleDownloadSavedReport(filename)}
                >
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-muted-foreground">
            No archived reports found.
          </p>
        )}
      </div>

      <div className="flex justify-end gap-2">
        <Button
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
          onClick={handleDownloadCsv}
          disabled={isDownloadingCsv}
        >
          <Download className="mr-2 h-4 w-4" />
          {isDownloadingCsv ? "Generating..." : "Download Ad-hoc CSV"}
        </Button>
        <Button
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
          onClick={handleDownloadPdf}
          disabled={isDownloading}
        >
          <Download className="mr-2 h-4 w-4" />
          {isDownloading ? "Generating..." : "Download Ad-hoc PDF"}
        </Button>
      </div>
    </div>
  )
}

export default Reports
