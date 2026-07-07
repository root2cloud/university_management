# -*- coding: utf-8 -*-

import base64
from odoo import http
from odoo.http import request, Response


class IICPosterController(http.Controller):

    @http.route('/iic/poster/<int:poster_id>/download', type='http', auth='user')
    def download_poster(self, poster_id, **kwargs):
        """Download IIC event poster as PDF/image."""
        poster = request.env['iic.poster'].sudo().browse(poster_id)
        if not poster.exists():
            return request.not_found()

        if poster.poster_image:
            image_data = base64.b64decode(poster.poster_image)
            filename = poster.poster_filename or f'IIC_Poster_{poster.id}.png'
            return Response(
                image_data,
                headers={
                    'Content-Type': 'image/png',
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Content-Length': len(image_data),
                }
            )
        # Fallback: redirect to event poster page
        return request.redirect(f'/web#id={poster_id}&model=iic.poster&view_type=form')
