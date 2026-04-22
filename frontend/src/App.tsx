import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import PageShell from "./components/layout/PageShell";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import FeatureErrorBoundary from "./components/FeatureErrorBoundary";
import { useAuth } from "./hooks/useAuth";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import AuthCallbackPage from "./pages/AuthCallbackPage";
import DashboardPage from "./pages/DashboardPage";
import ChatPage from "./pages/ChatPage";
import IngestPage from "./pages/IngestPage";
import { MemberList, MemberDetailView } from "./pages/MembersPage";
import SettingsPage from "./pages/SettingsPage";

// Lazy-load heavy pages to reduce initial bundle size
const LandingPage = lazy(() => import("./pages/LandingPage"));
const GraphPage = lazy(() => import("./pages/GraphPage"));
const PulsePage = lazy(() => import("./pages/PulsePage"));
const DecisionsHubPage = lazy(() => import("./pages/DecisionsHubPage"));
const OrganizationsPage = lazy(() => import("./pages/OrganizationsPage"));

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" role="status">
        <span className="sr-only">Loading...</span>
      </div>
    </div>
  );
}

/** Wrap a page element with error boundary + suspense fallback */
function guarded(element: React.ReactNode, name: string) {
  return (
    <FeatureErrorBoundary featureName={name}>
      <Suspense fallback={<PageFallback />}>{element}</Suspense>
    </FeatureErrorBoundary>
  );
}

/** Redirect to dashboard if authenticated, otherwise show landing page */
function LandingOrDashboard() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <PageFallback />;
  if (user) return <Navigate to="/dashboard" replace />;
  return (
    <Suspense fallback={<PageFallback />}>
      <LandingPage />
    </Suspense>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingOrDashboard />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route
        element={
          <ProtectedRoute>
            <PageShell />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={guarded(<DashboardPage />, "Dashboard")} />
        <Route path="/pulse" element={guarded(<PulsePage />, "Pulse")} />
        <Route path="/graph" element={guarded(<GraphPage />, "Knowledge Graph")} />
        <Route path="/decisions" element={guarded(<DecisionsHubPage />, "Decisions")} />
        <Route path="/ask" element={guarded(<ChatPage />, "Ask")} />
        {/* Legacy deep-link redirects */}
        <Route path="/chat" element={<Navigate to="/ask" replace />} />
        <Route path="/analytics" element={<Navigate to="/pulse#analytics" replace />} />
        <Route path="/health" element={<Navigate to="/pulse#health" replace />} />
        <Route path="/risk-radar" element={<Navigate to="/pulse#risk" replace />} />
        <Route path="/continuity" element={<Navigate to="/pulse#continuity" replace />} />
        <Route path="/decision-graph" element={<Navigate to="/decisions#map" replace />} />
        <Route path="/who-decides" element={<Navigate to="/decisions#who" replace />} />
        {/* Removed features — redirect to dashboard */}
        <Route path="/rooms" element={<Navigate to="/dashboard" replace />} />
        <Route path="/rooms/:roomId" element={<Navigate to="/dashboard" replace />} />
        <Route path="/discussions" element={<Navigate to="/dashboard" replace />} />
        <Route path="/onboarding" element={<Navigate to="/dashboard" replace />} />
        <Route path="/org-xray" element={<Navigate to="/dashboard" replace />} />
        <Route path="/public-kb" element={<Navigate to="/dashboard" replace />} />
        {/* Accessible but not in sidebar — reachable via Dashboard / Member detail / Settings */}
        <Route path="/ingest" element={guarded(<IngestPage />, "Data Ingestion")} />
        <Route path="/members" element={guarded(<MemberList />, "Members")} />
        <Route path="/members/:id" element={guarded(<MemberDetailView />, "Member Detail")} />
        <Route path="/settings" element={guarded(<SettingsPage />, "Settings")} />
        <Route path="/organizations" element={guarded(<OrganizationsPage />, "Organizations")} />
      </Route>
    </Routes>
  );
}
