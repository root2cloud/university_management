import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { UniversityCharts } from "./charts";

class UniversityDashboard extends Component {
    static template = "university_management.DashboardMain";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Check for saved theme preference
        const savedTheme = localStorage.getItem('university_theme') || 'light';

        this.state = useState({
            activeModule: "overview",
            isLoading: true,
            theme: savedTheme,
            overview: {
                total_students: 0,
                total_faculty: 0,
                avg_cgpa: 0,
                new_admissions_this_month: 0,
                placement_rate: 0,
                students_placed: 0,
                active_placement_drives: 0,
                recruiting_companies: 0,
                highest_package: 'N/A',
                total_vehicles: 0,
                active_routes: 0,
                transport_students: 0,
            },
            students: {
                total_enrolled: 0,
                new_this_year: 0,
                pending_admissions: 0,
                low_attendance: 0,
                program_distribution: [],
            },
            faculty: {
                total: 0,
                present_today: 0,
                on_leave: 0,
                avg_rating: 0,
            },
            fees: {
                total_collected: 0,
                monthly_collection: 0,
                total_pending: 0,
                late_payments: 0,
                invoices_count: 0,
                journal_entries: 0,
                posted_payments: 0,
                pending_verification: 0,
                scholarships_applied: 0,
                by_program: [],
                today_collection: 0,
                transaction_count_month: 0,
                payment_mode_breakdown: [],
                reconciliation_stats: {
                    fully_reconciled: 0,
                    partially_reconciled: 0,
                    not_reconciled: 0,
                },
                student_ledger_stats: {
                    total_students_with_dues: 0,
                    total_outstanding_fmt: '0',
                    avg_outstanding_fmt: '0',
                },
            },
            exams: {
                active_exams: 0,
                hall_tickets: 0,
                results_published: 0,
                revaluations: 0,
            },
            hostel: {
                total_rooms: 0,
                occupied_beds: 0,
                pending_complaints: 0,
                occupancy_rate: 0,
            },
            library: {
                total_books: 0,
                books_issued: 0,
                overdue: 0,
                fines_collected: 0,
            },
            assets: {
                total_assets: 0,
                available: 0,
                maintenance_due: 0,
                pending_requests: 0,
                low_stock_alerts: 0,
                pending_handovers: 0,
            },
            assetPurchaseRequests: [],
            assetHandovers: [],
            recentAdmissions: [],
            recentPayments: [],
            departmentStats: [],
            feeCollectionMonthly: [],
            semesterAdmissions: [],
            lastUpdated: null,
            batches: [],
            selectedBatch: null,
            departments: [],
            feeTrendBatch: null,
            feeTrendDept: null,
        });

        // Apply theme on mount
        onMounted(() => {
            this.applyTheme(this.state.theme);
            this.loadDashboardData();

            // Listen for system theme changes
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
                if (!localStorage.getItem('university_theme')) {
                    this.setTheme(e.matches ? 'dark' : 'light');
                }
            });
        });

        onWillUnmount(() => {
            UniversityCharts.destroyAll();
        });
    }

    // Theme management
    setTheme(theme) {
        this.state.theme = theme;
        localStorage.setItem('university_theme', theme);
        this.applyTheme(theme);

        setTimeout(() => {
            UniversityCharts.renderAll(
                this.state,
                (deptId, deptName, count) => this.drillDownDepartment(deptId, deptName, count),
                (progId, progName, count) => this.drillDownProgram(progId, progName, count),
                (label, ds, de) => this.drillDownFeeTrend(label, ds, de),
                (semId, semName, count) => this.drillDownSemester(semId, semName, count),
                (s, l) => this.drillDownFacultyStatus(s, l),
                (dId, dN, cgpa) => this.drillDownDeptCgpa(dId, dN, cgpa),
                (desigId, desigName) => this.drillDownDesignation(desigId, desigName),
                (key) => this.drillDownExam(key),
                (catId, catName) => this.drillDownAssetCategory(catId, catName),
                (stateKey, stateLabel) => this.drillDownAssetState(stateKey, stateLabel),
                (k, l) => this.drillDownHostelOccupancy(k, l),
                (k) => this.drillDownHostelRooms(k),
                (sk, sl) => this.drillDownComplaint(sk, sl),
                (k) => this.drillDownLibrary(k),
                (k) => this.drillDownLibrary(k),
                (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                (k) => this.drillDownTransport(k)
            );
        }, 100);

        // Show theme change notification
        this.notification.add(
            `${theme === 'dark' ? '🌙' : '☀️'} ${theme.charAt(0).toUpperCase() + theme.slice(1)} mode activated`,
            { type: 'info', sticky: false }
        );
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);

        // Update chart colors if needed
        if (UniversityCharts.instances) {
            Object.values(UniversityCharts.instances).forEach(chart => {
                if (chart && chart.update) {
                    chart.update();
                }
            });
        }
    }

    toggleTheme() {
        const newTheme = this.state.theme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }

    async loadDashboardData() {
        this.state.isLoading = true;

        try {
            const [data, batches, departments] = await Promise.all([
                this.orm.call("university.dashboard", "get_dashboard_data", []),
                this.orm.call("university.dashboard", "get_batches", []),
                this.orm.call("university.dashboard", "get_departments", []),
            ]);

            this.updateState(data);
            this.state.batches = batches;
            this.state.departments = departments;
            this.state.lastUpdated = new Date();

        } catch (error) {
            console.error("Failed to load dashboard data:", error);
            this.notification.add(
                "Unable to load dashboard data. Please try again.",
                { type: "danger" }
            );
        } finally {
            this.state.isLoading = false;

            setTimeout(() => {
                UniversityCharts.renderAll(
                    this.state,
                    (deptId, deptName, count) => this.drillDownDepartment(deptId, deptName, count),
                    (progId, progName, count) => this.drillDownProgram(progId, progName, count),
                    (label, ds, de) => this.drillDownFeeTrend(label, ds, de),
                    (semId, semName, count) => this.drillDownSemester(semId, semName, count),
                    (s, l) => this.drillDownFacultyStatus(s, l),
                    (dId, dN, cgpa) => this.drillDownDeptCgpa(dId, dN, cgpa),
                    (desigId, desigName) => this.drillDownDesignation(desigId, desigName),
                    (key) => this.drillDownExam(key),
                    (catId, catName) => this.drillDownAssetCategory(catId, catName),
                    (stateKey, stateLabel) => this.drillDownAssetState(stateKey, stateLabel),
                    (k, l) => this.drillDownHostelOccupancy(k, l),
                    (k) => this.drillDownHostelRooms(k),
                    (sk, sl) => this.drillDownComplaint(sk, sl),
                    (k) => this.drillDownLibrary(k),
                    (k) => this.drillDownLibrary(k),
                    (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                    (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                    (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                    (k) => this.drillDownTransport(k)
                );
            }, 100);
        }
    }

    updateState(data) {
        this.state.overview = { ...this.state.overview, ...(data.overview || {}) };

        this.state.students = {
            ...this.state.students,
            ...(data.students || {}),
            total_enrolled: (data.students && (
                data.students.total_enrolled ??
                data.students.total_active
            )) || this.state.students.total_enrolled || 0,
        };

        this.state.faculty = { ...this.state.faculty, ...(data.faculty || {}) };
        this.state.fees = { ...this.state.fees, ...(data.fees || {}) };
        this.state.exams = { ...this.state.exams, ...(data.exams || {}) };
        this.state.hostel = { ...this.state.hostel, ...(data.hostel || {}) };
        this.state.library = { ...this.state.library, ...(data.library || {}) };

        if (data.assets) {
            this.state.assets = { ...this.state.assets, ...data.assets };
        }
        this.state.assetPurchaseRequests = data.asset_purchase_requests || [];
        this.state.assetHandovers = data.asset_handovers || [];

        this.state.recentAdmissions = data.recent_admissions || [];
        this.state.recentPayments = data.recent_payments || [];
        this.state.departmentStats = data.department_stats || [];
        this.state.feeCollectionMonthly = data.fee_monthly || [];
        this.state.semesterAdmissions = data.semester_admissions || [];
    }

    setActiveModule(moduleKey) {
        this.state.activeModule = moduleKey;

        setTimeout(() => {
            UniversityCharts.renderForModule(
                moduleKey,
                this.state,
                (deptId, deptName, count) => this.drillDownDepartment(deptId, deptName, count),
                (progId, progName, count) => this.drillDownProgram(progId, progName, count),
                (label, ds, de) => this.drillDownFeeTrend(label, ds, de),
                (semId, semName, count) => this.drillDownSemester(semId, semName, count),
                (s, l) => this.drillDownFacultyStatus(s, l),
                (dId, dN, cgpa) => this.drillDownDeptCgpa(dId, dN, cgpa),
                (desigId, desigName) => this.drillDownDesignation(desigId, desigName),
                (key) => this.drillDownExam(key),
                (catId, catName) => this.drillDownAssetCategory(catId, catName),
                (stateKey, stateLabel) => this.drillDownAssetState(stateKey, stateLabel),
                (k, l) => this.drillDownHostelOccupancy(k, l),
                (k) => this.drillDownHostelRooms(k),
                (sk, sl) => this.drillDownComplaint(sk, sl),
                (k) => this.drillDownLibrary(k),
                (k) => this.drillDownLibrary(k),
                (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                (dId, dN, t) => this.drillDownPlacement(dId, dN, t),
                (k) => this.drillDownTransport(k)
            );
        }, 150);
    }

    async filterDeptByBatch(ev) {
        const batchId = ev.target.value ? parseInt(ev.target.value) : null;
        this.state.selectedBatch = batchId;
        try {
            const stats = await this.orm.call(
                "university.dashboard",
                "get_department_stats_by_batch",
                [batchId]
            );
            this.state.departmentStats = stats;
            setTimeout(() => {
                UniversityCharts.renderDepartmentDistribution(stats, (deptId, deptName, count) => {
                    this.drillDownDepartment(deptId, deptName, count);
                });
            }, 50);
        } catch (e) {
            console.error("Batch filter error:", e);
        }
    }

    async filterFeeTrend(ev) {
        const field = ev.target.dataset.field;
        const value = ev.target.value ? parseInt(ev.target.value) : null;
        if (field === 'batch') this.state.feeTrendBatch = value;
        if (field === 'dept') this.state.feeTrendDept = value;

        try {
            const trend = await this.orm.call(
                "university.dashboard",
                "get_fee_trend_filtered",
                [this.state.feeTrendBatch, this.state.feeTrendDept]
            );
            this.state.feeCollectionMonthly = trend;
            setTimeout(() => {
                UniversityCharts.renderFeeTrend(trend, (label, ds, de) => this.drillDownFeeTrend(label, ds, de));
            }, 50);
        } catch (e) {
            console.error("Fee trend filter error:", e);
        }
    }

    // ── Navigation helpers ──────────────────────────────────────────────────
    // FIX 3: Wrap all navigateTo calls in try/catch so missing actions
    // don't throw an uncaught OwlError ("Invalid handler: undefined").
    navigateTo(actionXmlId) {
        try {
            this.action.doAction(actionXmlId);
        } catch (e) {
            console.warn("Navigation not available:", actionXmlId, e);
        }
    }

    drillDownTransport(key) {
        const config = {
            vehicles: {
                name: 'Transport — All Vehicles',
                model: 'transport.vehicle',
                domain: [['active', '=', true]],
            },
            routes: {
                name: 'Transport — Active Routes',
                model: 'transport.route',
                domain: [['active', '=', true]],
            },
            students: {
                name: 'Transport — Students Using Transport',
                model: 'transport.allocation',
                domain: [['state', '=', 'active']],
            },
        };
        const c = config[key];
        if (!c) return;
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: c.name,
                res_model: c.model,
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: c.domain,
            });
        } catch (e) { console.warn('drillDownTransport failed:', e); }
    }

    drillDownPlacement(deptId, deptName, type) {
        try {
            if (type === 'placed') {
                const domain = [['state', '=', 'selected']];
                if (deptId) domain.push(['department_id', '=', deptId]);
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: deptId ? `${deptName} — Placed Students` : 'All Placed Students',
                    res_model: 'placement.application',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain,
                });
            } else {
                // not_placed — students with no selected placement application
                const domain = [['state', 'in', ['active', 'enrolled', 'admitted']]];
                if (deptId) domain.push(['department_id', '=', deptId]);
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: deptId ? `${deptName} — Not Yet Placed Students` : 'Students Not Yet Placed',
                    res_model: 'student.student',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain,
                });
            }
        } catch (e) { console.warn('drillDownPlacement failed:', e); }
    }

    drillDownLibrary(key) {
        const config = {
            total: {
                name: 'Library — All Books',
                model: 'library.book',
                domain: [],
            },
            issued: {
                name: 'Library — Currently Issued',
                model: 'library.issue',
                domain: [['state', '=', 'issued']],
            },
            overdue: {
                name: 'Library — Overdue Returns',
                model: 'library.issue',
                domain: [['state', '=', 'overdue']],
            },
            available: {
                name: 'Library — Available Books',
                model: 'library.book',
                domain: [['state', '=', 'available']],
            },
        };
        const c = config[key];
        if (!c) return;
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: c.name,
                res_model: c.model,
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: c.domain,
            });
        } catch (e) { console.warn('drillDownLibrary failed:', e); }
    }

    drillDownHostelOccupancy(key, label) {
        try {
            if (key === 'occupied') {
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Hostel — Occupied Rooms',
                    res_model: 'hostel.allocation',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [['state', 'in', ['active', 'allocated', 'occupied']]],
                });
            } else {
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Hostel — Vacant Rooms',
                    res_model: 'hostel.room',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [['active', '=', true], ['status', '=', 'available']],
                });
            }
        } catch (e) { console.warn('drillDownHostelOccupancy failed:', e); }
    }

    drillDownHostelRooms(key) {
        try {
            const actions = {
                total: {
                    name: 'Hostel — All Rooms',
                    model: 'hostel.room',
                    domain: [['active', '=', true]],
                },
                occupied: {
                    name: 'Hostel — Occupied Allocations',
                    model: 'hostel.allocation',
                    domain: [['state', 'in', ['active', 'allocated', 'occupied']]],
                },
                vacant: {
                    name: 'Hostel — Vacant Rooms',
                    model: 'hostel.room',
                    domain: [['active', '=', true], ['status', '=', 'available']],
                },
            };
            const a = actions[key];
            if (!a) return;
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: a.name,
                res_model: a.model,
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: a.domain,
            });
        } catch (e) { console.warn('drillDownHostelRooms failed:', e); }
    }

    drillDownComplaint(stateKey, stateLabel) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Hostel Complaints — ${stateLabel}`,
                res_model: 'hostel.complaint',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [['state', '=', stateKey]],
            });
        } catch (e) { console.warn('drillDownComplaint failed:', e); }
    }

    drillDownAssetCategory(catId, catName) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Assets — ${catName}`,
                res_model: 'asset.asset',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    ['category_id', '=', catId],
                    ['state', 'not in', ['disposed', 'condemned', 'lost']],
                ],
            });
        } catch (e) { console.warn('drillDownAssetCategory failed:', e); }
    }

    drillDownAssetState(stateKey, stateLabel) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Assets — ${stateLabel}`,
                res_model: 'asset.asset',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [['state', '=', stateKey]],
            });
        } catch (e) { console.warn('drillDownAssetState failed:', e); }
    }

    openPurchaseRecord(id) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'asset.purchase.request',
                view_mode: 'form',
                views: [[false, 'form']],
                res_id: id,
                target: 'current',
            });
        } catch (e) { console.warn('openPurchaseRecord failed:', e); }
    }

    openHandoverRecord(id) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'asset.handover',
                view_mode: 'form',
                views: [[false, 'form']],
                res_id: id,
                target: 'current',
            });
        } catch (e) { console.warn('openHandoverRecord failed:', e); }
    }

    drillDownExam(key) {
        const config = {
            active_exams: {
                name: 'Active Examinations',
                model: 'examination.examination',
                domain: [],
            },
            hall_tickets: {
                name: 'Hall Tickets Issued',
                model: 'examination.hall.ticket',
                domain: [['state', 'in', ['generated', 'issued', 'printed']]],
            },
            results_published: {
                name: 'Results Published',
                model: 'examination.result',
                domain: [['state', '=', 'published']],
            },
            revaluations: {
                name: 'Revaluation Requests',
                model: 'examination.revaluation',
                domain: [['state', 'in', ['submitted', 'under_review', 'revaluation_in_progress', 'completed']]],
            },
        };
        const c = config[key];
        if (!c) return;
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: c.name,
                res_model: c.model,
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: c.domain,
            });
        } catch (e) {
            console.warn('drillDownExam failed:', e);
        }
    }

    drillDownFacultyStatus(status, label) {
        const today = new Date().toISOString().split('T')[0];
        try {
            if (status === 'present') {
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: `Faculty — Present Today`,
                    res_model: 'faculty.attendance',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [['date', '=', today], ['state', '=', 'present']],
                });
            } else if (status === 'on_leave') {
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: `Faculty — On Leave Today`,
                    res_model: 'faculty.leave',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [
                        ['date_from', '<=', today],
                        ['date_to', '>=', today],
                        ['state', '=', 'approved'],
                    ],
                });
            } else {
                // Absent — open attendance with no record today (show all today's attendance to cross-check)
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: `Faculty — Attendance Today`,
                    res_model: 'faculty.attendance',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [['date', '=', today]],
                });
            }
        } catch (e) {
            console.warn('drillDownFacultyStatus failed:', e);
        }
    }

    drillDownDeptCgpa(deptId, deptName, avgCgpa) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `${deptName} — Students (Avg CGPA: ${avgCgpa})`,
                res_model: 'student.student',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    ['department_id', '=', deptId],
                    ['state', 'in', ['active', 'enrolled', 'admitted']],
                ],
                context: { search_default_department_id: deptId },
            });
        } catch (e) {
            console.warn('drillDownDeptCgpa failed:', e);
        }
    }

    drillDownDesignation(designationId, designationName) {
        try {
            const domain = designationId
                ? [['designation_id', '=', designationId], ['active', '=', true]]
                : [['designation_id', '=', false], ['active', '=', true]];
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Faculty — ${designationName}`,
                res_model: 'faculty.faculty',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain,
            });
        } catch (e) {
            console.warn('drillDownDesignation failed:', e);
        }
    }

    openPaymentRecord(id) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'fee.payment',
                view_mode: 'form',
                views: [[false, 'form']],
                res_id: id,
                target: 'current',
            });
        } catch (e) {
            console.warn('openPaymentRecord failed:', e);
        }
    }

    openAdmissionRecord(id, model) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: model || 'student.student',
                view_mode: 'form',
                views: [[false, 'form']],
                res_id: id,
                target: 'current',
            });
        } catch (e) {
            console.warn('openAdmissionRecord failed:', e);
        }
    }

    drillDownSemester(semId, semName, count) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `${semName} — Registrations (${count})`,
                res_model: 'student.registration',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    ['semester_id', '=', semId],
                ],
                context: {
                    search_default_semester_id: semId,
                },
            });
        } catch (e) {
            console.warn('drillDownSemester failed:', e);
        }
    }

    drillDownFeeTrend(monthLabel, dateStart, dateEnd) {
        try {
            // Show ALL fee payments related to this month:
            // 1. Payments actually received in this month (payment_date in range)
            // 2. Fees that were DUE in this month (due_date in range) — including
            //    those paid late (after the month) or still unpaid
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Fee Collection — ${monthLabel} (due or paid this month)`,
                res_model: 'fee.payment',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    '|',
                    // Paid/received in this calendar month
                    '&',
                        ['payment_date', '>=', dateStart],
                        ['payment_date', '<=', dateEnd],
                    // Due in this calendar month (regardless of when paid)
                    '&',
                        ['due_date', '>=', dateStart],
                        ['due_date', '<=', dateEnd],
                ],
                context: {
                    search_default_group_by_state: 1,
                },
            });
        } catch (e) {
            console.warn('drillDownFeeTrend failed:', e);
        }
    }

    drillDownProgram(progId, progName, studentCount) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `${progName} — Students (${studentCount})`,
                res_model: 'student.student',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    ['program_id', '=', progId],
                    ['state', 'in', ['active', 'enrolled', 'admitted']],
                ],
                context: {
                    search_default_program_id: progId,
                },
            });
        } catch (e) {
            console.warn('drillDownProgram failed:', e);
        }
    }

    drillDownDepartment(deptId, deptName, studentCount) {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `${deptName} — Students (${studentCount})`,
                res_model: 'student.student',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    ['department_id', '=', deptId],
                    ['state', 'in', ['active', 'enrolled', 'admitted']],
                ],
                context: {
                    search_default_department_id: deptId,
                },
            });
        } catch (e) {
            console.warn('drillDownDepartment failed:', e);
            // Fallback: navigate to all students filtered
            this.notification.add(
                `Showing students for ${deptName}`,
                { type: 'info', sticky: false }
            );
        }
    }

    openStudents() {
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Total Enrolled Students',
                res_model: 'student.student',
                view_mode: 'kanban,list,form',
                views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
                domain: [],
                context: {
                    search_default_filter_enrolled: 1,
                    search_default_group_by_program: 1,
                },
            });
        } catch (e) {
            console.warn('openStudents failed:', e);
            this.navigateTo("university_management.action_student");
        }
    }

    async openLowAttendance() {
        try {
            const studentIds = await this.orm.call(
                'university.dashboard',
                'get_low_attendance_student_ids',
                [],
                {}
            );
            if (!studentIds || studentIds.length === 0) {
                this.notification.add('No students with attendance below 75%.', { type: 'info' });
                return;
            }
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Low Attendance Students (<75%)',
                res_model: 'student.attendance',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [['student_id', 'in', studentIds]],
                context: { search_default_group_by_student: 1 },
            });
        } catch (e) {
            console.warn('openLowAttendance failed:', e);
        }
    }
    openNewThisYear() {
        const yearStart = new Date(new Date().getFullYear(), 0, 1)
            .toISOString().split('T')[0];
        try {
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'New Admissions This Year',
                res_model: 'student.admission',
                view_mode: 'list,form',
                views: [[false, 'list'], [false, 'form']],
                domain: [
                    ['state', 'in', ['approved', 'admitted']],
                    ['application_date', '>=', yearStart],
                ],
                context: { search_default_group_by_program: 1 },
            });
        } catch (e) {
            console.warn('openNewThisYear failed:', e);
        }
    }
    openAdmissions() { this.navigateTo("university_management.action_student_admission"); }
    openFaculty() { this.navigateTo("university_management.action_faculty"); }
    openFacultyPresent() { this.drillDownFacultyStatus('present', 'Present Today'); }
    openFacultyOnLeave() { this.drillDownFacultyStatus('on_leave', 'On Leave Today'); }
    openFeePayments() { this.navigateTo("university_management.action_fee_payment"); }

    openFeeCollectionMonth() {
        try {
            const today = new Date();
            const pad = (n) => String(n).padStart(2, '0');
            const monthStartStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-01`;
            const monthName = today.toLocaleString('en-IN', { month: 'long', year: 'numeric' });

            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Fee Collection — ${monthName}`,
                res_model: 'fee.payment',
                view_mode: 'kanban,list,form',
                views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
                domain: [
                    ['state', 'in', ['paid', 'partial']],
                    ['payment_date', '>=', monthStartStr],
                ],
                context: { search_default_this_month: 1 },
            });
        } catch (e) {
            console.warn('openFeeCollectionMonth failed:', e);
        }
    }

    openFeeCollectionYear() {
        try {
            const today = new Date();
            const yearStartStr = `${today.getFullYear()}-01-01`;

            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Fee Collection — Year ${today.getFullYear()}`,
                res_model: 'fee.payment',
                view_mode: 'kanban,list,form',
                views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
                domain: [
                    ['state', 'in', ['paid', 'partial']],
                    ['payment_date', '>=', yearStartStr],
                ],
            });
        } catch (e) {
            console.warn('openFeeCollectionYear failed:', e);
        }
    }

    openFeeCollectionToday() {
        try {
            const today = new Date();
            const pad = (n) => String(n).padStart(2, '0');
            const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
            const label = today.toLocaleString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });

            this.action.doAction({
                type: 'ir.actions.act_window',
                name: `Fee Collection — ${label}`,
                res_model: 'fee.payment',
                view_mode: 'kanban,list,form',
                views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
                domain: [
                    ['state', 'in', ['paid', 'partial']],
                    ['payment_date', '=', todayStr],
                ],
            });
        } catch (e) {
            console.warn('openFeeCollectionToday failed:', e);
        }
    }

    openFeeStructures() { this.navigateTo("university_management.action_fee_structure"); }

    openFeeOverdue() {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: "Fee Payments",
                res_model: "fee.payment",
                view_mode: "kanban,list,form",
                views: [[false, "kanban"], [false, "list"], [false, "form"]],
                domain: [["state", "in", ["draft", "invoiced", "pending", "partial", "verified"]]],
                context: {
                    search_default_group_by_state: 1,
                },
            });
        } catch (e) {
            console.warn("openFeeOverdue failed:", e);
        }
    }
    openExaminations() { this.navigateTo("university_management.action_examination"); }
    openHallTickets() { this.navigateTo("university_management.action_examination_hall_ticket"); }
    openExamResults() { this.navigateTo("university_management.action_exam_result"); }
    openHostel() { this.navigateTo("university_management.action_hostel_hostel"); }
    openHostelComplaints() { this.navigateTo("university_management.action_hostel_complaint"); }
    openLibrary() { this.navigateTo("university_management.action_library_book"); }
    openLibraryIssues() { this.navigateTo("university_management.action_library_issue"); }
    openPlacement() { this.navigateTo("university_management.action_placement_drive"); }
    openTransport() { this.navigateTo("university_management.action_transport_vehicle"); }
    openAssets() { this.navigateTo("university_management.action_asset_asset"); }
    openPurchaseRequests() { this.navigateTo("university_management.action_asset_purchase_request"); }
    openHandoverRequests() { this.navigateTo("university_management.action_asset_handover"); }

    // Utility methods
    formatNumber(num) {
        if (!num && num !== 0) return '0';
        if (num >= 10000000) return (num / 10000000).toFixed(1) + 'Cr';
        if (num >= 100000) return (num / 100000).toFixed(1) + 'L';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }

    formatCurrency(amount) {
        if (!amount) return '₹0';
        return '₹' + this.formatNumber(amount);
    }

    getCurrentDate() {
        return new Date().toLocaleDateString('en-IN', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
    }

    getGreeting() {
        const hour = new Date().getHours();
        if (hour < 12) return 'Good morning';
        if (hour < 17) return 'Good afternoon';
        if (hour < 20) return 'Good evening';
        return 'Good night';
    }

    get navModules() {
        return [
            { key: "overview", label: "Overview", icon: "fa-tachometer", badge: null },
            { key: "students", label: "Students", icon: "fa-graduation-cap", badge: this.state.students?.pending_admissions || 0 },
            { key: "faculty", label: "Faculty", icon: "fa-users", badge: null },
            { key: "fees", label: "Fees", icon: "fa-money", badge: this.state.fees?.pending_verification || 0 },
            { key: "exams", label: "Exams", icon: "fa-file-text", badge: this.state.exams?.active_exams || 0 },
            { key: "hostel", label: "Hostel", icon: "fa-building", badge: this.state.hostel?.pending_complaints || 0 },
            { key: "library", label: "Library", icon: "fa-book", badge: this.state.library?.overdue || 0 },
            { key: "placement", label: "Placement", icon: "fa-briefcase", badge: this.state.overview?.active_placement_drives || 0 },
            { key: "transport", label: "Transport", icon: "fa-bus", badge: null },
            { key: "assets", label: "Assets", icon: "fa-cubes", badge: this.state.assets?.pending_requests || 0 },
        ];
    }
}

registry.category("actions").add("university_dashboard_main", UniversityDashboard);
export { UniversityDashboard };