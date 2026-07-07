# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class NAACEvidenceBulkWizard(models.TransientModel):
    _name = 'naac.evidence.bulk.wizard'
    _description = 'NAAC Bulk Evidence Tagging Wizard'

    criterion_id = fields.Many2one('naac.criterion', string='NAAC Criterion', required=True)
    metric_id = fields.Many2one('naac.metric', string='Metric',
                                 domain="[('criterion_id', '=', criterion_id)]")
    department_id = fields.Many2one('university.department', string='Department')
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Evidence to bulk upload
    evidence_line_ids = fields.One2many('naac.evidence.bulk.wizard.line', 'wizard_id',
                                         string='Evidence Files')

    def action_save_evidence(self):
        for line in self.evidence_line_ids:
            self.env['naac.evidence'].create({
                'name': line.name,
                'criterion_id': self.criterion_id.id,
                'metric_id': self.metric_id.id if self.metric_id else False,
                'department_id': self.department_id.id if self.department_id else False,
                'academic_year_id': self.academic_year_id.id,
                'doc_type': line.doc_type,
                'document': line.document,
                'document_filename': line.document_filename,
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Evidence Uploaded'),
                'message': _('%d evidence files have been saved.') % len(self.evidence_line_ids),
                'type': 'success',
            }
        }


class NAACEvidenceBulkWizardLine(models.TransientModel):
    _name = 'naac.evidence.bulk.wizard.line'
    _description = 'NAAC Evidence Bulk Wizard Line'

    wizard_id = fields.Many2one('naac.evidence.bulk.wizard', required=True, ondelete='cascade')
    name = fields.Char(string='Evidence Title', required=True)
    doc_type = fields.Selection([
        ('photo', 'Photograph'),
        ('pdf_report', 'PDF Report'),
        ('attendance_sheet', 'Attendance Sheet'),
        ('mou', 'MoU Document'),
        ('research_paper', 'Research Paper'),
        ('certificate', 'Certificate'),
        ('other', 'Other'),
    ], string='Document Type', required=True, default='pdf_report')
    document = fields.Binary(string='File', attachment=True, required=True)
    document_filename = fields.Char(string='Filename')
