# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import logging

_logger = logging.getLogger(__name__)


class BulkOMRScanWizard(models.TransientModel):
    """
    Wizard to upload and process multiple scanned OMR sheets at once.
    Each uploaded file is created as an exam.omr.scanner record
    and processed (barcode decode → OCR → confirm).
    """
    _name = 'exam.omr.bulk.scan.wizard'
    _description = 'Bulk OMR Scan Wizard'

    examination_id = fields.Many2one('examination.examination',
                                     string='Examination (optional)',
                                     help='Pre-fill examination for all scans.')
    subject_id = fields.Many2one('university.subject',
                                 string='Subject (optional)')

    valuation_part = fields.Selection([
        ('valuation_1', 'Valuation 1 (Part-II)'),
        ('revaluation', 'Re-Valuation (Part-III)'),
    ], string='Valuation Part', default='valuation_1')

    scan_line_ids = fields.One2many('exam.omr.bulk.scan.wizard.line', 'wizard_id',
                                    string='Scanned Files')

    # Not stored, not used server-side. It only exists so the
    # "bulk_omr_multi_upload" JS widget has a field to attach to and can
    # let the user pick/drop many files (e.g. 100 PDFs) at once; each
    # selected file is turned into a scan_line_ids record automatically.
    bulk_upload_helper = fields.Binary(string='Upload Multiple Scanned Sheets',
                                       store=False)

    auto_confirm = fields.Boolean(string='Auto-Confirm Marks', default=False,
                                  help='Automatically confirm and update results after OCR.')

    def action_process(self):
        """Process all uploaded scan files."""
        self.ensure_one()
        if not self.scan_line_ids:
            raise UserError(_('Please upload at least one scanned OMR sheet.'))

        Scanner = self.env['exam.omr.scanner']
        created_ids = []

        for line in self.scan_line_ids:
            if not line.scanned_file:
                continue

            vals = {
                'scanned_file': line.scanned_file,
                'scanned_filename': line.scanned_filename,
                'valuation_part': self.valuation_part,
            }
            scan = Scanner.create(vals)

            # Step 1: Decode barcode
            try:
                scan.action_decode_barcode()
            except Exception as e:
                _logger.warning('Barcode decode failed for %s: %s',
                                line.scanned_filename, e)

            # If exam/subject not decoded, use wizard defaults
            if not scan.examination_id and self.examination_id:
                scan.examination_id = self.examination_id.id
            if not scan.subject_id and self.subject_id:
                scan.subject_id = self.subject_id.id

            # Step 2: Detect marks
            if scan.state == 'decoded':
                try:
                    scan.action_detect_marks()
                except Exception as e:
                    _logger.warning('OCR marks detection failed for %s: %s',
                                    line.scanned_filename, e)

            # Step 3: Auto-confirm
            if self.auto_confirm and scan.state == 'ocr_done':
                try:
                    scan.action_confirm_marks()
                except Exception as e:
                    _logger.warning('Auto-confirm failed for %s: %s',
                                    line.scanned_filename, e)

            created_ids.append(scan.id)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Processed Scans (%d)') % len(created_ids),
            'res_model': 'exam.omr.scanner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_ids)],
            'target': 'current',
        }


class BulkOMRScanWizardLine(models.TransientModel):
    _name = 'exam.omr.bulk.scan.wizard.line'
    _description = 'Bulk OMR Scan Wizard Line'

    wizard_id = fields.Many2one('exam.omr.bulk.scan.wizard', ondelete='cascade')
    scanned_file = fields.Binary(string='Scanned File', required=True)
    scanned_filename = fields.Char(string='Filename')