import { del, get, set } from "idb-keyval"
import { useEffect, useState } from "react"
import { AdminService } from "@/client"

const ROOT_HANDLE_KEY = "sharepoint_root_handle"

const SharePointService = () => {
  const [targetName, setTargetName] = useState<string>("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rootHandle, setRootHandle] = useState<any>(null)

  useEffect(() => {
    Promise.all([
      AdminService.readFolder()
        .then((data) => setTargetName(data.value))
        .catch(() =>
          setError(
            "Could not load admin configuration. Has the admin set a folder name?",
          ),
        ),
      get(ROOT_HANDLE_KEY).then((handle) => setRootHandle(handle)),
    ]).finally(() => setLoading(false))
  }, [])

  const handleConnect = async () => {
    try {
      const handle = await (window as any).showDirectoryPicker({
        mode: "readwrite",
      })

      // THE GUARDRAIL: Verify the user picked the right folder
      if (handle.name !== targetName) {
        alert(
          `Validation Failed: Please select the folder named "${targetName}". You selected "${handle.name}".`,
        )
        return
      }

      // Success! Save to local browser storage
      await set(ROOT_HANDLE_KEY, handle)
      setRootHandle(handle)
      alert("Export folder linked successfully!")
    } catch (_err) {
      console.error("User cancelled or browser blocked the picker.")
    }
  }

  const handleDisconnect = async () => {
    await del(ROOT_HANDLE_KEY)
    setRootHandle(null)
    alert("Export folder disconnected successfully!")
  }

  if (loading) return <div>Loading configuration...</div>

  if (!rootHandle || rootHandle.name !== targetName) {
    return (
      <div className="max-w-md">
        <h2 className="text-lg font-semibold py-4">Link Export Folder</h2>
        <p className="text-muted-foreground">
          Your administrator requires all files to be saved in:
          <span />
          <span className="block font-mono font-bold text-blue-600">
            {targetName
              ? targetName
              : error && <p className="text-red-500 text-xs">{error}</p>}
          </span>
        </p>
        <br />
        <div className="bg-blue-50 p-3 rounded text-sm text-blue-600">
          <strong>Notice:</strong> If your admin requires a SharePoint Library
          to export to, please ensure you have synced this folder to your
          Windows Explorer using the instructions provided by Microsoft&nbsp;
          <a
            className="underline"
            target="_blank"
            rel="noopener noreferrer"
            href="https://support.microsoft.com/en-us/office/view-sharepoint-files-in-file-explorer-66b574bb-08b4-46b6-a6a0-435fd98194cc"
          >
            here.
          </a>
        </div>
        <br />
        <p className="text-muted-foreground">
          You are currently configured for:
          <span />
          <span className="block font-mono font-bold text-[#D4AF37]">
            {rootHandle?.name ?? "None"}
          </span>
        </p>
        <br />
        <br />
        <button
          type="button"
          onClick={handleConnect}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
        >
          Select & Verify Folder
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-lg font-semibold py-4">Link Export Folder</h2>
      <p className="text-muted-foreground">
        You have already linked your export folder. Your current selection
        is:
        <span className="block font-mono font-bold text-[#D4AF37]">
          "{rootHandle.name}"
        </span>
        <br />
        <button
          type="button"
          onClick={handleDisconnect}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-500"
        >
          Unlink the Folder
        </button>
      </p>
    </div>
  )
}

/**
 * Programmatically creates a patient subfolder and saves the PDF.
 * This avoids the "Save As" dialog after the initial connection.
 */
const savePatientForm = async (
  blob: Blob,
  patientId: string,
  fileName: string,
) => {
  const rootHandle = await get<FileSystemDirectoryHandle>(ROOT_HANDLE_KEY)

  if (!rootHandle) {
    throw new Error("No export folder connected. Please run setup first.")
  }

  // 1. Request/Verify Permission (Browser security requires this check)
  // Most browsers will show a small prompt: "Allow this site to edit files?"
  if (
    (await (rootHandle as any).queryPermission({ mode: "readwrite" })) !==
    "granted"
  ) {
    await (rootHandle as any).requestPermission({ mode: "readwrite" })
  }

  try {
    // 2. Access or Create the patient-specific subfolder
    const patientFolder = await rootHandle.getDirectoryHandle(patientId, {
      create: true,
    })

    // 3. Create the file inside that subfolder
    const fileHandle = await patientFolder.getFileHandle(fileName, {
      create: true,
    })

    // 4. Stream the data to the file
    const writable = await fileHandle.createWritable()
    await writable.write(blob)
    await writable.close()

    console.log(`Success! ${fileName} saved to folder: ${patientId}`)
  } catch (err) {
    console.error("Error during silent save:", err)
    throw err
  }
}

export default SharePointService
export { savePatientForm }
