/**
 * Transactions View Component.
 * Connects to GET /api/v1/transactions with search, status filters, and pagination.
 * Clicking a row navigates to #transactions/:id.
 */

const TransactionsView = {
  currentStatus: '',
  currentSearch: '',
  currentSortBy: 'timestamp',
  currentOrder: 'desc',
  currentOffset: 0,
  includeArchived: false,
  limit: 10,

  async render(container) {
    container.innerHTML = `
      <div class="space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 class="text-2xl font-bold text-on-surface tracking-tight">Live Transactions Monitoring</h2>
            <p class="text-sm text-on-surface-variant mt-1">Audit log of evaluated live Razorpay payment transactions, AI recommendations, and human decisions.</p>
          </div>
          <div class="flex items-center gap-2">
            <a href="#review-queue" class="h-9 px-3 bg-tertiary-container text-on-tertiary-container border border-tertiary/30 rounded text-xs font-bold flex items-center gap-1.5 transition-colors">
              <span class="material-symbols-outlined text-[16px]">science</span>
              <span>Model Evaluation Queue</span>
            </a>
            <label class="flex items-center gap-2 px-3 py-1.5 bg-surface-container-lowest border border-outline-variant rounded text-xs text-on-surface cursor-pointer select-none">
              <input type="checkbox" id="txn-include-archived" ${this.includeArchived ? 'checked' : ''} class="rounded text-primary focus:ring-primary h-3.5 w-3.5" />
              <span>Show Archived</span>
            </label>
            <button id="txn-refresh-btn" class="h-9 px-3 bg-surface-container-lowest border border-outline-variant rounded text-sm text-on-surface hover:bg-surface-variant flex items-center gap-1.5 transition-colors">
              <span class="material-symbols-outlined text-[18px]">refresh</span>
              <span>Refresh</span>
            </button>
          </div>
        </div>

        <!-- Filters & Search Toolbar -->
        <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <!-- Status Filter Tabs -->
          <div class="flex items-center gap-1 p-1 bg-surface-container rounded-lg text-xs font-semibold">
            <button data-status="" class="txn-tab px-3 py-1.5 rounded transition-all bg-surface-container-lowest text-primary shadow-sm">All</button>
            <button data-status="APPROVE" class="txn-tab px-3 py-1.5 rounded text-on-surface-variant hover:text-on-surface transition-all">Approved</button>
            <button data-status="REVIEW" class="txn-tab px-3 py-1.5 rounded text-on-surface-variant hover:text-on-surface transition-all">Review</button>
            <button data-status="BLOCK" class="txn-tab px-3 py-1.5 rounded text-on-surface-variant hover:text-on-surface transition-all">Blocked</button>
          </div>

          <!-- Search & Sorting -->
          <div class="flex items-center gap-3">
            <div class="relative w-64">
              <span class="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">search</span>
              <input id="txn-search-input" type="text" placeholder="Search ID or event..." class="w-full pl-9 pr-3 h-9 text-xs bg-surface-container-low border border-outline-variant rounded focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-all" value="${this.currentSearch}">
            </div>
            <select id="txn-sort-select" class="h-9 text-xs bg-surface-container-lowest border border-outline-variant rounded px-2.5 text-on-surface outline-none focus:border-primary">
              <option value="timestamp:desc">Newest First</option>
              <option value="timestamp:asc">Oldest First</option>
              <option value="risk_score:desc">Highest Risk Score</option>
              <option value="expected_loss:desc">Highest Expected Loss</option>
            </select>
          </div>
        </div>

        <!-- Table Container -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-sm">
              <thead class="bg-surface-container-low text-xs uppercase font-semibold text-on-surface-variant border-b border-outline-variant tracking-wider">
                <tr>
                  <th class="py-3 px-4">Transaction ID</th>
                  <th class="py-3 px-4">Amount</th>
                  <th class="py-3 px-4">Risk Score</th>
                  <th class="py-3 px-4">Risk Tier</th>
                  <th class="py-3 px-4">AI Recommendation</th>
                  <th class="py-3 px-4">Human Decision / Status</th>
                  <th class="py-3 px-4">Timestamp</th>
                  <th class="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody id="txn-table-body" class="divide-y divide-outline-variant divide-opacity-50">
                <tr>
                  <td colspan="8" class="p-8 text-center text-on-surface-variant">
                    <div class="flex items-center justify-center gap-2">
                      <span class="material-symbols-outlined animate-spin">progress_activity</span>
                      <span>Loading transactions...</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Bar -->
          <div id="txn-pagination" class="p-3 bg-surface-container-low border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-variant">
            <span id="txn-page-info">Showing 0 of 0</span>
            <div class="flex items-center gap-1">
              <button id="txn-prev-btn" class="px-2.5 py-1.5 border border-outline-variant rounded bg-surface-container-lowest hover:bg-surface-variant disabled:opacity-40" disabled>Previous</button>
              <button id="txn-next-btn" class="px-2.5 py-1.5 border border-outline-variant rounded bg-surface-container-lowest hover:bg-surface-variant disabled:opacity-40" disabled>Next</button>
            </div>
          </div>
        </div>
      </div>
    `;

    this.bindEvents();
    await this.loadTransactions();
  },

  bindEvents() {
    // Status tabs
    document.querySelectorAll('.txn-tab').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.txn-tab').forEach(t => {
          t.classList.remove('bg-surface-container-lowest', 'text-primary', 'shadow-sm');
          t.classList.add('text-on-surface-variant');
        });
        btn.classList.remove('text-on-surface-variant');
        btn.classList.add('bg-surface-container-lowest', 'text-primary', 'shadow-sm');
        this.currentStatus = btn.dataset.status;
        this.currentOffset = 0;
        this.loadTransactions();
      });
    });

    // Include archived toggle
    document.getElementById('txn-include-archived')?.addEventListener('change', (e) => {
      this.includeArchived = e.target.checked;
      this.currentOffset = 0;
      this.loadTransactions();
    });

    // Search input with debounce
    let searchTimeout = null;
    document.getElementById('txn-search-input')?.addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        this.currentSearch = e.target.value.trim();
        this.currentOffset = 0;
        this.loadTransactions();
      }, 300);
    });

    // Sorting
    document.getElementById('txn-sort-select')?.addEventListener('change', (e) => {
      const [field, order] = e.target.value.split(':');
      this.currentSortBy = field;
      this.currentOrder = order;
      this.currentOffset = 0;
      this.loadTransactions();
    });

    // Pagination
    document.getElementById('txn-prev-btn')?.addEventListener('click', () => {
      if (this.currentOffset >= this.limit) {
        this.currentOffset -= this.limit;
        this.loadTransactions();
      }
    });

    document.getElementById('txn-next-btn')?.addEventListener('click', () => {
      this.currentOffset += this.limit;
      this.loadTransactions();
    });

    // Refresh
    document.getElementById('txn-refresh-btn')?.addEventListener('click', () => {
      this.loadTransactions();
    });
  },

  async loadTransactions() {
    const tbody = document.getElementById('txn-table-body');
    const pageInfo = document.getElementById('txn-page-info');
    const prevBtn = document.getElementById('txn-prev-btn');
    const nextBtn = document.getElementById('txn-next-btn');
    if (!tbody) return;

    try {
      const params = {
        limit: this.limit,
        offset: this.currentOffset,
        sort_by: this.currentSortBy,
        order: this.currentOrder,
        include_archived: this.includeArchived
      };
      if (this.currentStatus) params.status = this.currentStatus;
      if (this.currentSearch) params.search = this.currentSearch;

      const data = await window.ApiClient.getTransactions(params);
      const items = data.items || [];
      const total = data.total || 0;

      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="8" class="p-12 text-center text-on-surface-variant">
              <span class="material-symbols-outlined text-4xl text-outline-variant mb-2">receipt_long</span>
              <p class="font-medium text-on-surface">No transactions found</p>
              <p class="text-xs text-on-surface-variant mt-1">Try adjusting your filters or search query, or perform a test payment.</p>
            </td>
          </tr>
        `;
        if (pageInfo) pageInfo.textContent = 'Showing 0 of 0';
        if (prevBtn) prevBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = true;
        return;
      }

      tbody.innerHTML = items.map(t => {
        const aiRec = t.ai_recommendation || t.action || 'REVIEW';
        let aiBadgeClass = 'bg-surface-variant text-on-surface-variant';
        if (aiRec === 'APPROVE') aiBadgeClass = 'bg-status-approve-bg text-status-approve-text border border-status-approve-text/20';
        else if (aiRec === 'REVIEW') aiBadgeClass = 'bg-status-review-bg text-status-review-text border border-status-review-text/20';
        else if (aiRec === 'BLOCK') aiBadgeClass = 'bg-status-block-bg text-status-block-text border border-status-block-text/20';

        let statusBadgeClass = 'bg-surface-variant text-on-surface-variant';
        const isOverride = t.is_override;
        const statusLabel = t.status_label || t.action;

        if (t.action === 'ARCHIVE') {
          statusBadgeClass = 'bg-surface-container text-on-surface-variant border border-outline-variant';
        } else if (t.human_decision === 'APPROVE') {
          statusBadgeClass = isOverride 
            ? 'bg-amber-100 text-amber-900 border border-amber-300 font-bold' 
            : 'bg-status-approve-bg text-status-approve-text border border-status-approve-text/20';
        } else if (t.human_decision === 'BLOCK') {
          statusBadgeClass = isOverride 
            ? 'bg-rose-100 text-rose-900 border border-rose-300 font-bold' 
            : 'bg-status-block-bg text-status-block-text border border-status-block-text/20';
        } else if (t.action === 'REVIEW') {
          statusBadgeClass = 'bg-status-review-bg text-status-review-text border border-status-review-text/20 animate-pulse';
        }

        const scoreText = t.risk_score !== null && t.risk_score !== undefined
          ? Number(t.risk_score).toFixed(4)
          : '<span class="text-xs font-semibold text-on-surface-variant uppercase tracking-wider" title="Model Not Applicable">N/A</span>';

        const amountText = t.amount !== null && t.amount !== undefined
          ? `₹${Number(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
          : (t.expected_loss ? `₹${Number(t.expected_loss).toFixed(2)}` : '—');

        const dateStr = t.timestamp ? new Date(t.timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'medium' }) : '—';

        const safeTxnId = window.escapeHtml(t.transaction_id);
        const attrTxnId = encodeURIComponent(t.transaction_id).replace(/'/g, '%27');
        const safeRiskTier = window.escapeHtml(t.risk_tier || '—');

        return `
          <tr class="table-row-hover border-b border-outline-variant/40">
            <td class="py-3 px-4 font-mono font-bold text-primary text-xs">
              <a href="#transactions/${encodeURIComponent(t.transaction_id)}" class="hover:underline">${safeTxnId}</a>
            </td>
            <td class="py-3 px-4 font-semibold text-on-surface text-xs">${amountText}</td>
            <td class="py-3 px-4 font-mono text-xs">${scoreText}</td>
            <td class="py-3 px-4 text-xs font-medium">${safeRiskTier}</td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 rounded text-xs font-bold uppercase inline-flex items-center gap-1 ${aiBadgeClass}">
                ${aiRec}
              </span>
            </td>
            <td class="py-3 px-4">
              <span class="px-2 py-0.5 rounded text-xs font-semibold inline-flex items-center gap-1 ${statusBadgeClass}">
                ${statusLabel}
              </span>
            </td>
            <td class="py-3 px-4 text-xs text-on-surface-variant whitespace-nowrap">${dateStr}</td>
            <td class="py-3 px-4 text-right">
              <div class="flex items-center justify-end gap-1.5">
                <a href="#transactions/${encodeURIComponent(t.transaction_id)}" class="px-2 py-1 bg-surface-container hover:bg-surface-variant text-on-surface rounded text-[11px] font-semibold transition-colors" title="View details">
                  View
                </a>
                ${t.action !== 'ARCHIVE' ? `
                  <button onclick="TransactionsView.rereview('${attrTxnId}')" class="px-2 py-1 bg-surface-container hover:bg-surface-variant text-on-surface rounded text-[11px] font-semibold transition-colors" title="Re-review">
                    Re-review
                  </button>
                  <button onclick="TransactionsView.archive('${attrTxnId}')" class="px-2 py-1 bg-surface-container-low hover:bg-surface-variant text-on-surface-variant rounded text-[11px] transition-colors" title="Archive">
                    Archive
                  </button>
                ` : `
                  <button onclick="TransactionsView.rereview('${attrTxnId}')" class="px-2 py-1 bg-primary text-on-primary rounded text-[11px] font-semibold transition-colors" title="Restore">
                    Restore
                  </button>
                `}
              </div>
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
          <td colspan="8" class="p-6 text-center text-error">
            <p class="font-semibold">Error loading transactions</p>
            <p class="text-xs mt-1">${err.message}</p>
          </td>
        </tr>
      `;
    }
  },

  async archive(encodedTxnId) {
    const txnId = decodeURIComponent(encodedTxnId);
    if (!confirm(`Archive transaction ${txnId}? It will be hidden from active lists while preserving complete audit history.`)) return;

    try {
      await window.ApiClient.archiveTransaction(txnId, {
        reason: 'MANUAL_ARCHIVE',
        notes: 'Transaction archived from transactions table'
      });
      window.App.showToast(`Transaction ${txnId} archived.`, 'success');
      this.loadTransactions();
    } catch (err) {
      window.App.showToast(err.message || 'Failed to archive.', 'error');
    }
  },

  async rereview(encodedTxnId) {
    const txnId = decodeURIComponent(encodedTxnId);
    try {
      await window.ApiClient.rereviewTransaction(txnId, {
        reason: 'ANALYST_RE_REVIEW',
        notes: 'Transaction queued for re-review'
      });
      window.App.showToast(`Transaction ${txnId} re-opened for review.`, 'success');
      this.loadTransactions();
    } catch (err) {
      window.App.showToast(err.message || 'Failed to re-review.', 'error');
    }
  }
};

window.TransactionsView = TransactionsView;
