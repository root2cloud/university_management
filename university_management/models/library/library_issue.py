# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class LibraryIssue(models.Model):
    _name = 'library.issue'
    _description = 'Library Book Issue/Return Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc'

    name = fields.Char(string='Issue Number', required=True, readonly=True,
                       copy=False, default='/')

    # Member
    member_id = fields.Many2one('library.member', string='Member',
                                required=True, tracking=True, index=True)
    member_name = fields.Char(related='member_id.member_name', string='Member Name')
    member_type = fields.Selection(related='member_id.member_type', string='Member Type')

    # Book
    book_id = fields.Many2one('library.book', string='Book',
                              required=True, tracking=True, index=True,
                              domain=[('state', '=', 'available')])
    isbn = fields.Char(related='book_id.isbn', string='ISBN')

    # Issue Details
    issue_date = fields.Date(string='Issue Date', default=fields.Date.today(),
                             required=True, tracking=True)
    due_date = fields.Date(string='Due Date', required=True, tracking=True)
    return_date = fields.Date(string='Return Date', tracking=True)

    # Days
    issue_days = fields.Integer(string='Issue Days', compute='_compute_days')
    overdue_days = fields.Integer(string='Overdue Days', compute='_compute_overdue')

    # Issued By
    issued_by = fields.Many2one('res.users', string='Issued By',
                                default=lambda self: self.env.user, readonly=True)

    # Return Details
    returned_by = fields.Many2one('res.users', string='Returned By', readonly=True)

    # Book Condition
    issue_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ], string='Condition at Issue', default='good')

    return_condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ], string='Condition at Return')

    # Fine
    fine_id = fields.Many2one('library.fine', string='Fine', readonly=True)
    fine_amount = fields.Monetary(string='Fine Amount', currency_field='currency_id')
    fine_paid = fields.Boolean(string='Fine Paid')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('overdue', 'Overdue'),
        ('returned', 'Returned'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
    ], string='Status', default='issued', tracking=True, compute='_compute_state', store=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Issue Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('library.issue') or '/'
        return super(LibraryIssue, self).create(vals)

    @api.onchange('member_id', 'issue_date')
    def _onchange_due_date(self):
        if self.member_id and self.issue_date:
            self.due_date = self.issue_date + timedelta(days=self.member_id.max_issue_days)

    @api.depends('issue_date', 'return_date', 'due_date')
    def _compute_days(self):
        for record in self:
            if record.return_date:
                record.issue_days = (record.return_date - record.issue_date).days
            else:
                record.issue_days = (fields.Date.today() - record.issue_date).days

    @api.depends('due_date', 'return_date')
    def _compute_overdue(self):
        today = fields.Date.today()
        for record in self:
            record.overdue_days = 0  # default

            # avoid comparing date with False when due_date is not yet set
            if not record.due_date:
                continue

            if record.state in ['issued', 'overdue']:
                if today > record.due_date:
                    record.overdue_days = (today - record.due_date).days
            elif record.return_date and record.return_date > record.due_date:
                record.overdue_days = (record.return_date - record.due_date).days


    @api.depends('due_date' , 'return_date')
    def _compute_state(self):
        today = fields.Date.today()
        for record in self:
            if record.return_date:
                record.state = 'returned'
            elif today > record.due_date:
                record.state = 'overdue'
            else:
                record.state = 'issued'

    @api.constrains('member_id', 'book_id')
    def _check_issue_limit(self):
        for record in self:
            if record.member_id.current_issues >= record.member_id.max_books_allowed:
                raise ValidationError(_('Member has reached maximum book issue limit!'))

    @api.constrains('member_id')
    def _check_pending_fines(self):
        for record in self:
            if record.member_id.pending_fine > 0:
                raise ValidationError(_('Member has pending fines! Please clear before issuing new books.'))

    def action_confirm(self):
        """Confirm the issue (move from draft to issued)"""
        self.write({'state': 'issued'})

    def action_return_book(self):
        """Return book"""
        self.ensure_one()

        # Calculate fine if overdue
        if self.overdue_days > 0:
            fine_per_day = 5.0  # Fine amount per day
            fine_amount = self.overdue_days * fine_per_day

            fine = self.env['library.fine'].create({
                'member_id': self.member_id.id,
                'issue_id': self.id,
                'fine_type': 'overdue',
                'amount': fine_amount,
                'reason': f"Overdue for {self.overdue_days} days"
            })

            self.write({
                'fine_id': fine.id,
                'fine_amount': fine_amount
            })

        self.write({
            'return_date': fields.Date.today(),
            'returned_by': self.env.user.id,
            'state': 'returned'
        })

    def action_mark_lost(self):
        """Mark book as lost"""
        self.write({'state': 'lost'})

    def action_mark_damaged(self):
        """Mark book as damaged"""
        self.write({'state': 'damaged'})

    def action_reset_to_draft(self):
        """Reset issue to draft state"""
        self.write({
            'state': 'draft',
            'return_date': False,
            'returned_by': False,
            'return_condition': False,
            'fine_id': False,
            'fine_amount': False,
            'fine_paid': False
        })

    @api.model
    def _cron_check_overdue_books(self):
        """Scheduled action to check overdue books and send reminders"""
        today = fields.Date.today()
        overdue_issues = self.search([
            ('state', '=', 'issued'),
            ('due_date', '<', today)
        ])

        for issue in overdue_issues:
            issue.write({'state': 'overdue'})
            # Send reminder email
            template = self.env.ref('university_management.email_template_overdue_book',
                                    raise_if_not_found=False)
            if template:
                template.send_mail(issue.id, force_send=True)
