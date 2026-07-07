/* ============================================================
   UNIVERSITY MANAGEMENT SYSTEM - CHARTS.JS
   Enhanced with animations and interactive features
   ============================================================ */

const UniversityCharts = {

    instances: {},

    palette: {
        blue:   '#3b82f6',
        blueDark: '#2563eb',
        green:  '#10b981',
        greenDark: '#059669',
        amber:  '#f59e0b',
        amberDark: '#d97706',
        red:    '#ef4444',
        redDark: '#dc2626',
        purple: '#8b5cf6',
        purpleDark: '#7c3aed',
        teal:   '#14b8a6',
        tealDark: '#0d9488',
        navy:   '#1e293b',
        orange: '#f97316',
        orangeDark: '#ea580c',
        pink:   '#ec4899',
        pinkDark: '#db2777',
        indigo: '#6366f1',
        indigoDark: '#4f46e5',
        cyan:   '#06b6d4',
        cyanDark: '#0891b2',
    },

    multiColors: [
        '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
        '#8b5cf6', '#14b8a6', '#f97316', '#1e293b',
        '#ec4899', '#6366f1', '#06b6d4',
    ],

    // ─────────────────────────────────────────────────────────────
    // INTERNAL HELPERS
    // ─────────────────────────────────────────────────────────────

    _destroy(id) {
        if (this.instances[id]) {
            this.instances[id].destroy();
            delete this.instances[id];
        }
    },

    _canvas(id) {
        return document.getElementById(id);
    },

    _gradient(ctx, color1, color2, direction = 'vertical') {
        if (direction === 'vertical') {
            const g = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
            g.addColorStop(0, color1);
            g.addColorStop(0.6, color2 || color1);
            g.addColorStop(1, color2 ? color2 + 'dd' : color1 + 'dd');
            return g;
        } else {
            const g = ctx.createLinearGradient(0, 0, ctx.canvas.width, 0);
            g.addColorStop(0, color1);
            g.addColorStop(1, color2 || color1);
            return g;
        }
    },

    _initDefaults() {
        if (typeof Chart === 'undefined') {
            console.warn('[UniversityCharts] Chart.js not loaded yet.');
            return false;
        }
        Chart.defaults.font.family = "'Inter', 'Segoe UI', 'Roboto', Arial, sans-serif";
        Chart.defaults.color = '#64748b';
        Chart.defaults.plugins.legend.labels.boxWidth = 12;
        Chart.defaults.plugins.legend.labels.padding = 12;
        Chart.defaults.plugins.legend.labels.font = { size: 12, weight: '500' };
        Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(30,41,59,0.95)';
        Chart.defaults.plugins.tooltip.padding = 12;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
        Chart.defaults.plugins.tooltip.titleFont = { size: 13, weight: '600' };
        Chart.defaults.plugins.tooltip.bodyFont  = { size: 12 };
        Chart.defaults.plugins.tooltip.boxPadding = 4;
        Chart.defaults.plugins.tooltip.usePointStyle = true;
        Chart.defaults.responsive = true;
        Chart.defaults.maintainAspectRatio = false;
        return true;
    },

    // ─────────────────────────────────────────────────────────────
    // 1. MONTHLY FEE COLLECTION TREND (Bar with animation)
    // ─────────────────────────────────────────────────────────────
    renderFeeTrend(feeMonthly, onDrillDown) {
        const id = 'uni-fee-trend-chart';
        const canvas = this._canvas(id);
        if (!canvas || !feeMonthly.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const labels = feeMonthly.map(m => m.label);
        const values = feeMonthly.map(m => m.value);

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Fee Collection',
                    data: values,
                    backgroundColor: (context) => {
                        const chart = context.chart;
                        const {ctx, chartArea} = chart;
                        if (!chartArea) return this.palette.green;
                        return this._gradient(ctx, this.palette.green, this.palette.teal);
                    },
                    borderColor: this.palette.greenDark,
                    borderWidth: 0,
                    borderRadius: 8,
                    barPercentage: 0.7,
                    categoryPercentage: 0.8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart',
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                let value = ctx.parsed.y;
                                let formatted;
                                if (value >= 10000000) formatted = '₹ ' + (value/10000000).toFixed(2) + ' Cr';
                                else if (value >= 100000) formatted = '₹ ' + (value/100000).toFixed(2) + ' L';
                                else if (value >= 1000) formatted = '₹ ' + (value/1000).toFixed(2) + ' K';
                                else formatted = '₹ ' + value;
                                return onDrillDown ? formatted + ' — click to view' : formatted;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#e2e8f0', drawBorder: false },
                        ticks: {
                            callback: (value) => {
                                if (value >= 10000000) return '₹' + (value/10000000).toFixed(1) + 'Cr';
                                if (value >= 100000) return '₹' + (value/100000).toFixed(1) + 'L';
                                if (value >= 1000) return '₹' + (value/1000).toFixed(1) + 'K';
                                return '₹' + value;
                            }
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 11, weight: '500' } }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        const month = feeMonthly[index];
                        if (month) {
                            onDrillDown(month.label, month.date_start, month.date_end);
                        }
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 2. SEMESTER ADMISSIONS TREND (Bar)
    // ─────────────────────────────────────────────────────────────
    renderSemesterAdmissions(semData, onDrillDown) {
        const id = 'uni-semester-chart';
        const canvas = this._canvas(id);
        if (!canvas || !semData.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: semData.map(s => s.label),
                datasets: [{
                    label: 'Student Registrations',
                    data: semData.map(s => s.value),
                    backgroundColor: (context) => {
                        const chart = context.chart;
                        const {ctx, chartArea} = chart;
                        if (!chartArea) return this.palette.blue;
                        return this._gradient(ctx, this.palette.blue, this.palette.indigo);
                    },
                    borderColor: this.palette.blueDark,
                    borderWidth: 0,
                    borderRadius: 8,
                    barPercentage: 0.7,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart',
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const sem = semData[ctx.dataIndex];
                                const suffix = onDrillDown ? ' — click to view' : '';
                                return `${ctx.parsed.y} students${suffix}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#e2e8f0' },
                        ticks: { stepSize: 1 }
                    },
                    x: { grid: { display: false } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        const sem = semData[index];
                        if (sem) {
                            onDrillDown(sem.id, sem.label, sem.value);
                        }
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 3. DEPARTMENT STUDENT DISTRIBUTION (Doughnut with animation)
    // ─────────────────────────────────────────────────────────────
    renderDepartmentDistribution(deptStats, onDrillDown) {
        const id = 'uni-department-chart';
        const canvas = this._canvas(id);
        if (!canvas || !deptStats.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        // Store deptStats on the canvas for external access
        canvas._deptStats = deptStats;

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: deptStats.map(d => d.name),
                datasets: [{
                    data: deptStats.map(d => d.students),
                    backgroundColor: this.multiColors.slice(0, deptStats.length),
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 15,
                    spacing: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 2000,
                    easing: 'easeInOutQuart',
                },
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            padding: 16,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            generateLabels(chart) {
                                const data = chart.data;
                                const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
                                return data.labels.map((label, i) => ({
                                    text: `${label} (${data.datasets[0].data[i]})`,
                                    fillStyle: data.datasets[0].backgroundColor[i],
                                    strokeStyle: '#fff',
                                    lineWidth: 2,
                                    hidden: false,
                                    index: i,
                                    pointStyle: 'circle',
                                }));
                            }
                        },
                        onClick: (e, legendItem, legend) => {
                            const index = legendItem.index;
                            const dept = deptStats[index];
                            if (dept && onDrillDown) {
                                onDrillDown(dept.id, dept.name, dept.students);
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const value = ctx.parsed;
                                const percentage = ((value / total) * 100).toFixed(1);
                                return `${ctx.label}: ${value} students (${percentage}%) — click to view`;
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        const dept = deptStats[index];
                        if (dept) {
                            onDrillDown(dept.id, dept.name, dept.students);
                        }
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 4. DEPARTMENT PLACEMENT % (Horizontal Bar)
    // ─────────────────────────────────────────────────────────────
    renderPlacementChart(deptStats, onDrillDown) {
        const id = 'uni-placement-chart';
        const canvas = this._canvas(id);
        if (!canvas || !deptStats.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: deptStats.map(d => d.name),
                datasets: [{
                    label: 'Placement Rate',
                    data: deptStats.map(d => d.placement_rate),
                    backgroundColor: (context) => {
                        const value = context.raw;
                        if (value >= 80) return this.palette.green;
                        if (value >= 60) return this.palette.blue;
                        if (value >= 40) return this.palette.amber;
                        if (value >= 20) return this.palette.orange;
                        return this.palette.red;
                    },
                    borderRadius: 8,
                    barPercentage: 0.8,
                    categoryPercentage: 0.9,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.x}% placement rate${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true, max: 100, grid: { color: '#e2e8f0' },
                        ticks: { callback: (v) => v + '%', stepSize: 20 }
                    },
                    y: { grid: { display: false }, ticks: { font: { weight: '600' } } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const dept = deptStats[elements[0].index];
                        if (dept) onDrillDown(dept.id, dept.name, 'placed');
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 5. PROGRAM DISTRIBUTION (Pie)
    // ─────────────────────────────────────────────────────────────
    renderProgramChart(programDist, onDrillDown) {
        const id = 'uni-program-chart';
        const canvas = this._canvas(id);
        if (!canvas || !programDist || !programDist.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        this.instances[id] = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: programDist.map(p => p.name),
                datasets: [{
                    data: programDist.map(p => p.count),
                    backgroundColor: this.multiColors.slice(0, programDist.length),
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 15,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 2000,
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 16,
                            usePointStyle: true,
                            pointStyle: 'circle',
                        },
                        onClick: (e, legendItem, legend) => {
                            const index = legendItem.index;
                            const prog = programDist[index];
                            if (prog && onDrillDown) {
                                onDrillDown(prog.id, prog.name, prog.count);
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = ((ctx.parsed / total) * 100).toFixed(1);
                                return `${ctx.label}: ${ctx.parsed} students (${percentage}%) — click to view`;
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        const prog = programDist[index];
                        if (prog) {
                            onDrillDown(prog.id, prog.name, prog.count);
                        }
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 6. FACULTY STATUS (Doughnut)
    // ─────────────────────────────────────────────────────────────
    renderFacultyStatus(faculty, onDrillDown) {
        const id = 'uni-faculty-status-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const present = faculty.present_today || 0;
        const onLeave = faculty.on_leave || 0;
        const total   = faculty.total || 0;
        const absent  = Math.max(0, total - present - onLeave);
        const statuses = ['present', 'on_leave', 'absent'];

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Present', 'On Leave', 'Absent'],
                datasets: [{
                    data: [present, onLeave, absent],
                    backgroundColor: [this.palette.green, this.palette.amber, this.palette.red],
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 10,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 2000,
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 16,
                            usePointStyle: true,
                            pointStyle: 'circle',
                        },
                        onClick: (e, legendItem, legend) => {
                            if (onDrillDown) onDrillDown(statuses[legendItem.index], legendItem.text);
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${ctx.parsed} faculty${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        onDrillDown(statuses[index], ['Present', 'On Leave', 'Absent'][index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 7. HOSTEL OCCUPANCY (Doughnut)
    // ─────────────────────────────────────────────────────────────
    renderHostelOccupancy(hostel, onDrillDown) {
        const id = 'uni-hostel-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const occupied = hostel.occupied_beds || 0;
        const vacant   = Math.max(0, (hostel.total_beds || hostel.total_rooms || 0) - occupied);
        const sliceKeys = ['occupied', 'vacant'];

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Occupied', 'Vacant'],
                datasets: [{
                    data: [occupied, vacant],
                    backgroundColor: [this.palette.teal, this.palette.navy + '20'],
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 10,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                animation: { animateRotate: true, animateScale: true, duration: 2000 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 16, usePointStyle: true, pointStyle: 'circle' },
                        onClick: (e, legendItem) => {
                            if (onDrillDown) onDrillDown(sliceKeys[legendItem.index], legendItem.text);
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${ctx.parsed} rooms${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        onDrillDown(sliceKeys[elements[0].index], ['Occupied', 'Vacant'][elements[0].index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 8. LIBRARY ACTIVITY (Bar)
    // ─────────────────────────────────────────────────────────────
    renderLibraryChart(library, onDrillDown) {
        const id = 'uni-library-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');
        const barKeys = ['total', 'issued', 'overdue'];

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Total Books', 'Currently Issued', 'Overdue'],
                datasets: [{
                    label: 'Books',
                    data: [
                        library.total_books  || 0,
                        library.books_issued || 0,
                        library.overdue      || 0,
                    ],
                    backgroundColor: [
                        this.palette.blue,
                        this.palette.green,
                        this.palette.red,
                    ],
                    borderRadius: 8,
                    barPercentage: 0.6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.y} books${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#e2e8f0' }, ticks: { stepSize: 1 } },
                    x: { grid: { display: false } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        onDrillDown(barKeys[elements[0].index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // FA-2. DEPARTMENT-WISE AVG CGPA (Bar)
    // ─────────────────────────────────────────────────────────────
    renderFacultyCgpaChart(deptStats, onDrillDown) {
        const id = 'uni-faculty-cgpa-chart';
        const canvas = this._canvas(id);
        if (!canvas || !deptStats || !deptStats.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: deptStats.map(d => d.name),
                datasets: [{
                    label: 'Avg CGPA',
                    data: deptStats.map(d => d.avg_cgpa || 0),
                    backgroundColor: (context) => {
                        const chart = context.chart;
                        const { ctx, chartArea } = chart;
                        if (!chartArea) return this.palette.indigo;
                        return this._gradient(ctx, this.palette.indigo, this.palette.purple);
                    },
                    borderRadius: 8,
                    barPercentage: 0.6,
                    categoryPercentage: 0.8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `Avg CGPA: ${c.parsed.y.toFixed(1)}${onDrillDown ? ' — click to view students' : ''}` } }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 10,
                        grid: { color: '#e2e8f0' },
                        ticks: { stepSize: 2 }
                    },
                    x: { grid: { display: false }, ticks: { font: { weight: '600' } } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        const dept = deptStats[index];
                        if (dept) onDrillDown(dept.id, dept.name, dept.avg_cgpa);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // FA-3. FACULTY DESIGNATION BREAKDOWN (Doughnut)
    // ─────────────────────────────────────────────────────────────
    renderFacultyDesignationChart(faculty, onDrillDown) {
        const id = 'uni-faculty-designation-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const data = (faculty.designation_breakdown || []).filter(d => d.value > 0);
        if (!data.length) return;

        const labels = data.map(d => d.label);
        const values = data.map(d => d.value);

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: this.multiColors.slice(0, labels.length),
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 10,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                animation: { animateRotate: true, animateScale: true, duration: 2000 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 14,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            generateLabels(chart) {
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label} (${chart.data.datasets[0].data[i]})`,
                                    fillStyle: chart.data.datasets[0].backgroundColor[i],
                                    strokeStyle: '#fff',
                                    lineWidth: 2,
                                    hidden: false,
                                    index: i,
                                    pointStyle: 'circle',
                                }));
                            }
                        },
                        onClick: (e, legendItem) => {
                            if (onDrillDown) onDrillDown(data[legendItem.index].id, data[legendItem.index].label);
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (c) => ` ${c.label}: ${c.parsed} faculty${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        onDrillDown(data[index].id, data[index].label);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // HO-2. HOSTEL ROOMS SUMMARY (Bar)
    // ─────────────────────────────────────────────────────────────
    renderHostelRoomsChart(hostel, onDrillDown) {
        const id = 'uni-hostel-rooms-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const total    = hostel.total_rooms    || 0;
        const occupied = hostel.occupied_beds || 0;
        const vacant   = Math.max(0, total - occupied);
        const barKeys  = ['total', 'occupied', 'vacant'];

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Total Rooms', 'Occupied', 'Vacant'],
                datasets: [{
                    label: 'Rooms',
                    data: [total, occupied, vacant],
                    backgroundColor: [this.palette.blue, this.palette.teal, this.palette.amber],
                    borderRadius: 8,
                    barPercentage: 0.55,
                    categoryPercentage: 0.7,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.parsed.y} rooms${onDrillDown ? ' — click to view' : ''}` } }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#e2e8f0' }, ticks: { stepSize: 1 } },
                    x: { grid: { display: false } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        onDrillDown(barKeys[elements[0].index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // HO-3. HOSTEL COMPLAINTS STATUS (Doughnut)
    // ─────────────────────────────────────────────────────────────
    renderHostelComplaintsChart(hostel, onDrillDown) {
        const id = 'uni-hostel-complaints-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const breakdown = (hostel.complaints_breakdown || []).filter(d => d.value > 0);
        if (!breakdown.length) return;

        const labels = breakdown.map(d => d.label);
        const values = breakdown.map(d => d.value);

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: [this.palette.red, this.palette.amber, this.palette.green, this.palette.blue, this.palette.teal],
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 10,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                animation: { animateRotate: true, animateScale: true, duration: 2000 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 14,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            generateLabels(chart) {
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label} (${chart.data.datasets[0].data[i]})`,
                                    fillStyle: chart.data.datasets[0].backgroundColor[i],
                                    strokeStyle: '#fff',
                                    lineWidth: 2,
                                    hidden: false,
                                    index: i,
                                    pointStyle: 'circle',
                                }));
                            }
                        },
                        onClick: (e, legendItem) => {
                            if (onDrillDown) onDrillDown(breakdown[legendItem.index].key, breakdown[legendItem.index].label);
                        }
                    },
                    tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.parsed} complaints${onDrillDown ? ' — click to view' : ''}` } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        onDrillDown(breakdown[index].key, breakdown[index].label);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // LI-2. BOOKS STATUS DOUGHNUT (Available / Issued / Overdue)
    // ─────────────────────────────────────────────────────────────
    renderLibraryStatusChart(library, onDrillDown) {
        const id = 'uni-library-status-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const issued   = library.books_issued || 0;
        const overdue  = library.overdue      || 0;
        const total    = library.total_books  || 0;
        const available = Math.max(0, total - issued - overdue);

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Available', 'Issued', 'Overdue'],
                datasets: [{
                    data: [available, issued, overdue],
                    backgroundColor: [this.palette.green, this.palette.blue, this.palette.red],
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 12,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                animation: { animateRotate: true, animateScale: true, duration: 2000 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 14,
                            usePointStyle: true,
                            pointStyle: 'circle',
                            generateLabels(chart) {
                                const d = chart.data;
                                return d.labels.map((label, i) => ({
                                    text: `${label} (${d.datasets[0].data[i]})`,
                                    fillStyle: d.datasets[0].backgroundColor[i],
                                    strokeStyle: '#fff',
                                    lineWidth: 2,
                                    hidden: false,
                                    index: i,
                                    pointStyle: 'circle',
                                }));
                            }
                        },
                        onClick: (e, legendItem) => {
                            const keys = ['available', 'issued', 'overdue'];
                            if (onDrillDown) onDrillDown(keys[legendItem.index]);
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (c) => {
                                const total = c.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total ? ((c.parsed / total) * 100).toFixed(1) : 0;
                                return ` ${c.label}: ${c.parsed} books (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // PL-2. PLACEMENT SUMMARY DOUGHNUT (Placed vs Not Placed)
    // ─────────────────────────────────────────────────────────────
    renderPlacementSummaryChart(overview, onDrillDown) {
        const id = 'uni-placement-summary-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const placed    = overview.students_placed || 0;
        const total     = overview.total_students  || 0;
        const notPlaced = Math.max(0, total - placed);
        const sliceKeys = ['placed', 'not_placed'];

        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Placed', 'Not Yet Placed'],
                datasets: [{
                    data: [placed, notPlaced],
                    backgroundColor: [this.palette.green, this.palette.navy + '30'],
                    borderWidth: 3,
                    borderColor: '#ffffff',
                    hoverOffset: 12,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%',
                animation: { animateRotate: true, animateScale: true, duration: 2000 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 14, usePointStyle: true, pointStyle: 'circle' },
                        onClick: (e, legendItem) => {
                            if (onDrillDown) onDrillDown(null, null, sliceKeys[legendItem.index]);
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (c) => {
                                const total = c.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total ? ((c.parsed / total) * 100).toFixed(1) : 0;
                                return ` ${c.label}: ${c.parsed} students (${pct}%)${onDrillDown ? ' — click to view' : ''}`;
                            }
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        onDrillDown(null, null, sliceKeys[elements[0].index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // PL-3. PLACED VS TOTAL STUDENTS PER DEPT (Stacked Bar)
    // ─────────────────────────────────────────────────────────────
    renderPlacementStackedChart(deptStats, onDrillDown) {
        const id = 'uni-placement-stacked-chart';
        const canvas = this._canvas(id);
        if (!canvas || !deptStats || !deptStats.length) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const labels    = deptStats.map(d => d.name);
        const placed    = deptStats.map(d => Math.round((d.placement_rate || 0) / 100 * (d.students || 0)));
        const notPlaced = deptStats.map((d, i) => Math.max(0, (d.students || 0) - placed[i]));

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Placed',
                        data: placed,
                        backgroundColor: this.palette.green,
                        borderRadius: { topLeft: 0, topRight: 0, bottomLeft: 6, bottomRight: 6 },
                        stack: 'students',
                    },
                    {
                        label: 'Not Yet Placed',
                        data: notPlaced,
                        backgroundColor: this.palette.navy + '25',
                        borderRadius: { topLeft: 6, topRight: 6, bottomLeft: 0, bottomRight: 0 },
                        stack: 'students',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 14, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.parsed.y} students${onDrillDown ? ' — click to view' : ''}` } }
                },
                scales: {
                    y: { beginAtZero: true, stacked: true, grid: { color: '#e2e8f0' }, ticks: { stepSize: 1 } },
                    x: { stacked: true, grid: { display: false }, ticks: { font: { weight: '600' } } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const el = elements[0];
                        const dept = deptStats[el.index];
                        const sliceKey = el.datasetIndex === 0 ? 'placed' : 'not_placed';
                        if (dept) onDrillDown(dept.id, dept.name, sliceKey);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 9. EXAMINATION STATUS (Bar)
    // ─────────────────────────────────────────────────────────────
    renderExamsChart(exams, onDrillDown) {
        const id = 'uni-exams-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');

        const examKeys = ['active_exams', 'hall_tickets', 'results_published', 'revaluations'];

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Active Exams', 'Hall Tickets', 'Results Published', 'Revaluations'],
                datasets: [{
                    label: 'Count',
                    data: [
                        exams.active_exams      || 0,
                        exams.hall_tickets      || 0,
                        exams.results_published || 0,
                        exams.revaluations      || 0,
                    ],
                    backgroundColor: [
                        this.palette.blue,
                        this.palette.green,
                        this.palette.amber,
                        this.palette.orange,
                    ],
                    borderRadius: 8,
                    barPercentage: 0.55,
                    categoryPercentage: 0.8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.label}: ${ctx.parsed.y}${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#e2e8f0' },
                        ticks: { stepSize: 1 }
                    },
                    x: { grid: { display: false } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        onDrillDown(examKeys[elements[0].index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // 10. TRANSPORT OVERVIEW (Bar)
    // ─────────────────────────────────────────────────────────────
    renderTransportChart(overview, onDrillDown) {
        const id = 'uni-transport-chart';
        const canvas = this._canvas(id);
        if (!canvas) return;

        this._destroy(id);
        const ctx = canvas.getContext('2d');
        const barKeys = ['vehicles', 'routes', 'students'];

        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Total Vehicles', 'Active Routes', 'Students Using Transport'],
                datasets: [{
                    label: 'Count',
                    data: [
                        overview.total_vehicles      || 0,
                        overview.active_routes       || 0,
                        overview.transport_students  || 0,
                    ],
                    backgroundColor: [
                        this.palette.blue,
                        this.palette.green,
                        this.palette.orange,
                    ],
                    borderRadius: 8,
                    barPercentage: 0.55,
                    categoryPercentage: 0.8,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 2000, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.y}${onDrillDown ? ' — click to view' : ''}`
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, grid: { color: '#e2e8f0' }, ticks: { stepSize: 1 } },
                    x: { grid: { display: false } }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        onDrillDown(barKeys[elements[0].index]);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            }
        });
    },

    // ─────────────────────────────────────────────────────────────
    // MASTER RENDER
    // ─────────────────────────────────────────────────────────────

    // ─────────────────────────────────────────────────────────────
    // ASSET: Assets by Category (Doughnut)
    // ─────────────────────────────────────────────────────────────
    renderAssetsByCategory(data, onDrillDown) {
        const id = 'uni-asset-category-chart';
        const canvas = this._canvas(id);
        if (!canvas || !data || !data.length) return;
        this._destroy(id);
        const ctx = canvas.getContext('2d');
        this.instances[id] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    data: data.map(d => d.value),
                    backgroundColor: [
                        this.palette.blue, this.palette.green, this.palette.amber,
                        this.palette.purple, this.palette.teal, this.palette.red,
                        this.palette.orange, this.palette.indigo,
                    ],
                    borderWidth: 2,
                    borderColor: '#fff',
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1500, easing: 'easeInOutQuart' },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 16,
                            usePointStyle: true,
                            generateLabels(chart) {
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label} (${chart.data.datasets[0].data[i]})`,
                                    fillStyle: chart.data.datasets[0].backgroundColor[i],
                                    strokeStyle: '#fff',
                                    lineWidth: 2,
                                    hidden: false,
                                    index: i,
                                    pointStyle: 'circle',
                                }));
                            }
                        },
                        onClick: (e, legendItem) => {
                            if (onDrillDown) onDrillDown(data[legendItem.index].id, data[legendItem.index].label);
                        }
                    },
                    tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.parsed} assets${onDrillDown ? ' — click to view' : ''}` } },
                },
                cutout: '60%',
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        onDrillDown(data[index].id, data[index].label);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            },
        });
    },

    // ─────────────────────────────────────────────────────────────
    // ASSET: Asset State Breakdown (Bar)
    // ─────────────────────────────────────────────────────────────
    renderAssetStateChart(data, onDrillDown) {
        const id = 'uni-asset-state-chart';
        const canvas = this._canvas(id);
        if (!canvas || !data || !data.length) return;
        this._destroy(id);
        const ctx = canvas.getContext('2d');
        const colors = {
            active: this.palette.green, draft: this.palette.blue,
            under_maintenance: this.palette.amber, transferred: this.palette.teal,
            audited: this.palette.indigo,
        };
        this.instances[id] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.label),
                datasets: [{
                    label: 'Assets',
                    data: data.map(d => d.value),
                    backgroundColor: data.map(d => colors[d.key] || this.palette.blue),
                    borderRadius: 8,
                    barPercentage: 0.6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 1500, easing: 'easeInOutQuart' },
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: { label: (c) => `${c.parsed.y} assets${onDrillDown ? ' — click to view' : ''}` } }
                },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 },
                         grid: { color: 'rgba(0,0,0,0.05)' } },
                    x: { grid: { display: false } },
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onDrillDown) {
                        const index = elements[0].index;
                        onDrillDown(data[index].key, data[index].label);
                    }
                },
                onHover: (event, elements) => {
                    event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                },
            },
        });
    },

    renderAll(state, onDeptDrillDown, onProgramDrillDown, onFeeDrillDown, onSemDrillDown, onFacultyStatusDD, onCgpaDD, onDesignationDD, onExamDD, onAssetCatDD, onAssetStateDD, onHostelOccDD, onHostelRoomsDD, onComplaintDD, onLibActivityDD, onLibStatusDD, onPlacementDeptDD, onPlacementSumDD, onPlacementStackDD, onTransportDD) {
        if (!this._initDefaults()) return;

        // Fee trend
        if (state.feeCollectionMonthly && state.feeCollectionMonthly.length) {
            this.renderFeeTrend(state.feeCollectionMonthly, onFeeDrillDown);
        }

        // Semester admissions
        if (state.semesterAdmissions && state.semesterAdmissions.length) {
            this.renderSemesterAdmissions(state.semesterAdmissions, onSemDrillDown);
        }

        // Department charts (overview)
        if (state.departmentStats && state.departmentStats.length) {
            this.renderDepartmentDistribution(state.departmentStats, onDeptDrillDown);
        }

        // Program pie
        if (state.students && state.students.program_distribution) {
            this.renderProgramChart(state.students.program_distribution, onProgramDrillDown);
        }

        // Faculty doughnut
        if (state.faculty && state.faculty.total) {
            this.renderFacultyStatus(state.faculty, onFacultyStatusDD);
            this.renderFacultyDesignationChart(state.faculty, onDesignationDD);
        }
        if (state.departmentStats && state.departmentStats.length) {
            this.renderFacultyCgpaChart(state.departmentStats, onCgpaDD);
        }

        // Hostel doughnut
        if (state.hostel && state.hostel.total_rooms) {
            this.renderHostelOccupancy(state.hostel, onHostelOccDD);
            this.renderHostelRoomsChart(state.hostel, onHostelRoomsDD);
            this.renderHostelComplaintsChart(state.hostel, onComplaintDD);
        }

        // Library bar
        if (state.library) {
            this.renderLibraryChart(state.library, onLibActivityDD);
            this.renderLibraryStatusChart(state.library, onLibStatusDD);
        }

        // Placement charts
        if (state.departmentStats && state.departmentStats.length) {
            this.renderPlacementChart(state.departmentStats, onPlacementDeptDD);
            this.renderPlacementStackedChart(state.departmentStats, onPlacementStackDD);
        }
        if (state.overview) {
            this.renderPlacementSummaryChart(state.overview, onPlacementSumDD);
        }

        // Exams bar
        if (state.exams) {
            this.renderExamsChart(state.exams, onExamDD);
        }

        // Transport bar
        if (state.overview) {
            this.renderTransportChart(state.overview, onTransportDD);
        }

        // Asset charts
        if (state.assets?.charts) {
            this.renderAssetsByCategory(state.assets.charts.by_category || [], onAssetCatDD);
            this.renderAssetStateChart(state.assets.charts.by_state || [], onAssetStateDD);
        }
    },

    // ─────────────────────────────────────────────────────────────
    // Re-render only charts visible in the active module
    // ─────────────────────────────────────────────────────────────
    renderForModule(module, state, onDeptDrillDown, onProgramDrillDown, onFeeDrillDown, onSemDrillDown, onFacultyStatusDD, onCgpaDD, onDesignationDD, onExamDD, onAssetCatDD, onAssetStateDD, onHostelOccDD, onHostelRoomsDD, onComplaintDD, onLibActivityDD, onLibStatusDD, onPlacementDeptDD, onPlacementSumDD, onPlacementStackDD, onTransportDD) {
        if (!this._initDefaults()) return;

        setTimeout(() => {
            switch (module) {
                case 'overview':
                    if (state.feeCollectionMonthly?.length)
                        this.renderFeeTrend(state.feeCollectionMonthly, onFeeDrillDown);
                    if (state.departmentStats?.length)
                        this.renderDepartmentDistribution(state.departmentStats, onDeptDrillDown);
                    break;

                case 'students':
                    if (state.semesterAdmissions?.length)
                        this.renderSemesterAdmissions(state.semesterAdmissions, onSemDrillDown);
                    if (state.students?.program_distribution)
                        this.renderProgramChart(state.students.program_distribution, onProgramDrillDown);
                    break;

                case 'faculty':
                    if (state.faculty?.total) {
                        this.renderFacultyStatus(state.faculty, onFacultyStatusDD);
                        this.renderFacultyDesignationChart(state.faculty, onDesignationDD);
                    }
                    if (state.departmentStats?.length)
                        this.renderFacultyCgpaChart(state.departmentStats, onCgpaDD);
                    break;

                case 'fees':
                    if (state.feeCollectionMonthly?.length)
                        this.renderFeeTrend(state.feeCollectionMonthly, onFeeDrillDown);
                    break;

                case 'exams':
                    if (state.exams)
                        this.renderExamsChart(state.exams, onExamDD);
                    break;

                case 'hostel':
                    if (state.hostel?.total_rooms) {
                        this.renderHostelOccupancy(state.hostel, onHostelOccDD);
                        this.renderHostelRoomsChart(state.hostel, onHostelRoomsDD);
                        this.renderHostelComplaintsChart(state.hostel, onComplaintDD);
                    }
                    break;

                case 'library':
                    if (state.library) {
                        this.renderLibraryChart(state.library, onLibActivityDD);
                        this.renderLibraryStatusChart(state.library, onLibStatusDD);
                    }
                    break;

                case 'placement':
                    if (state.departmentStats?.length) {
                        this.renderPlacementChart(state.departmentStats, onPlacementDeptDD);
                        this.renderPlacementStackedChart(state.departmentStats, onPlacementStackDD);
                    }
                    if (state.overview)
                        this.renderPlacementSummaryChart(state.overview, onPlacementSumDD);
                    break;

                case 'transport':
                    if (state.overview)
                        this.renderTransportChart(state.overview, onTransportDD);
                    break;

                case 'assets':
                    if (state.assets?.charts) {
                        this.renderAssetsByCategory(state.assets.charts.by_category || [], onAssetCatDD);
                        this.renderAssetStateChart(state.assets.charts.by_state || [], onAssetStateDD);
                    }
                    break;
            }
        }, 100);
    },

    destroyAll() {
        Object.keys(this.instances).forEach(id => this._destroy(id));
    },

    exportChart(chartId, filename) {
        const chart = this.instances[chartId];
        if (chart) {
            const a = document.createElement('a');
            a.href = chart.toBase64Image();
            a.download = filename || chartId + '.png';
            a.click();
        }
    },
};

export { UniversityCharts };