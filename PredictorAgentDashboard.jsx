import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle, Clock,
  RefreshCw, Filter, Search, ChevronDown, ChevronUp, ExternalLink,
  Zap, Shield, Target, BarChart3, Users, DollarSign, Activity,
  Eye, Loader2, ArrowUpRight, ArrowDownRight, Info, X, Settings,
  Play, Pause, Moon, Sun, Bell
} from 'lucide-react';

// ============================================
// DEMO DATA - Simulates the Python signal generator output
// ============================================
const generateDemoSignals = () => [
  {
    id: 's1',
    market_slug: 'will-jd-vance-win-2028-presidential-election',
    market_title: 'Will JD Vance win the 2028 US Presidential Election?',
    direction: 'Yes',
    conviction: 0.08,
    num_traders: 2,
    total_size: 266270,
    avg_entry_price: 0.50,
    current_price: 0.27,
    expected_edge: -0.47,
    traders: ['BITCOINTO500K', '0xa0f21e6d351baa9185716b5c00c2925ed9621848'],
    ars_score: 0.37,
    recommended_size: 0.012,
    entry_quality: 'good',
    category: 'Politics',
    end_date: '2028-11-05',
    volume_24h: 45230,
  },
  {
    id: 's2',
    market_slug: 'will-trump-nominate-kevin-hassett-fed-chair',
    market_title: 'Will Trump nominate Kevin Hassett as the next Fed chair?',
    direction: 'Yes',
    conviction: 0.08,
    num_traders: 2,
    total_size: 4351,
    avg_entry_price: 0.40,
    current_price: 0.06,
    expected_edge: -0.84,
    traders: ['botbot', 'Brunoruno'],
    ars_score: 0.37,
    recommended_size: 0.012,
    entry_quality: 'good',
    category: 'Politics',
    end_date: '2025-06-01',
    volume_24h: 12450,
  },
  {
    id: 's3',
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
    id: 's4',
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
  {
    id: 's5',
    market_slug: 'openai-gpt5-release-2025',
    market_title: 'Will OpenAI release GPT-5 before July 2025?',
    direction: 'Yes',
    conviction: 0.20,
    num_traders: 5,
    total_size: 423000,
    avg_entry_price: 0.28,
    current_price: 0.45,
    expected_edge: 0.61,
    traders: ['aimaxi', 'techbull', 'futurist99', 'gpt_believer', 'silicon_whale'],
    ars_score: 0.41,
    recommended_size: 0.015,
    entry_quality: 'late',
    category: 'Tech',
    end_date: '2025-07-01',
    volume_24h: 156700,
  },
  {
    id: 's6',
    market_slug: 'democrats-win-2026-house',
    market_title: 'Will Democrats win the House in 2026 midterms?',
    direction: 'Yes',
    conviction: 0.12,
    num_traders: 3,
    total_size: 234500,
    avg_entry_price: 0.38,
    current_price: 0.41,
    expected_edge: 0.08,
    traders: ['pollster_pro', 'election_expert', 'bluewave'],
    ars_score: 0.58,
    recommended_size: 0.022,
    entry_quality: 'good',
    category: 'Politics',
    end_date: '2026-11-03',
    volume_24h: 67800,
  },
  {
    id: 's7',
    market_slug: 'tesla-stock-above-500-2025',
    market_title: 'Will Tesla stock close above $500 in 2025?',
    direction: 'No',
    conviction: 0.08,
    num_traders: 2,
    total_size: 89000,
    avg_entry_price: 0.55,
    current_price: 0.48,
    expected_edge: -0.13,
    traders: ['stockbear', 'value_investor'],
    ars_score: 0.33,
    recommended_size: 0.010,
    entry_quality: 'fair',
    category: 'Stocks',
    end_date: '2025-12-31',
    volume_24h: 45600,
  },
  {
    id: 's8',
    market_slug: 'ethereum-eth-etf-inflows-10b',
    market_title: 'Will Ethereum ETF see $10B+ inflows in first year?',
    direction: 'Yes',
    conviction: 0.16,
    num_traders: 4,
    total_size: 312000,
    avg_entry_price: 0.22,
    current_price: 0.31,
    expected_edge: 0.41,
    traders: ['ethmaxi', 'etf_tracker', 'institutional', 'defi_whale'],
    ars_score: 0.55,
    recommended_size: 0.020,
    entry_quality: 'fair',
    category: 'Crypto',
    end_date: '2025-07-23',
    volume_24h: 123400,
  },
];

const generateDemoTraders = () => [
  { rank: 1, username: 'BITCOINTO500K', wallet: '0xa0f21e6d...', pnl: 892450, volume: 7250000, efficiency: 0.123, score: 0.87, positions: 34, verified: true },
  { rank: 2, username: 'Fredi9999', wallet: '0x8b3f2c1a...', pnl: 654200, volume: 6680000, efficiency: 0.098, score: 0.82, positions: 28, verified: true },
  { rank: 3, username: 'whaletrader', wallet: '0x1d4e5f6a...', pnl: 523100, volume: 5120000, efficiency: 0.102, score: 0.79, positions: 41, verified: false },
  { rank: 4, username: 'cryptoking', wallet: '0x7c8b9d0e...', pnl: 445600, volume: 4890000, efficiency: 0.091, score: 0.75, positions: 22, verified: true },
  { rank: 5, username: 'macro_master', wallet: '0x2e3f4a5b...', pnl: 389200, volume: 3980000, efficiency: 0.098, score: 0.73, positions: 19, verified: false },
  { rank: 6, username: 'aimaxi', wallet: '0x6d7e8f9a...', pnl: 312400, volume: 3450000, efficiency: 0.091, score: 0.70, positions: 31, verified: true },
  { rank: 7, username: 'pollster_pro', wallet: '0x9a0b1c2d...', pnl: 278900, volume: 2890000, efficiency: 0.097, score: 0.68, positions: 15, verified: false },
  { rank: 8, username: 'techbull', wallet: '0x3e4f5a6b...', pnl: 234500, volume: 2670000, efficiency: 0.088, score: 0.65, positions: 26, verified: false },
];

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
        <circle
          cx="50%"
          cy="50%"
          r="36"
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          className="text-slate-700"
        />
        <circle
          cx="50%"
          cy="50%"
          r="36"
          fill="none"
          stroke="currentColor"
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className={getARSScoreColor(score)}
          style={{ transition: 'stroke-dashoffset 0.5s ease' }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center flex-col">
        <span className={`text-xl font-bold ${getARSScoreColor(score)}`}>
          {(score * 100).toFixed(0)}
        </span>
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
      {/* Header */}
      <div className="signal-card-header" onClick={onToggle}>
        <div className="flex items-start gap-4 flex-1">
          <ARSGauge score={signal.ars_score} size="sm" />
          
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
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
              <span className="meta-item">
                <Clock size={12} />
                Ends {new Date(signal.end_date).toLocaleDateString()}
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

      {/* Expanded Details */}
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
              <span className="detail-value">{formatNumber(signal.volume_24h)}</span>
            </div>
          </div>

          <div className="traders-section">
            <h4 className="section-title">
              <Users size={14} />
              Supporting Traders
            </h4>
            <div className="traders-list">
              {signal.traders.map((trader, i) => (
                <span key={i} className="trader-tag">
                  {trader.length > 15 ? `${trader.slice(0, 6)}...${trader.slice(-4)}` : trader}
                </span>
              ))}
            </div>
          </div>

          <div className="signal-actions">
            <a 
              href={`https://polymarket.com/event/${signal.market_slug}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-secondary"
            >
              <ExternalLink size={16} />
              View on Polymarket
            </a>
            <button className="btn-primary" onClick={() => onTrade(signal)}>
              <Target size={16} />
              Trade Signal
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Stats Card
const StatsCard = ({ icon: Icon, label, value, subValue, trend, color = 'indigo' }) => {
  const colorClasses = {
    indigo: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    emerald: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    amber: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  return (
    <div className="stats-card">
      <div className={`stats-icon ${colorClasses[color]}`}>
        <Icon size={20} />
      </div>
      <div className="stats-content">
        <span className="stats-value">{value}</span>
        <span className="stats-label">{label}</span>
        {subValue && <span className="stats-sub">{subValue}</span>}
      </div>
      {trend !== undefined && (
        <div className={`stats-trend ${trend >= 0 ? 'positive' : 'negative'}`}>
          {trend >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          {Math.abs(trend)}%
        </div>
      )}
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
      <span className={trader.pnl >= 0 ? 'positive' : 'negative'}>
        {formatNumber(trader.pnl)}
      </span>
    </td>
    <td className="volume-cell">{formatNumber(trader.volume)}</td>
    <td className="efficiency-cell">
      <span className={trader.efficiency >= 0.1 ? 'high' : ''}>
        {(trader.efficiency * 100).toFixed(1)}%
      </span>
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
            <button key={opt} onClick={() => { onChange(opt); setOpen(false); }}>
              {opt}
            </button>
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
  const [signals, setSignals] = useState([]);
  const [traders, setTraders] = useState([]);
  const [loading, setLoading] = useState(true);
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
  const loadData = useCallback(async () => {
    setLoading(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 800));
    setSignals(generateDemoSignals());
    setTraders(generateDemoTraders());
    setLastUpdated(new Date());
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(loadData, 30000); // 30 seconds
    return () => clearInterval(interval);
  }, [autoRefresh, loadData]);

  // Filter and sort signals
  const filteredSignals = useMemo(() => {
    let result = [...signals];

    if (entryFilter) {
      result = result.filter(s => s.entry_quality === entryFilter);
    }
    if (categoryFilter) {
      result = result.filter(s => s.category === categoryFilter);
    }
    if (directionFilter) {
      result = result.filter(s => s.direction === directionFilter);
    }
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(s => 
        s.market_title.toLowerCase().includes(query) ||
        s.traders.some(t => t.toLowerCase().includes(query))
      );
    }

    // Sort
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
  }, [signals, entryFilter, categoryFilter, directionFilter, searchQuery, sortBy]);

  // Actionable signals (good/fair entry only)
  const actionableSignals = useMemo(() => 
    filteredSignals.filter(s => ['good', 'fair'].includes(s.entry_quality)),
    [filteredSignals]
  );

  // Stats
  const stats = useMemo(() => ({
    totalSignals: signals.length,
    actionableSignals: signals.filter(s => ['good', 'fair'].includes(s.entry_quality)).length,
    avgARSScore: signals.length ? (signals.reduce((sum, s) => sum + s.ars_score, 0) / signals.length) : 0,
    totalVolume: signals.reduce((sum, s) => sum + s.total_size, 0),
    tradersAnalyzed: traders.length,
  }), [signals, traders]);

  // Categories for filters
  const categories = useMemo(() => [...new Set(signals.map(s => s.category))], [signals]);

  const handleTrade = (signal) => {
    // In production, this would open a trading modal or redirect to Polymarket
    window.open(`https://polymarket.com/event/${signal.market_slug}`, '_blank');
  };

  return (
    <div className="predictor-app">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-icon">
              <BarChart3 size={24} />
            </div>
            <div className="logo-text">
              <span className="logo-title">Predictor Agent</span>
              <span className="logo-subtitle">ARS-Powered Trading Signals</span>
            </div>
          </div>
        </div>

        <div className="header-center">
          <nav className="main-nav">
            <button 
              className={`nav-btn ${activeTab === 'signals' ? 'active' : ''}`}
              onClick={() => setActiveTab('signals')}
            >
              <Target size={18} />
              Signals
            </button>
            <button 
              className={`nav-btn ${activeTab === 'traders' ? 'active' : ''}`}
              onClick={() => setActiveTab('traders')}
            >
              <Users size={18} />
              Top Traders
            </button>
            <button 
              className={`nav-btn ${activeTab === 'analytics' ? 'active' : ''}`}
              onClick={() => setActiveTab('analytics')}
            >
              <Activity size={18} />
              Analytics
            </button>
          </nav>
        </div>

        <div className="header-right">
          <button 
            className={`auto-refresh-btn ${autoRefresh ? 'active' : ''}`}
            onClick={() => setAutoRefresh(!autoRefresh)}
            title={autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          >
            {autoRefresh ? <Pause size={16} /> : <Play size={16} />}
          </button>
          <button className="refresh-btn" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
          <button className="settings-btn">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Stats Bar */}
        <div className="stats-bar">
          <StatsCard 
            icon={Target} 
            label="Total Signals" 
            value={stats.totalSignals}
            color="indigo"
          />
          <StatsCard 
            icon={Zap} 
            label="Actionable" 
            value={stats.actionableSignals}
            subValue="Good/Fair entry"
            color="emerald"
          />
          <StatsCard 
            icon={Shield} 
            label="Avg ARS Score" 
            value={(stats.avgARSScore * 100).toFixed(0)}
            color="amber"
          />
          <StatsCard 
            icon={DollarSign} 
            label="Total Position Size" 
            value={formatNumber(stats.totalVolume)}
            color="indigo"
          />
          <StatsCard 
            icon={Users} 
            label="Traders Analyzed" 
            value={stats.tradersAnalyzed}
            color="emerald"
          />
        </div>

        {/* Last Updated */}
        <div className="update-bar">
          <span className="update-text">
            {lastUpdated ? (
              <>Last updated: {lastUpdated.toLocaleTimeString()}</>
            ) : (
              'Loading...'
            )}
          </span>
          {autoRefresh && (
            <span className="auto-refresh-indicator">
              <span className="pulse-dot" />
              Auto-refreshing every 30s
            </span>
          )}
        </div>

        {/* Signals Tab */}
        {activeTab === 'signals' && (
          <div className="signals-view">
            {/* Filters */}
            <div className="filters-bar">
              <div className="search-box">
                <Search size={16} />
                <input 
                  type="text"
                  placeholder="Search markets or traders..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                {searchQuery && (
                  <button className="clear-search" onClick={() => setSearchQuery('')}>
                    <X size={14} />
                  </button>
                )}
              </div>

              <div className="filter-group">
                <FilterDropdown 
                  label="Entry Quality"
                  options={['good', 'fair', 'late']}
                  value={entryFilter}
                  onChange={setEntryFilter}
                />
                <FilterDropdown 
                  label="Category"
                  options={categories}
                  value={categoryFilter}
                  onChange={setCategoryFilter}
                />
                <FilterDropdown 
                  label="Direction"
                  options={['Yes', 'No']}
                  value={directionFilter}
                  onChange={setDirectionFilter}
                />
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

            {/* Signals List */}
            {loading ? (
              <div className="loading-state">
                <Loader2 size={40} className="animate-spin" />
                <p>Analyzing trader positions...</p>
              </div>
            ) : filteredSignals.length === 0 ? (
              <div className="empty-state">
                <AlertTriangle size={48} />
                <h3>No signals found</h3>
                <p>Try adjusting your filters or check back later</p>
              </div>
            ) : (
              <div className="signals-list">
                <div className="signals-header">
                  <h2>
                    {entryFilter === 'good' || entryFilter === 'fair' || !entryFilter 
                      ? `📋 Actionable Signals (${actionableSignals.length})`
                      : `📊 All Signals (${filteredSignals.length})`
                    }
                  </h2>
                  <span className="signals-count">
                    Showing {filteredSignals.length} of {signals.length}
                  </span>
                </div>

                {filteredSignals.map(signal => (
                  <SignalCard
                    key={signal.id}
                    signal={signal}
                    expanded={expandedSignal === signal.id}
                    onToggle={() => setExpandedSignal(
                      expandedSignal === signal.id ? null : signal.id
                    )}
                    onTrade={handleTrade}
                  />
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
              <p>Ranked by efficiency and long-term performance, not just raw PnL</p>
            </div>

            <div className="traders-table-container">
              <table className="traders-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Trader</th>
                    <th>Total PnL</th>
                    <th>Volume</th>
                    <th>Efficiency</th>
                    <th>Score</th>
                    <th>Positions</th>
                  </tr>
                </thead>
                <tbody>
                  {traders.map((trader, index) => (
                    <TraderRow key={trader.wallet} trader={trader} rank={index + 1} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div className="analytics-view">
            <div className="analytics-header">
              <h2>📊 ARS Analytics</h2>
              <p>Performance metrics and market insights</p>
            </div>

            <div className="analytics-grid">
              <div className="analytics-card">
                <h3>Entry Quality Distribution</h3>
                <div className="quality-bars">
                  {['good', 'fair', 'late', 'very_late'].map(quality => {
                    const count = signals.filter(s => s.entry_quality === quality).length;
                    const percent = signals.length ? (count / signals.length) * 100 : 0;
                    const config = getEntryQualityConfig(quality);
                    return (
                      <div key={quality} className="quality-bar-row">
                        <span className={`quality-label ${config.color}`}>{quality.toUpperCase()}</span>
                        <div className="quality-bar-track">
                          <div 
                            className={`quality-bar-fill ${config.bg}`} 
                            style={{ width: `${percent}%` }}
                          />
                        </div>
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
                    const count = signals.filter(s => s.category === cat).length;
                    const totalSize = signals
                      .filter(s => s.category === cat)
                      .reduce((sum, s) => sum + s.total_size, 0);
                    return (
                      <div key={cat} className="category-row">
                        <span className="category-name">{cat}</span>
                        <span className="category-stats">
                          {count} signals • {formatNumber(totalSize)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="analytics-card wide">
                <h3>ARS Score Distribution</h3>
                <div className="score-histogram">
                  {[...Array(10)].map((_, i) => {
                    const min = i * 0.1;
                    const max = (i + 1) * 0.1;
                    const count = signals.filter(s => s.ars_score >= min && s.ars_score < max).length;
                    const height = signals.length ? (count / signals.length) * 100 : 0;
                    return (
                      <div key={i} className="histogram-bar-container">
                        <div 
                          className="histogram-bar" 
                          style={{ height: `${Math.max(height, 5)}%` }}
                          title={`${(min * 100).toFixed(0)}-${(max * 100).toFixed(0)}: ${count} signals`}
                        />
                        <span className="histogram-label">{(min * 100).toFixed(0)}</span>
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
        <div className="footer-left">
          <span>Predictor Agent v1.0</span>
          <span className="divider">•</span>
          <span>Powered by ARS Technology</span>
        </div>
        <div className="footer-right">
          <a href="https://polymarket.com" target="_blank" rel="noopener noreferrer">
            Data from Polymarket
          </a>
          <span className="divider">•</span>
          <span>Not financial advice</span>
        </div>
      </footer>
    </div>
  );
}
