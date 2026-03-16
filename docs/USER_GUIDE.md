# Collective Brain - User Guide

Welcome to Collective Brain! This guide will walk you through everything you need to know to get the most out of the platform. Collective Brain helps your team capture, organize, and discover knowledge using AI.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Dashboard](#dashboard)
- [AI Chat](#ai-chat)
- [Data Ingestion](#data-ingestion)
- [Team Members](#team-members)
- [Chat Rooms](#chat-rooms)
- [Knowledge Graph](#knowledge-graph)
- [Discussions](#discussions)
- [Analytics](#analytics)
- [Search](#search)
- [Settings](#settings)
- [Integrations](#integrations)

---

## Getting Started

### Creating Your Account

1. Open Collective Brain in your web browser.
2. Click **Sign Up** on the login page.
3. Fill in your name, email address, and choose a password.
4. Click **Create Account** to complete registration.
5. You will be logged in automatically and taken to the Dashboard.

### Signing In with Google

If your organization has enabled Google OAuth:

1. Click the **Sign in with Google** button on the login page.
2. Select your Google account or enter your Google credentials.
3. Grant Collective Brain permission to access your basic profile information.
4. You will be redirected to the Dashboard.

### Logging In

If you already have an account:

1. Enter your email and password on the login page.
2. Click **Sign In**.
3. You will be taken to the Dashboard.

---

## Dashboard

The Dashboard is your home base. It gives you a high-level overview of your team's collective knowledge.

### What You Will See

- **Team Knowledge Summary:** A quick snapshot of how much knowledge has been captured, including total documents, topics, and team members.
- **Top Members:** The most active contributors ranked by their contributions to the knowledge base.
- **Recent Insights:** The latest discoveries and connections the AI has found across your team's data.
- **Freshness Alerts:** Notifications about knowledge that may be outdated and could benefit from a review or update. This helps ensure your team's information stays current.

### Tips

- Check the Dashboard regularly to stay informed about your team's knowledge health.
- Click on any insight or alert to dive deeper into the details.

---

## AI Chat

AI Chat is your conversational interface for exploring team knowledge. Ask questions in plain language and get answers drawn from your team's collective data.

### Starting a Conversation

1. Click **AI Chat** in the navigation menu.
2. Type your question in the message box at the bottom of the screen.
3. Press **Enter** or click the send button.
4. The AI will search your team's knowledge base and respond with a relevant answer.

### Example Questions

- "What does our team know about microservices architecture?"
- "Who has experience with Kubernetes deployments?"
- "Summarize the key decisions from last quarter's planning discussions."

### Conversation History

Your past conversations are saved automatically. You can:

- Browse previous conversations in the sidebar.
- Continue any past conversation by selecting it.
- Start a new conversation by clicking **New Chat**.

### Source Attribution

Every AI response includes source references so you can verify where the information came from. Click on any source link to view the original document or data.

### Sharing Conversations

To share a conversation with a teammate:

1. Open the conversation you want to share.
2. Click the **Share** button at the top of the conversation.
3. Copy the generated link and send it to your colleague.
4. They will be able to view the conversation (they must be logged in).

---

## Data Ingestion

Collective Brain becomes more valuable as you feed it more data. Here are the ways to bring your team's knowledge into the system.

### Ingesting Git Repositories

Bring in code knowledge and documentation from your repositories:

1. Go to **Data Ingestion** from the navigation menu.
2. Select **Git Repository** as the source type.
3. Enter the repository URL (HTTPS or SSH).
4. Optionally specify a branch (defaults to main/master).
5. Click **Start Ingestion**.
6. The system will clone the repository and extract knowledge from code, README files, documentation, and comments.

### Uploading Documents

Upload files directly from your computer:

1. Go to **Data Ingestion**.
2. Click **Upload Documents** or drag and drop files onto the upload area.
3. Supported formats include PDF, Word documents (.docx), text files (.txt), and more.
4. The AI will process each document and extract key topics, entities, and relationships.

### Markdown Files

Markdown files are treated as first-class content:

1. Upload `.md` files through the document upload interface.
2. The system preserves headings, code blocks, and formatting.
3. Markdown content is fully searchable and referenced by the AI.

### Slack and Discord Exports

Import conversations from your team's communication channels:

1. Export your Slack or Discord data using their respective export tools.
2. Go to **Data Ingestion** and select **Slack Export** or **Discord Export**.
3. Upload the exported archive file (usually a `.zip` file).
4. The system will parse conversations, identify participants, and extract knowledge from discussions.

### Checking Ingestion Status

After starting an ingestion job, you can monitor its progress on the Data Ingestion page. Each job shows its current status (processing, completed, or failed) along with the number of items processed.

---

## Team Members

The Team Members section lets you see who is on the team and what they know.

### Browsing Members

1. Click **Team Members** in the navigation menu.
2. You will see a list of all team members with their profile information.
3. Use the search bar to find specific people by name or expertise.

### Viewing a Member's Profile

Click on any team member to see their detailed profile:

- **Expertise Areas:** Topics and technologies they are knowledgeable about, automatically detected from their contributions.
- **Contributions:** A summary of what they have contributed to the knowledge base (documents, code, discussions).
- **Activity:** A timeline of their recent activity.

### Auto-Discovered vs. Manual Members

Collective Brain identifies team members in two ways:

- **Auto-Discovered:** Members detected automatically from ingested data (e.g., git commit authors, Slack participants). These profiles are created and updated as new data is ingested.
- **Manual:** Members who registered directly on the platform. They can enrich their profiles with additional information.

---

## Chat Rooms

Chat Rooms provide real-time communication spaces for your team, enhanced with AI capabilities.

### Creating a Room

1. Go to **Chat Rooms** in the navigation menu.
2. Click **Create Room**.
3. Enter a room name and optional description.
4. Click **Create**.

### Inviting Members

1. Open the chat room.
2. Click the **Members** or **Settings** icon.
3. Search for team members and click **Invite** next to their name.
4. Invited members will see the room in their Chat Rooms list.

### Real-Time Messaging

- Type your message in the input box and press **Enter** to send.
- Messages appear instantly for all room members.
- You can see who is currently online in the room.

### AI Assistant in Rooms

Each chat room has access to the AI assistant:

- Mention the AI by typing `@ai` followed by your question.
- The AI can answer questions using knowledge from the entire platform or just from data scoped to that room.
- This is helpful for getting quick answers during team discussions without leaving the conversation.

### Room-Scoped Data

Chat rooms can have their own data sources. When you ingest data and associate it with a specific room, the AI assistant in that room will prioritize that data when answering questions. This is useful for project-specific or team-specific knowledge bases.

---

## Knowledge Graph

The Knowledge Graph visualizes the connections between people, topics, and knowledge in your organization.

### Accessing the Graph

1. Click **Knowledge Graph** in the navigation menu.
2. The graph will load with an interactive visualization.

### Visualization Modes

Switch between different views using the controls at the top of the graph:

- **Force Graph:** An interactive node-and-link diagram. Drag nodes to rearrange them, zoom in and out, and click on any node to see its details. Connections between nodes represent relationships (e.g., a person is an expert in a topic).

- **Mind Map:** A hierarchical tree layout that starts from a central concept and branches outward. This view is useful for exploring how topics relate to each other in a structured way.

- **Heatmap:** A grid-based view that shows the intensity of connections. Darker cells indicate stronger relationships. This is great for spotting patterns at a glance.

### Views

- **Member View:** Centers the graph around people, showing what topics each person is connected to.
- **Topic View:** Centers the graph around topics, showing which people and documents relate to each topic.
- **Expertise Matrix:** A table-style view mapping team members to skill areas, with indicators showing depth of expertise.

### Interacting with the Graph

- **Click** on a node to see detailed information in a side panel.
- **Hover** over a node to highlight its connections.
- **Scroll** to zoom in and out.
- **Drag** nodes to rearrange the layout (Force Graph mode).
- Use the **filter controls** to focus on specific topics or people.

---

## Discussions

Discussions are threaded conversations for deeper, more structured dialogue about specific topics.

### Creating a Discussion

1. Go to **Discussions** in the navigation menu.
2. Click **New Discussion**.
3. Enter a title and your opening message.
4. Optionally add tags to categorize the discussion.
5. Click **Create**.

### Participating

- Open any discussion to read the thread.
- Type your reply in the response box at the bottom and click **Post**.
- Replies appear in chronological order within the thread.
- You can reference other team knowledge by pasting links or mentioning topics.

### Real-Time Updates

Discussions update in real time. When someone posts a new reply, it appears immediately without needing to refresh the page. You will also see indicators when someone is typing.

---

## Analytics

Analytics give you insight into how your team's knowledge base is growing and being used.

### Accessing Analytics

1. Click **Analytics** in the navigation menu.
2. You will see a dashboard with charts and metrics.

### Available Metrics

- **Activity Timeline:** A chart showing ingestion and interaction activity over time. Spot trends in how actively your team is contributing knowledge.

- **Source Breakdown:** A pie or bar chart showing where your knowledge comes from (git repos, documents, Slack, etc.). This helps you understand your knowledge mix.

- **Topic Trends:** See which topics are gaining or losing attention over time. Identify emerging areas of interest or topics that may need refreshing.

- **Team Health Metrics:** Aggregate indicators of your knowledge base's overall health, including coverage (how many topics are well-documented), freshness (how recently data was updated), and engagement (how often the AI chat and search are used).

---

## Search

Search lets you find anything across your entire knowledge base quickly.

### Basic Search

1. Click the **Search** icon or press the keyboard shortcut to open search.
2. Type your search terms.
3. Results appear grouped by type (documents, people, topics, discussions).
4. Click any result to navigate to it.

### Cross-Entity Search

Search works across all entity types. A single query can return:

- Documents containing matching text.
- Team members with matching expertise.
- Topics related to your query.
- Discussion threads about the subject.

### Semantic Search

Toggle **Semantic Search** to find results based on meaning rather than exact keywords:

- Semantic search understands synonyms and related concepts.
- For example, searching "deployment pipeline" will also find content about "CI/CD" and "continuous delivery."
- This is powered by AI embeddings and works best for exploratory queries.

---

## Settings

### Profile

1. Click your avatar or name in the top-right corner.
2. Select **Settings** or **Profile**.
3. Update your name, bio, or profile picture.
4. Click **Save** to apply changes.

### Changing Your Password

1. Go to **Settings**.
2. Click **Change Password**.
3. Enter your current password.
4. Enter and confirm your new password.
5. Click **Update Password**.

### Theme Toggle

Switch between light and dark mode:

1. Go to **Settings**.
2. Find the **Theme** option.
3. Toggle between **Light** and **Dark** mode.
4. The change takes effect immediately.

---

## Integrations

### Slack Integration

Connect Collective Brain to your Slack workspace for automatic knowledge capture:

1. Go to **Settings > Integrations**.
2. Click **Connect Slack**.
3. You will be redirected to Slack to authorize the connection.
4. Select the workspace and channels you want to connect.
5. Click **Allow**.
6. Once connected, messages from the selected channels will be ingested into Collective Brain automatically.

You can manage connected channels at any time from the Integrations settings page.

### GitHub Webhooks

Set up GitHub webhooks to automatically ingest new code and documentation:

1. Go to **Settings > Integrations**.
2. Click **Set Up GitHub Webhook**.
3. Copy the generated webhook URL.
4. In your GitHub repository, go to **Settings > Webhooks > Add webhook**.
5. Paste the webhook URL into the **Payload URL** field.
6. Set the content type to **application/json**.
7. Select the events you want to trigger ingestion (recommended: **Push events** and **Pull request events**).
8. Click **Add webhook**.

Once configured, new commits and pull requests will be automatically ingested into your knowledge base.

---

## Need Help?

If you run into any issues or have questions not covered in this guide, reach out to your team administrator or check the project's GitHub repository for the latest documentation and issue tracker.
