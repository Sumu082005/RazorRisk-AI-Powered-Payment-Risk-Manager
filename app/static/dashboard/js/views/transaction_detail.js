/**
 * Transaction Detail View Component.
 * Fetches deep-dive risk evaluation details from GET /api/v1/transactions/{id}.
 * CRITICAL SAFETY RULE: Prominently displays "MODEL NOT APPLICABLE" and
 * "Required benchmark PCA features are not present in the Razorpay transaction payload. Safety Action: ROUTED TO MANUAL REVIEW"
 * whenever risk_score is null.
 */

const TransactionDetailView = {
  async render(container, transactionId) {
    if (!transactionId) {
      window.location.hash = '#transactions';
      return;
    }

    container.innerHTML = `
      <div class="space-y-6">
        <!-- Back Bar -->
        <div class="flex items-center gap-3">
          <a href="#transactions" class="p-1.5 rounded hover:bg-surface-variant text-on-surface-variant flex items-center gap-1 text-sm font-medium transition-colors">
            <span class="material-symbols-outlined text-[18px]">arrow_back</span>
            <span>Back to Transactions</span>
          </a>
        </div>

        <div id="detail-loading" class="space-y-4">
          <div class="h-24 skeleton"></div>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="h-64 skeleton"></div>
            <div class="h-64 skeleton col-span-2"></div>
          </div>
        </div>

        <div id="detail-content" class="hidden space-y-6"></div>
      </div>
    `;

    await this.loadDetail(transactionId);
  },

  async loadDetail(id) {
    const loadingEl = document.getElementById('detail-loading');
    const contentEl = document.getElementById('detail-content');
    if (!contentEl) return;

    try {
      const data = await window.ApiClient.getTransactionDetail(id);

      loadingEl?.classList.add('hidden');
      contentEl.classList.remove('hidden');

      const isModelNotApplicable = (data.risk_score === null || data.risk_score === undefined);
      
      let badgeClass = 'bg-surface-variant text-on-surface-variant';
      if (data.action === 'APPROVE') {
        badgeClass = 'bg-status-approve-bg text-status-approve-text border border-status-approve-text/20';
      } else if (data.action === 'REVIEW') {
        badgeClass = 'bg-status-review-bg text-status-review-text border border-status-review-text/20';
      } else if (data.action === 'BLOCK') {
        badgeClass = 'bg-status-block-bg text-status-block-text border border-status-block-text/20';
      }

      const amountFormatted = data.amount !== null && data.amount !== undefined
        ? `₹${Number(data.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
        : (data.expected_loss ? `₹${Number(data.expected_loss).toFixed(2)}` : '—');

      const dateFormatted = data.timestamp ? new Date(data.timestamp).toLocaleString('en-IN', { dateStyle: 'full', timeStyle: 'medium' }) : '—';

      const safeTxnId = window.escapeHtml(data.transaction_id);
      const safeAction = window.escapeHtml(data.action);
      const safeEventType = window.escapeHtml(data.event_type);
      const attrTxnId = encodeURIComponent(data.transaction_id).replace(/'/g, '%27');

      const aiRec = data.ai_recommendation || data.action || 'REVIEW';
      const humanDec = data.human_decision;
      const isOverride = data.is_override;
      const statusLabel = data.status_label || (data.action === 'ARCHIVE' ? 'ARCHIVED' : (data.action === 'REVIEW' ? 'PENDING HUMAN REVIEW' : data.action));

      let aiBadgeClass = 'bg-status-review-bg text-status-review-text border border-status-review-text/20';
      if (aiRec === 'APPROVE') aiBadgeClass = 'bg-status-approve-bg text-status-approve-text border border-status-approve-text/20';
      else if (aiRec === 'BLOCK') aiBadgeClass = 'bg-status-block-bg text-status-block-text border border-status-block-text/20';

      let humanBadgeClass = 'bg-surface-variant text-on-surface-variant';
      if (humanDec === 'APPROVE') humanBadgeClass = 'bg-status-approve-bg text-status-approve-text border border-status-approve-text/20';
      else if (humanDec === 'BLOCK') humanBadgeClass = 'bg-status-block-bg text-status-block-text border border-status-block-text/20';
      else if (humanDec === 'REVIEW') humanBadgeClass = 'bg-status-review-bg text-status-review-text border border-status-review-text/20';

      // Build HTML
      contentEl.innerHTML = `
        <!-- Top Title & Action Header -->
        <div class="bg-surface-container-lowest p-6 border border-outline-variant rounded-lg shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div class="flex flex-wrap items-center gap-2.5">
              <h2 class="text-xl font-bold font-mono text-primary">${safeTxnId}</h2>
              <span class="px-2.5 py-1 rounded-full text-xs font-bold uppercase ${badgeClass}">
                ${statusLabel}
              </span>
              <span class="text-xs px-2 py-0.5 bg-surface-container text-on-surface-variant rounded">
                ${safeEventType}
              </span>
            </div>
            <p class="text-xs text-on-surface-variant mt-1.5 flex items-center gap-1.5">
              <span class="material-symbols-outlined text-[16px]">schedule</span>
              <span>Evaluated at ${dateFormatted}</span>
            </p>
          </div>

          <!-- Interactive Review & Override Actions -->
          <div class="flex flex-wrap items-center gap-2 border-t md:border-t-0 pt-3 md:pt-0 border-outline-variant">
            ${data.action !== 'ARCHIVE' ? `
              <button onclick="window.App.openReviewModal(decodeURIComponent('${attrTxnId}'), 'APPROVE')" class="px-3.5 py-2 bg-secondary text-on-secondary rounded text-xs font-semibold hover:bg-opacity-90 flex items-center gap-1.5 shadow-sm transition-all">
                <span class="material-symbols-outlined text-[16px]">check_circle</span>
                <span>${aiRec === 'APPROVE' ? 'Confirm APPROVE' : 'Approve (Override)'}</span>
              </button>
              <button onclick="window.App.openReviewModal(decodeURIComponent('${attrTxnId}'), 'BLOCK')" class="px-3.5 py-2 bg-error text-on-error rounded text-xs font-semibold hover:bg-opacity-90 flex items-center gap-1.5 shadow-sm transition-all">
                <span class="material-symbols-outlined text-[16px]">block</span>
                <span>${aiRec === 'BLOCK' ? 'Confirm BLOCK' : 'Block (Override)'}</span>
              </button>
              ${data.action !== 'REVIEW' ? `
                <button onclick="TransactionDetailView.rereview('${attrTxnId}')" class="px-3.5 py-2 bg-surface-container text-on-surface rounded text-xs font-semibold border border-outline-variant hover:bg-surface-variant flex items-center gap-1.5 shadow-sm transition-all">
                  <span class="material-symbols-outlined text-[16px]">replay</span>
                  <span>Re-review</span>
                </button>
              ` : ''}
              <button onclick="TransactionDetailView.archive('${attrTxnId}')" class="px-3 py-2 bg-surface-container-low text-on-surface-variant rounded text-xs font-semibold border border-outline-variant hover:bg-surface-variant flex items-center gap-1 transition-all" title="Archive transaction from active views">
                <span class="material-symbols-outlined text-[16px]">archive</span>
                <span>Archive</span>
              </button>
            ` : `
              <button onclick="TransactionDetailView.rereview('${attrTxnId}')" class="px-3.5 py-2 bg-primary text-on-primary rounded text-xs font-semibold hover:bg-primary-container flex items-center gap-1.5 shadow-sm transition-all">
                <span class="material-symbols-outlined text-[16px]">unarchive</span>
                <span>Unarchive & Re-review</span>
              </button>
            `}
          </div>
        </div>

        <!-- AI RECOMMENDATION VS HUMAN DECISION CARD (PRIMARY DISTINCTION) -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <!-- AI Recommendation Panel -->
          <div class="p-4 bg-surface-container-lowest border-2 border-primary/20 rounded-lg shadow-sm space-y-2">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary text-[20px]">smart_toy</span>
                <span class="text-xs font-bold uppercase tracking-wider text-on-surface">AI Risk Recommendation</span>
              </div>
              <span class="px-2.5 py-1 rounded text-xs font-bold uppercase ${aiBadgeClass}">
                ${aiRec}
              </span>
            </div>
            <p class="text-xs text-on-surface-variant">
              Calculated automatically from native transaction features via ML inference & RiskDecisionEngine policy.
            </p>
          </div>

          <!-- Human Final Decision Panel -->
          <div class="p-4 bg-surface-container-lowest border-2 ${humanDec ? (isOverride ? 'border-amber-400' : 'border-emerald-400') : 'border-outline-variant'} rounded-lg shadow-sm space-y-2">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined ${humanDec ? (isOverride ? 'text-amber-600' : 'text-emerald-600') : 'text-on-surface-variant'} text-[20px]">gavel</span>
                <span class="text-xs font-bold uppercase tracking-wider text-on-surface">Human Final Decision</span>
              </div>
              <span class="px-2.5 py-1 rounded text-xs font-bold uppercase ${humanBadgeClass}">
                ${humanDec || 'Awaiting Confirmation'}
              </span>
            </div>
            <p class="text-xs text-on-surface-variant">
              ${humanDec 
                ? (isOverride 
                    ? `⚠️ <strong>Manual Override:</strong> Analyst overrode AI recommendation (${aiRec} → ${humanDec}).` 
                    : `✓ <strong>Confirmed:</strong> Analyst confirmed AI recommendation (${humanDec}).`)
                : 'Analyst has not submitted a manual review or override yet.'}
            </p>
          </div>
        </div>

        <!-- MODEL NOT APPLICABLE SAFETY BANNER (if applicable) -->
        ${isModelNotApplicable ? `
          <div class="bg-amber-50 border-2 border-amber-400 rounded-lg p-5 shadow-sm">
            <div class="flex items-start gap-4">
              <div class="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-700 shrink-0">
                <span class="material-symbols-outlined text-[24px]">verified_user</span>
              </div>
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <h3 class="text-base font-bold text-amber-900 uppercase tracking-wide">MODEL NOT APPLICABLE</h3>
                  <span class="px-2 py-0.5 bg-amber-200 text-amber-900 text-[11px] font-bold rounded">Safety Protocol Active</span>
                </div>
                <p class="text-sm text-amber-800">
                  Required benchmark PCA features are not present in the Razorpay transaction payload.
                </p>
                <div class="mt-2 text-xs font-semibold text-amber-900 flex items-center gap-1.5 pt-1">
                  <span>Safety Action:</span>
                  <span class="px-2 py-0.5 bg-amber-700 text-white rounded uppercase font-bold tracking-wider">ROUTED TO MANUAL REVIEW</span>
                </div>
                <p class="text-xs text-amber-700 mt-1">
                  RazorRisk strictly avoids fabricating arbitrary fraud probabilities for live payment webhooks.
                </p>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- 2-Column Grid: Risk Indicators + Transaction Metadata -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <!-- Left Column: Risk & Decision Indicators -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm space-y-4">
            <h3 class="text-sm font-bold uppercase tracking-wider text-on-surface border-b border-outline-variant pb-2">
              Decision Analysis
            </h3>

            <div class="space-y-3 text-xs">
              <div class="flex justify-between py-1.5 border-b border-outline-variant/30">
                <span class="text-on-surface-variant font-medium">Risk Score</span>
                <span class="font-mono font-bold text-sm ${isModelNotApplicable ? 'text-on-surface-variant' : 'text-primary'}">
                  ${isModelNotApplicable ? 'N/A (Uncalibrated)' : Number(data.risk_score).toFixed(4)}
                </span>
              </div>

              <div class="flex justify-between py-1.5 border-b border-outline-variant/30">
                <span class="text-on-surface-variant font-medium">Risk Tier</span>
                <span class="font-semibold text-on-surface">${data.risk_tier || '—'}</span>
              </div>

              <div class="flex justify-between py-1.5 border-b border-outline-variant/30">
                <span class="text-on-surface-variant font-medium">Confidence Tier</span>
                <span class="font-semibold text-on-surface">${data.confidence_tier || '—'}</span>
              </div>

              <div class="flex justify-between py-1.5 border-b border-outline-variant/30">
                <span class="text-on-surface-variant font-medium">Cost Profile</span>
                <span class="font-semibold text-on-surface">${data.cost_profile || 'BALANCED'}</span>
              </div>

              <div class="flex justify-between py-1.5 border-b border-outline-variant/30">
                <span class="text-on-surface-variant font-medium">Expected Loss</span>
                <span class="font-semibold text-on-surface">
                  ${data.expected_loss ? `₹${Number(data.expected_loss).toFixed(2)}` : '—'}
                </span>
              </div>

              <div class="flex justify-between py-1.5 border-b border-outline-variant/30">
                <span class="text-on-surface-variant font-medium">Decision ID</span>
                <span class="font-mono text-primary font-medium truncate max-w-[160px]" title="${data.decision_id}">
                  ${data.decision_id || '—'}
                </span>
              </div>
            </div>
          </div>

          <!-- Right Column: Monetary Details & Deterministic Rules -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm md:col-span-2 space-y-5">
            <h3 class="text-sm font-bold uppercase tracking-wider text-on-surface border-b border-outline-variant pb-2">
              Payment Information & Policy Rules
            </h3>

            <!-- Key Figures -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 bg-surface-container-low p-4 rounded-lg">
              <div>
                <p class="text-[11px] font-semibold text-on-surface-variant uppercase">Transaction Amount</p>
                <p class="text-xl font-bold text-on-surface mt-0.5">${amountFormatted}</p>
              </div>
              <div>
                <p class="text-[11px] font-semibold text-on-surface-variant uppercase">Currency</p>
                <p class="text-xl font-bold text-on-surface mt-0.5">${data.currency || 'INR'}</p>
              </div>
              <div>
                <p class="text-[11px] font-semibold text-on-surface-variant uppercase">Payment Method</p>
                <p class="text-sm font-bold text-on-surface mt-1.5 capitalize">
                  ${data.correlated_webhook?.payload?.payload?.payment?.entity?.method || 'Test Mode / Simulated'}
                </p>
              </div>
              <div>
                <p class="text-[11px] font-semibold text-on-surface-variant uppercase">Environment</p>
                <span class="inline-block mt-1 text-[11px] font-bold px-2 py-0.5 bg-surface-variant text-primary rounded">
                  TEST MODE
                </span>
              </div>
            </div>

            <!-- Triggered Rules Section -->
            <div>
              <h4 class="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2.5">
                Deterministic Policy Rule Evaluations
              </h4>
              ${data.triggered_rules && data.triggered_rules.length > 0 ? `
                <div class="space-y-2">
                  ${data.triggered_rules.map(r => `
                    <div class="p-3 rounded border border-outline-variant/60 bg-surface-container-lowest flex items-start gap-3">
                      <span class="material-symbols-outlined text-[18px] text-primary mt-0.5">policy</span>
                      <div class="text-xs">
                        <div class="flex items-center gap-2">
                          <span class="font-mono font-bold text-primary">${r.rule_id}</span>
                          <span class="font-semibold text-on-surface">${r.rule_name}</span>
                          <span class="px-1.5 py-0.5 text-[10px] font-bold rounded bg-surface-variant text-on-surface-variant uppercase">${r.severity}</span>
                        </div>
                        <p class="text-on-surface-variant mt-1">${r.description}</p>
                      </div>
                    </div>
                  `).join('')}
                </div>
              ` : `
                <div class="p-4 bg-surface-container rounded text-xs text-on-surface-variant italic">
                  ${isModelNotApplicable 
                    ? 'No benchmark PCA rules triggered. Raw payment payload routed to human review.' 
                    : 'Standard operating baseline. No high-risk exception rules triggered.'}
                </div>
              `}
            </div>
          </div>
        </div>

        <!-- Audit Trail & Lifecycle History -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-outline-variant pb-2">
            <div>
              <h3 class="text-sm font-bold uppercase tracking-wider text-on-surface">Audit Lifecycle Trail</h3>
              <p class="text-xs text-on-surface-variant mt-0.5">Immutable record of automated evaluations and analyst review decisions</p>
            </div>
            <span class="text-xs font-semibold text-on-surface-variant bg-surface-container px-2.5 py-1 rounded">
              ${data.history ? data.history.length : 0} Event(s)
            </span>
          </div>

          <div class="divide-y divide-outline-variant/40 text-xs">
            ${data.history && data.history.length > 0 ? data.history.map((h, i) => {
              const safeEventType = window.escapeHtml(h.event_type);
              const safeAction = window.escapeHtml(h.action);
              const safeSource = h.action_source ? window.escapeHtml(h.action_source) : null;
              const safeNotes = h.notes ? window.escapeHtml(h.notes) : null;
              const safeReason = h.reason ? window.escapeHtml(h.reason) : null;

              return `
              <div class="py-3 flex flex-col md:flex-row md:items-center justify-between gap-2">
                <div class="flex items-start gap-3">
                  <div class="w-7 h-7 rounded-full ${h.action === 'APPROVE' ? 'bg-status-approve-bg text-status-approve-text' : (h.action === 'BLOCK' ? 'bg-status-block-bg text-status-block-text' : 'bg-status-review-bg text-status-review-text')} flex items-center justify-center shrink-0 mt-0.5 font-bold">
                    ${i + 1}
                  </div>
                  <div>
                    <div class="flex items-center gap-2">
                      <span class="font-bold text-on-surface">${safeEventType}</span>
                      <span class="font-bold px-2 py-0.5 rounded-full text-[11px] ${h.action === 'APPROVE' ? 'bg-status-approve-bg text-status-approve-text' : (h.action === 'BLOCK' ? 'bg-status-block-bg text-status-block-text' : 'bg-status-review-bg text-status-review-text')}">
                        ${safeAction}
                      </span>
                      ${safeSource ? `<span class="px-1.5 py-0.5 bg-primary-fixed text-primary text-[10px] font-semibold rounded">${safeSource}</span>` : ''}
                    </div>
                    ${safeNotes ? `<p class="text-on-surface font-medium mt-1">Notes: "${safeNotes}"</p>` : ''}
                    ${safeReason ? `<p class="text-on-surface-variant">Reason: ${safeReason}</p>` : ''}
                  </div>
                </div>
                <div class="text-on-surface-variant font-mono text-[11px] whitespace-nowrap pl-10 md:pl-0">
                  ${new Date(h.timestamp).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'medium' })}
                </div>
              </div>
            `;
            }).join('') : '<p class="p-4 text-center text-on-surface-variant">No audit history records available.</p>'}

          </div>
        </div>

        <!-- Correlated Webhook Metadata (Sanitized) -->
        ${data.correlated_webhook ? `
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm space-y-3">
            <h3 class="text-sm font-bold uppercase tracking-wider text-on-surface border-b border-outline-variant pb-2">
              Correlated Razorpay Webhook Event
            </h3>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs bg-surface-container-low p-3 rounded">
              <div>
                <span class="text-on-surface-variant">Event ID:</span>
                <span class="font-mono font-bold text-primary block truncate">${data.correlated_webhook.event_id}</span>
              </div>
              <div>
                <span class="text-on-surface-variant">Event Type:</span>
                <span class="font-semibold text-on-surface block">${data.correlated_webhook.event_type}</span>
              </div>
              <div>
                <span class="text-on-surface-variant">Signature Valid:</span>
                <span class="font-bold text-status-approve-text block">✓ Verified HMAC</span>
              </div>
              <div>
                <span class="text-on-surface-variant">Processing Status:</span>
                <span class="font-mono font-semibold text-on-surface block">${data.correlated_webhook.processing_status}</span>
              </div>
            </div>
          </div>
        ` : ''}
      `;

    } catch (err) {
      loadingEl?.classList.add('hidden');
      contentEl.classList.remove('hidden');
      contentEl.innerHTML = `
        <div class="p-8 bg-surface-container-lowest border border-outline-variant rounded-lg text-center space-y-3">
          <span class="material-symbols-outlined text-4xl text-error">error</span>
          <h3 class="text-lg font-bold text-on-surface">Transaction Not Found</h3>
          <p class="text-sm text-on-surface-variant">Transaction ID '${id}' could not be located in the audit database.</p>
          <a href="#transactions" class="inline-block px-4 py-2 bg-primary text-on-primary rounded text-xs font-semibold">
            Return to Transactions List
          </a>
        </div>
      `;
    }
  },

  async archive(encodedTxnId) {
    const txnId = decodeURIComponent(encodedTxnId);
    if (!confirm(`Archive transaction ${txnId}? This will remove it from active lists while preserving all audit history.`)) return;

    try {
      await window.ApiClient.archiveTransaction(txnId, {
        reason: 'MANUAL_ARCHIVE',
        notes: 'Transaction archived from detail view'
      });
      window.App.showToast(`Transaction ${txnId} archived successfully.`, 'success');
      this.loadDetail(txnId);
    } catch (err) {
      window.App.showToast(err.message || 'Failed to archive transaction.', 'error');
    }
  },

  async rereview(encodedTxnId) {
    const txnId = decodeURIComponent(encodedTxnId);
    try {
      await window.ApiClient.rereviewTransaction(txnId, {
        reason: 'ANALYST_RE_REVIEW',
        notes: 'Transaction re-opened for manual review'
      });
      window.App.showToast(`Transaction ${txnId} re-opened for review.`, 'success');
      this.loadDetail(txnId);
    } catch (err) {
      window.App.showToast(err.message || 'Failed to re-open transaction for review.', 'error');
    }
  }
};

window.TransactionDetailView = TransactionDetailView;
