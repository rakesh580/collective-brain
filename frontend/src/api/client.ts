import type {
  QueryResponse,
  Member,
  MemberDetail,
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
  ExpertiseMatrixData,
  Room,
  RoomDetail,
  RoomMessage,
  RoomListResponse,
} from "../types";

const API_BASE = "/api";

function getAuthToken(): string | null {
  return localStorage.getItem("cb_token");
}

function handle401(res: Response): void {
  if (res.status === 401) {
    localStorage.removeItem("cb_token");
    if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
      window.location.href = "/login";
    }
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
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
  handle401(res);
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
  authLogin: (data: { username: string; password: string }) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  authProfile: () => request<User>("/auth/me"),
  authUpdateProfile: (data: Partial<User>) =>
    request<User>("/auth/me", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  getUsers: () => request<User[]>("/auth/users"),

  // Query
  query: (question: string, conversationId?: string, filters?: Record<string, unknown>) =>
    request<QueryResponse>("/query", {
      method: "POST",
      body: JSON.stringify({ question, conversation_id: conversationId, filters }),
    }),

  // Members
  getMembers: () => request<Member[]>("/members"),
  getMember: (id: string) => request<MemberDetail>(`/members/${id}`),
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
  getDashboard: () => request<DashboardData>("/insights/dashboard"),
  getWeeklySummary: () => request<WeeklySummary>("/insights/weekly"),
  getPatterns: () => request<Insight[]>("/insights/patterns"),
  generateInsights: () =>
    request<Insight[]>("/insights/generate", { method: "POST" }),

  // Graph
  getFullGraph: () => request<GraphData>("/graph/full"),
  getMemberGraph: (id: string) => request<GraphData>(`/graph/member/${id}`),
  getTopicGraph: (topic: string) => request<GraphData>(`/graph/topic/${topic}`),
  getExpertiseMatrix: () => request<ExpertiseMatrixData>("/graph/expertise-matrix"),

  // Ingest
  ingestGit: (repoPath: string, branch = "main", sinceDays = 90) =>
    request<IngestionJob>("/ingest/git", {
      method: "POST",
      body: JSON.stringify({ repo_path: repoPath, branch, since_days: sinceDays }),
    }),
  ingestMarkdown: (directoryPath: string) =>
    request<IngestionJob>("/ingest/markdown", {
      method: "POST",
      body: JSON.stringify({ directory_path: directoryPath }),
    }),
  ingestMarkdownFiles: async (files: File[]): Promise<IngestionJob> => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    for (const f of files) {
      form.append("files", f);
    }
    const res = await fetch(`${API_BASE}/ingest/markdown-upload`, {
      method: "POST",
      headers,
      body: form,
    });
    handle401(res);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Upload error ${res.status}: ${text}`);
    }
    return res.json();
  },
  ingestDocuments: async (files: File[]): Promise<IngestionJob> => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    for (const f of files) {
      form.append("files", f);
    }
    const res = await fetch(`${API_BASE}/ingest/documents`, {
      method: "POST",
      headers,
      body: form,
    });
    handle401(res);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Upload error ${res.status}: ${text}`);
    }
    return res.json();
  },
  ingestFile: async (sourceType: string, file: File): Promise<IngestionJob> => {
    const token = getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/ingest/${sourceType}`, {
      method: "POST",
      headers,
      body: form,
    });
    handle401(res);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Upload error ${res.status}: ${text}`);
    }
    return res.json();
  },

  // Conversations
  getConversations: (limit = 20, offset = 0) =>
    request<ConversationListResponse>(`/conversations?limit=${limit}&offset=${offset}`),
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
  getArtifacts: (sourceType?: string, limit = 50, offset = 0) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (sourceType) params.set("source_type", sourceType);
    return request<ArtifactListResponse>(`/artifacts?${params}`);
  },
  deleteArtifact: (id: string) =>
    request<{ status: string; artifact_id: string }>(`/artifacts/${id}`, { method: "DELETE" }),

  // Analytics
  getActivityTimeline: (days = 30) =>
    request<ActivityTimeline>(`/analytics/activity-timeline?days=${days}`),
  getSourceBreakdown: () =>
    request<SourceBreakdown>("/analytics/source-breakdown"),
  getAnalyticsExpertiseMatrix: () =>
    request<ExpertiseMatrix>("/analytics/expertise-matrix"),
  getContributionTypes: () =>
    request<ContributionTypes>("/analytics/contribution-types"),
  getMemberActivity: (days = 30) =>
    request<MemberActivity>(`/analytics/member-activity?days=${days}`),
  getTopicTrends: (days = 30) =>
    request<TopicTrends>(`/analytics/topic-trends?days=${days}`),

  // Discussions
  createThread: (data: { title: string; context_type?: string; context_id?: string }) =>
    request<DiscussionThread>("/discussions", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getThreads: (params?: { context_type?: string; context_id?: string; status?: string; limit?: number; offset?: number }) => {
    const p = new URLSearchParams();
    if (params?.context_type) p.set("context_type", params.context_type);
    if (params?.context_id) p.set("context_id", params.context_id);
    if (params?.status) p.set("status", params.status);
    if (params?.limit) p.set("limit", String(params.limit));
    if (params?.offset) p.set("offset", String(params.offset));
    return request<DiscussionThreadListResponse>(`/discussions?${p}`);
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
  createRoom: (data: { name: string; description?: string; member_user_ids?: string[] }) =>
    request<Room>("/rooms", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getRooms: (limit = 50, offset = 0) =>
    request<RoomListResponse>(`/rooms?limit=${limit}&offset=${offset}`),
  getRoom: (id: string) =>
    request<RoomDetail>(`/rooms/${id}`),
  updateRoom: (id: string, data: { name?: string; description?: string }) =>
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
  search: (q: string, limit = 20) =>
    request<SearchResults>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`),
};
