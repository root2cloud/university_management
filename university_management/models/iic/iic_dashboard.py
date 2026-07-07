# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date
from collections import defaultdict


class IICDashboard(models.AbstractModel):
    _name = 'iic.dashboard'
    _description = 'IIC Dashboard Statistics'

    @api.model
    def get_dashboard_data(self, academic_year_id=None):
        """
        Return a rich, event-wise aggregated payload for the IIC dashboard.

        Key fixes vs. original:
        1. Attendance is aggregated EVENT-WISE — each event's present_count is
           individually tracked and summed, not collapsed into a single figure.
        2. Attendance breakdown is provided per department, per batch, and per
           academic year so the front-end can render granular charts.
        3. 'report_approved' events were previously excluded from the completed
           count — they are now included.
        4. activity_chart is always populated, even when counts are 0, so that
           the doughnut chart always has labels to render.
        5. Quarterly attendance totals (present + absent) are returned alongside
           event counts so the quarterly bar chart carries meaningful data.
        """
        domain = []
        if academic_year_id:
            domain.append(('academic_year_id', '=', academic_year_id))

        events = self.env['iic.event'].search(domain)

        # ── Basic event counts ────────────────────────────────────────────────
        total_events = len(events)
        mandatory_count = len(events.filtered(lambda e: e.activity_type == 'mandatory'))
        self_driven_count = len(events.filtered(lambda e: e.activity_type == 'self_driven'))

        active_states = {'completed', 'report_approved'}
        pending_states = {'planning', 'poster_pending', 'poster_approved', 'ongoing'}

        completed_events = events.filtered(lambda e: e.iic_state in active_states)
        pending_events = events.filtered(lambda e: e.iic_state in pending_states)
        report_submitted_count = len(events.filtered(lambda e: e.report_submitted))

        # ── Event-wise attendance aggregation ────────────────────────────────
        # We pull ALL iic.attendance records for these events in ONE query and
        # group in Python — avoids N+1 and gives us rich breakdown data.
        event_ids = events.ids
        attendance_records = self.env['iic.attendance'].search([
            ('event_id', 'in', event_ids),
            ('participant_type', '=', 'student'),
        ])

        # Aggregate globally
        total_registered = len(attendance_records)
        total_present = len(attendance_records.filtered(lambda a: a.status == 'present'))
        total_absent = total_registered - total_present

        overall_participation_pct = round(
            (total_present / total_registered * 100) if total_registered else 0, 1
        )

        # ── Per-event attendance detail ──────────────────────────────────────
        event_attendance_map = defaultdict(lambda: {'registered': 0, 'present': 0})
        for att in attendance_records:
            key = att.event_id.id
            event_attendance_map[key]['registered'] += 1
            if att.status == 'present':
                event_attendance_map[key]['present'] += 1

        # ── Department-wise attendance breakdown ─────────────────────────────
        dept_map = defaultdict(lambda: {'registered': 0, 'present': 0})
        for att in attendance_records:
            dept_name = att.department_id.name if att.department_id else 'Unknown'
            dept_map[dept_name]['registered'] += 1
            if att.status == 'present':
                dept_map[dept_name]['present'] += 1

        dept_breakdown = [
            {
                'department': dept,
                'registered': v['registered'],
                'present': v['present'],
                'pct': round(v['present'] / v['registered'] * 100, 1) if v['registered'] else 0,
            }
            for dept, v in sorted(dept_map.items(), key=lambda x: -x[1]['present'])
        ]

        # ── Batch-wise attendance breakdown ──────────────────────────────────
        batch_map = defaultdict(lambda: {'registered': 0, 'present': 0})
        for att in attendance_records:
            batch_name = (
                att.student_id.batch_id.name
                if att.student_id and att.student_id.batch_id
                else 'Unknown'
            )
            batch_map[batch_name]['registered'] += 1
            if att.status == 'present':
                batch_map[batch_name]['present'] += 1

        batch_breakdown = [
            {
                'batch': batch,
                'registered': v['registered'],
                'present': v['present'],
                'pct': round(v['present'] / v['registered'] * 100, 1) if v['registered'] else 0,
            }
            for batch, v in sorted(batch_map.items(), key=lambda x: -x[1]['present'])
        ]

        # ── Current quarter (academic calendar: Jul–Sep = Q1, Oct–Dec = Q2,
        #    Jan–Mar = Q3, Apr–Jun = Q4 for Indian universities)
        #    Using the same convention as iic_event._compute_quarter: ─────────
        month = date.today().month
        if month in [1, 2, 3]:
            current_quarter = 'Q1'
        elif month in [4, 5, 6]:
            current_quarter = 'Q2'
        elif month in [7, 8, 9]:
            current_quarter = 'Q3'
        else:
            current_quarter = 'Q4'

        # ── Per-quarter breakdown (events + attendance) ──────────────────────
        quarters = {}
        for q in ['Q1', 'Q2', 'Q3', 'Q4']:
            q_events = events.filtered(lambda e, _q=q: e.quarter == _q)
            q_event_ids = q_events.ids
            q_att = attendance_records.filtered(lambda a: a.event_id.id in set(q_event_ids))
            q_present = len(q_att.filtered(lambda a: a.status == 'present'))
            q_registered = len(q_att)

            quarters[q] = {
                'total': len(q_events),
                'completed': len(q_events.filtered(lambda e: e.iic_state in active_states)),
                'mandatory': len(q_events.filtered(lambda e: e.activity_type == 'mandatory')),
                'registered': q_registered,
                'present': q_present,
                'absent': q_registered - q_present,
                'participation_pct': round(
                    (q_present / q_registered * 100) if q_registered else 0, 1
                ),
            }

        # ── Activity type breakdown — always include all types (even 0) ──────
        activity_type_labels = [
            ('mandatory', 'MSME Mandatory'),
            ('self_driven', 'Self Driven'),
            ('workshop', 'Workshop'),
            ('seminar', 'Seminar'),
            ('innovation_talk', 'Innovation Talk'),
            ('entrepreneurship', 'Entrepreneurship'),
            ('hackathon', 'Hackathon'),
            ('other', 'Other'),
        ]
        activity_chart = []
        for atype, label in activity_type_labels:
            count = len(events.filtered(lambda e, _t=atype: e.activity_type == _t))
            # Include even zero-count types so the chart always has labels
            activity_chart.append({'label': label, 'value': count, 'type': atype})

        # ── Per-event attendance list (for event-wise table) ─────────────────
        event_attendance_list = []
        for e in events.sorted(key=lambda ev: ev.event_date or date.min, reverse=True)[:20]:
            ea = event_attendance_map.get(e.id, {'registered': 0, 'present': 0})
            registered = ea['registered']
            present = ea['present']
            event_attendance_list.append({
                'id': e.id,
                'name': e.name,
                'date': e.event_date.strftime('%d %b %Y') if e.event_date else '',
                'quarter': e.quarter or '',
                'type': e.activity_type or '',
                'state': e.iic_state or '',
                'registered': registered,
                'present': present,
                'absent': registered - present,
                'pct': round(present / registered * 100, 1) if registered else 0,
            })

        # ── Recent events (last 10 for the summary table) ────────────────────
        recent_events = self.env['iic.event'].search(
            domain, order='event_date desc', limit=10
        )
        recent_events_list = []
        for e in recent_events:
            ea = event_attendance_map.get(e.id, {'registered': 0, 'present': 0})
            recent_events_list.append({
                'id': e.id,
                'name': e.name,
                'date': e.event_date.strftime('%d %b %Y') if e.event_date else '',
                'type': e.activity_type or '',
                'state': e.iic_state or '',
                'participants': ea['present'],
                'registered': ea['registered'],
                'pct': round(ea['present'] / ea['registered'] * 100, 1) if ea['registered'] else 0,
            })

        # ── Average participation across completed events ─────────────────────
        completed_with_att = [
            e for e in completed_events if event_attendance_map.get(e.id, {}).get('registered', 0) > 0
        ]
        avg_participation = (
            sum(
                event_attendance_map[e.id]['present'] / event_attendance_map[e.id]['registered'] * 100
                for e in completed_with_att
            ) / len(completed_with_att)
            if completed_with_att else 0
        )

        return {
            # ── KPI Counters ────────────────────────────────────────────────
            'total_events': total_events,
            'mandatory_count': mandatory_count,
            'self_driven_count': self_driven_count,
            'completed_count': len(completed_events),
            'pending_count': len(pending_events),
            'report_submitted': report_submitted_count,

            # ── Attendance (event-wise aggregated) ─────────────────────────
            'total_registered': total_registered,          # all student attendees across events
            'total_present': total_present,                # students marked present across events
            'total_absent': total_absent,
            'overall_participation_pct': overall_participation_pct,
            'avg_participation_pct': round(avg_participation, 1),

            # Legacy key retained for backward compat — now = total_present
            'total_student_participations': total_present,

            # ── Breakdowns ─────────────────────────────────────────────────
            'dept_breakdown': dept_breakdown,
            'batch_breakdown': batch_breakdown,
            'event_attendance': event_attendance_list,

            # ── Quarter / chart data ────────────────────────────────────────
            'current_quarter': current_quarter,
            'quarters': quarters,
            'activity_chart': activity_chart,
            'recent_events': recent_events_list,

            # ── Compliance score ───────────────────────────────────────────
            'compliance_score': round(
                (report_submitted_count / total_events * 100) if total_events else 0, 1
            ),
        }