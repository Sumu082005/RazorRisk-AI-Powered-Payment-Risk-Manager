/**
 * Audit Log View Component.
 * Connects to GET /api/v1/audit/logs.
 * Provides immutable, filterable audit trail for risk evaluations, webhooks, and manual overrides.
 * Strict security guardrails: never displays secret keys or authorization values.
 */

const AuditLogView = {
  currentEventType: '',
  currentAction: '',
  currentSearch: '',
  currentOffset: 0,
  limit: 15,

  async render(container) {
    container.innerHTML = `
      <div class="space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 class="text-2xl font-bold text-on-surface tracking-tight">Immutable Audit Log</h2>
            <p class="text-sm text-on-surface-variant mt-1">Append-only compliance audit trail recording all policy decisions, webhooks, and manual interventions.</p>
          </div>
          <button id="audit-refresh-btn" class="h-9 px-3 bg-surface-container-lowest border border-outline-variant rounded text-sm text-on-surface hover:bg-surface-variant flex items-center gap-1.5 transition-colors">
            <span class="material-symbols-outlined text-[18px]">refresh</span>
            <span>Refresh Logs</span>
          </button>
        </div>

        <!-- Filter Toolbar -->
        <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="flex flex-wrap items-center gap-3">
            <!-- Event Type Filter -->
            <select id="audit-event-filter" class="h-9 text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 text-on-surface outline-none focus:border-primary">
              <option value="">All Event Types</option>
              <option value="INTERNAL_RISK_SCORE">INTERNAL_RISK_SCORE (ML & Policy)</option>
              <option value="RAZORPAY_WEBHOOK">RAZORPAY_WEBHOOK_* (Payment Events)</option>
              <option value="MANUAL_REVIEW_DECISION">MANUAL_REVIEW_DECISION (Analyst Overrides)</option>
            </select>

            <!-- Action Filter -->
            <select id="audit-action-filter" class="h-9 text-xs bg-surface-container-low border border-outline-variant rounded px-2.5 text-on-surface outline-none focus:border-primary">
              <option value="">All Actions</option>
              <option value="APPROVE">APPROVE</option>
              <option value="REVIEW">REVIEW</option>
              <option value="BLOCK">BLOCK</option>
            </select>
          </div>

          <!-- Transaction ID search -->
          <div class="relative w-72">
            <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">search</span>
            <input id="audit-search-input" type="text" placeholder="Filter by Transaction ID..." class="w-full pl-9 pr-3 h-9 text-xs bg-surface-container-low border border-outline-variant rounded focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all">
          </div>
        </div>

        <!-- Audit Table -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead class="bg-surface-container-low font-bold uppercase text-on-surface-variant border-b border-outline-variant tracking-wider">
                <tr>
                  <th class="py-3 px-4">Audit ID / Timestamp</th>
                  <th class="py-3 px-4">Transaction / Decision ID</th>
                  <th class="py-3 px-4">Event Type</th>
                  <th class="py-3 px-4">Action</th>
                  <th class="py-3 px-4">Risk Score</th>
                  <th class="py-3 px-4">Confidence</th>
                  <th class="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody id="audit-table-body" class="divide-y divide-outline-variant divide-opacity-50">
                <tr>
                  <td colspan="7" class="p-8 text-center text-on-surface-variant">
                    <div class="flex items-center justify-center gap-2">
                      <span class="material-symbols-outlined animate-spin">progress_activity</span>
                      <span>Loading audit trail...</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Bar -->
          <div class="p-3 bg-surface-container-low border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-variant">
            <span id="audit-page-info">Showing 0 of 0</span>
            <div class="flex items-center gap-1">
              <button id="audit-prev-btn" class="px-2.5 py-1.5 border border-outline-variant rounded bg-surface-container-lowest hover:bg-surface-variant disabled:opacity-40" disabled>Previous</button>
              <button id="audit-next-btn" class="px-2.5 py-1.5 border border-outline-variant rounded bg-surface-container-lowest hover:bg-surface-variant disabled:opacity-40" disabled>Next</button>
            </div>
          </div>
        </div>

        <!-- Detail Drawer / Modal for Structured Details -->
        <div id="audit-detail-modal" class="fixed inset-0 bg-black/40 z-50 hidden flex items-center justify-center p-4 modal-backdrop">
          <div class="bg-surface-container-lowest rounded-lg border border-outline-variant max-w-2xl w-full p-6 shadow-xl modal-content space-y-4 max-h-[85vh] flex flex-col">
            <div class="flex items-center justify-between border-b border-outline-variant pb-3">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary">history_edu</span>
                <h3 class="text-base font-bold text-on-surface">Audit Event Payload</h3>
              </div>
              <button onclick="document.getElementById('audit-detail-modal').classList.add('hidden')" class="p-1 text-on-surface-variant hover:text-on-surface rounded">
                <span class="material-symbols-outlined">close</span>
              </button>
            </div>
            <div class="flex-1 overflow-y-auto">
              <pre id="audit-json-viewer" class="bg-surface-container-low p-4 rounded text-xs font-mono text-on-surface overflow-x-auto border border-outline-variant"></pre>
            </div>
            <div class="flex justify-end pt-2 border-t border-outline-variant">
              <button onclick="document.getElementById('audit-detail-modal').classList.add('hidden')" class="px-4 py-2 bg-surface-container hover:bg-surface-variant text-on-surface rounded text-xs font-semibold">
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    this.bindEvents();
    await this.loadLogs();
  },

  bindEvents() {
    document.getElementById('audit-refresh-btn')?.addEventListener('click', () => {
      this.loadLogs();
    });

    document.getElementById('audit-event-filter')?.addEventListener('change', (e) => {
      this.currentEventType = e.target.value;
      this.currentOffset = 0;
      this.loadLogs();
    });

    document.getElementById('audit-action-filter')?.addEventListener('change', (e) => {
      this.currentAction = e.target.value;
      this.currentOffset = 0;
      this.loadLogs();
    });

    let searchTimeout = null;
    document.getElementById('audit-search-input')?.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        this.currentSearch = e.target.value.trim();
        this.currentOffset = 0;
        this.loadLogs();
      }, 300);
    });

    document.getElementById('audit-prev-btn')?.addEventListener('click', () => {
      if (this.currentOffset >= this.limit) {
        this.currentOffset -= this.limit;
        this.loadLogs();
      }
    });

    document.getElementById('audit-next-btn')?.addEventListener('click', () => {
      this.currentOffset += this.limit;
      this.loadLogs();
    });
  },

  async loadLogs() {
    const tbody = document.getElementById('audit-table-body');
    const pageInfo = document.getElementById('audit-page-info');
    const prevBtn = document.getElementById('audit-prev-btn');
    const nextBtn = document.getElementById('audit-next-btn');
    if (!tbody) return;

    try {
      const params = {
        limit: this.limit,
        offset: this.currentOffset
      };
      if (this.currentAction) params.action = this.currentAction;
      if (this.currentSearch) params.transaction_id = this.currentSearch;

      const data = await window.ApiClient.getAuditLogs(params);
      let items = data.items || [];
      const total = data.total || 0;

      // Client-side event type prefix filter if selected
      if (this.currentEventType) {
        items = items.filter(i => i.event_type.startsWith(this.currentEventType));
      }

      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="p-12 text-center text-on-surface-variant">
              <span class="material-symbols-outlined text-4xl text-outline-variant mb-2">history_toggle_off</span>
              <p class="font-semibold text-on-surface">No audit records found</p>
              <p class="text-xs text-on-surface-variant mt-1">Try resetting the filters or executing a risk evaluation.</p>
            </td>
          </tr>
        `;
        if (pageInfo) pageInfo.textContent = 'Showing 0 of 0';
        if (prevBtn) prevBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = true;
        return;
      }

      tbody.innerHTML = items.map(log => {
        let badgeClass = 'bg-surface-variant text-on-surface-variant';
        if (log.action === 'APPROVE') {
          badgeClass = 'bg-status-approve-bg text-status-approve-text border border-status-approve-text/20';
        } else if (log.action === 'REVIEW') {
          badgeClass = 'bg-status-review-bg text-status-review-text border border-status-review-text/20';
        } else if (log.action === 'BLOCK') {
          badgeClass = 'bg-status-block-bg text-status-block-text border border-status-block-text/20';
        }

        const dateStr = log.timestamp ? new Date(log.timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'medium' }) : '—';
        const scoreStr = log.risk_score !== null && log.risk_score !== undefined
          ? Number(log.risk_score).toFixed(4)
          : '<span class="text-on-surface-variant text-[11px] font-semibold">N/A</span>';

        const safeAuditId = window.escapeHtml(log.audit_id);
        const safeTxnId = window.escapeHtml(log.transaction_id);
        const safeDecisionId = window.escapeHtml(log.decision_id || '—');
        const safeEventType = window.escapeHtml(log.event_type);
        const safeCostProfile = window.escapeHtml(log.cost_profile || 'BALANCED');
        const safeAction = window.escapeHtml(log.action);
        const safeConfidenceTier = window.escapeHtml(log.confidence_tier || '—');

        return `
          <tr class="table-row-hover border-b border-outline-variant/40">
            <!-- Audit ID & Timestamp -->
            <td class="py-3 px-4">
              <span class="font-mono font-bold text-on-surface block text-xs">${safeAuditId}</span>
              <span class="text-on-surface-variant text-[11px]">${dateStr}</span>
            </td>

            <!-- Transaction ID -->
            <td class="py-3 px-4">
              <a href="#transactions/${encodeURIComponent(log.transaction_id)}" class="font-mono font-bold text-primary hover:underline text-xs block">
                ${safeTxnId}
              </a>
              <span class="text-[11px] text-on-surface-variant font-mono truncate max-w-[140px] block" title="${safeDecisionId}">
                ${safeDecisionId}
              </span>
            </td>

            <!-- Event Type -->
            <td class="py-3 px-4">
              <span class="font-semibold text-on-surface block">${safeEventType}</span>
              <span class="text-[11px] text-on-surface-variant">Profile: ${safeCostProfile}</span>
            </td>

            <!-- Action -->
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 rounded text-[11px] font-bold ${badgeClass}">
                ${safeAction}
              </span>
            </td>

            <!-- Risk Score -->
            <td class="py-3 px-4 font-mono font-medium">${scoreStr}</td>

            <!-- Confidence -->
            <td class="py-3 px-4 text-on-surface-variant">${safeConfidenceTier}</td>

            <!-- Detail Trigger -->
            <td class="py-3 px-4 text-right">

              <button onclick="AuditLogView.viewDetails(${JSON.stringify(log.audit_id).replace(/"/g, '&quot;')}, ${JSON.stringify(log.details || {}).replace(/"/g, '&quot;')})" class="px-2.5 py-1 bg-surface-container hover:bg-surface-variant rounded text-[11px] font-semibold text-on-surface flex items-center gap-1 ml-auto">
                <span class="material-symbols-outlined text-[14px]">code</span>
                <span>Payload</span>
              </button>
            </td>
          </tr>
        `;
      }).join('');

      const start = this.currentOffset + 1;
      const end = Math.min(this.currentOffset + this.limit, total);
      if (pageInfo) pageInfo.textContent = `Showing ${start}–${end} of ${total}`;
      if (prevBtn) prevBtn.disabled = this.currentOffset === 0;
      if (nextBtn) nextBtn.disabled = end >= total;

    } catch (err) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="p-6 text-center text-error">
            <p class="font-semibold">Error loading audit records</p>
            <p class="text-xs mt-1">${err.message}</p>
          </td>
        </tr>
      `;
    }
  },

  viewDetails(auditId, details) {
    const modal = document.getElementById('audit-detail-modal');
    const viewer = document.getElementById('audit-json-viewer');
    if (!modal || !viewer) return;

    // Additional defense-in-depth sanitization: remove any key matching secret / key / password / token
    const safeDetails = JSON.parse(JSON.stringify(details, (key, value) => {
      const lower = key.toLowerCase();
      if (lower.includes('secret') || lower.includes('password') || lower.includes('signature') || lower.includes('auth')) {
        return undefined;
      }
      return value;
    }));

    viewer.textContent = JSON.stringify(safeDetails, null, 2);
    modal.classList.remove('hidden');
  }
};

window.AuditLogView = AuditLogView;
