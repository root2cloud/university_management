# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MessMenu(models.Model):
    _name = 'mess.menu'
    _description = 'Mess Daily/Weekly Menu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, meal_type'

    name = fields.Char(string='Menu Name', compute='_compute_name', store=True)

    # Mess
    mess_id = fields.Many2one('hostel.mess', string='Mess', required=True, index=True)

    # Date
    date = fields.Date(string='Date', default=fields.Date.today(), required=True)
    day_of_week = fields.Selection([
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ], string='Day', compute='_compute_day', store=True)

    # Meal Type
    meal_type = fields.Selection([
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('snacks', 'Snacks'),
        ('dinner', 'Dinner'),
    ], string='Meal Type', required=True)

    # Menu Items (using product.product from stock module)
    item_ids = fields.Many2many('mess.item', string='Menu Items')

    # Description
    description = fields.Html(string='Description')

    _sql_constraints = [
        ('unique_menu', 'unique(mess_id, date, meal_type)',
         'Menu already exists for this mess, date and meal type!'),
    ]

    @api.depends('mess_id', 'date', 'meal_type')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.mess_id.name} - {record.date} - {record.meal_type}"

    @api.depends('date')
    def _compute_day(self):
        for record in self:
            if record.date:
                day_num = record.date.weekday()
                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                record.day_of_week = days[day_num]
            else:
                record.day_of_week = False
