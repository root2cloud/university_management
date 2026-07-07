# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import http, fields, _
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class OnlineExamController(http.Controller):
    """
    Student-facing portal controller for Online Exam / MCQ module.

    Routes
    ------
    GET  /my/exams                               — list of available online exams
    GET  /my/exam/<id>                           — exam landing / instructions page
    POST /my/exam/<id>/start                     — create attempt, redirect to first question
    GET  /my/exam/attempt/<id>/q/<n>             — render question n (1-based)
    POST /my/exam/attempt/<id>/answer            — save response, go to next question
    POST /my/exam/attempt/<id>/flag/<n>          — toggle flag on question n
    POST /my/exam/attempt/<id>/submit            — submit attempt
    GET  /my/exam/attempt/<id>/result            — result page
    """

    # ------------------------------------------------------------------ helpers

    def _get_student(self):
        return request.env['student.student'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1
        )

    def _get_attempt_or_404(self, attempt_id):
        attempt = request.env['online.exam.attempt'].sudo().browse(attempt_id)
        if not attempt.exists():
            return None
        student = self._get_student()
        if attempt.student_id.id != student.id:
            return None
        return attempt

    def _check_expired(self, attempt):
        """Auto-expire and submit if time is up."""
        if attempt.state == 'in_progress' and attempt.is_expired():
            attempt.action_submit()
            return True
        return False

    def _ordered_questions(self, attempt):
        """Return the question list used for this attempt (ordered by response.sequence)."""
        responses = attempt.response_ids.sorted('sequence')
        return [r.question_id for r in responses]

    # ------------------------------------------------------------------ list

    @http.route('/my/exams', type='http', auth='user', website=True)
    def exam_list(self, **kw):
        student = self._get_student()
        if not student:
            return request.redirect('/my')

        now = fields.Datetime.now()
        exams = request.env['online.exam'].sudo().search([
            ('state', 'in', ('published', 'ongoing')),
            ('start_datetime', '<=', now),
            ('end_datetime', '>=', now),
        ])

        # Filter to student's programs/batches
        available = exams.filtered(
            lambda e: (
                not e.program_ids or student.program_id in e.program_ids
            ) and (
                not e.batch_ids or student.batch_id in e.batch_ids
            )
        )

        # Attach attempt info per exam
        exam_data = []
        for exam in available:
            existing = request.env['online.exam.attempt'].sudo().search([
                ('online_exam_id', '=', exam.id),
                ('student_id', '=', student.id),
            ], order='id desc', limit=1)
            exam_data.append({
                'exam': exam,
                'attempt': existing,
            })

        return request.render('university_management.online_exam_list', {
            'student': student,
            'exam_data': exam_data,
            'page_name': 'online_exams',
        })

    # ------------------------------------------------------------------ instructions

    @http.route('/my/exam/<int:exam_id>', type='http', auth='user', website=True)
    def exam_instructions(self, exam_id, **kw):
        student = self._get_student()
        if not student:
            return request.redirect('/my')

        exam = request.env['online.exam'].sudo().browse(exam_id)
        if not exam.exists() or exam.state not in ('published', 'ongoing'):
            return request.redirect('/my/exams')

        now = fields.Datetime.now()
        if now < exam.start_datetime or now > exam.end_datetime:
            return request.redirect('/my/exams')

        existing_attempts = request.env['online.exam.attempt'].sudo().search([
            ('online_exam_id', '=', exam.id),
            ('student_id', '=', student.id),
        ])

        # Check if student has an in-progress attempt
        in_progress = existing_attempts.filtered(lambda a: a.state == 'in_progress')
        if in_progress:
            return request.redirect(f'/my/exam/attempt/{in_progress[0].id}/q/1')

        can_start = True
        if not exam.allow_multiple_attempts and existing_attempts:
            can_start = False

        return request.render('university_management.online_exam_instructions', {
            'student': student,
            'exam': exam,
            'existing_attempts': existing_attempts,
            'can_start': can_start,
            'page_name': 'online_exam',
        })

    # ------------------------------------------------------------------ start

    @http.route('/my/exam/<int:exam_id>/start', type='http', auth='user',
                website=True, methods=['POST'])
    def exam_start(self, exam_id, **kw):
        student = self._get_student()
        if not student:
            return request.redirect('/my')

        exam = request.env['online.exam'].sudo().browse(exam_id)
        if not exam.exists() or exam.state not in ('published', 'ongoing'):
            return request.redirect('/my/exams')

        now = fields.Datetime.now()
        if now < exam.start_datetime or now > exam.end_datetime:
            return request.redirect('/my/exams')

        # Guard multiple attempts
        existing = request.env['online.exam.attempt'].sudo().search([
            ('online_exam_id', '=', exam.id),
            ('student_id', '=', student.id),
            ('state', '=', 'in_progress'),
        ], limit=1)
        if existing:
            return request.redirect(f'/my/exam/attempt/{existing.id}/q/1')

        if not exam.allow_multiple_attempts:
            done = request.env['online.exam.attempt'].sudo().search([
                ('online_exam_id', '=', exam.id),
                ('student_id', '=', student.id),
                ('state', 'in', ('submitted', 'evaluated')),
            ], limit=1)
            if done:
                return request.redirect(f'/my/exam/attempt/{done.id}/result')

        expiry = now + timedelta(minutes=exam.duration_minutes)

        attempt = request.env['online.exam.attempt'].sudo().create({
            'online_exam_id': exam.id,
            'student_id': student.id,
            'start_datetime': now,
            'expiry_datetime': expiry,
            'state': 'in_progress',
            'ip_address': request.httprequest.remote_addr,
        })

        # Pre-create response stubs in shuffled/ordered question sequence
        questions = exam.get_questions_for_student()
        for seq, question in enumerate(questions, start=1):
            request.env['online.exam.response'].sudo().create({
                'attempt_id': attempt.id,
                'question_id': question.id,
                'sequence': seq,
                'is_skipped': True,
            })

        return request.redirect(f'/my/exam/attempt/{attempt.id}/q/1')

    # ------------------------------------------------------------------ question

    @http.route('/my/exam/attempt/<int:attempt_id>/q/<int:q_no>',
                type='http', auth='user', website=True)
    def exam_question(self, attempt_id, q_no, **kw):
        student = self._get_student()
        attempt = self._get_attempt_or_404(attempt_id)
        if not attempt or not student:
            return request.redirect('/my/exams')

        if self._check_expired(attempt):
            return request.redirect(f'/my/exam/attempt/{attempt_id}/result')

        if attempt.state in ('submitted', 'evaluated', 'expired'):
            return request.redirect(f'/my/exam/attempt/{attempt_id}/result')

        questions = self._ordered_questions(attempt)
        total = len(questions)
        if q_no < 1 or q_no > total:
            q_no = 1

        question = questions[q_no - 1]
        response = attempt.response_ids.filtered(
            lambda r: r.question_id.id == question.id
        )[:1]

        # Shuffle options if configured
        options = list(question.option_ids)
        if attempt.online_exam_id.shuffle_options:
            import random
            random.shuffle(options)

        # Remaining seconds
        remaining_seconds = None
        if attempt.expiry_datetime:
            delta = attempt.expiry_datetime - fields.Datetime.now()
            remaining_seconds = max(0, int(delta.total_seconds()))

        return request.render('university_management.online_exam_question', {
            'student': student,
            'attempt': attempt,
            'exam': attempt.online_exam_id,
            'question': question,
            'options': options,
            'response': response,
            'q_no': q_no,
            'total': total,
            'questions': questions,
            'responses': attempt.response_ids.sorted('sequence'),
            'remaining_seconds': remaining_seconds,
            'page_name': 'online_exam',
        })

    # ------------------------------------------------------------------ answer

    @http.route('/my/exam/attempt/<int:attempt_id>/answer',
                type='http', auth='user', website=True, methods=['POST'])
    def exam_answer(self, attempt_id, **post):
        student = self._get_student()
        attempt = self._get_attempt_or_404(attempt_id)
        if not attempt or not student:
            return request.redirect('/my/exams')

        if self._check_expired(attempt):
            return request.redirect(f'/my/exam/attempt/{attempt_id}/result')

        if attempt.state != 'in_progress':
            return request.redirect(f'/my/exam/attempt/{attempt_id}/result')

        q_no = int(post.get('q_no', 1))
        action = post.get('action', 'next')  # next | prev | goto | flag
        questions = self._ordered_questions(attempt)
        total = len(questions)

        if 1 <= q_no <= total:
            question = questions[q_no - 1]
            response = attempt.response_ids.filtered(
                lambda r: r.question_id.id == question.id
            )[:1]

            vals = {'is_skipped': False}

            if question.question_type in ('mcq', 'true_false'):
                opt_id = post.get('option_id')
                if opt_id:
                    vals['selected_option_ids'] = [(6, 0, [int(opt_id)])]
                else:
                    vals['selected_option_ids'] = [(5, 0, 0)]
                    vals['is_skipped'] = True

            elif question.question_type == 'multi_select':
                opt_ids = post.getlist('option_ids') or []
                if opt_ids:
                    vals['selected_option_ids'] = [(6, 0, [int(i) for i in opt_ids])]
                else:
                    vals['selected_option_ids'] = [(5, 0, 0)]
                    vals['is_skipped'] = True

            elif question.question_type == 'short_answer':
                text = post.get('text_answer', '').strip()
                vals['text_answer'] = text
                vals['is_skipped'] = not text

            if response:
                response.sudo().write(vals)

        # Navigate
        next_q = q_no
        if action == 'next':
            next_q = min(q_no + 1, total)
        elif action == 'prev':
            next_q = max(q_no - 1, 1)
        elif action == 'goto':
            goto = int(post.get('goto_q', q_no))
            next_q = max(1, min(goto, total))

        return request.redirect(f'/my/exam/attempt/{attempt_id}/q/{next_q}')

    # ------------------------------------------------------------------ flag

    @http.route('/my/exam/attempt/<int:attempt_id>/flag/<int:q_no>',
                type='http', auth='user', website=True, methods=['POST'])
    def toggle_flag(self, attempt_id, q_no, **kw):
        attempt = self._get_attempt_or_404(attempt_id)
        if not attempt or attempt.state != 'in_progress':
            return request.redirect(f'/my/exam/attempt/{attempt_id}/q/{q_no}')

        questions = self._ordered_questions(attempt)
        if 1 <= q_no <= len(questions):
            question = questions[q_no - 1]
            response = attempt.response_ids.filtered(
                lambda r: r.question_id.id == question.id
            )[:1]
            if response:
                response.sudo().write({'is_flagged': not response.is_flagged})

        return request.redirect(f'/my/exam/attempt/{attempt_id}/q/{q_no}')

    # ------------------------------------------------------------------ submit

    @http.route('/my/exam/attempt/<int:attempt_id>/submit',
                type='http', auth='user', website=True, methods=['POST'])
    def exam_submit(self, attempt_id, **kw):
        student = self._get_student()
        attempt = self._get_attempt_or_404(attempt_id)
        if not attempt or not student:
            return request.redirect('/my/exams')

        if attempt.state == 'in_progress':
            attempt.sudo().action_submit()

        return request.redirect(f'/my/exam/attempt/{attempt_id}/result')

    # ------------------------------------------------------------------ result

    @http.route('/my/exam/attempt/<int:attempt_id>/result',
                type='http', auth='user', website=True)
    def exam_result(self, attempt_id, **kw):
        student = self._get_student()
        attempt = self._get_attempt_or_404(attempt_id)
        if not attempt or not student:
            return request.redirect('/my/exams')

        if attempt.state == 'in_progress':
            # Force-submit if somehow they land here
            attempt.sudo().action_submit()

        exam = attempt.online_exam_id
        show_result = exam.show_result_immediately or attempt.state in ('evaluated',)
        show_review = exam.allow_review and attempt.state == 'evaluated'

        responses = attempt.response_ids.sorted('sequence')

        return request.render('university_management.online_exam_result', {
            'student': student,
            'attempt': attempt,
            'exam': exam,
            'responses': responses,
            'show_result': show_result,
            'show_review': show_review,
            'page_name': 'online_exam',
        })