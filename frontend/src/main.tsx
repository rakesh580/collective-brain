import { StrictMode, useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { GoogleOAuthProvider } from "@react-oauth/google";
import { AuthProvider } from "./hooks/useAuth";
import { ThemeProvider } from "./hooks/useTheme";
import { GoogleAuthEnabledContext } from "./hooks/useGoogleAuth";
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
    api
      .authConfig()
      .then((config) => {
        if (config.google_client_id) {
          setGoogleClientId(config.google_client_id);
        }
      })
      .catch(() => {})
      .finally(() => setReady(true));
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

  // Only wrap with GoogleOAuthProvider when client ID is available
  if (googleClientId) {
    return (
      <GoogleAuthEnabledContext.Provider value={true}>
        <GoogleOAuthProvider clientId={googleClientId}>{app}</GoogleOAuthProvider>
      </GoogleAuthEnabledContext.Provider>
    );
  }

  return <GoogleAuthEnabledContext.Provider value={false}>{app}</GoogleAuthEnabledContext.Provider>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  </StrictMode>
);
