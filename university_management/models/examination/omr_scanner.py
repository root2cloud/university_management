# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import json
import logging
import re

_logger = logging.getLogger(__name__)

# Optional imports — gracefully degrade when not installed OR when
# native/system dependencies (DLLs on Windows, .so on Linux) are missing.
# NOTE: pyzbar and pytesseract can raise more than ImportError at import
# time — e.g. pyzbar raises FileNotFoundError/OSError when libzbar's
# native library isn't found on the system, which would otherwise crash
# the entire Odoo module load. We must catch broadly here.
try:
    from PIL import Image, ImageFilter, ImageEnhance
    HAS_PIL = True
except Exception as e:
    HAS_PIL = False
    _logger.warning('Pillow (PIL) not available — OMR image processing disabled: %s', e)

try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    HAS_PYZBAR = True
except Exception as e:
    HAS_PYZBAR = False
    _logger.warning(
        'pyzbar not available — barcode decoding disabled. '
        'On Windows this usually means the libzbar DLL is missing '
        '(install the zbar shared libraries, e.g. via the '
        '"pyzbar[scripts]" extra or by placing libzbar-64.dll on PATH). '
        'Detail: %s', e
    )

try:
    import pytesseract
    HAS_TESSERACT = True
except Exception as e:
    HAS_TESSERACT = False
    _logger.warning(
        'pytesseract not available — OCR marks detection disabled. '
        'Ensure the Tesseract OCR engine is installed and on PATH. '
        'Detail: %s', e
    )

# EasyOCR is a deep-learning OCR engine (CRAFT text detection + CRNN
# recognition) and is used in preference to Tesseract for reading the
# handwritten marks grid — Tesseract is a print-OCR engine and performs
# poorly on handwritten digits (see _ocr_cell). Barcode reading and the
# rest of the pipeline are unaffected; this only changes how individual
# grid cells are read. Falls back to Tesseract automatically if EasyOCR
# (or its ~100MB model download, fetched once on first use) isn't
# available.
try:
    import warnings
    # EasyOCR's internal DataLoader defaults to pin_memory=True, which is
    # a GPU-only optimisation; on a CPU-only server (no accelerator)
    # PyTorch raises a UserWarning every single time it's used — i.e.
    # once per grid cell, dozens of times per scan. It's not an error and
    # doesn't affect the result, just log noise, so it's silenced here
    # specifically (not warnings globally) right before importing torch's
    # dependents.
    warnings.filterwarnings(
        'ignore', message=".*pin_memory.*no accelerator is found.*", category=UserWarning)
    import easyocr
    import numpy as np
    HAS_EASYOCR = True
except Exception as e:
    HAS_EASYOCR = False
    _logger.warning(
        'easyocr not available — falling back to Tesseract for handwritten '
        'mark detection, which is noticeably less accurate on handwriting. '
        'Install it with: pip install easyocr. Detail: %s', e
    )

_EASYOCR_READER = None


def _get_easyocr_reader():
    """Lazily create and cache a single easyocr.Reader for the process.

    Loading the model is slow (a few seconds) and the model weights are
    ~100MB, downloaded once on first use — so this must not be
    re-created per cell or per scan.
    """
    global _EASYOCR_READER
    if _EASYOCR_READER is None and HAS_EASYOCR:
        try:
            _EASYOCR_READER = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            _logger.warning('Failed to initialise easyocr.Reader: %s', e)
            _EASYOCR_READER = False  # sentinel: don't retry every call
    return _EASYOCR_READER or None

# PyMuPDF is used to rasterize an uploaded PDF's page(s) into images so
# that the same PIL/pyzbar/pytesseract pipeline used for JPEG/PNG scans
# can be reused for PDF uploads. Pillow alone cannot open PDF files.
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception as e:
    HAS_FITZ = False
    _logger.warning(
        'PyMuPDF (fitz) not available — PDF uploads cannot be rasterized '
        'to an image, so OMR scans uploaded as PDF will fail to decode. '
        'Install it with "pip install PyMuPDF". Detail: %s', e
    )

# Render resolution when rasterizing a PDF page to an image. 300 DPI keeps
# barcode + handwritten-digit detail sharp without producing huge images.
PDF_RENDER_DPI = 300


class OMRScanner(models.Model):
    """
    Scanned OMR answer-sheet processor.
    1. Upload the scanned image / PDF of the corrected OMR sheet.
    2. OCR reads the barcode → identifies the student + subject + exam.
    3. OCR detects the handwritten marks in the grid cells
       (question-wise a, b, c, d and grand total).
    4. Marks are written back to the examination.result record.
    5. The scanned document is saved as an attachment.
    """
    _name = 'exam.omr.scanner'
    _description = 'OMR Sheet Scanner (OCR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'scan_date desc'

    # Reference page size (PDF points) that all _GRID_LAYOUT / _COLS_*
    # coordinates below were measured against — must match exam.omr.sheet's
    # PAGE_W/PAGE_H, since that's the exact PDF these sheets are printed
    # from. A scanned upload is assumed to be that same page (any
    # resolution), scaled proportionally — see _ocr_marks_grid.
    PAGE_W_REF = 651.12
    PAGE_H_REF = 1089.12

    name = fields.Char(string='Scan Reference',
                       default=lambda self: self.env['ir.sequence'].next_by_code('exam.omr.scanner') or 'NEW',
                       required=True, copy=False)

    # ---- Upload ----
    scanned_file = fields.Binary(string='Scanned OMR Sheet', required=True,
                                 attachment=True,
                                 help='Upload the scanned image (JPEG/PNG) or PDF of the corrected OMR sheet.')
    scanned_filename = fields.Char(string='Filename')
    scan_date = fields.Datetime(string='Scan Date', default=fields.Datetime.now)

    # ---- Barcode-decoded info ----
    barcode_raw = fields.Char(string='Barcode Raw Data', readonly=True)
    decoded_registration = fields.Char(string='Registration No. (decoded)', readonly=True)
    decoded_student_name = fields.Char(string='Student Name (decoded)', readonly=True)
    decoded_subject_code = fields.Char(string='Subject Code (decoded)', readonly=True)
    decoded_exam_id = fields.Integer(string='Examination ID (decoded)', readonly=True)
    decoded_serial = fields.Char(string='OMR Serial (decoded)', readonly=True)
    decoded_hall_ticket = fields.Char(string='Hall Ticket (decoded)', readonly=True)

    # ---- Linked records (auto-resolved from barcode) ----
    student_id = fields.Many2one('student.student', string='Student', readonly=True,
                                 tracking=True)
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     readonly=True, tracking=True)
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 readonly=True, tracking=True)
    omr_sheet_id = fields.Many2one('exam.omr.sheet', string='OMR Sheet',
                                   readonly=True)
    result_id = fields.Many2one('examination.result', string='Result Record',
                                readonly=True, tracking=True)

    # ---- OCR-detected marks ----
    detected_marks_json = fields.Text(
        string='Detected Marks (JSON)', readonly=True,
        help='JSON dict of question-wise marks as detected by OCR.',
    )
    detected_grand_total = fields.Integer(string='Detected Grand Total', readonly=True)

    # Editable — one Char field per printed question box. Edit a value
    # here if OCR detected it incorrectly (see QUESTION_FIELD_MAP below).
    # ------------------------------------------------------------------
    # Question-wise marks — ONE FIELD PER QUESTION (fixed columns)
    # ------------------------------------------------------------------
    # Matches the fixed, printed grid geometry in _COLS_PART_A /
    # _COLS_PART_B_LEFT / _COLS_PART_B_RIGHT above: every question box
    # printed on the OMR sheet gets its own stored Char field here (Q1A,
    # Q1B, ... Q12total), instead of being packed into one text blob or
    # one2many. Because they're real fields on this model, they behave
    # exactly like 'Grand Total Marks': they show as their own columns in
    # the list view and are picked up automatically by the Export Data
    # wizard (see QUESTION_FIELD_MAP below, and views/.../omr_scanner_views.xml).
    #
    # NOTE — bug fixed while adding these: _ocr_marks_grid() used to write
    # Part-A's own 'Q1total' cell and Part-B question 1's 'Q1total' cell to
    # the exact same dict key ('Q1total'), so Part-B silently overwrote
    # Part-A's total. Part-A's total cell is now read into 'Q1PAtotal'
    # instead, so both are captured correctly (see pa_q1_total below).
    pa_q1_a = fields.Char(string='Q1A')
    pa_q1_b = fields.Char(string='Q1B')
    pa_q1_c = fields.Char(string='Q1C')
    pa_q1_d = fields.Char(string='Q1D')
    pa_q1_e = fields.Char(string='Q1E')
    pa_q1_f = fields.Char(string='Q1F')
    pa_q1_g = fields.Char(string='Q1G')
    pa_q1_h = fields.Char(string='Q1H')
    pa_q1_i = fields.Char(string='Q1I')
    pa_q1_j = fields.Char(string='Q1J')
    pa_q1_extra = fields.Char(string='Q1 Extra')
    pa_q1_total = fields.Char(string='Q1 Total (Part-A)')
    pb_q1_a = fields.Char(string='Q1a')
    pb_q1_b = fields.Char(string='Q1b')
    pb_q1_c = fields.Char(string='Q1c')
    pb_q1_d = fields.Char(string='Q1d')
    pb_q1_total = fields.Char(string='Q1 Total')
    pb_q2_a = fields.Char(string='Q2a')
    pb_q2_b = fields.Char(string='Q2b')
    pb_q2_c = fields.Char(string='Q2c')
    pb_q2_d = fields.Char(string='Q2d')
    pb_q2_total = fields.Char(string='Q2 Total')
    pb_q3_a = fields.Char(string='Q3a')
    pb_q3_b = fields.Char(string='Q3b')
    pb_q3_c = fields.Char(string='Q3c')
    pb_q3_d = fields.Char(string='Q3d')
    pb_q3_total = fields.Char(string='Q3 Total')
    pb_q4_a = fields.Char(string='Q4a')
    pb_q4_b = fields.Char(string='Q4b')
    pb_q4_c = fields.Char(string='Q4c')
    pb_q4_d = fields.Char(string='Q4d')
    pb_q4_total = fields.Char(string='Q4 Total')
    pb_q5_a = fields.Char(string='Q5a')
    pb_q5_b = fields.Char(string='Q5b')
    pb_q5_c = fields.Char(string='Q5c')
    pb_q5_d = fields.Char(string='Q5d')
    pb_q5_total = fields.Char(string='Q5 Total')
    pb_q6_a = fields.Char(string='Q6a')
    pb_q6_b = fields.Char(string='Q6b')
    pb_q6_c = fields.Char(string='Q6c')
    pb_q6_d = fields.Char(string='Q6d')
    pb_q6_total = fields.Char(string='Q6 Total')
    pb_q7_a = fields.Char(string='Q7a')
    pb_q7_b = fields.Char(string='Q7b')
    pb_q7_c = fields.Char(string='Q7c')
    pb_q7_d = fields.Char(string='Q7d')
    pb_q7_total = fields.Char(string='Q7 Total')
    pb_q8_a = fields.Char(string='Q8a')
    pb_q8_b = fields.Char(string='Q8b')
    pb_q8_c = fields.Char(string='Q8c')
    pb_q8_d = fields.Char(string='Q8d')
    pb_q8_total = fields.Char(string='Q8 Total')
    pb_q9_a = fields.Char(string='Q9a')
    pb_q9_b = fields.Char(string='Q9b')
    pb_q9_c = fields.Char(string='Q9c')
    pb_q9_d = fields.Char(string='Q9d')
    pb_q9_total = fields.Char(string='Q9 Total')
    pb_q10_a = fields.Char(string='Q10a')
    pb_q10_b = fields.Char(string='Q10b')
    pb_q10_c = fields.Char(string='Q10c')
    pb_q10_d = fields.Char(string='Q10d')
    pb_q10_total = fields.Char(string='Q10 Total')
    pb_q11_a = fields.Char(string='Q11a')
    pb_q11_b = fields.Char(string='Q11b')
    pb_q11_c = fields.Char(string='Q11c')
    pb_q11_d = fields.Char(string='Q11d')
    pb_q11_total = fields.Char(string='Q11 Total')
    pb_q12_a = fields.Char(string='Q12a')
    pb_q12_b = fields.Char(string='Q12b')
    pb_q12_c = fields.Char(string='Q12c')
    pb_q12_d = fields.Char(string='Q12d')
    pb_q12_total = fields.Char(string='Q12 Total')

    # (field_name, marks_data key, question label) — single source of
    # truth used by _sync_question_mark_fields() to fill the fields above
    # from the OCR result, and by _compute_question_marks_display() to
    # rebuild the readable 'Q1A=3, Q1B=2 ...' summary posted to the result.
    QUESTION_FIELD_MAP = [
        ('pa_q1_a', 'Q1A'),
        ('pa_q1_b', 'Q1B'),
        ('pa_q1_c', 'Q1C'),
        ('pa_q1_d', 'Q1D'),
        ('pa_q1_e', 'Q1E'),
        ('pa_q1_f', 'Q1F'),
        ('pa_q1_g', 'Q1G'),
        ('pa_q1_h', 'Q1H'),
        ('pa_q1_i', 'Q1I'),
        ('pa_q1_j', 'Q1J'),
        ('pa_q1_extra', 'Q1extra'),
        ('pa_q1_total', 'Q1PAtotal'),
        ('pb_q1_a', 'Q1a'),
        ('pb_q1_b', 'Q1b'),
        ('pb_q1_c', 'Q1c'),
        ('pb_q1_d', 'Q1d'),
        ('pb_q1_total', 'Q1total'),
        ('pb_q2_a', 'Q2a'),
        ('pb_q2_b', 'Q2b'),
        ('pb_q2_c', 'Q2c'),
        ('pb_q2_d', 'Q2d'),
        ('pb_q2_total', 'Q2total'),
        ('pb_q3_a', 'Q3a'),
        ('pb_q3_b', 'Q3b'),
        ('pb_q3_c', 'Q3c'),
        ('pb_q3_d', 'Q3d'),
        ('pb_q3_total', 'Q3total'),
        ('pb_q4_a', 'Q4a'),
        ('pb_q4_b', 'Q4b'),
        ('pb_q4_c', 'Q4c'),
        ('pb_q4_d', 'Q4d'),
        ('pb_q4_total', 'Q4total'),
        ('pb_q5_a', 'Q5a'),
        ('pb_q5_b', 'Q5b'),
        ('pb_q5_c', 'Q5c'),
        ('pb_q5_d', 'Q5d'),
        ('pb_q5_total', 'Q5total'),
        ('pb_q6_a', 'Q6a'),
        ('pb_q6_b', 'Q6b'),
        ('pb_q6_c', 'Q6c'),
        ('pb_q6_d', 'Q6d'),
        ('pb_q6_total', 'Q6total'),
        ('pb_q7_a', 'Q7a'),
        ('pb_q7_b', 'Q7b'),
        ('pb_q7_c', 'Q7c'),
        ('pb_q7_d', 'Q7d'),
        ('pb_q7_total', 'Q7total'),
        ('pb_q8_a', 'Q8a'),
        ('pb_q8_b', 'Q8b'),
        ('pb_q8_c', 'Q8c'),
        ('pb_q8_d', 'Q8d'),
        ('pb_q8_total', 'Q8total'),
        ('pb_q9_a', 'Q9a'),
        ('pb_q9_b', 'Q9b'),
        ('pb_q9_c', 'Q9c'),
        ('pb_q9_d', 'Q9d'),
        ('pb_q9_total', 'Q9total'),
        ('pb_q10_a', 'Q10a'),
        ('pb_q10_b', 'Q10b'),
        ('pb_q10_c', 'Q10c'),
        ('pb_q10_d', 'Q10d'),
        ('pb_q10_total', 'Q10total'),
        ('pb_q11_a', 'Q11a'),
        ('pb_q11_b', 'Q11b'),
        ('pb_q11_c', 'Q11c'),
        ('pb_q11_d', 'Q11d'),
        ('pb_q11_total', 'Q11total'),
        ('pb_q12_a', 'Q12a'),
        ('pb_q12_b', 'Q12b'),
        ('pb_q12_c', 'Q12c'),
        ('pb_q12_d', 'Q12d'),
        ('pb_q12_total', 'Q12total'),
    ]

    unread_questions_display = fields.Char(
        string='Unread Questions',
        help='Question codes where OCR found ink but could not confidently '
             'read a digit — check the scanned sheet and type the value into '
             'the matching field above by hand.',
    )

    # Kept for anything still reading the old field name / for a readable
    # one-line summary posted to the result record's chatter (see
    # action_confirm_marks). Rebuilt automatically from the per-question
    # fields above — not edited directly.
    question_marks_display = fields.Char(
        string='Question-wise Marks (text)',
        compute='_compute_question_marks_display', store=True,
    )
    grand_total = fields.Integer(string='Grand Total Marks')

    @api.depends(
        'pa_q1_a', 'pa_q1_b', 'pa_q1_c', 'pa_q1_d', 'pa_q1_e', 'pa_q1_f',
        'pa_q1_g', 'pa_q1_h', 'pa_q1_i', 'pa_q1_j', 'pa_q1_extra',
        'pa_q1_total', 'pb_q1_a', 'pb_q1_b', 'pb_q1_c', 'pb_q1_d',
        'pb_q1_total', 'pb_q2_a', 'pb_q2_b', 'pb_q2_c', 'pb_q2_d',
        'pb_q2_total', 'pb_q3_a', 'pb_q3_b', 'pb_q3_c', 'pb_q3_d',
        'pb_q3_total', 'pb_q4_a', 'pb_q4_b', 'pb_q4_c', 'pb_q4_d',
        'pb_q4_total', 'pb_q5_a', 'pb_q5_b', 'pb_q5_c', 'pb_q5_d',
        'pb_q5_total', 'pb_q6_a', 'pb_q6_b', 'pb_q6_c', 'pb_q6_d',
        'pb_q6_total', 'pb_q7_a', 'pb_q7_b', 'pb_q7_c', 'pb_q7_d',
        'pb_q7_total', 'pb_q8_a', 'pb_q8_b', 'pb_q8_c', 'pb_q8_d',
        'pb_q8_total', 'pb_q9_a', 'pb_q9_b', 'pb_q9_c', 'pb_q9_d',
        'pb_q9_total', 'pb_q10_a', 'pb_q10_b', 'pb_q10_c', 'pb_q10_d',
        'pb_q10_total', 'pb_q11_a', 'pb_q11_b', 'pb_q11_c', 'pb_q11_d',
        'pb_q11_total', 'pb_q12_a', 'pb_q12_b', 'pb_q12_c', 'pb_q12_d',
        'pb_q12_total', 'unread_questions_display'
    )
    def _compute_question_marks_display(self):
        for omr in self:
            parts = [
                f'{key}={getattr(omr, fname)}'
                for fname, key in omr.QUESTION_FIELD_MAP
                if getattr(omr, fname)
            ]
            if omr.unread_questions_display:
                parts.append('UNREAD(check sheet)=' + omr.unread_questions_display)
            omr.question_marks_display = ', '.join(parts)

    # ---- Valuation part detected ----
    valuation_part = fields.Selection([
        ('valuation_1', 'Valuation 1 (Part-II)'),
        ('revaluation', 'Re-Valuation (Part-III)'),
    ], string='Valuation Part', default='valuation_1')

    # ---- Status ----
    state = fields.Selection([
        ('draft', 'Uploaded'),
        ('decoded', 'Barcode Decoded'),
        ('ocr_done', 'Marks Detected'),
        ('confirmed', 'Confirmed & Updated'),
        ('failed', 'Failed'),
    ], string='Status', default='draft', tracking=True)

    error_message = fields.Text(string='Error / Warnings', readonly=True)

    # ---- Human-review gate ----
    # Tesseract is a print-OCR engine, not a handwriting specialist: it can
    # (and does) confidently return a wrong digit, or silently drop a cell
    # that clearly has ink in it. needs_review is set by _ocr_marks_grid
    # whenever it isn't confident the detected marks are correct — e.g. a
    # cell has ink but no digit could be read, or the grand-total cell
    # OCR disagrees with the sum of the question-wise cells that WERE
    # read. action_confirm_marks refuses to run while needs_review is set
    # and reviewed_manually is not ticked, so a low-confidence OCR pass
    # can no longer be confirmed straight through without a human looking
    # at the sheet.
    needs_review = fields.Boolean(string='Needs Manual Review', readonly=True)
    review_notes = fields.Text(string='Review Notes', readonly=True,
                               help='Specific reasons OCR confidence was low for this scan.')
    reviewed_manually = fields.Boolean(
        string='I have checked the flagged marks against the scanned sheet',
        help='Tick this after visually comparing "Question-wise Marks" and '
             '"Grand Total Marks" below against the uploaded scan, then use '
             '3. Confirm & Update Result.',
    )

    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    # Plain reference to the ir.attachment wrapping the originally
    # uploaded sheet — not shown in any view. Not currently used by any
    # action; kept as a stable pointer to "the real attachment" in case
    # it's useful later.
    main_sheet_attachment_id = fields.Many2one('ir.attachment', copy=False)

    # ==================================================================
    # UPLOAD → CHATTER PREVIEW
    # ==================================================================
    # Post the actual uploaded sheet into the chatter as soon as it's
    # saved, rather than only ever showing generic status text. Covers
    # both "new record created with a file already attached" and
    # "existing record's file replaced" (write()).
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if vals.get('scanned_file'):
                rec._post_uploaded_sheet_preview()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('scanned_file'):
            for rec in self:
                rec._post_uploaded_sheet_preview()
        return result

    def _post_uploaded_sheet_preview(self):
        """Set the just-uploaded file as the record's main attachment, so
        Odoo's built-in o_attachment_preview panel (the split-screen
        PDF/image viewer next to the form — see hr.payslip for the same
        pattern) shows the actual scanned sheet.

        Deliberately does NOT also post a resized PNG copy to the
        chatter: o_attachment_preview lets you cycle between every
        attachment linked to the record via the small arrows at its
        edges, so a second "preview" image just became a confusing
        second, lower-quality thing to click through to. One real
        attachment (the original PDF/image, full quality) is enough.
        """
        self.ensure_one()
        self._set_main_attachment_from_scanned_file()

    def _set_main_attachment_from_scanned_file(self):
        """Wrap the raw uploaded file (PDF or image) as a real
        ir.attachment and point message_main_attachment_id at it, so the
        actual original file — barcode, photo, handwriting and all — is
        what shows in the preview panel, not a re-generated copy.

        Also remembered in main_sheet_attachment_id, a plain reference
        (not shown in any view) to whichever attachment is the actual
        uploaded sheet, kept in case it's useful later.
        """
        self.ensure_one()
        if not self.scanned_file:
            return
        try:
            data = base64.b64decode(self.scanned_file)
            attachment_vals = {
                'name': self.scanned_filename or f'OMR_Scan_{self.name}.pdf',
                'datas': self.scanned_file,
                'res_model': self._name,
                'res_id': self.id,
            }
            # Odoo auto-detects mimetype from content/filename when it's
            # not supplied — only worth overriding for the PDF case,
            # which we can already detect confidently and cheaply.
            if self._looks_like_pdf(data):
                attachment_vals['mimetype'] = 'application/pdf'
            attachment = self.env['ir.attachment'].create(attachment_vals)
            self.message_main_attachment_id = attachment.id
            self.main_sheet_attachment_id = attachment.id
        except Exception as e:
            _logger.warning('Failed to set main attachment for OMR preview panel: %s', e)

    # ==================================================================
    # 1. DECODE BARCODE
    # ==================================================================
    def action_decode_barcode(self):
        """Read the barcode from the scanned image to identify the student."""
        self.ensure_one()
        if not self.scanned_file:
            raise UserError(_('Please upload a scanned OMR sheet first.'))

        if not HAS_PYZBAR and not HAS_TESSERACT:
            raise UserError(_(
                'Barcode decoding is unavailable on this server: neither '
                'pyzbar nor pytesseract could be loaded. Check the server '
                'log at startup for the exact reason (commonly a missing '
                'native library — libzbar on Linux/Mac, libzbar-64.dll on '
                'Windows — or a missing Tesseract OCR installation).'
            ))
        if self._looks_like_pdf(base64.b64decode(self.scanned_file)) and not HAS_FITZ:
            raise UserError(_(
                'The uploaded file is a PDF, but PyMuPDF is not installed '
                'on this server, so it cannot be converted to an image. '
                'Install it with: pip install PyMuPDF, then try again.'
            ))
        if not HAS_PYZBAR:
            _logger.info(
                'pyzbar unavailable, falling back to Tesseract text '
                'recognition for barcode data (less reliable).'
            )

        img = self._get_image()
        if img is None:
            raise UserError(_('Could not read the uploaded file as an image.'))

        barcode_data = self._read_barcode(img)
        if not barcode_data:
            self.write({
                'state': 'failed',
                'error_message': 'No barcode detected in the scanned image. '
                                 'Please ensure the barcode area is clearly visible.',
            })
            return

        # The barcode printed on the sheet (see exam.omr.sheet._compute_barcode_data)
        # holds only the sheet's serial_number — not a pipe-delimited composite.
        # Look up the exam.omr.sheet record it was generated from and pull the
        # student/exam/subject/hall-ticket off THAT record, which is already
        # the single source of truth (and stays correct even if the student's
        # registration number, name, etc. change after the sheet was printed).
        serial = barcode_data.strip()
        omr = self.env['exam.omr.sheet'].search([
            ('serial_number', '=', serial),
        ], limit=1)

        if not omr:
            self.write({
                'state': 'failed',
                'barcode_raw': barcode_data,
                'error_message': _(
                    'Barcode decoded as "%s" but no OMR sheet with that serial '
                    'number was found. It may not have been generated from '
                    'this system, or the barcode was misread.', serial,
                ),
            })
            return

        vals = {
            'barcode_raw': barcode_data,
            'decoded_registration': omr.registration_number or '',
            'decoded_student_name': omr.student_name or '',
            'decoded_subject_code': omr.subject_id.code or '',
            'decoded_exam_id': omr.examination_id.id or 0,
            'decoded_serial': omr.serial_number or '',
            'decoded_hall_ticket': omr.hall_ticket_number or '',
            'student_id': omr.student_id.id,
            'examination_id': omr.examination_id.id,
            'subject_id': omr.subject_id.id,
            'omr_sheet_id': omr.id,
            'state': 'decoded',
            'error_message': False,
        }
        self.write(vals)

    # ==================================================================
    # 2. OCR — DETECT HANDWRITTEN MARKS
    # ==================================================================
    def action_detect_marks(self):
        """
        Run OCR on the marks grid area to detect handwritten digits
        in each cell (question-wise) and the grand total.
        """
        self.ensure_one()
        if self.state not in ('decoded', 'ocr_done'):
            raise UserError(_('Please decode the barcode first.'))

        if not HAS_TESSERACT and not HAS_EASYOCR:
            raise UserError(_(
                'No OCR engine is installed on the server (neither easyocr nor '
                'pytesseract). Install one with: pip install easyocr'
            ))

        img = self._get_image()
        if img is None:
            raise UserError(_('Could not read the uploaded file.'))


        marks_data, grand_total, needs_review, review_notes, unread_cells, engine_used = self._ocr_marks_grid(img)

        vals = {
            'detected_marks_json': json.dumps(marks_data, indent=2),
            'detected_grand_total': grand_total,
            'grand_total': grand_total,
            'state': 'ocr_done',
            'needs_review': needs_review,
            'review_notes': review_notes,
            'reviewed_manually': False,
            'error_message': False,
        }
        vals.update(self._build_question_field_vals(marks_data, unread_cells))
        self.write(vals)

    def _build_question_field_vals(self, marks_data, unread_cells=None):
        """Map a {question_code: mark} dict (as returned by
        _ocr_marks_grid) onto this model's fixed per-question fields
        (see QUESTION_FIELD_MAP), so every question gets its own
        stored, exportable field/column instead of one comma-separated
        blob or a one2many. Any question NOT present in marks_data
        (blank on the sheet) is cleared.
        """
        unread_cells = set(unread_cells or [])
        vals = {}
        for fname, key in self.QUESTION_FIELD_MAP:
            if key in marks_data:
                vals[fname] = str(marks_data[key])
            elif key in unread_cells:
                vals[fname] = False
            else:
                vals[fname] = False
        vals['unread_questions_display'] = ','.join(sorted(unread_cells)) if unread_cells else False
        return vals

    # ==================================================================
    # 3. CONFIRM & UPDATE RESULT
    # ==================================================================
    def action_confirm_marks(self):
        """
        Write the confirmed marks to the examination.result record
        and save the scanned document as an attachment.
        """
        self.ensure_one()
        if not self.student_id:
            raise UserError(_('Student not identified. Please decode barcode or set manually.'))
        if not self.examination_id:
            raise UserError(_('Examination not identified.'))

        # Find or create the result record
        result = self.env['examination.result'].search([
            ('student_id', '=', self.student_id.id),
            ('examination_id', '=', self.examination_id.id),
            ('subject_id', '=', self.subject_id.id) if self.subject_id else (1, '=', 1),
        ], limit=1)

        if result:
            result.write({
                'external_marks': self.grand_total,
                'evaluation_date': fields.Date.today(),
            })
            self.result_id = result.id
        else:
            # Log warning — result record not found
            self.write({
                'error_message': _(
                    'No existing result record found for student %s, exam %s, subject %s. '
                    'Please create the result record first or enter marks manually.',
                    self.student_id.name,
                    self.examination_id.name,
                    self.subject_id.name if self.subject_id else '(unknown)',
                ),
            })

        # Save scanned file as attachment on the result (and OMR sheet)
        if self.scanned_file:
            attachment_vals = {
                'name': self.scanned_filename or f'OMR_Scan_{self.name}',
                'type': 'binary',
                'datas': self.scanned_file,
                'res_model': 'examination.result',
                'res_id': result.id if result else False,
                'mimetype': 'image/jpeg',
            }
            self.env['ir.attachment'].create(attachment_vals)

            # Also attach to OMR sheet record
            if self.omr_sheet_id:
                self.env['ir.attachment'].create({
                    'name': self.scanned_filename or f'OMR_Scan_{self.name}',
                    'type': 'binary',
                    'datas': self.scanned_file,
                    'res_model': 'exam.omr.sheet',
                    'res_id': self.omr_sheet_id.id,
                    'mimetype': 'image/jpeg',
                })
                self.omr_sheet_id.write({'state': 'scanned'})

        # Save question-wise marks as a note on the result
        if result and self.question_marks_display:
            result.message_post(
                body=_(
                    '<b>Question-wise marks (OCR scan %s):</b><br/>%s<br/>'
                    '<b>Grand Total:</b> %s',
                    self.name,
                    self.question_marks_display.replace(',', '<br/>'),
                    self.grand_total,
                ),
            )

        self.write({'state': 'confirmed', 'error_message': False})

    def action_reset_draft(self):
        self.write({'state': 'draft', 'error_message': False})

    def action_view_sheet(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('OMR Sheet'),
            'res_model': 'exam.omr.sheet',
            'view_mode': 'form',
            'res_id': self.omr_sheet_id.id,
        }

    def action_view_result(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Result'),
            'res_model': 'examination.result',
            'view_mode': 'form',
            'res_id': self.result_id.id,
        }

    # ==================================================================
    # Batch processing
    # ==================================================================
    def action_process_all(self):
        """One-click: decode barcode → detect marks → confirm."""
        self.ensure_one()
        self.action_decode_barcode()
        if self.state == 'decoded':
            self.action_detect_marks()
        if self.state == 'ocr_done':
            self.action_confirm_marks()

    # ==================================================================
    # INTERNAL HELPERS
    # ==================================================================
    def _get_image(self):
        """
        Return a PIL Image built from the uploaded binary field.

        Supports plain image uploads (JPEG/PNG/...) as well as PDF
        uploads — PDFs are rasterized to an image (first page) before
        being handed to the barcode/OCR pipeline, since PIL cannot open
        PDF files directly.
        """
        if not HAS_PIL:
            _logger.error('Pillow (PIL) not installed.')
            return None
        try:
            data = base64.b64decode(self.scanned_file)
        except Exception as e:
            _logger.warning('Failed to decode base64 of scanned file: %s', e)
            return None

        if self._looks_like_pdf(data):
            return self._pdf_to_image(data)

        try:
            img = Image.open(io.BytesIO(data))
            img.load()  # force-read now so problems surface here, not later
            return img
        except Exception as e:
            _logger.warning('Failed to open scanned file as an image: %s', e)
            return None

    @staticmethod
    def _looks_like_pdf(data):
        """Detect PDF content regardless of the filename/extension used."""
        return bool(data) and data[:5] == b'%PDF-'

    def _pdf_to_image(self, data):
        """
        Rasterize the first page of an uploaded PDF into a PIL Image
        at PDF_RENDER_DPI, so the same barcode/OCR pipeline used for
        image uploads can be reused for PDF uploads.
        """
        if not HAS_FITZ:
            _logger.error(
                'Uploaded file is a PDF but PyMuPDF (fitz) is not '
                'installed, so it cannot be converted to an image. '
                'Install it with: pip install PyMuPDF'
            )
            return None
        try:
            doc = fitz.open(stream=data, filetype='pdf')
            if doc.page_count == 0:
                _logger.warning('Uploaded PDF has no pages.')
                return None
            page = doc.load_page(0)
            zoom = PDF_RENDER_DPI / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes('png')))
            img.load()
            doc.close()
            return img
        except Exception as e:
            _logger.warning('Failed to rasterize uploaded PDF: %s', e)
            return None

    def _read_barcode(self, img):
        """
        Attempt to read barcodes from the image using pyzbar.
        Falls back to pytesseract if pyzbar is not available.
        """
        if HAS_PYZBAR:
            try:
                # Try multiple preprocessing approaches
                for attempt_img in self._preprocess_for_barcode(img):
                    decoded = pyzbar_decode(attempt_img)
                    for obj in decoded:
                        data = obj.data.decode('utf-8', errors='ignore')
                        if '|' in data:
                            return data
                # If no pipe-delimited barcode found, return first barcode
                decoded = pyzbar_decode(img)
                if decoded:
                    return decoded[0].data.decode('utf-8', errors='ignore')
            except Exception as e:
                _logger.warning('pyzbar decode failed: %s', e)

        # Fallback: try tesseract to read barcode number as text
        if HAS_TESSERACT:
            try:
                # Crop top portion where barcode usually is
                w, h = img.size
                top_crop = img.crop((0, 0, w, int(h * 0.15)))
                text = pytesseract.image_to_string(top_crop, config='--psm 6')
                # Look for pipe-delimited pattern
                for line in text.split('\n'):
                    if '|' in line and len(line.split('|')) >= 3:
                        return line.strip()
            except Exception as e:
                _logger.warning('Tesseract barcode fallback failed: %s', e)

        return None

    def _preprocess_for_barcode(self, img):
        """Yield preprocessed versions of the image for better barcode detection."""
        # Original
        yield img
        # Grayscale
        gray = img.convert('L')
        yield gray
        # High contrast
        enhancer = ImageEnhance.Contrast(gray)
        yield enhancer.enhance(2.0)
        # Sharpened
        yield gray.filter(ImageFilter.SHARPEN)
        # Binarized
        threshold = 128
        yield gray.point(lambda p: 255 if p > threshold else 0, '1')

    # ------------------------------------------------------------------
    # Fixed grid geometry, measured directly off the printed template
    # (OMR.drawio.xml / the generated PDF) in PDF points, same coordinate
    # system as PAGE_W/PAGE_H and the _draw_* methods in omr_sheet.py.
    # Column positions are identical in PART-A and PART-B and in both the
    # Valuation and Re-Valuation copies — only the row y-positions differ
    # between the two copies (they're two separate printed sections).
    # ------------------------------------------------------------------
    _COLS_PART_A = {
        'A': (277.44, 290.88), 'B': (290.88, 304.56), 'C': (304.56, 318.0),
        'D': (318.0, 331.68), 'E': (331.68, 344.64), 'F': (344.64, 358.08),
        'G': (358.08, 371.76), 'H': (371.76, 385.2), 'I': (385.2, 398.64),
        'J': (398.64, 412.32), 'extra': (412.32, 426.48), 'total': (426.48, 446.88),
    }
    _COLS_PART_B_LEFT = {
        'a': (277.44, 290.88), 'b': (290.88, 304.56), 'c': (304.56, 318.0),
        'd': (318.0, 331.68), 'total': (331.68, 344.64),
    }
    _COLS_PART_B_RIGHT = {
        'a': (358.08, 371.76), 'b': (371.76, 385.2), 'c': (385.2, 398.64),
        'd': (398.64, 412.32), 'total': (412.32, 426.48),
    }
    _BEST_COL = (426.48, 446.88)

    # (question-left, question-right, row-top, row-bottom) for each PART-B
    # row, and the PART-A / grand-total row bands, per valuation part.
    _GRID_LAYOUT = {
        'valuation_1': {
            'part_a_row': (825.36, 838.8),
            'part_b_rows': [
                (1, 2, 865.92, 879.6), (3, 4, 879.6, 893.04), (5, 6, 893.04, 906.72),
                (7, 8, 906.72, 920.16), (9, 10, 920.16, 933.6), (11, 12, 933.6, 947.28),
            ],
            'grand_total_row': (947.28, 960.72),
        },
        'revaluation': {
            'part_a_row': (486.72, 500.16),
            'part_b_rows': [
                (1, 2, 527.28, 540.72), (3, 4, 540.72, 554.4), (5, 6, 554.4, 567.84),
                (7, 8, 567.84, 581.52), (9, 10, 581.52, 594.96), (11, 12, 594.96, 608.64),
            ],
            'grand_total_row': (608.64, 622.08),
        },
    }

    # Minimum fraction of dark pixels inside a cell (after excluding its
    # border) for the cell to be considered "has a handwritten mark".
    # Below this it's treated as blank rather than risking a false read
    # off the cell's own border lines.
    _INK_THRESHOLD = 0.03

    def _cell_ink_density(self, img, x0, y0, x1, y1, scale_x, scale_y, inset=6):
        px0 = int(x0 * scale_x + inset)
        py0 = int(y0 * scale_y + inset)
        px1 = int(x1 * scale_x - inset)
        py1 = int(y1 * scale_y - inset)
        if px1 <= px0 or py1 <= py0:
            return 0.0
        region = img.crop((px0, py0, px1, py1)).convert('L')
        import numpy as np  # local import: numpy is a Pillow/reportlab dependency already present
        arr = np.array(region)
        return float((arr < 150).mean())

    # Tesseract's own 0-100 confidence score (from image_to_data). Below
    # this, a "successful" digit read is treated the same as no read at
    # all — a confident wrong guess is worse than an honest blank, since
    # a blank gets surfaced to the examiner via unread_cells while a wrong
    # guess silently overwrites the correct mark (see the docstring on
    # needs_review).
    _OCR_CONF_THRESHOLD = 45

    def _ocr_cell(self, img, x0, y0, x1, y1, scale_x, scale_y, pad=4, upscale=6, threshold=150):
        """OCR a single grid cell, isolated by its own coordinates, instead
        of guessing which digit-shaped blob on the page belongs to it.

        Returns (value, confidence_0_to_100) — value is None if no digit
        could be read with acceptable confidence.

        Tries EasyOCR first (a deep-learning engine, much better on
        handwriting than Tesseract — see the import block at the top of
        this file), falling back to Tesseract only if EasyOCR isn't
        available. pad was increased from the original 2pt to 4pt:
        handwritten digits (loopy 8s/9s especially) routinely overflow a
        tightly-cropped cell, and clipping the top of an 8 or the tail of
        a 9 is exactly what turns them into a 4 or a 2.
        """
        px0 = x0 * scale_x - pad
        py0 = y0 * scale_y - pad
        px1 = x1 * scale_x + pad
        py1 = y1 * scale_y + pad
        base_crop = img.crop((px0, py0, px1, py1)).convert('RGB')

        reader = _get_easyocr_reader() if HAS_EASYOCR else None
        if reader is not None:
            try:
                results = reader.readtext(np.array(base_crop), allowlist='0123456789', detail=1)
            except Exception as e:
                _logger.warning('EasyOCR cell read failed, falling back to Tesseract: %s', e)
                results = None
            if results:
                text = ''.join(r[1] for r in results).strip()
                # confidence of the weakest detected character/word in the
                # cell — one misread digit shouldn't be hidden behind a
                # confident neighbour's score.
                conf = min(r[2] for r in results) * 100.0
                if text.isdigit() and conf >= self._OCR_CONF_THRESHOLD:
                    return int(text), conf
                return None, conf  # low confidence, or not a clean digit — don't guess

        if not HAS_TESSERACT:
            return None, 0.0

        best_value, best_conf = None, -1.0
        for thresh in (threshold, 180, 120):
            crop = base_crop.convert('L').resize(
                (max(1, base_crop.width * upscale), max(1, base_crop.height * upscale)), Image.LANCZOS)
            crop = crop.point(lambda p, t=thresh: 255 if p > t else 0)
            for psm in (7, 8, 6):
                config = f'--psm {psm} -c tessedit_char_whitelist=0123456789'
                try:
                    data = pytesseract.image_to_data(
                        crop, config=config, output_type=pytesseract.Output.DICT)
                except Exception as e:
                    _logger.warning('Tesseract cell OCR failed: %s', e)
                    continue
                for text, conf in zip(data.get('text', []), data.get('conf', [])):
                    text = text.strip()
                    try:
                        conf = float(conf)
                    except (TypeError, ValueError):
                        conf = -1.0
                    if text.isdigit() and conf > best_conf:
                        best_value, best_conf = int(text), conf
        if best_value is not None and best_conf >= self._OCR_CONF_THRESHOLD:
            return best_value, best_conf
        return None, best_conf

    def _ocr_marks_grid(self, img):
        """
        Detect handwritten digits in the marks grid, cell by cell, using
        the fixed grid geometry of the printed template (see _GRID_LAYOUT)
        rather than guessing positions from an unordered list of detected
        digits. Each cell is checked for ink first (_cell_ink_density) so
        a blank cell's own border lines can't be misread as a mark.

        Returns (marks_dict, grand_total, needs_review, review_notes,
        unread_cells, engine_used). Cells with no confidently-detected mark are absent
        from marks_dict — they are NOT assumed to be 0, since "blank" and
        "OCR couldn't read it" are different things the examiner should be
        able to tell apart when reviewing the result. Cells that clearly
        have ink but couldn't be read with acceptable confidence are
        collected into unread_cells instead of being silently dropped.

        NOTE: Tesseract is a general-purpose print-OCR engine, not a
        handwritten-digit specialist. Even with correct cell coordinates,
        stylised handwriting (loopy 8s, joined digits, etc.) will
        sometimes be missed or misread — and can do so *confidently*,
        which a bare digit-string check can't tell apart from a correct
        read. This detection is a best-effort first pass — needs_review /
        review_notes exist precisely so a low-confidence pass can't be
        confirmed without a human comparing it to the scanned sheet (see
        action_confirm_marks).
        """
        if not HAS_TESSERACT and not HAS_EASYOCR:
            return {}, 0, True, 'No OCR engine is installed (neither easyocr nor pytesseract) — nothing was detected automatically. Enter all marks manually.', [], 'None'

        easyocr_active = HAS_EASYOCR and _get_easyocr_reader() is not None
        engine_used = 'EasyOCR' if easyocr_active else ('Tesseract (fallback)' if HAS_TESSERACT else 'None')
        engine_note = []
        if easyocr_active:
            engine_note.append('Using OCR engine: EasyOCR (handwriting-capable).')
        elif HAS_TESSERACT:
            engine_note.append(
                'Using OCR engine: Tesseract only — EasyOCR is not active on this server, so '
                'handwritten-digit accuracy will be noticeably lower than it should be. Run '
                '"pip install easyocr" in the same Python environment as this Odoo server, then '
                'restart the server, to enable it.')

        layout = self._GRID_LAYOUT.get(self.valuation_part) or self._GRID_LAYOUT['valuation_1']
        scale_x = img.width / self.PAGE_W_REF
        scale_y = img.height / self.PAGE_H_REF

        marks_dict = {}
        unread_cells = []

        def read_cell(key, x0, y0, x1, y1):
            if self._cell_ink_density(img, x0, y0, x1, y1, scale_x, scale_y) <= self._INK_THRESHOLD:
                return  # genuinely blank — nothing written here
            val, conf = self._ocr_cell(img, x0, y0, x1, y1, scale_x, scale_y)
            if val is not None:
                marks_dict[key] = val
            else:
                unread_cells.append(key)

        # PART-A: single row, columns A-J (+ one unlabeled column) + Total.
        # NOTE: Part-A's own total cell is read into 'Q1PAtotal', NOT
        # 'Q1total' — 'Q1total' is Part-B question 1's total cell (read
        # below). Using the same key for both used to make Part-B silently
        # overwrite Part-A's total in marks_dict.
        a_y0, a_y1 = layout['part_a_row']
        for label, (x0, x1) in self._COLS_PART_A.items():
            key = 'Q1PAtotal' if label == 'total' else f'Q1{label}'
            read_cell(key, x0, a_y0, x1, a_y1)

        # PART-B: 6 printed rows, each holding two question numbers
        # side by side (odd on the left, even on the right).
        for q_left, q_right, y0, y1 in layout['part_b_rows']:
            for label, (x0, x1) in self._COLS_PART_B_LEFT.items():
                read_cell(f'Q{q_left}{label}', x0, y0, x1, y1)
            for label, (x0, x1) in self._COLS_PART_B_RIGHT.items():
                read_cell(f'Q{q_right}{label}', x0, y0, x1, y1)

        # GRAND TOTAL box (printed once, under the BEST column of the
        # last PART-B row) — this is the authoritative total the
        # examiner wrote, so prefer it over summing our own cell reads.
        gt_y0, gt_y1 = layout['grand_total_row']
        grand_total_ocr = None
        gt_conf = -1.0
        if self._cell_ink_density(img, self._BEST_COL[0], gt_y0, self._BEST_COL[1], gt_y1, scale_x, scale_y) > self._INK_THRESHOLD:
            grand_total_ocr, gt_conf = self._ocr_cell(
                img, self._BEST_COL[0], gt_y0, self._BEST_COL[1], gt_y1, scale_x, scale_y)

        # marks_dict also contains each question's own "...total" cell
        # (e.g. Q1total, the printed per-question total column) which
        # would double-count against that question's a/b/c/d cells if
        # included here, so exclude any key containing "total".
        sum_of_parts = sum(v for k, v in marks_dict.items() if 'total' not in k.lower())

        notes = []
        # Surface the degraded-accuracy warning prominently (and force a
        # review) whenever EasyOCR isn't the engine actually being used —
        # Tesseract-only results should never be trusted the way an
        # EasyOCR result can be. When EasyOCR *is* active, we don't add
        # noise here; its per-cell confidence already drives needs_review
        # via the unread/mismatch checks below.
        if HAS_TESSERACT and not easyocr_active:
            notes.extend(engine_note)
        if grand_total_ocr is not None:
            grand_total = grand_total_ocr
            # A lower partial sum is *expected* whenever some cells are
            # unread (they're simply missing from the sum, not wrong), so
            # only treat this as a suspicious mismatch when every cell
            # WAS read and it still doesn't add up — that's the case that
            # actually indicates a misread somewhere.
            if not unread_cells and sum_of_parts > 0 and abs(grand_total_ocr - sum_of_parts) > 2:
                notes.append(
                    f'Grand Total cell reads {grand_total_ocr}, but the question-wise '
                    f'cells that were read sum to {sum_of_parts}. One of them is '
                    f'likely wrong — check the Grand Total box on the sheet by eye.')
        else:
            grand_total = sum_of_parts
            notes.append(
                f'The Grand Total box on the sheet could not be read with confidence '
                f'(best guess confidence {gt_conf:.0f}/100) — Grand Total Marks was '
                f'filled in as {sum_of_parts}, the sum of the question-wise cells that '
                f'WERE read. Please read the Grand Total box on the sheet by eye and '
                f'correct this field if it differs.')

        if unread_cells:
            notes.append(
                f'{len(unread_cells)} cell(s) have handwriting in them that OCR could '
                f'not confidently read as a digit: {", ".join(sorted(unread_cells))}. '
                f'Look these up on the sheet and add them to Question-wise Marks '
                f'manually.')

        needs_review = bool(notes)
        review_notes = '\n'.join(notes)
        return marks_dict, grand_total, needs_review, review_notes, unread_cells, engine_used

    # ==================================================================
    # Bulk scan wizard entry point
    # ==================================================================
    @api.model
    def action_open_bulk_scan(self):
        """Open the bulk scanning wizard."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk OMR Scan'),
            'res_model': 'exam.omr.bulk.scan.wizard',
            'view_mode': 'form',
            'target': 'new',
        }