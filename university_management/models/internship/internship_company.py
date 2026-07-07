# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class InternshipCompany(models.Model):
    _name = 'internship.company'
    _description = 'Internship Company Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}  # Integration with contacts
    _order = 'name'

    # Partner (for contact details)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 required=True, ondelete='cascade', auto_join=True)

    # Industry
    industry = fields.Selection([
        ('it', 'IT/Software'),
        ('core', 'Core Engineering'),
        ('finance', 'Finance/Banking'),
        ('consulting', 'Consulting'),
        ('manufacturing', 'Manufacturing'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('startup', 'Startup'),
        ('other', 'Other'),
    ], string='Industry')

    # HR Contact
    hr_contact_name = fields.Char(string='HR Contact Name')
    hr_contact_email = fields.Char(string='HR Email')
    hr_contact_phone = fields.Char(string='HR Phone')

    # Internship History
    internship_ids = fields.One2many('internship.internship', 'company_id', string='Internships')
    total_internships = fields.Integer(string='Total Internships', compute='_compute_total', store=True)

    # Rating
    rating = fields.Selection([
        ('1', '1 Star'), ('2', '2 Stars'), ('3', '3 Stars'),
        ('4', '4 Stars'), ('5', '5 Stars'),
    ], string='Rating')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('internship_ids')
    def _compute_total(self):
        for record in self:
            record.total_internships = len(record.internship_ids)

    def action_view_internships(self):
        """Open the list of internships for this company."""
        self.ensure_one()
        return {
            'name': _('Internships'),
            'type': 'ir.actions.act_window',
            'res_model': 'internship.internship',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {'default_company_id': self.id},
        }
