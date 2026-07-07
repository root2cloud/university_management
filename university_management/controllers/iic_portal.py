# -*- coding: utf-8 -*-

from odoo import http, fields as odoo_fields
from odoo.http import request
from datetime import datetime


class IICPortalController(http.Controller):

    # ── Public events listing ─────────────────────────────────────────────
    @http.route('/iic/events', type='http', auth='public', website=True)
    def iic_events_list(self, **kwargs):
        domain = [('iic_state', 'not in', ['planning', 'archived'])]
        activity_type = kwargs.get('activity_type')
        quarter = kwargs.get('quarter')
        if activity_type:
            domain.append(('activity_type', '=', activity_type))
        if quarter:
            domain.append(('quarter', '=', quarter))
        events = request.env['iic.event'].sudo().search(domain, order='date_begin desc', limit=20)
        activity_types = request.env['iic.event']._fields['activity_type'].selection
        quarters = [('q1', 'Q1 Jan-Mar'), ('q2', 'Q2 Apr-Jun'),
                    ('q3', 'Q3 Jul-Sep'), ('q4', 'Q4 Oct-Dec')]
        return request.render('university_management.iic_portal_events', {
            'events': events,
            'activity_types': activity_types,
            'quarters': quarters,
            'selected_type': activity_type,
            'selected_quarter': quarter,
        })

    @http.route('/iic/events/<int:event_id>', type='http', auth='public', website=True)
    def iic_event_detail(self, event_id, **kwargs):
        event = request.env['iic.event'].sudo().browse(event_id)
        if not event.exists():
            return request.not_found()
        return request.render('university_management.iic_portal_event_detail', {
            'event': event,
        })

    # ── Helper: identify who is scanning ──────────────────────────────────
    def _get_attendee(self):
        """
        Returns (attendee_type, student_record, faculty_record).
        Works for both students and faculty who have a portal/internal user.
        """
        user = request.env.user
        # Check if this user is linked to a student
        student = request.env['student.student'].sudo().search(
            [('user_id', '=', user.id)], limit=1
        )
        if student:
            return 'student', student, None
        # Check if this user is linked to a faculty/employee
        employee = request.env['hr.employee'].sudo().search(
            [('user_id', '=', user.id)], limit=1
        )
        if employee:
            return 'faculty', None, employee
        return None, None, None

    # ── QR 1: CHECK-IN ────────────────────────────────────────────────────
    @http.route('/iic/attendance/checkin/<string:token>', type='http', auth='user', website=True)
    def iic_checkin(self, token, **kwargs):
        # Find the event by check-in token
        event = request.env['iic.event'].sudo().search([('qr_token', '=', token)], limit=1)
        if not event:
            return request.render('university_management.iic_qr_invalid', {
                'message': 'Invalid or expired check-in QR code. Please contact the event coordinator.',
                'scan_type': 'Check-in',
            })

        # Identify who is scanning
        attendee_type, student, employee = self._get_attendee()
        if not attendee_type:
            return request.render('university_management.iic_qr_invalid', {
                'message': 'Your account is not linked to any student or faculty record. Please contact the administrator.',
                'scan_type': 'Check-in',
            })

        now = datetime.utcnow()

        # Check if already has an attendance record
        domain = [('event_id', '=', event.id)]
        if attendee_type == 'student':
            domain.append(('student_id', '=', student.id))
        else:
            domain.append(('faculty_id', '=', employee.id))

        existing = request.env['iic.attendance'].sudo().search(domain, limit=1)

        if existing:
            if existing.checkin_time:
                # Already checked in
                return request.render('university_management.iic_qr_checkin_done', {
                    'event': event,
                    'attendance': existing,
                    'already_checked_in': True,
                    'attendee_name': student.name if student else employee.name,
                })
        else:
            # Create new attendance record with check-in time
            vals = {
                'event_id': event.id,
                'attendee_type': attendee_type,
                'participant_type': attendee_type,
                'checkin_time': now,
                'checkin_qr_verified': True,
                'status': 'checked_in',
                'marked_at': now,
                'qr_verified': True,
            }
            if attendee_type == 'student':
                vals.update({
                    'student_id': student.id,
                    'department_id': student.department_id.id if student.department_id else False,
                    'registration_number': student.registration_number,
                })
            else:
                vals['faculty_id'] = employee.id
                faculty_rec = request.env['faculty.faculty'].sudo().search(
                    [('employee_id', '=', employee.id)], limit=1
                )
                if faculty_rec and faculty_rec.department_id:
                    vals['department_id'] = faculty_rec.department_id.id
            existing = request.env['iic.attendance'].sudo().create(vals)

        return request.render('university_management.iic_qr_checkin_done', {
            'event': event,
            'attendance': existing,
            'already_checked_in': False,
            'attendee_name': student.name if student else employee.name,
        })

    # ── QR 2: CHECK-OUT ───────────────────────────────────────────────────
    @http.route('/iic/attendance/checkout/<string:token>', type='http', auth='user', website=True)
    def iic_checkout(self, token, **kwargs):
        # Find the event by check-OUT token
        event = request.env['iic.event'].sudo().search([('qr_checkout_token', '=', token)], limit=1)
        if not event:
            return request.render('university_management.iic_qr_invalid', {
                'message': 'Invalid or expired check-out QR code. Please contact the event coordinator.',
                'scan_type': 'Check-out',
            })

        # Identify who is scanning
        attendee_type, student, employee = self._get_attendee()
        if not attendee_type:
            return request.render('university_management.iic_qr_invalid', {
                'message': 'Your account is not linked to any student or faculty record.',
                'scan_type': 'Check-out',
            })

        now = datetime.utcnow()

        # Find their attendance record
        domain = [('event_id', '=', event.id)]
        if attendee_type == 'student':
            domain.append(('student_id', '=', student.id))
        else:
            domain.append(('faculty_id', '=', employee.id))

        attendance = request.env['iic.attendance'].sudo().search(domain, limit=1)
        attendee_name = student.name if student else employee.name

        # Case 1: No check-in found — scanned checkout without checkin
        if not attendance or not attendance.checkin_time:
            return request.render('university_management.iic_qr_checkout_no_checkin', {
                'event': event,
                'attendee_name': attendee_name,
            })

        # Case 2: Already checked out
        if attendance.checkout_time:
            return request.render('university_management.iic_qr_checkout_done', {
                'event': event,
                'attendance': attendance,
                'attendee_name': attendee_name,
                'already_done': True,
            })

        # Case 3: Valid check-out — calculate duration
        checkin = attendance.checkin_time
        duration_minutes = int((now - checkin).total_seconds() / 60)
        min_required = event.min_attendance_minutes

        if duration_minutes >= min_required:
            final_status = 'present'
        else:
            final_status = 'absent'

        attendance.sudo().write({
            'checkout_time': now,
            'checkout_qr_verified': True,
            'duration_minutes': duration_minutes,
            'status': final_status,
            'marked_at': now,
        })

        return request.render('university_management.iic_qr_checkout_done', {
            'event': event,
            'attendance': attendance,
            'attendee_name': attendee_name,
            'already_done': False,
            'duration_minutes': duration_minutes,
            'min_required': min_required,
            'final_status': final_status,
        })

    # ── Legacy route — keep for backwards compatibility ───────────────────
    @http.route('/iic/attendance/mark/<string:token>', type='http', auth='user', website=True)
    def iic_attendance_mark_legacy(self, token, **kwargs):
        """Legacy single-QR route — redirect to checkin flow."""
        return self.iic_checkin(token, **kwargs)