import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { AuthProvider, useAuth } from "../useAuth";
import type { ReactNode } from "react";

// vi.hoisted runs before vi.mock hoisting, so these are available in the factory
const mockApi = vi.hoisted(() => ({
  authLogin: vi.fn(),
  authRegister: vi.fn(),
  authGoogle: vi.fn(),
  authGoogleAccessToken: vi.fn(),
  authProfile: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  api: mockApi,
}));

// Helper wrapper
function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

const fakeUser = {
  id: "u1",
  username: "testuser",
  email: "test@example.com",
  display_name: "Test User",
  avatar_url: null,
  linked_member_id: null,
  is_active: true,
  created_at: "2025-01-01T00:00:00Z",
};

const fakeAuthResponse = {
  token: "tok_abc",
  refresh_token: "ref_xyz",
  user: fakeUser,
};

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("useAuth", () => {
  it("throws when used outside AuthProvider", () => {
    // Suppress console.error for the expected error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within AuthProvider");
    spy.mockRestore();
  });

  it("starts with no user and isLoading true, then finishes loading", async () => {
    // No token in localStorage, so loading should finish quickly
    const { result } = renderHook(() => useAuth(), { wrapper });

    // After the initial effect runs, isLoading becomes false
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.user).toBeNull();
  });

  it("loads user from token on mount when token exists", async () => {
    localStorage.setItem("cb_token", "existing_token");
    mockApi.authProfile.mockResolvedValueOnce(fakeUser);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.user).toEqual(fakeUser);
    expect(mockApi.authProfile).toHaveBeenCalled();
  });

  it("clears tokens when profile fetch fails on mount", async () => {
    localStorage.setItem("cb_token", "bad_token");
    localStorage.setItem("cb_refresh_token", "bad_refresh");
    mockApi.authProfile.mockRejectedValueOnce(new Error("401"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem("cb_token")).toBeNull();
    expect(localStorage.getItem("cb_refresh_token")).toBeNull();
  });

  it("login sets user and stores tokens", async () => {
    mockApi.authLogin.mockResolvedValueOnce(fakeAuthResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.login("testuser", "password123");
    });

    expect(result.current.user).toEqual(fakeUser);
    expect(localStorage.getItem("cb_token")).toBe("tok_abc");
    expect(localStorage.getItem("cb_refresh_token")).toBe("ref_xyz");
    expect(mockApi.authLogin).toHaveBeenCalledWith({
      username: "testuser",
      password: "password123",
    });
  });

  it("login propagates API errors", async () => {
    mockApi.authLogin.mockRejectedValueOnce(new Error("Invalid credentials"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await expect(
      act(async () => {
        await result.current.login("bad", "wrong");
      })
    ).rejects.toThrow("Invalid credentials");

    expect(result.current.user).toBeNull();
    expect(localStorage.getItem("cb_token")).toBeNull();
  });

  it("logout clears user and tokens", async () => {
    mockApi.authLogin.mockResolvedValueOnce(fakeAuthResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Login first
    await act(async () => {
      await result.current.login("testuser", "password123");
    });
    expect(result.current.user).toEqual(fakeUser);

    // Then logout
    act(() => {
      result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(localStorage.getItem("cb_token")).toBeNull();
    expect(localStorage.getItem("cb_refresh_token")).toBeNull();
  });

  it("googleLogin calls API and stores tokens", async () => {
    mockApi.authGoogle.mockResolvedValueOnce(fakeAuthResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.googleLogin("google_credential_abc");
    });

    expect(result.current.user).toEqual(fakeUser);
    expect(localStorage.getItem("cb_token")).toBe("tok_abc");
    expect(mockApi.authGoogle).toHaveBeenCalledWith("google_credential_abc");
  });

  it("register calls API and stores tokens", async () => {
    mockApi.authRegister.mockResolvedValueOnce(fakeAuthResponse);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.register("newuser", "new@example.com", "pass123", "New User");
    });

    expect(result.current.user).toEqual(fakeUser);
    expect(localStorage.getItem("cb_token")).toBe("tok_abc");
    expect(mockApi.authRegister).toHaveBeenCalledWith({
      username: "newuser",
      email: "new@example.com",
      password: "pass123",
      display_name: "New User",
    });
  });
});
