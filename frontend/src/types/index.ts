export interface Member {
  id: string;
  name: string;
  aliases: string[];
  email: string | null;
  expertise_tags: string[];
  expertise_scores: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  last_active: string;
  total_contributions: number;
}

export interface MembersListResponse {
  members: Member[];
  total: number;
}

export interface MemberDetail extends Member {
  contributions: Contribution[];
}

export interface Contribution {
  id: string;
  contribution_type: string;
  timestamp: string;
  description: string;
  topics: string[];
}

export interface MemberCreateRequest {
  name: string;
  email?: string;
  expertise_tags: string[];
  strengths: string[];
  weaknesses: string[];
}

export interface MemberUpdateRequest {
  name?: string;
  email?: string;
  expertise_tags?: string[];
  strengths?: string[];
  weaknesses?: string[];
}

// Auth
export interface User {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  linked_member_id: string | null;
  is_active: boolean;
  created_at: string;
  auth_provider?: string | null;
  skills: string[];
  role_title: string | null;
  bio: string | null;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  related_members?: RelatedMember[];
  timestamp: string;
  sender_user_id?: string;
  sender_name?: string;
}

export interface Source {
  chunk_id: string;
  text: string;
  source_type: string;
  source_ref: string;
  score: number;
}

export interface RelatedMember {
  id: string;
  name: string;
  relevance: string;
}

export interface QueryResponse {
  answer: string;
  sources: Source[];
  related_members: RelatedMember[];
  conversation_id: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphNode {
  id: string;
  type: string;
  label: string;
  properties: Record<string, unknown>;
  size: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
  label: string;
}

export interface ExpertiseMatrixData {
  members: { id: string; name: string; scores: Record<string, number> }[];
  topics: string[];
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  members: number;
  topics: number;
  artifacts: number;
  communities: number;
  density: number;
  top_members: { id: string; name: string; pagerank: number }[];
}

export interface Insight {
  id: string;
  insight_type: "pattern" | "risk" | "recommendation" | "weekly_summary";
  title: string;
  body: string;
  generated_at: string;
  related_member_ids: string[];
  confidence: number;
}

export interface DashboardData {
  total_members: number;
  total_artifacts: number;
  total_chunks: number;
  top_insights: Insight[];
  active_members: Member[];
}

export interface WeeklySummary {
  summary: string;
  period_start: string;
  period_end: string;
  highlights: string[];
  recommendations: string[];
}

export interface IngestionJob {
  artifact_id: string;
  source_type: string;
  status: "processing" | "completed" | "failed";
  chunk_count: number;
  member_count: number;
}

export interface HealthStatus {
  status: string;
  llm_provider: string;
  llm_available: boolean;
  vector_store_count: number;
  embedding_model: string;
  agent_mode: string;
}

// Conversations
export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  visibility?: "private" | "shared" | "team";
  owner_user_id?: string;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  sources?: Source[];
  related_members?: RelatedMember[];
  created_at: string;
  sender_user_id?: string;
  sender_name?: string;
}

export interface ConversationParticipant {
  user_id: string;
  username: string;
  display_name: string | null;
  role: "owner" | "participant";
  joined_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
  visibility?: "private" | "shared" | "team";
  owner_user_id?: string;
}

export interface ConversationListResponse {
  conversations: Conversation[];
  total: number;
}

// Artifacts
export interface Artifact {
  id: string;
  source_type: string;
  source_path: string;
  title: string;
  ingested_at: string;
  chunk_count: number;
  member_ids: string[];
  status: string;
}

export interface ArtifactListResponse {
  artifacts: Artifact[];
  total: number;
}

// Analytics
export interface TimelinePoint {
  date: string;
  count: number;
}

export interface ActivityTimeline {
  timeline: TimelinePoint[];
  total: number;
}

export interface SourceBreakdown {
  sources: { source_type: string; artifact_count: number }[];
  total_artifacts: number;
  total_chunks: number;
}

export interface ExpertiseMatrix {
  topics: string[];
  members: {
    member_id: string;
    member_name: string;
    scores: Record<string, number>;
  }[];
}

export interface ContributionTypes {
  types: { type: string; count: number }[];
  total: number;
}

export interface MemberActivity {
  activity: { member_id: string; member_name: string; contributions: number }[];
  period_days: number;
}

export interface TopicTrends {
  topics: { topic: string; count: number }[];
  period_days: number;
}

// Discussions
export interface DiscussionThread {
  id: string;
  title: string;
  created_by_user_id: string;
  created_by_username: string;
  created_by_display_name: string | null;
  status: "open" | "closed";
  context_type: "member" | "insight" | null;
  context_id: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface DiscussionMessage {
  id: string;
  thread_id: string;
  user_id: string;
  username: string;
  display_name: string | null;
  content: string;
  created_at: string;
  edited_at: string | null;
  parent_message_id: string | null;
}

export interface DiscussionThreadDetail extends DiscussionThread {
  messages: DiscussionMessage[];
}

export interface DiscussionThreadListResponse {
  threads: DiscussionThread[];
  total: number;
}

// Rooms (Group Collaboration)
export interface Room {
  id: string;
  name: string;
  description: string | null;
  created_by_user_id: string;
  created_by_username: string;
  avatar_color: string;
  is_public?: boolean;
  member_count: number;
  message_count: number;
  last_message_at: string | null;
  last_message_preview: string | null;
  created_at: string;
}

export interface RoomMember {
  user_id: string;
  username: string;
  display_name: string | null;
  role: "admin" | "member";
  joined_at: string;
  is_online: boolean;
  skills: string[];
  role_title: string | null;
}

export interface RoomMessage {
  id: string;
  room_id: string;
  user_id: string | null;
  sender_name: string;
  message_type: "user" | "ai" | "system";
  content: string;
  sources: Source[];
  related_members: RelatedMember[];
  created_at: string;
  edited_at: string | null;
  parent_message_id: string | null;
}

export interface RoomDetail extends Room {
  members: RoomMember[];
  messages: RoomMessage[];
}

export interface RoomListResponse {
  rooms: Room[];
}

// Search
export interface SearchResults {
  query: string;
  results: {
    members: { id: string; name: string; expertise_tags: string[]; total_contributions: number }[];
    artifacts: { id: string; title: string; source_type: string; source_path: string; ingested_at: string; chunk_count: number }[];
    insights: { id: string; insight_type: string; title: string; body: string; generated_at: string; confidence: number }[];
    rooms?: { id: string; name: string; description: string | null; is_public: boolean; created_at: string }[];
  };
  counts: Record<string, number>;
  semantic?: {
    chunks: { chunk_id: string; text: string; source_type: string; source_ref: string; score: number }[];
  };
}

export interface DiscoverRoomsResponse {
  rooms: Room[];
  total: number;
}

// Expert Routing
export interface ExpertRecommendation {
  member_id: string;
  name: string;
  match_score: number;
  expertise_topics: string[];
  last_active: string;
  availability_hint: string;
}

// Slack Integration
export interface SlackWorkspace {
  id: string;
  team_name: string;
  installed_at: string | null;
  is_active: boolean;
}

export interface SlackChannel {
  id: string;
  name: string;
  is_private: boolean;
  member_count: number;
  is_synced: boolean;
  sync_id: string | null;
  sync_mode: string | null;
}

// Slack Digest
export interface DigestPreview {
  period_start: string;
  period_end: string;
  summary: string;
  highlights: string[];
  metrics: {
    total_members: number;
    total_artifacts: number;
    new_contributions: number;
    active_members: number;
    bus_factor_risks: number;
  };
  top_contributors: { name: string; contributions: number }[];
  trending_topics: string[];
}

export interface DigestConfig {
  id: string;
  workspace_id: string;
  channel_id: string;
  channel_name: string;
  schedule_day: number;
  schedule_hour: number;
  enabled: boolean;
  last_sent_at: string | null;
}
