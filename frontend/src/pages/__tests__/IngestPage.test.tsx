import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  ingestGit: vi.fn(),
  ingestMarkdownFiles: vi.fn(),
  ingestDocuments: vi.fn(),
  ingestFile: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => {
      const { variants: _v, initial: _i, animate: _a, exit: _e, whileHover: _wh, transition: _t, ...rest } = props;
      return <div {...rest}>{children}</div>;
    },
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import IngestPage from "../IngestPage";

const mockIngestionJob = {
  artifact_id: "a1",
  source_type: "git",
  status: "completed",
  chunk_count: 42,
  member_count: 3,
};

function renderPage() {
  return render(<IngestPage />);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.ingestGit.mockResolvedValue(mockIngestionJob);
  mockApi.ingestMarkdownFiles.mockResolvedValue({
    ...mockIngestionJob,
    source_type: "markdown",
  });
  mockApi.ingestDocuments.mockResolvedValue({
    ...mockIngestionJob,
    source_type: "documents",
  });
});

describe("IngestPage", () => {
  it("renders the page heading", () => {
    renderPage();
    expect(screen.getByText("Ingest Data")).toBeInTheDocument();
    expect(screen.getByText("Feed your team's artifacts into the Collective Brain")).toBeInTheDocument();
  });

  it("renders source type selector buttons", () => {
    renderPage();
    expect(screen.getByText("Git Repository")).toBeInTheDocument();
    expect(screen.getByText("Markdown / Docs")).toBeInTheDocument();
    expect(screen.getByText("PDF / Word / Text")).toBeInTheDocument();
    expect(screen.getByText("Slack Export")).toBeInTheDocument();
    expect(screen.getByText("Discord Export")).toBeInTheDocument();
  });

  it("defaults to markdown source type with file upload", () => {
    renderPage();
    // Markdown is the default, should show its description
    expect(screen.getByText("Upload .md, .txt, or .zip files from your computer")).toBeInTheDocument();
    // Should show file input
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).toBeInTheDocument();
  });

  it("switches to git repo input when Git Repository is selected", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Git Repository"));

    expect(
      screen.getByPlaceholderText("https://github.com/user/repo or /path/to/repo"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Enter a GitHub URL or local path to a Git repository"),
    ).toBeInTheDocument();
  });

  it("calls ingestGit when git form is submitted", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Git Repository"));

    const input = screen.getByPlaceholderText("https://github.com/user/repo or /path/to/repo");
    await user.type(input, "https://github.com/test/repo");
    await user.click(screen.getByText("Ingest"));

    await waitFor(() => {
      expect(mockApi.ingestGit).toHaveBeenCalledWith(
        "https://github.com/test/repo",
        "main",
        90,
        undefined,
      );
    });
  });

  it("shows completed ingestion job in recent ingestions", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Git Repository"));

    const input = screen.getByPlaceholderText("https://github.com/user/repo or /path/to/repo");
    await user.type(input, "https://github.com/test/repo");
    await user.click(screen.getByText("Ingest"));

    await waitFor(() => {
      expect(screen.getByText("Recent Ingestions")).toBeInTheDocument();
    });
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText(/42 chunks/)).toBeInTheDocument();
  });

  it("shows error when ingestion fails", async () => {
    mockApi.ingestGit.mockRejectedValue(new Error("Repository not found"));
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Git Repository"));

    const input = screen.getByPlaceholderText("https://github.com/user/repo or /path/to/repo");
    await user.type(input, "https://github.com/bad/repo");
    await user.click(screen.getByText("Ingest"));

    await waitFor(() => {
      expect(screen.getByText("Repository not found")).toBeInTheDocument();
    });
  });

  it("disables ingest button when no input is provided", () => {
    renderPage();
    const ingestBtn = screen.getByText("Ingest");
    expect(ingestBtn).toBeDisabled();
  });

  it("switches to PDF/Word source and shows file input", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("PDF / Word / Text"));

    expect(
      screen.getByText("Upload PDF, Word (.docx), or text files — text is auto-extracted"),
    ).toBeInTheDocument();
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).toBeInTheDocument();
  });

  it("shows 'Ingesting...' text while loading", async () => {
    mockApi.ingestGit.mockReturnValue(new Promise(() => {})); // never resolves
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByText("Git Repository"));

    const input = screen.getByPlaceholderText("https://github.com/user/repo or /path/to/repo");
    await user.type(input, "https://github.com/test/repo");
    await user.click(screen.getByText("Ingest"));

    await waitFor(() => {
      expect(screen.getByText("Ingesting...")).toBeInTheDocument();
    });
  });

  it("renders Notion and Confluence source options", () => {
    renderPage();
    expect(screen.getByText("Notion")).toBeInTheDocument();
    expect(screen.getByText("Confluence")).toBeInTheDocument();
  });
});
