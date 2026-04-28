import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { QuotaListResponse, QuotaRow } from "../types";

const POLL_INTERVAL_MS = 10_000;

const DURATION_PRESETS = [
  { label: "15 min", minutes: 15 },
  { label: "1 hour", minutes: 60 },
  { label: "4 hours", minutes: 240 },
];

const MULTIPLIER_PRESETS = [1.5, 2, 5];

function formatRemaining(seconds: number): string {
  if (seconds <= 0) return "expired";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return remM === 0 ? `${h}h` : `${h}h ${remM}m`;
}

function usagePct(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function usageColor(pct: number): string {
  if (pct >= 90) return "#ef4444"; // red
  if (pct >= 70) return "#f59e0b"; // amber
  return "#10b981"; // green
}

interface OverrideModalState {
  row: QuotaRow;
}

function OverrideModal({
  state,
  maxMinutes,
  onClose,
  onApplied,
}: {
  state: OverrideModalState;
  maxMinutes: number;
  onClose: () => void;
  onApplied: () => void;
}) {
  const { row } = state;
  const [multiplier, setMultiplier] = useState<number>(2);
  const [duration, setDuration] = useState<number>(60);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const newLimit = Math.max(1, Math.round(row.baseline_limit * multiplier));

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.setQuotaOverride(row.org_id, {
        cost_class: row.cost_class,
        new_limit: newLimit,
        duration_minutes: duration,
        reason: reason || undefined,
      });
      onApplied();
    } catch (e: any) {
      setError(e?.message ?? "Failed to apply override");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="override-modal-title"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "white",
          borderRadius: 12,
          padding: 24,
          width: 420,
          maxWidth: "90vw",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
        }}
      >
        <h2 id="override-modal-title" style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>
          Override quota — {row.org_name}
        </h2>
        <p style={{ marginTop: 6, color: "#6b7280", fontSize: 13 }}>
          {row.cost_class.toUpperCase()} · baseline {row.baseline_limit}/{row.window_seconds}s
        </p>

        <label style={{ display: "block", marginTop: 16, fontSize: 13, fontWeight: 500 }}>Multiplier</label>
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          {MULTIPLIER_PRESETS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMultiplier(m)}
              style={{
                flex: 1,
                padding: "8px 12px",
                border: "1px solid",
                borderColor: multiplier === m ? "#6366f1" : "#e5e7eb",
                background: multiplier === m ? "#eef2ff" : "white",
                borderRadius: 8,
                cursor: "pointer",
              }}
            >
              {m}×
            </button>
          ))}
        </div>
        <p style={{ marginTop: 6, fontSize: 12, color: "#6b7280" }}>
          New limit: <strong>{newLimit}</strong> per {row.window_seconds}s
        </p>

        <label style={{ display: "block", marginTop: 16, fontSize: 13, fontWeight: 500 }}>Duration</label>
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          {DURATION_PRESETS.filter((p) => p.minutes <= maxMinutes).map((p) => (
            <button
              key={p.minutes}
              type="button"
              onClick={() => setDuration(p.minutes)}
              style={{
                flex: 1,
                padding: "8px 12px",
                border: "1px solid",
                borderColor: duration === p.minutes ? "#6366f1" : "#e5e7eb",
                background: duration === p.minutes ? "#eef2ff" : "white",
                borderRadius: 8,
                cursor: "pointer",
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        <label style={{ display: "block", marginTop: 16, fontSize: 13, fontWeight: 500 }} htmlFor="override-reason">
          Reason (optional)
        </label>
        <input
          id="override-reason"
          type="text"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={240}
          placeholder="Incident #1234 — runaway pipeline"
          style={{
            width: "100%",
            marginTop: 6,
            padding: "8px 10px",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            fontSize: 13,
            boxSizing: "border-box",
          }}
        />

        {error && (
          <p role="alert" style={{ marginTop: 12, color: "#ef4444", fontSize: 13 }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", gap: 8, marginTop: 20, justifyContent: "flex-end" }}>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            style={{
              padding: "8px 16px",
              border: "1px solid #e5e7eb",
              background: "white",
              borderRadius: 8,
              cursor: submitting ? "default" : "pointer",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={submitting}
            style={{
              padding: "8px 16px",
              border: "none",
              background: submitting ? "#a5b4fc" : "#6366f1",
              color: "white",
              borderRadius: 8,
              cursor: submitting ? "default" : "pointer",
            }}
          >
            {submitting ? "Applying…" : "Apply override"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function AdminQuotasPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin" || user?.role === "owner";
  const [data, setData] = useState<QuotaListResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [modalState, setModalState] = useState<OverrideModalState | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const resp = await api.getAdminQuotas();
      setData(resp);
      setLoadError(null);
    } catch (e: any) {
      setLoadError(e?.message ?? "Failed to load quotas");
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    refresh();
    const id = window.setInterval(refresh, POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [isAdmin, refresh]);

  const sortedRows = useMemo(() => {
    if (!data) return [];
    // Sort by usage percentage desc so noisy tenants surface at the top.
    return [...data.rows].sort((a, b) => usagePct(b.used, b.effective_limit) - usagePct(a.used, a.effective_limit));
  }, [data]);

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  const onRevoke = async (row: QuotaRow) => {
    const id = `${row.org_id}:${row.cost_class}`;
    setRevoking(id);
    try {
      await api.clearQuotaOverride(row.org_id, row.cost_class);
      await refresh();
    } catch {
      // Surface via the loadError channel for now; modal would be over-engineered.
      setLoadError("Failed to revoke override");
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Quota dashboard</h1>
        <p style={{ marginTop: 4, color: "#6b7280", fontSize: 13 }}>
          Live per-org usage of the W18 quota gate. Refreshes every {POLL_INTERVAL_MS / 1000}s. Apply an override to
          temporarily lift a tenant's budget during an incident.
        </p>
      </header>

      {loadError && (
        <div
          role="alert"
          style={{ marginBottom: 12, padding: 12, background: "#fef2f2", color: "#991b1b", borderRadius: 8, fontSize: 13 }}
        >
          {loadError}
        </div>
      )}

      {!data && !loadError && <p>Loading…</p>}

      {data && sortedRows.length === 0 && (
        <p style={{ color: "#6b7280" }}>No organizations registered yet.</p>
      )}

      {data && sortedRows.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>
                <th style={{ padding: "10px 8px" }}>Organization</th>
                <th style={{ padding: "10px 8px" }}>Class</th>
                <th style={{ padding: "10px 8px" }}>Usage</th>
                <th style={{ padding: "10px 8px" }}>Override</th>
                <th style={{ padding: "10px 8px", textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.map((row) => {
                const pct = usagePct(row.used, row.effective_limit);
                const rowKey = `${row.org_id}:${row.cost_class}`;
                return (
                  <tr key={rowKey} style={{ borderBottom: "1px solid #f3f4f6" }}>
                    <td style={{ padding: "10px 8px" }}>
                      <div style={{ fontWeight: 500 }}>{row.org_name}</div>
                      {row.org_slug && <div style={{ color: "#9ca3af", fontSize: 11 }}>{row.org_slug}</div>}
                    </td>
                    <td style={{ padding: "10px 8px", textTransform: "uppercase", color: "#6b7280" }}>{row.cost_class}</td>
                    <td style={{ padding: "10px 8px", minWidth: 200 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div
                          style={{
                            flex: 1,
                            height: 8,
                            background: "#f3f4f6",
                            borderRadius: 4,
                            overflow: "hidden",
                          }}
                        >
                          <div
                            data-testid={`usage-bar-${rowKey}`}
                            style={{
                              width: `${pct}%`,
                              height: "100%",
                              background: usageColor(pct),
                              transition: "width 200ms ease",
                            }}
                          />
                        </div>
                        <span style={{ minWidth: 90, textAlign: "right", color: "#6b7280" }}>
                          {row.used} / {row.effective_limit}
                          {row.effective_limit !== row.baseline_limit && (
                            <span style={{ color: "#9ca3af" }}> (base {row.baseline_limit})</span>
                          )}
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: "10px 8px" }}>
                      {row.override ? (
                        <span style={{ color: "#7c3aed" }}>
                          {row.override.limit} for {formatRemaining(row.override.remaining_seconds)}
                          {row.override.reason && (
                            <div style={{ color: "#9ca3af", fontSize: 11, fontStyle: "italic" }}>“{row.override.reason}”</div>
                          )}
                        </span>
                      ) : (
                        <span style={{ color: "#9ca3af" }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: "10px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                      {row.override ? (
                        <button
                          type="button"
                          onClick={() => onRevoke(row)}
                          disabled={revoking === rowKey}
                          style={{
                            padding: "6px 10px",
                            border: "1px solid #fca5a5",
                            background: "white",
                            color: "#b91c1c",
                            borderRadius: 6,
                            cursor: revoking === rowKey ? "default" : "pointer",
                            fontSize: 12,
                          }}
                        >
                          {revoking === rowKey ? "…" : "Revoke"}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => setModalState({ row })}
                          style={{
                            padding: "6px 10px",
                            border: "1px solid #e5e7eb",
                            background: "white",
                            borderRadius: 6,
                            cursor: "pointer",
                            fontSize: 12,
                          }}
                        >
                          Override
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modalState && (
        <OverrideModal
          state={modalState}
          maxMinutes={data?.max_override_minutes ?? 240}
          onClose={() => setModalState(null)}
          onApplied={async () => {
            setModalState(null);
            await refresh();
          }}
        />
      )}
    </div>
  );
}
