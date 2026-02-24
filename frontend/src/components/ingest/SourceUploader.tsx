import { useState, type FormEvent } from "react";
import { api } from "../../api/client";
import type { IngestionJob } from "../../types";

interface Props {
  onComplete: (job: IngestionJob) => void;
}

type SourceType = "git" | "markdown" | "documents" | "slack" | "discord" | "tasks";

interface SourceConfig {
  label: string;
  inputType: "path" | "file";
  accept?: string;
  multiple?: boolean;
  description: string;
}

const sourceConfigs: Record<SourceType, SourceConfig> = {
  git: {
    label: "Git Repository",
    inputType: "path",
    description: "Enter a GitHub URL or local path to a Git repository",
  },
  markdown: {
    label: "Markdown / Docs",
    inputType: "file",
    accept: ".md,.txt,.markdown,.zip",
    multiple: true,
    description: "Upload .md, .txt, or .zip files from your computer",
  },
  documents: {
    label: "PDF / Word / Text",
    inputType: "file",
    accept: ".pdf,.docx,.doc,.txt",
    multiple: true,
    description: "Upload PDF, Word (.docx), or text files — text is auto-extracted",
  },
  slack: {
    label: "Slack Export",
    inputType: "file",
    accept: ".zip",
    description: "Upload a Slack export ZIP file",
  },
  discord: {
    label: "Discord Export",
    inputType: "file",
    accept: ".json",
    description: "Upload a Discord JSON export",
  },
  tasks: {
    label: "Task List",
    inputType: "file",
    accept: ".json,.csv",
    description: "Upload a JSON or CSV task list",
  },
};

export default function SourceUploader({ onComplete }: Props) {
  const [sourceType, setSourceType] = useState<SourceType>("markdown");
  const [path, setPath] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const config = sourceConfigs[sourceType];

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      let result: IngestionJob;

      if (sourceType === "git") {
        result = await api.ingestGit(path);
      } else if (sourceType === "markdown") {
        if (files.length === 0) throw new Error("Please select files to upload");
        result = await api.ingestMarkdownFiles(files);
      } else if (sourceType === "documents") {
        if (files.length === 0) throw new Error("Please select files to upload");
        result = await api.ingestDocuments(files);
      } else if (files.length > 0) {
        result = await api.ingestFile(sourceType, files[0]);
      } else {
        throw new Error("Please select a file");
      }

      onComplete(result);
      setPath("");
      setFiles([]);
      // Reset the file input
      const fileInput = document.querySelector<HTMLInputElement>('input[type="file"]');
      if (fileInput) fileInput.value = "";
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Ingestion failed";
      // Parse API error JSON into a friendly message
      try {
        const match = raw.match(/(?:API|Upload) error \d+: (.+)/);
        if (match) {
          const body = JSON.parse(match[1]);
          setError(typeof body.detail === "string" ? body.detail : raw);
        } else {
          setError(raw);
        }
      } catch {
        setError(raw);
      }
    } finally {
      setLoading(false);
    }
  };

  const isDisabled =
    loading || (config.inputType === "path" ? !path : files.length === 0);

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-slate-200 p-6">
      <div className="flex gap-2 mb-4 flex-wrap">
        {(Object.keys(sourceConfigs) as SourceType[]).map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => {
              setSourceType(type);
              setPath("");
              setFiles([]);
              setError(null);
            }}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              sourceType === type
                ? "bg-indigo-600 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {sourceConfigs[type].label}
          </button>
        ))}
      </div>

      <p className="text-sm text-slate-500 mb-3">{config.description}</p>

      {config.inputType === "path" ? (
        <input
          type="text"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="https://github.com/user/repo or /path/to/repo"
          className="w-full px-4 py-2.5 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      ) : (
        <div>
          <input
            type="file"
            accept={config.accept}
            multiple={config.multiple}
            onChange={(e) => {
              const selected = e.target.files;
              if (selected) setFiles(Array.from(selected));
            }}
            className="w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
          />
          {files.length > 1 && (
            <p className="text-xs text-slate-400 mt-1.5">
              {files.length} files selected: {files.map((f) => f.name).join(", ")}
            </p>
          )}
        </div>
      )}

      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}

      <button
        type="submit"
        disabled={isDisabled}
        className="mt-4 px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "Ingesting..." : "Ingest"}
      </button>
    </form>
  );
}
