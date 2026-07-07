# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class NAACAQAR(models.Model):
    _name = 'naac.aqar'
    _description = 'NAAC Annual Quality Assurance Report (AQAR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'academic_year_id desc'

    name = fields.Char(string='AQAR Reference', readonly=True, copy=False, default='/')
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year', required=True, tracking=True)

    from_date = fields.Date(string='From Date')
    to_date = fields.Date(string='To Date')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('iqac_review', 'IQAC Review'),
        ('approved', 'Approved'),
        ('submitted', 'Submitted to NAAC'),
    ], string='Status', default='draft', tracking=True)

    # Institution info
    institute_name = fields.Char(string='Institution Name')
    naac_id = fields.Char(string='NAAC ID')
    accreditation_grade = fields.Char(string='Current Grade')
    iqac_coordinator = fields.Many2one('res.users', string='IQAC Coordinator')

    # Criterion wise data
    criterion1_summary = fields.Html(string='Criterion 1: Curricular Aspects')
    criterion2_summary = fields.Html(string='Criterion 2: Teaching Learning & Evaluation')
    criterion3_summary = fields.Html(string='Criterion 3: Research Innovation & Extension')
    criterion4_summary = fields.Html(string='Criterion 4: Infrastructure & Learning Resources')
    criterion5_summary = fields.Html(string='Criterion 5: Student Support & Progression')
    criterion6_summary = fields.Html(string='Criterion 6: Governance Leadership & Management')
    criterion7_summary = fields.Html(string='Criterion 7: Institutional Values & Best Practices')

    # Key Indicators
    total_faculty = fields.Integer(string='Total Faculty')
    total_students = fields.Integer(string='Total Students')
    total_programs = fields.Integer(string='Total Programs')
    placement_percentage = fields.Float(string='Placement %', digits=(5, 2))
    research_papers = fields.Integer(string='Research Papers Published')
    patents_filed = fields.Integer(string='Patents Filed')

    # Approval
    prepared_by = fields.Many2one('res.users', string='Prepared By',
                                   default=lambda self: self.env.uid)
    approved_by = fields.Many2one('res.users', string='Approved By')
    approved_date = fields.Datetime(string='Approved Date')

    notes = fields.Text(string='Additional Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('naac.aqar') or '/'
        return super().create(vals)

    def action_generate_data(self):
        """Auto-populate AQAR fields from ERP data."""
        for rec in self:
            # Get academic year ID first — used in all filtered queries below
            year_id = rec.academic_year_id.id if rec.academic_year_id else False

            # Count global stats from ERP
            rec.total_faculty = self.env['faculty.faculty'].search_count([('active', '=', True)])
            rec.total_students = self.env['student.student'].search_count([('active', '=', True)])
            rec.total_programs = self.env['university.program'].search_count([('active', '=', True)])

            # Year-specific stats
            research_domain = [('research_type', 'in', ['journal_paper', 'conference_paper']),
                                ('state', '=', 'verified')]
            patent_domain = [('research_type', 'in', ['patent_filed', 'patent_granted'])]
            if year_id:
                research_domain.insert(0, ('academic_year_id', '=', year_id))
                patent_domain.insert(0, ('academic_year_id', '=', year_id))

            rec.research_papers = self.env['naac.faculty.research'].search_count(research_domain)
            rec.patents_filed = self.env['naac.faculty.research'].search_count(patent_domain)

            # Placement % from student progression
            # naac.student.progression uses year (Char) not academic_year_id
            year_name = rec.academic_year_id.name if rec.academic_year_id else False
            if year_name:
                total_placed = self.env['naac.student.progression'].search_count([
                    ('year', '=', year_name),
                    ('progression_type', '=', 'placement'),
                    ('state', '=', 'verified'),
                ])
                total_students = rec.total_students or 1
                rec.placement_percentage = round(total_placed / total_students * 100, 2)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AQAR Data Generated'),
                'message': _('AQAR data has been auto-populated from ERP records.'),
                'type': 'success',
            }
        }

    def action_start_collection(self):
        self.write({'state': 'in_progress'})

    def action_submit_for_review(self):
        self.write({'state': 'iqac_review'})

    def action_submit_iqac(self):
        self.write({'state': 'iqac_review'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.uid,
            'approved_date': fields.Datetime.now(),
        })

    def action_submit_naac(self):
        self.write({'state': 'submitted'})

    def action_print_aqar(self):
        return self.env.ref(
            'university_management.action_report_naac_aqar'
        ).report_action(self)