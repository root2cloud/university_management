# -*- coding: utf-8 -*-
"""Schedule / calendar / syllabus pages for the student and faculty portals."""
import base64
import logging
from datetime import timedelta
from urllib.parse import quote

from odoo import http, fields, _
from odoo.http import request

from . import schedule_utils as su

_logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _student_courses(env, student):
    Course = env['university.course'].sudo()
    courses = su.student_slots(env, student).mapped('course_id')
    enrolled = Course.search([('student_ids', 'in', [student.id])]).filtered(
        lambda c: not c.semester_id or c.semester_id.semester_number == student.current_semester)
    return (courses | enrolled).filtered('active')


def _faculty_courses(env, faculty):
    Course = env['university.course'].sudo()
    courses = su.faculty_slots(env, faculty).mapped('course_id')
    courses |= Course.search(['|', ('faculty_id', '=', faculty.id), ('co_faculty_ids', 'in', [faculty.id])])
    subs = env['timetable.substitution'].sudo().search([
        ('substitute_faculty_id', '=', faculty.id), ('state', 'in', su.SUB_STATES)])
    courses |= subs.mapped('timetable_id.course_id')
    return courses.filtered('active')


_attach_progress = su.attach_progress


def _json(payload, status=200):
    return request.make_json_response(payload, status=status)


# ======================================================================
# STUDENT
# ======================================================================
class StudentSchedulePortal(http.Controller):

    def _student(self):
        return su.get_student(request.env)

    @http.route(['/my/schedule'], type='http', auth='user', website=True)
    def student_schedule(self, **kw):
        student = self._student()
        if not student:
            return request.redirect('/my')
        env = request.env
        nn = su.student_now_next(env, student)
        _attach_progress(env, [nn['current'], nn['next']] + nn['today'])
        courses = _student_courses(env, student)
        Log = env['syllabus.coverage.log'].sudo()
        overall = [Log.get_course_progress(c)['overall'] for c in courses]
        return request.render('university_management.student_schedule', {
            'student': student, 'nn': nn, 'page_name': 'student_schedule',
            'events_url': '/my/student/calendar/events',
            'ics_url': '/my/student/schedule.ics',
            'avg_progress': int(round(sum(overall) / len(overall))) if overall else 0,
            'subject_count': len(courses),
            'today_iso': nn['now'].date().isoformat(),
            'role': 'student',
        })

    @http.route(['/my/student/calendar/events'], type='http', auth='user', methods=['GET'], website=True)
    def student_calendar_events(self, start=None, end=None, **kw):
        student = self._student()
        if not student:
            return _json({'error': 'not_a_student'}, 403)
        today = su.local_now(request.env).date()
        d_from, d_to = su.parse_range(start, end, today)
        return _json({'events': su.build_student_events(request.env, student, d_from, d_to),
                      'today': today.isoformat()})

    @http.route(['/my/student/schedule.ics'], type='http', auth='user', website=True)
    def student_schedule_ics(self, **kw):
        student = self._student()
        if not student:
            return request.redirect('/my')
        today = su.local_now(request.env).date()
        events = su.build_student_events(request.env, student, today - timedelta(days=7),
                                         today + timedelta(days=120), extras=False)
        ics = su.build_ics(request.env, events, 'My Class Schedule')
        return request.make_response(ics, headers=[
            ('Content-Type', 'text/calendar; charset=utf-8'),
            ('Content-Disposition', 'attachment; filename="class_schedule.ics"')])

    # ---------------- syllabus ----------------
    @http.route(['/my/syllabus'], type='http', auth='user', website=True)
    def student_syllabus(self, **kw):
        student = self._student()
        if not student:
            return request.redirect('/my')
        env = request.env
        Log = env['syllabus.coverage.log'].sudo()
        rows = []
        for course in _student_courses(env, student).sorted(lambda c: c.subject_id.name or c.name):
            data = Log.get_course_progress(course)
            teachers = env['university.timetable'].sudo().search(
                [('course_id', '=', course.id), ('active', '=', True)]).mapped('faculty_id.name')
            rows.append({'course': course, 'data': data,
                         'teachers': ', '.join(sorted(set(teachers)))})
        overall = [r['data']['overall'] for r in rows]
        return request.render('university_management.student_syllabus', {
            'student': student, 'rows': rows, 'page_name': 'student_syllabus',
            'avg_progress': int(round(sum(overall) / len(overall))) if overall else 0,
        })

    @http.route(['/my/syllabus/<int:course_id>'], type='http', auth='user', website=True)
    def student_syllabus_detail(self, course_id, **kw):
        student = self._student()
        if not student:
            return request.redirect('/my')
        env = request.env
        courses = _student_courses(env, student)
        course = courses.filtered(lambda c: c.id == course_id)
        if not course:
            return request.redirect('/my/syllabus')
        data = env['syllabus.coverage.log'].sudo().get_course_progress(course)
        teachers = env['university.timetable'].sudo().search(
            [('course_id', '=', course.id), ('active', '=', True)]).mapped('faculty_id.name')
        return request.render('university_management.student_syllabus_detail', {
            'student': student, 'course': course, 'data': data,
            'syllabus': data['syllabus'], 'teachers': ', '.join(sorted(set(teachers))),
            'page_name': 'student_syllabus',
        })


# ======================================================================
# FACULTY
# ======================================================================
class FacultySchedulePortal(http.Controller):

    def _faculty(self):
        return su.get_faculty(request.env)

    @http.route(['/my/faculty/schedule'], type='http', auth='user', website=True)
    def faculty_schedule(self, **kw):
        faculty = self._faculty()
        if not faculty:
            return request.redirect('/my')
        env = request.env
        nn = su.faculty_now_next(env, faculty)
        _attach_progress(env, [nn['current'], nn['next']] + nn['today'])
        courses = _faculty_courses(env, faculty)
        Log = env['syllabus.coverage.log'].sudo()
        overall = [Log.get_course_progress(c)['overall'] for c in courses]
        today = nn['now'].date()
        pending = Log.search_count([('faculty_id', '=', faculty.id), ('date', '=', today)])
        return request.render('university_management.faculty_schedule', {
            'faculty': faculty, 'nn': nn, 'page_name': 'faculty_schedule',
            'events_url': '/my/faculty/calendar/events',
            'ics_url': '/my/faculty/schedule.ics',
            'avg_progress': int(round(sum(overall) / len(overall))) if overall else 0,
            'subject_count': len(courses),
            'logged_today': pending,
            'today_iso': today.isoformat(),
            'role': 'faculty',
        })

    @http.route(['/my/faculty/calendar/events'], type='http', auth='user', methods=['GET'], website=True)
    def faculty_calendar_events(self, start=None, end=None, **kw):
        faculty = self._faculty()
        if not faculty:
            return _json({'error': 'not_a_faculty'}, 403)
        today = su.local_now(request.env).date()
        d_from, d_to = su.parse_range(start, end, today)
        return _json({'events': su.build_faculty_events(request.env, faculty, d_from, d_to),
                      'today': today.isoformat()})

    @http.route(['/my/faculty/schedule.ics'], type='http', auth='user', website=True)
    def faculty_schedule_ics(self, **kw):
        faculty = self._faculty()
        if not faculty:
            return request.redirect('/my')
        today = su.local_now(request.env).date()
        events = su.build_faculty_events(request.env, faculty, today - timedelta(days=7),
                                         today + timedelta(days=120), extras=False)
        ics = su.build_ics(request.env, events, 'My Teaching Schedule')
        return request.make_response(ics, headers=[
            ('Content-Type', 'text/calendar; charset=utf-8'),
            ('Content-Disposition', 'attachment; filename="teaching_schedule.ics"')])

    # ---------------- syllabus tracking ----------------
    @http.route(['/my/faculty/syllabus'], type='http', auth='user', website=True)
    def faculty_syllabus(self, **kw):
        faculty = self._faculty()
        if not faculty:
            return request.redirect('/my')
        env = request.env
        Log = env['syllabus.coverage.log'].sudo()
        today = su.local_now(env).date()
        today_courses = {e['course_id'] for e in su.build_faculty_events(env, faculty, today, today, extras=False)
                         if e['kind'] == 'class' and not e['cancelled']}
        logged_today = set(Log.search([('faculty_id', '=', faculty.id), ('date', '=', today)]).mapped('course_id').ids)
        rows = []
        for course in _faculty_courses(env, faculty).sorted(lambda c: c.subject_id.name or c.name):
            data = Log.get_course_progress(course)
            rows.append({
                'course': course, 'data': data,
                'teaching_today': course.id in today_courses,
                'logged_today': course.id in logged_today,
            })
        overall = [r['data']['overall'] for r in rows]
        return request.render('university_management.faculty_syllabus', {
            'faculty': faculty, 'rows': rows, 'page_name': 'faculty_syllabus',
            'avg_progress': int(round(sum(overall) / len(overall))) if overall else 0,
        })

    @http.route(['/my/faculty/syllabus/<int:course_id>'], type='http', auth='user', website=True)
    def faculty_syllabus_detail(self, course_id, saved=None, error=None, **kw):
        faculty = self._faculty()
        if not faculty:
            return request.redirect('/my')
        env = request.env
        course = _faculty_courses(env, faculty).filtered(lambda c: c.id == course_id)
        if not course:
            return request.redirect('/my/faculty/syllabus')
        Log = env['syllabus.coverage.log'].sudo()
        data = Log.get_course_progress(course)
        logs = Log.search([('course_id', '=', course.id)], limit=40)
        slots = su.faculty_slots(env, faculty).filtered(lambda t: t.course_id.id == course.id)
        slot_rows = [{'id': t.id, 'label': '%s %s – %s' % (
            su.WEEKDAYS[int(t.day_of_week)][:3], su.float_to_label(t.start_time), su.float_to_label(t.end_time))}
            for t in slots]
        today = su.local_now(env).date()
        return request.render('university_management.faculty_syllabus_detail', {
            'faculty': faculty, 'course': course, 'data': data, 'syllabus': data['syllabus'],
            'logs': logs, 'slots': slot_rows, 'today_iso': today.isoformat(),
            'default_unit_id': data['next_unit']['id'] if data['next_unit'] else 0,
            'saved': bool(saved), 'error': error or '',
            'page_name': 'faculty_syllabus',
        })

    @http.route(['/my/faculty/syllabus/log'], type='http', auth='user', methods=['POST'],
                website=True, csrf=True)
    def faculty_syllabus_log(self, **post):
        faculty = self._faculty()
        if not faculty:
            return request.redirect('/my')
        env = request.env
        try:
            course_id = int(post.get('course_id') or 0)
        except ValueError:
            course_id = 0
        course = _faculty_courses(env, faculty).filtered(lambda c: c.id == course_id)
        if not course:
            return request.redirect('/my/faculty/syllabus')
        back = '/my/faculty/syllabus/%d' % course.id

        def fail(msg):
            return request.redirect('%s?error=%s' % (back, quote(msg)))

        Log = env['syllabus.coverage.log'].sudo()
        syllabus = Log._get_course_syllabus(course)
        try:
            unit = syllabus.unit_ids.filtered(lambda u: u.id == int(post.get('unit_id') or 0))
        except ValueError:
            unit = syllabus.unit_ids.browse()
        topics = (post.get('topics_covered') or '').strip()
        if not unit:
            return fail(_('Please select a unit.'))
        if not topics:
            return fail(_('Please describe the topics covered.'))
        try:
            log_date = fields.Date.from_string(post.get('date') or '')
        except Exception:
            log_date = None
        if not log_date:
            return fail(_('Please choose a valid date.'))
        try:
            percent = max(0, min(100, int(post.get('completion_percent') or 0)))
        except ValueError:
            percent = 0
        tt = env['university.timetable'].sudo().browse(int(post.get('timetable_id') or 0)).exists() \
            if (post.get('timetable_id') or '').isdigit() else env['university.timetable']
        own_course = course in su.faculty_slots(env, faculty).mapped('course_id')
        try:
            Log.create({
                'course_id': course.id, 'syllabus_id': syllabus.id, 'unit_id': unit.id,
                'faculty_id': faculty.id, 'date': log_date,
                'timetable_id': tt.id if tt and tt.course_id == course else False,
                'start_time': tt.start_time if tt and tt.course_id == course else 0.0,
                'end_time': tt.end_time if tt and tt.course_id == course else 0.0,
                'is_substitution': not own_course,
                'topics_covered': topics, 'completion_percent': percent,
                'unit_completed': bool(post.get('unit_completed')),
                'remarks': (post.get('remarks') or '').strip(),
            })
        except Exception as exc:  # validation errors etc.
            _logger.info('Syllabus log failed: %s', exc)
            return fail(getattr(exc, 'name', None) or str(exc))
        return request.redirect('%s?saved=1' % back)

    @http.route(['/my/faculty/syllabus/log/<int:log_id>/delete'], type='http', auth='user',
                methods=['POST'], website=True, csrf=True)
    def faculty_syllabus_log_delete(self, log_id, **post):
        faculty = self._faculty()
        if not faculty:
            return request.redirect('/my')
        log = request.env['syllabus.coverage.log'].sudo().browse(log_id).exists()
        if log and log.faculty_id == faculty:
            course_id = log.course_id.id
            log.unlink()
            return request.redirect('/my/faculty/syllabus/%d' % course_id)
        return request.redirect('/my/faculty/syllabus')


# ======================================================================
# FACULTY PHOTO (small round avatar used on the calendar chips)
# ======================================================================
class SchedulePhotoPortal(http.Controller):

    @http.route(['/my/schedule/faculty-photo/<int:faculty_id>'], type='http', auth='user')
    def faculty_photo(self, faculty_id, **kw):
        faculty = request.env['faculty.faculty'].sudo().browse(faculty_id).exists()
        image = faculty.employee_id.image_128 if faculty else False
        if not image:
            return request.not_found()
        content = base64.b64decode(image)
        return request.make_response(content, headers=[
            ('Content-Type', 'image/png'),
            ('Content-Length', str(len(content))),
            ('Cache-Control', 'private, max-age=3600'),
        ])