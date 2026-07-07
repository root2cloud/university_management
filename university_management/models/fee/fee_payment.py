# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FeePayment(models.Model):
    _name = 'fee.payment'
    _description = 'Fee Payment Records'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'payment_date desc'

    name = fields.Char(string='Payment Receipt Number', required=True, readonly=True,
                       copy=False, default='/')

    # ── Student ───────────────────────────────────────────────────────
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one('university.program', related='student_id.program_id',
                                 string='Program', store=True)
    department_id = fields.Many2one('university.department', related='student_id.department_id',
                                    string='Department', store=True)
    student_temp_id = fields.Char(
        related='student_id.temp_student_id',
        string='Temp Student ID',
        store=False,
    )
    student_usn = fields.Char(
        related='student_id.university_usn',
        string='University USN',
        store=False,
    )
    student_usn_mapped = fields.Boolean(
        related='student_id.usn_mapped',
        string='USN Mapped',
        store=False,
    )

    # ── Fee Structure ─────────────────────────────────────────────────
    fee_structure_id = fields.Many2one('fee.structure', string='Fee Structure',
                                       required=True, tracking=True)
    academic_year_id = fields.Many2one('university.academic.year',
                                       related='fee_structure_id.academic_year_id',
                                       string='Academic Year', store=True)
    semester_id = fields.Many2one('university.semester',
                                  related='fee_structure_id.semester_id',
                                  string='Semester', store=True)
    payment_term = fields.Char(
        related='fee_structure_id.payment_term',
        string='Payment Term', store=True,
    )

    # ── Payment Details ───────────────────────────────────────────────
    payment_date = fields.Date(string='Payment Date', tracking=True, index=True)
    due_date = fields.Date(string='Due Date', tracking=True)

    # ── Amount ────────────────────────────────────────────────────────
    amount = fields.Monetary(string='Fee Amount', required=True, tracking=True,
                             currency_field='currency_id')
    late_fee = fields.Monetary(string='Late Fee', currency_field='currency_id')
    discount_amount = fields.Monetary(string='Discount', currency_field='currency_id')
    total_amount = fields.Monetary(string='Total Amount', compute='_compute_total',
                                   store=True, currency_field='currency_id')

    # ── Portal payment tracking ───────────────────────────────────────
    amount_paid = fields.Monetary(string='Amount Paid So Far',
                                  compute='_compute_amount_paid', store=True,
                                  currency_field='currency_id')
    outstanding_amount = fields.Monetary(string='Outstanding Amount',
                                         compute='_compute_amount_paid', store=True,
                                         currency_field='currency_id')
    currency_id = fields.Many2one('res.currency',
                                  default=lambda self: self.env.company.currency_id)

    # ── Component Payment Lines ───────────────────────────────────────
    payment_line_ids = fields.One2many(
        'fee.payment.line', 'fee_payment_id', string='Fee Components',
    )

    # ── Accounting Integration ────────────────────────────────────────
    journal_id = fields.Many2one('account.journal', string='Payment Journal',
                                 domain="[('type', 'in', ['bank', 'cash'])]",
                                 default=lambda self: self._default_journal())
    account_move_id = fields.Many2one('account.move', string='Journal Entry')
    account_payment_id = fields.Many2one(
        'account.payment', string='Accounting Payment',
        compute='_compute_account_payment_id', store=True,
    )
    account_move_line_ids = fields.One2many('account.move.line', string='Journal Items',
                                            compute='_compute_account_move_lines')
    payment_state = fields.Selection([
        ('not_paid', 'Not Paid'), ('in_payment', 'In Payment'), ('paid', 'Paid'),
        ('partial', 'Partially Paid'), ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy'),
    ], string='Payment Status', compute='_compute_payment_state', store=True)
    reconciliation_status = fields.Selection([
        ('not_reconciled', 'Not Reconciled'),
        ('partially_reconciled', 'Partially Reconciled'),
        ('fully_reconciled', 'Fully Reconciled'),
    ], string='Reconciliation Status', compute='_compute_reconciliation_status', store=True)
    payment_method = fields.Char(string='Payment Method',
                                 compute='_compute_payment_method', store=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # ── Payment Reference ─────────────────────────────────────────────
    payment_reference = fields.Char(string='Payment Reference/Transaction ID', tracking=True)
    bank_name = fields.Char(string='Bank Name')
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')

    # ── Discount / Scholarship ────────────────────────────────────────
    discount_id = fields.Many2one('fee.discount', string='Applied Discount')
    scholarship_id = fields.Many2one('scholarship.scholarship', string='Scholarship Applied')

    # ── Invoice ───────────────────────────────────────────────────────
    invoice_id = fields.Many2one('account.move', string='Invoice', readonly=True)
    invoice_status = fields.Selection(related='invoice_id.state', string='Invoice Status')

    # ── State ─────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Verification'),
        ('verified', 'Verified'),
        ('invoiced', 'Invoice Sent'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    # ── Verification ──────────────────────────────────────────────────
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verification_date = fields.Date(string='Verification Date', readonly=True)

    # ── Receipt ───────────────────────────────────────────────────────
    receipt_printed = fields.Boolean(string='Receipt Printed')
    receipt_sent = fields.Boolean(string='Receipt Sent to Parent')
    collected_by = fields.Many2one('res.users', string='Collected By',
                                   default=lambda self: self.env.user, tracking=True)

    # ── Refund ────────────────────────────────────────────────────────
    refund_reason = fields.Text(string='Refund Reason')
    refund_date = fields.Date(string='Refund Date')
    refund_amount = fields.Monetary(string='Refund Amount', currency_field='currency_id')
    refund_move_id = fields.Many2one('account.move', string='Refund Journal Entry',
                                     readonly=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Payment Receipt Number must be unique!'),
    ]

    # ── Defaults ──────────────────────────────────────────────────────

    def _default_journal(self):
        return self.env['account.journal'].search([
            ('type', 'in', ['bank', 'cash']),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

    # ── ORM ───────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('fee.payment') or '/'
        return super(FeePayment, self).create(vals)

    # ── Computed Fields ───────────────────────────────────────────────

    @api.depends('amount', 'late_fee', 'discount_amount')
    def _compute_total(self):
        for record in self:
            record.total_amount = record.amount + record.late_fee - record.discount_amount

    @api.depends(
        'invoice_id', 'invoice_id.payment_state', 'invoice_id.amount_residual',
        'invoice_id.line_ids.matched_credit_ids',
        'invoice_id.line_ids.matched_debit_ids',
    )
    def _compute_amount_paid(self):
        for record in self:
            if record.invoice_id:
                total = record.invoice_id.amount_total
                residual = record.invoice_id.amount_residual
                record.amount_paid = total - residual
                record.outstanding_amount = residual
            else:
                record.amount_paid = 0.0
                record.outstanding_amount = record.total_amount

    @api.depends(
        'invoice_id', 'invoice_id.payment_state',
        'invoice_id.line_ids.matched_credit_ids',
        'invoice_id.line_ids.matched_debit_ids',
    )
    def _compute_account_payment_id(self):
        for record in self:
            if record.invoice_id and record.invoice_id.payment_state in (
                    'paid', 'in_payment', 'partial'):
                payment = record.invoice_id.line_ids.mapped(
                    'matched_credit_ids.credit_move_id.payment_id'
                )[:1]
                if payment:
                    record.account_payment_id = payment.id
                    record.account_move_id = payment.move_id.id
                else:
                    record.account_payment_id = False
                    record.account_move_id = False
            else:
                record.account_payment_id = False
                record.account_move_id = False

    @api.depends('invoice_id', 'invoice_id.payment_state')
    def _compute_payment_state(self):
        for record in self:
            if record.invoice_id:
                record.payment_state = record.invoice_id.payment_state
            elif record.state == 'paid':
                record.payment_state = 'paid'
            elif record.state == 'refunded':
                record.payment_state = 'reversed'
            else:
                record.payment_state = 'not_paid'

    @api.depends(
        'account_payment_id', 'account_payment_id.is_reconciled',
        'account_payment_id.move_id.line_ids.amount_residual',
        'account_payment_id.move_id.line_ids.matched_debit_ids',
        'account_payment_id.move_id.line_ids.matched_credit_ids',
    )
    def _compute_reconciliation_status(self):
        for record in self:
            if record.account_payment_id:
                payment = record.account_payment_id
                if payment.is_reconciled:
                    record.reconciliation_status = 'fully_reconciled'
                else:
                    reconcilable_lines = payment.move_id.line_ids.filtered(
                        lambda l: l.account_id.reconcile
                    )
                    has_residual = any(l.amount_residual != 0 for l in reconcilable_lines)
                    has_matched = any(
                        l.matched_debit_ids or l.matched_credit_ids
                        for l in reconcilable_lines
                    )
                    if has_matched and has_residual:
                        record.reconciliation_status = 'partially_reconciled'
                    else:
                        record.reconciliation_status = 'not_reconciled'
            else:
                record.reconciliation_status = 'not_reconciled'

    @api.depends('account_payment_id', 'account_payment_id.payment_method_line_id')
    def _compute_payment_method(self):
        for record in self:
            if record.account_payment_id:
                record.payment_method = (
                    record.account_payment_id.payment_method_line_id.name
                    or record.account_payment_id.journal_id.name
                )
            else:
                record.payment_method = False

    @api.depends('account_move_id')
    def _compute_account_move_lines(self):
        for record in self:
            if record.account_move_id:
                record.account_move_line_ids = record.account_move_id.line_ids
            else:
                record.account_move_line_ids = False

    # ── Onchange ──────────────────────────────────────────────────────

    @api.onchange('student_id', 'fee_structure_id')
    def _onchange_fee_structure(self):
        if self.student_id and self.fee_structure_id:
            self.amount = self.fee_structure_id.total_amount
            self.due_date = self.fee_structure_id.due_date
            if self.due_date and fields.Date.today() > self.due_date:
                days_late = (fields.Date.today() - self.due_date).days
                grace_period = self.fee_structure_id.grace_period_days or 0
                if days_late > grace_period and self.fee_structure_id.has_late_fee:
                    if self.fee_structure_id.late_fee_amount:
                        self.late_fee = self.fee_structure_id.late_fee_amount
                    elif self.fee_structure_id.late_fee_percentage:
                        self.late_fee = (
                            self.amount * self.fee_structure_id.late_fee_percentage
                        ) / 100

    # ── State Actions ─────────────────────────────────────────────────

    def action_submit(self):
        self.write({'state': 'pending'})

    def action_verify(self):
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verification_date': fields.Date.today(),
        })

    def action_confirm_payment(self):
        """
        Admin confirms payment record.
        1. Creates invoice (one invoice, all components as lines)
        2. Creates fee.payment.line records per component
        3. Sends invoice to student
        """
        self._create_invoice()
        self._create_payment_lines()
        self.write({'state': 'invoiced'})
        self._send_invoice_to_student()
        self.message_post(
            body=_('Invoice created and sent to student for portal payment.')
        )

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    # ── Component Line Management ─────────────────────────────────────

    def _create_payment_lines(self):
        """
        Create fee.payment.line for each fee.structure.line component.
        Called once when admin confirms payment. Skips if already created.
        """
        for record in self:
            if record.payment_line_ids:
                continue
            for struct_line in record.fee_structure_id.fee_line_ids:
                self.env['fee.payment.line'].create({
                    'fee_payment_id': record.id,
                    'fee_structure_line_id': struct_line.id,
                    'component_amount': struct_line.amount,
                    'amount_paid': 0.0,
                    'state': 'pending',
                })

    def apply_component_selection(self, component_selection):
        """
        Apply the student's specific component selection after payment.

        Called ONLY from portal_fee_return with the exact amounts
        the student entered per component in the payment form.

        :param dict component_selection: {str(line_id): float(amount)}

        This is the ONLY place where component amounts are updated.
        _sync_state_from_invoice does NOT touch component amounts —
        it only updates the parent fee.payment state.
        """
        self.ensure_one()

        if not component_selection:
            return

        for line_id_str, amount in component_selection.items():
            try:
                line_id = int(line_id_str)
                amount = float(amount)
            except (ValueError, TypeError):
                continue

            if amount <= 0:
                continue

            line = self.payment_line_ids.filtered(lambda l: l.id == line_id)
            if not line:
                continue

            # Cap at component outstanding to prevent overpayment
            applicable = min(amount, line.outstanding_amount)
            if applicable <= 0:
                continue

            new_paid = line.amount_paid + applicable
            # Compute new state
            if new_paid >= line.component_amount - 0.01:
                new_state = 'paid'
                new_paid = line.component_amount  # fix rounding
            elif new_paid > 0:
                new_state = 'partial'
            else:
                new_state = 'pending'

            line.write({
                'amount_paid': new_paid,
                'state': new_state,
            })

        self.message_post(
            body=_('Component payments applied: %s') % ', '.join(
                '%s: ₹%s' % (k, v) for k, v in component_selection.items()
            )
        )

    def _sync_component_states(self):
        """
        Update the parent fee.payment state based on component line states.

        Rules:
        - ALL lines 'paid'               → fee.payment = 'paid'
        - ANY line 'partial' or 'paid'   → fee.payment = 'partial'
        - ALL lines 'pending'            → no state change (stays 'invoiced')

        IMPORTANT: This method does NOT update component amounts.
        It only reads the current component states and updates the parent.
        """
        for record in self:
            if not record.payment_line_ids:
                continue

            line_states = record.payment_line_ids.mapped('state')

            if all(s == 'paid' for s in line_states):
                if record.state != 'paid':
                    record.write({'state': 'paid'})
                    record._send_receipt()
                    record.message_post(
                        body=_('All fee components fully paid. Fee payment marked as PAID.')
                    )
            elif any(s in ('paid', 'partial') for s in line_states):
                if record.state in ('invoiced', 'partial'):
                    record.write({'state': 'partial'})

    # ── Automated State Sync ──────────────────────────────────────────

    def _sync_state_from_invoice(self):
        """
        Called by account_move_ext.py reconcile() hook after each payment.
        Also called by portal_fee_return as a safety net.

        CRITICAL DESIGN DECISION:
        This method ONLY updates fee.payment.state (invoiced/partial/paid).
        It does NOT touch fee.payment.line amounts.

        Component amount allocation is handled separately in
        apply_component_selection() called from portal_fee_return
        with the student's exact selections from the session.

        Why? Because this hook fires from Odoo's reconcile() which has
        no knowledge of which components the student chose to pay.
        If we allocated here, we would always dump money into the first
        component regardless of what the student selected — which is
        exactly the bug we are fixing.
        """
        for record in self:
            if not record.invoice_id:
                continue

            invoice = record.invoice_id
            current_state = record.state

            if current_state not in ('invoiced', 'partial'):
                continue

            invoice_payment_state = invoice.payment_state

            if invoice_payment_state == 'paid':
                # Invoice fully paid — mark fee.payment as paid too
                # Component states will be finalized in portal_fee_return
                # via apply_component_selection + _sync_component_states

                # Capture actual payment date from reconciled invoice payment
                actual_payment_date = record._get_actual_payment_date(invoice)
                write_vals = {'state': 'paid'}
                if actual_payment_date:
                    write_vals['payment_date'] = actual_payment_date
                record.write(write_vals)
                record._send_receipt()
                record.message_post(
                    body=_('Invoice %s fully paid.') % invoice.name
                )

            elif invoice_payment_state in ('partial', 'in_payment'):
                # Partial payment received — just move to partial state
                # Component allocation handled by portal_fee_return
                paid = invoice.amount_total - invoice.amount_residual

                # Capture most recent partial payment date
                actual_payment_date = record._get_actual_payment_date(invoice)
                write_vals = {'state': 'partial'}
                if actual_payment_date:
                    write_vals['payment_date'] = actual_payment_date
                record.write(write_vals)
                record.message_post(
                    body=_('Partial payment received. ₹%s paid, ₹%s remaining on Invoice %s.')
                    % (paid, invoice.amount_residual, invoice.name)
                )

    # ── Private Helpers ───────────────────────────────────────────────

    def _get_actual_payment_date(self, invoice):
        """
        Return the date of the most recent payment reconciled against the invoice.

        Looks at account.payment records linked to this invoice and returns
        the latest payment date. Falls back to payment.transaction date,
        then today as a last resort.

        This ensures payment_date reflects when the student actually paid
        via the portal, not when the admin created the fee.payment record.
        """
        payments = (
            invoice.line_ids.mapped('matched_credit_ids.credit_move_id.payment_id')
            | invoice.line_ids.mapped('matched_debit_ids.debit_move_id.payment_id')
        )
        if payments:
            return max(payments.mapped('date'))
        # Fallback: check payment.transaction date
        tx = self.env['payment.transaction'].sudo().search([
            ('invoice_ids', 'in', [invoice.id]),
            ('state', 'in', ['done', 'authorized']),
        ], order='last_state_change desc', limit=1)
        if tx:
            return tx.last_state_change.date()
        return fields.Date.today()

    def _create_invoice(self):
        """Create and post one invoice with all fee components as lines."""
        if self.invoice_id:
            return

        invoice_lines = []
        for line in self.fee_structure_id.fee_line_ids:
            invoice_lines.append((0, 0, {
                'name': line.name,
                'quantity': 1,
                'price_unit': line.amount,
                'product_id': (
                    line.product_id.id if line.product_id
                    else self.fee_structure_id.product_id.id
                ),
                'account_id': (
                    line.income_account_id.id if line.income_account_id
                    else self.fee_structure_id.income_account_id.id
                ),
                'analytic_distribution': (
                    {str(line.analytic_account_id.id): 100}
                    if line.analytic_account_id
                    else (
                        {str(self.fee_structure_id.analytic_account_id.id): 100}
                        if self.fee_structure_id.analytic_account_id
                        else False
                    )
                ),
                'fee_structure_line_id': line.id,
            }))

        if self.late_fee > 0:
            invoice_lines.append((0, 0, {
                'name': 'Late Fee',
                'quantity': 1,
                'price_unit': self.late_fee,
                'account_id': (
                    self.fee_structure_id.late_fee_account_id.id
                    if self.fee_structure_id.late_fee_account_id else False
                ),
            }))

        if self.discount_amount > 0 and self.discount_id:
            invoice_lines.append((0, 0, {
                'name': f'Discount: {self.discount_id.name}',
                'quantity': 1,
                'price_unit': -self.discount_amount,
                'account_id': (
                    self.discount_id.account_id.id
                    if self.discount_id.account_id else False
                ),
            }))

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.student_id.partner_id.id,
            'invoice_date': self.payment_date,
            'invoice_date_due': self.due_date or self.payment_date,
            'invoice_line_ids': invoice_lines,
            'payment_reference': self.payment_reference,
            'invoice_payment_term_id': (
                self.fee_structure_id.payment_term_id.id
                if self.fee_structure_id.payment_term_id else False
            ),
            'journal_id': (
                self.fee_structure_id.journal_id.id
                if self.fee_structure_id.journal_id
                else self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1).id
            ),
            'invoice_origin': self.name,
        }

        invoice = self.env['account.move'].create(invoice_vals)
        invoice.action_post()
        self.invoice_id = invoice.id

    def _send_invoice_to_student(self):
        if self.invoice_id:
            self.invoice_id.action_send_and_print()

    def _send_receipt(self):
        self.write({'receipt_sent': True})
        template = self.env.ref(
            'university_management.email_template_fee_receipt',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

    # ── Action Buttons ────────────────────────────────────────────────

    def action_print_receipt(self):
        self.write({'receipt_printed': True})
        return self.env.ref(
            'university_management.action_report_fee_receipt'
        ).report_action(self)

    def action_view_account_payment(self):
        if self.account_payment_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'view_mode': 'form',
                'res_id': self.account_payment_id.id,
                'target': 'current',
            }

    def action_view_journal_entry(self):
        if self.account_move_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.account_move_id.id,
                'target': 'current',
            }

    # ── Refund / Cancel ───────────────────────────────────────────────

    def action_refund(self):
        if not self.refund_amount or self.refund_amount <= 0:
            raise ValidationError(_('Please enter refund amount.'))

        refund_payment_vals = {
            'payment_type': 'outbound',
            'partner_type': 'customer',
            'partner_id': self.student_id.partner_id.id,
            'amount': self.refund_amount,
            'currency_id': self.currency_id.id,
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'memo': f'Refund for {self.name}',
        }
        refund_payment = self.env['account.payment'].create(refund_payment_vals)
        refund_payment.action_post()

        partner = self.student_id.partner_id
        refund_move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': f'Refund: {self.name}',
            'line_ids': [
                (0, 0, {
                    'account_id': partner.property_account_receivable_id.id,
                    'debit': self.refund_amount, 'credit': 0,
                    'name': f'Refund: {self.name}', 'partner_id': partner.id,
                }),
                (0, 0, {
                    'account_id': self.journal_id.default_account_id.id,
                    'debit': 0, 'credit': self.refund_amount,
                    'name': f'Refund: {self.name}',
                }),
            ],
        })
        refund_move.action_post()
        self.write({
            'state': 'refunded',
            'refund_date': fields.Date.today(),
            'refund_move_id': refund_move.id,
        })

    def action_cancel(self):
        if self.account_payment_id:
            self.account_payment_id.action_draft()
            self.account_payment_id.action_cancel()
        if self.account_move_id:
            self.account_move_id.button_cancel()
        if self.invoice_id:
            self.invoice_id.button_cancel()
        self.write({'state': 'cancelled'})