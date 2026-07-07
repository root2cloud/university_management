# -*- coding: utf-8 -*-

from odoo import models, fields, api


class IICApprovalLog(models.Model):
    _name = 'iic.approval.log'
    _description = 'IIC Approval / Action Log'
    _order = 'create_date desc'

    event_id = fields.Many2one('iic.event', string='Event', required=True, ondelete='cascade')
    action = fields.Char(string='Action', required=True)
    user_id = fields.Many2one('res.users', string='Performed By', default=lambda self: self.env.user)
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now)
    remarks = fields.Text(string='Remarks')
