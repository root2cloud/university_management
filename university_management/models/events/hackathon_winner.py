# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HackathonWinner(models.Model):
    _name = 'hackathon.winner'
    _description = 'Hackathon Winners'
    _order = 'position'

    # Hackathon
    hackathon_id = fields.Many2one('hackathon.hackathon', string='Hackathon',
                                   required=True, index=True, ondelete='cascade')

    # Team
    team_id = fields.Many2one('hackathon.team', string='Winning Team',
                              required=True, tracking=True)

    # Position
    position = fields.Selection([
        ('1', 'First Prize'),
        ('2', 'Second Prize'),
        ('3', 'Third Prize'),
        ('special', 'Special Mention'),
    ], string='Position', required=True, tracking=True)

    # Prize
    prize_amount = fields.Monetary(string='Prize Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Certificate
    certificate = fields.Binary(string='Certificate', attachment=True)

    # Remarks
    remarks = fields.Text(string='Remarks')
