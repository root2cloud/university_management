/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

// ─── Activity type display helpers ────────────────────────────────────────────
const ACTIVITY_LABELS = {
    mandatory:       'MSME Mandatory',
    self_driven:     'Self Driven',
    workshop:        'Workshop',
    seminar:         'Seminar',
    innovation_talk: 'Innovation Talk',
    entrepreneurship:'Entrepreneurship',
    hackathon:       'Hackathon',
    other:           'Other',
};

const STATE_LABELS = {
    planning:        'Planning',
    poster_pending:  'Poster Pending',
    poster_approved: 'Poster Approved',
    ongoing:         'Ongoing',
    completed:       'Completed',
    report_pending:  'Report Pending',
    report_approved: 'Report Approved',
    archived:        'Archived',
};

// ─── Wait for Chart.js (CDN may load after onMounted fires) ──────────────────
// This is the primary fix for the empty charts: Chart.js is loaded from CDN
// via a <script> tag in __manifest__.py. onMounted can fire before the CDN
// response arrives, leaving window.Chart undefined. We poll until it's ready.
function waitForChart(timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
        if (window.Chart) { resolve(window.Chart); return; }
        const start = Date.now();
        const interval = setInterval(() => {
            if (window.Chart) {
                clearInterval(interval);
                resolve(window.Chart);
            } else if (Date.now() - start > timeoutMs) {
                clearInterval(interval);
                reject(new Error('Chart.js did not load within timeout'));
            }
        }, 100);
    });
}

// ─── Chart colour palette ─────────────────────────────────────────────────────
const PALETTE = [
    '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e',
    '#e74a3b', '#858796', '#5a5c69', '#2ecc71',
];

class IICDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            error: null,

            // ── KPI counters ────────────────────────────────────────────────
            totalEvents: 0,
            mandatoryCount: 0,
            selfDrivenCount: 0,
            completedEvents: 0,
            pendingReports: 0,
            reportSubmitted: 0,
            complianceScore: 0,
            currentQuarter: '',

            // ── Attendance summary ─────────────────────────────────────────
            totalRegistered: 0,
            totalPresent: 0,
            totalAbsent: 0,
            overallPct: 0,
            avgParticipationPct: 0,

            // ── Breakdown tables ───────────────────────────────────────────
            eventAttendance: [],       // per-event attendance rows
            deptBreakdown: [],         // per-department attendance
            batchBreakdown: [],        // per-batch attendance

            // ── Chart/quarter data ─────────────────────────────────────────
            quarterlyBreakdown: {},
            activityBreakdown: [],
            recentEvents: [],

            // ── Active tab for breakdown panel ────────────────────────────
            activeTab: 'event',       // 'event' | 'dept' | 'batch'
        });

        // Keep chart instance refs so we can destroy before re-render
        this._charts = {};

        onMounted(async () => {
            await this.loadDashboardData();
        });
    }

    // ── Data loading ────────────────────────────────────────────────────────

    async loadDashboardData() {
        try {
            const data = await this.orm.call(
                "iic.dashboard",
                "get_dashboard_data",
                [],
                {}
            );

            Object.assign(this.state, {
                loading: false,
                error: null,

                totalEvents:          data.total_events            || 0,
                mandatoryCount:       data.mandatory_count         || 0,
                selfDrivenCount:      data.self_driven_count       || 0,
                completedEvents:      data.completed_count         || 0,
                pendingReports:       data.pending_count           || 0,
                reportSubmitted:      data.report_submitted        || 0,
                complianceScore:      data.compliance_score        || 0,
                currentQuarter:       data.current_quarter         || '',

                totalRegistered:      data.total_registered        || 0,
                totalPresent:         data.total_present           || 0,
                totalAbsent:          data.total_absent            || 0,
                overallPct:           data.overall_participation_pct || 0,
                avgParticipationPct:  data.avg_participation_pct   || 0,

                eventAttendance:      data.event_attendance        || [],
                deptBreakdown:        data.dept_breakdown          || [],
                batchBreakdown:       data.batch_breakdown         || [],

                quarterlyBreakdown:   data.quarters                || {},
                activityBreakdown:    data.activity_chart          || [],
                recentEvents:         data.recent_events           || [],
            });

            // Render charts AFTER state is set and DOM has re-rendered.
            // We defer via waitForChart + requestAnimationFrame to ensure
            // canvas elements are in the DOM before Chart.js tries to use them.
            try {
                await waitForChart();
                // One rAF to let OWL flush the DOM update
                await new Promise(r => requestAnimationFrame(r));
                this._renderCharts(data);
            } catch (chartErr) {
                console.warn('IIC Dashboard: Chart.js unavailable —', chartErr.message);
            }

        } catch (e) {
            console.error("IIC Dashboard load failed:", e);
            this.state.loading = false;
            this.state.error = "Failed to load dashboard data. Please refresh.";
        }
    }

    // ── Tab switching ────────────────────────────────────────────────────────

    setTab(tab) {
        this.state.activeTab = tab;
    }

    // ── Chart rendering ──────────────────────────────────────────────────────

    _destroyChart(id) {
        if (this._charts[id]) {
            this._charts[id].destroy();
            delete this._charts[id];
        }
    }

    _renderCharts(data) {
        this._renderQuarterlyChart(data.quarters || {});
        this._renderActivityTypeChart(data.activity_chart || []);
    }

    _renderQuarterlyChart(quarters) {
        const canvasId = 'iicQuarterlyChart';
        this._destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas || !window.Chart) return;

        const labels    = ['Q1', 'Q2', 'Q3', 'Q4'];
        const totals    = labels.map(q => (quarters[q] || {}).total      || 0);
        const completed = labels.map(q => (quarters[q] || {}).completed  || 0);
        const present   = labels.map(q => (quarters[q] || {}).present    || 0);

        this._charts[canvasId] = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Total Events',
                        data: totals,
                        backgroundColor: 'rgba(78, 115, 223, 0.75)',
                        borderColor:     'rgba(78, 115, 223, 1)',
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Completed',
                        data: completed,
                        backgroundColor: 'rgba(28, 200, 138, 0.75)',
                        borderColor:     'rgba(28, 200, 138, 1)',
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Students Present',
                        data: present,
                        backgroundColor: 'rgba(54, 185, 204, 0.75)',
                        borderColor:     'rgba(54, 185, 204, 1)',
                        borderWidth: 1,
                        borderRadius: 4,
                        // Render as line so the three series don't crowd
                        type: 'line',
                        yAxisID: 'y2',
                        tension: 0.4,
                        fill: false,
                        pointRadius: 5,
                        pointHoverRadius: 7,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                    tooltip: {
                        callbacks: {
                            // Append participation % to the "Students Present" tooltip
                            afterBody: (items) => {
                                const q = items[0]?.label;
                                const pct = (this.state.quarterlyBreakdown[q] || {}).participation_pct;
                                return pct != null ? [`Participation: ${pct}%`] : [];
                            },
                        },
                    },
                },
                scales: {
                    y:  { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: 'Events' } },
                    y2: { beginAtZero: true, position: 'right', ticks: { precision: 0 }, title: { display: true, text: 'Students Present' }, grid: { drawOnChartArea: false } },
                },
            },
        });
    }

    _renderActivityTypeChart(activityData) {
        const canvasId = 'iicActivityTypeChart';
        this._destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas || !window.Chart) return;

        // Filter to types that have at least 1 event so the doughnut isn't
        // dominated by empty slices — but keep a minimum of all types if all 0
        const nonZero = activityData.filter(a => a.value > 0);
        const display = nonZero.length > 0 ? nonZero : activityData;

        this._charts[canvasId] = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: display.map(a => a.label),
                datasets: [{
                    data:            display.map(a => a.value),
                    backgroundColor: PALETTE.slice(0, display.length),
                    borderWidth: 2,
                    hoverOffset: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 12,
                            font: { size: 11 },
                            padding: 10,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct   = total ? Math.round(ctx.parsed / total * 100) : 0;
                                return `  ${ctx.label}: ${ctx.parsed} (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    // ── Display helpers ──────────────────────────────────────────────────────

    activityLabel(type) {
        return ACTIVITY_LABELS[type] || type;
    }

    stateLabel(state) {
        return STATE_LABELS[state] || state;
    }

    // ── Navigation helpers ──────────────────────────────────────────────────

    openEvent(eventId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'iic.event',
            res_id: eventId,
            views: [[false, 'form']],
        });
    }
}

IICDashboard.template = "university_management.IICDashboard";

registry.category("actions").add("iic_dashboard", IICDashboard);