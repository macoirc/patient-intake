import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileText, FolderOpen, Trash2 } from "lucide-react";

import { FormsService, type IntakePacketPublic } from "@/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Dialog,
	DialogClose,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import useAuth from "@/hooks/useAuth";
import useCustomToast from "@/hooks/useCustomToast";
import { handleError } from "@/utils";

interface PacketHistoryProps {
	onOpen: (packet: IntakePacketPublic) => void;
	packets: IntakePacketPublic[];
	isLoading: boolean;
}

export function PacketHistory({
	onOpen,
	packets,
	isLoading,
}: PacketHistoryProps) {
	const { user } = useAuth();
	const queryClient = useQueryClient();
	const { showSuccessToast, showErrorToast } = useCustomToast();

	const deletePacketMutation = useMutation({
		mutationFn: (packetId: string) => FormsService.deletePacket({ packetId }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["packets"] });
			queryClient.invalidateQueries({ queryKey: ["packets_and_patients"] });
			showSuccessToast("Packet deleted successfully.");
		},
		onError: handleError.bind(showErrorToast),
	});

	function formatDate(iso: string | null | undefined) {
		if (!iso) return "—";
		return new Date(iso).toLocaleDateString("en-US", {
			month: "short",
			day: "numeric",
			year: "numeric",
		});
	}

	return (
		<div className="flex flex-col h-full rounded-lg border bg-card overflow-hidden">
			<div className="flex-1 overflow-y-auto p-4">
				{isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}

				{!isLoading && packets.length === 0 && (
					<div className="flex flex-col items-center justify-center h-full gap-3 text-center py-16">
						<FileText className="h-10 w-10 text-muted-foreground/40" />
						<p className="text-sm text-muted-foreground">
							No packets yet. Fill in the patient info and generate your first
							intake packet.
						</p>
					</div>
				)}

				<div className="space-y-3">
					{packets.map((packet) => (
						<Card
							key={packet.id}
							className="hover:bg-accent/50 transition-colors"
						>
							<CardHeader className="pb-2 pt-3 px-4">
								<div className="flex items-start justify-between gap-2">
									<CardTitle className="text-sm font-medium leading-tight">
										{packet.patient_name}
									</CardTitle>
									<Badge
										variant={
											packet.status === "completed" ? "default" : "secondary"
										}
										className="text-xs shrink-0"
									>
										{packet.status}
									</Badge>
								</div>
								<p className="text-xs text-muted-foreground">
									ID: {packet.patient_id_number} ·{" "}
									{formatDate(packet.created_at)}
								</p>
							</CardHeader>
							<CardContent className="px-4 pb-3">
								<div className="flex items-center justify-between">
									<p className="text-xs text-muted-foreground">
										{packet.documents?.length} form
										{packet.documents?.length !== 1 ? "s" : ""}
									</p>
									<div className="flex items-center gap-2">
										{user?.is_superuser && (
											<Dialog>
												<DialogTrigger asChild>
													<Button
														size="sm"
														variant="destructive"
														className="h-7 text-xs"
														disabled={deletePacketMutation.isPending}
													>
														<Trash2 className="mr-1.5 h-3.5 w-3.5" />
														Delete
													</Button>
												</DialogTrigger>
												<DialogContent>
													<DialogHeader>
														<DialogTitle>Are you sure?</DialogTitle>
														<DialogDescription>
															This will permanently delete the intake packet for{" "}
															<strong>{packet.patient_name}</strong>. This
															action cannot be undone.
														</DialogDescription>
													</DialogHeader>
													<DialogFooter>
														<DialogClose asChild>
															<Button variant="outline">Cancel</Button>
														</DialogClose>
														<DialogClose asChild>
															<Button
																variant="destructive"
																onClick={() =>
																	deletePacketMutation.mutate(packet.id)
																}
															>
																Yes, delete
															</Button>
														</DialogClose>
													</DialogFooter>
												</DialogContent>
											</Dialog>
										)}
										<Button
											size="sm"
											variant="outline"
											className="h-7 text-xs"
											onClick={() => onOpen(packet)}
											disabled={packet.documents?.length === 0}
										>
											<FolderOpen className="mr-1.5 h-3.5 w-3.5" />
											Open
										</Button>
									</div>
								</div>
							</CardContent>
						</Card>
					))}
				</div>
			</div>
		</div>
	);
}
