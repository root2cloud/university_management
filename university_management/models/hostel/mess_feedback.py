# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MessFeedback(models.Model):
    _name = 'mess.feedback'
    _description = 'Mess Food Feedback'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'feedback_date desc'

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True)

    # Mess
    mess_id = fields.Many2one('hostel.mess', string='Mess', required=True)

    # Feedback Date
    feedback_date = fields.Date(string='Feedback Date', default=fields.Date.today())

    # Rating
    rating = fields.Selection([
        ('1', 'Very Poor'),
        ('2', 'Poor'),
        ('3', 'Average'),
        ('4', 'Good'),
        ('5', 'Excellent'),
    ], string='Rating', required=True, tracking=True)

    # Feedback Categories
    food_quality = fields.Selection([
        ('1', 'Very Poor'), ('2', 'Poor'), ('3', 'Average'), ('4', 'Good'), ('5', 'Excellent')
    ], string='Food Quality')

    taste = fields.Selection([
        ('1', 'Very Poor'), ('2', 'Poor'), ('3', 'Average'), ('4', 'Good'), ('5', 'Excellent')
    ], string='Taste')

    cleanliness = fields.Selection([
        ('1', 'Very Poor'), ('2', 'Poor'), ('3', 'Average'), ('4', 'Good'), ('5', 'Excellent')
    ], string='Cleanliness')

    service = fields.Selection([
        ('1', 'Very Poor'), ('2', 'Poor'), ('3', 'Average'), ('4', 'Good'), ('5', 'Excellent')
    ], string='Service')

    # Comments
    comments = fields.Text(string='Comments/Suggestions')
