# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class LibraryOPACController(http.Controller):
    """
    OPAC — Online Public Access Catalog
    Routes:
        /library/opac                   — main catalog page
        /library/opac/search            — search results (AJAX + full page)
        /library/book/<int:book_id>     — physical book detail page
        /library/resource/<int:rid>     — digital resource detail page
        /library/resource/<int:rid>/access — log access + redirect/serve
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_current_member(self):
        """Return the library.member for the logged-in user, or False."""
        if request.env.uid == request.env.ref('base.public_user').id:
            return False
        student = request.env['student.student'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1)
        if student:
            return request.env['library.member'].sudo().search(
                [('student_id', '=', student.id), ('state', '=', 'active')],
                limit=1)
        faculty = request.env['faculty.faculty'].sudo().search(
            [('user_id', '=', request.env.uid)], limit=1)
        if faculty:
            return request.env['library.member'].sudo().search(
                [('faculty_id', '=', faculty.id), ('state', '=', 'active')],
                limit=1)
        return False

    def _build_opac_domain(self, search='', res_type='', category_id=None,
                           language='', access='', subject_id=None):
        """Build domain for unified OPAC book+resource search."""
        book_domain = [('active', '=', True), ('opac_visible', '=', True)]
        res_domain = [('state', '=', 'published'), ('is_available', '=', True)]

        if search:
            book_domain += ['|', '|', '|',
                            ('title', 'ilike', search),
                            ('primary_author', 'ilike', search),
                            ('subject', 'ilike', search),
                            ('tags', 'ilike', search)]
            res_domain += ['|', '|', '|',
                           ('title', 'ilike', search),
                           ('primary_author', 'ilike', search),
                           ('tags', 'ilike', search),
                           ('doi', 'ilike', search)]

        if category_id:
            book_domain.append(('category_id', '=', int(category_id)))
            res_domain.append(('category_id', '=', int(category_id)))

        if language:
            book_domain.append(('language', 'ilike', language))
            res_domain.append(('language', 'ilike', language))

        if res_type and res_type != 'physical':
            res_domain.append(('resource_type', '=', res_type))

        if access == 'open':
            res_domain.append(('access_type', '=', 'open'))

        return book_domain, res_domain

    # ------------------------------------------------------------------
    # Main OPAC Page
    # ------------------------------------------------------------------

    @http.route(['/library/opac'], type='http', auth='public', website=True)
    def opac_home(self, **kw):
        """OPAC landing page — shows search bar, featured resources, stats."""
        env = request.env

        # Stats
        total_books = env['library.book'].sudo().search_count(
            [('active', '=', True), ('opac_visible', '=', True)])
        total_resources = env['library.digital.resource'].sudo().search_count(
            [('state', '=', 'published'), ('is_available', '=', True)])
        total_collections = env['library.digital.collection'].sudo().search_count(
            [('is_subscribed', '=', True), ('is_subscription_active', '=', True)])

        # Featured / newest resources
        featured_resources = env['library.digital.resource'].sudo().search(
            [('state', '=', 'published'), ('is_available', '=', True)],
            order='id desc', limit=8)

        # Most accessed
        popular_resources = env['library.digital.resource'].sudo().search(
            [('state', '=', 'published'), ('is_available', '=', True)],
            order='total_access_count desc', limit=6)

        # Collections
        collections = env['library.digital.collection'].sudo().search(
            [('is_subscription_active', '=', True)], limit=12)

        # Categories
        categories = env['library.category'].sudo().search([('active', '=', True)])

        member = self._get_current_member()

        values = {
            'page_name': 'opac',
            'total_books': total_books,
            'total_resources': total_resources,
            'total_collections': total_collections,
            'featured_resources': featured_resources,
            'popular_resources': popular_resources,
            'collections': collections,
            'categories': categories,
            'member': member,
        }
        return request.render('university_management.opac_home', values)

    # ------------------------------------------------------------------
    # OPAC Search
    # ------------------------------------------------------------------

    @http.route(['/library/opac/search'], type='http', auth='public', website=True)
    def opac_search(self, search='', res_type='', category_id=None,
                    language='', access='', subject_id=None,
                    page=1, **kw):
        """Unified search — returns both books and digital resources."""
        env = request.env
        PPG = 20  # results per page

        book_domain, res_domain = self._build_opac_domain(
            search=search, res_type=res_type, category_id=category_id,
            language=language, access=access, subject_id=subject_id)

        # Fetch physical books (only if not filtering to digital-only type)
        books = []
        book_count = 0
        if not res_type or res_type == 'physical':
            books = env['library.book'].sudo().search(book_domain, limit=PPG)
            book_count = env['library.book'].sudo().search_count(book_domain)

        # Fetch digital resources (only if not filtering physical)
        resources = []
        resource_count = 0
        if res_type != 'physical':
            resources = env['library.digital.resource'].sudo().search(
                res_domain, limit=PPG)
            resource_count = env['library.digital.resource'].sudo().search_count(
                res_domain)

        total_count = book_count + resource_count

        # Log the search
        try:
            member = self._get_current_member()
            env['library.opac.search.log'].sudo().create({
                'query': search or '(all)',
                'member_id': member.id if member else False,
                'is_anonymous': not bool(member),
                'filter_type': res_type or '',
                'filter_category': str(category_id) if category_id else '',
                'filter_language': language or '',
                'results_count': total_count,
                'ip_address': request.httprequest.environ.get('REMOTE_ADDR', ''),
            })
        except Exception:
            pass  # Never let logging break the search

        # Filter options
        categories = env['library.category'].sudo().search([('active', '=', True)])
        languages = ['English', 'Hindi', 'Tamil', 'Telugu', 'Kannada',
                     'French', 'German', 'Spanish', 'Other']

        values = {
            'page_name': 'opac_search',
            'search': search,
            'res_type': res_type,
            'category_id': int(category_id) if category_id else None,
            'language': language,
            'access': access,
            'books': books,
            'resources': resources,
            'book_count': book_count,
            'resource_count': resource_count,
            'total_count': total_count,
            'categories': categories,
            'languages': languages,
            'member': self._get_current_member(),
        }
        return request.render('university_management.opac_search_results', values)

    # ------------------------------------------------------------------
    # Physical Book Detail
    # ------------------------------------------------------------------

    @http.route(['/library/book/<int:book_id>'], type='http',
                auth='public', website=True)
    def book_detail(self, book_id, **kw):
        """Physical book detail / OPAC record page."""
        book = request.env['library.book'].sudo().browse(book_id)
        if not book.exists() or not book.opac_visible:
            return request.not_found()

        member = self._get_current_member()
        # Check if member has an active reservation
        existing_reservation = False
        if member:
            existing_reservation = request.env['library.reservation'].sudo().search([
                ('member_id', '=', member.id),
                ('book_id', '=', book_id),
                ('state', 'in', ['draft', 'reserved']),
            ], limit=1)

        values = {
            'page_name': 'opac_book',
            'book': book,
            'member': member,
            'existing_reservation': existing_reservation,
        }
        return request.render('university_management.opac_book_detail', values)

    # ------------------------------------------------------------------
    # Digital Resource Detail
    # ------------------------------------------------------------------

    @http.route(['/library/resource/<int:rid>'], type='http',
                auth='public', website=True)
    def resource_detail(self, rid, **kw):
        """Digital resource detail / OPAC record page."""
        resource = request.env['library.digital.resource'].sudo().browse(rid)
        if not resource.exists() or resource.state != 'published':
            return request.not_found()

        member = self._get_current_member()
        can_access = self._check_resource_access(resource, member)

        values = {
            'page_name': 'opac_resource',
            'resource': resource,
            'member': member,
            'can_access': can_access,
        }
        return request.render('university_management.opac_resource_detail', values)

    # ------------------------------------------------------------------
    # Digital Resource Access / Download
    # ------------------------------------------------------------------

    @http.route(['/library/resource/<int:rid>/access'], type='http',
                auth='user', website=True)
    def resource_access(self, rid, download=False, **kw):
        """
        Log the access event and redirect the member to the resource.
        For file resources — serves or redirects to the file.
        For URL resources — redirects to external URL.
        """
        resource = request.env['library.digital.resource'].sudo().browse(rid)
        if not resource.exists() or resource.state != 'published':
            return request.not_found()

        member = self._get_current_member()
        if not member:
            return request.redirect('/web/login?redirect=/library/resource/%d' % rid)

        if not self._check_resource_access(resource, member):
            return request.render('university_management.opac_access_denied', {
                'resource': resource, 'member': member})

        access_type = 'download' if download else 'view'

        # Check download quota
        if access_type == 'download' and not resource.download_allowed:
            return request.render('university_management.opac_access_denied', {
                'resource': resource, 'member': member,
                'reason': 'download_not_allowed'})

        if access_type == 'download' and resource.max_downloads_per_member:
            download_count = request.env['library.digital.access'].sudo().search_count([
                ('resource_id', '=', rid),
                ('member_id', '=', member.id),
                ('access_type', '=', 'download'),
            ])
            if download_count >= resource.max_downloads_per_member:
                return request.render('university_management.opac_access_denied', {
                    'resource': resource, 'member': member,
                    'reason': 'download_quota_exceeded'})

        # Log the access
        try:
            request.env['library.digital.access'].sudo().create({
                'resource_id': rid,
                'member_id': member.id,
                'access_type': access_type,
                'access_date': fields.Datetime.now(),
                'ip_address': request.httprequest.environ.get('REMOTE_ADDR', ''),
                'user_agent': request.httprequest.environ.get('HTTP_USER_AGENT', '')[:255],
            })
        except Exception as e:
            _logger.warning('Failed to log digital access: %s', e)

        # Redirect / serve
        if resource.content_type == 'url':
            return request.redirect(resource.resource_url)
        elif resource.content_type == 'embed':
            return request.render('university_management.opac_resource_detail', {
                'resource': resource, 'member': member,
                'can_access': True, 'show_embed': True})
        elif resource.content_type == 'file' and resource.resource_file:
            import base64
            file_data = base64.b64decode(resource.resource_file)
            headers = [
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition',
                 'attachment; filename="%s"' % (resource.resource_filename or 'resource')),
                ('Content-Length', len(file_data)),
            ]
            return request.make_response(file_data, headers=headers)

        return request.redirect('/library/resource/%d' % rid)

    # ------------------------------------------------------------------
    # OPAC Reserve Book (POST)
    # ------------------------------------------------------------------

    @http.route(['/library/book/<int:book_id>/reserve'], type='http',
                auth='user', website=True, methods=['POST'])
    def reserve_book(self, book_id, **kw):
        """Allow a logged-in member to place a reservation from OPAC."""
        book = request.env['library.book'].sudo().browse(book_id)
        if not book.exists():
            return request.not_found()

        member = self._get_current_member()
        if not member:
            return request.redirect('/web/login?redirect=/library/book/%d' % book_id)

        # Check existing reservation
        existing = request.env['library.reservation'].sudo().search([
            ('member_id', '=', member.id),
            ('book_id', '=', book_id),
            ('state', 'in', ['draft', 'reserved']),
        ], limit=1)
        if not existing:
            from datetime import timedelta
            expiry = fields.Date.today() + timedelta(days=3)
            request.env['library.reservation'].sudo().create({
                'member_id': member.id,
                'book_id': book_id,
                'reservation_date': fields.Date.today(),
                'expiry_date': expiry,
                'state': 'reserved',
            })

        return request.redirect('/library/book/%d' % book_id)

    # ------------------------------------------------------------------
    # Collection detail
    # ------------------------------------------------------------------

    @http.route(['/library/collection/<int:cid>'], type='http',
                auth='public', website=True)
    def collection_detail(self, cid, **kw):
        """Digital collection landing page."""
        collection = request.env['library.digital.collection'].sudo().browse(cid)
        if not collection.exists():
            return request.not_found()

        resources = request.env['library.digital.resource'].sudo().search([
            ('collection_id', '=', cid),
            ('state', '=', 'published'),
            ('is_available', '=', True),
        ])
        member = self._get_current_member()
        values = {
            'page_name': 'opac_collection',
            'collection': collection,
            'resources': resources,
            'member': member,
        }
        return request.render('university_management.opac_collection_detail', values)

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _check_resource_access(self, resource, member):
        """Return True if the member/visitor is allowed to access this resource."""
        if resource.access_type == 'open':
            return True
        if not member:
            return False
        if not member.digital_access_enabled:
            return False
        if resource.access_type in ('member', 'subscribed'):
            return member.state == 'active'
        if resource.access_type == 'restricted':
            # Future: check allowed_member_types
            return member.state == 'active'
        return False