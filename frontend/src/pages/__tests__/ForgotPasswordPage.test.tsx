import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

const mockApi = vi.hoisted(() => ({
  authForgotPassword: vi.fn(),
  authResetPassword: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

vi.mock("../../components/layout/Logo", () => ({
  LogoIcon: ({ size: _size }: any) => <div data-testid="logo-icon" />,
}));

import ForgotPasswordPage from "../ForgotPasswordPage";

function renderPage() {
  return render(
    <BrowserRouter>
      <ForgotPasswordPage />
    </BrowserRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.authForgotPassword.mockResolvedValue({ code: "123456" });
  mockApi.authResetPassword.mockResolvedValue({
    token: "test-token",
    refresh_token: "test-refresh",
  });
});

describe("ForgotPasswordPage", () => {
  it("renders the Reset Password heading", () => {
    renderPage();
    expect(screen.getByText("Reset Password")).toBeInTheDocument();
  });

  it("renders the email step initially", () => {
    renderPage();
    expect(screen.getByText("Enter your email to receive a verification code")).toBeInTheDocument();
    expect(screen.getByText("Email Address")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getByText("Send Verification Code")).toBeInTheDocument();
  });

  it("renders email input field", () => {
    renderPage();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
  });

  it("renders back to sign in link", () => {
    renderPage();
    expect(screen.getByText("Back to Sign In")).toBeInTheDocument();
  });

  it("calls authForgotPassword on email submit", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.click(screen.getByText("Send Verification Code"));
    await waitFor(() => {
      expect(mockApi.authForgotPassword).toHaveBeenCalledWith("test@example.com");
    });
  });

  it("advances to code step after email submission", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.click(screen.getByText("Send Verification Code"));
    await waitFor(() => {
      expect(screen.getByText("Enter the code and your new password")).toBeInTheDocument();
    });
    expect(screen.getByText("Verification Code")).toBeInTheDocument();
    expect(screen.getByText("New Password")).toBeInTheDocument();
    expect(screen.getByText("Confirm New Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reset Password/i })).toBeInTheDocument();
  });

  it("shows dev code in demo mode", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.click(screen.getByText("Send Verification Code"));
    await waitFor(() => {
      expect(screen.getByText("123456")).toBeInTheDocument();
    });
  });

  it("shows error when passwords do not match", async () => {
    const user = userEvent.setup();
    renderPage();
    // Step 1: email
    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.click(screen.getByText("Send Verification Code"));
    // Step 2: code
    await waitFor(() => {
      expect(screen.getByPlaceholderText("000000")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("000000"), "123456");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "password123");
    await user.type(screen.getByPlaceholderText("********"), "differentpassword");
    // Submit the code form via the submit button
    const submitBtn = screen.getByRole("button", { name: /Reset Password/i });
    await user.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });
  });

  it("shows error when email submission fails", async () => {
    mockApi.authForgotPassword.mockRejectedValue(new Error("User not found"));
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByPlaceholderText("you@example.com"), "bad@example.com");
    await user.click(screen.getByText("Send Verification Code"));
    await waitFor(() => {
      expect(screen.getByText("User not found")).toBeInTheDocument();
    });
  });

  it("shows success step after password reset", async () => {
    const user = userEvent.setup();
    renderPage();
    // Step 1
    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.click(screen.getByText("Send Verification Code"));
    // Step 2
    await waitFor(() => {
      expect(screen.getByPlaceholderText("000000")).toBeInTheDocument();
    });
    await user.type(screen.getByPlaceholderText("000000"), "123456");
    await user.type(screen.getByPlaceholderText("Min 8 characters"), "newpassword123");
    await user.type(screen.getByPlaceholderText("********"), "newpassword123");
    const submitBtn = screen.getByRole("button", { name: /Reset Password/i });
    await user.click(submitBtn);
    await waitFor(() => {
      // "Password reset successful!" appears in both subtitle and success message
      expect(screen.getAllByText("Password reset successful!").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("Redirecting you to the dashboard...")).toBeInTheDocument();
  });
});
