# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NAACEvidence(models.Model):
    _name = 'naac.evidence'
    _description = 'NAAC Evidence Document'
    _order = 'create_date desc'

    name = fields.Char(string='Document Title', required=True)
    activity_id = fields.Many2one('naac.department.activity', string='Activity', ondelete='cascade')
    criterion_id = fields.Many2one('naac.criterion', string='NAAC Criterion', required=True)
    metric_id = fields.Many2one('naac.metric', string='NAAC Metric',
                                 domain="[('criterion_id', '=', criterion_id)]")
    department_id = fields.Many2one('university.department', string='Department')
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    doc_type = fields.Selection([
        ('photo', 'Photo'),
        ('pdf_report', 'PDF Report'),
        ('attendance_sheet', 'Attendance Sheet'),
        ('mou', 'MoU Document'),
        ('research_paper', 'Research Paper'),
        ('media_coverage', 'Media Coverage'),
        ('certificate', 'Certificate / Award'),
        ('brochure', 'Brochure / Flyer'),
        ('other', 'Other'),
    ], string='Document Type', required=True)

    document = fields.Binary(string='Upload Document', attachment=True, required=True)
    document_filename = fields.Char(string='Filename')
    description = fields.Text(string='Document Description')
    tags = fields.Char(string='Tags')

    uploaded_by = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.user)
    upload_date = fields.Datetime(string='Upload Date', default=fields.Datetime.now)

    is_verified = fields.Boolean(string='Verified', default=False)
    verified_by = fields.Many2one('res.users', string='Verified By')

    # Add the missing verified_date field
    verified_date = fields.Datetime(string='Verified Date')

    # Add the missing file_size field
    file_size = fields.Integer(string='File Size', compute='_compute_file_size', store=False)

    # Add the missing reference field
    reference = fields.Char(string='Reference',
                            default=lambda self: self.env['ir.sequence'].next_by_code('naac.evidence') or 'New')

    @api.depends('document')
    def _compute_file_size(self):
        for record in self:
            if record.document:
                # Approximate file size calculation (base64 string length * 0.75 gives approximate bytes)
                record.file_size = int(len(record.document) * 0.75)
            else:
                record.file_size = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('naac.evidence') or 'New'
        return super().create(vals_list)

    def action_verify(self):
        """Mark the evidence as verified"""
        for record in self:
            record.is_verified = True
            record.verified_by = self.env.user.id
            record.verified_date = fields.Datetime.now()
        return True
