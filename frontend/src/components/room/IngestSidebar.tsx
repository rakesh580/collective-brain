import { Upload, X, CheckCircle, XCircle, Clock } from "lucide-react";
import SourceUploader from "../ingest/SourceUploader";
import type { IngestionJob } from "../../types";

interface IngestSidebarProps {
 roomId?: string;
 roomName?: string;
 ingestJobs: IngestionJob[];
 onJobComplete: (job: IngestionJob) => void;
 onClose: () => void;
}

export default function IngestSidebar({
 roomId,
 roomName,
 ingestJobs,
 onJobComplete,
 onClose,
}: IngestSidebarProps) {
 return (
 <div className="w-80 border-l border-default bg-elevated flex flex-col overflow-auto">
 <div className="flex items-center justify-between px-4 py-3 border-b border-default">
 <div className="flex items-center gap-2">
 <Upload size={16} className="text-emerald-500" />
 <h3 className="text-sm font-semibold text-slate-800">Ingest Data</h3>
 </div>
 <button
 onClick={onClose}
 className="text-slate-400 p-1" aria-label="Close ingest panel" >
 <X size={14} />
 </button>
 </div>

 <div className="p-4 flex-1 overflow-auto">
 <p className="text-xs text-slate-500 mb-3">
 Data ingested here is scoped to <span className="font-semibold text-slate-700">{roomName}</span> only.
 </p>
 <SourceUploader
 roomId={roomId}
 onComplete={onJobComplete}
 />
 {ingestJobs.length > 0 && (
 <div className="mt-4">
 <h4 className="text-xs font-semibold text-slate-600 mb-2">Recent</h4>
 <div className="space-y-1.5">
 {ingestJobs.map((job) => (
 <div
 key={job.artifact_id}
 className="flex items-center justify-between bg-muted/50 rounded-lg px-3 py-2" >
 <div className="flex items-center gap-2">
 {job.status ==="completed" ? (
 <CheckCircle size={14} className="text-emerald-500" aria-hidden="true" />
 ) : job.status ==="failed" ? (
 <XCircle size={14} className="text-red-500" aria-hidden="true" />
 ) : (
 <Clock size={14} className="text-amber-500" aria-hidden="true" />
 )}
 <span className="text-xs text-slate-700">
 {job.source_type} &middot; {job.chunk_count} chunks
 </span>
 </div>
 <span className={`text-2xs capitalize font-medium ${
 job.status ==="completed" ? "text-emerald-600" :
 job.status ==="failed" ? "text-red-600" : "text-amber-600"
 }`}>{job.status}</span>
 </div>
 ))}
 </div>
 </div>
 )}
 </div>
 </div>
 );
}
