/**
 * Overview View Component.
 * Fetches real aggregate metrics from GET /api/v1/analytics/overview.
 * Preserves exact Stitch layout, styling, colors, and Chart.js visualization.
 */

const OverviewView = {
  chartInstance: null,

  async render(container) {
    container.innerHTML = `
      <div class="space-y-6">
        <!-- Header & Action Bar (Clean: No refresh button) -->
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h2 class="text-2xl font-bold text-on-surface tracking-tight">Risk Overview</h2>
            <p class="text-sm text-on-surface-variant mt-1">Real-time payment risk decisions and live fraud posture.</p>
          </div>
          <div class="flex items-center gap-3">
            <a href="#model-performance" class="h-9 px-3.5 bg-surface-container-highest text-on-surface rounded text-xs font-semibold hover:bg-surface-variant flex items-center gap-1.5 border border-outline-variant transition-colors">
              <span class="material-symbols-outlined text-[18px] text-primary">biotech</span>
              <span>Benchmark ML Studio</span>
            </a>
            <a href="#transactions" class="h-9 px-4 bg-primary text-on-primary rounded text-xs font-semibold hover:bg-primary-container flex items-center gap-1.5 transition-colors">
              <span>View Transactions</span>
              <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
            </a>
          </div>

        </div>

        <!-- Dynamic Content Container -->
        <div id="overview-content">
          <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div class="h-24 skeleton"></div>
            <div class="h-24 skeleton"></div>
            <div class="h-24 skeleton"></div>
            <div class="h-24 skeleton"></div>
            <div class="h-24 skeleton"></div>
          </div>
        </div>
      </div>
    `;

    await this.loadData();
  },

  async loadData() {
    const target = document.getElementById('overview-content');
    if (!target) return;

    try {
      const data = await window.ApiClient.getOverview();

      const monitored = data.transactions_monitored || 0;
      const approved = data.approved || 0;
      const review = data.review || 0;
      const blocked = data.blocked || 0;
      const totalAmount = (data.total_amount !== undefined && data.total_amount !== null) 
        ? Number(data.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) 
        : '0.00';
      const approvalRate = data.approval_rate_pct || 0;

      const approvePct = monitored > 0 ? Math.round((approved / monitored) * 100) : 0;
      const reviewPct = monitored > 0 ? Math.round((review / monitored) * 100) : 0;
      const blockPct = monitored > 0 ? Math.round((blocked / monitored) * 100) : 0;

      target.innerHTML = `
        <!-- Top KPI Cards (Bento-style Grid) -->
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
          <!-- Monitored -->
          <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm">
            <p class="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Monitored</p>
            <p class="text-2xl font-bold text-on-surface">${monitored}</p>
            <p class="text-xs text-on-surface-variant mt-2 flex items-center gap-1">
              <span class="material-symbols-outlined text-[14px] text-primary">visibility</span>
              <span>Total Evaluations</span>
            </p>
          </div>

          <!-- Approved -->
          <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm border-t-4 border-t-status-approve-text">
            <p class="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Approved</p>
            <p class="text-2xl font-bold text-on-surface">${approved}</p>
            <div class="mt-2 w-full bg-surface-variant h-1 rounded overflow-hidden">
              <div class="bg-status-approve-text h-full" style="width: ${approvePct}%"></div>
            </div>
            <p class="text-xs text-status-approve-text font-medium mt-1">${approvalRate}% approval rate</p>
          </div>

          <!-- Review -->
          <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm border-t-4 border-t-status-review-text">
            <p class="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Manual Review</p>
            <p class="text-2xl font-bold text-on-surface">${review}</p>
            <div class="mt-2 w-full bg-surface-variant h-1 rounded overflow-hidden">
              <div class="bg-status-review-text h-full" style="width: ${reviewPct}%"></div>
            </div>
            <p class="text-xs text-status-review-text font-medium mt-1">${reviewPct}% of evaluations</p>
          </div>

          <!-- Blocked -->
          <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm border-t-4 border-t-status-block-text">
            <p class="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Blocked</p>
            <p class="text-2xl font-bold text-on-surface">${blocked}</p>
            <div class="mt-2 w-full bg-surface-variant h-1 rounded overflow-hidden">
              <div class="bg-status-block-text h-full" style="width: ${blockPct}%"></div>
            </div>
            <p class="text-xs text-status-block-text font-medium mt-1">${blockPct}% fraud prevented</p>
          </div>

          <!-- Total Volume -->
          <div class="bg-surface-container-lowest p-4 border border-outline-variant rounded-lg shadow-sm col-span-2 md:col-span-1">
            <p class="text-xs font-semibold uppercase tracking-wider text-on-surface-variant mb-1">Total Exposure</p>
            <p class="text-2xl font-bold text-primary">₹${totalAmount}</p>
            <p class="text-xs text-on-surface-variant mt-2 flex items-center gap-1">
              <span class="material-symbols-outlined text-[14px]">account_balance_wallet</span>
              <span>Monitored Volume</span>
            </p>
          </div>
        </div>

        <!-- RISK LEVELS EXPLANATION CARD (Compact Judge Guide) -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-4 shadow-sm space-y-3">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-1 border-b border-outline-variant pb-2.5">
            <div class="flex items-center gap-2">
              <span class="material-symbols-outlined text-primary text-[18px]">verified_user</span>
              <h3 class="text-xs font-bold uppercase tracking-wider text-on-surface">RISK LEVELS</h3>
            </div>
            <p class="text-[11px] text-on-surface-variant italic">
              "Risk tier describes assessed risk. Final action requires human confirmation."
            </p>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <!-- LOW -->
            <div class="p-3 bg-surface-container-low rounded border-l-4 border-l-status-approve-text flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-status-approve-text uppercase">LOW</span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-status-approve-bg text-status-approve-text">APPROVE</span>
                </div>
                <p class="text-xs text-on-surface-variant mt-1.5 leading-snug">Transaction appears normal.</p>
              </div>
              <p class="text-xs text-on-surface font-medium mt-2 pt-1.5 border-t border-outline-variant/30">
                AI recommendation: <strong class="text-status-approve-text font-bold">APPROVE</strong>
              </p>
            </div>

            <!-- MEDIUM -->
            <div class="p-3 bg-surface-container-low rounded border-l-4 border-l-status-review-text flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-status-review-text uppercase">MEDIUM</span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-status-review-bg text-status-review-text">REVIEW</span>
                </div>
                <p class="text-xs text-on-surface-variant mt-1.5 leading-snug">Some risk signals detected.</p>
              </div>
              <p class="text-xs text-on-surface font-medium mt-2 pt-1.5 border-t border-outline-variant/30">
                AI recommendation: <strong class="text-status-review-text font-bold">REVIEW</strong>
              </p>
            </div>

            <!-- HIGH -->
            <div class="p-3 bg-surface-container-low rounded border-l-4 border-l-status-block-text flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-status-block-text uppercase">HIGH</span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-status-block-bg text-status-block-text">BLOCK</span>
                </div>
                <p class="text-xs text-on-surface-variant mt-1.5 leading-snug">Strong fraud indicators detected.</p>
              </div>
              <p class="text-xs text-on-surface font-medium mt-2 pt-1.5 border-t border-outline-variant/30">
                AI recommendation: <strong class="text-status-block-text font-bold">BLOCK</strong>
              </p>
            </div>

            <!-- CRITICAL -->
            <div class="p-3 bg-surface-container-low rounded border-l-4 border-l-error flex flex-col justify-between">
              <div>
                <div class="flex items-center justify-between">
                  <span class="text-xs font-bold text-error uppercase">CRITICAL</span>
                  <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-error text-on-error">BLOCK</span>
                </div>
                <p class="text-xs text-on-surface-variant mt-1.5 leading-snug">Extremely high-confidence fraud risk.</p>
              </div>
              <p class="text-xs text-on-surface font-medium mt-2 pt-1.5 border-t border-outline-variant/30">
                AI recommendation: <strong class="text-error font-bold">BLOCK</strong>
              </p>
            </div>
          </div>
        </div>

        <!-- AI-FIRST PIPELINE COVERAGE & EFFICIENCY PANEL -->
        <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm space-y-4">
          <div class="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-outline-variant pb-3">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-primary text-on-primary text-[10px] font-bold rounded uppercase tracking-wider">AI-First Pipeline</span>
              <h3 class="text-sm font-bold text-on-surface">Measured Model Applicability & Human Escalation</h3>
            </div>
            <span class="text-xs font-mono text-on-surface-variant font-semibold">
              Measured AI Coverage: <strong class="text-primary font-bold">${data.ai_applicability_rate_pct || 0}%</strong>
            </span>
          </div>

          <!-- AI-First Architecture Communication Text -->
          <div class="p-3 bg-surface-container-low border-l-4 border-secondary rounded-r text-xs text-on-surface-variant leading-relaxed">
            <strong>Pipeline Philosophy:</strong> AI analyzes applicable transactions automatically. Transactions outside the model's supported input space are safely escalated to human review.
          </div>

          <!-- 4 Measured Breakdown Cards -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <!-- AI Analyzed -->
            <div class="p-3 bg-surface-container-low rounded border border-outline-variant">
              <span class="text-[10px] font-bold uppercase text-on-surface-variant block">AI Analyzed</span>
              <span class="text-xl font-bold text-primary font-mono block mt-0.5">${data.ai_analyzed_count || 0}</span>
              <span class="text-[11px] text-on-surface-variant block mt-0.5">Scored by Random Forest</span>
            </div>

            <!-- AI Escalated to Review -->
            <div class="p-3 bg-surface-container-low rounded border border-outline-variant">
              <span class="text-[10px] font-bold uppercase text-on-surface-variant block">AI-Escalated Review</span>
              <span class="text-xl font-bold text-status-review-text font-mono block mt-0.5">${data.ai_escalated_count || 0}</span>
              <span class="text-[11px] text-on-surface-variant block mt-0.5">Boundary / Uncertainty gates</span>
            </div>

            <!-- Model Not Applicable -->
            <div class="p-3 bg-surface-container-low rounded border border-outline-variant">
              <span class="text-[10px] font-bold uppercase text-on-surface-variant block">Model Not Applicable</span>
              <span class="text-xl font-bold text-on-surface font-mono block mt-0.5">${data.model_not_applicable_count || 0}</span>
              <span class="text-[11px] text-on-surface-variant block mt-0.5">Escalated to human review</span>
            </div>

            <!-- Final Human Decisions -->
            <div class="p-3 bg-surface-container-low rounded border border-outline-variant">
              <span class="text-[10px] font-bold uppercase text-on-surface-variant block">Final Authorizations</span>
              <span class="text-xl font-bold text-on-surface font-mono block mt-0.5">${data.final_user_approvals || approved} / ${data.final_user_blocks || blocked}</span>
              <span class="text-[11px] text-on-surface-variant block mt-0.5">${data.manual_overrides_count || 0} manual overrides</span>
            </div>
          </div>
        </div>


        <!-- Analytics Bento: Distribution & Tier Charts -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <!-- Decision Distribution -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm lg:col-span-1 flex flex-col justify-between">
            <div>
              <h3 class="text-base font-semibold text-on-surface">Decision Distribution</h3>
              <p class="text-xs text-on-surface-variant mt-0.5">Real-time outcome breakdown</p>
            </div>
            
            <div class="relative w-full h-56 flex items-center justify-center my-4">
              ${monitored === 0 
                ? '<p class="text-sm text-on-surface-variant italic">No transaction records stored yet.</p>'
                : '<canvas id="decisionChart" class="max-h-56"></canvas>'
              }
            </div>

            <div class="grid grid-cols-3 gap-2 pt-3 border-t border-outline-variant text-center">
              <div>
                <p class="text-xs text-status-approve-text font-semibold">Approved</p>
                <p class="text-base font-bold text-on-surface">${approved}</p>
              </div>
              <div>
                <p class="text-xs text-status-review-text font-semibold">Review</p>
                <p class="text-base font-bold text-on-surface">${review}</p>
              </div>
              <div>
                <p class="text-xs text-status-block-text font-semibold">Blocked</p>
                <p class="text-base font-bold text-on-surface">${blocked}</p>
              </div>
            </div>
          </div>

          <!-- Risk Tier Breakdown & System Safety Card -->
          <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-5 shadow-sm lg:col-span-2 flex flex-col justify-between">
            <div>
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="text-base font-semibold text-on-surface">Risk Tier Distribution</h3>
                  <p class="text-xs text-on-surface-variant mt-0.5">Deterministic policy tier categorization</p>
                </div>
                <span class="px-2.5 py-1 text-xs font-semibold bg-surface-variant text-on-surface rounded-full">
                  ${monitored} Total
                </span>
              </div>

              <div class="space-y-4 mt-6">
                <!-- Low Risk -->
                <div>
                  <div class="flex justify-between text-xs font-semibold mb-1">
                    <span class="text-on-surface flex items-center gap-1.5">
                      <span class="w-2.5 h-2.5 rounded-full bg-status-approve-text inline-block"></span>
                      Low Risk (Automated Approval)
                    </span>
                    <span class="text-on-surface-variant">${data.risk_tier_distribution?.LOW || 0}</span>
                  </div>
                  <div class="w-full bg-surface-variant h-2 rounded overflow-hidden">
                    <div class="bg-status-approve-text h-full" style="width: ${monitored > 0 ? ((data.risk_tier_distribution?.LOW || 0) / monitored) * 100 : 0}%"></div>
                  </div>
                </div>

                <!-- Medium Risk -->
                <div>
                  <div class="flex justify-between text-xs font-semibold mb-1">
                    <span class="text-on-surface flex items-center gap-1.5">
                      <span class="w-2.5 h-2.5 rounded-full bg-status-review-text inline-block"></span>
                      Medium Risk (Manual Review / Test Mode)
                    </span>
                    <span class="text-on-surface-variant">${data.risk_tier_distribution?.MEDIUM || 0}</span>
                  </div>
                  <div class="w-full bg-surface-variant h-2 rounded overflow-hidden">
                    <div class="bg-status-review-text h-full" style="width: ${monitored > 0 ? ((data.risk_tier_distribution?.MEDIUM || 0) / monitored) * 100 : 0}%"></div>
                  </div>
                </div>

                <!-- High Risk -->
                <div>
                  <div class="flex justify-between text-xs font-semibold mb-1">
                    <span class="text-on-surface flex items-center gap-1.5">
                      <span class="w-2.5 h-2.5 rounded-full bg-status-block-text inline-block"></span>
                      High Risk (Automated Block)
                    </span>
                    <span class="text-on-surface-variant">${data.risk_tier_distribution?.HIGH || 0}</span>
                  </div>
                  <div class="w-full bg-surface-variant h-2 rounded overflow-hidden">
                    <div class="bg-status-block-text h-full" style="width: ${monitored > 0 ? ((data.risk_tier_distribution?.HIGH || 0) / monitored) * 100 : 0}%"></div>
                  </div>
                </div>

                <!-- Critical Risk -->
                <div>
                  <div class="flex justify-between text-xs font-semibold mb-1">
                    <span class="text-on-surface flex items-center gap-1.5">
                      <span class="w-2.5 h-2.5 rounded-full bg-red-800 inline-block"></span>
                      Critical Exposure (Hard Stop Gate)
                    </span>
                    <span class="text-on-surface-variant">${data.risk_tier_distribution?.CRITICAL || 0}</span>
                  </div>
                  <div class="w-full bg-surface-variant h-2 rounded overflow-hidden">
                    <div class="bg-red-800 h-full" style="width: ${monitored > 0 ? ((data.risk_tier_distribution?.CRITICAL || 0) / monitored) * 100 : 0}%"></div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Architecture Safety Notice -->
            <div class="mt-6 p-3 bg-surface-container rounded-lg border border-outline-variant flex items-start gap-3 text-xs text-on-surface-variant">
              <span class="material-symbols-outlined text-primary text-[20px] shrink-0 mt-0.5">verified_user</span>
              <div>
                <span class="font-semibold text-on-surface">Dual-Pipeline Security Active:</span>
                <span> Razorpay Test Mode transactions lacking benchmark PCA features safely fallback to <strong class="text-status-review-text">ROUTED_TO_MANUAL_REVIEW</strong> rather than fabricating arbitrary ML risk predictions.</span>
              </div>
            </div>
          </div>
        </div>
      `;

      if (monitored > 0 && typeof Chart !== 'undefined') {
        const canvas = document.getElementById('decisionChart');
        if (canvas) {
          if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
          }
          this.chartInstance = new Chart(canvas, {
            type: 'doughnut',
            data: {
              labels: ['Approved', 'Review', 'Blocked'],
              datasets: [{
                data: [approved, review, blocked],
                backgroundColor: ['#006c49', '#d48700', '#ba1a1a'],
                borderWidth: 2,
                borderColor: '#ffffff'
              }]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                legend: {
                  position: 'bottom',
                  labels: {
                    boxWidth: 12,
                    font: { family: 'Inter', size: 11 }
                  }
                }
              },
              cutout: '68%'
            }
          });
        }
      }

    } catch (err) {
      target.innerHTML = `
        <div class="p-6 bg-red-50 border border-error rounded-lg text-error">
          <h4 class="font-semibold flex items-center gap-2">
            <span class="material-symbols-outlined">error</span>
            Failed to Load Overview Metrics
          </h4>
          <p class="text-sm mt-1">${err.message || 'Unable to connect to the RazorRisk API.'}</p>
          <button onclick="OverviewView.loadData()" class="mt-3 px-3 py-1.5 bg-error text-on-error rounded text-xs font-semibold">
            Retry Connection
          </button>
        </div>
      `;
    }
  }
};

window.OverviewView = OverviewView;
