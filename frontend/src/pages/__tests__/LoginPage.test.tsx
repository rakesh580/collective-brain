import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockLogin = vi.fn();
const mockGoogleLoginWithToken = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    login: mockLogin,
    googleLoginWithToken: mockGoogleLoginWithToken,
    user: null,
    isLoading: false,
    logout: vi.fn(),
  }),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock sub-components that have external deps (Google OAuth, canvas, etc.)
vi.mock("../../components/auth/NeuralBackground", () => ({
  default: () => <div data-testid="neural-bg" />,
}));
vi.mock("../../components/auth/TypingText", () => ({
  default: () => <span data-testid="typing-text">AI-powered team intelligence</span>,
}));
vi.mock("../../components/auth/FeatureOrb", () => ({
  default: ({ label }: any) => <div data-testid="feature-orb">{label}</div>,
}));
vi.mock("../../components/auth/LoginForm", () => ({
  default: ({ error, isLoading, onSubmit, onGoogleError, onGoogleAccessToken }: any) => (
    <form
      data-testid="login-form"
      onSubmit={(e: any) => {
        e.preventDefault();
        const formData = new FormData(e.target);
        onSubmit(formData.get("username"), formData.get("password"));
      }}
    >
      {error && <div data-testid="error-message">{error}</div>}
      <input name="username" placeholder="your-username" />
      <input name="password" type="password" placeholder="********" />
      <button type="submit" disabled={isLoading}>
        {isLoading ? "Signing in..." : "Sign In"}
      </button>
      <button type="button" data-testid="google-btn" onClick={() => onGoogleAccessToken("mock-token")}>
        Google
      </button>
      <button type="button" data-testid="google-error-btn" onClick={onGoogleError}>
        Trigger Google Error
      </button>
      <a href="/register">Sign up</a>
    </form>
  ),
}));

import LoginPage from "../LoginPage";

function renderPage() {
  return render(
    <BrowserRouter>
      <LoginPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockLogin.mockResolvedValue(undefined);
  mockGoogleLoginWithToken.mockResolvedValue(undefined);
});

describe("LoginPage", () => {
  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Collective")).toBeInTheDocument();
    expect(screen.getByText("Brain")).toBeInTheDocument();
  });

  it("renders the login form", () => {
    renderPage();
    expect(screen.getByTestId("login-form")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("your-username")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("********")).toBeInTheDocument();
  });

  it("renders the sign in button", () => {
    renderPage();
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  it("calls login on form submit and navigates on success", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "alice");
    await user.type(screen.getByPlaceholderText("********"), "password123");
    await user.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("alice", "password123");
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows error message on failed login", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid credentials"));
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "alice");
    await user.type(screen.getByPlaceholderText("********"), "wrong");
    await user.click(screen.getByText("Sign In"));

    await waitFor(() => {
      expect(screen.getByTestId("error-message")).toBeInTheDocument();
    });
    expect(screen.getByText("Invalid credentials")).toBeInTheDocument();
  });

  it("calls googleLoginWithToken when Google auth succeeds", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByTestId("google-btn"));

    await waitFor(() => {
      expect(mockGoogleLoginWithToken).toHaveBeenCalledWith("mock-token");
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("renders feature orbs", () => {
    renderPage();
    const orbs = screen.getAllByTestId("feature-orb");
    expect(orbs.length).toBeGreaterThanOrEqual(4);
  });

  it("renders stats ribbon", () => {
    renderPage();
    expect(screen.getByText("Knowledge Nodes")).toBeInTheDocument();
    expect(screen.getByText("10K+")).toBeInTheDocument();
    expect(screen.getByText("Teams Active")).toBeInTheDocument();
  });

  it("has a link to register page", () => {
    renderPage();
    const signUpLink = screen.getByText("Sign up");
    expect(signUpLink).toBeInTheDocument();
    expect(signUpLink.getAttribute("href")).toBe("/register");
  });

  it("shows error on Google login failure", async () => {
    mockGoogleLoginWithToken.mockRejectedValue(new Error("Google auth failed"));
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByTestId("google-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("error-message")).toBeInTheDocument();
    });
  });
});
