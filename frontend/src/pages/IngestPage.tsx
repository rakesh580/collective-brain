import { useState } from "react";
import SourceUploader from "../components/ingest/SourceUploader";
import type { IngestionJob } from "../types";
import { Upload, CheckCircle, XCircle, Clock } from "lucide-react";

export default function IngestPage() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);

  const handleComplete = (job: IngestionJob) => {
    setJobs((prev) => [job, ...prev]);
  };

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-2 mb-1">
        <Upload size={20} className="text-slate-500" />
        <h2 className="text-lg font-bold text-slate-800 dark:text-white">Ingest Data</h2>
      </div>
      <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
        Feed your team's artifacts into the Collective Brain
      </p>

      <SourceUploader onComplete={handleComplete} />

      {jobs.length > 0 && (
        <div className="mt-8">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200 mb-3">Recent Ingestions</h3>
          <div className="space-y-2">
            {jobs.map((job) => (
              <div
                key={job.artifact_id}
                className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 flex items-center justify-between card-hover"
              >
                <div className="flex items-center gap-3">
                  {job.status === "completed" ? (
                    <CheckCircle size={16} className="text-emerald-500" />
                  ) : job.status === "failed" ? (
                    <XCircle size={16} className="text-red-500" />
                  ) : (
                    <Clock size={16} className="text-amber-500" />
                  )}
                  <div>
                    <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
                      {job.source_type}
                    </span>
                    <span className="text-xs text-slate-400 ml-2">
                      {job.chunk_count} chunks · {job.member_count} members
                    </span>
                  </div>
                </div>
                <span className={`text-xs capitalize font-medium ${
                  job.status === "completed" ? "text-emerald-600 dark:text-emerald-400" :
                  job.status === "failed" ? "text-red-600 dark:text-red-400" :
                  "text-amber-600 dark:text-amber-400"
                }`}>{job.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
