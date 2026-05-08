import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { HttpStatusCode } from "axios"
import { AdminService } from "@/client"

function SetSharePoint() {
  const queryClient = useQueryClient()

  const { data: priorFolder, isLoading } = useQuery({
    queryKey: ["sharepointFolder"],
    queryFn: async () => {
      try {
        return await AdminService.readFolder()
      } catch (error: any) {
        if (
          error?.status === HttpStatusCode.NotFound ||
          error?.response?.status === HttpStatusCode.NotFound
        ) {
          return null
        }
        throw error
      }
    },
  })

  const mutation = useMutation({
    mutationFn: (folderName: string) =>
      AdminService.updateFolder({ folder: folderName }),
    onSuccess: (data) => {
      console.log("Successfully updated folder:", data)
      alert("SharePoint folder updated successfully!")
    },
    onError: (err) => {
      console.error("Could not update the folder name.", err)
      alert("Could not update the folder name. Please try again.")
    },
    onSettled: () => {
      // This tells React Query to refetch the folder name automatically
      queryClient.invalidateQueries({ queryKey: ["sharepointFolder"] })
    },
  })

  const handleUpdateFolder = async () => {
    try {
      const handle = await (window as any).showDirectoryPicker()
      if (handle?.name) {
        mutation.mutate(handle.name)
      }
    } catch (err) {
      console.error("User cancelled or browser blocked the picker.", err)
    }
  }

  const rootHandle = priorFolder?.value ?? null

  return (
    <div className="max-w-md">
      <p className="text-muted-foreground">
        Configure your SharePoint location
      </p>
      <form>
        <div className="grid gap-4 py-4">
          <div className="flex flex-col gap-2">
            Current Folder Name:&nbsp;
            <span className="font-mono font-bold text-[#D4AF37]">
              {isLoading ? " Loading..." : (rootHandle ?? "None")}
            </span>
          </div>
          <div className="bg-blue-50 p-3 rounded text-sm text-blue-800">
            <strong>Notice:</strong> Ensure you have synced the folder you want
            to your Windows Explorer using the instructions provided by
            Microsoft&nbsp;
            <a
              className="underline"
              target="_blank"
              rel="noopener noreferrer"
              href="https://support.microsoft.com/en-us/office/view-sharepoint-files-in-file-explorer-66b574bb-08b4-46b6-a6a0-435fd98194cc"
            >
              here.
            </a>
          </div>
          <button
            type="button"
            onClick={handleUpdateFolder}
            disabled={mutation.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-50"
          >
            {mutation.isPending ? "Updating..." : "Update Folder"}
          </button>
        </div>
      </form>
    </div>
  )
}

export default SetSharePoint
