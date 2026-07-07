# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class NAACSSR(models.Model):
    _name = 'naac.ssr'
    _description = 'NAAC Self Study Report (SSR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'accreditation_cycle desc'

    name = fields.Char(string='SSR Reference', readonly=True, copy=False, default='/')
    accreditation_cycle = fields.Char(string='Accreditation Cycle', required=True,
                                       help='e.g. 3rd Cycle 2024-25')
    from_year = fields.Char(string='From Year')
    to_year = fields.Char(string='To Year')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('data_collection', 'Data Collection'),
        ('iqac_review', 'IQAC Review'),
        ('management_review', 'Management Review'),
        ('finalized', 'Finalized'),
        ('submitted', 'Submitted to NAAC'),
    ], string='Status', default='draft', tracking=True)

    # Executive Summary
    executive_summary = fields.Html(string='Executive Summary')
    institutional_profile = fields.Html(string='Institutional Profile')

    # Criterion summaries
    criterion1_ssr = fields.Html(string='Criterion 1: Curricular Aspects')
    criterion2_ssr = fields.Html(string='Criterion 2: Teaching Learning & Evaluation')
    criterion3_ssr = fields.Html(string='Criterion 3: Research Innovation & Extension')
    criterion4_ssr = fields.Html(string='Criterion 4: Infrastructure & Learning Resources')
    criterion5_ssr = fields.Html(string='Criterion 5: Student Support & Progression')
    criterion6_ssr = fields.Html(string='Criterion 6: Governance Leadership & Management')
    criterion7_ssr = fields.Html(string='Criterion 7: Institutional Values & Best Practices')

    # Evidence summary
    total_evidence_docs = fields.Integer(string='Total Evidence Documents',
                                          compute='_compute_evidence_summary', store=True)
    evidence_summary = fields.Text(string='Evidence Summary')

    # AQAR references
    aqar_ids = fields.Many2many('naac.aqar', string='Referenced AQARs')

    prepared_by = fields.Many2one('res.users', string='Prepared By',
                                   default=lambda self: self.env.uid)
    approved_by = fields.Many2one('res.users', string='Final Approval By')
    finalized_date = fields.Datetime(string='Finalized Date')

    notes = fields.Text(string='Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('naac.ssr') or '/'
        return super().create(vals)

    def _compute_evidence_summary(self):
        for rec in self:
            rec.total_evidence_docs = self.env['naac.evidence'].search_count([])

    def action_generate_from_aqar(self):
        """Pull data from linked AQARs into SSR."""
        for rec in self:
            if rec.aqar_ids:
                summaries = []
                for aqar in rec.aqar_ids:
                    summaries.append(f'<h3>{aqar.academic_year_id.name}</h3>')
                    if aqar.criterion3_summary:
                        summaries.append(aqar.criterion3_summary)
                rec.criterion3_ssr = ''.join(summaries)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SSR Data Pulled'),
                'message': _('SSR has been populated from linked AQAR records.'),
                'type': 'success',
            }
        }

    def action_start_collection(self):
        self.write({'state': 'data_collection'})

    def action_submit_for_review(self):
        self.write({'state': 'iqac_review'})

    def action_submit_to_naac(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'management_review',
            'approved_by': self.env.uid,
        })

    def action_submit_iqac(self):
        self.write({'state': 'iqac_review'})

    def action_finalize(self):
        self.write({
            'state': 'finalized',
            'approved_by': self.env.uid,
            'finalized_date': fields.Datetime.now(),
        })

    def action_submit_naac(self):
        self.write({'state': 'submitted'})