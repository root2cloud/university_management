# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class NBAEvidenceBulkWizard(models.TransientModel):
    _name = 'nba.evidence.bulk.wizard'
    _description = 'NBA Bulk Evidence Upload Wizard'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True)
    criterion = fields.Selection([
        ('c1', 'C1 - Curriculum'), ('c2', 'C2 - Teaching-Learning'),
        ('c3', 'C3 - Assessment'), ('c4', 'C4 - Students'),
        ('c5', 'C5 - Faculty Info'), ('c6', 'C6 - Contributions'),
        ('c7', 'C7 - Facilities'), ('c8', 'C8 - Improvement'),
        ('c9', 'C9 - Governance'), ('general', 'General'),
    ], string='Criterion', required=True, default='general')
    sub_section = fields.Char(string='Sub-Section')
    line_ids = fields.One2many('nba.evidence.bulk.wizard.line', 'wizard_id', string='Files')

    def action_upload(self):
        self.ensure_one()
        for line in self.line_ids:
            if line.document_file:
                self.env['nba.evidence'].create({
                    'sar_id': self.sar_id.id,
                    'name': line.name or line.document_filename or 'Document',
                    'criterion': self.criterion,
                    'sub_section': self.sub_section,
                    'document_file': line.document_file,
                    'document_filename': line.document_filename,
                    'document_type': line.document_type,
                })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Upload Complete'),
                'message': _('%d evidence document(s) uploaded.') % len(self.line_ids),
                'type': 'success',
            }
        }


class NBAEvidenceBulkWizardLine(models.TransientModel):
    _name = 'nba.evidence.bulk.wizard.line'
    _description = 'NBA Evidence Bulk Wizard Line'

    wizard_id = fields.Many2one('nba.evidence.bulk.wizard', string='Wizard', ondelete='cascade')
    name = fields.Char(string='Title')
    document_file = fields.Binary(string='File', attachment=False)
    document_filename = fields.Char(string='Filename')
    document_type = fields.Selection([
        ('policy', 'Policy'), ('minutes', 'Minutes'), ('report', 'Report'),
        ('certificate', 'Certificate'), ('photo', 'Photo'),
        ('data_sheet', 'Data Sheet'), ('other', 'Other'),
    ], string='Type', default='other')