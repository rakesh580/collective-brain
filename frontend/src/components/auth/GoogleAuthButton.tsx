import { useCallback } from "react";
import { useGoogleAuthEnabled } from "../../hooks/useGoogleAuth";
import { useGoogleClientId } from "../../GoogleClientIdContext";

/* ── Google Sign-In icon (official Google "G" as inline SVG) ── */
function GoogleIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59a14.5 14.5 0 0 1 0-9.18l-7.98-6.19a24.0 24.0 0 0 0 0 21.56l7.98-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  );
}

/**
 * Open Google OAuth popup manually — no GSI library dependency.
 * This avoids all the initTokenClient/error_callback issues in iframe contexts.
 */
function openGoogleOAuthPopup(clientId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const redirectUri = window.location.origin;
    const scope = "openid email profile";
    const state = Math.random().toString(36).substring(2);
    const authUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
    authUrl.searchParams.set("client_id", clientId);
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("response_type", "token");
    authUrl.searchParams.set("scope", scope);
    authUrl.searchParams.set("state", state);
    authUrl.searchParams.set("prompt", "select_account");

    const width = 500, height = 600;
    const left = window.screenX + (window.outerWidth - width) / 2;
    const top = window.screenY + (window.outerHeight - height) / 2;
    const popup = window.open(
      authUrl.toString(),
      "google-auth",
      `width=${width},height=${height},left=${left},top=${top},popup=yes`
    );

    if (!popup) {
      reject(new Error("Popup was blocked by the browser"));
      return;
    }

    // Poll the popup for the redirect with the access token
    const interval = setInterval(() => {
      try {
        if (popup.closed) {
          clearInterval(interval);
          reject(new Error("Popup was closed"));
          return;
        }
        // When the popup redirects back to our origin, we can read its URL
        const popupUrl = popup.location.href;
        if (popupUrl.startsWith(redirectUri)) {
          clearInterval(interval);
          popup.close();
          // Extract access_token from the URL fragment
          const hash = new URL(popupUrl).hash.substring(1);
          const params = new URLSearchParams(hash);
          const accessToken = params.get("access_token");
          if (accessToken) {
            resolve(accessToken);
          } else {
            reject(new Error(params.get("error") || "No access token received"));
          }
        }
      } catch {
        // Cross-origin error — popup hasn't redirected back yet, keep polling
      }
    }, 200);

    // Timeout after 2 minutes
    setTimeout(() => {
      clearInterval(interval);
      if (!popup.closed) popup.close();
      reject(new Error("Authentication timed out"));
    }, 120000);
  });
}

/* ── Google Login wrapper ── */
export default function GoogleAuthButton({ onError, onAccessTokenSuccess }: {
  onError: () => void;
  onAccessTokenSuccess: (accessToken: string) => void;
}) {
  const enabled = useGoogleAuthEnabled();
  const clientId = useGoogleClientId();

  const handleGoogleClick = useCallback(async () => {
    if (!clientId) {
      console.error("Google client ID not available");
      onError();
      return;
    }
    try {
      const accessToken = await openGoogleOAuthPopup(clientId);
      onAccessTokenSuccess(accessToken);
    } catch (err) {
      console.error("Google OAuth popup error:", err);
      onError();
    }
  }, [clientId, onError, onAccessTokenSuccess]);

  if (!enabled) return null;

  return (
    <>
      <div className="flex items-center gap-4 my-5">
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent" />
        <span className="text-2xs text-slate-500 uppercase tracking-[0.2em] font-medium">or</span>
        <div className="flex-1 h-px bg-gradient-to-r from-transparent via-slate-600/50 to-transparent" />
      </div>

      {/* Custom styled button — works in all contexts via manual OAuth popup */}
      <button
        type="button"
        onClick={handleGoogleClick}
          className="w-full relative flex items-center justify-center gap-3 py-3.5 px-5 rounded-xl
            text-white font-medium cursor-pointer
            transition-all duration-300 hover:scale-[1.01] hover:shadow-xl hover:shadow-indigo-500/15
            overflow-hidden group/google"
          style={{
            background: "linear-gradient(135deg, rgba(25,22,50,0.95) 0%, rgba(35,30,65,0.95) 50%, rgba(30,25,55,0.95) 100%)",
            border: "1px solid rgba(99,102,241,0.2)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)",
          }}
        >
          {/* Animated gradient border glow */}
          <div
            className="absolute -inset-[1px] rounded-xl opacity-0 group-hover/google:opacity-100 transition-opacity duration-500 blur-[0.5px]"
            style={{
              background: "linear-gradient(135deg, rgba(99,102,241,0.4), rgba(139,92,246,0.3), rgba(99,102,241,0.4))",
            }}
          />
          {/* Inner background to cover the border glow */}
          <div
            className="absolute inset-[1px] rounded-[11px]"
            style={{
              background: "linear-gradient(135deg, rgba(25,22,50,0.98) 0%, rgba(35,30,65,0.98) 50%, rgba(30,25,55,0.98) 100%)",
            }}
          />
          {/* Shimmer sweep on hover */}
          <div
            className="absolute inset-0 opacity-0 group-hover/google:opacity-100 transition-opacity duration-500"
            style={{
              background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.05) 50%, transparent 100%)",
              animation: "shimmer 2s infinite",
            }}
          />
          {/* Button content */}
          <div className="relative z-10 flex items-center justify-center gap-3">
            <div className="w-7 h-7 flex items-center justify-center rounded-lg bg-white/[0.08] backdrop-blur-sm border border-white/[0.06]">
              <GoogleIcon />
            </div>
            <span className="text-sm tracking-wide">Continue with Google</span>
          </div>
        </button>
    </>
  );
}
