# -*- coding: utf-8 -*-

from odoo import models, fields

MONTH_SELECTION = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Fix 1: Missing field from Project module ──────────────────────────
    internal_project_id = fields.Many2one(
        'project.project',
        string='Internal Project',
        help='Project used for internal tasks.',
        config_parameter='project.default_project_id',
    )

    # ── Fix 2: Missing field from project_timesheet_holidays module ───────
    leave_timesheet_task_id = fields.Many2one(
        'project.task',
        string='Leave Timesheet Task',
        help='Task used to record timesheets for employee leaves.',
        config_parameter='project_timesheet_holidays.leave_timesheet_task_id',
    )

    # ── Fix 3: Add missing Jitsi field ────────────────────────────────────
    jitsi_server_domain = fields.Char(
        string='Jitsi Server Domain',
        help="Jitsi server domain (e.g., meet.jit.si)",
        config_parameter='jitsi.server_domain',
    )

    # HR settings compatibility fields
    notice_period = fields.Boolean(
        string='Enable Notice Period',
        config_parameter='university_management.notice_period',
    )
    no_of_days = fields.Integer(
        string='Notice Period Days',
        default=0,
        config_parameter='university_management.notice_period_days',
    )

    # Accounting settings compatibility fields
    # In many Odoo builds these are related fields on res.company.
    group_fiscal_year = fields.Boolean(
        string='Fiscal Years',
        implied_group='base.group_user',
    )
    fiscalyear_lock_date = fields.Date(
        string='Fiscal Year Lock Date',
        related='company_id.fiscalyear_lock_date',
        readonly=False,
    )
    sale_lock_date = fields.Date(string='Sales Lock Date')
    purchase_lock_date = fields.Date(string='Purchase Lock Date')
    tax_lock_date = fields.Date(string='Tax Lock Date')
    hard_lock_date = fields.Date(string='Hard Lock Date')
    fiscalyear_last_month = fields.Selection(
        MONTH_SELECTION,
        string='Fiscal Year Last Month',
        related='company_id.fiscalyear_last_month',
        readonly=False,
    )
    fiscalyear_last_day = fields.Integer(
        string='Fiscal Year Last Day',
        related='company_id.fiscalyear_last_day',
        readonly=False,
    )