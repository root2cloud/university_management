/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useState } from "@odoo/owl";

class NAACIQACDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            overallReadiness: 0,
            criterionScores: [],
            totalEvidence: 0,
            verifiedEvidence: 0,
            pendingEvidence: 0,
            totalActivities: 0,
            verifiedActivities: 0,
            pendingActivities: 0,
            totalPapers: 0,
            totalPatents: 0,
            totalGrants: 0,
            placements: 0,
            higherStudies: 0,
            entrepreneurs: 0,
            deptReadiness: [],
            recentActivities: [],
        });

        onMounted(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            const data = await this.orm.call(
                "naac.dashboard",
                "get_dashboard_data",
                [],
                {}
            );
            Object.assign(this.state, {
                loading: false,
                overallReadiness: data.overall_readiness || 0,
                criterionScores: data.criterion_scores || [],
                totalEvidence: data.total_evidence || 0,
                verifiedEvidence: data.verified_evidence || 0,
                pendingEvidence: data.pending_evidence || 0,
                totalActivities: data.total_activities || 0,
                verifiedActivities: data.verified_activities || 0,
                pendingActivities: data.pending_activities || 0,
                totalPapers: data.total_papers || 0,
                totalPatents: data.total_patents || 0,
                totalGrants: data.total_grants || 0,
                placements: data.placements || 0,
                higherStudies: data.higher_studies || 0,
                entrepreneurs: data.entrepreneurs || 0,
                deptReadiness: data.dept_readiness || [],
                recentActivities: data.recent_activities || [],
            });
        } catch (e) {
            console.error("NAAC Dashboard load failed:", e);
            this.state.loading = false;
        }
    }

    getReadinessClass(score) {
        if (score >= 75) return "bg-success";
        if (score >= 50) return "bg-warning";
        return "bg-danger";
    }
}

NAACIQACDashboard.template = "university_management.NAACDashboard";

registry.category("actions").add("naac_iqac_dashboard", NAACIQACDashboard);
registry.category("actions").add("naac_dept_dashboard", NAACIQACDashboard);
registry.category("actions").add("combined_admin_dashboard", NAACIQACDashboard);