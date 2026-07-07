# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class AlumniPortal(CustomerPortal):
    """Portal controller for alumni self-service."""

    # ── Portal home count ────────────────────────────────────────────

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'alumni_count' in counters:
            partner = request.env.user.partner_id
            alumni = request.env['alumni.alumni'].sudo().search([
                ('partner_id', '=', partner.id)
            ], limit=1)
            values['alumni_count'] = 1 if alumni else 0
        return values

    # ── Alumni Profile ────────────────────────────────────────────────

    @http.route('/my/alumni', type='http', auth='user', website=True)
    def portal_alumni_profile(self, **kw):
        """Display the logged-in alumni's own profile."""
        partner = request.env.user.partner_id
        alumni = request.env['alumni.alumni'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        if not alumni:
            return request.redirect('/my/home')

        values = {
            'alumni': alumni,
            'page_name': 'alumni_profile',
        }
        return request.render('university_management.portal_alumni_profile', values)

    @http.route('/my/alumni/edit', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def portal_alumni_edit(self, **post):
        """Allow alumni to update their own profile (employment, contact, social)."""
        partner = request.env.user.partner_id
        alumni = request.env['alumni.alumni'].sudo().search([
            ('partner_id', '=', partner.id)
        ], limit=1)

        if not alumni:
            return request.redirect('/my/home')

        errors = {}
        success = False

        if request.httprequest.method == 'POST':
            update_vals = {}

            # Contact
            if post.get('mobile'):
                update_vals['mobile'] = post['mobile']
            if post.get('linkedin_profile'):
                update_vals['linkedin_profile'] = post['linkedin_profile']
            if post.get('twitter_handle'):
                update_vals['twitter_handle'] = post['twitter_handle']
            if post.get('facebook_profile'):
                update_vals['facebook_profile'] = post['facebook_profile']

            # Employment
            update_vals['is_employed'] = bool(post.get('is_employed'))
            if update_vals['is_employed']:
                update_vals['current_company'] = post.get('current_company', '')
                update_vals['current_designation'] = post.get('current_designation', '')
                update_vals['current_location'] = post.get('current_location', '')
                update_vals['industry'] = post.get('industry', False)

            # Higher education
            update_vals['pursuing_higher_education'] = bool(post.get('pursuing_higher_education'))
            if update_vals['pursuing_higher_education']:
                update_vals['higher_education_details'] = post.get('higher_education_details', '')

            # Mentorship
            update_vals['willing_to_mentor'] = bool(post.get('willing_to_mentor'))
            if update_vals['willing_to_mentor']:
                update_vals['mentorship_area'] = post.get('mentorship_area', '')

            if not errors:
                alumni.sudo().write(update_vals)
                success = True

        values = {
            'alumni': alumni,
            'errors': errors,
            'success': success,
            'page_name': 'alumni_edit',
        }
        return request.render('university_management.portal_alumni_edit', values)

    # ── Alumni Directory (public) ─────────────────────────────────────

    @http.route('/alumni', type='http', auth='public', website=True)
    def alumni_directory(self, page=1, program=None, graduation_year=None, **kw):
        """Public alumni directory page."""
        Alumni = request.env['alumni.alumni'].sudo()
        domain = [('active', '=', True)]

        if program:
            domain.append(('program_id', '=', int(program)))
        if graduation_year:
            domain.append(('graduation_year', '=', int(graduation_year)))

        alumni_count = Alumni.search_count(domain)
        pager = portal_pager(
            url='/alumni',
            url_args={'program': program, 'graduation_year': graduation_year},
            total=alumni_count,
            page=page,
            step=20,
        )

        alumni_list = Alumni.search(
            domain,
            limit=20,
            offset=pager['offset'],
            order='graduation_year desc, name',
        )

        programs = request.env['university.program'].sudo().search([])
        graduation_years = Alumni.read_group([], ['graduation_year'], ['graduation_year'])
        years = sorted(
            [g['graduation_year'] for g in graduation_years if g['graduation_year']],
            reverse=True,
        )

        values = {
            'alumni_list': alumni_list,
            'pager': pager,
            'programs': programs,
            'graduation_years': years,
            'selected_program': int(program) if program else False,
            'selected_year': int(graduation_year) if graduation_year else False,
            'page_name': 'alumni_directory',
        }
        return request.render('university_management.portal_alumni_directory', values)

    @http.route('/alumni/<int:alumni_id>', type='http', auth='public', website=True)
    def alumni_detail(self, alumni_id, **kw):
        """Public alumni profile detail page."""
        alumni = request.env['alumni.alumni'].sudo().browse(alumni_id)
        if not alumni.exists() or not alumni.active:
            return request.not_found()

        values = {
            'alumni': alumni,
            'page_name': 'alumni_detail',
        }
        return request.render('university_management.portal_alumni_detail', values)