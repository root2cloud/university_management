# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date
import logging

_logger = logging.getLogger(__name__)


class UniversityDashboard(models.TransientModel):
    _name = 'university.dashboard'
    _description = 'University Dashboard Data Provider'

    @api.model
    def get_dashboard_data(self):
        asset_summary = self._get_asset_summary()
        return {
            'overview': self._get_overview_data(),
            'students': self._get_students_data(),
            'faculty': self._get_faculty_data(),
            'fees': self._get_fees_data(),
            'exams': self._get_exams_data(),
            'hostel': self._get_hostel_data(),
            'library': self._get_library_data(),
            'recent_admissions': self._get_recent_admissions(),
            'recent_payments': self._get_recent_payments(),
            'department_stats': self._get_department_stats(),
            'fee_monthly': self._get_fee_monthly_trend(),
            'semester_admissions': self._get_semester_admissions(),
            'assets': asset_summary['kpi'],
            'asset_purchase_requests': asset_summary['purchase_requests'],
            'asset_handovers': asset_summary['handovers'],
        }

    def _student_active_domain(self):
        """Central place for student live/active states."""
        return [('state', 'in', ['active', 'enrolled', 'admitted'])]

    @api.model
    def get_batches(self):
        """Return all batches for the batch filter dropdown."""
        batches = self.env['university.batch'].search([], order='start_year desc')
        return [{'id': b.id, 'name': b.name} for b in batches]

    @api.model
    def get_department_stats_by_batch(self, batch_id=None):
        """Return department student distribution filtered by batch."""
        result = []
        try:
            base_domain = self._student_active_domain()
            if batch_id:
                base_domain = [('batch_id', '=', batch_id)] + base_domain

            departments = self.env['university.department'].search([])
            for dept in departments:
                domain = [('department_id', '=', dept.id)] + base_domain
                students = self.env['student.student'].search_count(domain)
                if not students:
                    continue
                result.append({
                    'id': dept.id,
                    'name': dept.name,
                    'students': students,
                })
        except Exception as e:
            _logger.warning("Department stats by batch error: %s", e)
        return result

    @api.model
    def get_departments(self):
        """Return all departments for filter dropdowns."""
        depts = self.env['university.department'].search([])
        return [{'id': d.id, 'name': d.name} for d in depts]

    @api.model
    def get_fee_trend_filtered(self, batch_id=None, department_id=None):
        """Return monthly fee collection trend filtered by batch and/or department."""
        from calendar import monthrange
        today = date.today()
        result = []
        monthly_vals = []
        try:
            for i in range(7, -1, -1):
                year = today.year
                month = today.month - i
                while month <= 0:
                    month += 12
                    year -= 1
                _, last_day = monthrange(year, month)
                start = date(year, month, 1).strftime('%Y-%m-%d')
                end = date(year, month, last_day).strftime('%Y-%m-%d')
                domain = [
                    ('state', 'in', ['paid', 'partial']),
                    ('payment_date', '>=', start),
                    ('payment_date', '<=', end),
                ]
                if batch_id:
                    domain.append(('student_id.batch_id', '=', batch_id))
                if department_id:
                    domain.append(('department_id', '=', department_id))
                payments = self.env['fee.payment'].search(domain)
                total = sum(payments.mapped('total_amount'))
                label = date(year, month, 1).strftime('%b')
                monthly_vals.append({'label': label, 'value': total, 'date_start': start, 'date_end': end})
        except Exception as e:
            _logger.warning("Fee trend filtered error: %s", e)

        max_val = max((mv['value'] for mv in monthly_vals), default=1) or 1
        for mv in monthly_vals:
            result.append({
                'label': mv['label'],
                'value': mv['value'],
                'height': round(mv['value'] / max_val * 100),
                'date_start': mv['date_start'],
                'date_end': mv['date_end'],
            })
        return result

    def _get_overview_data(self):
        env = self.env
        today = date.today()

        total_students = 0
        try:
            total_students = env['student.student'].search_count(self._student_active_domain())
        except Exception:
            pass

        total_faculty = 0
        try:
            total_faculty = env['faculty.faculty'].search_count([('active', '=', True)])
        except Exception:
            pass

        avg_cgpa = 0.0
        try:
            results = env['examination.result'].search([('state', '=', 'published')])
            if results:
                cgpa_vals = [r.grade_point for r in results if r.grade_point]
                avg_cgpa = sum(cgpa_vals) / len(cgpa_vals) if cgpa_vals else 0.0
        except Exception:
            pass

        month_start = today.replace(day=1)
        new_admissions_this_month = 0
        try:
            new_admissions_this_month = env['student.admission'].search_count([
                ('state', '=', 'approved'),
                ('application_date', '>=', month_start.strftime('%Y-%m-%d')),
            ])
        except Exception:
            pass

        students_placed = 0
        total_eligible = 0
        active_placement_drives = 0
        recruiting_companies = 0
        highest_package = 'N/A'
        try:
            students_placed = env['placement.offer'].search_count([('state', '=', 'accepted')])
            total_eligible = env['student.student'].search_count(
                self._student_active_domain()
            )
            active_placement_drives = env['placement.drive'].search_count([
                ('state', 'in', ['registration_open', 'registration_closed', 'scheduled', 'ongoing'])
            ])
            recruiting_companies = env['placement.company'].search_count([('active', '=', True)])

            # Compute highest package from accepted placement offers
            accepted_offers = env['placement.offer'].search(
                [('state', '=', 'accepted'), ('ctc', '>', 0)],
                order='ctc desc',
                limit=1,
            )
            if accepted_offers:
                top_offer = accepted_offers[0]
                ctc_value = top_offer.ctc
                currency = top_offer.currency_id
                symbol = currency.symbol if currency else ''
                # Format as LPA if currency is INR, otherwise use 2-decimal format
                if currency and currency.name == 'INR':
                    lpa = ctc_value / 100000  # convert to Lakhs Per Annum
                    highest_package = '{}{:.2f} LPA'.format(symbol, lpa)
                else:
                    highest_package = '{}{:,.0f}'.format(symbol, ctc_value)
        except Exception:
            pass

        placement_rate = round((students_placed / total_eligible * 100) if total_eligible else 0, 1)

        total_vehicles = 0
        active_routes = 0
        transport_students = 0
        try:
            total_vehicles = env['transport.vehicle'].search_count([('active', '=', True)])
            active_routes = env['transport.route'].search_count([('active', '=', True)])
            transport_students = env['transport.allocation'].search_count([('state', '=', 'active')])
        except Exception:
            pass

        return {
            'total_students': total_students,
            'total_faculty': total_faculty,
            'avg_cgpa': round(avg_cgpa, 2),
            'new_admissions_this_month': new_admissions_this_month,
            'placement_rate': placement_rate,
            'students_placed': students_placed,
            'active_placement_drives': active_placement_drives,
            'recruiting_companies': recruiting_companies,
            'highest_package': highest_package,
            'total_vehicles': total_vehicles,
            'active_routes': active_routes,
            'transport_students': transport_students,
        }

    def _get_asset_summary(self):
        """Return asset KPIs and recent records for the main university dashboard."""
        env = self.env
        kpi = {
            'total_assets': 0, 'available': 0, 'maintenance_due': 0,
            'pending_requests': 0, 'low_stock_alerts': 0, 'pending_handovers': 0,
        }
        purchase_requests = []
        handovers = []

        state_label_map = {
            'draft': 'Draft', 'principal_review': 'Awaiting Principal',
            'vendor_quotes': 'Awaiting Quotes', 'acc_review': 'ACC Review',
            'secretary_review': 'Awaiting Secretary', 'trust_execution': 'Executing',
            'done': 'Done', 'rejected': 'Rejected',
        }
        handover_label_map = {
            'draft': 'Draft', 'pending_hod': 'Pending HOD',
            'pending_principal': 'Pending Principal', 'approved': 'Approved',
            'completed': 'Completed', 'rejected': 'Rejected',
        }

        try:
            from datetime import date as _date
            today_str = _date.today().strftime('%Y-%m-%d')

            # asset.asset: state values = draft/active/under_maintenance/transferred/disposed/condemned/lost/audited
            # asset.asset: status values = available/not_available/needs_purchase/in_audit
            kpi['total_assets'] = env['asset.asset'].search_count(
                [('state', 'not in', ['disposed', 'condemned', 'lost'])])
            kpi['available'] = env['asset.asset'].search_count(
                [('state', 'not in', ['disposed', 'condemned', 'lost']),
                 ('status', '=', 'available')])
            kpi['maintenance_due'] = env['asset.asset'].search_count(
                [('next_service_date', '!=', False),
                 ('next_service_date', '<=', today_str),
                 ('state', 'in', ['active', 'audited'])])
            # low_stock is a computed Boolean on asset.asset
            kpi['low_stock_alerts'] = env['asset.asset'].search_count(
                [('low_stock', '=', True),
                 ('state', 'not in', ['disposed', 'condemned', 'lost'])])
            kpi['pending_requests'] = env['asset.purchase.request'].search_count(
                [('state', 'not in', ['done', 'rejected', 'draft'])])
            kpi['pending_handovers'] = env['asset.handover'].search_count(
                [('state', 'in', ['pending_hod', 'pending_principal'])])

            # Recent purchase requests (exclude pure drafts to show meaningful data)
            prs = env['asset.purchase.request'].search(
                [], order='request_date desc', limit=6)
            for pr in prs:
                purchase_requests.append({
                    'id': pr.id,
                    'name': pr.name or '/',
                    'requested_by': pr.requested_by.name if pr.requested_by else '',
                    'item_description': (pr.item_description or '')[:60],
                    'state': pr.state,
                    'state_label': state_label_map.get(pr.state, pr.state),
                })

            # Recent handover requests
            hvs = env['asset.handover'].search(
                [], order='request_date desc', limit=6)
            for hv in hvs:
                handovers.append({
                    'id': hv.id,
                    'name': hv.name or '/',
                    'asset_name': hv.asset_id.name if hv.asset_id else '',
                    'to_department': hv.to_department_id.name if hv.to_department_id else '',
                    'state': hv.state,
                    'state_label': handover_label_map.get(hv.state, hv.state),
                })

            # Chart data: assets by category
            by_category = []
            categories = env['asset.category'].search([])
            for cat in categories:
                count = env['asset.asset'].search_count([
                    ('category_id', '=', cat.id),
                    ('state', 'not in', ['disposed', 'condemned', 'lost']),
                ])
                if count:
                    by_category.append({'id': cat.id, 'label': cat.name, 'value': count})

            # Chart data: assets by state
            state_labels = {
                'draft': 'Draft', 'active': 'Active',
                'under_maintenance': 'Maintenance', 'transferred': 'Transferred',
                'audited': 'Audited',
            }
            by_state = []
            for s_key, s_label in state_labels.items():
                count = env['asset.asset'].search_count([('state', '=', s_key)])
                if count:
                    by_state.append({'key': s_key, 'label': s_label, 'value': count})

            kpi['charts'] = {'by_category': by_category, 'by_state': by_state}

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning('Asset summary in university dashboard failed: %s', e)

        return {'kpi': kpi, 'purchase_requests': purchase_requests, 'handovers': handovers}

    def _get_students_data(self):
        env = self.env
        today = date.today()
        year_start = today.replace(month=1, day=1)

        total_active = 0
        new_this_year = 0
        pending_admissions = 0
        try:
            total_active = env['student.student'].search_count([('state', '=', 'enrolled')])
            new_this_year = env['student.admission'].search_count([
                ('state', 'in', ['approved', 'admitted']),
                ('application_date', '>=', year_start.strftime('%Y-%m-%d')),
            ])
            pending_admissions = env['student.admission'].search_count([
                ('state', 'in', ['submitted', 'under_review'])
            ])
        except Exception:
            pass

        low_attendance = 0
        try:
            students = env['student.student'].search(self._student_active_domain())
            for student in students:
                att_records = env['student.attendance'].search([
                    ('student_id', '=', student.id),
                    ('date', '>=', year_start.strftime('%Y-%m-%d')),
                ])
                if att_records:
                    present = len(att_records.filtered(lambda r: r.state == 'present'))
                    pct = present / len(att_records) * 100
                    if pct < 75:
                        low_attendance += 1
        except Exception:
            pass

        program_distribution = []
        try:
            programs = env['university.program'].search([])
            all_active_count = env['student.student'].search_count(self._student_active_domain())
            total = max(all_active_count, 1)
            for prog in programs:
                count = env['student.student'].search_count(
                    [('program_id', '=', prog.id)] + self._student_active_domain()
                )
                if count:
                    program_distribution.append({
                        'id': prog.id,
                        'name': prog.name,
                        'count': count,
                        'percentage': round(count / total * 100, 1),
                    })
        except Exception:
            pass

        return {
            'total_active': total_active,
            'new_this_year': new_this_year,
            'pending_admissions': pending_admissions,
            'low_attendance': low_attendance,
            'program_distribution': program_distribution,
        }

    def _get_faculty_data(self):
        env = self.env
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')

        total = 0
        present_today = 0
        on_leave = 0
        avg_rating = 0.0

        try:
            total = env['faculty.faculty'].search_count([('active', '=', True)])
        except Exception:
            pass

        try:
            present_today = env['faculty.attendance'].search_count([
                ('date', '=', today_str),
                ('state', '=', 'present'),
            ])
        except Exception:
            pass

        try:
            on_leave = env['faculty.leave'].search_count([
                ('date_from', '<=', today_str),
                ('date_to', '>=', today_str),
                ('state', '=', 'approved'),
            ])
        except Exception:
            pass

        try:
            evals = env['faculty.evaluation'].search([('state', '=', 'approved')])
            if evals:
                avg_rating = sum(e.overall_rating for e in evals if e.overall_rating) / len(evals)
        except Exception:
            pass

        # Designation breakdown
        designation_breakdown = []
        try:
            all_faculty = env['faculty.faculty'].search([('active', '=', True)])
            desig_map = {}  # {(id, name): count}
            for f in all_faculty:
                if f.designation_id:
                    key = (f.designation_id.id, f.designation_id.name)
                else:
                    key = (False, 'Other')
                desig_map[key] = desig_map.get(key, 0) + 1
            designation_breakdown = [
                {'id': k[0], 'label': k[1], 'value': v}
                for k, v in sorted(desig_map.items(), key=lambda x: -x[1])
            ]
        except Exception:
            pass

        # Department-wise faculty count
        dept_distribution = []
        try:
            departments = env['university.department'].search([])
            for dept in departments:
                count = env['faculty.faculty'].search_count([
                    ('department_id', '=', dept.id),
                    ('active', '=', True),
                ])
                if count:
                    dept_distribution.append({'label': dept.name, 'value': count})
        except Exception:
            pass

        return {
            'total': total,
            'present_today': present_today,
            'on_leave': on_leave,
            'avg_rating': round(avg_rating, 1),
            'designation_breakdown': designation_breakdown,
            'dept_distribution': dept_distribution,
        }

    def _get_fees_data(self):
        env = self.env
        today = date.today()
        month_start = today.replace(day=1)

        # ── Core collection figures ────────────────────────────────────
        total_collected = 0.0
        monthly_collection = 0.0
        today_collection = 0.0
        total_pending = 0.0
        late_payments = 0
        transaction_count_month = 0

        # ── Accounting figures ─────────────────────────────────────────
        invoices_count = 0
        journal_entries = 0
        posted_payments = 0
        pending_verification = 0
        scholarships_applied = 0

        # ── New: extended analytics ────────────────────────────────────
        by_program = []
        payment_mode_breakdown = []
        reconciliation_stats = {
            'fully_reconciled': 0,
            'partially_reconciled': 0,
            'not_reconciled': 0,
        }
        student_ledger_stats = {
            'total_students_with_dues': 0,
            'total_outstanding_fmt': '0',
            'avg_outstanding_fmt': '0',
        }

        try:
            # Total ever collected
            all_payments = env['fee.payment'].search([('state', 'in', ['paid', 'partial'])])
            total_collected = sum(all_payments.mapped('total_amount'))

            # This month's collection
            monthly_payments = env['fee.payment'].search([
                ('state', 'in', ['paid', 'partial']),
                ('payment_date', '>=', month_start.strftime('%Y-%m-%d')),
            ])
            monthly_collection = sum(monthly_payments.mapped('total_amount'))
            transaction_count_month = len(monthly_payments)

            # Today's collection  (PDF Finance Dashboard – "Today's Fee Collection")
            today_payments = env['fee.payment'].search([
                ('state', 'in', ['paid', 'partial']),
                ('payment_date', '=', today.strftime('%Y-%m-%d')),
            ])
            today_collection = sum(today_payments.mapped('total_amount'))

            # Outstanding / pending  (PDF Student Ledger – "Outstanding Balance")
            pending_payments = env['fee.payment'].search([
                ('state', 'in', ['draft', 'pending', 'verified', 'invoiced'])
            ])
            total_pending = sum(pending_payments.mapped('total_amount'))

            # Late payments
            fp_fields = env['fee.payment'].fields_get(allfields=['is_late_payment'])
            if 'is_late_payment' in fp_fields:
                late_payments = env['fee.payment'].search_count([
                    ('is_late_payment', '=', True),
                    ('state', 'not in', ['cancelled']),
                ])

            # Accounting counters
            invoices_count = env['fee.payment'].search_count([('invoice_id', '!=', False)])
            journal_entries = env['fee.payment'].search_count([('account_move_id', '!=', False)])
            posted_payments = env['fee.payment'].search_count([('state', 'in', ['paid', 'partial'])])
            pending_verification = env['fee.payment'].search_count([('state', '=', 'pending')])

            # ── Payment Mode Breakdown  (PDF section 12 – "Payment Mode Analysis")
            # Uses the existing computed field `payment_method` on fee.payment
            all_settled = env['fee.payment'].search([('state', 'in', ['paid', 'partial'])])
            mode_totals = {}
            for pmt in all_settled:
                mode_label = pmt.payment_method or 'Unspecified'
                if mode_label not in mode_totals:
                    mode_totals[mode_label] = {'count': 0, 'amount': 0.0}
                mode_totals[mode_label]['count'] += 1
                mode_totals[mode_label]['amount'] += pmt.total_amount

            for label, vals in sorted(mode_totals.items(), key=lambda x: -x[1]['amount']):
                payment_mode_breakdown.append({
                    'label': label,
                    'count': vals['count'],
                    'amount': vals['amount'],
                    'amount_fmt': self._format_amount(vals['amount']),
                })

            # ── Bank Reconciliation Stats  (PDF section 8 – "Bank Reconciliation")
            # Uses the existing `reconciliation_status` computed field
            reconciliation_stats['fully_reconciled'] = env['fee.payment'].search_count([
                ('state', 'in', ['paid', 'partial']),
                ('reconciliation_status', '=', 'fully_reconciled'),
            ])
            reconciliation_stats['partially_reconciled'] = env['fee.payment'].search_count([
                ('state', 'in', ['paid', 'partial']),
                ('reconciliation_status', '=', 'partially_reconciled'),
            ])
            reconciliation_stats['not_reconciled'] = env['fee.payment'].search_count([
                ('state', 'in', ['paid', 'partial']),
                ('reconciliation_status', '=', 'not_reconciled'),
            ])

            # ── Student Ledger Stats  (PDF section 4 – "Student Ledger System")
            # Uses existing `outstanding_amount` and `amount_paid` computed fields
            pending_recs = env['fee.payment'].search([
                ('state', 'in', ['draft', 'pending', 'verified', 'invoiced'])
            ])
            student_ids_with_dues = list(set(pending_recs.mapped('student_id').ids))
            total_outstanding = sum(pending_recs.mapped('outstanding_amount'))
            avg_outstanding = (
                total_outstanding / len(student_ids_with_dues)
                if student_ids_with_dues else 0.0
            )
            student_ledger_stats = {
                'total_students_with_dues': len(student_ids_with_dues),
                'total_outstanding_fmt': self._format_amount(total_outstanding),
                'avg_outstanding_fmt': self._format_amount(avg_outstanding),
            }

        except Exception as e:
            _logger.warning("Fee data fetch error: %s", e)

        try:
            scholarships_applied = env['scholarship.application'].search_count([('state', '=', 'approved')])
        except Exception:
            pass

        # ── Fee Collection by Program ──────────────────────────────────
        try:
            programs = env['university.program'].search([])
            for prog in programs:
                prog_students = env['student.student'].search(
                    [('program_id', '=', prog.id)] + self._student_active_domain()
                )
                if not prog_students:
                    continue

                student_ids = prog_students.ids

                payments = env['fee.payment'].search([
                    ('student_id', 'in', student_ids),
                    ('state', 'in', ['paid', 'partial']),
                ])
                collected = sum(payments.mapped('total_amount'))

                pending = env['fee.payment'].search([
                    ('student_id', 'in', student_ids),
                    ('state', 'in', ['draft', 'pending', 'verified', 'invoiced']),
                ])
                pending_amt = sum(pending.mapped('total_amount'))

                total = collected + pending_amt
                pct = round(collected / total * 100, 1) if total else 0

                by_program.append({
                    'name': prog.name,
                    'students': len(prog_students),
                    'collected': collected,
                    'collected_fmt': self._format_amount(collected),
                    'pending': pending_amt,
                    'pending_fmt': self._format_amount(pending_amt),
                    'collection_pct': pct,
                })
        except Exception as e:
            _logger.warning("Fee by_program fetch error: %s", e)

        return {
            # Existing fields – untouched
            'total_collected': total_collected,
            'monthly_collection': monthly_collection,
            'total_pending': total_pending,
            'late_payments': late_payments,
            'invoices_count': invoices_count,
            'journal_entries': journal_entries,
            'posted_payments': posted_payments,
            'pending_verification': pending_verification,
            'scholarships_applied': scholarships_applied,
            'by_program': by_program,
            # New fields from PDF
            'today_collection': today_collection,
            'transaction_count_month': transaction_count_month,
            'payment_mode_breakdown': payment_mode_breakdown,
            'reconciliation_stats': reconciliation_stats,
            'student_ledger_stats': student_ledger_stats,
        }

    def _get_exams_data(self):
        env = self.env
        active_exams = 0
        hall_tickets = 0
        results_published = 0
        revaluations = 0

        try:
            active_exams = env['examination.examination'].search_count([])
        except Exception:
            pass
        try:
            hall_tickets = env['examination.hall.ticket'].search_count([
                ('state', 'in', ['generated', 'issued', 'printed'])
            ])
        except Exception:
            pass
        try:
            results_published = env['examination.result'].search_count([('state', '=', 'published')])
        except Exception:
            pass
        try:
            revaluations = env['examination.revaluation'].search_count([
                ('state', 'in', ['submitted', 'under_review', 'revaluation_in_progress', 'completed'])
            ])
        except Exception:
            pass

        return {
            'active_exams': active_exams,
            'hall_tickets': hall_tickets,
            'results_published': results_published,
            'revaluations': revaluations,
        }

    def _get_hostel_data(self):
        env = self.env
        total_rooms = 0
        total_beds = 0
        occupied_beds = 0
        pending_complaints = 0

        try:
            active_rooms = env['hostel.room'].search([('active', '=', True)])
            total_rooms = len(active_rooms)
            # Sum actual bed capacity and occupied beds across all active rooms
            total_beds = sum(active_rooms.mapped('capacity'))
            occupied_beds = sum(active_rooms.mapped('occupied_beds'))
        except Exception:
            pass
        try:
            pending_complaints = env['hostel.complaint'].search_count([
                ('state', 'in', ['open', 'in_progress'])
            ])
        except Exception:
            pass

        # Complaints by status
        complaints_breakdown = []
        try:
            all_complaints = env['hostel.complaint'].search([])
            state_map = {}  # {(key, label): count}
            for c in all_complaints:
                key = c.state or 'unknown'
                label = key.replace('_', ' ').title()
                state_map[(key, label)] = state_map.get((key, label), 0) + 1
            complaints_breakdown = [
                {'key': k[0], 'label': k[1], 'value': v}
                for k, v in sorted(state_map.items(), key=lambda x: -x[1])
            ]
        except Exception:
            pass

        # Occupancy rate = occupied beds / total bed capacity (capped at 100%)
        occupancy_rate = round(min(occupied_beds / total_beds * 100, 100.0), 1) if total_beds else 0

        return {
            'total_rooms': total_rooms,
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'pending_complaints': pending_complaints,
            'occupancy_rate': occupancy_rate,
            'complaints_breakdown': complaints_breakdown,
        }

    def _get_library_data(self):
        env = self.env
        total_books = 0
        books_issued = 0
        overdue = 0
        fines_collected = 0.0

        try:
            total_books = env['library.book'].search_count([])
        except Exception:
            pass
        try:
            books_issued = env['library.issue'].search_count([('state', '=', 'issued')])
        except Exception:
            pass
        try:
            overdue = env['library.issue'].search_count([('state', '=', 'overdue')])
        except Exception:
            pass
        try:
            fines = env['library.fine'].search([('state', '=', 'paid')])
            fines_collected = sum(fines.mapped('amount'))
        except Exception:
            pass

        return {
            'total_books': total_books,
            'books_issued': books_issued,
            'overdue': overdue,
            'fines_collected': fines_collected,
        }

    def _get_recent_admissions(self):
        result = []
        try:
            # Try fetching from student.student first (photos are stored there)
            students = self.env['student.student'].search(
                [],
                order='create_date desc',
                limit=8,
            )
            for stu in students:
                photo_b64 = False
                try:
                    if stu.student_photo:
                        photo_b64 = stu.student_photo.decode('utf-8') if isinstance(stu.student_photo, bytes) else stu.student_photo
                except Exception:
                    photo_b64 = False
                result.append({
                    'id': stu.id,
                    'model': 'student.student',
                    'name': stu.name or 'Unknown',
                    'program': stu.program_id.name if stu.program_id else '',
                    'date': stu.create_date.strftime('%d %b %Y') if stu.create_date else '',
                    'state': stu.state or 'active',
                    'state_label': (stu.state or 'active').replace('_', ' ').title(),
                    'photo': photo_b64,
                })
        except Exception as e:
            _logger.warning("Recent admissions fetch error: %s", e)

        # Fallback to student.admission if no student records found
        if not result:
            try:
                admissions = self.env['student.admission'].search(
                    [('state', 'not in', ['cancelled'])],
                    order='application_date desc',
                    limit=8,
                )
                state_selection = dict(
                    admissions.fields_get(['state'])['state']['selection']
                ) if admissions else {}

                for adm in admissions:
                    photo_b64 = False
                    try:
                        if adm.applicant_photo:
                            photo_b64 = adm.applicant_photo.decode('utf-8') if isinstance(adm.applicant_photo, bytes) else adm.applicant_photo
                        elif adm.student_id and adm.student_id.student_photo:
                            photo_b64 = adm.student_id.student_photo.decode('utf-8') if isinstance(adm.student_id.student_photo, bytes) else adm.student_id.student_photo
                    except Exception:
                        photo_b64 = False
                    result.append({
                        'id': adm.id,
                        'model': 'student.admission',
                        'name': adm.applicant_name or 'Unknown',
                        'program': adm.program_id.name if adm.program_id else '',
                        'date': adm.application_date.strftime('%d %b %Y') if adm.application_date else '',
                        'state': adm.state,
                        'state_label': state_selection.get(adm.state, adm.state),
                        'photo': photo_b64,
                    })
            except Exception as e:
                _logger.warning("Recent admissions fallback fetch error: %s", e)

        return result

    def _get_recent_payments(self):
        result = []
        try:
            payments = self.env['fee.payment'].search(
                [('state', 'not in', ['cancelled'])],
                order='payment_date desc',
                limit=8,
            )

            for pmt in payments:
                photo_b64 = False
                try:
                    if pmt.student_id and pmt.student_id.student_photo:
                        photo_b64 = pmt.student_id.student_photo.decode('utf-8') if isinstance(pmt.student_id.student_photo, bytes) else pmt.student_id.student_photo
                except Exception:
                    photo_b64 = False
                result.append({
                    'id': pmt.id,
                    'student': pmt.student_id.name if pmt.student_id else 'Unknown',
                    'amount': self._format_amount(pmt.total_amount),
                    'method': pmt.payment_method or '',
                    'state': pmt.state,
                    'photo': photo_b64,
                })
        except Exception as e:
            _logger.warning("Recent payments fetch error: %s", e)

        return result

    def _get_department_stats(self):
        result = []
        try:
            departments = self.env['university.department'].search([])
            for dept in departments:
                students = self.env['student.student'].search_count(
                    [('department_id', '=', dept.id)] + self._student_active_domain()
                )
                if not students:
                    continue

                btech = self.env['student.student'].search_count(
                    [
                        ('department_id', '=', dept.id),
                        '|',
                        ('program_id.name', 'ilike', 'B.Tech'),
                        ('program_id.name', 'ilike', 'Bachelor of Technology'),
                    ] + self._student_active_domain()
                )

                placed = 0
                try:
                    dept_student_ids = self.env['student.student'].search([
                        ('department_id', '=', dept.id),
                    ]).ids
                    placed = self.env['placement.offer'].search_count([
                        ('student_id', 'in', dept_student_ids),
                        ('state', '=', 'accepted'),
                    ])
                except Exception:
                    pass

                placement_rate = round(placed / students * 100, 1) if students else 0

                avg_cgpa = 0.0
                try:
                    results = self.env['examination.result'].search([
                        ('student_id.department_id', '=', dept.id),
                        ('state', '=', 'published'),
                    ])
                    if results:
                        vals = [r.grade_point for r in results if r.grade_point]
                        avg_cgpa = round(sum(vals) / len(vals), 1) if vals else 0.0
                except Exception:
                    pass

                result.append({
                    'id': dept.id,
                    'name': dept.name,
                    'students': students,
                    'btech_students': btech,
                    'placement_rate': placement_rate,
                    'avg_cgpa': avg_cgpa,
                })
        except Exception as e:
            _logger.warning("Department stats fetch error: %s", e)

        return result[:6]

    def _get_fee_monthly_trend(self):
        from calendar import monthrange
        today = date.today()
        result = []
        monthly_vals = []

        try:
            for i in range(7, -1, -1):
                year = today.year
                month = today.month - i
                while month <= 0:
                    month += 12
                    year -= 1
                _, last_day = monthrange(year, month)
                start = date(year, month, 1).strftime('%Y-%m-%d')
                end = date(year, month, last_day).strftime('%Y-%m-%d')
                payments = self.env['fee.payment'].search([
                    ('state', 'in', ['paid', 'partial']),
                    ('payment_date', '>=', start),
                    ('payment_date', '<=', end),
                ])
                total = sum(payments.mapped('total_amount'))
                label = date(year, month, 1).strftime('%b')
                monthly_vals.append({'label': label, 'value': total, 'date_start': start, 'date_end': end})
        except Exception as e:
            _logger.warning("Fee monthly trend fetch error: %s", e)

        max_val = max((mv['value'] for mv in monthly_vals), default=1) or 1
        for mv in monthly_vals:
            result.append({
                'label': mv['label'],
                'value': mv['value'],
                'height': round(mv['value'] / max_val * 100),
                'date_start': mv['date_start'],
                'date_end': mv['date_end'],
            })

        return result

    def _get_semester_admissions(self):
        result = []
        vals = []

        try:
            semesters = self.env['university.semester'].search([], order='name', limit=8)
            for sem in semesters:
                count = self.env['student.registration'].search_count([
                    ('semester_id', '=', sem.id),
                ])
                vals.append({'label': sem.name, 'value': count, 'id': sem.id})
        except Exception as e:
            _logger.warning("Semester admissions fetch error: %s", e)

        max_val = max((v['value'] for v in vals), default=1) or 1
        for v in vals:
            result.append({
                'label': v['label'],
                'value': v['value'],
                'height': round(v['value'] / max_val * 100),
                'id': v['id'],
            })

        return result

    @api.model
    def get_low_attendance_student_ids(self):
        """Return IDs of active students whose attendance is below 75%."""
        env = self.env
        today = date.today()
        year_start = today.replace(month=1, day=1)
        low_ids = []
        try:
            students = env['student.student'].search(self._student_active_domain())
            for student in students:
                att_records = env['student.attendance'].search([
                    ('student_id', '=', student.id),
                    ('date', '>=', year_start.strftime('%Y-%m-%d')),
                ])
                if att_records:
                    present = len(att_records.filtered(lambda r: r.state == 'present'))
                    pct = present / len(att_records) * 100
                    if pct < 75:
                        low_ids.append(student.id)
        except Exception as e:
            _logger.warning("get_low_attendance_student_ids error: %s", e)
        return low_ids

    @staticmethod
    def _format_amount(amount):
        if not amount:
            return '0'
        if amount >= 100000:
            return f"{amount / 100000:.1f}L"
        if amount >= 1000:
            return f"{amount / 1000:.1f}K"
        return str(round(amount))