import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Clock,
  RefreshCw, Filter, Search, ChevronDown, ChevronUp, ExternalLink,
  Zap, Shield, Target, BarChart3, Users, DollarSign, Activity,
  Eye, Loader2, ArrowUpRight, ArrowDownRight, Info, X, Settings,
  Play, Pause, Bell, WifiOff, Database, Wallet, FileText,
  ThumbsUp, BookOpen, Power, AlertCircle, ArrowRight, CircleDot
} from 'lucide-react';

// ============================================
// CONFIGURATION
// ============================================
const PREDICTOR_API = 'https://predictor-agent-api-164814074525.us-central1.run.app';
const TRADER_API = 'https://live-trader-164814074525.us-central1.run.app';

// ============================================
// API SERVICES
// ============================================
const predictorApi = {
  async getSignals(refresh = false) {
    const url = `${PREDICTOR_API}/api/signals${refresh ? '?refresh=true' : ''}`;
    const r = await fetch(url); if (!r.ok) throw new Error('Failed'); return r.json();
  },
  async getStats() { const r = await fetch(`${PREDICTOR_API}/api/stats`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async getTraders() { const r = await fetch(`${PREDICTOR_API}/api/traders`); if (!r.ok) throw new Error('Failed'); return r.json(); },
};

const traderApi = {
  async dashboard() { const r = await fetch(`${TRADER_API}/dashboard`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async run() { const r = await fetch(`${TRADER_API}/run`, { method: 'POST' }); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async balance() { const r = await fetch(`${TRADER_API}/balance`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async stats() { const r = await fetch(`${TRADER_API}/stats`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async positions() { const r = await fetch(`${TRADER_API}/positions`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async trades() { const r = await fetch(`${TRADER_API}/trades`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async audit() { const r = await fetch(`${TRADER_API}/audit`); if (!r.ok) throw new Error('Failed'); return r.json(); },
  async killSwitch(activate, reason = 'dashboard') {
    const r = await fetch(`${TRADER_API}/kill-switch?activate=${activate}&reason=${reason}`, { method: 'POST' });
    if (!r.ok) throw new Error('Failed'); return r.json();
  },
};

// ============================================
// UTILITIES
// ============================================
const fmt = (n, d = 0) => { if (n >= 1e6) return `$${(n/1e6).toFixed(1)}M`; if (n >= 1e3) return `$${(n/1e3).toFixed(1)}K`; return `$${n.toFixed(d)}`; };
const fmtPct = (n) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(0)}%`;
const entryConfig = (q) => ({
  good: { color: '#34d399', bg: 'rgba(52,211,153,0.15)', label: 'GOOD' },
  fair: { color: '#fbbf24', bg: 'rgba(251,191,36,0.15)', label: 'FAIR' },
  late: { color: '#f97316', bg: 'rgba(249,115,22,0.15)', label: 'LATE' },
  very_late: { color: '#ef4444', bg: 'rgba(239,68,68,0.15)', label: 'LATE' },
}[q] || { color: '#fbbf24', bg: 'rgba(251,191,36,0.15)', label: 'FAIR' });
const arsColor = (s) => s >= 0.6 ? '#34d399' : s >= 0.4 ? '#fbbf24' : '#ef4444';

// ============================================
// SIDEBAR
// ============================================
const navItems = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'signals', label: 'Signals', icon: Target },
  { id: 'traders', label: 'Top Traders', icon: Users },
  { id: 'kalshi', label: 'Kalshi Trading', icon: Zap, accent: true },
  { id: 'governance', label: 'Governance', icon: Shield },
  { id: 'transactions', label: 'Transactions', icon: FileText },
  { id: 'rules', label: 'Rules', icon: BookOpen },
];

function Sidebar({ page, setPage }) {
  return (
    <div style={{
      width: 220, minHeight: '100vh', background: '#0c1222', borderRight: '1px solid #1e293b',
      display: 'flex', flexDirection: 'column', position: 'fixed', left: 0, top: 0, zIndex: 50,
    }}>
      <div style={{ padding: '20px 18px', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 32, height: 32, borderRadius: 8, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Shield size={18} color="#fff" />
        </div>
        <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9', letterSpacing: -0.5 }}>AgentWallet</span>
      </div>

      <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {navItems.map(item => {
          const Icon = item.icon;
          const active = page === item.id;
          return (
            <button key={item.id} onClick={() => setPage(item.id)} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 8,
              border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: active ? 600 : 400, width: '100%', textAlign: 'left',
              background: active ? 'rgba(99,102,241,0.15)' : 'transparent',
              color: active ? '#818cf8' : item.accent ? '#a78bfa' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}>
              <Icon size={18} />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div style={{ padding: '16px 14px', borderTop: '1px solid #1e293b' }}>
        <button onClick={() => setPage('settings')} style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 8,
          border: 'none', cursor: 'pointer', fontSize: 13, color: '#64748b', background: 'transparent', width: '100%',
        }}>
          <Settings size={18} /> Settings
        </button>
        <div style={{ padding: '10px 12px', fontSize: 12, color: '#475569' }}>
          <div style={{ fontWeight: 600, color: '#e2e8f0' }}>Jack</div>
          <div>jack@bytem.co</div>
        </div>
      </div>
    </div>
  );
}

// ============================================
// OVERVIEW PAGE
// ============================================
function OverviewPage({ liveData, signalData, onNavigate }) {
  const bal = liveData?.balance?.usd ?? 0;
  const gov = liveData?.governance ?? {};
  const positions = liveData?.positions?.market_positions ?? [];
  const signalCount = signalData?.signals?.length ?? 0;

  return (
    <div>
      <PageHeader title="Overview" subtitle="AgentWallet trading infrastructure at a glance" />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <MetricBox label="Kalshi Balance" value={`$${bal.toFixed(2)}`} icon={<DollarSign size={18} />} color="#34d399" />
        <MetricBox label="Active Positions" value={positions.length} icon={<BarChart3 size={18} />} color="#6366f1" />
        <MetricBox label="Signals Available" value={signalCount} icon={<Target size={18} />} color="#f59e0b" />
        <MetricBox label="Approval Rate" value={`${((gov.approval_rate ?? 0) * 100).toFixed(0)}%`} icon={<Shield size={18} />} color="#a855f7" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <Card title="Quick Actions">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <QuickAction label="View Signals" sub="Polymarket smart money signals" onClick={() => onNavigate('signals')} />
            <QuickAction label="Kalshi Trading" sub="Live positions & execution" onClick={() => onNavigate('kalshi')} />
            <QuickAction label="Governance Engine" sub="Rules, approvals, audit trail" onClick={() => onNavigate('governance')} />
          </div>
        </Card>
        <Card title="System Status">
          <StatusRow label="Predictor Agent" status="connected" />
          <StatusRow label="Kalshi API" status={liveData ? "connected" : "disconnected"} />
          <StatusRow label="Governance Engine" status={gov.kill_switch_active ? "kill_switch" : "active"} />
          <StatusRow label="Cloud Scheduler" status="running" sub="Every 30 min" />
        </Card>
      </div>
    </div>
  );
}

// ============================================
// KALSHI TRADING PAGE
// ============================================
function KalshiTradingPage({ liveData, onRefresh }) {
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [killLoading, setKillLoading] = useState(false);
  const [fills, setFills] = useState([]);
  const [fillsLoading, setFillsLoading] = useState(true);

  const bal = liveData?.balance?.usd ?? 0;
  const gov = liveData?.governance ?? {};
  const positions = liveData?.positions?.market_positions ?? [];
  const killActive = gov.kill_switch_active;

  useEffect(() => {
    traderApi.trades().then(d => setFills(d.fills || [])).catch(() => {}).finally(() => setFillsLoading(false));
  }, []);

  const handleRun = async () => {
    setRunning(true); setRunResult(null);
    try { const r = await traderApi.run(); setRunResult(r); onRefresh(); }
    catch (e) { setRunResult({ error: e.message }); }
    finally { setRunning(false); }
  };

  const handleKillSwitch = async (activate) => {
    setKillLoading(true);
    try { await traderApi.killSwitch(activate); onRefresh(); }
    catch (e) { console.error(e); }
    finally { setKillLoading(false); }
  };

  return (
    <div>
      <PageHeader title="Kalshi Trading" subtitle="AI agent prediction market trading with guardrails">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusPill connected={!!liveData} />
          <span style={{ fontSize: 13, color: liveData?.dry_run ? '#f59e0b' : '#ef4444', fontWeight: 600, fontFamily: 'monospace' }}>
            {liveData?.dry_run ? '🧪 DRY RUN' : '🔴 LIVE'}
          </span>
        </div>
      </PageHeader>

      {/* Balance + Key Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
        <MetricBox label="Kalshi Balance" value={`$${bal.toFixed(2)}`} icon={<DollarSign size={18} />} color="#34d399" />
        <MetricBox label="Positions" value={positions.length} icon={<BarChart3 size={18} />} color="#6366f1" />
        <MetricBox label="Daily Spend" value={`$${((gov.daily_spend_cents ?? 0) / 100).toFixed(2)}`} sub={`of $${((gov.config?.max_daily_spend_cents ?? 1000) / 100).toFixed(2)}`} icon={<Activity size={18} />} color="#f59e0b" />
        <MetricBox label="Drawdown" value={`${((gov.current_drawdown_pct ?? 0) * 100).toFixed(1)}%`} sub={`${((gov.config?.drawdown_kill_switch_pct ?? 0.2) * 100).toFixed(0)}% kill`} icon={<AlertTriangle size={18} />} color={gov.current_drawdown_pct > 0.15 ? '#ef4444' : '#64748b'} />
      </div>

      {/* Controls */}
      <Card title="Controls" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', padding: 16 }}>
          <button onClick={handleRun} disabled={running || killActive} style={{
            background: running ? '#1e293b' : 'linear-gradient(135deg, #059669, #10b981)', border: 'none', color: '#fff',
            padding: '10px 20px', borderRadius: 8, cursor: running || killActive ? 'not-allowed' : 'pointer',
            fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8, opacity: killActive ? 0.4 : 1,
          }}>
            {running ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Running...</> : <><Play size={16} /> Run Trade Cycle</>}
          </button>

          <button onClick={() => handleKillSwitch(!killActive)} disabled={killLoading} style={{
            background: killActive ? 'linear-gradient(135deg, #991b1b, #dc2626)' : 'transparent',
            border: killActive ? 'none' : '1px solid #dc2626', color: killActive ? '#fff' : '#dc2626',
            padding: '10px 20px', borderRadius: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13,
          }}>
            {killActive ? '🔴 KILL SWITCH ACTIVE — Click to Reset' : '⚡ Arm Kill Switch'}
          </button>
        </div>

        {runResult && (
          <div style={{
            margin: '0 16px 16px', padding: 14, borderRadius: 8, fontSize: 13, fontFamily: 'monospace',
            background: runResult.error ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)',
            border: `1px solid ${runResult.error ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
            color: runResult.error ? '#fca5a5' : '#86efac',
          }}>
            {runResult.error ? `Error: ${runResult.error}` : (
              <>
                <strong>Pipeline Complete</strong> — {runResult.results?.total ?? 0} signals → {runResult.results?.matched ?? 0} matched → {runResult.results?.approved ?? 0} approved → {runResult.results?.executed ?? 0} executed
                {runResult.results?.trades?.map((t, i) => (
                  <div key={i} style={{ marginTop: 4 }}>💸 {t.side?.toUpperCase()} {t.count}x {t.ticker} @ {t.price}¢</div>
                ))}
              </>
            )}
          </div>
        )}
      </Card>

      {/* Positions */}
      <Card title={`Active Positions (${positions.length})`} style={{ marginBottom: 20 }}>
        {positions.length === 0 ? (
          <div style={{ padding: 30, textAlign: 'center', color: '#475569', fontSize: 13 }}>No active positions</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                {['Market', 'Side', 'Qty', 'Exposure'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, color: '#64748b', fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {positions.map((p, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.5)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: '#e2e8f0', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>
                    {p.ticker || p.market_ticker || '—'}
                  </td>
                  <td style={{ padding: '10px 14px' }}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'rgba(52,211,153,0.15)', color: '#34d399' }}>
                      {(p.side || 'YES').toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 14px', fontSize: 13, color: '#f1f5f9', fontFamily: 'monospace' }}>{p.total_traded ?? p.quantity ?? '—'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 13, color: '#34d399', fontFamily: 'monospace' }}>
                    {p.market_exposure !== undefined ? `$${(p.market_exposure / 100).toFixed(2)}` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Recent Fills */}
      <Card title={`Recent Trades (${fills.length})`}>
        {fillsLoading ? (
          <div style={{ padding: 30, textAlign: 'center', color: '#475569' }}><Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} /></div>
        ) : fills.length === 0 ? (
          <div style={{ padding: 30, textAlign: 'center', color: '#475569', fontSize: 13 }}>No trades yet</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {fills.slice(0, 20).map((f, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px',
                background: 'rgba(15,23,42,0.5)', borderRadius: 6, border: '1px solid rgba(30,41,59,0.5)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
                    background: f.action === 'buy' ? 'rgba(52,211,153,0.15)' : 'rgba(239,68,68,0.15)',
                    color: f.action === 'buy' ? '#34d399' : '#f87171',
                  }}>{(f.action || 'BUY').toUpperCase()}</span>
                  <div>
                    <div style={{ fontSize: 12, color: '#e2e8f0', fontFamily: 'monospace' }}>{f.ticker || '—'}</div>
                    <div style={{ fontSize: 10, color: '#475569' }}>{f.created_time ? new Date(f.created_time).toLocaleString() : '—'}</div>
                  </div>
                </div>
                <div style={{ textAlign: 'right', fontFamily: 'monospace' }}>
                  <div style={{ fontSize: 13, color: '#f1f5f9', fontWeight: 600 }}>
                    {f.count ?? f.yes_count ?? f.no_count ?? '—'}x @ {f.yes_price ?? f.no_price ?? '—'}¢
                  </div>
                  <div style={{ fontSize: 11, color: '#64748b' }}>{(f.side || '—').toUpperCase()}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

// ============================================
// GOVERNANCE PAGE
// ============================================
function GovernancePage({ liveData, signalData, onRefresh }) {
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [auditEntries, setAuditEntries] = useState([]);

  const bal = liveData?.balance?.usd ?? 0;
  const gov = liveData?.governance ?? {};
  const config = gov.config ?? {};

  useEffect(() => {
    traderApi.audit().then(d => setAuditEntries(d.entries || [])).catch(() => {});
  }, []);

  const handleRun = async () => {
    setRunning(true); setRunResult(null);
    try { const r = await traderApi.run(); setRunResult(r); onRefresh();
      traderApi.audit().then(d => setAuditEntries(d.entries || [])).catch(() => {});
    } catch (e) { setRunResult({ error: e.message }); }
    finally { setRunning(false); }
  };

  const dailyPct = config.max_daily_spend_cents ? ((gov.daily_spend_cents ?? 0) / config.max_daily_spend_cents) * 100 : 0;

  return (
    <div>
      <PageHeader title="Governance Engine" subtitle="Signal evaluation, rules engine, and audit trail">
        <button onClick={handleRun} disabled={running} style={{
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', color: '#fff',
          padding: '10px 20px', borderRadius: 8, cursor: running ? 'not-allowed' : 'pointer',
          fontWeight: 600, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          {running ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Running...</> : <><Play size={16} /> Run Governance Pipeline</>}
        </button>
      </PageHeader>

      {/* Key Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 24 }}>
        <MetricBox label="Balance" value={`$${bal.toFixed(2)}`} icon={<DollarSign size={18} />} color="#34d399" />
        <MetricBox label="Daily Spend" value={`$${((gov.daily_spend_cents ?? 0) / 100).toFixed(2)}`} sub={`of $${((config.max_daily_spend_cents ?? 0) / 100).toFixed(2)} limit`} icon={<Activity size={18} />} color="#3b82f6" />
        <MetricBox label="Approved" value={gov.signals_approved ?? 0} sub={`of ${gov.signals_processed ?? 0} signals`} icon={<CheckCircle size={18} />} color="#34d399" />
        <MetricBox label="Blocked" value={gov.signals_blocked ?? 0} sub={gov.signals_blocked > 0 ? 'review rules' : 'none yet'} icon={<AlertTriangle size={18} />} color="#f59e0b" />
        <GaugeBox label="DAILY USAGE" value={dailyPct} sub={`$${((gov.daily_spend_cents ?? 0) / 100).toFixed(2)} / $${((config.max_daily_spend_cents ?? 0) / 100).toFixed(2)}`} killLabel={`DRAWDOWN (${((config.drawdown_kill_switch_pct ?? 0.2) * 100).toFixed(0)}% KILL)`} />
      </div>

      {/* Run Result */}
      {runResult && (
        <div style={{
          marginBottom: 20, padding: 16, borderRadius: 10, fontSize: 13, fontFamily: 'monospace',
          background: runResult.error ? 'rgba(239,68,68,0.08)' : 'rgba(34,197,94,0.08)',
          border: `1px solid ${runResult.error ? 'rgba(239,68,68,0.2)' : 'rgba(34,197,94,0.2)'}`,
          color: runResult.error ? '#fca5a5' : '#86efac',
        }}>
          {runResult.error ? `Error: ${runResult.error}` : (
            <><strong>✅ Pipeline Complete</strong> — {runResult.results?.total ?? 0} signals → {runResult.results?.matched ?? 0} matched → {runResult.results?.approved ?? 0} approved → {runResult.results?.executed ?? 0} executed</>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Signals */}
        <Card title={`Incoming Signals (${signalData?.signals?.length ?? 0})`}>
          {(signalData?.signals || []).slice(0, 8).map((s, i) => (
            <div key={i} style={{
              padding: '12px 14px', borderBottom: '1px solid rgba(30,41,59,0.4)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>{s.market_title?.slice(0, 50)}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                    background: s.direction?.toLowerCase() === 'yes' ? 'rgba(52,211,153,0.2)' : 'rgba(239,68,68,0.2)',
                    color: s.direction?.toLowerCase() === 'yes' ? '#34d399' : '#f87171',
                  }}>{(s.direction || '').toUpperCase()}</span>
                </div>
                <div style={{ fontSize: 11, color: '#64748b', fontFamily: 'monospace' }}>
                  ARS <span style={{ color: arsColor(s.ars_score), fontWeight: 600 }}>{s.ars_score?.toFixed(2)}</span>
                  {' '}ENTRY <span style={{ color: entryConfig(s.entry_quality).color, fontWeight: 600 }}>{s.entry_quality}</span>
                  {' '}PRICE {(s.current_price * 100).toFixed(0)}¢
                  {' '}TRADERS {s.num_traders}
                </div>
              </div>
            </div>
          ))}
          {(!signalData?.signals || signalData.signals.length === 0) && (
            <div style={{ padding: 30, textAlign: 'center', color: '#475569', fontSize: 13 }}>No signals loaded yet</div>
          )}
        </Card>

        {/* Audit Log */}
        <Card title={`Audit Log — ${auditEntries.length} ENTRIES`}>
          {auditEntries.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#475569' }}>
              <div style={{ fontSize: 13 }}>Audit entries will appear here as signals are processed</div>
            </div>
          ) : (
            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
              {auditEntries.slice(0, 20).map((entry, i) => (
                <div key={i} style={{ padding: '10px 14px', borderBottom: '1px solid rgba(30,41,59,0.3)', fontSize: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>
                      {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '—'}
                    </span>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
                      background: entry.event === 'RUN_COMPLETE' ? 'rgba(52,211,153,0.15)' : 'rgba(99,102,241,0.15)',
                      color: entry.event === 'RUN_COMPLETE' ? '#34d399' : '#818cf8',
                    }}>{entry.event || 'LOG'}</span>
                  </div>
                  <div style={{ color: '#cbd5e1', fontSize: 11 }}>
                    {entry.details ? (typeof entry.details === 'string' ? entry.details : JSON.stringify(entry.details).slice(0, 120)) : '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Rules Summary */}
      <Card title="Active Rules" style={{ marginTop: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, padding: 14 }}>
          {[
            { label: 'Max Per Trade', value: `$${((config.max_per_trade_cents ?? 0) / 100).toFixed(2)}`, icon: '💰' },
            { label: 'Max Daily Spend', value: `$${((config.max_daily_spend_cents ?? 0) / 100).toFixed(2)}`, icon: '📅' },
            { label: 'Max Weekly Spend', value: `$${((config.max_weekly_spend_cents ?? 0) / 100).toFixed(2)}`, icon: '📊' },
            { label: 'Drawdown Kill Switch', value: `${((config.drawdown_kill_switch_pct ?? 0) * 100).toFixed(0)}%`, icon: '🛑' },
            { label: 'Min ARS Score', value: config.min_ars_score ?? '—', icon: '📈' },
            { label: 'Consecutive Loss Limit', value: config.consecutive_loss_limit ?? '—', icon: '🚨' },
          ].map((rule, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px',
              background: 'rgba(15,23,42,0.5)', borderRadius: 6, border: '1px solid rgba(30,41,59,0.5)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>{rule.icon}</span>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>{rule.label}</span>
              </div>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', fontFamily: 'monospace' }}>{rule.value}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ============================================
// SIGNALS PAGE
// ============================================
function SignalsPage({ data, loading, onRefresh }) {
  const [expanded, setExpanded] = useState(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('ars_score');

  const signals = useMemo(() => {
    let r = [...(data?.signals || [])];
    if (search) { const q = search.toLowerCase(); r = r.filter(s => s.market_title?.toLowerCase().includes(q)); }
    r.sort((a, b) => { if (sortBy === 'ars_score') return b.ars_score - a.ars_score; if (sortBy === 'edge') return b.expected_edge - a.expected_edge; return b.total_size - a.total_size; });
    return r;
  }, [data?.signals, search, sortBy]);

  return (
    <div>
      <PageHeader title="Trading Signals" subtitle="ARS-powered signals from Polymarket smart money">
        <button onClick={() => onRefresh(true)} style={{
          background: 'transparent', border: '1px solid #1e293b', color: '#94a3b8',
          padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12, display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <RefreshCw size={14} /> Refresh
        </button>
      </PageHeader>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={16} style={{ position: 'absolute', left: 12, top: 10, color: '#475569' }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search markets..." style={{
            width: '100%', padding: '8px 12px 8px 36px', background: '#0f172a', border: '1px solid #1e293b',
            borderRadius: 6, color: '#e2e8f0', fontSize: 13, outline: 'none',
          }} />
        </div>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{
          padding: '8px 12px', background: '#0f172a', border: '1px solid #1e293b', borderRadius: 6, color: '#94a3b8', fontSize: 12,
        }}>
          <option value="ars_score">Sort: ARS Score</option>
          <option value="edge">Sort: Edge</option>
          <option value="total_size">Sort: Size</option>
        </select>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#475569' }}><Loader2 size={30} style={{ animation: 'spin 1s linear infinite' }} /><p>Loading signals...</p></div>
      ) : signals.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#475569' }}>No signals found</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {signals.map((s, i) => {
            const ec = entryConfig(s.entry_quality);
            const isExpanded = expanded === (s.id || i);
            return (
              <div key={s.id || i} onClick={() => setExpanded(isExpanded ? null : (s.id || i))} style={{
                background: 'rgba(15,23,42,0.6)', border: '1px solid #1e293b', borderRadius: 10, padding: '16px 18px', cursor: 'pointer',
                borderColor: isExpanded ? '#6366f1' : '#1e293b',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: s.direction?.toLowerCase() === 'yes' ? 'rgba(52,211,153,0.2)' : 'rgba(239,68,68,0.2)', color: s.direction?.toLowerCase() === 'yes' ? '#34d399' : '#f87171' }}>
                        {(s.direction || '').toUpperCase()}
                      </span>
                      <span style={{ fontSize: 11, padding: '2px 6px', borderRadius: 4, background: ec.bg, color: ec.color, fontWeight: 600 }}>{ec.label}</span>
                      {s.category && <span style={{ fontSize: 10, color: '#64748b', background: 'rgba(100,116,139,0.15)', padding: '2px 6px', borderRadius: 4 }}>{s.category}</span>}
                    </div>
                    <div style={{ fontSize: 14, color: '#e2e8f0', fontWeight: 500, marginBottom: 6 }}>{s.market_title}</div>
                    <div style={{ fontSize: 11, color: '#64748b', display: 'flex', gap: 14 }}>
                      <span>👥 {s.num_traders} traders ({(s.conviction * 100).toFixed(0)}%)</span>
                      <span>💰 {fmt(s.total_size)}</span>
                      <span>ARS: <span style={{ color: arsColor(s.ars_score), fontWeight: 600 }}>{(s.ars_score * 100).toFixed(0)}</span></span>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 20, fontWeight: 700, color: '#f1f5f9', fontFamily: 'monospace' }}>{(s.current_price * 100).toFixed(0)}¢</div>
                    <div style={{ fontSize: 12, color: s.expected_edge > 0 ? '#34d399' : '#f87171', fontWeight: 600 }}>{fmtPct(s.expected_edge)} edge</div>
                  </div>
                </div>
                {isExpanded && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #1e293b' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 10 }}>
                      <MiniStat label="Avg Entry" value={`${(s.avg_entry_price * 100).toFixed(0)}¢`} />
                      <MiniStat label="Current" value={`${(s.current_price * 100).toFixed(0)}¢`} />
                      <MiniStat label="Rec Size" value={`${(s.recommended_size * 100).toFixed(1)}%`} />
                      <MiniStat label="Volume 24h" value={fmt(s.volume_24h || 0)} />
                    </div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>Traders: {(s.traders || []).join(', ')}</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ============================================
// TRADERS PAGE
// ============================================
function TradersPage({ data }) {
  const traders = data?.traders || [];
  return (
    <div>
      <PageHeader title="Top Traders" subtitle="Ranked by consistency score and efficiency" />
      {traders.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#475569' }}>No trader data available</div>
      ) : (
        <Card>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b' }}>
                {['Rank', 'Trader', 'PnL', 'Volume', 'Efficiency', 'Score', 'Positions'].map(h => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, color: '#64748b', fontWeight: 500, textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {traders.map((t, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.4)' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: i < 3 ? '#f59e0b' : '#94a3b8' }}>#{i + 1}</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ color: '#e2e8f0', fontWeight: 500, fontSize: 13 }}>{t.username} {t.verified && <CheckCircle size={12} style={{ display: 'inline', color: '#34d399' }} />}</div>
                    <div style={{ color: '#475569', fontSize: 11 }}>{t.wallet}</div>
                  </td>
                  <td style={{ padding: '10px 14px', color: t.pnl >= 0 ? '#34d399' : '#f87171', fontWeight: 600, fontFamily: 'monospace' }}>{fmt(t.pnl)}</td>
                  <td style={{ padding: '10px 14px', color: '#94a3b8', fontFamily: 'monospace' }}>{fmt(t.volume)}</td>
                  <td style={{ padding: '10px 14px', color: t.efficiency >= 0.1 ? '#34d399' : '#94a3b8', fontFamily: 'monospace' }}>{(t.efficiency * 100).toFixed(1)}%</td>
                  <td style={{ padding: '10px 14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ flex: 1, height: 4, background: '#1e293b', borderRadius: 2 }}>
                        <div style={{ height: '100%', width: `${t.score * 100}%`, background: '#6366f1', borderRadius: 2 }} />
                      </div>
                      <span style={{ fontSize: 12, color: '#e2e8f0', fontFamily: 'monospace' }}>{t.score?.toFixed(2)}</span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 14px', color: '#94a3b8' }}>{t.positions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ============================================
// TRANSACTIONS PAGE
// ============================================
function TransactionsPage() {
  const [fills, setFills] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { traderApi.trades().then(d => setFills(d.fills || [])).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div>
      <PageHeader title="Transactions" subtitle="Complete trade history and fill records" />
      <Card>
        {loading ? <div style={{ padding: 40, textAlign: 'center', color: '#475569' }}><Loader2 size={20} style={{ animation: 'spin 1s linear infinite' }} /></div> :
         fills.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: '#475569' }}>No transactions yet</div> : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr style={{ borderBottom: '1px solid #1e293b' }}>
              {['Time', 'Action', 'Ticker', 'Side', 'Qty', 'Price'].map(h => (
                <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, color: '#64748b', textTransform: 'uppercase' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {fills.map((f, i) => (
                <tr key={i} style={{ borderBottom: '1px solid rgba(30,41,59,0.4)' }}>
                  <td style={{ padding: '10px 14px', fontSize: 11, color: '#94a3b8', fontFamily: 'monospace' }}>{f.created_time ? new Date(f.created_time).toLocaleString() : '—'}</td>
                  <td style={{ padding: '10px 14px' }}><span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 4, background: f.action === 'buy' ? 'rgba(52,211,153,0.15)' : 'rgba(239,68,68,0.15)', color: f.action === 'buy' ? '#34d399' : '#f87171' }}>{(f.action || '').toUpperCase()}</span></td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: '#e2e8f0', fontFamily: 'monospace' }}>{f.ticker || '—'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: '#94a3b8' }}>{(f.side || '—').toUpperCase()}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: '#f1f5f9', fontFamily: 'monospace' }}>{f.count ?? f.yes_count ?? '—'}</td>
                  <td style={{ padding: '10px 14px', fontSize: 12, color: '#f1f5f9', fontFamily: 'monospace' }}>{f.yes_price ?? f.no_price ?? '—'}¢</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

// ============================================
// RULES PAGE
// ============================================
function RulesPage({ liveData }) {
  const config = liveData?.governance?.config ?? {};
  const rules = [
    { name: 'Max Per Trade', desc: 'Maximum spend on any single trade', value: `$${((config.max_per_trade_cents ?? 500) / 100).toFixed(2)}`, status: 'active' },
    { name: 'Max Daily Spend', desc: 'Total allowed spend per calendar day', value: `$${((config.max_daily_spend_cents ?? 1000) / 100).toFixed(2)}`, status: 'active' },
    { name: 'Max Weekly Spend', desc: 'Total allowed spend per 7-day window', value: `$${((config.max_weekly_spend_cents ?? 2500) / 100).toFixed(2)}`, status: 'active' },
    { name: 'Drawdown Kill Switch', desc: 'Auto-kill if portfolio drops by this %', value: `${((config.drawdown_kill_switch_pct ?? 0.2) * 100).toFixed(0)}%`, status: 'active' },
    { name: 'Min ARS Score', desc: 'Minimum signal quality to approve', value: `${config.min_ars_score ?? 0.3}`, status: 'active' },
    { name: 'Consecutive Loss Limit', desc: 'Kill switch after N losses in a row', value: `${config.consecutive_loss_limit ?? 5}`, status: 'active' },
  ];

  return (
    <div>
      <PageHeader title="Rules" subtitle="Governance rules protecting your agent's trading" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {rules.map((r, i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px',
            background: 'rgba(15,23,42,0.6)', border: '1px solid #1e293b', borderRadius: 10,
          }}>
            <div>
              <div style={{ fontSize: 14, color: '#e2e8f0', fontWeight: 500 }}>{r.name}</div>
              <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{r.desc}</div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9', fontFamily: 'monospace' }}>{r.value}</span>
              <span style={{ fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 12, background: 'rgba(52,211,153,0.15)', color: '#34d399' }}>ACTIVE</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================
// SHARED COMPONENTS
// ============================================
function PageHeader({ title, subtitle, children }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: '#f1f5f9', margin: 0 }}>{title}</h1>
        {subtitle && <p style={{ fontSize: 14, color: '#64748b', margin: '4px 0 0' }}>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function Card({ title, children, style: s }) {
  return (
    <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid #1e293b', borderRadius: 12, overflow: 'hidden', ...s }}>
      {title && <div style={{ padding: '14px 18px', borderBottom: '1px solid #1e293b', fontSize: 13, fontWeight: 600, color: '#e2e8f0' }}>{title}</div>}
      <div>{children}</div>
    </div>
  );
}

function MetricBox({ label, value, sub, icon, color = '#6366f1' }) {
  return (
    <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid #1e293b', borderRadius: 10, padding: '18px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ color, opacity: 0.8 }}>{icon}</div>
        <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color: '#f1f5f9', fontFamily: 'monospace' }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function GaugeBox({ label, value, sub, killLabel }) {
  return (
    <div style={{ background: 'rgba(15,23,42,0.6)', border: '1px solid #1e293b', borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <span style={{ fontSize: 10, color: '#64748b', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>{label}</span>
      <div style={{ width: 60, height: 60, borderRadius: '50%', border: '4px solid #1e293b', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
        <svg width="60" height="60" style={{ position: 'absolute', transform: 'rotate(-90deg)' }}>
          <circle cx="30" cy="30" r="26" fill="none" stroke="#34d399" strokeWidth="4" strokeDasharray={`${value * 1.63} 163`} />
        </svg>
        <span style={{ fontSize: 14, fontWeight: 700, color: value > 80 ? '#ef4444' : '#34d399' }}>{value.toFixed(1)}%</span>
      </div>
      <span style={{ fontSize: 10, color: '#475569', marginTop: 6 }}>{sub}</span>
      <span style={{ fontSize: 9, color: '#475569', marginTop: 2, textTransform: 'uppercase' }}>{killLabel}</span>
    </div>
  );
}

function MiniStat({ label, value }) {
  return (
    <div style={{ background: 'rgba(30,41,59,0.5)', borderRadius: 6, padding: '8px 10px', textAlign: 'center' }}>
      <div style={{ fontSize: 10, color: '#64748b', marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#f1f5f9', fontFamily: 'monospace' }}>{value}</div>
    </div>
  );
}

function StatusPill({ connected }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
      background: connected ? 'rgba(52,211,153,0.15)' : 'rgba(239,68,68,0.15)',
      color: connected ? '#34d399' : '#f87171', border: `1px solid ${connected ? 'rgba(52,211,153,0.3)' : 'rgba(239,68,68,0.3)'}`,
    }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? '#34d399' : '#ef4444' }} />
      {connected ? 'Connected' : 'Disconnected'}
    </div>
  );
}

function StatusRow({ label, status, sub }) {
  const colors = { connected: '#34d399', active: '#34d399', running: '#34d399', disconnected: '#ef4444', kill_switch: '#ef4444' };
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid rgba(30,41,59,0.3)' }}>
      <span style={{ fontSize: 13, color: '#94a3b8' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: colors[status] || '#f59e0b' }} />
        <span style={{ fontSize: 12, color: colors[status] || '#f59e0b', fontWeight: 500 }}>{status === 'kill_switch' ? 'KILL SWITCH' : status.charAt(0).toUpperCase() + status.slice(1)}</span>
        {sub && <span style={{ fontSize: 10, color: '#475569' }}>({sub})</span>}
      </div>
    </div>
  );
}

function QuickAction({ label, sub, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px',
      background: 'rgba(15,23,42,0.4)', border: '1px solid #1e293b', borderRadius: 8, cursor: 'pointer', width: '100%', textAlign: 'left',
    }}>
      <div>
        <div style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: 11, color: '#64748b' }}>{sub}</div>
      </div>
      <ArrowRight size={16} color="#64748b" />
    </button>
  );
}

// ============================================
// MAIN APP
// ============================================
export default function AgentWalletDashboard() {
  const [page, setPage] = useState('overview');
  const [liveData, setLiveData] = useState(null);
  const [signalData, setSignalData] = useState(null);
  const [signalLoading, setSignalLoading] = useState(true);
  const [liveLoading, setLiveLoading] = useState(true);

  const fetchLiveData = useCallback(async () => {
    try { const d = await traderApi.dashboard(); setLiveData(d); } catch (e) { console.error('Live data error:', e); }
    finally { setLiveLoading(false); }
  }, []);

  const fetchSignals = useCallback(async (refresh = false) => {
    setSignalLoading(true);
    try { const d = await predictorApi.getSignals(refresh); setSignalData(d); }
    catch (e) { console.error('Signal error:', e); }
    finally { setSignalLoading(false); }
  }, []);

  useEffect(() => { fetchLiveData(); fetchSignals(); }, [fetchLiveData, fetchSignals]);
  useEffect(() => { const i = setInterval(fetchLiveData, 30000); return () => clearInterval(i); }, [fetchLiveData]);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: '#080e1a', color: '#e2e8f0', fontFamily: "'Inter', -apple-system, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; margin: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
        input, select { font-family: inherit; }
      `}</style>

      <Sidebar page={page} setPage={setPage} />

      <main style={{ flex: 1, marginLeft: 220, padding: '24px 32px', maxWidth: 1100 }}>
        {/* Top bar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginBottom: 20 }}>
          <StatusPill connected={!!liveData} />
          <button onClick={() => { fetchLiveData(); fetchSignals(); }} style={{
            background: 'transparent', border: '1px solid #1e293b', color: '#94a3b8', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 11,
          }}>
            <RefreshCw size={14} />
          </button>
          <button style={{ background: 'transparent', border: '1px solid #1e293b', color: '#94a3b8', padding: '6px 10px', borderRadius: 6, cursor: 'pointer' }}>
            <Search size={14} />
          </button>
          <button style={{ background: 'transparent', border: '1px solid #1e293b', color: '#94a3b8', padding: '6px 10px', borderRadius: 6, cursor: 'pointer', position: 'relative' }}>
            <Bell size={14} />
            <div style={{ position: 'absolute', top: -2, right: -2, width: 8, height: 8, background: '#6366f1', borderRadius: '50%' }} />
          </button>
          <button style={{
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', border: 'none', color: '#fff',
            padding: '7px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 12, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6,
          }}>
            + New Agent
          </button>
        </div>

        {page === 'overview' && <OverviewPage liveData={liveData} signalData={signalData} onNavigate={setPage} />}
        {page === 'signals' && <SignalsPage data={signalData} loading={signalLoading} onRefresh={fetchSignals} />}
        {page === 'traders' && <TradersPage data={signalData} />}
        {page === 'kalshi' && <KalshiTradingPage liveData={liveData} onRefresh={fetchLiveData} />}
        {page === 'governance' && <GovernancePage liveData={liveData} signalData={signalData} onRefresh={fetchLiveData} />}
        {page === 'transactions' && <TransactionsPage />}
        {page === 'rules' && <RulesPage liveData={liveData} />}
        {page === 'settings' && (
          <div>
            <PageHeader title="Settings" subtitle="Configuration and preferences" />
            <Card title="API Endpoints">
              <div style={{ padding: 14 }}>
                <div style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>Predictor Agent API</div>
                <div style={{ fontSize: 13, color: '#94a3b8', fontFamily: 'monospace', marginBottom: 12 }}>{PREDICTOR_API}</div>
                <div style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>Live Trader API (Cloud Run)</div>
                <div style={{ fontSize: 13, color: '#94a3b8', fontFamily: 'monospace' }}>{TRADER_API}</div>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}