#!/usr/bin/env python3
"""Generate Collective Brain technical documentation PDF."""

from fpdf import FPDF


class CBDocument(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, "Collective Brain - Technical Documentation", align="C")
            self.ln(5)
            self.set_draw_color(200, 200, 200)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def cover_page(self):
        self.add_page()
        self.ln(60)
        self.set_font("Helvetica", "B", 36)
        self.set_text_color(30, 30, 80)
        self.cell(0, 15, "Collective Brain", align="C")
        self.ln(15)
        self.set_font("Helvetica", "", 18)
        self.set_text_color(80, 80, 120)
        self.cell(0, 10, "AI-Powered Team Knowledge Management", align="C")
        self.ln(8)
        self.cell(0, 10, "Platform", align="C")
        self.ln(25)
        self.set_draw_color(80, 80, 180)
        self.set_line_width(0.5)
        self.line(60, self.get_y(), 150, self.get_y())
        self.ln(15)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Complete Use Case & Technical Deep Dive", align="C")
        self.ln(8)
        self.cell(0, 8, "Version 0.3.0", align="C")
        self.ln(8)
        self.cell(0, 8, "February 2026", align="C")

    def section_title(self, num, title):
        self.ln(5)
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(30, 30, 80)
        self.cell(0, 12, f"{num}. {title}")
        self.ln(8)
        self.set_draw_color(80, 80, 180)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def sub_title(self, title):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(50, 50, 100)
        self.cell(0, 9, title)
        self.ln(7)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet(self, text, indent=10):
        x = self.get_x()
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.set_x(x + indent)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def bold_bullet(self, bold_part, rest, indent=10):
        x = self.get_x()
        self.set_x(x + indent)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.cell(5, 5.5, "-")
        self.set_font("Helvetica", "B", 10)
        self.write(5.5, bold_part)
        self.set_font("Helvetica", "", 10)
        self.write(5.5, rest)
        self.ln(6)

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(240, 240, 245)
        self.set_text_color(30, 30, 30)
        lines = text.split("\n")
        for line in lines:
            self.cell(0, 5, "  " + line, fill=True)
            self.ln(4.5)
        self.ln(3)

    def table_row(self, cols, widths, bold=False, header=False):
        if header:
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(50, 50, 100)
            self.set_text_color(255, 255, 255)
        elif bold:
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(245, 245, 250)
            self.set_text_color(40, 40, 40)
        else:
            self.set_font("Helvetica", "", 9)
            self.set_fill_color(255, 255, 255)
            self.set_text_color(40, 40, 40)
        for i, (col, w) in enumerate(zip(cols, widths)):
            self.cell(w, 7, str(col), border=1, fill=True)
        self.ln()


def build_pdf():
    pdf = CBDocument()
    pdf.alias_nb_pages()

    # ── Cover Page ──
    pdf.cover_page()

    # ── Table of Contents ──
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 30, 80)
    pdf.cell(0, 12, "Table of Contents")
    pdf.ln(15)
    toc = [
        ("1", "Overview", 3),
        ("2", "Use Cases", 3),
        ("3", "Technical Architecture", 4),
        ("4", "Data Ingestion Pipeline", 6),
        ("5", "AI Query Pipeline", 7),
        ("6", "Knowledge Graph", 9),
        ("7", "Insight Engine", 10),
        ("8", "Room-Scoped Workspaces", 11),
        ("9", "Database Schema", 12),
        ("10", "API Reference", 13),
        ("11", "Frontend Architecture", 15),
        ("12", "Deployment & Infrastructure", 16),
        ("13", "Security & Resilience", 17),
    ]
    for num, title, _ in toc:
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(10, 8, num + ".")
        pdf.cell(0, 8, title)
        pdf.ln(8)

    # ── 1. Overview ──
    pdf.add_page()
    pdf.section_title("1", "Overview")
    pdf.body_text(
        "Collective Brain is an AI-powered team knowledge management platform that ingests "
        "your team's documents, code repositories, chat logs, and task data - then lets you "
        "ask natural language questions, discover expertise, visualize knowledge relationships, "
        "and collaborate in isolated workspaces."
    )
    pdf.ln(3)
    pdf.body_text(
        "Think of it as: Slack's collaboration + Notion's knowledge base + an AI analyst "
        "that understands your entire team's collective knowledge."
    )
    pdf.ln(3)
    pdf.sub_title("Key Capabilities")
    pdf.bold_bullet("AI-Powered Q&A: ", "Ask natural language questions about your team's knowledge, get answers with source citations")
    pdf.bold_bullet("Knowledge Graph: ", "Three-layer graph (Social + Artifact + Concept) with temporal decay")
    pdf.bold_bullet("Expertise Discovery: ", "Find who knows what, identify bus factors and knowledge silos")
    pdf.bold_bullet("Room Workspaces: ", "Isolated collaborative spaces with their own data, analytics, and AI context")
    pdf.bold_bullet("Real-Time Chat: ", "WebSocket-based room messaging with integrated AI queries")
    pdf.bold_bullet("Multi-Source Ingestion: ", "Markdown, Git, Slack, Discord, PDF, DOCX, and task data")
    pdf.bold_bullet("Automated Insights: ", "Weekly summaries, pattern detection, risk identification")

    # ── 2. Use Cases ──
    pdf.add_page()
    pdf.section_title("2", "Use Cases")

    pdf.sub_title('Use Case 1: "Who knows about X?"')
    pdf.body_text(
        'A manager needs to assign a Kubernetes migration task. They ask: "Who has the most '
        'experience with container orchestration?" The AI searches ingested docs, git commits, '
        "and chat logs, then returns members ranked by expertise with source citations showing "
        "exactly where their knowledge was demonstrated."
    )

    pdf.sub_title('Use Case 2: "What happened last week?"')
    pdf.body_text(
        'A team lead returning from vacation asks: "Give me a weekly summary of the team\'s '
        'activity." The Insight Engine analyzes the last 7 days of contributions and generates '
        "an LLM-formatted narrative with highlights, key decisions, and recommendations."
    )

    pdf.sub_title('Use Case 3: "Are we at risk?"')
    pdf.body_text("The system automatically detects organizational patterns:")
    pdf.bold_bullet("Bus Factor Risk: ", "Only one person knows the payment system")
    pdf.bold_bullet("Knowledge Silos: ", "Backend and frontend teams have zero shared artifacts")
    pdf.bold_bullet("Stale Expertise: ", "No one has touched the auth module in 90+ days")
    pdf.bold_bullet("Strong Collaboration: ", "Alice and Bob consistently co-contribute to shared artifacts")

    pdf.sub_title("Use Case 4: Room-Scoped Workspaces")
    pdf.body_text(
        "Each team or project gets an isolated room with its own ingested data, knowledge graph, "
        "analytics, insights, and AI context. Data never leaks between rooms - like separate "
        "Slack workspaces but with full AI-powered knowledge management."
    )

    pdf.sub_title("Use Case 5: Real-Time Team Collaboration")
    pdf.body_text(
        "Team members in a room can chat in real-time via WebSocket, ask the AI questions scoped "
        "to that room's data, start threaded discussions linked to specific insights or members, "
        "and add new members by searching usernames."
    )

    # ── 3. Technical Architecture ──
    pdf.add_page()
    pdf.section_title("3", "Technical Architecture")

    pdf.sub_title("Technology Stack")
    tech_stack = [
        ("Layer", "Technology"),
        ("Frontend", "React 19 + TypeScript 5.9, Vite 7, Tailwind CSS 4"),
        ("Backend", "FastAPI (Python 3.11), Uvicorn ASGI, 2 workers"),
        ("Database", "PostgreSQL (Neon) / SQLite via SQLAlchemy 2.0"),
        ("Vector DB", "ChromaDB 0.5 with HNSW index, cosine similarity"),
        ("Embeddings", "Sentence-Transformers all-MiniLM-L6-v2 (384-dim)"),
        ("LLM", "Multi-provider: Claude, Mistral (HF), Ollama"),
        ("Agent", "LangGraph ReAct agent with 9 tools OR RAG pipeline"),
        ("Auth", "JWT (30min) + bcrypt + Google OAuth"),
        ("Real-time", "WebSocket per room, optional Redis pub/sub"),
        ("Visualization", "react-force-graph-2d, Recharts"),
        ("Deployment", "Docker multi-stage, HuggingFace Spaces + Neon"),
    ]
    widths = [35, 155]
    pdf.table_row(tech_stack[0], widths, header=True)
    for row in tech_stack[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("System Architecture")
    pdf.code_block(
        "User Browser (React SPA)\n"
        "        |\n"
        "        v\n"
        "HuggingFace Spaces Container\n"
        "  +----------------------------------+\n"
        "  | Uvicorn (2 workers)              |\n"
        "  |   FastAPI Application            |\n"
        "  |     +-- Auth (JWT + Google)      |\n"
        "  |     +-- REST API (13 routers)    |\n"
        "  |     +-- WebSocket (rooms)        |\n"
        "  |                                  |\n"
        "  | ChromaDB (Vector Store)          |\n"
        "  |   /data/chroma_db               |\n"
        "  +----------------------------------+\n"
        "        |\n"
        "        v\n"
        "Neon PostgreSQL (Cloud Database)\n"
        "  Users, Rooms, Artifacts, etc."
    )

    # ── 4. Data Ingestion Pipeline ──
    pdf.add_page()
    pdf.section_title("4", "Data Ingestion Pipeline")

    pdf.sub_title("Pipeline Flow")
    pdf.code_block(
        "Source (Markdown, Git, Slack, Discord, PDF, DOCX, Tasks)\n"
        "    |\n"
        "    v\n"
        "Connector (parses format, extracts text + metadata)\n"
        "    |\n"
        "    v\n"
        "Member Resolution (match @mentions, emails, aliases)\n"
        "    |\n"
        "    v\n"
        "Chunking (512 chars, 64 overlap, recursive splitting)\n"
        "    |\n"
        "    v\n"
        "Embedding (all-MiniLM-L6-v2, batch of 64)\n"
        "    |\n"
        "    v\n"
        "Storage:\n"
        "  ArtifactRecord  -> PostgreSQL (metadata, room_id)\n"
        "  ContributionRecord -> PostgreSQL (member, topics)\n"
        "  Vector chunks   -> ChromaDB (embeddings + metadata)"
    )

    pdf.sub_title("Six Ingestion Connectors")
    pdf.bold_bullet("Markdown: ", "Parses .md files with YAML frontmatter, extracts @mentions and topic headers")
    pdf.bold_bullet("Git: ", "Mines commit history - author, message, changed files, branch via GitPython")
    pdf.bold_bullet("Slack: ", "Chat export JSON parsing with user mapping and thread reconstruction")
    pdf.bold_bullet("Discord: ", "Discord export format with role-based member filtering")
    pdf.bold_bullet("Documents: ", "PDF (PyMuPDF) and DOCX (python-docx) text extraction with formatting hints")
    pdf.bold_bullet("Tasks: ", "GitHub/Jira-style issue data with assignee-to-member mapping")

    pdf.sub_title("Chunking Strategy")
    pdf.body_text(
        "Recursive splitting with configurable separators: paragraph breaks, line breaks, sentence "
        "endings, and word boundaries. Default chunk size is 512 characters with 64-character overlap "
        "to maintain context across chunk boundaries. Each chunk carries full metadata: source_type, "
        "source_ref, author, timestamp, artifact_id, and room_id."
    )

    # ── 5. AI Query Pipeline ──
    pdf.add_page()
    pdf.section_title("5", "AI Query Pipeline")

    pdf.sub_title("Mode 1: RAG Pipeline (Simple, Fast)")
    pdf.body_text("The RAG pipeline follows a 5-step process:")
    pdf.ln(2)
    pdf.bold_bullet("1. Intent Classification (rule-based): ", "Categorizes questions into member_recommendation, pattern_analysis, strategy_generation, or general based on keyword matching")
    pdf.bold_bullet("2. Retrieval: ", "Embeds the question using SentenceTransformer, queries ChromaDB with cosine similarity (top-8 chunks), applies optional metadata filters (source types, authors, room_id)")
    pdf.bold_bullet("3. Context Building: ", "Formats retrieved chunks with source metadata using intent-specific templates. Includes member expertise summaries for recommendations and contribution data for pattern analysis")
    pdf.bold_bullet("4. LLM Generation: ", "Loads last 6 conversation messages for continuity, calls the configured LLM provider with system prompt + context (90-second timeout), falls back to a default response if LLM is unavailable")
    pdf.bold_bullet("5. Persistence: ", "Saves user message and assistant response to ConversationRecord, extracts related member names from the response, stores source references with relevance scores")

    pdf.sub_title("Mode 2: LangGraph Agent (Autonomous, Reasoning)")
    pdf.body_text(
        "The LangGraph agent uses a ReAct (Reasoning + Acting) loop with 9 available tools. "
        "It autonomously decides which tools to call, reasons about the results, and can chain "
        "multiple tool calls to build a comprehensive answer."
    )
    pdf.ln(2)

    tools = [
        ("Tool", "Description"),
        ("search_knowledge", "Semantic search across all ingested data"),
        ("get_member_profile", "Full member expertise + recent contributions"),
        ("list_team_members", "All members with tags and contribution counts"),
        ("find_experts", "Graph-based: who connects to a given topic"),
        ("get_contributions", "Member's activity over N days"),
        ("analyze_patterns", "Bus factors, silos, stale expertise detection"),
        ("get_topic_network", "2-hop topic subgraph visualization"),
        ("get_weekly_summary", "Cached or freshly generated weekly narrative"),
        ("get_recent_activity", "Team-wide activity grouped by type"),
    ]
    widths = [45, 145]
    pdf.table_row(tools[0], widths, header=True)
    for row in tools[1:]:
        pdf.table_row(row, widths)

    # ── 6. Knowledge Graph ──
    pdf.add_page()
    pdf.section_title("6", "Knowledge Graph")

    pdf.sub_title("Three-Layer Architecture")
    pdf.code_block(
        "CONCEPT LAYER (Topics)\n"
        "  [React]  [Kubernetes]  [Security]  ...\n"
        "    |          |            |\n"
        "    | KNOWS     | HAS_EXPERTISE  | COVERS\n"
        "    v          v            v\n"
        "SOCIAL LAYER (Members)\n"
        "  [Alice] --COLLABORATED-- [Bob]\n"
        "    |                        |\n"
        "    | CONTRIBUTED             | CONTRIBUTED\n"
        "    v                        v\n"
        "ARTIFACT LAYER (Documents/Code)\n"
        "  [API Docs]    [Auth Module]  ..."
    )

    pdf.sub_title("Temporal Decay Algorithm")
    pdf.body_text(
        "All edges use exponential temporal decay with a 180-day half-life to ensure recent "
        "work is weighted more heavily than older contributions:"
    )
    pdf.code_block("weight = exp(-0.693 * age_days / 180)")
    pdf.body_text("At 0 days: weight = 1.0, at 180 days: weight = 0.5, at 360 days: weight = 0.25")

    pdf.sub_title("Contribution Type Weights")
    weights = [
        ("Source Type", "Weight"),
        ("Git commits", "0.50"),
        ("Documents (PDF/DOCX)", "0.35"),
        ("Slack / Discord messages", "0.30"),
        ("Markdown files", "0.25"),
        ("Tasks / Issues", "0.15"),
    ]
    widths = [95, 95]
    pdf.table_row(weights[0], widths, header=True)
    for row in weights[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Pattern Detection Algorithms")
    pdf.bold_bullet("Bus Factor: ", "Topics with a single contributor are flagged as high risk (confidence: 0.8)")
    pdf.bold_bullet("Knowledge Silos: ", "Members with 3+ contributions but zero shared artifacts with others (confidence: 0.7)")
    pdf.bold_bullet("Strong Collaboration Pairs: ", "Members sharing 5+ artifacts are flagged as strong collaborators (confidence: 0.6)")
    pdf.bold_bullet("Stale Expertise: ", "Topics with no contributions in 90+ days, confidence scaled by temporal decay (0.5-0.9)")

    # ── 7. Insight Engine ──
    pdf.add_page()
    pdf.section_title("7", "Insight Engine")

    pdf.sub_title("Weekly Summary Generation")
    pdf.body_text(
        "The engine gathers the last 7 days of contributions, formats them into a structured "
        "prompt, and calls the LLM to generate a narrative summary. The output includes highlights "
        "(key achievements) and recommendations (action items), extracted via regex parsing. "
        "Summaries are cached as InsightRecords with period_start/period_end timestamps."
    )

    pdf.sub_title("Pattern Detection Pipeline")
    pdf.body_text("Pattern detection runs in two phases:")
    pdf.bold_bullet("Phase 1 - Graph Analysis (no LLM): ", "Bus factors, knowledge silos, strong collaboration pairs, and stale expertise are detected using pure graph algorithms against the MemoryGraph")
    pdf.bold_bullet("Phase 2 - LLM Analysis (optional): ", "For deeper insights, contribution data is formatted and sent to the LLM for narrative analysis. Results are stored as InsightRecords with confidence scores (0.5-0.9)")

    pdf.sub_title("Insight Types")
    insights_table = [
        ("Type", "Description", "Source"),
        ("pattern", "Collaboration and workflow patterns", "Graph"),
        ("risk", "Bus factors, stale expertise", "Graph"),
        ("recommendation", "Actionable suggestions", "LLM"),
        ("weekly_summary", "Periodic team narrative", "LLM"),
    ]
    widths = [40, 90, 60]
    pdf.table_row(insights_table[0], widths, header=True)
    for row in insights_table[1:]:
        pdf.table_row(row, widths)

    # ── 8. Room-Scoped Workspaces ──
    pdf.add_page()
    pdf.section_title("8", "Room-Scoped Workspaces")

    pdf.body_text(
        "Every room is a fully isolated workspace. All data - artifacts, contributions, "
        "conversations, insights, discussions, and vector chunks - is tagged with a room_id "
        "and filtered accordingly. This enables multi-tenant-like isolation without separate databases."
    )

    pdf.sub_title("Data Isolation Model")
    pdf.code_block(
        "Room A (Engineering)       Room B (Marketing)\n"
        "+-- Artifacts (code, docs)  +-- Artifacts (campaigns)\n"
        "+-- Contributions           +-- Contributions\n"
        "+-- Conversations (AI)      +-- Conversations (AI)\n"
        "+-- Graph & Analytics       +-- Graph & Analytics\n"
        "+-- Insights (patterns)     +-- Insights (patterns)\n"
        "+-- Discussions (threads)   +-- Discussions (threads)\n"
        "+-- Vector chunks (Chroma)  +-- Vector chunks (Chroma)"
    )

    pdf.sub_title("Room Features")
    pdf.bold_bullet("Public Rooms: ", "Visible in Discover tab, any user can join via self-service")
    pdf.bold_bullet("Private Rooms: ", "Invite-only, admin adds members by searching usernames")
    pdf.bold_bullet("Room Chat: ", "Real-time WebSocket messaging with user, AI, and system messages")
    pdf.bold_bullet("Room AI: ", "Questions are scoped to the room's ingested data via ChromaDB room_id filter")
    pdf.bold_bullet("Room Analytics: ", "Activity timeline, expertise matrix, topic trends - all room-scoped")

    pdf.sub_title("Technical Implementation")
    pdf.body_text(
        "All 13 backend routers accept an optional room_id parameter. When provided, database "
        "queries filter by room_id, ChromaDB searches use where:{room_id: 'xxx'} metadata "
        "filtering, and the MemoryGraph constructs room-specific subgraphs. The InsightEngine "
        "generates per-room patterns and weekly summaries."
    )

    # ── 9. Database Schema ──
    pdf.add_page()
    pdf.section_title("9", "Database Schema")

    pdf.body_text("The application uses 11 database tables across PostgreSQL (production) or SQLite (development):")
    pdf.ln(3)

    tables = [
        ("Table", "Purpose", "Key Fields"),
        ("users", "Auth accounts", "username, email, password_hash, google_id"),
        ("members", "Team directory", "name, aliases, expertise_tags, scores"),
        ("artifacts", "Ingested data", "source_type, title, chunk_count, room_id"),
        ("contributions", "Who did what", "member_id, artifact_id, topics, room_id"),
        ("conversations", "AI chat sessions", "owner_user_id, visibility, room_id"),
        ("messages", "Chat messages", "role, content, sources, related_members"),
        ("insights", "Generated patterns", "insight_type, confidence, room_id"),
        ("chat_rooms", "Collaborative spaces", "name, is_public, message_count"),
        ("chat_room_members", "Room membership", "user_id, role (admin/member)"),
        ("chat_room_messages", "Room chat", "message_type (user/ai/system)"),
        ("discussion_threads", "Forum threads", "context_type, context_id, room_id"),
    ]
    widths = [45, 50, 95]
    pdf.table_row(tables[0], widths, header=True)
    for row in tables[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Migration System")
    pdf.body_text(
        "The application uses a custom migration system (no Alembic). On startup, init_db() calls "
        "Base.metadata.create_all() to create missing tables, then _run_migrations() adds missing "
        "columns to existing tables via ALTER TABLE. This ensures schema evolution without data loss."
    )

    # ── 10. API Reference ──
    pdf.add_page()
    pdf.section_title("10", "API Reference")

    pdf.sub_title("Authentication (4 endpoints)")
    endpoints_auth = [
        ("Method", "Path", "Description"),
        ("POST", "/auth/register", "Create account with username/email/password"),
        ("POST", "/auth/login", "JWT token generation (30min expiry)"),
        ("POST", "/auth/google", "Google OAuth with auto account creation"),
        ("POST", "/auth/reset-password", "Password reset with 8-character code"),
    ]
    widths = [20, 55, 115]
    pdf.table_row(endpoints_auth[0], widths, header=True)
    for row in endpoints_auth[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Knowledge Ingestion (6 endpoints)")
    endpoints_ingest = [
        ("Method", "Path", "Description"),
        ("POST", "/ingest/markdown-upload", "Upload and parse markdown files"),
        ("POST", "/ingest/git", "Mine git repository commit history"),
        ("POST", "/ingest/slack", "Ingest Slack message exports"),
        ("POST", "/ingest/discord", "Ingest Discord message exports"),
        ("POST", "/ingest/documents", "Upload PDF/DOCX files"),
        ("POST", "/ingest/tasks", "Ingest task/issue tracking data"),
    ]
    pdf.table_row(endpoints_ingest[0], widths, header=True)
    for row in endpoints_ingest[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Query & Conversations (5 endpoints)")
    endpoints_query = [
        ("Method", "Path", "Description"),
        ("POST", "/query", "AI question-answering (RAG or LangGraph)"),
        ("GET", "/conversations", "List user's conversation history"),
        ("GET", "/conversations/{id}", "Full conversation with messages"),
        ("POST", "/conversations/{id}/share", "Share conversation with users"),
        ("DELETE", "/conversations/{id}", "Delete a conversation"),
    ]
    pdf.table_row(endpoints_query[0], widths, header=True)
    for row in endpoints_query[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Members & Expertise (5 endpoints)")
    endpoints_members = [
        ("Method", "Path", "Description"),
        ("GET", "/members", "List all team members with expertise"),
        ("GET", "/members/{id}", "Member profile with contributions"),
        ("POST", "/members", "Create a new member manually"),
        ("PUT", "/members/{id}", "Update expertise tags, strengths"),
        ("PUT", "/members/{id}/aliases", "Manage name aliases for matching"),
    ]
    pdf.table_row(endpoints_members[0], widths, header=True)
    for row in endpoints_members[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Knowledge Graph (4 endpoints)")
    endpoints_graph = [
        ("Method", "Path", "Description"),
        ("GET", "/graph/full", "Complete 3-layer graph visualization"),
        ("GET", "/graph/member/{id}", "1-hop member subgraph"),
        ("GET", "/graph/topic/{topic}", "2-hop topic subgraph"),
        ("GET", "/graph/expertise-matrix", "Member x Topic heatmap data"),
    ]
    pdf.table_row(endpoints_graph[0], widths, header=True)
    for row in endpoints_graph[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Insights & Analytics (10 endpoints)")
    endpoints_analytics = [
        ("Method", "Path", "Description"),
        ("GET", "/insights/dashboard", "Key stats and top insights"),
        ("GET", "/insights/weekly", "Cached weekly team summary"),
        ("GET", "/insights/patterns", "Detected patterns and risks"),
        ("POST", "/insights/generate", "Force pattern detection"),
        ("GET", "/analytics/activity-timeline", "Contribution counts over time"),
        ("GET", "/analytics/expertise-matrix", "Topic scores per member"),
        ("GET", "/analytics/source-breakdown", "Artifact counts by type"),
        ("GET", "/analytics/contribution-types", "Contribution type distribution"),
        ("GET", "/analytics/member-activity", "Per-member activity ranking"),
        ("GET", "/analytics/topic-trends", "Top topics over time period"),
    ]
    pdf.table_row(endpoints_analytics[0], widths, header=True)
    for row in endpoints_analytics[1:]:
        pdf.table_row(row, widths)
    pdf.ln(5)

    pdf.sub_title("Rooms & Discussions (10 endpoints)")
    endpoints_rooms = [
        ("Method", "Path", "Description"),
        ("GET", "/rooms", "List user's rooms"),
        ("POST", "/rooms", "Create new room (public/private)"),
        ("GET", "/rooms/discover", "Browse public rooms to join"),
        ("POST", "/rooms/{id}/join", "Self-service join for public rooms"),
        ("POST", "/rooms/{id}/messages", "Send message to room"),
        ("POST", "/rooms/{id}/ai", "Ask AI within room context"),
        ("WS", "/rooms/{id}/ws", "WebSocket for real-time chat"),
        ("POST", "/discussions", "Create discussion thread"),
        ("GET", "/discussions", "List threads with filters"),
        ("POST", "/discussions/{id}/msgs", "Add message to thread"),
    ]
    pdf.table_row(endpoints_rooms[0], widths, header=True)
    for row in endpoints_rooms[1:]:
        pdf.table_row(row, widths)

    # ── 11. Frontend Architecture ──
    pdf.add_page()
    pdf.section_title("11", "Frontend Architecture")

    pdf.sub_title("Technology Stack")
    pdf.bold_bullet("Framework: ", "React 19.2 with TypeScript 5.9")
    pdf.bold_bullet("Build Tool: ", "Vite 7.3 with @tailwindcss/vite plugin")
    pdf.bold_bullet("Styling: ", "Tailwind CSS 4.2 with dark mode support")
    pdf.bold_bullet("State Management: ", "@tanstack/react-query 5.90 for server state")
    pdf.bold_bullet("Routing: ", "React Router DOM 7.13 with protected routes")
    pdf.bold_bullet("Animations: ", "Framer Motion 12.34 for page transitions")
    pdf.bold_bullet("Icons: ", "Lucide React 0.575 (500+ icons)")
    pdf.bold_bullet("Graphs: ", "react-force-graph-2d 1.29 for knowledge graph visualization")
    pdf.bold_bullet("Charts: ", "Recharts 3.7 for analytics (line, bar, heatmap)")
    pdf.bold_bullet("Auth: ", "@react-oauth/google 0.13 for Google Sign-In")

    pdf.sub_title("Page Routes (13 pages)")
    routes = [
        ("Route", "Page", "Description"),
        ("/login", "LoginPage", "JWT login + Google Sign-In"),
        ("/register", "RegisterPage", "Account creation form"),
        ("/forgot-password", "ForgotPasswordPage", "Password recovery flow"),
        ("/", "DashboardPage", "Stats, top members, insights"),
        ("/chat", "ChatPage", "Conversational AI Q&A"),
        ("/ingest", "IngestPage", "Upload documents, git repos"),
        ("/members", "MembersPage", "Team explorer with cards"),
        ("/members/:id", "MemberDetailView", "Profile, expertise, contributions"),
        ("/graph", "GraphPage", "Interactive force-directed graph"),
        ("/analytics", "AnalyticsPage", "Timeline, heatmap, trends"),
        ("/rooms", "RoomsPage", "My Rooms + Discover tabs"),
        ("/rooms/:id", "RoomChatPage", "Real-time chat + AI queries"),
        ("/discussions", "DiscussionsPage", "Threaded forum"),
    ]
    widths = [38, 45, 107]
    pdf.table_row(routes[0], widths, header=True)
    for row in routes[1:]:
        pdf.table_row(row, widths)

    # ── 12. Deployment ──
    pdf.add_page()
    pdf.section_title("12", "Deployment & Infrastructure")

    pdf.sub_title("Docker Multi-Stage Build")
    pdf.code_block(
        "Stage 1: Frontend Build (Node 20-alpine)\n"
        "  npm ci -> npm run build (Vite)\n"
        "  Output: /app/dist/\n"
        "\n"
        "Stage 2: Backend + Static (Python 3.11-slim)\n"
        "  Install: build-essential, libpq, git\n"
        "  Install: PyTorch CPU-only (saves 1.5GB)\n"
        "  Install: requirements.txt\n"
        "  Copy frontend build -> /app/static/\n"
        "  CMD: uvicorn app.main:app --workers 2"
    )

    pdf.sub_title("Production Environment (HuggingFace Spaces)")
    pdf.bold_bullet("Container: ", "Python 3.11-slim with 2 Uvicorn workers on port 7860")
    pdf.bold_bullet("Database: ", "Neon PostgreSQL (free tier, 0.5GB, always-on cloud database)")
    pdf.bold_bullet("Vector Store: ", "ChromaDB persistent on /data volume")
    pdf.bold_bullet("Persistent Storage: ", "HF Spaces /data volume for ChromaDB data")

    pdf.sub_title("Key Environment Variables")
    envvars = [
        ("Variable", "Purpose"),
        ("CB_DATABASE_URL", "PostgreSQL connection string (Neon)"),
        ("CB_LLM_PROVIDER", "claude | ollama | mistral"),
        ("CB_MISTRAL_API_KEY", "HuggingFace Inference API key"),
        ("CB_CLAUDE_API_KEY", "Anthropic API key (if using Claude)"),
        ("CB_JWT_SECRET", "JWT signing secret (change from default!)"),
        ("CB_GOOGLE_CLIENT_ID", "Google OAuth client ID"),
        ("CB_AGENT_MODE", "rag (simple) | langgraph (autonomous)"),
        ("CB_CHROMA_PERSIST_DIR", "ChromaDB data directory path"),
        ("CB_REDIS_URL", "Optional Redis for pub/sub and caching"),
    ]
    widths = [55, 135]
    pdf.table_row(envvars[0], widths, header=True)
    for row in envvars[1:]:
        pdf.table_row(row, widths)

    # ── 13. Security & Resilience ──
    pdf.add_page()
    pdf.section_title("13", "Security & Resilience")

    pdf.sub_title("Authentication & Authorization")
    pdf.bold_bullet("Password Hashing: ", "bcrypt with 12 salt rounds via passlib")
    pdf.bold_bullet("JWT Tokens: ", "HS256 algorithm, 30-minute expiry, stored in localStorage")
    pdf.bold_bullet("Google OAuth: ", "ID token verification via google-auth library, auto account linking")
    pdf.bold_bullet("Password Reset: ", "8-character codes with 15-minute expiry")
    pdf.bold_bullet("Rate Limiting: ", "Auth endpoints: 5 register/min, 10 login/min per IP")

    pdf.sub_title("Circuit Breaker Pattern")
    pdf.body_text(
        "External service calls (LLM, embeddings) are protected by a circuit breaker that "
        "prevents cascading failures:"
    )
    pdf.bold_bullet("CLOSED (normal): ", "Requests flow through, failures are counted")
    pdf.bold_bullet("OPEN (after 3 failures): ", "Returns 503 with Retry-After header, no requests sent")
    pdf.bold_bullet("HALF-OPEN (after 30s): ", "Allows test requests, 2 successes close the circuit")

    pdf.sub_title("Rate Limiting")
    pdf.body_text(
        "Token bucket algorithm via Redis (or in-memory fallback). General endpoints: 60 requests/minute "
        "per user. AI query endpoints: 10 requests/minute per user. Returns 429 Too Many Requests "
        "when exceeded."
    )

    pdf.sub_title("Graceful Degradation")
    pdf.bold_bullet("Redis unavailable: ", "Falls back to in-memory dict for rate limiting and caching")
    pdf.bold_bullet("LLM unavailable: ", "Returns fallback response with available context data")
    pdf.bold_bullet("Database: ", "PostgreSQL with connection pooling (10+20 overflow) and pre-ping health checks")
    pdf.bold_bullet("ChromaDB race condition: ", "Retry logic (3 attempts, 1s delay) for multi-worker startup")

    pdf.sub_title("Data Protection")
    pdf.bold_bullet("Room isolation: ", "All queries filter by room_id, preventing cross-room data leakage")
    pdf.bold_bullet("Conversation privacy: ", "Visibility controls: private, shared, or team-wide")
    pdf.bold_bullet("CORS: ", "Configurable allowed origins, credentials enabled")
    pdf.bold_bullet("SQL injection: ", "SQLAlchemy ORM with parameterized queries throughout")

    # ── Save ──
    output_path = "/Users/rakeshchintanippu/collective-brain/Collective_Brain_Documentation.pdf"
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
