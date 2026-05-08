import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/form-signer")({
  component: FormSigner,
})

export default function FormSigner() {
  return (
    <div className="h-full w-full">
      <iframe
        src="/form-filler/index.html"
        title="PDF Signer"
        className="w-full h-[calc(100vh-80px)] border-0"
      />
    </div>
  )
}
