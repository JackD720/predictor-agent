import { useState, useEffect, useCallback } from "react";

const API_BASE = "https://live-trader-164814074525.us-central1.run.app";

// ─── Utility Components ───────────────────────────────────────

function StatusPulse({ active, label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: active ? "#22c55e" : "#ef4444",
          boxShadow: active
            ? "0 0 8px #22c55e, 0 0 16px #22c55e40"
            : "0 0 8px #ef4444, 0 0 16px #ef444440",
          animation: active ? "pulse 2s ease-in-out infinite" : "none",
        }}
      />
      <span style={{ fontSize: 12, color: "#94a3b8", fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase", letterSpacing: 1 }}>
        {label}
      </span>
    </div>
  );
}

function MetricCard({ label, value, sub, accent = "#22c55e", large }) {
  return (
    <div
      style={{
        background: "linear-gradient(135deg, #0f172a 0%, #1a1f35 100%)",
        border: "1px solid #1e293b",
        borderRadius: 12,
        padding: large ? "28px 24px" : "20px 18px",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 2,
          background: `linear-gradient(90deg, transparent 0%, ${accent} 50%, transparent 100%)`,
          opacity: 0.6,
        }}
      />
      <div style={{ fontSize: 11, color: "#64748b", fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase", letterSpacing: 1.5, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: large ? 32 : 24, fontWeight: 700, color: "#f1f5f9", fontFamily: "JetBrains Mono, monospace" }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 12, color: "#64748b", marginTop: 4, fontFamily: "JetBrains Mono, monospace" }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function SectionHeader({ icon, title, action }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, marginTop: 32 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#e2e8f0", fontFamily: "JetBrains Mono, monospace", textTransform: "uppercase", letterSpacing: 1 }}>
          {title}
        </h2>
      </div>
      {action}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────

export default function AgentWalletDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [runResult, setRunResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [killSwitchLoading, setKillSwitchLoading] = useState(false);

  const fetchDashboard = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/dashboard`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
      setError(null);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 30000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const triggerRun = async () => {
    setRunning(true);
    setRunResult(null);
    try {
      const resp = await fetch(`${API_BASE}/run`, { method: "POST" });
      const json = await resp.json();
      setRunResult(json);
      fetchDashboard();
    } catch (e) {
      setRunResult({ error: e.message });
    } finally {
      setRunning(false);
    }
  };

  const toggleKillSwitch = async (activate) => {
    setKillSwitchLoading(true);
    try {
      await fetch(`${API_BASE}/kill-switch?activate=${activate}&reason=dashboard`, { method: "POST" });
      fetchDashboard();
    } catch (e) {
      console.error(e);
    } finally {
      setKillSwitchLoading(false);
    }
  };

  const killActive = data?.governance?.kill_switch_active;
  const balance = data?.balance?.usd ?? 0;
  const positions = data?.positions?.market_positions ?? data?.positions?.positions ?? [];
  const fills = data?.recent_fills?.fills ?? [];
  const gov = data?.governance ?? {};

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #020617 0%, #0a0f1e 50%, #020617 100%)",
        color: "#e2e8f0",
        fontFamily: "'Inter', -apple-system, sans-serif",
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes slideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
      `}</style>

      {/* ─── Header ─── */}
      <div
        style={{
          borderBottom: "1px solid #1e293b",
          padding: "20px 32px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "rgba(2, 6, 23, 0.8)",
          backdropFilter: "blur(12px)",
          position: "sticky",
          top: 0,
          zIndex: 100,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "JetBrains Mono, monospace", color: "#f1f5f9" }}>
            <span style={{ color: "#22c55e" }}>agent</span>wallet
          </div>
          <div style={{ width: 1, height: 24, background: "#1e293b" }} />
          <div style={{ fontSize: 12, color: "#64748b", fontFamily: "JetBrains Mono, monospace" }}>
            LIVE TRADER v1.0
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <StatusPulse active={!error && !loading} label={error ? "Error" : "Connected"} />

          {lastRefresh && (
            <span style={{ fontSize: 11, color: "#475569", fontFamily: "JetBrains Mono, monospace" }}>
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}

          <button
            onClick={fetchDashboard}
            style={{
              background: "transparent",
              border: "1px solid #1e293b",
              color: "#94a3b8",
              padding: "6px 12px",
              borderRadius: 6,
              cursor: "pointer",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 11,
            }}
          >
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* ─── Content ─── */}
      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 32px" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 80, color: "#475569" }}>
            <div style={{ width: 24, height: 24, border: "2px solid #22c55e", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite", margin: "0 auto 16px" }} />
            Connecting to agent...
          </div>
        ) : error ? (
          <div style={{ textAlign: "center", padding: 80, color: "#ef4444" }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>⚠</div>
            <div style={{ fontSize: 14, fontFamily: "JetBrains Mono, monospace" }}>Connection failed: {error}</div>
            <div style={{ fontSize: 12, color: "#64748b", marginTop: 8 }}>Check that your Cloud Run service is running</div>
          </div>
        ) : (
          <>
            {/* ─── Top Metrics ─── */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, animation: "slideIn 0.3s ease-out" }}>
              <MetricCard
                label="Balance"
                value={`$${balance.toFixed(2)}`}
                sub={`${data?.balance?.cents ?? 0} cents`}
                accent="#22c55e"
                large
              />
              <MetricCard
                label="Positions"
                value={positions.length}
                sub="active markets"
                accent="#3b82f6"
              />
              <MetricCard
                label="Approval Rate"
                value={`${((gov.approval_rate ?? 0) * 100).toFixed(0)}%`}
                sub={`${gov.signals_processed ?? 0} signals processed`}
                accent="#a855f7"
              />
              <MetricCard
                label="Daily Spend"
                value={`$${((gov.daily_spend_cents ?? 0) / 100).toFixed(2)}`}
                sub={`of $${((gov.config?.max_daily_spend_cents ?? 1000) / 100).toFixed(2)} limit`}
                accent="#f59e0b"
              />
            </div>

            {/* ─── Controls ─── */}
            <SectionHeader icon="🎮" title="Controls" />
            <div
              style={{
                display: "flex",
                gap: 12,
                padding: 20,
                background: "linear-gradient(135deg, #0f172a 0%, #1a1f35 100%)",
                border: "1px solid #1e293b",
                borderRadius: 12,
              }}
            >
              <button
                onClick={triggerRun}
                disabled={running || killActive}
                style={{
                  background: running
                    ? "#1e293b"
                    : "linear-gradient(135deg, #059669 0%, #10b981 100%)",
                  border: "none",
                  color: running ? "#64748b" : "#fff",
                  padding: "12px 24px",
                  borderRadius: 8,
                  cursor: running || killActive ? "not-allowed" : "pointer",
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 13,
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  opacity: killActive ? 0.4 : 1,
                }}
              >
                {running ? (
                  <>
                    <span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>⟳</span>
                    Running Pipeline...
                  </>
                ) : (
                  <>▶ Run Trade Cycle</>
                )}
              </button>

              <button
                onClick={() => toggleKillSwitch(!killActive)}
                disabled={killSwitchLoading}
                style={{
                  background: killActive
                    ? "linear-gradient(135deg, #991b1b 0%, #dc2626 100%)"
                    : "transparent",
                  border: killActive ? "none" : "1px solid #dc2626",
                  color: killActive ? "#fff" : "#dc2626",
                  padding: "12px 24px",
                  borderRadius: 8,
                  cursor: "pointer",
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 13,
                  fontWeight: 600,
                }}
              >
                {killActive ? "🔴 KILL SWITCH ACTIVE — Click to Reset" : "⚡ Arm Kill Switch"}
              </button>

              <div style={{ flex: 1 }} />

              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#64748b", fontSize: 12, fontFamily: "JetBrains Mono, monospace" }}>
                <span>Mode:</span>
                <span style={{ color: data?.dry_run ? "#f59e0b" : "#ef4444", fontWeight: 600 }}>
                  {data?.dry_run ? "🧪 DRY RUN" : "🔴 LIVE"}
                </span>
              </div>
            </div>

            {/* ─── Run Result ─── */}
            {runResult && (
              <div
                style={{
                  marginTop: 12,
                  padding: 16,
                  background: runResult.error ? "#1c0a0a" : "#0a1c0a",
                  border: `1px solid ${runResult.error ? "#7f1d1d" : "#14532d"}`,
                  borderRadius: 8,
                  fontFamily: "JetBrains Mono, monospace",
                  fontSize: 12,
                  animation: "slideIn 0.3s ease-out",
                }}
              >
                {runResult.error ? (
                  <span style={{ color: "#fca5a5" }}>Error: {runResult.error}</span>
                ) : (
                  <div style={{ color: "#86efac" }}>
                    <strong>Pipeline Complete</strong> — 
                    {" "}{runResult.results?.total ?? 0} signals → 
                    {" "}{runResult.results?.matched ?? 0} matched → 
                    {" "}{runResult.results?.approved ?? 0} approved → 
                    {" "}{runResult.results?.executed ?? 0} executed
                    {runResult.results?.trades?.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        {runResult.results.trades.map((t, i) => (
                          <div key={i} style={{ color: "#bbf7d0" }}>
                            💸 {t.side.toUpperCase()} {t.count}x {t.ticker} @ {t.price}¢
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ─── Governance Rules ─── */}
            <SectionHeader icon="🔐" title="Governance Engine" />
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: 12,
              }}
            >
              {[
                { label: "Max Per Trade", value: `$${((gov.config?.max_per_trade_cents ?? 0) / 100).toFixed(2)}`, icon: "💰" },
                { label: "Max Daily", value: `$${((gov.config?.max_daily_spend_cents ?? 0) / 100).toFixed(2)}`, icon: "📅" },
                { label: "Max Weekly", value: `$${((gov.config?.max_weekly_spend_cents ?? 0) / 100).toFixed(2)}`, icon: "📊" },
                { label: "Drawdown Kill", value: `${((gov.config?.drawdown_kill_switch_pct ?? 0) * 100).toFixed(0)}%`, icon: "🛑" },
                { label: "Min ARS Score", value: gov.config?.min_ars_score ?? "—", icon: "📈" },
                { label: "Consecutive Loss Limit", value: gov.config?.consecutive_loss_limit ?? "—", icon: "🚨" },
              ].map((rule, i) => (
                <div
                  key={i}
                  style={{
                    background: "#0f172a",
                    border: "1px solid #1e293b",
                    borderRadius: 8,
                    padding: "14px 16px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span>{rule.icon}</span>
                    <span style={{ fontSize: 12, color: "#94a3b8", fontFamily: "JetBrains Mono, monospace" }}>{rule.label}</span>
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9", fontFamily: "JetBrains Mono, monospace" }}>
                    {rule.value}
                  </span>
                </div>
              ))}
            </div>

            {/* ─── Active Positions ─── */}
            <SectionHeader
              icon="📊"
              title={`Positions (${positions.length})`}
            />
            {positions.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: "#475569", background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, fontFamily: "JetBrains Mono, monospace", fontSize: 13 }}>
                No active positions
              </div>
            ) : (
              <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #1e293b" }}>
                      {["Market", "Side", "Qty", "Avg Price", "Value"].map((h) => (
                        <th
                          key={h}
                          style={{
                            padding: "12px 16px",
                            textAlign: "left",
                            fontSize: 11,
                            color: "#64748b",
                            fontFamily: "JetBrains Mono, monospace",
                            textTransform: "uppercase",
                            letterSpacing: 1,
                            fontWeight: 500,
                          }}
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((p, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid #0f172a" }}>
                        <td style={{ padding: "12px 16px", fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#e2e8f0", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {p.ticker || p.market_ticker || "—"}
                        </td>
                        <td style={{ padding: "12px 16px" }}>
                          <span
                            style={{
                              fontFamily: "JetBrains Mono, monospace",
                              fontSize: 11,
                              fontWeight: 600,
                              padding: "2px 8px",
                              borderRadius: 4,
                              background: (p.side || "yes") === "yes" ? "#052e16" : "#450a0a",
                              color: (p.side || "yes") === "yes" ? "#4ade80" : "#fca5a5",
                            }}
                          >
                            {(p.side || "YES").toUpperCase()}
                          </span>
                        </td>
                        <td style={{ padding: "12px 16px", fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: "#f1f5f9" }}>
                          {p.total_traded ?? p.quantity ?? "—"}
                        </td>
                        <td style={{ padding: "12px 16px", fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: "#94a3b8" }}>
                          {p.resting_orders_count !== undefined ? `${p.resting_orders_count} orders` : "—"}
                        </td>
                        <td style={{ padding: "12px 16px", fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: "#22c55e" }}>
                          {p.market_exposure !== undefined ? `$${(p.market_exposure / 100).toFixed(2)}` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ─── Recent Fills ─── */}
            <SectionHeader
              icon="⚡"
              title={`Recent Trades (${fills.length})`}
            />
            {fills.length === 0 ? (
              <div style={{ padding: 40, textAlign: "center", color: "#475569", background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, fontFamily: "JetBrains Mono, monospace", fontSize: 13 }}>
                No recent trades
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {fills.map((fill, i) => (
                  <div
                    key={i}
                    style={{
                      background: "#0f172a",
                      border: "1px solid #1e293b",
                      borderRadius: 8,
                      padding: "14px 18px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      animation: `slideIn 0.3s ease-out ${i * 0.05}s both`,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span
                        style={{
                          fontFamily: "JetBrains Mono, monospace",
                          fontSize: 11,
                          fontWeight: 600,
                          padding: "2px 8px",
                          borderRadius: 4,
                          background: fill.action === "buy" ? "#052e16" : "#450a0a",
                          color: fill.action === "buy" ? "#4ade80" : "#fca5a5",
                        }}
                      >
                        {(fill.action || "BUY").toUpperCase()}
                      </span>
                      <div>
                        <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#e2e8f0" }}>
                          {fill.ticker || "—"}
                        </div>
                        <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 10, color: "#475569", marginTop: 2 }}>
                          {fill.created_time ? new Date(fill.created_time).toLocaleString() : "—"}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 13, color: "#f1f5f9", fontWeight: 600 }}>
                        {fill.count ?? fill.no_count ?? fill.yes_count ?? "—"}x @ {fill.yes_price ?? fill.no_price ?? "—"}¢
                      </div>
                      <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, color: "#64748b", marginTop: 2 }}>
                        Side: {(fill.side || "—").toUpperCase()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ─── Spend Tracking ─── */}
            <SectionHeader icon="📈" title="Spend Tracking" />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
              {[
                {
                  label: "Daily",
                  spent: (gov.daily_spend_cents ?? 0) / 100,
                  limit: (gov.config?.max_daily_spend_cents ?? 1000) / 100,
                  color: "#3b82f6",
                },
                {
                  label: "Weekly",
                  spent: (gov.weekly_spend_cents ?? 0) / 100,
                  limit: (gov.config?.max_weekly_spend_cents ?? 2500) / 100,
                  color: "#a855f7",
                },
              ].map((track, i) => {
                const pct = track.limit > 0 ? (track.spent / track.limit) * 100 : 0;
                return (
                  <div
                    key={i}
                    style={{
                      background: "#0f172a",
                      border: "1px solid #1e293b",
                      borderRadius: 8,
                      padding: "18px 20px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                      <span style={{ fontSize: 12, color: "#94a3b8", fontFamily: "JetBrains Mono, monospace" }}>
                        {track.label} Spend
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9", fontFamily: "JetBrains Mono, monospace" }}>
                        ${track.spent.toFixed(2)} / ${track.limit.toFixed(2)}
                      </span>
                    </div>
                    <div style={{ height: 6, background: "#1e293b", borderRadius: 3, overflow: "hidden" }}>
                      <div
                        style={{
                          height: "100%",
                          width: `${Math.min(pct, 100)}%`,
                          background: pct > 80 ? "#ef4444" : track.color,
                          borderRadius: 3,
                          transition: "width 0.5s ease-out",
                        }}
                      />
                    </div>
                    <div style={{ fontSize: 10, color: "#475569", marginTop: 6, fontFamily: "JetBrains Mono, monospace", textAlign: "right" }}>
                      {pct.toFixed(1)}% used
                    </div>
                  </div>
                );
              })}
            </div>

            {/* ─── Footer ─── */}
            <div style={{ textAlign: "center", padding: "40px 0 20px", color: "#334155", fontSize: 11, fontFamily: "JetBrains Mono, monospace" }}>
              AgentWallet • Autonomous AI Trading Infrastructure • Cloud Run + Kalshi
            </div>
          </>
        )}
      </div>
    </div>
  );
}