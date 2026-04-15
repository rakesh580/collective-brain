import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../client";

// Store original location
const originalLocation = window.location;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();

  // Mock window.location
  Object.defineProperty(window, "location", {
    writable: true,
    value: { ...originalLocation, href: "/", pathname: "/" },
  });
});

afterEach(() => {
  Object.defineProperty(window, "location", {
    writable: true,
    value: originalLocation,
  });
  vi.restoreAllMocks();
});

function mockFetch(response: Partial<Response>) {
  const fn = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    text: () => Promise.resolve(""),
    ...response,
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("API client request function", () => {
  it("adds Authorization header when token exists in localStorage", async () => {
    localStorage.setItem("cb_token", "my_token");
    const fetchFn = mockFetch({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: "ok" }),
    });

    await api.health();

    expect(fetchFn).toHaveBeenCalledTimes(1);
    const [, options] = fetchFn.mock.calls[0];
    expect(options.headers["Authorization"]).toBe("Bearer my_token");
  });

  it("does not add Authorization header when no token exists", async () => {
    const fetchFn = mockFetch({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: "ok" }),
    });

    await api.health();

    expect(fetchFn).toHaveBeenCalledTimes(1);
    const [, options] = fetchFn.mock.calls[0];
    expect(options.headers["Authorization"]).toBeUndefined();
  });

  it("attempts token refresh on 401 response", async () => {
    localStorage.setItem("cb_token", "expired_token");
    localStorage.setItem("cb_refresh_token", "valid_refresh");

    const fetchFn = vi.fn();
    // First call: 401 on /health
    fetchFn.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve("Unauthorized"),
    });
    // Second call: refresh endpoint succeeds
    fetchFn.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          token: "new_token",
          refresh_token: "new_refresh",
        }),
    });
    // Third call: retry of original /health with new token
    fetchFn.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ status: "healthy" }),
    });
    vi.stubGlobal("fetch", fetchFn);

    const result = await api.health();

    expect(result).toEqual({ status: "healthy" });
    expect(fetchFn).toHaveBeenCalledTimes(3);
    // The refresh call
    expect(fetchFn.mock.calls[1][0]).toContain("/auth/refresh");
    // The retry call should use the new token
    const retryHeaders = fetchFn.mock.calls[2][1].headers;
    expect(retryHeaders["Authorization"]).toBe("Bearer new_token");
    // Tokens should be updated in localStorage
    expect(localStorage.getItem("cb_token")).toBe("new_token");
    expect(localStorage.getItem("cb_refresh_token")).toBe("new_refresh");
  });

  it("redirects to /login when refresh fails", async () => {
    localStorage.setItem("cb_token", "expired_token");
    localStorage.setItem("cb_refresh_token", "bad_refresh");

    const fetchFn = vi.fn();
    // First call: 401 on /health
    fetchFn.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve("Unauthorized"),
    });
    // Second call: refresh endpoint fails
    fetchFn.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({}),
      text: () => Promise.resolve("Invalid refresh token"),
    });
    vi.stubGlobal("fetch", fetchFn);

    await expect(api.health()).rejects.toThrow("Session expired");

    // Auth tokens should be cleared
    expect(localStorage.getItem("cb_token")).toBeNull();
    expect(localStorage.getItem("cb_refresh_token")).toBeNull();
    // Should redirect to login
    expect(window.location.href).toBe("/login");
  });

  it("throws on non-401 error responses", async () => {
    mockFetch({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Internal Server Error"),
    });

    await expect(api.health()).rejects.toThrow("API error 500: Internal Server Error");
  });

  it("sends correct method and body for POST requests", async () => {
    localStorage.setItem("cb_token", "tok");
    const fetchFn = mockFetch({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({ token: "t", refresh_token: "r", user: {} }),
    });

    await api.authLogin({ username: "user", password: "pass" });

    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/auth/login");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({
      username: "user",
      password: "pass",
    });
  });
});
