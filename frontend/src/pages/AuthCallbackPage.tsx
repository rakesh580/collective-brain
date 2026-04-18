import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const MESSAGE_TYPE = "cb-google-oauth";

function parseFragment(hash: string): { accessToken: string | null; error: string | null } {
  const params = new URLSearchParams(hash.startsWith("#") ? hash.substring(1) : hash);
  return {
    accessToken: params.get("access_token"),
    error: params.get("error") || params.get("error_description"),
  };
}

export default function AuthCallbackPage() {
  const { googleLoginWithToken } = useAuth();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"processing" | "error">("processing");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const handledRef = useRef(false);

  useEffect(() => {
    if (handledRef.current) return;
    handledRef.current = true;

    const { accessToken, error } = parseFragment(window.location.hash);

    // Popup mode: post result back to opener, then close
    if (window.opener && window.opener !== window) {
      try {
        window.opener.postMessage(
          { type: MESSAGE_TYPE, accessToken, error },
          window.location.origin,
        );
      } catch (e) {
        console.error("Failed to postMessage to opener:", e);
      }
      window.close();
      return;
    }

    // Tab/fallback mode: exchange the token directly in this window
    if (error) {
      setStatus("error");
      setErrorMsg(error);
      return;
    }
    if (!accessToken) {
      setStatus("error");
      setErrorMsg("No access token returned from Google");
      return;
    }

    googleLoginWithToken(accessToken)
      .then(() => navigate("/dashboard", { replace: true }))
      .catch((err) => {
        console.error("Google sign-in failed:", err);
        setStatus("error");
        setErrorMsg(err instanceof Error ? err.message : "Sign-in failed");
      });
  }, [googleLoginWithToken, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="text-center">
        {status === "processing" ? (
          <>
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-500 mx-auto mb-4" />
            <p className="text-slate-300">Completing Google sign-in…</p>
          </>
        ) : (
          <>
            <p className="text-red-400 mb-4">Sign-in failed: {errorMsg}</p>
            <button
              type="button"
              onClick={() => navigate("/login", { replace: true })}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500"
            >
              Back to login
            </button>
          </>
        )}
      </div>
    </div>
  );
}
