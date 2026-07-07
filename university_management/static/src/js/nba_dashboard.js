/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

class NBADashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            totalScore: 0,
            readinessPct: 0,
            criterionScores: [],
            sarList: [],
            evidenceCount: 0,
            coCount: 0,
            researchCount: 0,
            activeSarId: false,
            activeSarName: "",
            activeProgram: "",
        });

        onMounted(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData(sarId = null) {
        try {
            const data = await this.orm.call(
                "nba.dashboard",
                "get_dashboard_data",
                [],
                { sar_id: sarId }
            );
            Object.assign(this.state, {
                loading: false,
                totalScore: data.total_score || 0,
                readinessPct: data.readiness_pct || 0,
                criterionScores: data.criterion_scores || [],
                sarList: data.sar_list || [],
                evidenceCount: data.evidence_count || 0,
                coCount: data.co_count || 0,
                researchCount: data.research_count || 0,
                activeSarId: data.active_sar_id || false,
                activeSarName: data.active_sar_name || "",
                activeProgram: data.active_program || "",
            });
            this._renderRadarChart();
        } catch (e) {
            console.error("NBA Dashboard load error:", e);
            this.state.loading = false;
        }
    }

    _renderRadarChart() {
        const canvas = document.getElementById("nba_radar_chart");
        if (!canvas || !window.Chart) return;
        // Destroy existing chart
        if (this._radarChart) { this._radarChart.destroy(); }
        const scores = this.state.criterionScores;
        const maxArr = scores.map(s => s.max);
        const actualArr = scores.map(s => s.score);
        const labels = scores.map(s => s.label.split(" – ")[0]);
        this._radarChart = new window.Chart(canvas, {
            type: "radar",
            data: {
                labels,
                datasets: [
                    {
                        label: "Actual Score",
                        data: actualArr,
                        backgroundColor: "rgba(0,51,102,0.2)",
                        borderColor: "rgba(0,51,102,0.8)",
                        pointBackgroundColor: "#003366",
                    },
                    {
                        label: "Max Score",
                        data: maxArr,
                        backgroundColor: "rgba(200,200,200,0.1)",
                        borderColor: "rgba(150,150,150,0.5)",
                        borderDash: [4, 4],
                        pointRadius: 0,
                    },
                ],
            },
            options: {
                responsive: true,
                scales: { r: { beginAtZero: true } },
                plugins: { legend: { position: "bottom" } },
            },
        });
    }

    openSar() {
        if (this.state.activeSarId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "nba.sar",
                res_id: this.state.activeSarId,
                views: [[false, "form"]],
            });
        }
    }

    openResearch() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "nba.research",
            views: [[false, "list"], [false, "form"]],
            domain: this.state.activeSarId
                ? [["sar_id", "=", this.state.activeSarId]]
                : [],
        });
    }

    openEvidence() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "nba.evidence",
            views: [[false, "list"], [false, "form"]],
            domain: this.state.activeSarId
                ? [["sar_id", "=", this.state.activeSarId]]
                : [],
        });
    }

    async switchSar(ev) {
        const sarId = parseInt(ev.target.value);
        if (sarId) {
            await this.loadDashboardData(sarId);
        }
    }

    statusColor(pct) {
        if (pct >= 60) return "#28a745";
        if (pct >= 40) return "#fd7e14";
        return "#dc3545";
    }
}

NBADashboard.template = "university_management.NBADashboard";

registry.category("actions").add("nba_dashboard", NBADashboard);