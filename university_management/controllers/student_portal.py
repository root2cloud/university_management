# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.tools import groupby as groupbyelem
from operator import itemgetter
import base64
import logging
import datetime

_logger = logging.getLogger(__name__)


class StudentPortalController(CustomerPortal):
    """Student Portal Controller"""

    def _prepare_portal_layout_values(self):
        """Add student-specific values to portal layout."""
        values = super(StudentPortalController, self)._prepare_portal_layout_values()

        # Always fetch student — will be an empty recordset if user is not a student
        student = request.env['student.student'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1
        )

        # Always set 'student' so templates never get a KeyError
        values['student'] = student
        values['is_student'] = bool(student)

        if student:
            values.update({
                'fee_count': len(student.fee_payment_ids),
                'attendance_count': len(student.attendance_ids),
                'result_count': len(student.exam_result_ids),
                'library_issue_count': request.env['library.issue'].sudo().search_count([
                    ('member_id', '=', student.id),
                    ('state', 'in', ['issued', 'overdue']),
                ]),
            })

        return values

    # ==================== STUDENT DASHBOARD ====================
    @http.route(['/my/student/dashboard'], type='http', auth="user", website=True)
    def student_dashboard(self, **kw):
        """Student Dashboard"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        # Get dashboard data
        values = {
            'student': student,
            'page_name': 'student_dashboard',

            # Academic Info
            'current_semester': student.current_semester,
            'cgpa': student.cgpa,
            'attendance_percentage': student.attendance_percentage,

            # Recent Activity
            'recent_attendance': request.env['student.attendance'].search([
                ('student_id', '=', student.id)
            ], limit=5, order='date desc'),

            'recent_fees': student.fee_payment_ids.sorted(key=lambda r: r.payment_date or datetime.date.min, reverse=True)[:5],

            # Upcoming
            'upcoming_exams': request.env['examination.examination'].search([
                ('semester_id', '=', student.current_semester),
                ('start_date', '>=', request.env.context.get('today', fields.Date.today())),
            ], limit=3, order='start_date'),
        }

        return request.render("university_management.student_dashboard", values)

    # ==================== PROFILE ====================
    @http.route(['/my/profile'], type='http', auth="user", website=True)
    def student_profile(self, **kw):
        """Student Profile"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        countries = request.env['res.country'].sudo().search([])
        states = request.env['res.country.state'].sudo().search([])

        values = {
            'student': student,
            'countries': countries,
            'states': states,
            'page_name': 'student_profile',
        }

        return request.render("university_management.student_profile", values)

    @http.route(['/my/profile/update'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def student_profile_update(self, **post):
        """Update student profile"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        try:
            # Update allowed fields
            update_vals = {
                'mobile': post.get('mobile'),
                'email': post.get('email'),
                'current_address': post.get('current_address'),
                'city': post.get('city'),
                'zip': post.get('zip'),
                'emergency_contact_name': post.get('emergency_contact_name'),
                'emergency_contact_phone': post.get('emergency_contact_phone'),
            }

            if post.get('state_id'):
                update_vals['state_id'] = int(post.get('state_id'))

            # Handle photo upload
            if post.get('photo'):
                update_vals['photo'] = base64.b64encode(post.get('photo').read())

            student.write(update_vals)

            return request.redirect('/my/profile?success=1')
        except Exception as e:
            _logger.error("Error updating student profile: %s", str(e))
            return request.redirect('/my/profile?error=1')

    # ==================== ATTENDANCE ====================
    @http.route(['/my/attendance', '/my/attendance/page/<int:page>'], type='http', auth="user", website=True)
    def student_attendance(self, page=1, date_from=None, date_to=None, subject=None, **kw):
        """View attendance records"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        Attendance = request.env['student.attendance']

        domain = [('student_id', '=', student.id)]
        if date_from:
            domain += [('date', '>=', date_from)]
        if date_to:
            domain += [('date', '<=', date_to)]
        if subject:
            domain += [('subject_id', '=', int(subject))]

        # Pager
        attendance_count = Attendance.search_count(domain)
        pager = portal_pager(
            url="/my/attendance",
            url_args={'date_from': date_from, 'date_to': date_to, 'subject': subject},
            total=attendance_count,
            page=page,
            step=20,
        )

        attendance = Attendance.search(domain, limit=20, offset=pager['offset'], order='date desc')
        subjects = request.env['university.subject'].search([
            ('semester_number', '=', student.current_semester)
        ])

        values = {
            'student': student,
            'attendance': attendance,
            'subjects': subjects,
            'pager': pager,
            'date_from': date_from,
            'date_to': date_to,
            'selected_subject': int(subject) if subject else None,
            'page_name': 'attendance',
        }

        return request.render("university_management.student_attendance", values)

    # ==================== TIMETABLE ====================
    @http.route(['/my/timetable'], type='http', auth="user", website=True)
    def student_timetable(self, **kw):
        """View class timetable"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        timetable = request.env['university.timetable'].search([
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
            'student': student,
            'timetable_by_day': timetable_by_day,
            'page_name': 'timetable',
        }

        return request.render("university_management.student_timetable", values)

    # ==================== FEE PAYMENTS ====================
    @http.route(['/my/fees', '/my/fees/page/<int:page>'], type='http', auth="user", website=True)
    def student_fees(self, page=1, **kw):
        """View fee payments"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        FeePayment = request.env['fee.payment']

        domain = [('student_id', '=', student.id)]

        # Pager
        fee_count = FeePayment.search_count(domain)
        pager = portal_pager(
            url="/my/fees",
            total=fee_count,
            page=page,
            step=10,
        )

        fees = FeePayment.search(domain, limit=10, offset=pager['offset'], order='payment_date desc')

        total_fee = sum(student.fee_payment_ids.mapped('amount')) + student.total_fee_due

        values = {
            'student': student,
            'fees': fees,
            'pager': pager,
            'total_fee': total_fee,
            'total_paid': student.total_fee_paid,
            'total_due': student.total_fee_due,
            'page_name': 'fees',
        }

        return request.render("university_management.student_fees", values)

    @http.route(['/my/fee/<int:fee_id>'], type='http', auth="user", website=True)
    def student_fee_detail(self, fee_id, **kw):
        """Fee payment detail"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)
        fee = request.env['fee.payment'].browse(fee_id)

        if not student or fee.student_id != student:
            return request.redirect('/my/fees')

        values = {
            'student': student,
            'fee': fee,
            'page_name': 'fee_detail',
        }

        return request.render("university_management.student_fee_detail", values)

    # ==================== RESULTS ====================
    @http.route(['/my/results'], type='http', auth="user", website=True)
    def student_results(self, **kw):
        """View examination results"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        results = request.env['examination.result'].search([
            ('student_id', '=', student.id),
            ('state', '=', 'published')
        ], order='examination_id desc')

        values = {
            'student': student,
            'results': results,
            'page_name': 'results',
        }

        return request.render("university_management.student_results", values)

    # ==================== LIBRARY ====================
    @http.route(['/my/library'], type='http', auth="user", website=True)
    def student_library(self, **kw):
        """View library issued books"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        issued_books = request.env['library.issue'].search([
            ('member_id', '=', student.id),
            ('state', 'in', ['issued', 'overdue'])
        ])

        history = request.env['library.issue'].search([
            ('member_id', '=', student.id),
            ('state', '=', 'returned')
        ], limit=10, order='return_date desc')

        fines = request.env['library.fine'].search([
            ('issue_id.member_id', '=', student.id),
            ('state', '!=', 'paid')
        ])

        values = {
            'student': student,
            'issued_books': issued_books,
            'history': history,
            'fines': fines,
            'page_name': 'library',
        }

        return request.render("university_management.student_library", values)

    # ==================== EVENTS ====================
    @http.route(['/my/events', '/my/registrations'], type='http', auth="user", website=True)
    def student_events(self, **kw):
        """View registered events"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        registrations = request.env['university.event.registration'].sudo().search([
            ('student_id', '=', student.id)
        ], order='create_date desc')

        values = {
            'student': student,
            'registrations': registrations,
            'page_name': 'events',
        }

        return request.render("university_management.student_events", values)

    # ==================== HOSTEL ====================
    @http.route(['/my/hostel'], type='http', auth="user", website=True)
    def student_hostel(self, **kw):
        """View hostel allocation"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        allocation = request.env['hostel.allocation'].search([
            ('student_id', '=', student.id),
            ('state', '=', 'allocated')
        ], limit=1)

        values = {
            'student': student,
            'allocation': allocation,
            'page_name': 'hostel',
        }

        return request.render("university_management.student_hostel", values)

    # ==================== TRANSPORT ====================
    @http.route(['/my/transport'], type='http', auth="user", website=True)
    def student_transport(self, **kw):
        """View transport allocation"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        transport = request.env['transport.allocation'].search([
            ('student_id', '=', student.id),
            ('state', '=', 'active')
        ], limit=1)

        # Prepare safe values for template
        driver_name = ""
        driver_mobile = ""
        vehicle_name = ""
        vehicle_number = ""

        if transport:
            # Get vehicle info safely
            if transport.vehicle_id:
                vehicle_name = transport.vehicle_id.name or ""
                vehicle_number = transport.vehicle_id.vehicle_number or ""

                # Try to get driver info - handle potential access errors
                try:
                    if transport.vehicle_id.driver_id:
                        driver_name = transport.vehicle_id.driver_id.name or ""
                        driver_mobile = transport.vehicle_id.driver_id.mobile or ""
                except Exception:
                    # If we can't access driver info, just show generic message
                    driver_name = "Driver Assigned"
                    driver_mobile = ""

        values = {
            'student': student,
            'transport': transport,
            'driver_name': driver_name,
            'driver_mobile': driver_mobile,
            'vehicle_name': vehicle_name,
            'vehicle_number': vehicle_number,
            'page_name': 'transport',
        }

        return request.render("university_management.student_transport", values)