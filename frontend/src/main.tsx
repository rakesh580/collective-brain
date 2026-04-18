import { StrictMode, useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "./hooks/useAuth";
import { ThemeProvider } from "./hooks/useTheme";
import { GoogleAuthEnabledContext } from "./hooks/useGoogleAuth";
import { GoogleClientIdProvider } from "./GoogleClientIdContext";
import { api } from "./api/client";
import "./index.css";
import App from "./App.tsx";
import ErrorBoundary from "./components/ErrorBoundary";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function Root() {
  const [googleClientId, setGoogleClientId] = useState<string>(
    import.meta.env.VITE_GOOGLE_CLIENT_ID || ""
  );
  const [ready, setReady] = useState(!!googleClientId);

  // Fetch Google client ID from backend at runtime (needed for Docker/HF Spaces
  // where VITE_ env vars aren't available at build time)
  useEffect(() => {
    if (googleClientId) return;
    const controller = new AbortController();
    api
      .authConfig(controller.signal)
      .then((config) => {
        if (config.google_client_id) {
          setGoogleClientId(config.google_client_id);
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError") console.error("Failed to fetch auth config:", err);
      })
      .finally(() => setReady(true));
    return () => controller.abort();
  }, [googleClientId]);

  if (!ready) return null;

  const app = (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );

  // Expose client ID + enabled flag to descendants; no GSI script is loaded —
  // GoogleAuthButton drives the OAuth popup itself via window.open().
  return (
    <GoogleClientIdProvider value={googleClientId}>
      <GoogleAuthEnabledContext.Provider value={!!googleClientId}>
        {app}
      </GoogleAuthEnabledContext.Provider>
    </GoogleClientIdProvider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  </StrictMode>
);
