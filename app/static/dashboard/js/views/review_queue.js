/**
 * Review Queue View Component.
 * Connects to GET /api/v1/review/queue.
 * Provides Approve / Block actions with analyst confirmation modal and notes.
 * Automatically refreshes queue upon action completion.
 */

const ReviewQueueView = {
  currentOffset: 0,
  limit: 10,

  async render(container) {
    container.innerHTML = `
      <div class="space-y-6">
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div class="flex items-center gap-2">
              <h2 class="text-2xl font-bold text-on-surface tracking-tight">Manual Review Queue</h2>
              <span id="queue-badge" class="px-2.5 py-0.5 bg-status-review-bg text-status-review-text border border-status-review-text/30 text-xs font-bold rounded-full">
                0 Pending
              </span>
            </div>
            <p class="text-sm text-on-surface-variant mt-1">High-stakes payment decisions flagged for analyst review or awaiting policy override.</p>
          </div>
          <div class="flex items-center gap-2">
            <button id="queue-refresh-btn" class="h-9 px-3 bg-surface-container-lowest border border-outline-variant rounded text-sm text-on-surface hover:bg-surface-variant flex items-center gap-1.5 transition-colors">
              <span class="material-symbols-outlined text-[18px]">refresh</span>
              <span>Refresh Queue</span>
            </button>
          </div>
        </div>

        <!-- Guidance Banner -->
        <div class="p-4 bg-surface-container-low border border-outline-variant rounded-lg flex items-start gap-3 text-xs text-on-surface-variant">
          <span class="material-symbols-outlined text-primary text-[20px] shrink-0 mt-0.5">info</span>
          <div>
            <p class="font-semibold text-on-surface">Analyst Protocol:</p>
            <p class="mt-0.5">Transactions in this queue require deliberate human review. Approving or blocking an item will commit an immutable audit trail entry (<code class="font-mono text-primary font-bold">MANUAL_REVIEW_DECISION</code>) while preserving the original system decision.</p>
          </div>
        </div>

        <!-- Queue Cards / Table -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg shadow-sm overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-sm">
              <thead class="bg-surface-container-low text-xs uppercase font-semibold text-on-surface-variant border-b border-outline-variant tracking-wider">
                <tr>
                  <th class="py-3 px-4">Transaction ID</th>
                  <th class="py-3 px-4">Flag Reason / Event</th>
                  <th class="py-3 px-4">Amount</th>
                  <th class="py-3 px-4">Risk State</th>
                  <th class="py-3 px-4">Flagged At</th>
                  <th class="py-3 px-4 text-right">Analyst Actions</th>
                </tr>
              </thead>
              <tbody id="queue-table-body" class="divide-y divide-outline-variant divide-opacity-50">
                <tr>
                  <td colspan="6" class="p-8 text-center text-on-surface-variant">
                    <div class="flex items-center justify-center gap-2">
                      <span class="material-symbols-outlined animate-spin">progress_activity</span>
                      <span>Loading review queue...</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Pagination Bar -->
          <div class="p-3 bg-surface-container-low border-t border-outline-variant flex items-center justify-between text-xs text-on-surface-variant">
            <span id="queue-page-info">Showing 0 of 0</span>
            <div class="flex items-center gap-1">
              <button id="queue-prev-btn" class="px-2.5 py-1.5 border border-outline-variant rounded bg-surface-container-lowest hover:bg-surface-variant disabled:opacity-40" disabled>Previous</button>
              <button id="queue-next-btn" class="px-2.5 py-1.5 border border-outline-variant rounded bg-surface-container-lowest hover:bg-surface-variant disabled:opacity-40" disabled>Next</button>
            </div>
          </div>
        <!-- Model Evaluation Queue Section -->
        <div class="mt-8 space-y-4">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-outline-variant pb-3">
            <div class="flex items-center gap-3">
              <h3 class="text-xl font-bold text-on-surface tracking-tight">Model Evaluation Queue</h3>
              <span class="px-2.5 py-0.5 bg-tertiary-container text-on-tertiary-container border border-tertiary/30 text-xs font-bold rounded-full uppercase tracking-wider">
                OFFLINE EVALUATION
              </span>
            </div>
            <span class="text-xs font-mono text-on-surface-variant">3 Verified Held-Out Cases</span>
          </div>

          <div class="p-3.5 bg-surface-container-low border border-outline-variant rounded-lg text-xs text-on-surface-variant flex items-start gap-2.5">
            <span class="material-symbols-outlined text-primary text-[18px] shrink-0 mt-0.5">verified</span>
            <p>
              <strong class="text-on-surface">Offline Held-Out Evaluation:</strong>
              These cases are automatically selected from held-out evaluation data using the same native ML model and decision engine. They are not live Razorpay transactions. Demonstrates the complete AI risk classification and human analyst decision lifecycle across Medium, High, and Critical risk tiers.
            </p>
          </div>

          <!-- Evaluation Queue Cards / Table -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg shadow-sm overflow-hidden">
            <div class="overflow-x-auto">
              <table class="w-full text-left text-sm">
                <thead class="bg-surface-container-low text-xs uppercase font-semibold text-on-surface-variant border-b border-outline-variant tracking-wider">
                  <tr>
                    <th class="py-3 px-4">Evaluation ID</th>
                    <th class="py-3 px-4">Dataset Source</th>
                    <th class="py-3 px-4">Evaluated Features</th>
                    <th class="py-3 px-4">Risk Score & Tier</th>
                    <th class="py-3 px-4">AI Recommendation</th>
                    <th class="py-3 px-4">Current Status</th>
                    <th class="py-3 px-4 text-right">Analyst Actions</th>
                  </tr>
                </thead>
                <tbody id="eval-table-body" class="divide-y divide-outline-variant divide-opacity-50">
                  <tr>
                    <td colspan="7" class="p-6 text-center text-on-surface-variant">
                      <div class="flex items-center justify-center gap-2">
                        <span class="material-symbols-outlined animate-spin">progress_activity</span>
                        <span>Loading evaluation cases...</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    `;

    this.bindEvents();
    await Promise.all([this.loadQueue(), this.loadEvaluationQueue()]);
  },

  bindEvents() {
    document.getElementById('queue-refresh-btn')?.addEventListener('click', () => {
      this.loadQueue();
      this.loadEvaluationQueue();
    });

    document.getElementById('queue-prev-btn')?.addEventListener('click', () => {
      if (this.currentOffset >= this.limit) {
        this.currentOffset -= this.limit;
        this.loadQueue();
      }
    });

    document.getElementById('queue-next-btn')?.addEventListener('click', () => {
      this.currentOffset += this.limit;
      this.loadQueue();
    });
  },

  async loadEvaluationQueue() {
    const tbody = document.getElementById('eval-table-body');
    if (!tbody) return;

    try {
      const data = await window.ApiClient.getEvaluationQueue();
      const items = data.items || [];

      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="7" class="p-6 text-center text-on-surface-variant text-xs">
              No evaluation queue records available.
            </td>
          </tr>
        `;
        return;
      }

      tbody.innerHTML = items.map(item => {
        const safeEvalId = window.escapeHtml(item.eval_id);
        const attrTxnId = encodeURIComponent(item.eval_id).replace(/'/g, '%27');
        const feats = item.extracted_features || {};
        
        const tierBadgeClass = item.risk_tier === 'CRITICAL'
          ? 'bg-status-block-bg text-status-block-text border-error font-extrabold'
          : (item.risk_tier === 'HIGH'
            ? 'bg-status-block-bg text-status-block-text border-error/50 font-bold'
            : 'bg-status-review-bg text-status-review-text border-status-review-text/50 font-bold');

        const recBadgeClass = item.ai_recommendation === 'BLOCK'
          ? 'bg-error text-on-error'
          : (item.ai_recommendation === 'REVIEW' ? 'bg-secondary-container text-on-secondary-container' : 'bg-secondary text-on-secondary');

        const featureSummary = `${feats.card_network || 'card'} ${feats.card_type || ''}, ${feats.attempts || 1} att, intl=${feats.is_international ?? 0}, ${feats.email_domain || 'email'}`;

        return `
          <tr class="table-row-hover border-b border-outline-variant/40">
            <!-- Evaluation ID -->
            <td class="py-3.5 px-4">
              <span class="font-mono font-bold text-primary text-xs block">${safeEvalId}</span>
              <span class="inline-block mt-1 px-1.5 py-0.5 bg-surface-container border border-outline-variant rounded text-[10px] text-on-surface-variant font-semibold">
                HELD-OUT DATA
              </span>
            </td>

            <!-- Source -->
            <td class="py-3.5 px-4 text-xs">
              <span class="font-semibold text-on-surface block">${window.escapeHtml(item.source)}</span>
              <span class="text-[11px] text-on-surface-variant">Non-live reference</span>
            </td>

            <!-- Features -->
            <td class="py-3.5 px-4 text-xs">
              <span class="font-mono text-on-surface text-[11px] block">$${Number(item.amount).toFixed(2)} USD</span>
              <span class="text-[11px] text-on-surface-variant block mt-0.5">${window.escapeHtml(featureSummary)}</span>
            </td>

            <!-- Risk Score & Tier -->
            <td class="py-3.5 px-4 text-xs">
              <span class="px-2 py-0.5 rounded text-[11px] border ${tierBadgeClass}">
                ${item.risk_tier}
              </span>
              <span class="text-[11px] font-mono text-on-surface block mt-1">
                Score: ${Number(item.risk_score).toFixed(4)}
              </span>
            </td>

            <!-- AI Recommendation -->
            <td class="py-3.5 px-4 text-xs">
              <span class="px-2 py-0.5 rounded text-[11px] font-bold ${recBadgeClass}">
                ${item.ai_recommendation}
              </span>
            </td>

            <!-- Status -->
            <td class="py-3.5 px-4 text-xs">
              <span class="font-semibold ${item.human_decision ? 'text-primary font-bold' : 'text-on-surface-variant'}">
                ${window.escapeHtml(item.status_label)}
              </span>
            </td>

            <!-- Actions -->
            <td class="py-3.5 px-4 text-right">
              <div class="flex items-center justify-end gap-1.5">
                <button onclick="window.App.openReviewModal(decodeURIComponent('${attrTxnId}'), 'APPROVE')" class="px-2.5 py-1.5 bg-secondary text-on-secondary rounded text-xs font-semibold hover:bg-opacity-90 flex items-center gap-1 shadow-sm transition-all" title="Approve Evaluation Record">
                  <span class="material-symbols-outlined text-[15px]">check</span>
                  <span>Approve</span>
                </button>
                <button onclick="window.App.openReviewModal(decodeURIComponent('${attrTxnId}'), 'BLOCK')" class="px-2.5 py-1.5 bg-error text-on-error rounded text-xs font-semibold hover:bg-opacity-90 flex items-center gap-1 shadow-sm transition-all" title="Confirm Block on Evaluation Record">
                  <span class="material-symbols-outlined text-[15px]">block</span>
                  <span>Confirm Block</span>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="p-4 text-center text-error text-xs">
            Failed to load evaluation queue: ${err.message}
          </td>
        </tr>
      `;
    }
  },

  async loadQueue() {
    const tbody = document.getElementById('queue-table-body');
    const badge = document.getElementById('queue-badge');
    const pageInfo = document.getElementById('queue-page-info');
    const prevBtn = document.getElementById('queue-prev-btn');
    const nextBtn = document.getElementById('queue-next-btn');
    if (!tbody) return;

    try {
      const data = await window.ApiClient.getReviewQueue({
        limit: this.limit,
        offset: this.currentOffset
      });

      const items = data.items || [];
      const total = data.total || 0;

      if (badge) {
        badge.textContent = `${total} Pending`;
      }

      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="p-12 text-center text-on-surface-variant">
              <span class="material-symbols-outlined text-4xl text-status-approve-text mb-2">task_alt</span>
              <p class="font-semibold text-on-surface">Review Queue is Empty</p>
              <p class="text-xs text-on-surface-variant mt-1">All flagged transactions have been reviewed and resolved.</p>
            </td>
          </tr>
        `;
        if (pageInfo) pageInfo.textContent = 'Showing 0 of 0';
        if (prevBtn) prevBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = true;
        return;
      }

      tbody.innerHTML = items.map(t => {
        const isNotApplicable = (t.risk_score === null || t.risk_score === undefined);
        const amountText = t.amount !== null && t.amount !== undefined
          ? `₹${Number(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
          : (t.expected_loss ? `₹${Number(t.expected_loss).toFixed(2)}` : '—');

        const dateStr = t.timestamp ? new Date(t.timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'medium' }) : '—';
        const safeTxnId = window.escapeHtml(t.transaction_id);
        const safeDecisionId = window.escapeHtml(t.decision_id || '');
        const safeEventType = window.escapeHtml(t.event_type);
        const attrTxnId = encodeURIComponent(t.transaction_id).replace(/'/g, '%27');

        return `
          <tr class="table-row-hover border-b border-outline-variant/40">
            <!-- Transaction ID with detail link -->
            <td class="py-3 px-4">
              <a href="#transactions/${encodeURIComponent(t.transaction_id)}" class="font-mono font-bold text-primary hover:underline text-xs block">
                ${safeTxnId}
              </a>
              <span class="text-[11px] text-on-surface-variant font-mono">${safeDecisionId}</span>
            </td>

            <!-- Flag Reason -->
            <td class="py-3 px-4 text-xs">
              <span class="font-semibold text-on-surface block">${safeEventType}</span>
              ${isNotApplicable 
                ? '<span class="text-status-review-text font-medium text-[11px]">Benchmark features not present; routed to review</span>'
                : '<span class="text-on-surface-variant text-[11px]">Uncertainty / policy threshold trigger</span>'
              }
            </td>

            <!-- Amount -->
            <td class="py-3 px-4 font-semibold text-on-surface text-xs">${amountText}</td>

            <!-- Risk State -->
            <td class="py-3 px-4 text-xs">
              <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-status-review-bg text-status-review-text border border-status-review-text/20">
                REVIEW
              </span>
              <span class="text-[11px] text-on-surface-variant block mt-0.5">
                ${isNotApplicable ? 'Model N/A' : `Score: ${Number(t.risk_score).toFixed(4)}`}
              </span>
            </td>

            <!-- Timestamp -->
            <td class="py-3 px-4 text-xs text-on-surface-variant whitespace-nowrap">${dateStr}</td>

            <!-- Actions -->
            <td class="py-3 px-4 text-right">
              <div class="flex items-center justify-end gap-2">
                <button onclick="window.App.openReviewModal(decodeURIComponent('${attrTxnId}'), 'APPROVE')" class="px-3 py-1.5 bg-secondary text-on-secondary rounded text-xs font-semibold hover:bg-opacity-90 flex items-center gap-1 shadow-sm transition-all" title="Approve Transaction">
                  <span class="material-symbols-outlined text-[16px]">check</span>
                  <span>Approve</span>
                </button>
                <button onclick="window.App.openReviewModal(decodeURIComponent('${attrTxnId}'), 'BLOCK')" class="px-3 py-1.5 bg-error text-on-error rounded text-xs font-semibold hover:bg-opacity-90 flex items-center gap-1 shadow-sm transition-all" title="Block Transaction">
                  <span class="material-symbols-outlined text-[16px]">block</span>
                  <span>Block</span>
                </button>
                <a href="#transactions/${encodeURIComponent(t.transaction_id)}" class="p-1.5 hover:bg-surface-variant text-on-surface-variant rounded" title="View Full Details">
                  <span class="material-symbols-outlined text-[18px]">chevron_right</span>
                </a>
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
          <td colspan="6" class="p-6 text-center text-error">
            <p class="font-semibold">Failed to load review queue</p>
            <p class="text-xs mt-1">${err.message}</p>
          </td>
        </tr>
      `;
    }
  }
};

window.ReviewQueueView = ReviewQueueView;
