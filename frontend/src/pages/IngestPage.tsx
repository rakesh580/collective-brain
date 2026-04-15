import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import SourceUploader from "../components/ingest/SourceUploader";
import type { IngestionJob } from "../types";
import { Upload, CheckCircle, XCircle, Clock, Database } from "lucide-react";

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] } },
};

export default function IngestPage() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);

  const handleComplete = (job: IngestionJob) => {
    setJobs((prev) => [job, ...prev]);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="p-6 max-w-3xl mx-auto"
    >
      {/* Header */}
      <div className="flex items-center gap-2.5 mb-1">
        <div
          className="flex items-center justify-center w-9 h-9 rounded-xl"
          style={{ background: "var(--gradient-brand)", boxShadow: "var(--shadow-brand)" }}
        >
          <Upload size={17} className="text-white" />
        </div>
        <div>
          <h2 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Ingest Data</h2>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            Feed your team's artifacts into the Collective Brain
          </p>
        </div>
      </div>

      <div className="mt-6">
        <SourceUploader onComplete={handleComplete} />
      </div>

      {/* Recent ingestions */}
      <AnimatePresence>
        {jobs.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8"
          >
            <div className="flex items-center gap-2 mb-3">
              <Database size={14} style={{ color: "var(--text-tertiary)" }} />
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Recent Ingestions</h3>
              <span className="badge badge-brand">{jobs.length}</span>
            </div>

            <motion.div
              variants={container}
              initial="hidden"
              animate="show"
              className="space-y-2"
            >
              {jobs.map((job) => {
                const isOk = job.status === "completed";
                const isFail = job.status === "failed";
                const color = isOk ? "#34d399" : isFail ? "#fb7185" : "#fbbf24";

                return (
                  <motion.div
                    key={job.artifact_id}
                    variants={item}
                    className="flex items-center justify-between p-3.5 rounded-xl"
                    style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-default)" }}
                  >
                    <div className="flex items-center gap-3">
                      {isOk ? (
                        <CheckCircle size={16} style={{ color: "#34d399" }} />
                      ) : isFail ? (
                        <XCircle size={16} style={{ color: "#fb7185" }} />
                      ) : (
                        <Clock size={16} style={{ color: "#fbbf24" }} className="animate-pulse" />
                      )}
                      <div>
                        <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                          {job.source_type}
                        </span>
                        <span className="text-xs ml-2" style={{ color: "var(--text-tertiary)" }}>
                          {job.chunk_count} chunks · {job.member_count} members
                        </span>
                      </div>
                    </div>
                    <span className="text-xs capitalize font-semibold" style={{ color }}>
                      {job.status}
                    </span>
                  </motion.div>
                );
              })}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
