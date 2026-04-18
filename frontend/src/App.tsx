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
import RoomsPage from "./pages/RoomsPage";

// Lazy-load heavy pages to reduce initial bundle size
const LandingPage = lazy(() => import("./pages/LandingPage"));
const GraphPage = lazy(() => import("./pages/GraphPage"));
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage"));
const DiscussionsPage = lazy(() => import("./pages/DiscussionsPage"));
const RoomChatPage = lazy(() => import("./pages/RoomChatPage"));
const TeamHealthPage = lazy(() => import("./pages/TeamHealthPage"));
const PublicKBPage = lazy(() => import("./pages/PublicKBPage"));
const OrganizationsPage = lazy(() => import("./pages/OrganizationsPage"));
const DecisionsPage = lazy(() => import("./pages/DecisionsPage"));
const RiskRadarPage = lazy(() => import("./pages/RiskRadarPage"));
const ContinuityPage = lazy(() => import("./pages/ContinuityPage"));
const DecisionGraphPage = lazy(() => import("./pages/DecisionGraphPage"));
const WhoShouldDecidePage = lazy(() => import("./pages/WhoShouldDecidePage"));
const OnboardingBriefingPage = lazy(() => import("./pages/OnboardingBriefingPage"));
const OrgXrayPage = lazy(() => import("./pages/OrgXrayPage"));

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
        <Route path="/chat" element={guarded(<ChatPage />, "AI Chat")} />
        <Route path="/ingest" element={guarded(<IngestPage />, "Data Ingestion")} />
        <Route path="/members" element={guarded(<MemberList />, "Members")} />
        <Route path="/members/:id" element={guarded(<MemberDetailView />, "Member Detail")} />
        <Route path="/graph" element={guarded(<GraphPage />, "Knowledge Graph")} />
        <Route path="/analytics" element={guarded(<AnalyticsPage />, "Analytics")} />
        <Route path="/health" element={guarded(<TeamHealthPage />, "Team Health")} />
        <Route path="/decisions" element={guarded(<DecisionsPage />, "Decisions")} />
        <Route path="/risk-radar" element={guarded(<RiskRadarPage />, "Risk Radar")} />
        <Route path="/continuity" element={guarded(<ContinuityPage />, "Continuity")} />
        <Route path="/decision-graph" element={guarded(<DecisionGraphPage />, "Decision Graph")} />
        <Route path="/who-decides" element={guarded(<WhoShouldDecidePage />, "Who Decides")} />
        <Route path="/onboarding" element={guarded(<OnboardingBriefingPage />, "Onboarding")} />
        <Route path="/org-xray" element={guarded(<OrgXrayPage />, "Org X-Ray")} />
        <Route path="/rooms" element={guarded(<RoomsPage />, "Rooms")} />
        <Route path="/rooms/:roomId" element={guarded(<RoomChatPage />, "Room Chat")} />
        <Route path="/discussions" element={guarded(<DiscussionsPage />, "Discussions")} />
        <Route path="/settings" element={guarded(<SettingsPage />, "Settings")} />
        <Route path="/public-kb" element={guarded(<PublicKBPage />, "Public KB")} />
        <Route path="/organizations" element={guarded(<OrganizationsPage />, "Organizations")} />
      </Route>
    </Routes>
  );
}
