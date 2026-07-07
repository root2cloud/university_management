# -*- coding: utf-8 -*-
from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError
import logging
from datetime import timedelta, datetime

_logger = logging.getLogger(__name__)


class IDCardController(http.Controller):
    """ID Card Download and Management Controller"""

    # ==================== ID CARD PORTAL ====================
    @http.route(['/my/id-card'], type='http', auth="user", website=True)
    def id_card_page(self, **kw):
        """View ID card details"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        # Get ID card
        id_card = request.env['student.id.card'].search([
            ('student_id', '=', student.id),
            ('state', '=', 'issued')
        ], limit=1)

        values = {
            'student': student,
            'id_card': id_card,
            'page_name': 'id_card',
        }

        return request.render("university_management.student_id_card_page", values)

    # ==================== DOWNLOAD ID CARD ====================
    @http.route(['/my/id-card/download'], type='http', auth="user")
    def id_card_download(self, **kw):
        """Download ID card as PDF"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        id_card = request.env['student.id.card'].sudo().search([
            ('student_id', '=', student.id),
            ('state', '=', 'issued')  # FIXED: 'active' → 'issued'
        ], limit=1)

        if not id_card:
            # Redirect to main ID card page with error parameter
            return request.redirect('/my/id-card?error=no_id_card')

        try:
            # FIXED: Use the ir.actions.report model directly to avoid the account module's invoice check
            # Get the report template name from the report action
            report_action = request.env.ref('university_management.action_report_student_id_card')

            # Use the report model to render PDF directly with the template name
            pdf_content, _ = request.env['ir.actions.report']._render_qweb_pdf(
                'university_management.report_student_id_card',
                id_card.ids
            )

            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="IDCard_{id_card.name}.pdf"')
            ]

            return request.make_response(pdf_content, headers=pdfhttpheaders)

        except Exception as e:
            _logger.error("Error generating ID card PDF: %s", str(e))
            return request.redirect('/my/id-card?error=pdf_generation_failed')

    # ==================== REQUEST NEW ID CARD ====================
    @http.route(['/my/id-card/request-new'], type='http', auth="user", website=True)
    def id_card_request_new_page(self, **kw):
        """Request new ID card page"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        # Get existing requests
        existing_requests = request.env['id.card.request'].search([
            ('student_id', '=', student.id)
        ], order='request_date desc')

        values = {
            'student': student,
            'existing_requests': existing_requests,
            'page_name': 'request_new_id',
        }

        return request.render("university_management.request_new_id_card", values)

    @http.route(['/my/id-card/request-new/submit'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def id_card_request_new_submit(self, **post):
        """Submit new ID card request"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        try:
            request_vals = {
                'student_id': student.id,
                'request_type': post.get('request_type', 'duplicate'),
                'reason': post.get('reason'),
                'request_date': fields.Date.today(),
            }

            request.env['id.card.request'].sudo().create(request_vals)

            return request.redirect('/my/id-card/request-new?success=1')
        except Exception as e:
            _logger.error("Error submitting ID card request: %s", str(e))
            return request.redirect('/my/id-card/request-new?error=1')

    # ==================== ID CARD VERIFICATION (PUBLIC) ====================
    @http.route(['/id-card/verify'], type='http', auth="public", website=True)
    def id_card_verify_page(self, **kw):
        """ID card verification page"""
        values = {
            'page_name': 'id_card_verify',
        }
        return request.render("university_management.id_card_verify_page", values)

    @http.route(['/id-card/verify/check'], type='http', auth="public", methods=['POST'], website=True, csrf=True)
    def id_card_verify_check(self, **post):
        """Verify ID card"""
        card_number = post.get('name')

        if not card_number:
            return request.render("university_management.id_card_verify_page", {
                'error': _('Please provide ID Card Number'),
            })

        # Search ID card
        id_card = request.env['student.id.card'].sudo().search([
            ('name', '=', card_number),
            ('state', '=', 'issued')
        ], limit=1)

        if not id_card:
            return request.render("university_management.id_card_verify_page", {
                'error': _('Invalid ID Card Number or card is inactive'),
            })

        values = {
            'id_card': id_card,
            'student': id_card.student_id,
            'verified': True,
        }

        return request.render("university_management.id_card_verify_result", values)

    # ==================== REPORT LOST ID CARD ====================
    @http.route(['/my/id-card/report-lost'], type='http', auth="user", methods=['POST'], website=True, csrf=True)
    def id_card_report_lost(self, **post):
        """Report lost ID card"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return request.redirect('/my')

        try:
            id_card = request.env['student.id.card'].search([
                ('student_id', '=', student.id),
                ('state', '=', 'issued')
            ], limit=1)

            if id_card:
                # Mark as lost
                id_card.write({
                    'state': 'lost',
                    'lost_date': fields.Date.today(),
                })

                # Create request for new card
                request.env['id.card.request'].sudo().create({
                    'student_id': student.id,
                    'request_type': 'lost',
                    'reason': post.get('reason', 'ID card lost'),
                    'request_date': fields.Date.today(),
                })

            return request.redirect('/my/id-card?lost_reported=1')
        except Exception as e:
            _logger.error("Error reporting lost ID card: %s", str(e))
            return request.redirect('/my/id-card?error=1')

    # ==================== BULK ID CARD GENERATION (Admin) ====================
    @http.route(['/admin/id-cards/generate-bulk'], type='http', auth="user", website=True)
    def id_card_generate_bulk_page(self, **kw):
        """Bulk ID card generation page"""
        if not request.env.user.has_group('university_management.group_university_admin'):
            raise AccessError(_("You don't have permission to access this page"))

        programs = request.env['university.program'].search([('active', '=', True)])
        batches = request.env['university.batch'].search([('active', '=', True)])

        values = {
            'programs': programs,
            'batches': batches,
            'page_name': 'generate_bulk_id_cards',
        }

        return request.render("university_management.generate_bulk_id_cards", values)

    @http.route(['/admin/id-cards/generate-bulk/process'], type='http', auth="user", methods=['POST'], csrf=True)
    def id_card_generate_bulk_process(self, **post):
        """Process bulk ID card generation"""
        if not request.env.user.has_group('university_management.group_university_admin'):
            raise AccessError(_("You don't have permission to perform this action"))

        try:
            batch_id = post.get('batch_id')
            program_id = post.get('program_id')

            domain = [('state', '=', 'enrolled')]
            if batch_id:
                domain += [('batch_id', '=', int(batch_id))]
            if program_id:
                domain += [('program_id', '=', int(program_id))]

            students = request.env['student.student'].search(domain)

            generated_count = 0
            for student in students:
                # Check if ID card already exists
                existing = request.env['student.id.card'].search([
                    ('student_id', '=', student.id),
                    ('state', '=', 'issued')
                ])

                if not existing:
                    request.env['student.id.card'].create({
                        'student_id': student.id,
                        'issue_date': fields.Date.today(),
                        'expiry_date': fields.Date.today() + timedelta(days=365 * 4),  # 4 years validity
                        'state': 'issued',
                    })
                    generated_count += 1

            return request.redirect(f'/admin/id-cards/generate-bulk?success=1&count={generated_count}')
        except Exception as e:
            _logger.error("Error generating bulk ID cards: %s", str(e))
            return request.redirect('/admin/id-cards/generate-bulk?error=1')

    # ==================== BULK DOWNLOAD ID CARDS ====================
    @http.route(['/admin/id-cards/download-bulk'], type='http', auth="user")
    def id_card_download_bulk(self, batch_id=None, program_id=None, **kw):
        """Bulk download ID cards"""
        if not request.env.user.has_group('university_management.group_university_admin'):
            raise AccessError(_("You don't have permission to download bulk ID cards"))

        domain = [('state', '=', 'issued')]
        if batch_id:
            domain += [('student_id.batch_id', '=', int(batch_id))]
        if program_id:
            domain += [('student_id.program_id', '=', int(program_id))]

        id_cards = request.env['student.id.card'].search(domain)

        if not id_cards:
            return request.render("university_management.no_id_cards", {
                'message': _('No ID cards found for the selected criteria.')
            })

        try:
            # Generate PDF report for all ID cards - using ir.actions.report model directly
            pdf_content, _ = request.env['ir.actions.report']._render_qweb_pdf(
                'university_management.report_student_id_card',
                id_cards.ids
            )

            filename = f"IDCards_Bulk_{fields.Date.today().strftime('%Y%m%d')}.pdf"

            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf_content)),
                ('Content-Disposition', f'attachment; filename="{filename}"')
            ]

            return request.make_response(pdf_content, headers=pdfhttpheaders)

        except Exception as e:
            _logger.error("Error generating bulk ID cards PDF: %s", str(e))
            return request.render("university_management.no_id_cards", {
                'message': _('Error generating PDF. Please contact administrator.')
            })

    # ==================== ID CARD API ====================
    @http.route(['/api/id-card/info'], type='json', auth="user")
    def id_card_info(self, **kw):
        """Get ID card information (API)"""
        student = request.env['student.student'].search([('user_id', '=', request.env.uid)], limit=1)

        if not student:
            return {'success': False, 'error': 'Student not found'}

        id_card = request.env['student.id.card'].search([
            ('student_id', '=', student.id),
            ('state', '=', 'issued')
        ], limit=1)

        if not id_card:
            return {'success': False, 'error': 'ID card not found'}

        return {
            'success': True,
            'data': {
                'card_number': id_card.name,
                'issue_date': id_card.issue_date,
                'valid_until': id_card.expiry_date,
                'status': id_card.state,
                'student': {
                    'name': student.name,
                    'registration_number': student.registration_number,
                    'program': student.program_id.name,
                    'batch': student.batch_id.name,
                }
            }
        }
