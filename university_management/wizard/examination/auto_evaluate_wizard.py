# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardAutoEvaluateExam(models.TransientModel):
    _name = 'wizard.auto.evaluate.exam'
    _description = 'Auto Evaluate Online Exam Attempts'

    online_exam_id = fields.Many2one('online.exam', string='Online Exam', required=True)

    state_filter = fields.Selection([
        ('submitted', 'Submitted (not yet evaluated)'),
        ('all', 'All non-draft attempts'),
    ], string='Evaluate', default='submitted', required=True)

    evaluated_count = fields.Integer(string='Attempts Evaluated', readonly=True)
    done = fields.Boolean(default=False)

    def action_evaluate(self):
        self.ensure_one()
        domain = [('online_exam_id', '=', self.online_exam_id.id)]
        if self.state_filter == 'submitted':
            domain.append(('state', '=', 'submitted'))
        else:
            domain.append(('state', 'in', ('submitted', 'evaluated')))

        attempts = self.env['online.exam.attempt'].search(domain)
        if not attempts:
            raise UserError(_('No attempts found matching the selected criteria.'))

        for attempt in attempts:
            attempt.auto_evaluate()

        self.write({'evaluated_count': len(attempts), 'done': True})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.auto.evaluate.exam',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }