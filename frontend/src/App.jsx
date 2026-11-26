import { useEffect, useMemo, useState } from 'react'
import {
  Activity, ArrowDownLeft, ArrowLeftRight, ArrowRight, ArrowUpRight, BadgeCheck, BarChart3,
  Bell, BookOpen, Building2, CalendarDays, Check, CheckCircle2, ChevronDown, CircleHelp,
  Clock3, CloudUpload, Compass, CreditCard, ExternalLink, FileCheck2, FileText, Globe2, Hotel, Layers, LayoutDashboard,
  LoaderCircle, LockKeyhole, LogOut, Menu, MessageSquareText, Plane, Play, Plus, RefreshCw, Search,
  Send, ShieldCheck, Sparkles, TrendingUp, Upload, Wallet, X,
} from 'lucide-react'

const NAV = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, group: 'WORKSPACE' },
  { id: 'assistant', label: 'Policy assistant', icon: MessageSquareText },
  { id: 'expense', label: 'Expense review', icon: CreditCard },
  { id: 'travel', label: 'Travel requests', icon: Plane },
  { id: 'fx', label: 'Currency rates', icon: ArrowLeftRight, group: 'INSIGHTS' },
  { id: 'operations', label: 'Operations', icon: Activity },
]
const CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'SGD', 'AED', 'CHF']
const DESTINATION_COUNTRIES = [
  'Australia', 'Brazil', 'Canada', 'China', 'Denmark', 'France', 'Germany', 'India', 'Indonesia', 'Ireland',
  'Italy', 'Japan', 'Malaysia', 'Mexico', 'Netherlands', 'New Zealand', 'Poland', 'Singapore', 'South Africa',
  'South Korea', 'Spain', 'Sweden', 'Switzerland', 'United Kingdom', 'United States', 'Other',
]
const EMPLOYEE_GRADES = ['G1', 'G2', 'G3', 'G4', 'G5']
const DEFAULT_GRADE = 'M6'

async function api(path, options = {}) {
  const response = await fetch(path, options)
  const type = response.headers.get('content-type') || ''
  const body = type.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const detail = typeof body === 'object' ? body.detail : body
    throw new Error(detail || `Request failed (${response.status})`)
  }
  return body
}
const get = (path, params = {}) => {
  const query = new URLSearchParams(params)
  const serialized = query.toString()
  return api(`${path}${serialized ? `?${serialized}` : ''}`)
}
const postQuery = (path, params = {}) => {
  const query = new URLSearchParams(params).toString()
  return api(`${path}${query ? `?${query}` : ''}`, { method: 'POST' })
}
const post = (path, payload) => api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
const money = (value, currency = 'INR') => new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value || 0))
const dateLabel = (value) => value ? new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—'

function Button({ children, variant = 'primary', icon: Icon, className = '', ...props }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{Icon && <Icon size={16} strokeWidth={2} />}{children}</button>
}

function Field({ label, hint, children, className = '' }) {
  return <label className={`field ${className}`}><span className="field-label">{label}</span>{children}{hint && <span className="field-hint">{hint}</span>}</label>
}

function Select({ value, onChange, children, ...props }) {
  return <div className="select-wrap"><select value={value} onChange={onChange} {...props}>{children}</select><ChevronDown size={15} /></div>
}

function Notice({ kind = 'info', children }) {
  const Icon = kind === 'success' ? CheckCircle2 : kind === 'warning' ? CircleHelp : LockKeyhole
  return <div className={`notice notice-${kind}`}><Icon size={17} /> <span>{children}</span></div>
}

function App() {
  const [page, setPage] = useState('overview')
  const [orgs, setOrgs] = useState(['default'])
  const [org, setOrg] = useState('default')
  const [health, setHealth] = useState(null)
  const [policy, setPolicy] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [booting, setBooting] = useState(true)
  const [error, setError] = useState('')
  const [mobileNav, setMobileNav] = useState(false)

  const loadWorkspace = async () => {
    try {
      const [service, directory] = await Promise.all([get('/health'), get('/api/v1/policies/organizations')])
      setHealth(service)
      const list = directory.organizations?.length ? directory.organizations : ['default']
      setOrgs(list)
      setOrg((current) => list.includes(current) ? current : (list.includes('globaltech') ? 'globaltech' : list[0]))
      setError('')
    } catch (e) { setError(e.message || 'The API could not be reached.') }
    finally { setBooting(false) }
  }

  useEffect(() => { loadWorkspace() }, [])
  useEffect(() => {
    if (!org) return
    let current = true
    get('/api/v1/policies/status', { organization_id: org })
      .then((value) => { if (current) setPolicy(value) })
      .catch(() => { if (current) setPolicy(null) })
    return () => { current = false }
  }, [org])
  useEffect(() => {
    get('/api/v1/dashboard/analytics').then(setAnalytics).catch(() => {})
  }, [])

  const active = NAV.find((item) => item.id === page) || NAV[0]
  const connection = health ? 'Connected' : booting ? 'Connecting' : 'Offline'

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><Plane size={19} fill="currentColor" /></div><span>travelwise<span className="brand-period">.</span></span><button className="icon-button mobile-close" onClick={() => setMobileNav(false)} aria-label="Close navigation"><X size={18} /></button></div>
      <div className="workspace-switch"><div className="workspace-avatar"><Building2 size={16} /></div><div className="workspace-copy"><span>Workspace</span><strong>GlobalTech</strong></div><ChevronDown size={15} /></div>
      <div className="nav-list">
        {NAV.map((item) => <div key={item.id}>
          {item.group && <div className="nav-group">{item.group}</div>}
          <button className={`nav-item ${page === item.id ? 'nav-item-active' : ''}`} onClick={() => { setPage(item.id); setMobileNav(false) }}>
            <item.icon size={17} strokeWidth={1.8} /><span>{item.label}</span>{item.id === 'operations' && health && <span className="nav-ping" />}
          </button>
        </div>)}
      </div>
      <div className="sidebar-bottom">
        <div className="sidebar-help"><div className="help-icon"><BookOpen size={16} /></div><div><strong>Need a hand?</strong><span>View the quick guide</span></div><ArrowRight size={15} /></div>
        <div className="sidebar-user"><div className="user-avatar">SR</div><div className="user-copy"><strong>Workspace Admin</strong><span>admin@globaltech.test</span></div><button className="icon-button" title="Account"><LogOut size={16} /></button></div>
      </div>
    </aside>
    {mobileNav && <button className="nav-scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}

    <main className="main-area">
      <header className="topbar">
        <div className="topbar-left"><button className="icon-button mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={19} /></button><div className="breadcrumbs"><span>Workspace</span><span className="crumb-divider">/</span><strong>{active.label}</strong></div></div>
        <div className="topbar-right">
          <div className={`connection ${health ? 'connection-on' : ''}`}><span className="connection-dot" />{connection}</div>
          <div className="topbar-divider" />
          <label className="org-picker" title="Select organization"><Building2 size={15} /><Select value={org} onChange={(e) => setOrg(e.target.value)}>{orgs.map((item) => <option key={item}>{item}</option>)}</Select></label>
          <button className="icon-button notification-button" title="Notifications"><Bell size={17} /><i /></button>
          <div className="top-avatar">S</div>
        </div>
      </header>

      <div className="page-scroll">
        {error && <div className="global-error"><span>{error}</span><Button variant="text" icon={RefreshCw} onClick={loadWorkspace}>Retry</Button></div>}
        {page === 'overview' && <Overview health={health} policy={policy} analytics={analytics} setPage={setPage} org={org} />}
        {page === 'assistant' && <Assistant org={org} policy={policy} onPolicyChanged={setPolicy} health={health} onHealthChanged={setHealth} />}
        {page === 'expense' && <Expense org={org} />}
        {page === 'travel' && <Travel />}
        {page === 'fx' && <Rates />}
        {page === 'operations' && <Operations org={org} health={health} policy={policy} analytics={analytics} refresh={() => { loadWorkspace(); get('/api/v1/dashboard/analytics').then(setAnalytics) }} />}
      </div>
    </main>
  </div>
}

function PageHeading({ eyebrow, title, subtitle, action }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>
}

function Overview({ health, policy, analytics, setPage, org }) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const stats = [
    { label: 'Assistant requests', value: analytics?.total_queries ?? '—', note: `${analytics?.success_rate ? Math.round(analytics.success_rate * 100) : 0}% successful`, icon: MessageSquareText, color: 'blue' },
    { label: 'Policy documents', value: policy?.document_count?.toLocaleString() ?? '—', note: policy?.synthetic_document_count ? 'Synthetic evaluation corpus' : 'Approved source files', icon: FileCheck2, color: 'violet' },
    { label: 'Average response', value: analytics?.average_latency_ms ? `${Math.round(analytics.average_latency_ms)} ms` : '—', note: 'Across recent queries', icon: Clock3, color: 'amber' },
    { label: 'Service status', value: health ? 'Operational' : 'Checking', note: health?.llm_mode === 'hosted' && health?.hosted_model?.configured ? `${health.hosted_model.model || 'Qwen/Qwen3-8B'} enabled` : 'Evidence-only mode', icon: Activity, color: 'green' },
  ]
  const quick = [
    { id: 'assistant', title: 'Ask about a policy', desc: 'Get a grounded answer with source citations.', icon: MessageSquareText, tone: 'blue' },
    { id: 'expense', title: 'Review an expense', desc: 'Convert a claim and check the evidence path.', icon: CreditCard, tone: 'teal' },
    { id: 'travel', title: 'Start a travel request', desc: 'Capture trip details for human review.', icon: Plane, tone: 'violet' },
  ]
  return <div className="page-content">
    <PageHeading eyebrow="YOUR WORKSPACE" title={`${greeting}`} subtitle="A clear view of travel policy and expense activity across your organization." action={<Button variant="secondary" icon={RefreshCw} onClick={() => window.location.reload()}>Refresh data</Button>} />
    <div className="welcome-banner"><div className="welcome-copy"><div className="banner-kicker"><Sparkles size={14} /> YOUR POLICY WORKSPACE</div><h2>Make every travel decision<br className="desktop-only" /> with confidence.</h2><p>Ask questions, review expenses and keep your team moving with policy-backed guidance.</p><Button variant="white" icon={MessageSquareText} onClick={() => setPage('assistant')}>Ask the policy assistant <ArrowRight size={15} /></Button></div><div className="banner-art"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="banner-globe"><Globe2 size={74} strokeWidth={1.1} /></div><div className="float-card float-card-top"><div className="float-card-icon"><ShieldCheck size={16} /></div><div><b>Policy grounded</b><span>Sources included</span></div><Check size={15} /></div><div className="float-card float-card-bottom"><div className="avatar-stack"><i>AK</i><i>JM</i><i>+</i></div><div><b>One workspace</b><span>Built for your team</span></div></div><div className="banner-plane"><Plane size={29} /></div></div></div>
    <div className="section-heading"><div><h2>Workspace pulse</h2><p>Live signals from your policy and expense workflows</p></div><span className="live-tag"><i /> LIVE</span></div>
    <div className="stat-grid">{stats.map((item) => <div className="stat-card" key={item.label}><div className={`stat-icon stat-${item.color}`}><item.icon size={18} /></div><span className="stat-label">{item.label}</span><strong>{item.value}</strong><small>{item.note}</small></div>)}</div>
    {policy?.synthetic_document_count > 0 && <div className="corpus-note"><div className="corpus-note-icon"><CircleHelp size={18} /></div><div><strong>Evaluation corpus loaded</strong><span>{policy.synthetic_document_count} synthetic policies · {policy.batches?.join(', ')} · {policy.corpus_complete ? 'Complete' : `${policy.full_corpus_expected_documents - policy.document_count} documents still to add for the full guide corpus`}</span></div><span className="synthetic-pill">TEST DATA</span></div>}
    <div className="section-heading section-heading-spaced"><div><h2>Jump back in</h2><p>Choose a workflow to get started</p></div><button className="link-button" onClick={() => setPage('operations')}>View operations <ArrowRight size={15} /></button></div>
    <div className="quick-grid">{quick.map((item) => <button className="quick-card" key={item.id} onClick={() => setPage(item.id)}><div className={`quick-icon quick-${item.tone}`}><item.icon size={19} /></div><div className="quick-copy"><strong>{item.title}</strong><span>{item.desc}</span></div><ArrowRight className="quick-arrow" size={17} /></button>)}</div>
    <div className="bottom-info"><div className="bottom-info-mark"><LockKeyhole size={15} /></div><span>Decisions stay transparent. Policy responses include citations, and approvals always remain with a human.</span><button onClick={() => setPage('operations')}>View safeguards</button></div>
  </div>
}

function Assistant({ org, policy, onPolicyChanged, health, onHealthChanged }) {
  const [destinationCountry, setDestinationCountry] = useState('')
  const [employeeGrade, setEmployeeGrade] = useState('')
  const [tripType, setTripType] = useState('')
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState([])
  const [sessionId, setSessionId] = useState(() => `SES-${Math.random().toString(36).slice(2, 10)}`)
  const [loading, setLoading] = useState(false)
  const [modelBusy, setModelBusy] = useState(false)
  const [error, setError] = useState('')
  const [ingestOpen, setIngestOpen] = useState(false)
  const [providerOpen, setProviderOpen] = useState(false)
  const hostedInfo = health?.hosted_model || {}
  const embeddingInfo = health?.embeddings || {}
  const availableModels = hostedInfo.available_models?.length ? hostedInfo.available_models : [
    { id: 'evidence-only', label: 'Evidence-only (No model)', mode: 'mock', model: null },
    { id: 'Qwen/Qwen3-8B', label: 'Qwen/Qwen3-8B (Hosted)', mode: 'hosted', model: 'Qwen/Qwen3-8B' },
  ]
  const selectedModel = hostedInfo.active_selection || (health?.llm_mode === 'hosted' && hostedInfo.configured ? (hostedInfo.model || 'Qwen/Qwen3-8B') : 'evidence-only')
  const generatedResponsesAvailable = health?.llm_mode === 'hosted' && hostedInfo.configured === true
  const prompts = ['What evidence do I need for a hotel expense?', 'How should I handle a multi-country trip?', 'What applies to a historical policy version?']

  const handleModelSelect = async (nextSelection) => {
    setError('')
    if (nextSelection === 'evidence-only') {
      setModelBusy(true)
      try {
        await post('/api/v1/llm/select', { selection: 'evidence-only', mode: 'mock' })
        onHealthChanged?.(await get('/health'))
      } catch (e) { setError(e.message || 'Could not switch model mode.') }
      finally { setModelBusy(false) }
      return
    }
    if (!hostedInfo.configured) {
      setProviderOpen(true)
      return
    }
    setModelBusy(true)
    try {
      await post('/api/v1/llm/select', { selection: nextSelection, mode: 'hosted', model: nextSelection })
      onHealthChanged?.(await get('/health'))
    } catch (e) {
      setError(e.message || 'Could not activate hosted model.')
      setProviderOpen(true)
    } finally { setModelBusy(false) }
  }

  const ask = async (value = query) => {
    const cleanQuery = value.trim()
    if (!cleanQuery || loading) return
    setLoading(true); setError(''); setQuery('')
    const travelContext = {}
    if (destinationCountry) travelContext.destination_country = destinationCountry
    if (employeeGrade) travelContext.employee_grade = employeeGrade
    if (tripType) travelContext.trip_type = tripType
    const hasContext = Object.keys(travelContext).length > 0
    const userTurn = { role: 'user', text: cleanQuery }
    setHistory((items) => [...items, userTurn])
    try {
      if (generatedResponsesAvailable) {
        const payload = {
          query: cleanQuery,
          employee_id: 'EMP1001',
          organization_id: org,
          model: hostedInfo.model || 'Qwen/Qwen3-8B',
          session_id: sessionId,
          ...(employeeGrade ? { grade: employeeGrade } : {}),
          ...(hasContext ? { travel_context: travelContext } : {}),
        }
        const result = await post('/api/v1/ai/chat', payload)
        setHistory((items) => [...items, { role: 'assistant', result }])
      } else {
        const contextTerms = [destinationCountry, employeeGrade, tripType].filter(Boolean)
        const searchQuery = hasContext ? `${cleanQuery} ${contextTerms.join(' ')}` : cleanQuery
        const params = {
          query: searchQuery,
          organization_id: org,
          ...(employeeGrade ? { grade: employeeGrade } : {}),
        }
        const evidence = await postQuery('/api/v1/ai/policy-search', params)
        setHistory((items) => [...items, { role: 'assistant', result: { mode: 'evidence', ...evidence } }])
      }
    } catch (e) { setError(e.message || 'The request could not be completed.') }
    finally { setLoading(false) }
  }
  const latestResult = history.filter((item) => item.role === 'assistant').at(-1)?.result
  const latestDocs = latestResult?.documents || latestResult?.tool_results?.policy_search?.documents || []

  const newSession = () => {
    setHistory([])
    setError('')
    setSessionId(`SES-${Math.random().toString(36).slice(2, 10)}`)
  }

  return <div className="page-content">
    <PageHeading eyebrow="POLICY INTELLIGENCE" title="Policy assistant" subtitle="Answers grounded in your organization’s policy documents, with the sources shown alongside." action={<div className="assistant-heading-actions"><span className="secure-label"><ShieldCheck size={15} /> Evidence-backed</span>{history.length > 0 && <Button variant="secondary" icon={RefreshCw} onClick={newSession}>New chat</Button>}<Button variant="secondary" icon={Sparkles} onClick={() => setProviderOpen(true)}>Model &amp; embeddings</Button><Button variant="secondary" icon={Upload} onClick={() => setIngestOpen(true)}>Add documents</Button></div>} />
    {!generatedResponsesAvailable && <div className="model-notice"><div className="model-notice-icon"><Sparkles size={16} /></div><div><strong>Evidence-only mode</strong><span>No hosted language model is configured. Select <code>Qwen/Qwen3-8B</code> and connect your approved provider key &amp; CA certificate (<code>vm04-ca.crt</code>) before enabling generated responses.</span></div><Button variant="secondary" onClick={() => setProviderOpen(true)}>Select model</Button><span className="mode-chip">NO MODEL</span></div>}
    <div className="assistant-layout">
      <section className="assistant-main card">
        <div className="assistant-toolbar"><div className="assistant-agent"><div className="agent-avatar"><Sparkles size={17} /></div><div><strong>TravelWise assistant</strong><span><i className="online-dot" /> {generatedResponsesAvailable ? `${selectedModel} active` : 'Ready to help'}</span></div></div><div className="assistant-context"><Field label="Select model"><Select value={selectedModel} disabled={modelBusy} onChange={(e) => handleModelSelect(e.target.value)}>{availableModels.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</Select></Field><strong className="assistant-context-title" style={{ fontSize: 9, color: '#617480', whiteSpace: 'nowrap' }}>Travel context</strong><Field label="Destination country"><Select value={destinationCountry} onChange={(e) => setDestinationCountry(e.target.value)}><option value="">Select country</option>{DESTINATION_COUNTRIES.map((country) => <option key={country}>{country}</option>)}</Select></Field><Field label="Employee grade" hint={employeeGrade ? `${employeeGrade} selected; use its assigned policy rules.` : 'Optional; leave blank for direct questions or if unknown.'}><Select value={employeeGrade} onChange={(e) => setEmployeeGrade(e.target.value)}><option value="">Select grade</option>{EMPLOYEE_GRADES.map((grade) => <option key={grade}>{grade}</option>)}</Select></Field><Field label="Trip type"><Select value={tripType} onChange={(e) => setTripType(e.target.value)}><option value="">Select trip type</option><option>Domestic</option><option>International</option></Select></Field></div></div>
        <div className="conversation">
          {history.length === 0 ? <div className="assistant-welcome"><div className="assistant-welcome-icon"><Sparkles size={22} /></div><h2>What would you like to know?</h2><p>{generatedResponsesAvailable ? 'Ask about travel rules, expenses or policy exceptions. I’ll show the documents that support the answer.' : 'Search your organization’s policy evidence. Generated answers become available when an approved provider is configured.'}</p><div className="prompt-list">{prompts.map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}<ArrowRight size={14} /></button>)}</div></div> : history.map((item, index) => item.role === 'user' ? <div className="chat-row chat-user" key={index}><div className="chat-user-bubble">{item.text}</div><div className="mini-user-avatar">S</div></div> : <div className="chat-row chat-assistant" key={index}><div className="chat-assistant-avatar"><Sparkles size={15} /></div><div className="chat-answer"><div className="answer-meta"><strong>{item.result.mode === 'evidence' ? 'Retrieved policy evidence' : 'TravelWise assistant'}</strong><span>{item.result.mode === 'evidence' ? `${item.result.documents?.length || 0} sources · evidence only` : `${item.result.latency_ms} ms · ${item.result.status}`}</span></div>{item.result.mode === 'evidence' ? item.result.documents?.length ? <div className="evidence-results">{item.result.documents.map((doc) => <article className="evidence-result" key={doc.id}><div><strong>{doc.title || doc.document_id}</strong><code>{doc.id}</code></div><p>{doc.text}</p><small>{[doc.document_id, doc.jurisdiction, doc.version && `v${doc.version}`].filter(Boolean).join(' · ')}</small></article>)}</div> : <p>No matching policy evidence was found, so no policy conclusion is available.</p> : <p>{item.result.answer}</p>}{item.result.citations?.length > 0 && <div className="answer-citations"><span><BookOpen size={14} /> Sources</span>{item.result.citations.map((citation) => <code key={citation}>{citation}</code>)}</div>}</div></div>)}
          {loading && <div className="chat-row chat-assistant"><div className="chat-assistant-avatar"><Sparkles size={15} /></div><div className="thinking"><LoaderCircle size={16} className="spin" /> Searching policy evidence and preparing an answer…</div></div>}
          {error && <div className="inline-error">{error}</div>}
        </div>
        <div className="composer"><textarea rows="1" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask() } }} placeholder={generatedResponsesAvailable ? 'Ask a travel or expense policy question…' : 'Search policy evidence…'} /><div className="composer-footer"><span><LockKeyhole size={12} /> Your query is recorded in the audit trace</span><Button icon={generatedResponsesAvailable ? Send : Search} onClick={() => ask()} disabled={!query.trim() || loading}>{generatedResponsesAvailable ? 'Send question' : 'Search evidence'}</Button></div></div>
      </section>
      <aside className="assistant-side">
        <div className="side-card card"><div className="side-card-title"><div className="side-card-icon"><BookOpen size={17} /></div><div><strong>Knowledge source</strong><span>{org}</span></div><BadgeCheck size={17} className="verified-icon" /></div><div className="knowledge-count"><strong>{policy?.document_count ?? '—'}</strong><span>policy documents</span></div><div className="knowledge-meter"><i style={{ width: `${Math.min(100, (policy?.document_count || 0) / (policy?.full_corpus_expected_documents || 500) * 100)}%` }} /></div><div className="knowledge-meta"><span>Corpus coverage</span><strong>{policy ? `${Math.min(100, Math.round(policy.document_count / (policy.full_corpus_expected_documents || 500) * 100))}%` : '—'}</strong></div>{policy?.synthetic_document_count > 0 && <div className="test-data-note"><CircleHelp size={14} /> Synthetic test content</div>}</div>
        <div className="side-card card"><div className="side-card-heading"><strong>Response principles</strong><span>Every answer follows these checks</span></div><div className="principle"><div className="principle-check"><Check size={13} /></div><span>Uses retrieved policy evidence</span></div><div className="principle"><div className="principle-check"><Check size={13} /></div><span>Shows source citations</span></div><div className="principle"><div className="principle-check"><Check size={13} /></div><span>Escalates when evidence is missing</span></div><div className="principle"><div className="principle-check"><Check size={13} /></div><span>Never initiates a payment</span></div></div>
        <div className="side-card card"><div className="side-card-heading"><strong>Model &amp; retrieval</strong><span>Active inference and vector config</span></div><div className="principle"><div className="principle-check"><Sparkles size={13} /></div><span>Chat: {generatedResponsesAvailable ? (hostedInfo.model || 'Qwen/Qwen3-8B') : `Evidence-only (${hostedInfo.model || 'Qwen/Qwen3-8B'} ready)`}</span></div><div className="principle"><div className="principle-check"><Search size={13} /></div><span>Embeddings: {embeddingInfo.configured ? `${embeddingInfo.model} (${embeddingInfo.dimensions || 384}d)` : `${embeddingInfo.model || 'bge-small-en-v1.5'} (TF-IDF fallback)`}</span></div></div>
        {latestDocs.length > 0 && <div className="side-card card retrieved-card"><div className="side-card-heading"><strong>Retrieved evidence</strong><span>Most recent response</span></div>{latestDocs.slice(0, 4).map((doc) => <div className="retrieved-source" key={doc.id}><div className="source-file-icon"><FileText size={14} /></div><div><strong>{doc.document_id || doc.id}</strong><span>{doc.title || doc.source_file}</span><small>{[doc.jurisdiction, doc.version && `v${doc.version}`].filter(Boolean).join(' · ')}</small></div></div>)}</div>}
      </aside>
    </div>
    {ingestOpen && <IngestModal org={org} onClose={() => setIngestOpen(false)} onComplete={onPolicyChanged} />}
    {providerOpen && <ProviderConfigModal hosted={hostedInfo} embeddings={embeddingInfo} onClose={() => setProviderOpen(false)} onSaved={async () => { onHealthChanged?.(await get('/health')); setProviderOpen(false) }} />}
  </div>
}

function ProviderConfigModal({ hosted, embeddings, onClose, onSaved }) {
  const [llmModel, setLlmModel] = useState(hosted?.model || 'Qwen/Qwen3-8B')
  const [llmBaseUrl, setLlmBaseUrl] = useState(hosted?.endpoint_url || 'https://103.42.50.41:1034/v1')
  const [llmCaCert, setLlmCaCert] = useState(hosted?.ca_certificate_path || 'C:/Users/SR/Downloads/vm04-ca.crt')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [embMode, setEmbMode] = useState(embeddings?.mode || 'hybrid')
  const [embModel, setEmbModel] = useState(embeddings?.model || 'bge-small-en-v1.5')
  const [embBaseUrl, setEmbBaseUrl] = useState(embeddings?.endpoint_url || 'https://103.42.50.41:1035/v1')
  const [embCaCert, setEmbCaCert] = useState(embeddings?.ca_certificate_path || 'C:/Users/SR/Downloads/vm02-ca.crt')
  const [embApiKey, setEmbApiKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async (e) => {
    e.preventDefault()
    setBusy(true); setError('')
    try {
      await post('/api/v1/llm/select', {
        selection: llmModel,
        mode: 'hosted',
        model: llmModel,
        base_url: llmBaseUrl,
        ca_cert_file: llmCaCert,
        ...(llmApiKey.trim() ? { api_key: llmApiKey.trim() } : {}),
      })
      if (embApiKey.trim() || embMode !== embeddings?.mode || embBaseUrl !== embeddings?.endpoint_url || embModel !== embeddings?.model) {
        await post('/api/v1/embeddings/config', {
          mode: embMode,
          model: embModel,
          base_url: embBaseUrl,
          ca_cert_file: embCaCert,
          ...(embApiKey.trim() ? { api_key: embApiKey.trim() } : {}),
        })
      }
      await onSaved()
    } catch (err) {
      setError(err.message || 'Could not connect hosted provider.')
    } finally {
      setBusy(false)
    }
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
    <section className="ingest-modal card" role="dialog" aria-modal="true" aria-labelledby="provider-title">
      <div className="modal-heading"><div><div className="eyebrow">HOSTED PROVIDERS</div><h2 id="provider-title">Connect model &amp; embeddings</h2><p>Configure hosted chat (<code>Qwen/Qwen3-8B</code>) and Capstone retrieval embeddings (<code>bge-small-en-v1.5</code>) with CA verification.</p></div><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button></div>
      <form onSubmit={save}>
        <div className="form-grid">
          <Field label="Chat model ID"><input value={llmModel} onChange={(e) => setLlmModel(e.target.value)} required /></Field>
          <Field label="Chat base URL"><input value={llmBaseUrl} onChange={(e) => setLlmBaseUrl(e.target.value)} required /></Field>
          <Field label="Chat CA cert (vm04-ca.crt)" className="field-wide"><input value={llmCaCert} onChange={(e) => setLlmCaCert(e.target.value)} required /></Field>
          <Field label="Group API key" className="field-wide" hint="Kept in API process memory only; never logged or saved to traces."><input type="password" placeholder={hosted?.configured ? 'Key already configured (leave blank to keep)' : 'YOUR_GROUP_API_KEY'} value={llmApiKey} onChange={(e) => setLlmApiKey(e.target.value)} /></Field>
          <Field label="Embedding model ID"><input value={embModel} onChange={(e) => setEmbModel(e.target.value)} required /></Field>
          <Field label="Embedding mode"><Select value={embMode} onChange={(e) => setEmbMode(e.target.value)}><option value="hybrid">Hybrid (bge + TF-IDF)</option><option value="hosted">Hosted (bge only)</option><option value="tfidf">TF-IDF only</option></Select></Field>
          <Field label="Embedding base URL" className="field-wide"><input value={embBaseUrl} onChange={(e) => setEmbBaseUrl(e.target.value)} /></Field>
          <Field label="Embedding CA cert (vm02-ca.crt)" className="field-wide"><input value={embCaCert} onChange={(e) => setEmbCaCert(e.target.value)} /></Field>
          <Field label="Embedding API key" className="field-wide" hint="Optional; 384-d vectors, up to 16 texts/batch, <=512 tokens."><input type="password" placeholder={embeddings?.configured ? 'Key already configured (leave blank to keep)' : 'YOUR_EMBEDDINGS_KEY'} value={embApiKey} onChange={(e) => setEmbApiKey(e.target.value)} /></Field>
        </div>
        {error && <div className="inline-error">{error}</div>}
        <div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button icon={busy ? LoaderCircle : Check} disabled={busy}>{busy ? 'Connecting…' : `Enable ${llmModel}`}</Button></div>
      </form>
    </section>
  </div>
}

function IngestModal({ org, onClose, onComplete }) {
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const upload = async (e) => {
    e.preventDefault()
    if (!file) return
    setBusy(true); setError(''); setResult(null)
    const body = new FormData()
    body.append('organization_id', org)
    body.append('file', file)
    try {
      const added = await api('/api/v1/policies/ingest', { method: 'POST', body })
      setResult(added)
      const fresh = await get('/api/v1/policies/status', { organization_id: org })
      onComplete(fresh)
    } catch (err) { setError(err.message || 'The file could not be ingested.') }
    finally { setBusy(false) }
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}><section className="ingest-modal card" role="dialog" aria-modal="true" aria-labelledby="ingest-title"><div className="modal-heading"><div><div className="eyebrow">KNOWLEDGE SOURCE</div><h2 id="ingest-title">Add policy documents</h2><p>Documents are stored in the selected organization’s policy workspace.</p></div><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={18} /></button></div><form onSubmit={upload}><Field label="Organization"><div className="modal-org"><Building2 size={15} /> {org}</div></Field><label className={`upload-drop ${file ? 'upload-selected' : ''}`}><input type="file" accept=".txt,.md,.html,.htm,.pdf,.docx" onChange={(e) => setFile(e.target.files?.[0] || null)} /><div className="upload-icon"><CloudUpload size={21} /></div><strong>{file ? file.name : 'Choose a file or drag it here'}</strong><span>{file ? `${(file.size / (1024 * 1024)).toFixed(2)} MB · ${file.type || 'Document'}` : 'TXT, Markdown, HTML, PDF or DOCX · up to 20 MB'}</span></label>{error && <div className="inline-error">{error}</div>}{result && <Notice kind="success">Added {result.filename}. {result.indexed_clauses} chunks are ready for retrieval.</Notice>}<div className="modal-footnote"><ShieldCheck size={14} /> Only upload approved policy content. Answers will cite this source.</div><div className="modal-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button icon={busy ? LoaderCircle : Plus} disabled={!file || busy}>{busy ? 'Adding document…' : 'Add to knowledge base'}</Button></div></form></section></div>
}

function Expense({ org }) {
  const [form, setForm] = useState({ employee_id: 'EMP1001', category: 'hotel', currency: 'INR', amount: '8500', nights: '1' })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const update = (key) => (e) => setForm((value) => ({ ...value, [key]: e.target.value }))
  const submit = async (e) => { e.preventDefault(); setLoading(true); setError(''); setResult(null); try { setResult(await post('/api/v1/expenses/validate', { ...form, grade: DEFAULT_GRADE, amount: Number(form.amount), nights: Number(form.nights), organization_id: org })) } catch (err) { setError(err.message) } finally { setLoading(false) } }
  return <div className="page-content">
    <PageHeading eyebrow="EXPENSE OPERATIONS" title="Expense review" subtitle="Convert a claim to INR and check what evidence is available for a policy review." />
    <div className="workflow-layout"><form className="card workflow-card" onSubmit={submit}><div className="card-heading"><div><h2>Claim details</h2><p>Enter the receipt information to begin the review.</p></div><div className="step-badge">01 <span>/</span> 01</div></div><div className="form-grid"><Field label="Employee ID"><input value={form.employee_id} onChange={update('employee_id')} required /></Field><Field label="Expense category"><Select value={form.category} onChange={update('category')}><option value="hotel">Hotel & accommodation</option><option value="meal">Meals & hospitality</option><option value="flight">Air travel</option><option value="local_transport">Local transportation</option><option value="other">Other expense</option></Select></Field><Field label="Receipt currency"><Select value={form.currency} onChange={update('currency')}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select></Field><Field label="Claim amount"><div className="input-with-prefix"><span>{form.currency}</span><input type="number" min="0.01" step="0.01" value={form.amount} onChange={update('amount')} required /></div></Field><Field label="Number of nights" hint="Only applies to accommodation claims"><input type="number" min="1" step="1" value={form.nights} onChange={update('nights')} /></Field></div>{error && <div className="inline-error">{error}</div>}<div className="form-actions"><span><LockKeyhole size={13} /> No reimbursement or approval is initiated</span><Button icon={loading ? LoaderCircle : ArrowRight} disabled={loading}>{loading ? 'Checking…' : 'Convert and review'}</Button></div></form>
      <aside className="workflow-side"><div className="side-card card"><div className="side-card-title"><div className="side-card-icon side-teal"><CreditCard size={17} /></div><div><strong>Review workflow</strong><span>What happens next</span></div></div><div className="workflow-step"><span>1</span><div><strong>Currency conversion</strong><p>Uses the latest published reference rate.</p></div></div><div className="workflow-step"><span>2</span><div><strong>Policy source check</strong><p>Searches the selected organization’s policy corpus.</p></div></div><div className="workflow-step"><span>3</span><div><strong>Human decision</strong><p>Final eligibility stays with your reviewer.</p></div></div></div><Notice kind="warning">A conversion is not an eligibility decision. Claims need approved policy evidence before they can be assessed.</Notice></aside></div>
      {result && <div className="result-panel card"><div className="result-header"><div><div className="eyebrow">REVIEW SUMMARY</div><h2>Claim converted</h2></div><span className="status-pill status-review"><Clock3 size={13} /> Policy review required</span></div><div className="result-metrics"><div><span>Original claim</span><strong>{money(result.source_amount, result.source_currency)}</strong></div><ArrowRight size={18} /><div><span>Converted total</span><strong className="result-total">{money(result.amount_inr)}</strong></div><div className="result-rate"><span>Published rate</span><strong>1 {result.source_currency} = {Number(result.exchange_rate).toFixed(4)} INR</strong><small>Rate date {result.fx?.rate_date} · {result.fx?.freshness?.replaceAll('_', ' ')}</small></div></div><Notice kind="warning">{result.note || 'No approved eligibility rule was found. A reviewer must assess this claim.'}</Notice></div>}
    </div>
}

function Travel() {
  const today = new Date().toISOString().slice(0, 10)
  const later = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10)
  const [form, setForm] = useState({ employee_id: 'EMP1001', origin: 'Delhi', destination: 'Bengaluru', start_date: today, end_date: later, purpose: '', estimated_budget: '25000' })
  const [result, setResult] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const update = (key) => (e) => setForm((value) => ({ ...value, [key]: e.target.value }))
  const submit = async (e) => { e.preventDefault(); setLoading(true); setError(''); setResult(null); try { setResult(await post('/api/v1/travel/requests', { ...form, grade: DEFAULT_GRADE, estimated_budget: Number(form.estimated_budget) })) } catch (err) { setError(err.message) } finally { setLoading(false) } }
  return <div className="page-content"><PageHeading eyebrow="TRAVEL OPERATIONS" title="Travel requests" subtitle="Capture the business trip details and route the request for the right review." />
    <div className="workflow-layout"><form className="card workflow-card" onSubmit={submit}><div className="card-heading"><div><h2>Trip details</h2><p>Complete the itinerary and business purpose before submitting.</p></div><div className="step-badge">DRAFT</div></div><div className="form-grid"><Field label="Employee ID"><input value={form.employee_id} onChange={update('employee_id')} required /></Field><Field label="Origin"><div className="input-with-icon"><ArrowUpRight size={15} /><input value={form.origin} onChange={update('origin')} required /></div></Field><Field label="Destination"><div className="input-with-icon"><ArrowDownLeft size={15} /><input value={form.destination} onChange={update('destination')} required /></div></Field><Field label="Departure date"><input type="date" value={form.start_date} onChange={update('start_date')} required /></Field><Field label="Return date"><input type="date" min={form.start_date} value={form.end_date} onChange={update('end_date')} required /></Field><Field label="Business purpose" className="field-wide"><input placeholder="e.g. Customer workshop, project kickoff" value={form.purpose} onChange={update('purpose')} required /></Field><Field label="Estimated budget (INR)"><div className="input-with-prefix"><span>₹</span><input type="number" min="1" step="1" value={form.estimated_budget} onChange={update('estimated_budget')} required /></div></Field></div>{error && <div className="inline-error">{error}</div>}<div className="form-actions"><span><ShieldCheck size={13} /> Submitted for human review</span><Button icon={loading ? LoaderCircle : Send} disabled={loading}>{loading ? 'Submitting…' : 'Submit travel request'}</Button></div></form><aside className="workflow-side"><div className="trip-summary-card"><div className="trip-sky"><div className="trip-sky-top"><span>YOUR ITINERARY</span><Plane size={18} /></div><div className="trip-route"><div><small>FROM</small><strong>{form.origin.slice(0, 3).toUpperCase() || 'DEL'}</strong><span>{form.origin || 'Origin'}</span></div><div className="route-line"><i /><span /><i /></div><div className="trip-dest"><small>TO</small><strong>{form.destination.slice(0, 3).toUpperCase() || 'BLR'}</strong><span>{form.destination || 'Destination'}</span></div></div></div><div className="trip-summary-bottom"><div><CalendarDays size={15} /><span>{form.start_date || 'Start'} — {form.end_date || 'End'}</span></div><div><Wallet size={15} /><span>{money(form.estimated_budget)}</span></div></div></div><Notice>Submitting creates a request record. It does not book travel or approve a budget.</Notice></aside></div>
    {result && <div className="success-panel"><div className="success-check"><Check size={19} /></div><div><strong>Request submitted for review</strong><span>Reference {result.request_id} · status: {result.status}</span></div><BadgeCheck size={19} /></div>}
  </div>
}

function Rates() {
  const [base, setBase] = useState('USD'); const [quote, setQuote] = useState('INR'); const [amount, setAmount] = useState('100'); const [result, setResult] = useState(null); const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const convert = async (e) => { e?.preventDefault(); setLoading(true); setError(''); try { setResult(await get('/api/v1/market/fx', { base, quote, amount })) } catch (err) { setError(err.message) } finally { setLoading(false) } }
  const swap = () => { setBase(quote); setQuote(base); setResult(null) }
  return <div className="page-content"><PageHeading eyebrow="MARKET DATA" title="Currency rates" subtitle="Convert using the latest published reference rates. Values are not live market quotes." action={<span className="provider-badge"><Globe2 size={14} /> Frankfurter</span>} />
    <div className="rates-layout"><form className="rate-card card" onSubmit={convert}><div className="card-heading"><div><h2>Currency converter</h2><p>Reference rates are refreshed from the provider as published.</p></div><div className="rate-symbol"><ArrowLeftRight size={18} /></div></div><Field label="Amount"><input className="rate-amount" type="number" min="0.01" step="any" value={amount} onChange={(e) => setAmount(e.target.value)} required /></Field><div className="currency-pair"><Field label="From"><Select value={base} onChange={(e) => setBase(e.target.value)}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select></Field><button className="swap-button" type="button" onClick={swap} aria-label="Swap currencies"><ArrowLeftRight size={16} /></button><Field label="To"><Select value={quote} onChange={(e) => setQuote(e.target.value)}>{CURRENCIES.map((c) => <option key={c}>{c}</option>)}</Select></Field></div>{error && <div className="inline-error">{error}</div>}<Button icon={loading ? LoaderCircle : ArrowLeftRight} disabled={loading} className="convert-button">{loading ? 'Fetching rate…' : 'Get published rate'}</Button><div className="rate-fineprint"><LockKeyhole size={13} /> Published reference data · provider timestamp shown below</div></form>
      <div className="rate-result-card">{result ? <><div className="rate-result-top"><span className="eyebrow">CONVERSION RESULT</span><span className={`freshness fresh-${result.freshness === 'stale_fallback' ? 'stale' : 'current'}`}><i />{result.freshness?.replaceAll('_', ' ')}</span></div><div className="converted-label">{Number(result.amount).toLocaleString()} {result.base} converts to</div><div className="converted-amount">{money(result.converted_amount, result.quote)}</div><div className="rate-equation">1 {result.base} <ArrowRight size={13} /> {Number(result.rate).toFixed(6)} {result.quote}</div><div className="rate-result-meta"><div><span>Published date</span><strong>{result.rate_date}</strong></div><div><span>Retrieved</span><strong>{dateLabel(result.retrieved_at)}</strong></div></div>{result.freshness === 'stale_fallback' && <Notice kind="warning">Provider unavailable. Confirm the date before using this cached rate.</Notice>}</> : <div className="rate-empty"><div className="rate-empty-art"><div className="currency-orbit orbit-a">$</div><div className="currency-orbit orbit-b">€</div><div className="currency-orbit orbit-c">₹</div><Globe2 size={60} strokeWidth={1.1} /></div><h3>Rates, made clear.</h3><p>Choose two currencies to see the latest published reference rate and its source date.</p><div className="rate-trust"><div><CheckCircle2 size={15} /> Source date included</div><div><CheckCircle2 size={15} /> Stale data is flagged</div></div></div>}</div></div>
    <div className="fx-footnote"><div className="fx-footnote-icon"><CircleHelp size={17} /></div><div><strong>About these rates</strong><span>Frankfurter publishes reference exchange rates based on source institutions. They may differ from your bank’s settlement rate or the current market price.</span></div><a href="https://frankfurter.dev" target="_blank" rel="noreferrer">Provider details <ArrowRight size={13} /></a></div>
  </div>
}

function Operations({ org, health, policy, analytics, refresh }) {
  const [fx, setFx] = useState(null)
  const [model, setModel] = useState(null)
  const [traces, setTraces] = useState([])
  const [selected, setSelected] = useState(null)
  const [pipeline, setPipeline] = useState(null)
  const [diagQuery, setDiagQuery] = useState('What receipts are required for expense reimbursement?')
  const [diagResult, setDiagResult] = useState(null)
  const [diagBusy, setDiagBusy] = useState(false)
  const [evSource, setEvSource] = useState('evaluation')
  const [evSummary, setEvSummary] = useState(null)
  const [evBusy, setEvBusy] = useState(false)
  const [evNonce, setEvNonce] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true); setError('')
    try {
      const [f, m, t, p] = await Promise.all([
        get('/api/v1/market/status'),
        get('/api/v1/llm/status'),
        get('/api/v1/traces', { limit: 100 }),
        get('/api/v1/observability/pipeline'),
      ])
      setFx(f); setModel(m); setTraces(t || []); setPipeline(p); setSelected(null); refresh()
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  const loadEvidently = async (source = evSource, forceRun = false) => {
    setEvBusy(true)
    try {
      const data = forceRun
        ? await postQuery('/api/v1/observability/evidently/run', { source })
        : await get('/api/v1/observability/evidently/summary', { source })
      setEvSummary(data)
      setEvNonce((n) => n + 1)
    } catch (e) { setError(e.message || 'Could not generate Evidently report.') }
    finally { setEvBusy(false) }
  }

  const runDiagnostic = async (e) => {
    e?.preventDefault()
    if (!diagQuery.trim() || diagBusy) return
    setDiagBusy(true); setError('')
    try {
      const res = await post('/api/v1/observability/pipeline/test', {
        query: diagQuery.trim(),
        organization_id: org || 'globaltech',
      })
      setDiagResult(res)
    } catch (err) { setError(err.message || 'Pipeline diagnostic failed.') }
    finally { setDiagBusy(false) }
  }

  useEffect(() => { load() }, [org])
  useEffect(() => { loadEvidently(evSource, false) }, [evSource])

  const failures = analytics?.failure_taxonomy || {}
  const maxFailure = Math.max(1, ...Object.values(failures))
  const levels = pipeline?.levels || []
  const evidentlyReportUrl = `/api/v1/observability/evidently/report?source=${evSource}&v=${evNonce}`
  const requestTrend = useMemo(() => {
    const byDay = new Map()
    traces.forEach((trace) => {
      const day = trace.created_at ? new Date(trace.created_at).toISOString().slice(0, 10) : ''
      if (!day) return
      const item = byDay.get(day) || { day, total: 0, failed: 0 }
      item.total += 1
      if (trace.status === 'failed' || trace.status === 'blocked') item.failed += 1
      byDay.set(day, item)
    })
    return [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day)).slice(-7)
  }, [traces])
  const maxTrend = Math.max(1, ...requestTrend.map((item) => item.total))
  const successRate = analytics?.success_rate ?? 0

  return <div className="page-content operations-page"><PageHeading eyebrow="SYSTEM HEALTH" title="Operations" subtitle="A live view of service reliability, request activity, and assistant performance." action={<Button variant="secondary" icon={loading ? LoaderCircle : RefreshCw} onClick={load} disabled={loading}>Refresh</Button>} />
    {error && <div className="inline-error">{error}</div>}
    <div className="ops-kpis"><div className="ops-kpi card"><span>Total assistant requests</span><strong>{analytics?.total_queries ?? '—'}</strong><small>Recorded traces</small></div><div className="ops-kpi card"><span>Successful</span><strong className="text-green">{analytics?.successful ?? '—'}</strong><small>{analytics?.success_rate != null ? `${Math.round(analytics.success_rate * 100)}% success rate` : 'No data yet'}</small></div><div className="ops-kpi card"><span>Failed or degraded</span><strong className="text-amber">{analytics?.failed ?? '—'}</strong><small>Requires attention</small></div><div className="ops-kpi card"><span>Average latency</span><strong>{analytics?.average_latency_ms ? `${Math.round(analytics.average_latency_ms)} ms` : '—'}</strong><small>Recent requests</small></div></div>
    <div className="ops-charts-grid">
      <section className="card ops-chart-card">
        <div className="ops-card-header"><div><h2>Request activity</h2><p>Assistant traces by day · last 7 active days</p></div><TrendingUp size={18} className="muted-icon" /></div>
        {requestTrend.length ? <div className="request-chart" role="img" aria-label="Assistant request activity by day">
          {requestTrend.map((item) => <div className="request-chart-column" key={item.day} title={`${item.total} requests, ${item.failed} failed`}><span className="request-chart-count">{item.total}</span><div className="request-chart-track"><i style={{ height: `${Math.max(8, item.total / maxTrend * 100)}%` }} /><b style={{ height: `${item.total ? item.failed / item.total * 100 : 0}%` }} /></div><span className="request-chart-day">{new Date(`${item.day}T12:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span></div>)}
        </div> : <div className="chart-empty">Request activity will appear when assistant traces are recorded.</div>}
      </section>
      <section className="card ops-chart-card">
        <div className="ops-card-header"><div><h2>Service reliability</h2><p>Successful outcomes across all recorded requests</p></div><ShieldCheck size={18} className="muted-icon" /></div>
        <div className="reliability-chart"><div className="reliability-donut" style={{ '--success-rate': `${Math.max(0, Math.min(100, successRate * 100))}%` }}><div><strong>{analytics?.success_rate != null ? `${Math.round(successRate * 100)}%` : '—'}</strong><span>success</span></div></div><div className="reliability-legend"><div><i className="legend-success"/><span>Successful</span><strong>{analytics?.successful ?? '—'}</strong></div><div><i className="legend-failed"/><span>Failed or degraded</span><strong>{analytics?.failed ?? '—'}</strong></div><small>Based on {analytics?.total_queries ?? 0} recorded requests</small></div></div>
      </section>
    </div>
    <div className="ops-grid"><section className="card ops-card"><div className="ops-card-header"><div><h2>Service health</h2><p>Current provider and model status</p></div><span className={`status-pill ${health ? 'status-healthy' : 'status-review'}`}><i />{health ? 'Healthy' : 'Unavailable'}</span></div><div className="health-row"><div className="health-icon health-blue"><Activity size={17} /></div><div className="health-label"><strong>API service</strong><span>Rate limit · {health?.rate_limit?.limit ?? '—'} requests / {health?.rate_limit?.window_seconds ?? '—'} sec</span></div><span className="health-value">{health?.status || 'Unknown'}</span></div><div className="health-row"><div className="health-icon health-purple"><Sparkles size={17} /></div><div className="health-label"><strong>Response model</strong><span>{model?.model || 'Qwen/Qwen3-8B'} · {model?.endpoint_host || 'not configured'}</span></div><span className="health-value">{model?.configured ? model?.mode : 'evidence-only'}</span></div><div className="health-row"><div className="health-icon health-blue"><Search size={17} /></div><div className="health-label"><strong>Embedding model</strong><span>{health?.embeddings?.model || 'bge-small-en-v1.5'} · {health?.embeddings?.dimensions || 384}d · {health?.embeddings?.configured ? health?.embeddings?.mode : 'tfidf fallback'}</span></div><span className="health-value">{health?.embeddings?.configured ? 'ready' : 'unconfigured'}</span></div><div className="health-row"><div className="health-icon health-teal"><Globe2 size={17} /></div><div className="health-label"><strong>FX provider</strong><span>{fx?.provider || 'Frankfurter'} · {fx?.cache_entries ?? 0} cached rates</span></div><span className="health-value">{fx?.circuit_breaker || '—'}</span></div><div className="health-row"><div className="health-icon health-green"><BookOpen size={17} /></div><div className="health-label"><strong>Policy source</strong><span>{policy?.document_count ?? 0} docs · {policy?.clause_count ?? 0} chunks · {org}</span></div><span className="health-value">{policy?.status || '—'}</span></div></section>
      <section className="card ops-card"><div className="ops-card-header"><div><h2>Failure categories</h2><p>Recent query outcomes by category</p></div><BarChart3 size={18} className="muted-icon" /></div>{Object.keys(failures).length ? <div className="failure-bars">{Object.entries(failures).map(([name, value]) => <div className="failure-row" key={name}><div><span>{name.replaceAll('_', ' ')}</span><strong>{value}</strong></div><div className="bar-track"><i style={{ width: `${(value / maxFailure) * 100}%` }} /></div></div>)}</div> : <div className="empty-state"><div><ShieldCheck size={22} /></div><strong>No failures recorded</strong><span>Failure categories will appear here as requests are processed.</span></div>}</section></div>

    <section className="card trace-card">
      <div className="ops-card-header"><div><h2>How the model works · Stage-by-stage architecture &amp; results</h2><p>Inspect each pipeline level, evaluation metrics, and run a live level-by-level diagnostic</p></div><Layers size={18} className="muted-icon" /></div>
      <div className="ops-levels-grid">
        {levels.map((lvl) => <article className="ops-level-card" key={lvl.level}>
          <div className="ops-level-top"><span className="ops-level-badge">Level {lvl.level}</span><code>{lvl.module}</code></div>
          <strong>{lvl.name}</strong>
          <p>{lvl.how_it_works}</p>
          <pre className="ops-level-metrics">{JSON.stringify(lvl.metrics, null, 2)}</pre>
        </article>)}
      </div>
      <form className="ops-diag-bar" onSubmit={runDiagnostic}>
        <input value={diagQuery} onChange={(e) => setDiagQuery(e.target.value)} placeholder="Enter a policy question to inspect every pipeline level…" />
        <Button icon={diagBusy ? LoaderCircle : Play} disabled={diagBusy || !diagQuery.trim()}>{diagBusy ? 'Running levels…' : 'Run pipeline test'}</Button>
      </form>
      {diagResult && <div className="ops-diag-results">
        {diagResult.levels?.map((stage) => <div className="ops-diag-stage" key={stage.level}>
          <div className="ops-diag-stage-head"><strong>Level {stage.level} · {stage.name}</strong><span className="trace-status trace-success">{stage.status || stage.llm_mode}</span></div>
          <pre>{JSON.stringify(stage, null, 2)}</pre>
        </div>)}
      </div>}
    </section>

    <section className="card trace-card">
      <div className="ops-card-header">
        <div><h2>Evidently AI observability report</h2><p>Interactive Evidently {evSummary?.evidently_version || '0.7.23'} DataSummary &amp; TextEvals dashboard embedded in UI</p></div>
        <div className="ops-evidently-actions">
          <Select value={evSource} onChange={(e) => setEvSource(e.target.value)}>
            <option value="evaluation">Golden Evaluation (70 cases)</option>
            <option value="traces">Live Assistant Traces</option>
          </Select>
          <Button variant="secondary" icon={evBusy ? LoaderCircle : RefreshCw} onClick={() => loadEvidently(evSource, true)} disabled={evBusy}>{evBusy ? 'Generating…' : 'Refresh report'}</Button>
          <a className="button button-secondary" href={evidentlyReportUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Open HTML</a>
        </div>
      </div>
      {evSummary && <div className="ops-evidently-meta">
        <span>Dataset rows: <strong>{evSummary.row_count}</strong></span>
        <span>Metrics computed: <strong>{evSummary.metrics_count}</strong></span>
        <span>Descriptors: <strong>{evSummary.descriptors?.join(', ')}</strong></span>
        <span>Generated: <strong>{dateLabel(evSummary.generated_at)}</strong></span>
      </div>}
      <div className="evidently-frame-wrap">
        <iframe key={evidentlyReportUrl} title="Evidently AI Report" src={evidentlyReportUrl} className="evidently-frame" />
      </div>
    </section>

    <section className="card trace-card"><div className="ops-card-header"><div><h2>Recent assistant activity</h2><p>Audit traces for policy questions</p></div><span className="trace-count">{traces.length} records</span></div>{traces.length ? <div className="table-wrap"><table><thead><tr><th>Trace ID</th><th>Created</th><th>Employee</th><th>Status</th><th>Steps</th><th>Latency</th><th>Category</th></tr></thead><tbody>{traces.map((row) => <tr key={row.trace_id} onClick={() => get(`/api/v1/traces/${row.trace_id}`).then(setSelected)}><td className="mono">{row.trace_id}</td><td>{dateLabel(row.created_at)}</td><td>{row.employee_id}</td><td><span className={`trace-status trace-${row.status}`}>{row.status}</span></td><td>{row.steps}</td><td>{row.latency_ms} ms</td><td>{row.failure_category || '—'}</td></tr>)}</tbody></table></div> : <div className="table-empty"><FileText size={20} /><strong>No assistant traces yet</strong><span>Queries to the policy assistant will appear here.</span></div>}{selected && <div className="trace-detail"><div><strong>Trace details · {selected.trace_id}</strong><button className="icon-button" onClick={() => setSelected(null)}><X size={16} /></button></div><pre>{JSON.stringify(selected.trace, null, 2)}</pre></div>}</section>
    {policy?.synthetic_document_count > 0 && <div className="ops-disclaimer"><CircleHelp size={15} /> The {policy.synthetic_document_count} loaded GlobalTech policies are synthetic test data. The supplied guide describes {policy.full_corpus_expected_documents} documents; {policy.document_count} are currently loaded.</div>}
  </div>
}

export default App
