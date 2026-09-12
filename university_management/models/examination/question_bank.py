# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import re
import logging

_logger = logging.getLogger(__name__)

try:
    import docx
except ImportError:
    docx = None
    _logger.warning('python-docx is not installed. Question bank import will not work. '
                     'Install it with: pip install python-docx')

# Maps the free-text words used in the uploaded question bank documents to
# the selection keys used on exam.theory.question.
_RBT_MAP = {
    'remember': 'remembering', 'remembering': 'remembering',
    'understand': 'understanding', 'understanding': 'understanding',
    'apply': 'applying', 'applying': 'applying',
    'analyze': 'analyzing', 'analyse': 'analyzing', 'analyzing': 'analyzing', 'analysing': 'analyzing',
    'evaluate': 'evaluating', 'evaluating': 'evaluating',
    'create': 'creating', 'creating': 'creating',
}

_DIFFICULTY_MAP = {
    'easy': 'easy',
    'medium': 'medium',
    'moderate': 'medium',
    'hard': 'hard',
    'difficult': 'hard',
}

_UNIT_RE = re.compile(r'unit\s*[-:]?\s*(\d+)', re.IGNORECASE)


class TheoryQuestionBank(models.Model):
    """
    Theory / Descriptive Question Bank.
    Faculty upload questions organised by subject, unit, CO and RBT level.
    The system can then auto-generate question papers from these banks.
    """
    _name = 'exam.theory.question.bank'
    _description = 'Theory / Descriptive Question Bank'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Bank Name', required=True, tracking=True)
    code = fields.Char(
        string='Bank Code', required=True, copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('exam.theory.question.bank') or 'NEW',
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')

    # Academic linkage
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 required=True, index=True, tracking=True)
    department_id = fields.Many2one('university.department', string='Department',
                                   index=True, tracking=True)
    program_id = fields.Many2one('university.program', string='Program')
    semester_id = fields.Many2one('university.semester', string='Semester')
    regulation = fields.Char(string='Regulation', help='e.g. R20, R22, R23')

    # Faculty who created / owns the bank
    faculty_id = fields.Many2one('faculty.faculty', string='Created By (Faculty)',
                                 tracking=True)

    # Questions
    question_ids = fields.One2many('exam.theory.question', 'bank_id',
                                   string='Questions')
    question_count = fields.Integer(compute='_compute_question_count',
                                    string='Total Questions', store=True)
    easy_count = fields.Integer(compute='_compute_question_count', string='Easy', store=True)
    medium_count = fields.Integer(compute='_compute_question_count', string='Medium', store=True)
    hard_count = fields.Integer(compute='_compute_question_count', string='Hard', store=True)

    # Upload helper
    import_file = fields.Binary(string='Import Questions (.docx)',
                                attachment=False)
    import_filename = fields.Char(string='Import Filename')
    import_log = fields.Text(string='Last Import Result', readonly=True, copy=False)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True)

    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    _sql_constraints = [
        ('code_unique', 'unique(code)',
         'Question Bank Code must be unique!'),
    ]

    @api.depends('question_ids', 'question_ids.difficulty')
    def _compute_question_count(self):
        for rec in self:
            rec.question_count = len(rec.question_ids)
            rec.easy_count = len(rec.question_ids.filtered(lambda q: q.difficulty == 'easy'))
            rec.medium_count = len(rec.question_ids.filtered(lambda q: q.difficulty == 'medium'))
            rec.hard_count = len(rec.question_ids.filtered(lambda q: q.difficulty == 'hard'))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_submit_review(self):
        self.write({'state': 'review'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_questions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Questions'),
            'res_model': 'exam.theory.question',
            'view_mode': 'list,form',
            'domain': [('bank_id', '=', self.id)],
            'context': {'default_bank_id': self.id},
        }

    def action_view_easy(self):
        return self._action_view_by_difficulty('easy')

    def action_view_medium(self):
        return self._action_view_by_difficulty('medium')

    def action_view_hard(self):
        return self._action_view_by_difficulty('hard')

    def _action_view_by_difficulty(self, difficulty):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Questions'),
            'res_model': 'exam.theory.question',
            'view_mode': 'list,form',
            'domain': [('bank_id', '=', self.id), ('difficulty', '=', difficulty)],
            'context': {'default_bank_id': self.id},
        }

    # ------------------------------------------------------------------
    # Import / "OCR" — reads the uploaded .docx question bank and creates
    # exam.theory.question records from it. Uploaded question banks are
    # expected to look like the standard Lendi format: a paragraph reading
    # "UNIT-<n>" followed immediately by a table with columns
    # Q.No | Sub-part | Question Text | Marks | CO/RBT | RBT | Difficulty
    # ------------------------------------------------------------------
    def action_import_questions(self):
        self.ensure_one()
        if not docx:
            raise UserError(_(
                'python-docx is not installed on this server. Ask your administrator to run: '
                'pip install python-docx'))
        if not self.import_file:
            raise UserError(_('Please attach a .docx file first.'))
        if self.import_filename and not self.import_filename.lower().endswith('.docx'):
            raise UserError(_('Only .docx files are supported for import.'))

        try:
            file_content = base64.b64decode(self.import_file)
            document = docx.Document(io.BytesIO(file_content))
        except Exception as e:
            raise UserError(_('Could not read the uploaded file as a Word document: %s') % e)

        questions_by_unit = self._extract_questions_from_docx(document)

        total_found = sum(len(v) for v in questions_by_unit.values())
        if not total_found:
            raise UserError(_(
                'No questions could be found in this document. Make sure it has "UNIT-1", '
                '"UNIT-2" … paragraphs each followed by a table of questions, like the '
                'standard question bank format.'))

        # Replace whatever was there before with the freshly parsed content,
        # so re-importing a corrected file doesn't duplicate rows.
        self.question_ids.unlink()

        created = 0
        skipped = 0
        vals_list = []
        for unit, rows in questions_by_unit.items():
            for row in rows:
                if not row.get('question_text'):
                    skipped += 1
                    continue
                vals_list.append({
                    'bank_id': self.id,
                    'unit': unit,
                    'question_number': row.get('question_number'),
                    'sub_part': row.get('sub_part'),
                    'question_text': row.get('question_text'),
                    'marks': row.get('marks') or 1,
                    'co_level': row.get('co_level'),
                    'rbt_level': row.get('rbt_level') or 'understanding',
                    'difficulty': row.get('difficulty') or 'medium',
                })
        if vals_list:
            self.env['exam.theory.question'].create(vals_list)
            created = len(vals_list)

        self.import_log = _(
            '%(date)s — Imported %(created)s questions across %(units)s units from "%(file)s" '
            '(%(skipped)s empty rows skipped).'
        ) % {
            'date': fields.Datetime.now(),
            'created': created,
            'units': len(questions_by_unit),
            'file': self.import_filename or '',
            'skipped': skipped,
        }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import complete'),
                'message': _('%s questions imported from %s.') % (created, len(questions_by_unit)),
                'type': 'success',
                'sticky': False,
            },
        }

    def _extract_questions_from_docx(self, document):
        """Walk the document body in order so that each table can be
        associated with the UNIT-n heading that precedes it, then parse
        each table's rows into question dicts.

        Returns: {'UNIT-1': [ {question_number, sub_part, question_text,
                                marks, co_level, rbt_level, difficulty}, ... ], ...}
        """
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        body = document.element.body
        current_unit = None
        result = {}

        for child in body.iterchildren():
            tag = child.tag.rsplit('}', 1)[-1]
            if tag == 'p':
                para = Paragraph(child, document)
                text = para.text.strip()
                if text:
                    match = _UNIT_RE.search(text)
                    if match:
                        current_unit = 'UNIT-%s' % match.group(1)
                        result.setdefault(current_unit, [])
            elif tag == 'tbl':
                table = Table(child, document)
                if not current_unit:
                    # A table before any UNIT heading — skip, not part of the pattern.
                    continue
                rows = self._parse_question_table(table)
                result[current_unit].extend(rows)

        return result

    def _parse_question_table(self, table):
        rows_out = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if not cells or len(cells) < 4:
                continue
            first = cells[0].strip().lower()
            if first in ('q. no', 'q.no', 'qno', 's.no', 'sno', ''):
                # header / separator row
                if not any(c for c in cells[1:]):
                    continue
                if first in ('q. no', 'q.no', 'qno', 's.no', 'sno'):
                    continue

            q_no = cells[0].strip()
            sub_part = cells[1].strip() if len(cells) > 1 else ''
            question_text = cells[2].strip() if len(cells) > 2 else ''
            marks_raw = cells[3].strip() if len(cells) > 3 else ''
            co_rbt_raw = cells[4].strip() if len(cells) > 4 else ''
            rbt_raw = cells[5].strip() if len(cells) > 5 else ''
            difficulty_raw = cells[6].strip() if len(cells) > 6 else ''

            if not question_text:
                continue

            marks = None
            m = re.search(r'\d+', marks_raw)
            if m:
                marks = int(m.group())

            co_level = None
            rbt_text = rbt_raw
            # The CO and RBT level are typically two paragraphs in the same
            # cell (python-docx joins them with '\n'), but some files use
            # a literal '|' instead — handle both.
            combo_sep = '\n' if '\n' in co_rbt_raw else ('|' if '|' in co_rbt_raw else None)
            if combo_sep:
                parts = [p.strip() for p in co_rbt_raw.split(combo_sep)]
                co_level = parts[0] or None
                if len(parts) > 1 and not rbt_text:
                    rbt_text = parts[1]
            elif co_rbt_raw:
                co_level = co_rbt_raw

            rbt_level = _RBT_MAP.get(rbt_text.strip().lower()) if rbt_text else None
            difficulty = _DIFFICULTY_MAP.get(difficulty_raw.strip().lower()) if difficulty_raw else None

            rows_out.append({
                'question_number': q_no,
                'sub_part': sub_part,
                'question_text': question_text,
                'marks': marks,
                'co_level': co_level,
                'rbt_level': rbt_level,
                'difficulty': difficulty,
            })
        return rows_out


class TheoryQuestion(models.Model):
    """Individual theory / descriptive question inside a question bank."""
    _name = 'exam.theory.question'
    _description = 'Theory / Descriptive Question'
    _order = 'unit, sequence, id'

    bank_id = fields.Many2one('exam.theory.question.bank', string='Question Bank',
                              required=True, ondelete='cascade', index=True)

    sequence = fields.Integer(string='Sequence', default=10)
    question_number = fields.Char(string='Q. No')
    sub_part = fields.Char(string='Sub Part', help='e.g. A, B, C …')

    question_text = fields.Text(string='Question', required=True)
    question_image = fields.Binary(string='Question Image')

    # Classification
    unit = fields.Char(string='Unit', help='e.g. UNIT-1, UNIT-2')
    marks = fields.Integer(string='Marks', required=True, default=7)
    co_level = fields.Char(string='CO Level', help='e.g. CO1, CO2')

    rbt_level = fields.Selection([
        ('remembering', 'Remembering'),
        ('understanding', 'Understanding'),
        ('applying', 'Applying'),
        ('analyzing', 'Analyzing'),
        ('evaluating', 'Evaluating'),
        ('creating', 'Creating'),
    ], string='RBT Level', default='understanding')

    difficulty = fields.Selection([
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ], string='Difficulty', default='medium')

    # Subject (inherited from bank for convenience filtering)
    subject_id = fields.Many2one(related='bank_id.subject_id', store=True,
                                 string='Subject')

    # Whether this question has been used before
    used_count = fields.Integer(string='Times Used', default=0)

    # Expected answer / solution (for evaluator reference)
    model_answer = fields.Html(string='Model Answer / Key Points')

    @api.constrains('marks')
    def _check_marks(self):
        for rec in self:
            if rec.marks <= 0:
                raise ValidationError(_('Marks must be greater than zero.'))