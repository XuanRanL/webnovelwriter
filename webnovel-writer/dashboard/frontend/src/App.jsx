import { useState, useEffect, useCallback } from 'react'
import { fetchJSON, subscribeSSE } from './api.js'
import ForceGraph3D from 'react-force-graph-3d'

// ====================================================================
// 主应用
// ====================================================================

export default function App() {
    const [page, setPage] = useState('dashboard')
    const [projectInfo, setProjectInfo] = useState(null)
    const [refreshKey, setRefreshKey] = useState(0)
    const [connected, setConnected] = useState(false)

    const loadProjectInfo = useCallback(() => {
        fetchJSON('/api/project/info')
            .then(setProjectInfo)
            .catch(() => setProjectInfo(null))
    }, [])

    useEffect(() => { loadProjectInfo() }, [loadProjectInfo, refreshKey])

    // SSE 订阅
    useEffect(() => {
        const unsub = subscribeSSE(
            () => {
                setRefreshKey(k => k + 1)
            },
            {
                onOpen: () => setConnected(true),
                onError: () => setConnected(false),
            },
        )
        return () => { unsub(); setConnected(false) }
    }, [])

    const title = projectInfo?.project_info?.title || '未加载'

    return (
        <div className="app-layout">
            <aside className="sidebar">
                <div className="sidebar-header">
                    <h1>📖 Dashboard</h1>
                    <div className="subtitle">{title}</div>
                </div>
                <nav className="sidebar-nav">
                    {NAV_ITEMS.map(item => (
                        <button
                            key={item.id}
                            className={`nav-item ${page === item.id ? 'active' : ''}`}
                            onClick={() => setPage(item.id)}
                        >
                            <span className="icon">{item.icon}</span>
                            <span>{item.label}</span>
                        </button>
                    ))}
                </nav>
                <div className="live-indicator">
                    <span className={`live-dot ${connected ? '' : 'disconnected'}`} />
                    {connected ? '实时同步中' : '未连接'}
                </div>
            </aside>

            <main className="main-content">
                {page === 'dashboard' && <DashboardPage data={projectInfo} key={refreshKey} />}
                {page === 'entities' && <EntitiesPage key={refreshKey} />}
                {page === 'graph' && <GraphPage key={refreshKey} />}
                {page === 'chapters' && <ChaptersPage key={refreshKey} />}
                {page === 'files' && <FilesPage />}
                {page === 'reading' && <ReadingPowerPage key={refreshKey} />}
            </main>
        </div>
    )
}

const NAV_ITEMS = [
    { id: 'dashboard', icon: '📊', label: '数据总览' },
    { id: 'entities', icon: '👤', label: '设定词典' },
    { id: 'graph', icon: '🕸️', label: '关系图谱' },
    { id: 'chapters', icon: '📝', label: '章节一览' },
    { id: 'files', icon: '📁', label: '文档浏览' },
    { id: 'reading', icon: '🔥', label: '追读力' },
]


// ====================================================================
// 页面 1：数据总览
// ====================================================================

function DashboardPage({ data }) {
    if (!data) return <div className="loading">加载中…</div>

    const info = data.project_info || {}
    const progress = data.progress || {}
    const protagonist = data.protagonist_state || {}
    const strand = data.strand_tracker || {}
    const foreshadowing = data.plot_threads?.foreshadowing || []

    const totalWords = progress.total_words || 0
    const targetWords = info.target_words || 2000000
    const pct = targetWords > 0 ? Math.min(100, (totalWords / targetWords * 100)).toFixed(1) : 0

    const unresolvedForeshadow = foreshadowing.filter(f => {
        const s = (f.status || '').toLowerCase()
        return s !== '已回收' && s !== '已兑现' && s !== 'resolved'
    })

    // Strand 历史统计
    const history = strand.history || []
    const strandCounts = { quest: 0, fire: 0, constellation: 0 }
    history.forEach(h => { if (strandCounts[h.strand] !== undefined) strandCounts[h.strand]++ })
    const total = history.length || 1

    return (
        <>
            <div className="page-header">
                <h2>📊 数据总览</h2>
                <span className="card-badge badge-blue">{info.genre || '未知题材'}</span>
            </div>

            <div className="dashboard-grid">
                <div className="card stat-card">
                    <span className="stat-label">总字数</span>
                    <span className="stat-value">{formatNumber(totalWords)}</span>
                    <span className="stat-sub">目标 {formatNumber(targetWords)} 字 · {pct}%</span>
                    <div className="progress-track">
                        <div className="progress-fill" style={{ width: `${pct}%` }} />
                    </div>
                </div>

                <div className="card stat-card">
                    <span className="stat-label">当前章节</span>
                    <span className="stat-value">第 {progress.current_chapter || 0} 章</span>
                    <span className="stat-sub">目标 {info.target_chapters || '?'} 章 · 卷 {progress.current_volume || 1}</span>
                </div>

                <div className="card stat-card">
                    <span className="stat-label">主角状态</span>
                    <span className="stat-value plain">{protagonist.name || '未设定'}</span>
                    <span className="stat-sub">
                        {protagonist.power?.realm || '未知境界'}
                        {protagonist.location?.current ? ` · ${protagonist.location.current}` : ''}
                    </span>
                </div>

                <div className="card stat-card">
                    <span className="stat-label">未回收伏笔</span>
                    <span className="stat-value" style={{ color: unresolvedForeshadow.length > 10 ? 'var(--accent-red)' : 'var(--accent-amber)' }}>
                        {unresolvedForeshadow.length}
                    </span>
                    <span className="stat-sub">总计 {foreshadowing.length} 条伏笔</span>
                </div>
            </div>

            {/* Strand Weave 比例 */}
            <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">
                    <span className="card-title">Strand Weave 节奏分布</span>
                    <span className="card-badge badge-purple">{strand.current_dominant || '?'}</span>
                </div>
                <div className="strand-bar" style={{ marginBottom: 14 }}>
                    <div className="segment strand-quest" style={{ width: `${(strandCounts.quest / total * 100).toFixed(1)}%` }} />
                    <div className="segment strand-fire" style={{ width: `${(strandCounts.fire / total * 100).toFixed(1)}%` }} />
                    <div className="segment strand-constellation" style={{ width: `${(strandCounts.constellation / total * 100).toFixed(1)}%` }} />
                </div>
                <div style={{ display: 'flex', gap: 24, fontSize: 13, color: 'var(--text-secondary)' }}>
                    <span>🔵 Quest {(strandCounts.quest / total * 100).toFixed(0)}%</span>
                    <span>🔴 Fire {(strandCounts.fire / total * 100).toFixed(0)}%</span>
                    <span>🟣 Constellation {(strandCounts.constellation / total * 100).toFixed(0)}%</span>
                </div>
            </div>

            {/* 伏笔列表 */}
            {unresolvedForeshadow.length > 0 ? (
                <div className="card">
                    <div className="card-header">
                        <span className="card-title">⚠️ 待回收伏笔 (Top 20)</span>
                    </div>
                    <table className="data-table">
                        <thead><tr><th>内容</th><th>状态</th><th>埋设章</th></tr></thead>
                        <tbody>
                            {unresolvedForeshadow.slice(0, 20).map((f, i) => (
                                <tr key={i}>
                                    <td className="truncate" style={{ maxWidth: 400 }}>{f.content || f.description || '—'}</td>
                                    <td><span className="card-badge badge-amber">{f.status || '未知'}</span></td>
                                    <td>{f.chapter || f.planted_chapter || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ) : null}
        </>
    )
}


// ====================================================================
// 页面 2：设定词典
// ====================================================================

function EntitiesPage() {
    const [entities, setEntities] = useState([])
    const [typeFilter, setTypeFilter] = useState('')
    const [selected, setSelected] = useState(null)
    const [changes, setChanges] = useState([])

    useEffect(() => {
        fetchJSON('/api/entities', typeFilter ? { type: typeFilter } : {}).then(setEntities).catch(() => { })
    }, [typeFilter])

    useEffect(() => {
        if (selected) {
            fetchJSON('/api/state-changes', { entity: selected.id, limit: 30 }).then(setChanges).catch(() => setChanges([]))
        }
    }, [selected])

    const types = [...new Set(entities.map(e => e.type))].sort()

    return (
        <>
            <div className="page-header">
                <h2>👤 设定词典</h2>
                <span className="card-badge badge-green">{entities.length} 个实体</span>
            </div>

            <div className="filter-group">
                <button className={`filter-btn ${typeFilter === '' ? 'active' : ''}`} onClick={() => setTypeFilter('')}>全部</button>
                {types.map(t => (
                    <button key={t} className={`filter-btn ${typeFilter === t ? 'active' : ''}`} onClick={() => setTypeFilter(t)}>{t}</button>
                ))}
            </div>

            <div style={{ display: 'flex', gap: 20 }}>
                <div style={{ flex: 1 }}>
                    <div className="card">
                        <table className="data-table">
                            <thead><tr><th>名称</th><th>类型</th><th>层级</th><th>首现</th><th>末现</th></tr></thead>
                            <tbody>
                                {entities.map(e => (
                                    <tr
                                        key={e.id}
                                        role="button"
                                        tabIndex={0}
                                        onKeyDown={evt => (evt.key === 'Enter' || evt.key === ' ') && (evt.preventDefault(), setSelected(e))}
                                        onClick={() => setSelected(e)}
                                        style={{ cursor: 'pointer', background: selected?.id === e.id ? 'var(--bg-card-hover)' : undefined }}
                                    >
                                        <td style={{ fontWeight: 600, color: e.is_protagonist ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                                            {e.canonical_name} {e.is_protagonist ? '⭐' : ''}
                                        </td>
                                        <td><span className="card-badge badge-blue">{e.type}</span></td>
                                        <td>{e.tier}</td>
                                        <td>{e.first_appearance || '—'}</td>
                                        <td>{e.last_appearance || '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {selected && (
                    <div style={{ width: 360, minWidth: 320 }}>
                        <div className="card">
                            <div className="card-header">
                                <span className="card-title">{selected.canonical_name}</span>
                                <span className="card-badge badge-purple">{selected.tier}</span>
                            </div>
                            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                                <p><strong>类型：</strong>{selected.type}</p>
                                <p><strong>ID：</strong><code style={{ fontSize: 12, color: 'var(--text-muted)' }}>{selected.id}</code></p>
                                {selected.desc && <p style={{ marginTop: 8 }}>{selected.desc}</p>}
                                {selected.current_json && (
                                    <div style={{ marginTop: 12 }}>
                                        <strong>当前状态：</strong>
                                        <pre style={{ marginTop: 4, padding: 10, background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', fontSize: 12, overflow: 'auto', maxHeight: 200 }}>
                                            {formatJSON(selected.current_json)}
                                        </pre>
                                    </div>
                                )}
                            </div>
                            {changes.length > 0 ? (
                                <div style={{ marginTop: 16 }}>
                                    <div className="card-title" style={{ marginBottom: 8, fontSize: 14 }}>状态变化历史</div>
                                    <table className="data-table">
                                        <thead><tr><th>章</th><th>字段</th><th>变化</th></tr></thead>
                                        <tbody>
                                            {changes.map((c, i) => (
                                                <tr key={i}>
                                                    <td>{c.chapter}</td>
                                                    <td>{c.field}</td>
                                                    <td style={{ fontSize: 12 }}>{c.old_value} → {c.new_value}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : null}
                        </div>
                    </div>
                )}
            </div>
        </>
    )
}


// ====================================================================
// 页面 3：3D 宇宙关系图谱
// ====================================================================

function GraphPage() {
    const [relationships, setRelationships] = useState([])
    const [graphData, setGraphData] = useState({ nodes: [], links: [] })

    useEffect(() => {
        Promise.all([
            fetchJSON('/api/relationships', { limit: 1000 }),
            fetchJSON('/api/entities'),
        ]).then(([rels, ents]) => {
            setRelationships(rels)
            const typeColors = {
                '角色': '#4f8ff7', '地点': '#34d399', '星球': '#22d3ee', '神仙': '#f59e0b',
                '势力': '#8b5cf6', '招式': '#ef4444', '法宝': '#ec4899'
            }
            const relatedIds = new Set()
            rels.forEach(r => { relatedIds.add(r.from_entity); relatedIds.add(r.to_entity) })
            const entityMap = {}
            ents.forEach(e => { entityMap[e.id] = e })

            const nodes = [...relatedIds].map(id => ({
                id,
                name: entityMap[id]?.canonical_name || id,
                val: (entityMap[id]?.tier === 'S' ? 8 : entityMap[id]?.tier === 'A' ? 5 : 2),
                color: typeColors[entityMap[id]?.type] || '#5c6078'
            }))
            const links = rels.map(r => ({
                source: r.from_entity,
                target: r.to_entity,
                name: r.type
            }))
            setGraphData({ nodes, links })
        }).catch(() => { })
    }, [])

    return (
        <>
            <div className="page-header">
                <h2>🕸️ 关系图谱</h2>
                <span className="card-badge badge-blue">{relationships.length} 条引力链接</span>
            </div>
            <div className="card" style={{ padding: 0, overflow: 'hidden', height: 'calc(100vh - 180px)', minHeight: 600 }}>
                <ForceGraph3D
                    graphData={graphData}
                    nodeLabel="name"
                    nodeColor="color"
                    nodeRelSize={6}
                    linkColor={() => 'rgba(139, 92, 246, 0.25)'}
                    linkWidth={1}
                    linkDirectionalParticles={2}
                    linkDirectionalParticleWidth={1.5}
                    linkDirectionalParticleSpeed={d => 0.005 + Math.random() * 0.005}
                    backgroundColor="#080a12"
                    showNavInfo={false}
                />
            </div>
        </>
    )
}



// ====================================================================
// 页面 4：章节一览
// ====================================================================

function ChaptersPage() {
    const [chapters, setChapters] = useState([])

    useEffect(() => {
        fetchJSON('/api/chapters').then(setChapters).catch(() => { })
    }, [])

    const totalWords = chapters.reduce((s, c) => s + (c.word_count || 0), 0)

    return (
        <>
            <div className="page-header">
                <h2>📝 章节一览</h2>
                <span className="card-badge badge-green">{chapters.length} 章 · {formatNumber(totalWords)} 字</span>
            </div>
            <div className="card">
                <table className="data-table">
                    <thead><tr><th>章节</th><th>标题</th><th>字数</th><th>地点</th><th>角色</th></tr></thead>
                    <tbody>
                        {chapters.map(c => (
                            <tr key={c.chapter}>
                                <td style={{ fontWeight: 600 }}>第 {c.chapter} 章</td>
                                <td>{c.title || '—'}</td>
                                <td>{formatNumber(c.word_count || 0)}</td>
                                <td>{c.location || '—'}</td>
                                <td className="truncate" style={{ fontSize: 12, maxWidth: 200 }}>{c.characters || '—'}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {chapters.length === 0 ? <div className="empty-state"><div className="empty-icon">📭</div><p>暂无章节数据</p></div> : null}
            </div>
        </>
    )
}


// ====================================================================
// 页面 5：文档浏览
// ====================================================================

function FilesPage() {
    const [tree, setTree] = useState({})
    const [selectedPath, setSelectedPath] = useState(null)
    const [content, setContent] = useState('')

    useEffect(() => {
        fetchJSON('/api/files/tree').then(setTree).catch(() => { })
    }, [])

    useEffect(() => {
        if (selectedPath) {
            fetchJSON('/api/files/read', { path: selectedPath })
                .then(d => setContent(d.content))
                .catch(() => setContent('[读取失败]'))
        }
    }, [selectedPath])

    return (
        <>
            <div className="page-header">
                <h2>📁 文档浏览</h2>
            </div>
            <div style={{ display: 'flex', gap: 20 }}>
                <div style={{ width: 280, minWidth: 240, maxHeight: '80vh', overflowY: 'auto' }}>
                    {Object.entries(tree).map(([folder, items]) => (
                        <div key={folder} style={{ marginBottom: 12 }}>
                            <div style={{ fontWeight: 600, fontSize: 14, padding: '6px 0', color: 'var(--text-primary)' }}>📂 {folder}</div>
                            <ul className="file-tree">
                                <TreeNodes items={items} selected={selectedPath} onSelect={setSelectedPath} />
                            </ul>
                        </div>
                    ))}
                </div>
                <div style={{ flex: 1 }}>
                    {selectedPath ? (
                        <div>
                            <div style={{ marginBottom: 12, fontSize: 13, color: 'var(--text-muted)' }}>{selectedPath}</div>
                            <div className="file-preview">{content}</div>
                        </div>
                    ) : (
                        <div className="empty-state"><div className="empty-icon">📄</div><p>选择左侧文件以预览内容</p></div>
                    )}
                </div>
            </div>
        </>
    )
}


// ====================================================================
// 页面 6：追读力
// ====================================================================

function ReadingPowerPage() {
    const [data, setData] = useState([])

    useEffect(() => {
        fetchJSON('/api/reading-power', { limit: 50 }).then(setData).catch(() => { })
    }, [])

    return (
        <>
            <div className="page-header">
                <h2>🔥 追读力分析</h2>
                <span className="card-badge badge-amber">{data.length} 章数据</span>
            </div>
            <div className="card">
                <table className="data-table">
                    <thead><tr><th>章节</th><th>钩子类型</th><th>钩子强度</th><th>过渡章</th><th>Override</th><th>债务余额</th></tr></thead>
                    <tbody>
                        {data.map(r => (
                            <tr key={r.chapter}>
                                <td style={{ fontWeight: 600 }}>第 {r.chapter} 章</td>
                                <td>{r.hook_type || '—'}</td>
                                <td>
                                    <span className={`card-badge ${r.hook_strength === 'strong' ? 'badge-green' : r.hook_strength === 'weak' ? 'badge-red' : 'badge-amber'}`}>
                                        {r.hook_strength || '—'}
                                    </span>
                                </td>
                                <td>{r.is_transition ? '✅' : '—'}</td>
                                <td>{r.override_count || 0}</td>
                                <td style={{ color: r.debt_balance > 0 ? 'var(--accent-red)' : 'var(--text-muted)' }}>{(r.debt_balance || 0).toFixed(2)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {data.length === 0 ? <div className="empty-state"><div className="empty-icon">🔥</div><p>暂无追读力数据</p></div> : null}
            </div>
        </>
    )
}


// ====================================================================
// 子组件：文件树递归
// ====================================================================

function TreeNodes({ items, selected, onSelect, depth = 0 }) {
    const [expanded, setExpanded] = useState({})
    if (!items || items.length === 0) return null

    return items.map((item, i) => {
        const key = item.path || `${depth}-${i}`
        if (item.type === 'dir') {
            const isOpen = expanded[key]
            return (
                <li key={key}>
                    <div
                        className="tree-item"
                        role="button"
                        tabIndex={0}
                        onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setExpanded(prev => ({ ...prev, [key]: !prev[key] })))}
                        onClick={() => setExpanded(prev => ({ ...prev, [key]: !prev[key] }))}
                    >
                        <span className="tree-icon">{isOpen ? '📂' : '📁'}</span>
                        <span>{item.name}</span>
                    </div>
                    {isOpen && item.children && (
                        <ul className="tree-children">
                            <TreeNodes items={item.children} selected={selected} onSelect={onSelect} depth={depth + 1} />
                        </ul>
                    )}
                </li>
            )
        }
        return (
            <li key={key}>
                <div
                    className={`tree-item ${selected === item.path ? 'active' : ''}`}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onSelect(item.path))}
                    onClick={() => onSelect(item.path)}
                >
                    <span className="tree-icon">📄</span>
                    <span>{item.name}</span>
                </div>
            </li>
        )
    })
}


// ====================================================================
// 辅助：数字格式化
// ====================================================================

function formatNumber(n) {
    if (n >= 10000) return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(n / 10000) + ' 万'
    return new Intl.NumberFormat('zh-CN').format(n)
}

function formatJSON(str) {
    try {
        return JSON.stringify(JSON.parse(str), null, 2)
    } catch {
        return str
    }
}
