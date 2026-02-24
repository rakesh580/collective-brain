import { useNavigate } from "react-router-dom";

interface Props {
  contextType: "member" | "insight";
  contextId: string;
  label?: string;
}

export default function DiscussButton({ contextType, contextId, label = "Discuss" }: Props) {
  const navigate = useNavigate();

  return (
    <button
      onClick={() =>
        navigate(`/discussions?context_type=${contextType}&context_id=${contextId}`)
      }
      className="text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-1 rounded hover:bg-indigo-50 transition-colors"
    >
      {label}
    </button>
  );
}
