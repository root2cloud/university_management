# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import base64
import logging

_logger = logging.getLogger(__name__)


class FacultyPortalController(CustomerPortal):
    """Faculty Portal Controller"""

    def _get_faculty(self):
        """Get faculty record for current user"""
        env = request.env(su=True)
        faculty = env['faculty.faculty'].search([('user_id', '=', request.env.uid)], limit=1)
        if not faculty:
            employee = env['hr.employee'].search([('user_id', '=', request.env.uid)], limit=1)
            if employee:
                faculty = env['faculty.faculty'].search([('employee_id', '=', employee.id)], limit=1)
        return faculty

    # ==================== FACULTY DASHBOARD ====================
    @http.route(['/my/faculty/dashboard'], type='http', auth="user", website=True)
    def faculty_dashboard(self, **kw):
        """Faculty Dashboard"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        # Get today's classes
        today = fields.Date.today()
        env = request.env(su=True)
        today_classes = env['university.timetable'].search([
            ('faculty_id', '=', faculty.id),
            ('active', '=', True),
        ])

        # Get attendance summary
        attendance_today = env['student.attendance'].search_count([
            ('faculty_id', '=', faculty.id),
            ('date', '=', today)
        ])

        values = {
            'faculty': faculty,
            'today_classes': today_classes,
            'attendance_today': attendance_today,
            'page_name': 'faculty_dashboard',
        }

        return request.render("university_management.faculty_dashboard", values)

    # ==================== MY CLASSES ====================
    @http.route(['/my/faculty/classes'], type='http', auth="user", website=True)
    def faculty_classes(self, **kw):
        """View assigned classes"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        # Get timetable
        env = request.env(su=True)
        timetable = env['university.timetable'].search([
            ('faculty_id', '=', faculty.id),
            ('active', '=', True)
        ], order='day_of_week, start_time')

        # Group by day
        timetable_by_day = {}
        for tt in timetable:
            if tt.day_of_week not in timetable_by_day:
                timetable_by_day[tt.day_of_week] = []
            timetable_by_day[tt.day_of_week].append(tt)

        # Get subjects
        subjects = env['university.subject'].search([
            ('faculty_ids', 'in', [faculty.id])
        ])

        values = {
            'faculty': faculty,
            'timetable_by_day': timetable_by_day,
            'subjects': subjects,
            'page_name': 'faculty_classes',
        }

        return request.render("university_management.faculty_classes", values)

    # ==================== ATTENDANCE ====================
    @http.route(['/my/faculty/attendance'], type='http', auth="user", website=True)
    def faculty_attendance(self, date=None, subject=None, batch=None, **kw):
        """Mark and view attendance"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        if not date:
            date = fields.Date.today()

        env = request.env(su=True)

        # Get subjects taught by faculty via courses
        taught_courses = env['university.course'].search([
            '|',
            ('faculty_id', '=', faculty.id),
            ('co_faculty_ids', 'in', [faculty.id])
        ])
        subjects = taught_courses.mapped('subject_id')

        # Get batches
        batches = env['university.batch'].search([
            ('active', '=', True)
        ])

        # Get attendance records
        domain = [('faculty_id', '=', faculty.id)]
        if date:
            domain += [('date', '=', str(date))]
        if subject:
            domain += [('subject_id', '=', int(subject))]
        if batch:
            # batch_id is a related field on student; filter via student_id instead
            batch_students = env['student.student'].search([('batch_id', '=', int(batch))]).ids
            if batch_students:
                domain += [('student_id', 'in', batch_students)]

        attendance_records = env['student.attendance'].search(domain, order='id')

        values = {
            'faculty': faculty,
            'subjects': subjects,
            'batches': batches,
            'attendance_records': attendance_records,
            'selected_date': date,
            'selected_subject': int(subject) if subject else None,
            'selected_batch': int(batch) if batch else None,
            'page_name': 'faculty_attendance',
        }

        return request.render("university_management.faculty_attendance", values)

    @http.route(['/my/faculty/attendance/students'], type='http', auth="user", website=True)
    def faculty_attendance_students(self, subject_id=None, batch_id=None, **kw):
        """Return JSON list of students for attendance modal"""
        import json
        faculty = self._get_faculty()
        if not faculty or not subject_id or not batch_id:
            return request.make_response(json.dumps({'students': []}),
                headers=[('Content-Type', 'application/json')])

        env = request.env(su=True)
        students = env['student.student'].search([
            ('batch_id', '=', int(batch_id)),
            ('state', 'not in', ['dropped', 'expelled'])
        ], order='id')

        result = []
        for s in students:
            result.append({
                'id': s.id,
                'name': s.partner_id.name or '',
                'reg_no': s.registration_number or '',
            })

        return request.make_response(json.dumps({'students': result}),
            headers=[('Content-Type', 'application/json')])

    @http.route(['/my/faculty/attendance/mark'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def faculty_attendance_mark(self, **post):
        """Mark attendance for students"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        try:
            date = post.get('date')
            subject_id = int(post.get('subject_id'))
            batch_id = int(post.get('batch_id'))

            # Get students
            env = request.env(su=True)
            students = env['student.student'].search([
                ('batch_id', '=', batch_id),
                ('state', 'not in', ['dropped', 'expelled'])
            ])

            # Get the course_id for this subject + faculty combo
            course = env['university.course'].search([
                ('subject_id', '=', subject_id),
                ('faculty_id', '=', faculty.id),
                ('batch_id', '=', batch_id),
            ], limit=1)

            # Mark attendance
            for student in students:
                status = post.get(f'attendance_{student.id}', 'absent')

                # Check if attendance already exists
                existing = env['student.attendance'].search([
                    ('student_id', '=', student.id),
                    ('course_id', '=', course.id),
                    ('date', '=', date),
                    ('faculty_id', '=', faculty.id)
                ])

                if existing:
                    existing.write({'state': status})
                else:
                    env['student.attendance'].create({
                        'student_id': student.id,
                        'course_id': course.id,
                        'date': date,
                        'faculty_id': faculty.id,
                        'state': status,
                    })

            return request.redirect(
                f'/my/faculty/attendance?date={date}&subject={subject_id}&batch={batch_id}&success=1')
        except Exception as e:
            _logger.error("Error marking attendance: %s", str(e))
            return request.redirect('/my/faculty/attendance?error=1')

    # ==================== STUDENTS ====================
    @http.route(['/my/faculty/students'], type='http', auth="user", website=True)
    def faculty_students(self, batch=None, **kw):
        """View students"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        env = request.env(su=True)

        # Get batches assigned to faculty (as coordinator OR as course faculty/co-faculty)
        coordinator_batches = env['university.batch'].search([
            ('coordinator_id', '=', faculty.id)
        ])

        # Batches where faculty teaches a course (as primary or co-faculty)
        taught_courses = env['university.course'].search([
            '|',
            ('faculty_id', '=', faculty.id),
            ('co_faculty_ids', 'in', [faculty.id])
        ])
        course_batch_ids = taught_courses.mapped('batch_id').ids

        # Combine both sources and remove duplicates
        all_batch_ids = list(set(coordinator_batches.ids + course_batch_ids))
        batches = env['university.batch'].browse(all_batch_ids)

        # Get students only when a batch is selected
        if batch:
            domain = [
                ('state', 'not in', ['dropped', 'expelled']),
                ('batch_id', '=', int(batch))
            ]
            students = env['student.student'].search(domain, order='id')
        else:
            students = env['student.student'].browse()

        values = {
            'faculty': faculty,
            'students': students,
            'batches': batches,
            'selected_batch': int(batch) if batch else None,
            'page_name': 'faculty_students',
        }

        return request.render("university_management.faculty_students", values)

    @http.route(['/my/faculty/student/<int:student_id>'], type='http', auth="user", website=True)
    def faculty_student_detail(self, student_id, **kw):
        """View student detail"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my/faculty/students')

        env = request.env(su=True)
        student = env['student.student'].browse(student_id)

        if not student.exists():
            return request.redirect('/my/faculty/students')

        # Get student's attendance in faculty's subjects
        attendance = env['student.attendance'].search([
            ('student_id', '=', student_id),
            ('faculty_id', '=', faculty.id)
        ], order='date desc', limit=20)

        values = {
            'faculty': faculty,
            'student': student,
            'attendance': attendance,
            'page_name': 'student_detail',
        }

        return request.render("university_management.faculty_student_detail", values)

    # ==================== LEAVE REQUESTS ====================
    @http.route(['/my/faculty/leave'], type='http', auth="user", website=True)
    def faculty_leave(self, **kw):
        """View and request leave"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        env = request.env(su=True)
        leave_requests = env['faculty.leave'].search([
            ('faculty_id', '=', faculty.id)
        ], order='date_from desc')

        values = {
            'faculty': faculty,
            'leave_requests': leave_requests,
            'page_name': 'faculty_leave',
        }

        return request.render("university_management.faculty_leave", values)

    @http.route(['/my/faculty/leave/request'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def faculty_leave_request(self, **post):
        """Submit leave request"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        try:
            leave_vals = {
                'faculty_id': faculty.id,
                'date_from': post.get('from_date'),
                'date_to': post.get('to_date'),
                'leave_type': post.get('leave_type'),
                'reason': post.get('reason'),
            }

            request.env(su=True)['faculty.leave'].create(leave_vals)

            return request.redirect('/my/faculty/leave?success=1')
        except Exception as e:
            _logger.error("Error submitting leave request: %s", str(e))
            return request.redirect('/my/faculty/leave?error=1')

    # ==================== PROFILE ====================
    @http.route(['/my/faculty/profile'], type='http', auth="user", website=True)
    def faculty_profile(self, **kw):
        """View and update profile"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        values = {
            'faculty': faculty,
            'page_name': 'faculty_profile',
        }

        return request.render("university_management.faculty_profile", values)

    @http.route(['/my/faculty/profile/update'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def faculty_profile_update(self, **post):
        """Update faculty profile"""
        faculty = self._get_faculty()

        if not faculty:
            return request.redirect('/my')

        try:
            update_vals = {
                'mobile': post.get('mobile'),
                'email': post.get('email'),
                'current_address': post.get('current_address'),
                'qualification': post.get('qualification'),
                'specialization': post.get('specialization'),
                'bio': post.get('bio'),
            }

            # Handle photo upload
            if post.get('photo'):
                update_vals['photo'] = base64.b64encode(post.get('photo').read())

            faculty.write(update_vals)

            return request.redirect('/my/faculty/profile?success=1')
        except Exception as e:
            _logger.error("Error updating faculty profile: %s", str(e))
            return request.redirect('/my/faculty/profile?error=1')