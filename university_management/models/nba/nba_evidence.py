# -*- coding: utf-8 -*-
from odoo import models, fields, api


class NBAEvidence(models.Model):
    _name = 'nba.evidence'
    _description = 'NBA Evidence Vault'
    _order = 'sar_id, criterion, name'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Document Title', required=True)
    criterion = fields.Selection([
        ('c1', 'C1 - Curriculum'),
        ('c2', 'C2 - Teaching-Learning'),
        ('c3', 'C3 - Assessment'),
        ('c4', 'C4 - Students'),
        ('c5', 'C5 - Faculty Info'),
        ('c6', 'C6 - Contributions'),
        ('c7', 'C7 - Facilities'),
        ('c8', 'C8 - Improvement'),
        ('c9', 'C9 - Governance'),
        ('general', 'General'),
    ], string='Criterion', required=True, default='general')
    sub_section = fields.Char(string='Sub-Section', help='e.g., 1.1.3, 4.7.4')
    document_type = fields.Selection([
        ('policy', 'Policy Document'),
        ('minutes', 'Meeting Minutes'),
        ('report', 'Report'),
        ('certificate', 'Certificate'),
        ('photo', 'Photo / Screenshot'),
        ('data_sheet', 'Data Sheet / Table'),
        ('other', 'Other'),
    ], string='Document Type', default='other')
    document_file = fields.Binary(string='File', attachment=True)
    document_filename = fields.Char(string='Filename')
    document_url = fields.Char(string='URL / Link')
    upload_date = fields.Date(string='Upload Date', default=fields.Date.today)
    uploaded_by = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.uid)
    verified = fields.Boolean(string='Verified', default=False)
    notes = fields.Text(string='Notes')