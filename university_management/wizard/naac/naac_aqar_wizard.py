# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class NAACAgARWizard(models.TransientModel):
    _name = 'naac.aqar.wizard'
    _description = 'NAAC AQAR Generation Wizard'

    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    institute_name = fields.Char(string='Institution Name')
    iqac_coordinator = fields.Many2one('res.users', string='IQAC Coordinator',
                                        default=lambda self: self.env.uid)

    def action_generate_aqar(self):
        self.ensure_one()
        # Create AQAR record
        aqar = self.env['naac.aqar'].create({
            'academic_year_id': self.academic_year_id.id,
            'from_date': self.from_date,
            'to_date': self.to_date,
            'institute_name': self.institute_name,
            'iqac_coordinator': self.iqac_coordinator.id,
            'state': 'in_progress',
        })
        # Auto generate data
        aqar.action_generate_data()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'naac.aqar',
            'view_mode': 'form',
            'res_id': aqar.id,
        }
