import type {
  QueryResponse,
  Member,
  MemberDetail,
  MembersListResponse,
  MemberCreateRequest,
  MemberUpdateRequest,
  DashboardData,
  WeeklySummary,
  Insight,
  GraphData,
  IngestionJob,
  HealthStatus,
  ConversationListResponse,
  ConversationDetail,
  ArtifactListResponse,
  ActivityTimeline,
  SourceBreakdown,
  ExpertiseMatrix,
  ContributionTypes,
  MemberActivity,
  TopicTrends,
  SearchResults,
  AuthResponse,
  User,
  ConversationParticipant,
  DiscussionThread,
  DiscussionThreadDetail,
  DiscussionThreadListResponse,
  DiscussionMessage,
  DiscoverRoomsResponse,
  ExpertiseMatrixData,
  ExpertRecommendation,
  GraphStats,
  Room,
  RoomDetail,
  RoomMessage,
  RoomListResponse,
  SlackWorkspace,
  SlackChannel,
  DigestPreview,
  DigestConfig,
  FreshnessReport,
  FreshnessAlert,
  HealthSnapshot,
  HealthSnapshotRecord,
  HealthPrediction,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

function getAuthToken(): string | null {
  return localStorage.getItem("cb_token");
}

function getRefreshToken(): string | null {
  return localStorage.getItem("cb_refresh_token");
}

let refreshPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("cb_token", data.token);
    localStorage.setItem("cb_refresh_token", data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

function clearAuthAndRedirect(): void {
  localStorage.removeItem("cb_token");
  localStorage.removeItem("cb_refresh_token");
  const authPages = ["/login", "/register", "/forgot-password"];
  if (!authPages.includes(window.location.pathname)) {
    window.location.href = "/login";
  }
}

async function request<T>(path: string, options?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });
  if (res.status === 401 && token && path !== "/auth/refresh") {
    // Deduplicate concurrent refresh attempts
    if (!refreshPromise) {
      refreshPromise = tryRefreshToken().finally(() => { refreshPromise = null; });
    }
    const refreshed = await refreshPromise;
    if (refreshed) {
      // Retry the original request with the new token
      const retryHeaders = { ...headers, Authorization: `Bearer ${localStorage.getItem("cb_token")}` };
      const retryRes = await fetch(`${API_BASE}${path}`, { ...options, headers: retryHeaders });
      if (!retryRes.ok) {
        if (retryRes.status === 401) {
          clearAuthAndRedirect();
        }
        const text = await retryRes.text();
        throw new Error(`API error ${retryRes.status}: ${text}`);
      }
      return retryRes.json();
    }
    clearAuthAndRedirect();
    throw new Error("API error 401: Session expired");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => request<HealthStatus>("/health"),

  // Auth
  authRegister: (data: { username: string; email: string; password: string; display_name?: string }) =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  authConfig: (signal?: AbortSignal) =>
    request<{ google_client_id: string; google_enabled: boolean }>("/auth/config", { signal }),
  authLogin: (data: { username: string; password: string }) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  authGoogle: (credential: string) =>
    request<AuthResponse>("/auth/google", {
      method: "POST",
      body: JSON.stringify({ credential }),
    }),
  authGoogleAccessToken: (accessToken: string) =>
    request<AuthResponse>("/auth/google-token", {
      method: "POST",
      body: JSON.stringify({ access_token: accessToken }),
    }),
  authForgotPassword: (email: string) =>
    request<{ message: string; code?: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  authResetPassword: (email: string, code: string, new_password: string) =>
    request<AuthResponse>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ email, code, new_password }),
    }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ status: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),
  authRefresh: (refreshToken: string) =>
    request<AuthResponse>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
  authProfile: () => request<User>("/auth/me"),
  authUpdateProfile: (data: Partial<User>) =>
    request<User>("/auth/me", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  getUsers: (signal?: AbortSignal) => request<User[]>("/auth/users", { signal }),

  // Query
  query: (question: string, conversationId?: string, filters?: Record<string, unknown>, roomId?: string) =>
    request<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({ question, conversation_id: conversationId, filters, room_id: roomId }),
    }),

  // Members
  getMembers: (roomId?: string, limit = 50, offset = 0, signal?: AbortSignal) => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (roomId) p.set("room_id", roomId);
    return request<MembersListResponse>(`/members?${p}`, { signal });
  },
  getMember: (id: string, roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<MemberDetail>(`/members/${id}${p}`);
  },
  updateAliases: (id: string, aliases: string[]) =>
    request<Member>(`/members/${id}/aliases`, {
      method: "PUT",
      body: JSON.stringify({ aliases }),
    }),
  createMember: (data: MemberCreateRequest) =>
    request<Member>("/members", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateMember: (id: string, data: MemberUpdateRequest) =>
    request<Member>(`/members/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  deleteMember: (id: string) =>
    request<{ status: string; member_id: string }>(`/members/${id}`, {
      method: "DELETE",
    }),

  // Insights
  getDashboard: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<DashboardData>(`/insights/dashboard${p}`);
  },
  getWeeklySummary: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<WeeklySummary>(`/insights/weekly${p}`);
  },
  getPatterns: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<Insight[]>(`/insights/patterns${p}`);
  },
  generateInsights: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<Insight[]>(`/insights/generate${p}`, { method: "POST" });
  },

  // Graph
  getFullGraph: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<GraphData>(`/graph/full${p}`);
  },
  getMemberGraph: (id: string, roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<GraphData>(`/graph/member/${id}${p}`);
  },
  getTopicGraph: (topic: string, roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<GraphData>(`/graph/topic/${encodeURIComponent(topic)}${p}`);
  },
  getExpertiseMatrix: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<ExpertiseMatrixData>(`/graph/expertise-matrix${p}`);
  },
  getGraphStats: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<GraphStats>(`/graph/stats${p}`);
  },
  getGraphClusters: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<any>(`/graph/clusters${p}`);
  },
  getExpertiseGaps: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<any>(`/graph/expertise-gaps${p}`);
  },

  // Ingest
  ingestGit: (repoPath: string, branch = "main", sinceDays = 90, roomId?: string) =>
    request<IngestionJob>("/ingest/git", {
      method: "POST",
      body: JSON.stringify({ repo_path: repoPath, branch, since_days: sinceDays, room_id: roomId }),
    }),
  ingestMarkdown: (directoryPath: string, roomId?: string) =>
    request<IngestionJob>("/ingest/markdown", {
      method: "POST",
      body: JSON.stringify({ directory_path: directoryPath, room_id: roomId }),
    }),
  ingestMarkdownFiles: async (files: File[], roomId?: string): Promise<IngestionJob> => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    for (const f of files) {
      form.append("files", f);
    }
    const q = roomId ? `?room_id=${roomId}` : "";
    const res = await fetch(`${API_BASE}/ingest/markdown-upload${q}`, {
      method: "POST",
      headers,
      body: form,
    });
    if (res.status === 401) clearAuthAndRedirect();
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Upload error ${res.status}: ${text}`);
    }
    return res.json();
  },
  ingestDocuments: async (files: File[], roomId?: string): Promise<IngestionJob> => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    for (const f of files) {
      form.append("files", f);
    }
    const q = roomId ? `?room_id=${roomId}` : "";
    const res = await fetch(`${API_BASE}/ingest/documents${q}`, {
      method: "POST",
      headers,
      body: form,
    });
    if (res.status === 401) clearAuthAndRedirect();
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Upload error ${res.status}: ${text}`);
    }
    return res.json();
  },
  ingestFile: async (sourceType: string, file: File, roomId?: string): Promise<IngestionJob> => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    form.append("file", file);
    const q = roomId ? `?room_id=${roomId}` : "";
    const res = await fetch(`${API_BASE}/ingest/${sourceType}${q}`, {
      method: "POST",
      headers,
      body: form,
    });
    if (res.status === 401) clearAuthAndRedirect();
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Upload error ${res.status}: ${text}`);
    }
    return res.json();
  },

  // Conversations
  getConversations: (limit = 20, offset = 0, roomId?: string, signal?: AbortSignal) => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (roomId) p.set("room_id", roomId);
    return request<ConversationListResponse>(`/conversations?${p}`, { signal });
  },
  getConversation: (id: string) =>
    request<ConversationDetail>(`/conversations/${id}`),
  deleteConversation: (id: string) =>
    request<{ status: string }>(`/conversations/${id}`, { method: "DELETE" }),
  shareConversation: (id: string, userIds: string[]) =>
    request<{ status: string }>(`/conversations/${id}/share`, {
      method: "POST",
      body: JSON.stringify({ user_ids: userIds }),
    }),
  getParticipants: (id: string) =>
    request<ConversationParticipant[]>(`/conversations/${id}/participants`),
  removeParticipant: (conversationId: string, userId: string) =>
    request<{ status: string }>(`/conversations/${conversationId}/participants/${userId}`, {
      method: "DELETE",
    }),

  // Artifacts
  getArtifacts: (sourceType?: string, limit = 50, offset = 0, roomId?: string) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (sourceType) params.set("source_type", sourceType);
    if (roomId) params.set("room_id", roomId);
    return request<ArtifactListResponse>(`/artifacts?${params}`);
  },
  deleteArtifact: (id: string) =>
    request<{ status: string; artifact_id: string }>(`/artifacts/${id}`, { method: "DELETE" }),

  // Analytics
  getActivityTimeline: (days = 30, roomId?: string) => {
    const p = new URLSearchParams({ days: String(days) });
    if (roomId) p.set("room_id", roomId);
    return request<ActivityTimeline>(`/analytics/activity-timeline?${p}`);
  },
  getSourceBreakdown: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<SourceBreakdown>(`/analytics/source-breakdown${p}`);
  },
  getAnalyticsExpertiseMatrix: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<ExpertiseMatrix>(`/analytics/expertise-matrix${p}`);
  },
  getContributionTypes: (roomId?: string) => {
    const p = roomId ? `?room_id=${roomId}` : "";
    return request<ContributionTypes>(`/analytics/contribution-types${p}`);
  },
  getMemberActivity: (days = 30, roomId?: string) => {
    const p = new URLSearchParams({ days: String(days) });
    if (roomId) p.set("room_id", roomId);
    return request<MemberActivity>(`/analytics/member-activity?${p}`);
  },
  getTopicTrends: (days = 30, roomId?: string) => {
    const p = new URLSearchParams({ days: String(days) });
    if (roomId) p.set("room_id", roomId);
    return request<TopicTrends>(`/analytics/topic-trends?${p}`);
  },

  // Discussions
  createThread: (data: { title: string; context_type?: string; context_id?: string; room_id?: string }) =>
    request<DiscussionThread>("/discussions", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getThreads: (params?: { context_type?: string; context_id?: string; status?: string; room_id?: string; limit?: number; offset?: number }, signal?: AbortSignal) => {
    const p = new URLSearchParams();
    if (params?.context_type) p.set("context_type", params.context_type);
    if (params?.context_id) p.set("context_id", params.context_id);
    if (params?.status) p.set("status", params.status);
    if (params?.room_id) p.set("room_id", params.room_id);
    if (params?.limit) p.set("limit", String(params.limit));
    if (params?.offset) p.set("offset", String(params.offset));
    return request<DiscussionThreadListResponse>(`/discussions?${p}`, { signal });
  },
  getThread: (id: string) =>
    request<DiscussionThreadDetail>(`/discussions/${id}`),
  addDiscussionMessage: (threadId: string, content: string, parentMessageId?: string) =>
    request<DiscussionMessage>(`/discussions/${threadId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, parent_message_id: parentMessageId }),
    }),
  editDiscussionMessage: (threadId: string, messageId: string, content: string) =>
    request<DiscussionMessage>(`/discussions/${threadId}/messages/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  deleteDiscussionMessage: (threadId: string, messageId: string) =>
    request<{ status: string }>(`/discussions/${threadId}/messages/${messageId}`, {
      method: "DELETE",
    }),

  // Rooms (Group Collaboration)
  createRoom: (data: { name: string; description?: string; member_user_ids?: string[]; is_public?: boolean }) =>
    request<Room>("/rooms", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getRooms: (limit = 50, offset = 0, signal?: AbortSignal) =>
    request<RoomListResponse>(`/rooms?limit=${limit}&offset=${offset}`, { signal }),
  discoverRooms: (q?: string, limit = 50, offset = 0, signal?: AbortSignal) => {
    const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (q) p.set("q", q);
    return request<DiscoverRoomsResponse>(`/rooms/discover?${p}`, { signal });
  },
  joinRoom: (roomId: string) =>
    request<{ status: string; room_id: string }>(`/rooms/${roomId}/join`, { method: "POST" }),
  getRoom: (id: string) =>
    request<RoomDetail>(`/rooms/${id}`),
  updateRoom: (id: string, data: { name?: string; description?: string; is_public?: boolean }) =>
    request<{ status: string }>(`/rooms/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  addRoomMembers: (roomId: string, userIds: string[]) =>
    request<{ added: number }>(`/rooms/${roomId}/members`, {
      method: "POST",
      body: JSON.stringify({ user_ids: userIds }),
    }),
  removeRoomMember: (roomId: string, userId: string) =>
    request<{ status: string }>(`/rooms/${roomId}/members/${userId}`, {
      method: "DELETE",
    }),
  sendRoomMessage: (roomId: string, content: string, parentMessageId?: string) =>
    request<RoomMessage>(`/rooms/${roomId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, parent_message_id: parentMessageId }),
    }),
  sendRoomAIQuery: (roomId: string, question: string) =>
    request<RoomMessage>(`/rooms/${roomId}/ai`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  getRoomMessages: (roomId: string, limit = 50, before?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (before) params.set("before", before);
    return request<{ messages: RoomMessage[] }>(`/rooms/${roomId}/messages?${params}`);
  },

  // Search
  search: (q: string, limit = 20, roomId?: string, semantic = false) => {
    const p = new URLSearchParams({ q, limit: String(limit) });
    if (roomId) p.set("room_id", roomId);
    if (semantic) p.set("semantic", "true");
    return request<SearchResults>(`/search?${p}`);
  },

  // Slack Integration
  slackStatus: () =>
    request<{ configured: boolean; has_signing_secret: boolean }>("/slack/status"),
  slackInstall: () =>
    request<{ install_url: string }>("/slack/install"),
  slackWorkspaces: () =>
    request<{ workspaces: SlackWorkspace[] }>("/slack/workspaces"),
  slackDisconnect: (workspaceId: string) =>
    request<{ status: string }>(`/slack/workspaces/${workspaceId}`, { method: "DELETE" }),
  slackChannels: (workspaceId: string) =>
    request<{ channels: SlackChannel[] }>(`/slack/workspaces/${workspaceId}/channels`),
  slackSyncChannel: (workspaceId: string, channelId: string, roomId?: string, syncMode = "ingest") => {
    const p = new URLSearchParams({ sync_mode: syncMode });
    if (roomId) p.set("room_id", roomId);
    return request<{ status: string; sync_id: string; channel_name?: string }>(
      `/slack/workspaces/${workspaceId}/channels/${channelId}/sync?${p}`,
      { method: "POST" }
    );
  },
  slackStopSync: (syncId: string) =>
    request<{ status: string }>(`/slack/syncs/${syncId}`, { method: "DELETE" }),
  slackBackfill: (syncId: string, limit = 200) =>
    request<{ status: string; messages_ingested: number }>(`/slack/syncs/${syncId}/backfill?limit=${limit}`, { method: "POST" }),

  // GitHub Integration
  githubStatus: () =>
    request<{ configured: boolean; webhook_url: string }>("/github/status"),
  githubSetup: () =>
    request<{ configured: boolean; webhook_url: string; instructions: string[]; required_env_vars: string[]; supported_events: string[] }>("/github/setup"),
  githubEvents: (limit = 20) =>
    request<{ events: { id: string; type: string; title: string; source_path: string; chunk_count: number; ingested_at: string | null; member_ids: string[] }[]; total: number }>(`/github/events?limit=${limit}`),

  // Slack Digest
  digestPreview: () => request<{ digest: DigestPreview }>("/slack/digest/preview"),
  digestSend: (workspaceId: string, channelId: string) =>
    request<{ success: boolean; message: string }>("/slack/digest/send", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, channel_id: channelId }),
    }),
  digestConfigure: (config: { workspace_id: string; channel_id: string; schedule_day: number; schedule_hour: number; enabled: boolean }) =>
    request<{ success: boolean }>("/slack/digest/configure", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  digestConfig: () => request<{ config: DigestConfig | null }>("/slack/digest/config"),

  // Expert Routing
  recommendExperts: (query: string, topK = 3) =>
    request<{ experts: ExpertRecommendation[]; query: string; topics: string[] }>(`/experts/recommend?query=${encodeURIComponent(query)}&top_k=${topK}`),
  requestHelp: (expertMemberId: string, query: string, topics: string[]) =>
    request<{ id: string; status: string }>("/experts/request-help", {
      method: "POST",
      body: JSON.stringify({ expert_member_id: expertMemberId, query, topics }),
    }),

  // Knowledge Freshness
  getFreshnessReport: () => request<FreshnessReport>("/insights/freshness"),
  getFreshnessAlerts: () => request<{ alerts: FreshnessAlert[] }>("/insights/freshness/alerts"),

  // Team Health
  getHealthSnapshot: () => request<HealthSnapshot>("/analytics/health"),
  getHealthTrends: (days = 90) =>
    request<{ snapshots: HealthSnapshotRecord[]; period_days: number }>(`/analytics/health/trends?days=${days}`),
  getHealthPredictions: () =>
    request<{ predictions: HealthPrediction[] }>("/analytics/health/predictions"),
  saveHealthSnapshot: () =>
    request<{ success: boolean }>("/analytics/health/snapshot", { method: "POST" }),
};
