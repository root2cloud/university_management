# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.addons.payment import utils as payment_utils
from odoo.addons.account_payment.controllers.payment import PaymentPortal
import json
import logging

_logger = logging.getLogger(__name__)


class FeePortalController(http.Controller):
    """
    Fee portal controller — component-wise payment flow.

    KEY DESIGN:
    ───────────
    We inherit from PaymentPortal and override _get_extra_payment_form_values
    to inject our custom landing_route (/my/fees/<id>/return).

    Without this override, account_payment's _get_extra_payment_form_values
    always sets landing_route = invoice.access_url (the invoice portal page).
    So our /return route was never being called, session data was never
    consumed, and component lines were never updated.
    """

    def _get_portal_student(self):
        partner = request.env.user.partner_id
        return request.env['student.student'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

    def _get_portal_fee(self, fee_payment_id):
        student = self._get_portal_student()
        if not student:
            return False, False
        fee_payment = request.env['fee.payment'].sudo().browse(fee_payment_id)
        if not fee_payment.exists() or fee_payment.student_id.id != student.id:
            return student, False
        return student, fee_payment

    # ------------------------------------------------------------------
    # /my/fees — Fee list
    # ------------------------------------------------------------------

    @http.route('/my/fees', type='http', auth='user', website=True)
    def portal_my_fees(self, **kwargs):
        student = self._get_portal_student()
        if not student:
            return request.render('university_management.portal_fee_no_student', {})

        fee_payments = request.env['fee.payment'].sudo().search([
            ('student_id', '=', student.id)
        ], order='id desc')

        return request.render('university_management.portal_my_fees', {
            'student': student,
            'fee_payments': fee_payments,
            'page_name': 'fees',
        })

    # ------------------------------------------------------------------
    # /my/fees/<id> — Fee detail with component breakdown
    # ------------------------------------------------------------------

    @http.route('/my/fees/<int:fee_payment_id>', type='http', auth='user', website=True)
    def portal_fee_detail(self, fee_payment_id, **kwargs):
        student, fee_payment = self._get_portal_fee(fee_payment_id)

        if not student:
            return request.render('university_management.portal_fee_no_student', {})
        if not fee_payment:
            return request.not_found()

        transactions = []
        if fee_payment.invoice_id:
            transactions = request.env['payment.transaction'].sudo().search([
                ('invoice_ids', 'in', [fee_payment.invoice_id.id]),
                ('state', 'in', ['done', 'authorized', 'pending']),
            ], order='create_date desc')

        error = kwargs.get('error', '')
        success = kwargs.get('success', '')

        return request.render('university_management.portal_fee_detail', {
            'student': student,
            'fee_payment': fee_payment,
            'payment_lines': fee_payment.payment_line_ids,
            'transactions': transactions,
            'page_name': 'fee_detail',
            'error': error,
            'success': success,
        })

    # ------------------------------------------------------------------
    # /my/fees/<id>/pay — Validate selections → save session → /payment/pay
    # ------------------------------------------------------------------

    @http.route(
        '/my/fees/<int:fee_payment_id>/pay',
        type='http', auth='user', website=True,
        methods=['POST'], csrf=True,
    )
    def portal_fee_pay(self, fee_payment_id, **post):
        student, fee_payment = self._get_portal_fee(fee_payment_id)

        if not student:
            return request.redirect('/my/fees')
        if not fee_payment:
            return request.not_found()

        if not fee_payment.invoice_id:
            return request.redirect(
                f'/my/fees/{fee_payment_id}?error=Invoice not found. Please contact admin.'
            )
        if not fee_payment.payment_line_ids:
            return request.redirect(
                f'/my/fees/{fee_payment_id}?error=Fee components not set up. Please contact admin.'
            )

        # ── Collect and validate per-component amounts ────────────────
        selected_components = {}  # {line_id (int): amount (float)}
        total_amount = 0.0

        for line in fee_payment.payment_line_ids:
            if line.state == 'paid':
                continue

            field_key = f'component_amount_{line.id}'
            raw_value = post.get(field_key, '').strip()

            if not raw_value:
                continue

            try:
                amount = float(raw_value)
            except (ValueError, TypeError):
                return request.redirect(
                    f'/my/fees/{fee_payment_id}?error=Invalid amount for {line.name}.'
                )

            if amount <= 0:
                continue

            if amount < 100:
                return request.redirect(
                    f'/my/fees/{fee_payment_id}'
                    f'?error=Minimum payment for {line.name} is Rs.100.'
                )

            if amount > line.outstanding_amount + 0.01:
                return request.redirect(
                    f'/my/fees/{fee_payment_id}'
                    f'?error=Amount for {line.name} (Rs.{amount:,.0f}) cannot exceed '
                    f'outstanding Rs.{line.outstanding_amount:,.2f}.'
                )

            selected_components[line.id] = amount
            total_amount += amount

        if not selected_components:
            return request.redirect(
                f'/my/fees/{fee_payment_id}'
                f'?error=Please enter an amount for at least one fee component.'
            )

        if total_amount < 100:
            return request.redirect(
                f'/my/fees/{fee_payment_id}?error=Total payment must be at least Rs.100.'
            )

        if total_amount > fee_payment.outstanding_amount + 0.01:
            return request.redirect(
                f'/my/fees/{fee_payment_id}'
                f'?error=Total Rs.{total_amount:,.2f} exceeds outstanding '
                f'Rs.{fee_payment.outstanding_amount:,.2f}.'
            )

        # ── Save selection to session ─────────────────────────────────
        session_key = f'fee_component_selection_{fee_payment_id}'
        request.session[session_key] = json.dumps(
            {str(k): v for k, v in selected_components.items()}
        )
        request.session['fee_payment_id_return'] = fee_payment_id

        # ── Generate access token ─────────────────────────────────────
        invoice = fee_payment.invoice_id.sudo()
        partner = request.env.user.partner_id
        currency_id = fee_payment.currency_id.id

        access_token = payment_utils.generate_access_token(
            partner.id, total_amount, currency_id
        )

        # ── Build /payment/pay URL ────────────────────────────────────
        # We pass fee_payment_id as extra param so our
        # _get_extra_payment_form_values override can inject the correct
        # landing_route = /my/fees/<fee_payment_id>/return
        from urllib.parse import urlencode
        params = {
            'invoice_id': invoice.id,
            'amount': total_amount,
            'currency_id': currency_id,
            'partner_id': partner.id,
            'access_token': access_token,
            'company_id': invoice.company_id.id,
            'fee_payment_id': fee_payment_id,   # ← passed to override below
        }
        return request.redirect('/payment/pay?' + urlencode(params))

    # ------------------------------------------------------------------
    # /my/fees/<id>/return — Apply exact component allocation from session
    # ------------------------------------------------------------------

    @http.route('/my/fees/<int:fee_payment_id>/return', type='http', auth='user', website=True)
    def portal_fee_return(self, fee_payment_id, **kwargs):
        student, fee_payment = self._get_portal_fee(fee_payment_id)

        if not student:
            return request.redirect('/my/fees')
        if not fee_payment:
            return request.redirect('/my/fees')

        invoice = fee_payment.invoice_id
        if not invoice:
            return request.redirect(
                f'/my/fees/{fee_payment_id}?error=Invoice not found.'
            )

        # ── Check payment completed ───────────────────────────────────
        done_tx = request.env['payment.transaction'].sudo().search([
            ('invoice_ids', 'in', [invoice.id]),
            ('state', 'in', ['done', 'authorized']),
        ], order='create_date desc', limit=1)

        invoice_paid = invoice.sudo().payment_state in ('paid', 'partial', 'in_payment')

        if not done_tx and not invoice_paid:
            request.session.pop(f'fee_component_selection_{fee_payment_id}', None)
            return request.redirect(
                f'/my/fees/{fee_payment_id}'
                f'?error=Payment was not completed. Please try again.'
            )

        # ── Apply exact component amounts from session ────────────────
        session_key = f'fee_component_selection_{fee_payment_id}'
        session_data = request.session.pop(session_key, None)

        if session_data:
            try:
                component_selection = json.loads(session_data)
                # e.g. {'12': 30000.0, '13': 3000.0, '14': 2000.0, '15': 1000.0}
                fee_payment.sudo().apply_component_selection(component_selection)
                fee_payment.sudo()._sync_component_states()

            except Exception as e:
                _logger.error(
                    'FeePortal: Error applying component selection for fee %s: %s',
                    fee_payment_id, str(e)
                )
                fee_payment.sudo()._sync_state_from_invoice()
        else:
            # No session — just sync state (handles browser back button case)
            fee_payment.sudo()._sync_state_from_invoice()

        # ── Redirect with success ─────────────────────────────────────
        invoice_sudo = invoice.sudo()
        paid_amount = invoice_sudo.amount_total - invoice_sudo.amount_residual

        return request.redirect(
            f'/my/fees/{fee_payment_id}'
            f'?success=Payment of Rs.{paid_amount:,.2f} received! '
            f'Fee component statuses updated.'
        )


# ======================================================================
# Override PaymentPortal to inject our custom landing_route
# ======================================================================

class FeePaymentPortalOverride(PaymentPortal):
    """
    Override account_payment's PaymentPortal to intercept fee payments
    and set landing_route to our /my/fees/<id>/return instead of the
    default invoice portal URL.

    Without this, account_payment._get_extra_payment_form_values always
    sets:
        landing_route = invoice.access_url?access_token=...
    which means the student always lands on the invoice page after paying,
    and our /my/fees/<id>/return is NEVER called, so component lines
    never get updated.

    How it works:
    1. portal_fee_pay passes fee_payment_id as a URL param to /payment/pay
    2. This override reads fee_payment_id from kwargs
    3. Sets landing_route = /my/fees/<fee_payment_id>/return
    4. After payment, Odoo redirects student to our return route ✅
    """

    def _get_extra_payment_form_values(
        self, invoice_id=None, access_token=None, fee_payment_id=None, **kwargs
    ):
        """
        Override to inject /my/fees/<id>/return as landing_route
        when fee_payment_id is present in the payment URL params.
        """
        # Get base values from account_payment's override
        form_values = super()._get_extra_payment_form_values(
            invoice_id=invoice_id,
            access_token=access_token,
            **kwargs
        )

        # If this is a fee payment (fee_payment_id present in URL params),
        # override the landing_route to point to our custom return page
        if fee_payment_id:
            try:
                fid = int(fee_payment_id)
                form_values['landing_route'] = f'/my/fees/{fid}/return'
                _logger.info(
                    'FeePortal: Overriding landing_route to /my/fees/%s/return', fid
                )
            except (ValueError, TypeError):
                pass  # Invalid fee_payment_id — fall back to default

        return form_values