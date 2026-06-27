const app = document.querySelector('#app')

const STATUS_TONE = {
  completed: 'green',
  partial: 'orange',
  not_started: 'gray',
  locked: 'red',
  blocked: 'red',
  packet_only: 'blue',
  done: 'green',
  passed: 'green',
  active: 'blue',
  live: 'blue',
  tracked: 'blue',
  observed: 'blue',
  planned: 'gray',
  pending: 'orange',
  failed: 'red',
  diverged: 'red',
  local_behind: 'orange',
  local_ahead: 'blue',
  up_to_date: 'green',
  remote_differs: 'orange',
}

const STATUS_LABEL = {
  completed: 'Completed',
  partial: 'Partial',
  not_started: 'Future',
  locked: 'Locked',
  blocked: 'Blocked',
  packet_only: 'Packet only',
}

const PHASE_TONE = {
  'v0.1': 'green',
  'v0.1.1': 'green',
  'v0.2': 'blue',
  'v0.3': 'blue',
  'v0.4': 'blue',
  'v0.5': 'purple',
  'v0.6': 'purple',
  'v0.7': 'purple',
  'v0.8': 'purple',
  'v0.9': 'purple',
  'v1.0': 'orange',
  future: 'gray',
}

let state = {
  status: null,
  git: null,
  kpis: null,
  statusError: null,
  gitError: null,
  kpiError: null,
  filter: 'all',
  query: '',
  selected: null,
  selectedMap: null,
  loadedAt: null,
}

function esc(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function tone(value, fallback = 'gray') {
  return STATUS_TONE[String(value || '').toLowerCase()] || fallback
}

function badge(label, toneName = 'gray') {
  return `<span class="badge ${esc(toneName)}">${esc(label || 'unknown')}</span>`
}

function list(items) {
  if (!items || !items.length) return '<p class="empty">None listed.</p>'
  return `<ul>${items.map(item => `<li>${esc(item)}</li>`).join('')}</ul>`
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function normalizeTitle(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[—:]/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function canonicalGoalId(value) {
  const match = String(value || '').toUpperCase().match(/GOAL-\d{3}/)
  return match ? match[0] : ''
}

function blockGoalId(block) {
  return canonicalGoalId(block?.title) || canonicalGoalId(block?.id)
}

function goalNumber(goalId) {
  const match = String(goalId || '').match(/GOAL-(\d{3})/)
  return match ? Number(match[1]) : null
}

function packetBlockFromGoal(goal, index) {
  const title = goal.title || goal.name || goal.id || `Goal packet ${index + 1}`
  const packetId = String(goal.id || goal.name || `goal-${index + 1}`)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return {
    id: `packet_${packetId || index + 1}`,
    title,
    phase: goal.phase || goal.version || 'future',
    status: 'packet_only',
    completion_pct: 0,
    completed: [],
    pending: ['Not yet tracked in PMO status ledger.'],
    risks: ['Packet exists without curated PMO progress state.'],
    evidence: goal.path ? [goal.path] : [],
    next_goal: 'Add this packet to docs/pmo/status/current_status.json when it becomes tracked.',
    source: 'goal_packet',
  }
}

function getBlocks() {
  const fromBlocks = asArray(state.status?.blocks)
  const seenTitles = new Set(fromBlocks.map(block => normalizeTitle(block.title)))
  const seenGoalIds = new Set(fromBlocks.map(blockGoalId).filter(Boolean))
  const packetBlocks = asArray(state.status?.goals)
    .map(packetBlockFromGoal)
    .filter(block => {
      const id = blockGoalId(block)
      if (id && seenGoalIds.has(id)) return false
      return !seenTitles.has(normalizeTitle(block.title))
    })
  return [...fromBlocks, ...packetBlocks]
}

function goalAudit() {
  const blocks = asArray(state.status?.blocks)
  const goals = asArray(state.status?.goals)
  const trackedIds = [...new Set(blocks.map(blockGoalId).filter(Boolean))]
  const trackedNumbers = trackedIds.map(goalNumber).filter(number => number !== null && number < 100).sort((a, b) => a - b)
  const maxTracked = trackedNumbers.length ? Math.max(...trackedNumbers) : 0
  const missing = []
  for (let index = 0; index <= maxTracked; index += 1) {
    const label = `GOAL-${String(index).padStart(3, '0')}`
    if (!trackedIds.includes(label)) missing.push(label)
  }

  const packetIdCounts = new Map()
  goals.forEach(goal => {
    const id = canonicalGoalId(goal.id) || canonicalGoalId(goal.title) || canonicalGoalId(goal.name)
    if (id) packetIdCounts.set(id, (packetIdCounts.get(id) || 0) + 1)
  })
  const hiddenPacketIds = [...packetIdCounts.keys()].filter(id => trackedIds.includes(id)).sort()
  const duplicatePacketIds = [...packetIdCounts.entries()].filter(([, count]) => count > 1).map(([id]) => id).sort()
  const packetOnlyCount = getBlocks().filter(block => block.source === 'goal_packet').length

  return {
    trackedCount: trackedIds.length,
    packetOnlyCount,
    missing,
    hiddenPacketIds,
    duplicatePacketIds,
  }
}

function projectName() {
  return state.status?.project || 'Nornyx Developer PMO Portal'
}

function sourceRepo() {
  return state.status?.source_of_truth?.repository || state.status?.source_of_truth?.repo || state.git?.local?.github_web_url || state.git?.local?.remote_url || 'not configured'
}

function sourceBranch() {
  return state.status?.source_of_truth?.branch || state.git?.local?.branch || 'unknown'
}

function findSelected() {
  return getBlocks().find(block => block.id === state.selected) || null
}

function filteredBlocks() {
  const q = state.query.trim().toLowerCase()
  return getBlocks()
    .filter(block => state.filter === 'all' || block.status === state.filter || block.phase === state.filter)
    .filter(block => !q || JSON.stringify(block).toLowerCase().includes(q))
}

function sortedVisionMaps() {
  const maps = asArray(state.status?.vision_map?.maps)
  const order = asArray(state.status?.vision_map?.priority_order)
  const explicit = new Map(order.map((id, index) => [id, index]))
  const priorityWeight = value => value === 'P0' ? 0 : value === 'P1' ? 1 : value === 'P2' ? 2 : 3
  return [...maps].sort((a, b) => {
    if (explicit.has(a.id) || explicit.has(b.id)) return (explicit.get(a.id) ?? 999) - (explicit.get(b.id) ?? 999)
    return priorityWeight(a.priority) - priorityWeight(b.priority)
  })
}

function renderError(message) {
  app.innerHTML = `
    <section class="error-card">
      <h1>Nornyx Developer PMO Portal</h1>
      <p>${esc(message)}</p>
      <p class="small">Run with: <code>python apps/nornyx-dev-pmo-portal/server.py --enable-all</code></p>
      <p class="small">For local-only PMO without remote Git calls: <code>python apps/nornyx-dev-pmo-portal/server.py --enable-api --enable-git-api</code></p>
    </section>
  `
}

function renderHero() {
  const overall = state.status?.summary?.overall_status || state.status?.status || state.status?.github_status?.overall || 'active'
  return `
    <section class="hero">
      <div>
        <p class="eyebrow">Developer PMO Portal · Local command center</p>
        <h1>${esc(projectName())}</h1>
        <p class="sub">
          Box-based control room for Nornyx: local repository truth, remote GitHub signal,
          vision maps, evidence readiness, risks, and next execution focus.
        </p>
      </div>
      <div class="heroBox">
        <span>Current state</span>
        <strong>${esc(overall)}</strong>
        <small>Loaded ${esc(state.loadedAt || 'not yet loaded')}</small>
        <button id="refreshNow" class="button">Refresh now</button>
      </div>
    </section>
  `
}

function renderExecutiveBoxes() {
  const nextGoal = state.status?.summary?.next_recommended_goal || asArray(state.status?.next_actions)[0] || 'GOAL-001 — Core block spec freeze'
  const blocks = getBlocks()
  const maps = sortedVisionMaps()
  const evidenceCount = asArray(state.status?.evidence).length + blocks.reduce((sum, b) => sum + asArray(b.evidence).length, 0)
  return `
    <section class="boxGrid executiveGrid">
      <div class="box p0">
        <span>Repository</span>
        <strong>${esc(sourceRepo())}</strong>
        <small>Source of truth visible from PMO + Git status.</small>
      </div>
      <div class="box">
        <span>Branch</span>
        <strong>${esc(sourceBranch())}</strong>
        <small>Current delivery branch.</small>
      </div>
      <div class="box">
        <span>Next focus</span>
        <strong>${esc(nextGoal)}</strong>
        <small>Do not expand scope beyond approved goal.</small>
      </div>
      <div class="box">
        <span>Vision maps</span>
        <strong>${maps.length}</strong>
        <small>P0/P1/P2 strategy boxes loaded.</small>
      </div>
      <div class="box">
        <span>Work cards</span>
        <strong>${blocks.length}</strong>
        <small>Goals/tasks from PMO status.</small>
      </div>
      <div class="box">
        <span>Evidence links</span>
        <strong>${evidenceCount}</strong>
        <small>Evidence prevents false completion.</small>
      </div>
    </section>
  `
}

function renderGoalAudit() {
  const audit = goalAudit()
  const missingText = audit.missing.length ? audit.missing.join(', ') : 'none'
  const hiddenText = audit.hiddenPacketIds.length ? audit.hiddenPacketIds.join(', ') : 'none'
  const duplicateText = audit.duplicatePacketIds.length ? audit.duplicatePacketIds.join(', ') : 'none'

  return `
    <section class="card">
      <div class="sectionHead">
        <div>
          <p class="eyebrow">Roadmap numbering</p>
          <h2>Goal Ledger Clarity</h2>
        </div>
        <div class="badges">
          ${badge(`${audit.trackedCount} tracked`, 'green')}
          ${badge(`${audit.packetOnlyCount} packet-only`, audit.packetOnlyCount ? 'blue' : 'gray')}
        </div>
      </div>
      <div class="boxGrid auditGrid">
        <div class="box">
          <span>Skipped numbers</span>
          <strong>${esc(audit.missing.length ? `${audit.missing.length}` : '0')}</strong>
          <small>${esc(missingText)}</small>
        </div>
        <div class="box">
          <span>Tracked packet files hidden</span>
          <strong>${esc(audit.hiddenPacketIds.length)}</strong>
          <small>${esc(hiddenText)}</small>
        </div>
        <div class="box">
          <span>Duplicate packet IDs</span>
          <strong>${esc(audit.duplicatePacketIds.length)}</strong>
          <small>${esc(duplicateText)}</small>
        </div>
      </div>
    </section>
  `
}

function renderGitStatus() {
  const git = state.git
  if (!git) {
    return `
      <section class="card">
        <div class="sectionHead">
          <div>
            <p class="eyebrow">Local + remote Git status</p>
            <h2>Repository Signal</h2>
          </div>
          ${badge(state.gitError ? 'Git API disabled' : 'Loading', state.gitError ? 'orange' : 'blue')}
        </div>
        <p class="small">${esc(state.gitError || 'Reading local Git status...')}</p>
      </section>
    `
  }

  const local = git.local || {}
  const remote = git.remote || {}
  const localDirtyTone = local.dirty ? 'orange' : 'green'
  const remoteTone = tone(remote.status)
  const remoteStatus = remote.checked ? remote.status : 'remote disabled'

  return `
    <section class="card">
      <div class="sectionHead">
        <div>
          <p class="eyebrow">Direct repository update</p>
          <h2>Local + Remote GitHub Status</h2>
        </div>
        <div class="badges">
          ${badge(local.dirty ? 'working tree dirty' : 'clean working tree', localDirtyTone)}
          ${badge(remoteStatus, remote.checked ? remoteTone : 'gray')}
        </div>
      </div>

      <div class="boxGrid gitGrid">
        <div class="box p0">
          <span>Local branch</span>
          <strong>${esc(local.branch || 'unknown')}</strong>
          <small>${esc(local.upstream || 'no upstream configured')}</small>
        </div>
        <div class="box">
          <span>Local commit</span>
          ${local.commit_url ? `<a href="${esc(local.commit_url)}" target="_blank" rel="noreferrer">${esc(local.short_sha || 'unknown')}</a>` : `<strong>${esc(local.short_sha || 'unknown')}</strong>`}
          <small>${esc(local.commit_message || 'no commit message')}</small>
        </div>
        <div class="box">
          <span>Remote commit</span>
          <strong>${esc(remote.short_sha || 'not checked')}</strong>
          <small>${esc(remote.error || (remote.checked ? 'remote branch observed' : 'start with --enable-remote-git'))}</small>
        </div>
        <div class="box">
          <span>Ahead / behind</span>
          <strong>${Number(local.ahead || 0)} / ${Number(local.behind || 0)}</strong>
          <small>Compared with upstream when configured.</small>
        </div>
        <div class="box">
          <span>Changed files</span>
          <strong>${Number(local.total_changed || 0)}</strong>
          <small>${Number(local.staged_count || 0)} staged · ${Number(local.modified_count || 0)} modified · ${Number(local.untracked_count || 0)} untracked</small>
        </div>
        <div class="box">
          <span>Remote URL</span>
          ${local.github_web_url ? `<a href="${esc(local.github_web_url)}" target="_blank" rel="noreferrer">${esc(local.github_web_url)}</a>` : `<strong>${esc(local.remote_url || 'not configured')}</strong>`}
          <small>Read-only git CLI. No GitHub token required.</small>
        </div>
      </div>

      <p class="small">Git checked at ${esc(git.checked_at)} · Safety: ${esc(git.safety?.mode)} · shell execution: ${esc(git.safety?.shell_execution)}</p>
    </section>
  `
}

function renderKpiPanel() {
  const kpis = state.kpis
  if (!kpis) {
    return `
      <section class="card">
        <div class="sectionHead">
          <div>
            <p class="eyebrow">KPI quality signal</p>
            <h2>Local Metrics</h2>
          </div>
          ${badge(state.kpiError ? 'KPI API disabled' : 'Loading', state.kpiError ? 'orange' : 'blue')}
        </div>
        <p class="small">${esc(state.kpiError || 'Reading local KPI metrics...')}</p>
      </section>
    `
  }

  const repo = kpis.repo_kpis || {}
  const evidence = kpis.current_goal_evidence || {}
  return `
    <section class="card">
      <div class="sectionHead">
        <div>
          <p class="eyebrow">KPI quality signal</p>
          <h2>Agentic Development Readiness</h2>
        </div>
        <div class="badges">
          ${badge(repo.agentic_dev_readiness_status || 'unknown', tone(repo.agentic_dev_readiness_status))}
          ${badge(evidence.status || 'evidence unknown', tone(evidence.status))}
        </div>
      </div>

      <div class="boxGrid kpiGrid">
        <div class="box p0">
          <span>Readiness score</span>
          <strong>${Number(repo.agentic_dev_readiness_score || 0)} / ${Number(repo.agentic_dev_readiness_max || 100)}</strong>
          <small>Local repo structure, tests, examples, evidence, and quality scripts.</small>
        </div>
        <div class="box">
          <span>Goal packets</span>
          <strong>${Number(repo.goals_count || 0)}</strong>
          <small>${Number(repo.evidence_goal_dirs_count || 0)} evidence goal folders.</small>
        </div>
        <div class="box">
          <span>Tests</span>
          <strong>${Number(repo.test_file_count || 0)}</strong>
          <small>${Number(repo.dev_check_script_count || 0)} local check scripts.</small>
        </div>
        <div class="box">
          <span>Examples</span>
          <strong>${Number(repo.nyx_example_count || 0)}</strong>
          <small>${Number(repo.triage_candidate_count || 0)} triage candidate files.</small>
        </div>
        <div class="box">
          <span>GOAL-029 evidence</span>
          <strong>${Number(evidence.percent || 0)}%</strong>
          <small>${Number(evidence.score || 0)} / ${Number(evidence.max_score || 0)} evidence points.</small>
        </div>
        <div class="box">
          <span>Safety mode</span>
          <strong>${esc(kpis.safety?.mode || 'read only')}</strong>
          <small>writes: ${esc(kpis.safety?.writes || 'disabled')} · network: ${esc(kpis.safety?.network || 'disabled')}</small>
        </div>
      </div>
      <p class="small">KPI checked at ${esc(kpis.checked_at)} · local read-only metrics only.</p>
    </section>
  `
}

function renderVisionMap() {
  const maps = sortedVisionMaps()
  const selected = maps.find(map => map.id === state.selectedMap) || maps[0]

  if (!maps.length) {
    return `
      <section class="card">
        <div class="sectionHead">
          <div>
            <p class="eyebrow">Inspiring vision map</p>
            <h2>Vision Map</h2>
          </div>
          ${badge('no map data', 'orange')}
        </div>
        <p class="small">Add <code>vision_map.maps</code> to docs/pmo/status/current_status.json.</p>
      </section>
    `
  }

  return `
    <section class="card visionCard">
      <div class="sectionHead">
        <div>
          <p class="eyebrow">Inspiring vision map</p>
          <h2>North Star → Delivery Gates → Evidence</h2>
        </div>
        <div class="badges">
          ${badge(`${maps.length} maps`, 'blue')}
          ${badge(selected.priority || 'P?', tone(selected.status))}
        </div>
      </div>

      <div class="mapTabs">
        ${maps.map(map => `
          <button class="mapTab ${selected.id === map.id ? 'active' : ''}" data-map-id="${esc(map.id)}">
            <strong>${esc(map.title)}</strong>
            <span>${esc(map.priority)} · ${esc(map.status)}</span>
          </button>
        `).join('')}
      </div>

      <article class="visionFocus">
        <div>
          <span class="mapPriority">${esc(selected.priority)}</span>
          <h3>${esc(selected.title)}</h3>
          <p>${esc(selected.purpose)}</p>
        </div>
        <div class="visionNodes">
          ${asArray(selected.nodes).length ? asArray(selected.nodes).map(node => `
            <div class="visionNode ${tone(node.status)}">
              <div class="nodeTop">
                <span>${esc(node.kind)}</span>
                <strong>${esc(node.status)}</strong>
              </div>
              <h4>${esc(node.label)}</h4>
              <p>${esc(node.summary || '')}</p>
              ${asArray(node.evidence).length ? `<div class="evidenceLinks">${node.evidence.map(e => `<a href="${esc(e)}" target="_blank" rel="noreferrer">evidence</a>`).join('')}</div>` : ''}
            </div>
          `).join('') : `
            <div class="visionNode">
              <h4>Awaiting detail</h4>
              <p>This vision map is selected but has no nodes yet.</p>
            </div>
          `}
        </div>
      </article>
    </section>
  `
}

function renderToolbar() {
  return `
    <section class="toolbar">
      <input id="query" placeholder="Search goals, risks, evidence…" value="${esc(state.query)}" />
      <select id="filter">
        ${['all','completed','partial','packet_only','not_started','locked','blocked','active','planned','v0.1','v0.1.1','v0.2','v0.3','v0.4','v0.5','v0.6','v0.7','v0.8','v0.9','v1.0'].map(v => `<option value="${v}" ${state.filter === v ? 'selected' : ''}>${v}</option>`).join('')}
      </select>
    </section>
  `
}

function renderWorkCards() {
  const blocks = filteredBlocks()
  if (!blocks.length) {
    return `
      <section class="card">
        <div class="sectionHead">
          <div>
            <p class="eyebrow">Goal boxes</p>
            <h2>Execution Board</h2>
          </div>
          ${badge('empty', 'orange')}
        </div>
        <p class="small">No <code>blocks</code> or <code>goals</code> are currently listed in PMO status. Vision maps and Git status are still visible.</p>
      </section>
    `
  }

  return `
    <section class="grid">
      ${blocks.map(block => {
        const pct = Math.max(0, Math.min(100, Number(block.completion_pct || 0)))
        return `
          <button class="card goal-card" data-id="${esc(block.id)}">
            <div class="goal-title">
              <h3>${esc(block.title)}</h3>
              <div>${badge(block.phase || 'phase', PHASE_TONE[block.phase] || tone(block.status))}</div>
            </div>
            <div class="meta-row">
              ${badge(STATUS_LABEL[block.status] || block.status, tone(block.status))}
              <span class="small"><strong>${pct}%</strong> complete</span>
            </div>
            <div class="progress"><span style="width:${pct}%"></span></div>
            <div class="small">✓ ${asArray(block.completed).length} done · ⏳ ${asArray(block.pending).length} pending · ⚠️ ${asArray(block.risks).length} risks${block.source === 'goal_packet' ? ' · packet' : ''}</div>
            <div class="next">Next: ${esc(block.next_goal || 'Not defined')}</div>
          </button>
        `
      }).join('')}
    </section>
  `
}

function renderModal(block) {
  return `
    <section class="modal-backdrop">
      <div class="modal">
        <div class="modal-head">
          <div>
            <h2>${esc(block.title)}</h2>
            <div class="badges" style="justify-content:flex-start">
              ${badge(block.phase || 'phase', PHASE_TONE[block.phase] || 'gray')}
              ${badge(STATUS_LABEL[block.status] || block.status, tone(block.status))}
              ${badge(`${Number(block.completion_pct || 0)}%`, 'blue')}
            </div>
          </div>
          <button class="close" aria-label="Close">✕</button>
        </div>
        <div class="progress"><span style="width:${Math.max(0, Math.min(100, block.completion_pct || 0))}%"></span></div>
        <div class="detail-grid">
          <div class="kv"><small>Completed</small>${list(block.completed)}</div>
          <div class="kv"><small>Pending</small>${list(block.pending)}</div>
          <div class="kv"><small>Risks</small>${list(block.risks)}</div>
        </div>
        <div class="card soft-card">
          <h2>Evidence</h2>
          ${list(block.evidence)}
        </div>
        <div class="card soft-card">
          <h2>Next recommended goal</h2>
          <p>${esc(block.next_goal || 'Not defined')}</p>
        </div>
      </div>
    </section>
  `
}

function bindEvents() {
  document.querySelector('#refreshNow')?.addEventListener('click', () => boot())
  document.querySelector('#query')?.addEventListener('input', event => {
    state.query = event.target.value
    render()
  })
  document.querySelector('#filter')?.addEventListener('change', event => {
    state.filter = event.target.value
    render()
  })
  document.querySelectorAll('.goal-card').forEach(card => {
    card.addEventListener('click', () => {
      state.selected = card.getAttribute('data-id')
      render()
    })
  })
  document.querySelectorAll('.mapTab').forEach(tab => {
    tab.addEventListener('click', () => {
      state.selectedMap = tab.getAttribute('data-map-id')
      render()
    })
  })
  document.querySelector('.modal-backdrop')?.addEventListener('click', event => {
    if (event.target.classList.contains('modal-backdrop')) {
      state.selected = null
      render()
    }
  })
  document.querySelector('.close')?.addEventListener('click', () => {
    state.selected = null
    render()
  })
}

function render() {
  if (!state.status && state.statusError) {
    renderError(state.statusError)
    return
  }
  if (!state.status) {
    app.innerHTML = '<section class="loading">Loading Nornyx Developer PMO Portal…</section>'
    return
  }

  const selectedBlock = findSelected()
  app.innerHTML = `
    ${renderHero()}
    ${renderExecutiveBoxes()}
    ${renderGoalAudit()}
    ${renderGitStatus()}
    ${renderKpiPanel()}
    ${renderVisionMap()}
    ${renderToolbar()}
    ${renderWorkCards()}
    <p class="footer">Source: docs/pmo/status/current_status.json · Git source: read-only local git CLI · Developer-only local portal.</p>
    ${selectedBlock ? renderModal(selectedBlock) : ''}
  `
  bindEvents()
}

async function fetchJson(url) {
  const response = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${body}`)
  }
  return response.json()
}

async function boot() {
  try {
    state.status = await fetchJson('/api/dev/pmo/status')
    state.statusError = null
    state.loadedAt = new Date().toISOString()
  } catch (err) {
    state.statusError = String(err)
  }

  try {
    state.git = await fetchJson('/api/dev/git/status')
    state.gitError = null
  } catch (err) {
    state.git = null
    state.gitError = String(err)
  }

  try {
    state.kpis = await fetchJson('/api/dev/kpi/status')
    state.kpiError = null
  } catch (err) {
    state.kpis = null
    state.kpiError = String(err)
  }

  render()
}

window.addEventListener('keydown', event => {
  if (event.key === 'Escape' && state.selected) {
    state.selected = null
    render()
  }
})

boot()
window.setInterval(boot, 15000)
