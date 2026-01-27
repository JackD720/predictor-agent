import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Clock,
  RefreshCw, Filter, Search, ChevronDown, ChevronUp, ExternalLink,
  Zap, Shield, Target, BarChart3, Users, DollarSign, Activity,
  Eye, Loader2, ArrowUpRight, ArrowDownRight, Info, X, Settings,
  Play, Pause, Moon, Sun, Bell, WifiOff, Database
} from 'lucide-react';

// ============================================
// CONFIGURATION
// ============================================
// Change this to your deployed API URL
const API_BASE_URL = 'https://predictor-agent-api-164814074525.us-central1.run.app';
const USE_DEMO_DATA = false; // Set to true to force demo mode

// ============================================
// API SERVICE
// ============================================
const api = {
  async getSignals(refresh = false) {
    const url = `${API_BASE_URL}/api/signals${refresh ? '?refresh=true' : ''}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch signals');
    return response.json();
  },
  
  async getStats() {
    const response = await fetch(`${API_BASE_URL}/api/stats`);
    if (!response.ok) throw new Error('Failed to fetch stats');
    return response.json();
  },
  
  async getTraders() {
    const response = await fetch(`${API_BASE_URL}/api/traders`);
    if (!response.ok) throw new Error('Failed to fetch traders');
    return response.json();
  },
  
  async health() {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error('API not healthy');
    return response.json();
  },
  
  async refresh() {
    const response = await fetch(`${API_BASE_URL}/api/refresh`, { method: 'POST' });
    if (!response.ok) throw new Error('Failed to refresh');
    return response.json();
  }
};

// ============================================
// DEMO DATA (fallback)
// ============================================
const generateDemoSignals = () => ({
  signals: [
    {
      id: 's1',
      market_slug: 'bitcoin-above-150k-2025',
      market_title: 'Will Bitcoin be above $150,000 on December 31, 2025?',
      direction: 'Yes',
      conviction: 0.16,
      num_traders: 4,
      total_size: 892000,
      avg_entry_price: 0.35,
      current_price: 0.42,
      expected_edge: 0.20,
      traders: ['BITCOINTO500K', 'Fredi9999', 'whaletrader', 'cryptoking'],
      ars_score: 0.65,
      recommended_size: 0.025,
      entry_quality: 'fair',
      category: 'Crypto',
      end_date: '2025-12-31',
      volume_24h: 234500,
    },
    {
      id: 's2',
      market_slug: 'fed-rate-cut-march-2025',
      market_title: 'Will the Fed cut rates in March 2025?',
      direction: 'No',
      conviction: 0.12,
      num_traders: 3,
      total_size: 156000,
      avg_entry_price: 0.62,
      current_price: 0.71,
      expected_edge: 0.15,
      traders: ['macro_master', 'fedwatcher', 'bondking'],
      ars_score: 0.52,
      recommended_size: 0.018,
      entry_quality: 'fair',
      category: 'Economics',
      end_date: '2025-03-20',
      volume_24h: 87600,
    },
  ],
  traders: [
    { rank: 1, username: 'BITCOINTO500K', wallet: '0xa0f2...', pnl: 892450, volume: 7250000, efficiency: 0.123, score: 0.87, positions: 34, verified: true },
    { rank: 2, username: 'Fredi9999', wallet: '0x8b3f...', pnl: 654200, volume: 6680000, efficiency: 0.098, score: 0.82, positions: 28, verified: true },
  ],
  stats: {
    total_signals: 2,
    actionable_signals: 2,
    avg_ars_score: 0.58,
    total_position_size: 1048000,
    traders_analyzed: 2,
    last_updated: new Date().toISOString()
  }
});

// ============================================
// UTILITY FUNCTIONS
// ============================================
const formatNumber = (num, decimals = 0) => {
  if (num >= 1000000) return `$${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`;
  return `$${num.toFixed(decimals)}`;
};

const formatPercent = (num) => {
  const sign = num >= 0 ? '+' : '';
  return `${sign}${(num * 100).toFixed(0)}%`;
};

const getEntryQualityConfig = (quality) => {
  const configs = {
    good: { color: 'text-emerald-400', bg: 'bg-emerald-500/20', border: 'border-emerald-500/30', label: 'GOOD ENTRY' },
    fair: { color: 'text-amber-400', bg: 'bg-amber-500/20', border: 'border-amber-500/30', label: 'FAIR ENTRY' },
    late: { color: 'text-orange-400', bg: 'bg-orange-500/20', border: 'border-orange-500/30', label: 'LATE ENTRY' },
    very_late: { color: 'text-red-400', bg: 'bg-red-500/20', border: 'border-red-500/30', label: 'TOO LATE' },
  };
  return configs[quality] || configs.fair;
};

const getARSScoreColor = (score) => {
  if (score >= 0.6) return 'text-emerald-400';
  if (score >= 0.4) return 'text-amber-400';
  return 'text-red-400';
};

// ============================================
// COMPONENTS
// ============================================

// Connection Status
const ConnectionStatus = ({ connected, demoMode, loading }) => (
  <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
    loading 
      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
      : demoMode 
        ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' 
        : connected 
          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
          : 'bg-red-500/20 text-red-400 border border-red-500/30'
  }`}>
    {loading ? (
      <>
        <Loader2 size={12} className="animate-spin" />
        Loading...
      </>
    ) : demoMode ? (
      <>
        <Database size={12} />
        Demo Mode
      </>
    ) : connected ? (
      <>
        <Zap size={12} />
        Live Data
      </>
    ) : (
      <>
        <WifiOff size={12} />
        Disconnected
      </>
    )}
  </div>
);

// ARS Score Gauge
const ARSGauge = ({ score, size = 'md' }) => {
  const circumference = 2 * Math.PI * 36;
  const progress = score * circumference;
  const sizeClasses = {
    sm: 'w-16 h-16',
    md: 'w-24 h-24',
    lg: 'w-32 h-32',
  };

  return (
    <div className={`relative ${sizeClasses[size]}`}>
      <svg className="w-full h-full transform -rotate-90">
        <circle cx="50%" cy="50%" r="36" fill="none" stroke="currentColor" strokeWidth="6" className="text-slate-700" />
        <circle
          cx="50%" cy="50%" r="36" fill="none" stroke="currentColor" strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={circumference - progress}
          strokeLinecap="round" className={getARSScoreColor(score)}
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center flex-col">
        <span className={`text-xl font-bold ${getARSScoreColor(score)}`}>{(score * 100).toFixed(0)}</span>
        <span className="text-[10px] text-slate-500 uppercase tracking-wider">ARS</span>
      </div>
    </div>
  );
};

// Signal Card
const SignalCard = ({ signal, expanded, onToggle, onTrade }) => {
  const entryConfig = getEntryQualityConfig(signal.entry_quality);
  const isPositiveEdge = signal.expected_edge > 0;

  return (
    <div className={`signal-card ${expanded ? 'expanded' : ''}`}>
      <div className="signal-card-header" onClick={onToggle}>
        <div className="flex items-start gap-4 flex-1">
          <ARSGauge score={signal.ars_score} size="sm" />
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`direction-badge ${signal.direction.toLowerCase()}`}>
                {signal.direction.toUpperCase()}
              </span>
              <span className={`entry-badge ${entryConfig.bg} ${entryConfig.color} ${entryConfig.border}`}>
                {entryConfig.label}
              </span>
              <span className="category-badge">{signal.category}</span>
            </div>
            
            <h3 className="signal-title">{signal.market_title}</h3>
            
            <div className="signal-meta">
              <span className="meta-item">
                <Users size={12} />
                {signal.num_traders} traders ({(signal.conviction * 100).toFixed(0)}%)
              </span>
              <span className="meta-item">
                <DollarSign size={12} />
                {formatNumber(signal.total_size)} total
              </span>
            </div>
          </div>
        </div>

        <div className="signal-price-info">
          <div className="price-current">
            <span className="price-label">Current</span>
            <span className="price-value">{(signal.current_price * 100).toFixed(0)}¢</span>
          </div>
          <div className={`price-edge ${isPositiveEdge ? 'positive' : 'negative'}`}>
            {isPositiveEdge ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            {formatPercent(signal.expected_edge)}
          </div>
        </div>

        <button className="expand-toggle">
          {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
      </div>

      {expanded && (
        <div className="signal-card-details">
          <div className="details-grid">
            <div className="detail-box">
              <span className="detail-label">Avg Entry Price</span>
              <span className="detail-value">{(signal.avg_entry_price * 100).toFixed(0)}¢</span>
            </div>
            <div className="detail-box">
              <span className="detail-label">Current Price</span>
              <span className="detail-value">{(signal.current_price * 100).toFixed(0)}¢</span>
            </div>
            <div className="detail-box">
              <span className="detail-label">Recommended Size</span>
              <span className="detail-value highlight">{(signal.recommended_size * 100).toFixed(1)}%</span>
            </div>
            <div className="detail-box">
              <span className="detail-label">24h Volume</span>
              <span className="detail-value">{formatNumber(signal.volume_24h || 0)}</span>
            </div>
          </div>

          <div className="traders-section">
            <h4 className="section-title"><Users size={14} /> Supporting Traders</h4>
            <div className="traders-list">
              {signal.traders.map((trader, i) => (
                <span key={i} className="trader-tag">
                  {trader.length > 15 ? `${trader.slice(0, 6)}...${trader.slice(-4)}` : trader}
                </span>
              ))}
            </div>
          </div>

          <div className="signal-actions">
            <a href={`https://polymarket.com/event/${signal.market_slug}`} target="_blank" rel="noopener noreferrer" className="btn-secondary">
              <ExternalLink size={16} /> View on Polymarket
            </a>
            <button className="btn-primary" onClick={() => onTrade(signal)}>
              <Target size={16} /> Trade Signal
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Stats Card
const StatsCard = ({ icon: Icon, label, value, subValue, color = 'indigo' }) => {
  const colorClasses = {
    indigo: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    emerald: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  };

  return (
    <div className="stats-card">
      <div className={`stats-icon ${colorClasses[color]}`}><Icon size={20} /></div>
      <div className="stats-content">
        <span className="stats-value">{value}</span>
        <span className="stats-label">{label}</span>
        {subValue && <span className="stats-sub">{subValue}</span>}
      </div>
    </div>
  );
};

// Trader Row
const TraderRow = ({ trader, rank }) => (
  <tr className="trader-row">
    <td className="rank-cell">
      <span className={`rank-badge ${rank <= 3 ? 'top-3' : ''}`}>#{rank}</span>
    </td>
    <td className="trader-cell">
      <div className="trader-info">
        <span className="trader-name">
          {trader.username}
          {trader.verified && <CheckCircle size={12} className="verified-icon" />}
        </span>
        <span className="trader-wallet">{trader.wallet}</span>
      </div>
    </td>
    <td className="pnl-cell">
      <span className={trader.pnl >= 0 ? 'positive' : 'negative'}>{formatNumber(trader.pnl)}</span>
    </td>
    <td className="volume-cell">{formatNumber(trader.volume)}</td>
    <td className="efficiency-cell">
      <span className={trader.efficiency >= 0.1 ? 'high' : ''}>{(trader.efficiency * 100).toFixed(1)}%</span>
    </td>
    <td className="score-cell">
      <div className="score-bar-container">
        <div className="score-bar" style={{ width: `${trader.score * 100}%` }} />
        <span className="score-value">{trader.score.toFixed(2)}</span>
      </div>
    </td>
    <td className="positions-cell">{trader.positions}</td>
  </tr>
);

// Filter Dropdown
const FilterDropdown = ({ label, options, value, onChange }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="filter-dropdown">
      <button className="filter-trigger" onClick={() => setOpen(!open)}>
        <span>{label}: {value || 'All'}</span>
        <ChevronDown size={14} className={open ? 'rotate-180' : ''} />
      </button>
      {open && (
        <div className="filter-menu">
          <button onClick={() => { onChange(null); setOpen(false); }}>All</button>
          {options.map(opt => (
            <button key={opt} onClick={() => { onChange(opt); setOpen(false); }}>{opt}</button>
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================
// MAIN APP
// ============================================
export default function PredictorAgentDashboard() {
  const [data, setData] = useState({ signals: [], traders: [], stats: null });
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [demoMode, setDemoMode] = useState(USE_DEMO_DATA);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('signals');
  const [expandedSignal, setExpandedSignal] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  // Filters
  const [entryFilter, setEntryFilter] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState(null);
  const [directionFilter, setDirectionFilter] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('ars_score');

  // Load data
  const loadData = useCallback(async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    
    if (demoMode || USE_DEMO_DATA) {
      await new Promise(r => setTimeout(r, 500));
      const demo = generateDemoSignals();
      setData(demo);
      setLastUpdated(new Date());
      setLoading(false);
      return;
    }
    
    try {
      const response = await api.getSignals(forceRefresh);
      setData(response);
      setConnected(true);
      setLastUpdated(new Date(response.stats?.last_updated || Date.now()));
    } catch (err) {
      console.error('Failed to fetch:', err);
      setError(err.message);
      setConnected(false);
      // Fallback to demo
      const demo = generateDemoSignals();
      setData(demo);
      setDemoMode(true);
    } finally {
      setLoading(false);
    }
  }, [demoMode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => loadData(false), 60000);
    return () => clearInterval(interval);
  }, [autoRefresh, loadData]);

  // Filter signals
  const filteredSignals = useMemo(() => {
    let result = [...(data.signals || [])];
    if (entryFilter) result = result.filter(s => s.entry_quality === entryFilter);
    if (categoryFilter) result = result.filter(s => s.category === categoryFilter);
    if (directionFilter) result = result.filter(s => s.direction === directionFilter);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s => s.market_title.toLowerCase().includes(q) || s.traders.some(t => t.toLowerCase().includes(q)));
    }
    result.sort((a, b) => {
      switch (sortBy) {
        case 'ars_score': return b.ars_score - a.ars_score;
        case 'conviction': return b.conviction - a.conviction;
        case 'total_size': return b.total_size - a.total_size;
        case 'edge': return b.expected_edge - a.expected_edge;
        default: return 0;
      }
    });
    return result;
  }, [data.signals, entryFilter, categoryFilter, directionFilter, searchQuery, sortBy]);

  const categories = useMemo(() => [...new Set((data.signals || []).map(s => s.category))], [data.signals]);
  const stats = data.stats || { total_signals: 0, actionable_signals: 0, avg_ars_score: 0, total_position_size: 0, traders_analyzed: 0 };

  const handleTrade = (signal) => {
    window.open(`https://polymarket.com/event/${signal.market_slug}`, '_blank');
  };

  const toggleDemoMode = () => {
    setDemoMode(!demoMode);
  };

  return (
    <div className="predictor-app">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-icon"><BarChart3 size={24} /></div>
            <div className="logo-text">
              <span className="logo-title">Predictor Agent</span>
              <span className="logo-subtitle">ARS-Powered Trading Signals</span>
            </div>
          </div>
        </div>

        <div className="header-center">
          <nav className="main-nav">
            <button className={`nav-btn ${activeTab === 'signals' ? 'active' : ''}`} onClick={() => setActiveTab('signals')}>
              <Target size={18} /> Signals
            </button>
            <button className={`nav-btn ${activeTab === 'traders' ? 'active' : ''}`} onClick={() => setActiveTab('traders')}>
              <Users size={18} /> Top Traders
            </button>
            <button className={`nav-btn ${activeTab === 'analytics' ? 'active' : ''}`} onClick={() => setActiveTab('analytics')}>
              <Activity size={18} /> Analytics
            </button>
          </nav>
        </div>

        <div className="header-right">
          <ConnectionStatus connected={connected} demoMode={demoMode} loading={loading} />
          <button className={`auto-refresh-btn ${autoRefresh ? 'active' : ''}`} onClick={() => setAutoRefresh(!autoRefresh)} title="Toggle auto-refresh">
            {autoRefresh ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button className="refresh-btn" onClick={() => loadData(true)} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button className="settings-btn" onClick={toggleDemoMode} title="Toggle demo mode">
            <Database size={18} />
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="app-main">
        {/* Stats */}
        <div className="stats-bar">
          <StatsCard icon={Target} label="Total Signals" value={stats.total_signals} color="indigo" />
          <StatsCard icon={Zap} label="Actionable" value={stats.actionable_signals} subValue="Good/Fair entry" color="emerald" />
          <StatsCard icon={Shield} label="Avg ARS Score" value={(stats.avg_ars_score * 100).toFixed(0)} color="amber" />
          <StatsCard icon={DollarSign} label="Total Position Size" value={formatNumber(stats.total_position_size)} color="indigo" />
          <StatsCard icon={Users} label="Traders Analyzed" value={stats.traders_analyzed} color="emerald" />
        </div>

        {/* Last Updated */}
        <div className="update-bar">
          <span className="update-text">
            {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading...'}
            {demoMode && ' (Demo Data)'}
          </span>
          {autoRefresh && <span className="auto-refresh-indicator"><span className="pulse-dot" /> Auto-refreshing</span>}
        </div>

        {/* Error Banner */}
        {error && (
          <div className="error-banner">
            <AlertTriangle size={16} />
            <span>Failed to connect to API: {error}. Using demo data.</span>
            <button onClick={() => setError(null)}><X size={14} /></button>
          </div>
        )}

        {/* Signals Tab */}
        {activeTab === 'signals' && (
          <div className="signals-view">
            <div className="filters-bar">
              <div className="search-box">
                <Search size={16} />
                <input type="text" placeholder="Search markets or traders..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
                {searchQuery && <button className="clear-search" onClick={() => setSearchQuery('')}><X size={14} /></button>}
              </div>
              <div className="filter-group">
                <FilterDropdown label="Entry Quality" options={['good', 'fair', 'late']} value={entryFilter} onChange={setEntryFilter} />
                <FilterDropdown label="Category" options={categories} value={categoryFilter} onChange={setCategoryFilter} />
                <FilterDropdown label="Direction" options={['Yes', 'No']} value={directionFilter} onChange={setDirectionFilter} />
              </div>
              <div className="sort-group">
                <label>Sort by:</label>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                  <option value="ars_score">ARS Score</option>
                  <option value="conviction">Conviction</option>
                  <option value="total_size">Position Size</option>
                  <option value="edge">Expected Edge</option>
                </select>
              </div>
            </div>

            {loading ? (
              <div className="loading-state"><Loader2 size={40} className="animate-spin" /><p>Fetching signals from Polymarket...</p></div>
            ) : filteredSignals.length === 0 ? (
              <div className="empty-state"><AlertTriangle size={48} /><h3>No signals found</h3><p>Try adjusting filters or refresh</p></div>
            ) : (
              <div className="signals-list">
                <div className="signals-header">
                  <h2>📋 Signals ({filteredSignals.length})</h2>
                  <span className="signals-count">Showing {filteredSignals.length} of {data.signals?.length || 0}</span>
                </div>
                {filteredSignals.map(signal => (
                  <SignalCard key={signal.id} signal={signal} expanded={expandedSignal === signal.id}
                    onToggle={() => setExpandedSignal(expandedSignal === signal.id ? null : signal.id)} onTrade={handleTrade} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Traders Tab */}
        {activeTab === 'traders' && (
          <div className="traders-view">
            <div className="traders-header">
              <h2>🎯 Top Traders by Consistency Score</h2>
              <p>Ranked by efficiency and long-term performance</p>
            </div>
            <div className="traders-table-container">
              <table className="traders-table">
                <thead>
                  <tr><th>Rank</th><th>Trader</th><th>Total PnL</th><th>Volume</th><th>Efficiency</th><th>Score</th><th>Positions</th></tr>
                </thead>
                <tbody>
                  {(data.traders || []).map((trader, i) => <TraderRow key={trader.wallet} trader={trader} rank={i + 1} />)}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="analytics-view">
            <div className="analytics-header"><h2>📊 Analytics</h2><p>Signal distribution and insights</p></div>
            <div className="analytics-grid">
              <div className="analytics-card">
                <h3>Entry Quality Distribution</h3>
                <div className="quality-bars">
                  {['good', 'fair', 'late', 'very_late'].map(quality => {
                    const count = (data.signals || []).filter(s => s.entry_quality === quality).length;
                    const percent = data.signals?.length ? (count / data.signals.length) * 100 : 0;
                    const config = getEntryQualityConfig(quality);
                    return (
                      <div key={quality} className="quality-bar-row">
                        <span className={`quality-label ${config.color}`}>{quality.toUpperCase()}</span>
                        <div className="quality-bar-track"><div className={`quality-bar-fill ${config.bg}`} style={{ width: `${percent}%` }} /></div>
                        <span className="quality-count">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              <div className="analytics-card">
                <h3>Signals by Category</h3>
                <div className="category-list">
                  {categories.map(cat => {
                    const count = (data.signals || []).filter(s => s.category === cat).length;
                    const totalSize = (data.signals || []).filter(s => s.category === cat).reduce((sum, s) => sum + s.total_size, 0);
                    return (
                      <div key={cat} className="category-row">
                        <span className="category-name">{cat}</span>
                        <span className="category-stats">{count} signals • {formatNumber(totalSize)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-left"><span>Predictor Agent v1.0</span><span className="divider">•</span><span>Powered by ARS</span></div>
        <div className="footer-right">
          <a href="https://polymarket.com" target="_blank" rel="noopener noreferrer">Data from Polymarket</a>
          <span className="divider">•</span><span>Not financial advice</span>
        </div>
      </footer>

      <style>{`
        .error-banner {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 8px;
          margin-bottom: 16px;
          color: #f87171;
          font-size: 0.875rem;
        }
        .error-banner button {
          margin-left: auto;
          background: none;
          border: none;
          color: inherit;
          cursor: pointer;
          padding: 4px;
        }
      `}</style>
    </div>
  );
}
