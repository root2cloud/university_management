# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import random
import logging

_logger = logging.getLogger(__name__)


class QuestionPaper(models.Model):
    """
    Auto-generated question paper from one or more theory question banks.
    The system picks questions according to the configured rules
    (unit coverage, marks distribution, RBT mix, etc.) and renders the
    final printable PDF.
    """
    _name = 'exam.question.paper'
    _description = 'Question Paper'
    _inherit = ['mail.thread.main.attachment', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Paper Title', required=True, tracking=True)
    code = fields.Char(
        string='Paper Code', required=True, copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('exam.question.paper') or 'NEW',
    )

    # Linkage
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     tracking=True)
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 required=True, tracking=True, index=True)
    department_id = fields.Many2one('university.department', string='Department')
    semester_id = fields.Many2one('university.semester', string='Semester')
    regulation = fields.Char(string='Regulation', default='R23', help='e.g. R20, R22, R23 — printed top-right')

    # Source banks
    bank_ids = fields.Many2many('exam.theory.question.bank',
                                'question_paper_bank_rel',
                                'paper_id', 'bank_id',
                                string='Source Question Banks')

    # ------------------------------------------------------------------
    # Header fields — these map directly onto the printed letterhead, e.g.
    #   R23EEE-PC3103                                                R23
    #   LENDI INSTITUTE OF ENGINEERING &TECHNOLOGY (AUTONOMOUS)
    #   Permanently Affiliated to JNTUGV, Vizianagaram
    #   Jonnada: Vizianagaram
    #   III B. Tech, I-Semester Regular Examinations, December 2025
    #   Power Systems-II
    #   (EEE)
    #   Date: 12-12-2025        Time: 3 Hours.        Max. Marks: 70
    # ------------------------------------------------------------------
    subject_code = fields.Char(string='Paper Code', help='e.g. R23EEE-PC3103 — printed top-left')
    affiliation_line = fields.Char(string='Affiliation Line', default='Permanently Affiliated to JNTUGV, Vizianagaram')
    location_line = fields.Char(string='Location Line', default='Jonnada: Vizianagaram')
    exam_session = fields.Char(string='Class / Session Line',
                               help='e.g. "III B. Tech, I-Semester Regular Examinations, December 2025"')
    branch_short = fields.Char(string='Branch (Short)', help='e.g. EEE — printed under the subject name')
    exam_date = fields.Date(string='Exam Date')

    # Paper configuration
    total_marks = fields.Integer(string='Total Marks', required=True, default=70)
    duration_minutes = fields.Integer(string='Duration (minutes)', default=180)
    number_of_questions = fields.Integer(string='Number of Questions', default=10)

    paper_pattern = fields.Selection([
        ('r23', 'R23 - Part A (10 x 2M) + Part B (5 Units, Either/Or)'),
        ('r20', 'R20 - Part A (Objective) + Part B (Descriptive)'),
        ('r22', 'R22 - 10 Questions (Either/Or)'),
        ('custom', 'Custom Pattern'),
    ], string='Paper Pattern', default='r23', required=True)

    # Part-A config
    part_a_questions = fields.Integer(string='Part-A Questions', default=10,
                                      help='Short-answer questions (lettered A–J), spread evenly across units')
    part_a_marks_each = fields.Integer(string='Part-A Marks Each', default=2)
    # Part-B config
    part_b_questions = fields.Integer(string='Part-B Questions', default=5,
                                      help='Number of units covered — one either/or pair per unit')
    part_b_marks_each = fields.Integer(string='Part-B Marks Each', default=10,
                                       help='Total marks for one full Part-B question (split across its A)/B) sub-parts)')

    # Generated questions
    paper_question_ids = fields.One2many('exam.question.paper.line', 'paper_id',
                                        string='Paper Questions')
    question_line_count = fields.Integer(string='Questions', compute='_compute_line_counts')
    bank_count = fields.Integer(string='Source Banks', compute='_compute_line_counts')

    # PDF output
    paper_pdf = fields.Binary(string='Question Paper PDF', attachment=True, readonly=True)
    paper_pdf_filename = fields.Char(string='PDF Filename')
    main_paper_attachment_id = fields.Many2one('ir.attachment', copy=False)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('approved', 'Approved'),
        ('locked', 'Locked / Printed'),
    ], string='Status', default='draft', tracking=True)

    instructions = fields.Html(string='Instructions to Candidates')

    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Paper Code must be unique!'),
    ]

    @api.depends('paper_question_ids', 'bank_ids')
    def _compute_line_counts(self):
        for rec in self:
            rec.question_line_count = len(rec.paper_question_ids)
            rec.bank_count = len(rec.bank_ids)

    def action_view_paper_questions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Paper Questions'),
            'res_model': 'exam.question.paper.line',
            'view_mode': 'list,form',
            'domain': [('paper_id', '=', self.id)],
        }

    def action_view_source_banks(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Source Question Banks'),
            'res_model': 'exam.theory.question.bank',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.bank_ids.ids)],
        }

    # ------------------------------------------------------------------
    # Auto-generation logic
    # ------------------------------------------------------------------
    def action_generate_paper(self):
        """
        Auto-pick questions from linked banks based on pattern,
        ensuring unit coverage and marks distribution, then render the PDF.
        """
        self.ensure_one()
        if not self.bank_ids:
            raise ValidationError(_('Please select at least one source question bank.'))

        all_questions = self.env['exam.theory.question'].search([
            ('bank_id', 'in', self.bank_ids.ids),
        ])
        if not all_questions:
            raise ValidationError(_('No questions found in the selected banks.'))

        # Clear existing lines
        self.paper_question_ids.unlink()

        if self.paper_pattern == 'r23':
            lines = self._generate_r23(all_questions)
        elif self.paper_pattern == 'r22':
            lines = self._generate_r22(all_questions)
        elif self.paper_pattern == 'r20':
            lines = self._generate_r20(all_questions)
        else:
            lines = self._generate_custom(all_questions)

        for seq, line_vals in enumerate(lines, 1):
            line_vals.update({
                'paper_id': self.id,
                'sequence': seq,
            })
            self.env['exam.question.paper.line'].create(line_vals)

        # Increment usage count
        used_q_ids = [l['question_id'] for l in lines if l.get('question_id')]
        for q in self.env['exam.theory.question'].browse(used_q_ids):
            q.used_count += 1

        self.state = 'generated'
        self._generate_pdf()

    def _units_sorted(self, questions, limit=5):
        units = sorted({u for u in questions.mapped('unit') if u})
        return units[:limit]

    def _pick(self, pool, count):
        """Random sample of `count` from pool, padding by repeating the
        available ones if the bank doesn't have enough distinct questions."""
        pool = list(pool)
        if not pool:
            return []
        if len(pool) >= count:
            return random.sample(pool, count)
        picked = list(pool)
        while len(picked) < count:
            picked.append(random.choice(pool))
        return picked

    # ------------------------------------------------------------------
    # R23 pattern — matches the live Lendi format:
    #   PART-A [20 MARKS] — one question "1." with 10 lettered sub-parts
    #     (A-J), 2 marks each, 2 letters drawn from each of the 5 units.
    #   PART-B [50 MARKS] — 5 units, 2 full questions per unit (numbered
    #     consecutively 1-10 across the whole paper), each full question
    #     has two lettered sub-parts A)/B), 5 marks each (10 total),
    #     student answers ONE full question per unit.
    # ------------------------------------------------------------------
    def _generate_r23(self, questions):
        lines = []
        units = self._units_sorted(questions, limit=self.part_b_questions or 5)
        if not units:
            raise ValidationError(_('None of the selected questions have a Unit set. '
                                     'Import / tag questions with UNIT-1, UNIT-2 … first.'))

        # ---- PART A ----
        letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        per_unit = max(1, (self.part_a_questions or 10) // len(units))
        letter_idx = 0
        for unit in units:
            candidates = questions.filtered(
                lambda q, u=unit: q.unit == u and q.marks == self.part_a_marks_each)
            if not candidates:
                candidates = questions.filtered(lambda q, u=unit: q.unit == u)
            picked = self._pick(candidates, per_unit)
            for q in picked:
                lines.append({
                    'question_number': '1',
                    'sub_part': letters[letter_idx] if letter_idx < len(letters) else str(letter_idx + 1),
                    'question_id': q.id,
                    'marks': self.part_a_marks_each,
                    'part': 'part_a',
                })
                letter_idx += 1

        # ---- PART B ----
        sub_marks = max(1, (self.part_b_marks_each or 10) // 2)
        q_no = 1
        for unit in units:
            candidates = questions.filtered(
                lambda q, u=unit: q.unit == u and q.marks == sub_marks)
            if len(candidates) < 4:
                candidates = questions.filtered(lambda q, u=unit: q.unit == u)
            picked = self._pick(candidates, 4)
            # Two full questions per unit (either/or), each with A)/B) sub-parts
            for full_q in range(2):
                for sub_letter, q in zip(('A', 'B'), picked[full_q * 2: full_q * 2 + 2]):
                    lines.append({
                        'question_number': str(q_no),
                        'sub_part': sub_letter,
                        'question_id': q.id,
                        'marks': sub_marks,
                        'part': 'part_b',
                    })
                q_no += 1

        return lines

    def _generate_r22(self, questions):
        """R22 pattern: 5 units × 2 questions each = 10 questions (either/or)."""
        units = self._units_sorted(questions)

        lines = []
        q_no = 1
        for unit in units:
            unit_qs = questions.filtered(lambda q: q.unit == unit)
            picked = self._pick(unit_qs, 2)
            if not picked:
                continue
            lines.append({
                'question_number': str(q_no),
                'sub_part': 'A',
                'question_id': picked[0].id,
                'marks': picked[0].marks,
                'part': 'main',
            })
            if len(picked) > 1:
                lines.append({
                    'question_number': str(q_no),
                    'sub_part': 'B (OR)',
                    'question_id': picked[1].id,
                    'marks': picked[1].marks,
                    'part': 'main',
                })
            q_no += 1

        return lines

    def _generate_r20(self, questions):
        """R20 pattern: Part-A short + Part-B long descriptive."""
        lines = []
        short_qs = questions.filtered(lambda q: q.marks <= self.part_a_marks_each)
        long_qs = questions.filtered(lambda q: q.marks > self.part_a_marks_each)

        picked_a = self._pick(short_qs or questions, self.part_a_questions)
        for i, q in enumerate(picked_a, 1):
            lines.append({
                'question_number': str(i),
                'sub_part': '',
                'question_id': q.id,
                'marks': self.part_a_marks_each,
                'part': 'part_a',
            })

        picked_b = self._pick(long_qs or questions, self.part_b_questions * 2)
        q_no = 1
        for i in range(0, len(picked_b), 2):
            lines.append({
                'question_number': str(q_no),
                'sub_part': 'A',
                'question_id': picked_b[i].id,
                'marks': self.part_b_marks_each,
                'part': 'part_b',
            })
            if i + 1 < len(picked_b):
                lines.append({
                    'question_number': str(q_no),
                    'sub_part': 'B (OR)',
                    'question_id': picked_b[i + 1].id,
                    'marks': self.part_b_marks_each,
                    'part': 'part_b',
                })
            q_no += 1

        return lines

    def _generate_custom(self, questions):
        """Custom: just pick N random questions up to total marks."""
        picked = self._pick(questions, self.number_of_questions)
        lines = []
        for i, q in enumerate(picked, 1):
            lines.append({
                'question_number': str(i),
                'sub_part': '',
                'question_id': q.id,
                'marks': q.marks,
                'part': 'main',
            })
        return lines

    # ------------------------------------------------------------------
    # PDF rendering
    # ------------------------------------------------------------------
    def _generate_pdf(self):
        self.ensure_one()
        report = self.env.ref('university_management.action_report_question_paper')
        pdf_content, _fmt = report._render_qweb_pdf(
            'university_management.report_question_paper', self.ids)
        filename = '%s.pdf' % (self.code or self.name or 'Question_Paper')
        self.write({
            'paper_pdf': base64.b64encode(pdf_content),
            'paper_pdf_filename': filename,
        })
        self._set_main_attachment_from_paper_pdf(pdf_content, filename)

    def _set_main_attachment_from_paper_pdf(self, pdf_content, filename):
        """Wrap the generated PDF as a real ir.attachment and point
        message_main_attachment_id at it, the same way exam.omr.scanner
        does for its uploaded sheet, so o_attachment_preview shows the
        paper right after Auto-Generate / Regenerate.
        """
        self.ensure_one()
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(pdf_content),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        self.message_main_attachment_id = attachment.id
        self.main_paper_attachment_id = attachment.id

    def action_print_pdf(self):
        self.ensure_one()
        if not self.paper_pdf:
            self._generate_pdf()
        return self.env.ref('university_management.action_report_question_paper').report_action(self)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_lock(self):
        self.write({'state': 'locked'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class QuestionPaperLine(models.Model):
    _name = 'exam.question.paper.line'
    _description = 'Question Paper Line'
    _order = 'part, sequence'

    paper_id = fields.Many2one('exam.question.paper', ondelete='cascade',
                               required=True, index=True)
    sequence = fields.Integer(default=10)

    question_number = fields.Char(string='Q.No')
    sub_part = fields.Char(string='Sub Part')

    question_id = fields.Many2one('exam.theory.question', string='Question')
    question_text = fields.Text(related='question_id.question_text',
                                string='Question Text')
    question_image = fields.Binary(related='question_id.question_image', string='Question Image')

    marks = fields.Integer(string='Marks')
    co_level = fields.Char(related='question_id.co_level', string='CO')
    rbt_level = fields.Selection(related='question_id.rbt_level', string='RBT')
    rbt_display = fields.Char(compute='_compute_rbt_display', string='RBT (Print)')
    unit = fields.Char(related='question_id.unit', string='Unit')

    _RBT_PRINT_MAP = {
        'remembering': 'Remember',
        'understanding': 'Understand',
        'applying': 'Apply',
        'analyzing': 'Analyze',
        'evaluating': 'Evaluate',
        'creating': 'Create',
    }

    @api.depends('rbt_level')
    def _compute_rbt_display(self):
        for rec in self:
            rec.rbt_display = rec._RBT_PRINT_MAP.get(rec.rbt_level, rec.rbt_level or '')

    part = fields.Selection([
        ('part_a', 'Part A'),
        ('part_b', 'Part B'),
        ('main', 'Main'),
    ], string='Part', default='main')