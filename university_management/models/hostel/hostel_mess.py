# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HostelMess(models.Model):
    _name = 'hostel.mess'
    _description = 'Hostel Mess/Canteen Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Mess Name', required=True, tracking=True)
    code = fields.Char(string='Mess Code', required=True)

    # Hostel
    hostel_ids = fields.Many2many('hostel.hostel', string='Attached to Hostels')

    # Manager
    manager_id = fields.Many2one('res.users', string='Mess Manager', tracking=True)

    # Capacity
    seating_capacity = fields.Integer(string='Seating Capacity')

    # Meal Times
    breakfast_time = fields.Char(string='Breakfast Time', default='07:00 AM - 09:00 AM')
    lunch_time = fields.Char(string='Lunch Time', default='12:00 PM - 02:00 PM')
    dinner_time = fields.Char(string='Dinner Time', default='07:00 PM - 09:00 PM')

    # Menu
    menu_ids = fields.One2many('mess.menu', 'mess_id', string='Weekly Menu')

    # Feedback
    feedback_ids = fields.One2many('mess.feedback', 'mess_id', string='Feedback')
    average_rating = fields.Float(string='Average Rating', compute='_compute_rating', store=True, digits=(3, 2))

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='active', tracking=True)

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Mess Code must be unique!'),
    ]

    @api.depends('feedback_ids', 'feedback_ids.rating')
    def _compute_rating(self):
        for record in self:
            if record.feedback_ids:
                # Get all ratings as strings, convert to integers, then calculate average
                ratings = record.feedback_ids.mapped('rating')
                # Filter out False/None values and convert to integers
                numeric_ratings = [int(rating) for rating in ratings if rating]
                if numeric_ratings:
                    record.average_rating = sum(numeric_ratings) / len(numeric_ratings)
                else:
                    record.average_rating = 0.0
            else:
                record.average_rating = 0.0

    # Workflow Actions
    def action_activate(self):
        """Activate the mess (move from draft to active)"""
        self.write({'state': 'active'})

    def action_close(self):
        """Close the mess"""
        self.write({'state': 'closed'})

    def action_reset_to_draft(self):
        """Reset mess to draft state"""
        self.write({'state': 'draft'})