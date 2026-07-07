# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HackathonJudge(models.Model):
    _name = 'hackathon.judge'
    _description = 'Hackathon Judges'
    _order = 'name'

    name = fields.Char(string='Judge Name', required=True)

    # Judge Type
    judge_type = fields.Selection([
        ('internal', 'Internal Faculty'),
        ('external', 'External Expert'),
        ('industry', 'Industry Professional'),
    ], string='Judge Type', required=True)

    # Faculty (if internal)
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty')

    # External Details
    designation = fields.Char(string='Designation')
    company = fields.Char(string='Company/Organization')
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')

    # Expertise
    expertise = fields.Text(string='Area of Expertise')

    # Photo
    photo = fields.Binary(string='Photo', attachment=True)

    # Bio
    bio = fields.Html(string='Biography')
