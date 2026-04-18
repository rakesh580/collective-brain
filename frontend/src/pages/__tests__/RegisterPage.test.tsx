import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockRegister = vi.fn();
const mockGoogleLoginWithToken = vi.fn();
const mockNavigate = vi.fn();

vi.mock("../../hooks/useAuth", () => ({
  useAuth: () => ({
    register: mockRegister,
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

vi.mock("../../components/auth/GoogleAuthButton", () => ({
  default: ({ onError, onAccessTokenSuccess }: any) => (
    <>
      <button
        type="button"
        data-testid="google-btn"
        onClick={() => onAccessTokenSuccess("mock-token")}
      >
        Continue with Google
      </button>
      <button type="button" data-testid="google-error-btn" onClick={onError}>
        Trigger Google Error
      </button>
    </>
  ),
}));

// Mock Logo
vi.mock("../../components/layout/Logo", () => ({
  LogoIcon: () => <div data-testid="logo-icon" />,
}));

import RegisterPage from "../RegisterPage";

function renderPage() {
  return render(
    <BrowserRouter>
      <RegisterPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockRegister.mockResolvedValue(undefined);
  mockGoogleLoginWithToken.mockResolvedValue(undefined);
});

describe("RegisterPage", () => {
  it("renders the page title and subtitle", () => {
    renderPage();
    expect(screen.getByText("Collective Brain")).toBeInTheDocument();
    expect(screen.getByText("Create your account")).toBeInTheDocument();
  });

  it("renders all form fields", () => {
    renderPage();
    expect(screen.getByPlaceholderText("your-username")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("John Doe")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Min 8 characters")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("********")).toBeInTheDocument();
  });

  it("renders the submit button", () => {
    renderPage();
    expect(screen.getByText("Create Account")).toBeInTheDocument();
  });

  it("shows password mismatch error", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "newuser");
    await user.type(screen.getByPlaceholderText("you@example.com"), "new@test.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.type(screen.getByPlaceholderText("********"), "different123");
    await user.click(screen.getByText("Create Account"));

    await waitFor(() => {
      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("shows password too short error", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "newuser");
    await user.type(screen.getByPlaceholderText("you@example.com"), "new@test.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "short");
    await user.type(screen.getByPlaceholderText("********"), "short");
    await user.click(screen.getByText("Create Account"));

    await waitFor(() => {
      expect(screen.getByText("Password must be at least 8 characters")).toBeInTheDocument();
    });
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("calls register and navigates on successful submit", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "newuser");
    await user.type(screen.getByPlaceholderText("you@example.com"), "new@test.com");
    await user.type(screen.getByPlaceholderText("John Doe"), "New User");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.type(screen.getByPlaceholderText("********"), "password123");
    await user.click(screen.getByText("Create Account"));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith("newuser", "new@test.com", "password123", "New User");
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows API error on duplicate user registration", async () => {
    mockRegister.mockRejectedValue(new Error('API error 409: {"detail":"Username already taken"}'));
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "existing");
    await user.type(screen.getByPlaceholderText("you@example.com"), "x@test.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.type(screen.getByPlaceholderText("********"), "password123");
    await user.click(screen.getByText("Create Account"));

    await waitFor(() => {
      expect(screen.getByText("Username already taken")).toBeInTheDocument();
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("renders Google sign-in button", () => {
    renderPage();
    expect(screen.getByTestId("google-btn")).toBeInTheDocument();
  });

  it("calls googleLoginWithToken on Google auth success", async () => {
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

  it("shows error on Google login failure", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByTestId("google-error-btn"));

    await waitFor(() => {
      expect(
        screen.getByText(/Google sign-in failed/i),
      ).toBeInTheDocument();
    });
  });

  it("has a link to login page", () => {
    renderPage();
    const signInLink = screen.getByText("Sign in");
    expect(signInLink).toBeInTheDocument();
    expect(signInLink.closest("a")).toHaveAttribute("href", "/login");
  });

  it("shows loading state during registration", async () => {
    mockRegister.mockReturnValue(new Promise(() => {})); // never resolves
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText("your-username"), "newuser");
    await user.type(screen.getByPlaceholderText("you@example.com"), "x@test.com");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.type(screen.getByPlaceholderText("********"), "password123");
    await user.click(screen.getByText("Create Account"));

    await waitFor(() => {
      expect(screen.getByText("Creating account...")).toBeInTheDocument();
    });
  });
});
