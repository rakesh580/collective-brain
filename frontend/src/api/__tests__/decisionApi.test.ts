import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../client";

const originalLocation = window.location;

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  localStorage.setItem("cb_token", "test_token");

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

describe("Decision Intelligence API methods", () => {
  // ── Decision endpoints ──

  it("getDecisions sends correct request", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ decisions: [], total: 0 }),
    });
    await api.getDecisions();
    expect(fetchFn).toHaveBeenCalledTimes(1);
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/decisions?");
  });

  it("getDecisions passes filter params", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ decisions: [], total: 0 }),
    });
    await api.getDecisions({ type: "technical", status: "active", limit: 10 });
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("type=technical");
    expect(url).toContain("status=active");
    expect(url).toContain("limit=10");
  });

  it("getDecision sends correct request with id", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ id: "d1", title: "Test" }),
    });
    await api.getDecision("d1");
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/decisions/d1");
  });

  it("searchDecisions sends query param", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ decisions: [], total: 0 }),
    });
    await api.searchDecisions("React");
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/decisions/search?q=React");
  });

  it("whyDidWe sends POST with question", async () => {
    const fetchFn = mockFetch({
      json: () =>
        Promise.resolve({
          answer: "Because...",
          decisions: [],
          sources: [],
          confidence: 0.9,
        }),
    });
    await api.whyDidWe("choose React?");
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/decisions/why");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ question: "choose React?" });
  });

  it("extractDecisions sends POST with artifact_ids", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ extracted_count: 0, decisions: [] }),
    });
    await api.extractDecisions(["a1", "a2"]);
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/decisions/extract");
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ artifact_ids: ["a1", "a2"] });
  });

  it("getDecisionTimeline sends topic param", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ timeline: [] }),
    });
    await api.getDecisionTimeline("authentication");
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/decisions/timeline?topic=authentication");
  });

  // ── Risk Radar endpoints ──

  it("scanRisks sends POST request", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ alerts: [], summary: {} }),
    });
    await api.scanRisks();
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/risk-radar/scan");
    expect(options.method).toBe("POST");
  });

  it("getAlerts sends correct request", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ alerts: [], total: 0 }),
    });
    await api.getAlerts();
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/risk-radar/alerts?");
  });

  it("getAlerts passes filter params", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ alerts: [], total: 0 }),
    });
    await api.getAlerts({ severity: "critical", type: "key_person_risk" });
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("severity=critical");
    expect(url).toContain("type=key_person_risk");
  });

  it("acknowledgeAlert sends POST with correct id", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ status: "ok" }),
    });
    await api.acknowledgeAlert("alert-123");
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/risk-radar/alerts/alert-123/acknowledge");
    expect(options.method).toBe("POST");
  });

  it("resolveAlert sends POST with correct id", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ status: "ok" }),
    });
    await api.resolveAlert("alert-456");
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/risk-radar/alerts/alert-456/resolve");
    expect(options.method).toBe("POST");
  });

  it("getRiskSummary sends GET request", async () => {
    const fetchFn = mockFetch({
      json: () =>
        Promise.resolve({
          total_alerts: 0,
          by_severity: {},
          by_type: {},
          critical_count: 0,
          high_count: 0,
          medium_count: 0,
          low_count: 0,
        }),
    });
    await api.getRiskSummary();
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/risk-radar/summary");
    // GET is the default method, so method may be undefined or GET
    expect(options.method).toBeUndefined();
  });

  // ── Continuity endpoints ──

  it("getContinuityDashboard sends GET request", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ overall_score: 80 }),
    });
    await api.getContinuityDashboard();
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/continuity/dashboard");
    expect(options.method).toBeUndefined();
  });

  it("getMemberContinuity sends correct member id", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ member_id: "m1", score: 45 }),
    });
    await api.getMemberContinuity("m1");
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/continuity/member/m1");
  });

  it("getTeamContinuity sends GET request", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ overall_score: 70 }),
    });
    await api.getTeamContinuity();
    const [url] = fetchFn.mock.calls[0];
    expect(url).toContain("/continuity/team");
  });

  it("calculateContinuity sends POST request", async () => {
    const fetchFn = mockFetch({
      json: () => Promise.resolve({ status: "ok" }),
    });
    await api.calculateContinuity();
    const [url, options] = fetchFn.mock.calls[0];
    expect(url).toContain("/continuity/calculate");
    expect(options.method).toBe("POST");
  });
});
