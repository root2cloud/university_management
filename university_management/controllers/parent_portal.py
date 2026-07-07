# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import logging
from types import SimpleNamespace

_logger = logging.getLogger(__name__)


class ParentPortalController(CustomerPortal):
    """Parent Portal Controller"""

    def _get_parent_students(self):
        """Get students linked to parent"""
        # Get all parent records for this user
        parent_records = request.env['student.parent'].sudo().search([
            ('user_id', '=', request.env.uid)
        ])

        # Get student IDs from parent records
        if parent_records:
            student_ids = parent_records.mapped('student_id').ids
            return request.env['student.student'].sudo().search([('id', 'in', student_ids)])
        return request.env['student.student']

    def _calculate_attendance_summary(self, student_id):
        """Calculate attendance statistics"""
        attendance_records = request.env['student.attendance'].sudo().search([
            ('student_id', '=', student_id),
        ])

        present = len(attendance_records.filtered(lambda r: r.state == 'present'))
        absent = len(attendance_records.filtered(lambda r: r.state == 'absent'))
        total = len(attendance_records)

        overall_percentage = (present / total * 100) if total > 0 else 0

        # Return a SimpleNamespace object instead of a dict
        return SimpleNamespace(
            present=present,
            absent=absent,
            total=total,
            overall=overall_percentage
        )

    # ==================== PARENT DASHBOARD ====================
    @http.route(['/my/parent/dashboard'], type='http', auth="user", website=True)
    def parent_dashboard(self, **kw):
        """Parent Dashboard"""
        # Get all parent records for this user
        parents = request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)])

        if not parents:
            return request.redirect('/my')

        # Get the first parent for display info
        parent = parents[0]
        # Get all student records (not parent records)
        students = self._get_parent_students()

        values = {
            'parent': parent,
            'students': students,  # This should now be student.student records
            'page_name': 'parent_dashboard',
        }

        return request.render("university_management.parent_dashboard", values)

    # ==================== STUDENT SELECTION ====================
    @http.route(['/my/parent/select-student'], type='http', auth="user", website=True)
    def parent_select_student(self, **kw):
        """Select student to view details"""
        students = self._get_parent_students()

        if not students:
            return request.redirect('/my')

        values = {
            'students': students,
            'page_name': 'select_student',
        }

        return request.render("university_management.parent_select_student", values)

    # ==================== STUDENT PROGRESS ====================
    @http.route(['/my/parent/student/<int:student_id>/progress'], type='http', auth="user", website=True)
    def parent_student_progress(self, student_id, **kw):
        """View student academic progress"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Get academic data
        results = request.env['examination.result'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'published')
        ], order='examination_id desc', limit=5)

        # Calculate attendance summary using the helper method
        attendance_summary = self._calculate_attendance_summary(student.id)

        # Calculate performance metrics for progress page
        # Get all published results for the student
        all_results = request.env['examination.result'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'published')
        ])

        # Calculate CGPA
        if all_results:
            total_grade_points = sum(all_results.mapped('grade_point'))
            cgpa = total_grade_points / len(all_results)

            # Calculate percentage
            total_obtained = sum(all_results.mapped('total_marks'))
            total_max = sum(all_results.mapped('max_marks'))
            percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
        else:
            cgpa = 0.0
            percentage = 0.0

        # Create performance object
        performance = SimpleNamespace(
            cgpa=cgpa,
            percentage=percentage,
            # Add other performance metrics if needed
        )

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'results': results,
            'attendance_summary': attendance_summary,
            'performance': performance,  # Add performance to template context
            'page_name': 'student_progress',
        }

        return request.render("university_management.parent_student_progress", values)

    # ==================== ATTENDANCE ====================
    @http.route(['/my/parent/student/<int:student_id>/attendance'], type='http', auth="user", website=True)
    def parent_student_attendance(self, student_id, date_from=None, date_to=None, **kw):
        """View student attendance"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Calculate attendance summary
        attendance_summary = self._calculate_attendance_summary(student_id)

        domain = [('student_id', '=', student.id)]
        if date_from:
            domain += [('date', '>=', date_from)]
        if date_to:
            domain += [('date', '<=', date_to)]

        attendance = request.env['student.attendance'].sudo().search(domain, order='date desc', limit=30)

        # Subject-wise attendance
        subject_attendance = {}
        for att in student.attendance_ids:
            subject = att.subject_id.name
            if subject not in subject_attendance:
                subject_attendance[subject] = {'present': 0, 'absent': 0, 'total': 0}
            subject_attendance[subject]['total'] += 1
            if att.state == 'present':
                subject_attendance[subject]['present'] += 1
            elif att.state == 'absent':
                subject_attendance[subject]['absent'] += 1

        # Calculate percentages
        for subject in subject_attendance:
            total = subject_attendance[subject]['total']
            if total > 0:
                subject_attendance[subject]['percentage'] = (subject_attendance[subject]['present'] / total) * 100

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'attendance': attendance,
            'attendance_summary': attendance_summary,
            'subject_attendance': subject_attendance,
            'date_from': date_from,
            'date_to': date_to,
            'page_name': 'student_attendance',
        }

        return request.render("university_management.parent_student_attendance", values)

    # ==================== FEE PAYMENTS ====================
    @http.route(['/my/parent/student/<int:student_id>/fees'], type='http', auth="user", website=True)
    def parent_student_fees(self, student_id, **kw):
        """View student fee payments"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Get all fee payments for this student
        fee_payments = request.env['fee.payment'].sudo().search([
            ('student_id', '=', student.id)
        ], order='payment_date desc')

        # Calculate fee summary from payments
        total_paid = sum(fee_payments.filtered(lambda p: p.state == 'paid').mapped('total_amount'))

        # Get all fee structures for the student's program
        fee_structures = request.env['fee.structure'].sudo().search([
            ('program_id', '=', student.program_id.id)
        ])

        total_fee = sum(fee_structures.mapped('total_amount')) if fee_structures else 0
        total_due = total_fee - total_paid if total_fee > total_paid else 0

        # Fee summary as SimpleNamespace object
        fee_summary = SimpleNamespace(
            total_fee=total_fee,
            paid=total_paid,
            due=total_due,
            percentage_paid=(total_paid / total_fee * 100) if total_fee > 0 else 0,
        )

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'fee_payments': fee_payments,
            'fee_summary': fee_summary,
            'page_name': 'student_fees',
        }

        return request.render("university_management.parent_student_fees", values)

    # ==================== RESULTS ====================
    @http.route(['/my/parent/student/<int:student_id>/results'], type='http', auth="user", website=True)
    def parent_student_results(self, student_id, **kw):
        """View student examination results"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        results = request.env['examination.result'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'published')
        ], order='examination_id desc')

        # Calculate performance metrics
        # Get all published results for the student
        all_results = request.env['examination.result'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'published')
        ])

        # Calculate CGPA
        if all_results:
            total_grade_points = sum(all_results.mapped('grade_point'))
            cgpa = total_grade_points / len(all_results)

            # Calculate percentage
            total_obtained = sum(all_results.mapped('total_marks'))
            total_max = sum(all_results.mapped('max_marks'))
            percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
        else:
            cgpa = 0.0
            percentage = 0.0

        # Calculate total credits earned
        passed_results = all_results.filtered(lambda r: r.is_pass)
        total_credits = sum(passed_results.mapped('course_id.credits')) if passed_results else 0

        # Performance summary as SimpleNamespace object
        performance = SimpleNamespace(
            cgpa=cgpa,
            percentage=percentage,
            total_credits=total_credits,
            rank=student.class_rank if hasattr(student, 'class_rank') else None,
        )

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'results': results,
            'performance': performance,
            'page_name': 'student_results',
        }

        return request.render("university_management.parent_student_results", values)

    # ==================== TIMETABLE ====================
    @http.route(['/my/parent/student/<int:student_id>/timetable'], type='http', auth="user", website=True)
    def parent_student_timetable(self, student_id, **kw):
        """View student timetable"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        timetable = request.env['university.timetable'].sudo().search([
            ('batch_id', '=', student.batch_id.id),
            ('semester_id', '=', student.current_semester),
            ('active', '=', True)
        ], order='day_of_week, start_time')

        # Group by day
        timetable_by_day = {}
        for tt in timetable:
            if tt.day_of_week not in timetable_by_day:
                timetable_by_day[tt.day_of_week] = []
            timetable_by_day[tt.day_of_week].append(tt)

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'timetable_by_day': timetable_by_day,
            'page_name': 'student_timetable',
        }

        return request.render("university_management.parent_student_timetable", values)

    # ==================== LEAVE REQUESTS ====================
    @http.route(['/my/parent/student/<int:student_id>/leave/request'], type='http', auth="user", website=True)
    def parent_leave_request(self, student_id, **kw):
        """Request leave for student"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Get existing leave requests
        leave_requests = request.env['student.leave'].sudo().search([
            ('student_id', '=', student.id)
        ], order='date_from desc')

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'leave_requests': leave_requests,
            'page_name': 'leave_request',
        }

        return request.render("university_management.parent_leave_request", values)

    @http.route(['/my/parent/student/<int:student_id>/leave/submit'], type='http', auth="user", methods=['POST'],
                website=True, csrf=True)
    def parent_leave_submit(self, student_id, **post):
        """Submit leave request"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        try:
            leave_vals = {
                'student_id': student.id,
                'date_from': post.get('date_from'),
                'to_date': post.get('to_date'),
                'leave_type': post.get('leave_type'),
                'reason': post.get('reason'),
                'requested_by': 'parent',
            }

            request.env['student.leave'].sudo().create(leave_vals)

            return request.redirect(f'/my/parent/student/{student_id}/leave/request?success=1')
        except Exception as e:
            _logger.error("Error submitting leave request: %s", str(e))
            return request.redirect(f'/my/parent/student/{student_id}/leave/request?error=1')

    # ==================== COMMUNICATION ====================
    @http.route(['/my/parent/student/<int:student_id>/messages'], type='http', auth="user", website=True)
    def parent_student_messages(self, student_id, **kw):
        """View messages and communications"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Get messages/notifications
        messages = request.env['mail.message'].sudo().search([
            ('model', '=', 'student.student'),
            ('res_id', '=', student.id),
        ], order='date desc', limit=20)

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'messages': messages,
            'page_name': 'student_messages',
        }

        return request.render("university_management.parent_student_messages", values)

    # ==================== CONTACT TEACHER ====================
    @http.route(['/my/parent/contact-teacher'], type='http', auth="user", website=True)
    def parent_contact_teacher(self, student_id=None, **kw):
        """Contact teacher form"""
        students = self._get_parent_students()

        if not students:
            return request.redirect('/my')

        student = None
        if student_id:
            student = students.filtered(lambda s: s.id == int(student_id))

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'students': students,
            'student': student,
            'page_name': 'contact_teacher',
        }

        return request.render("university_management.parent_contact_teacher", values)

    @http.route(['/my/parent/contact-teacher/submit'], type='http', auth="user", methods=['POST'], website=True,
                csrf=True)
    def parent_contact_teacher_submit(self, **post):
        """Submit contact teacher request"""
        try:
            # Create communication record or send message
            vals = {
                'parent_id': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1).id,
                'student_id': int(post.get('student_id')),
                'subject': post.get('subject'),
                'message': post.get('message'),
            }

            # Send to class coordinator or HOD
            # Implementation depends on your communication model

            return request.redirect('/my/parent/contact-teacher?success=1')
        except Exception as e:
            _logger.error("Error submitting teacher contact: %s", str(e))
            return request.redirect('/my/parent/contact-teacher?error=1')

    # ==================== EVENTS & ACTIVITIES ====================
    @http.route(['/my/parent/student/<int:student_id>/events'], type='http', auth="user", website=True)
    def parent_student_events(self, student_id, **kw):
        """View student events and activities"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Get event registrations (sudo so parent portal user can read
        # university.event records accessed via the registration Many2one)
        event_registrations = request.env['university.event.registration'].sudo().search([
            ('student_id', '=', student.id)
        ], order='create_date desc')

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'event_registrations': event_registrations,
            'page_name': 'student_events',
        }

        return request.render("university_management.parent_student_events", values)

    # ==================== DOCUMENTS ====================
    @http.route(['/my/parent/student/<int:student_id>/documents'], type='http', auth="user", website=True)
    def parent_student_documents(self, student_id, **kw):
        """View and download student documents"""
        students = self._get_parent_students()
        student = students.filtered(lambda s: s.id == student_id)

        if not student:
            return request.redirect('/my/parent/select-student')

        # Get documents with sudo so portal user can read student.document
        # and pre-compute attachment URLs to avoid ir.attachment access error in template
        documents = request.env['student.document'].sudo().search([
            ('student_id', '=', student.id)
        ], order='create_date desc')

        # Build a dict of doc.id -> download URL using access tokens so that
        # portal users (who cannot read ir.attachment directly) can still download.
        # generate_access_token() is called in sudo context and returns a
        # time-limited token that authorises the /web/content route for any user.
        doc_download_urls = {}
        for doc in documents:
            if doc.attachment_id:
                attachment = doc.attachment_id.sudo()
                tokens = attachment.generate_access_token()
                token = tokens[0] if tokens else ''
                doc_download_urls[doc.id] = (
                    '/web/content/%s/%s?access_token=%s&download=true'
                    % (attachment.id, attachment.name, token)
                )

        values = {
            'parent': request.env['student.parent'].sudo().search([('user_id', '=', request.env.uid)], limit=1),
            'student': student,
            'documents': documents,
            'doc_download_urls': doc_download_urls,
            'page_name': 'student_documents',
        }

        return request.render("university_management.parent_student_documents", values)