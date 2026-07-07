# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request, content_disposition
import json
import logging
from datetime import datetime
from odoo.tools import ustr

_logger = logging.getLogger(__name__)

class PredictiveEngineController(http.Controller):
    @http.route('/predictive_engine/dashboard', type='http', auth='user', website=True)
    def show_dashboard(self, **kw):
        """
        Renders the dashboard view with interactive Plotly charts
        """
        _logger.info("Rendering interactive dashboard view")
        
        # Get filter values from URL parameters
        date_filter = kw.get('date_filter', '6months')  # Default to last 6 months
        year_filter = kw.get('year_filter')
        custom_date_from = kw.get('date_from')
        custom_date_to = kw.get('date_to')
        
        # Convert dates if provided
        if custom_date_from:
            try:
                custom_date_from = datetime.strptime(custom_date_from, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                custom_date_from = None
                
        if custom_date_to:
            try:
                custom_date_to = datetime.strptime(custom_date_to, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                custom_date_to = None
        # If user selected custom filter but left 'To Date' empty, default to today's date
        if kw.get('date_filter') == 'custom' and not custom_date_to:
            custom_date_to = datetime.today().date()
        
        # Validation: If custom selected and From Date missing, prepare error message
        error_message = ''
        if kw.get('date_filter') == 'custom' and not custom_date_from:
            error_message = 'Please select From Date.'
        
        # Call the model method with filters
        dashboard_data = request.env['predictive.engine'].get_dashboard_data(
            date_filter=date_filter,
            year_filter=year_filter,
            date_from=custom_date_from,
            date_to=custom_date_to
        )
        
        # Sanitize date_from and date_to to prevent XML injection
        date_from_str = ustr(custom_date_from.strftime('%Y-%m-%d')) if custom_date_from else ''
        date_to_str = ustr(custom_date_to.strftime('%Y-%m-%d')) if custom_date_to else ''
        # Today's date string for limiting future date selection in template inputs
        today_str = datetime.today().strftime('%Y-%m-%d')

        return request.render('DashBoat.predictive_engine_dashboard_page', {
            'dashboard_data': dashboard_data,
            'current_filter': date_filter,
            'selected_year': year_filter,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'error_message': error_message,
            'plotly_js': 'https://cdn.plot.ly/plotly-2.27.0.min.js',  # Include Plotly JS
            'today': today_str,
        })

    @http.route('/predictive_engine/crm_dashboard', type='http', auth='user', website=True)
    def show_crm_dashboard(self, **kw):
        """
        Renders the CRM dashboard view with interactive Plotly charts
        """
        _logger.info("Rendering interactive CRM dashboard view")

        # Get filter values from URL parameters
        date_filter = kw.get('date_filter', '6months')
        year_filter = kw.get('year_filter')
        custom_date_from = kw.get('date_from')
        custom_date_to = kw.get('date_to')

        # Convert dates if provided
        if custom_date_from:
            try:
                custom_date_from = datetime.strptime(custom_date_from, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                custom_date_from = None

        if custom_date_to:
            try:
                custom_date_to = datetime.strptime(custom_date_to, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                custom_date_to = None
        # If user selected custom filter but left 'To Date' empty, default to today's date
        if kw.get('date_filter') == 'custom' and not custom_date_to:
            custom_date_to = datetime.today().date()

        # Validation: If custom selected and From Date missing, prepare error message
        error_message = ''
        if kw.get('date_filter') == 'custom' and not custom_date_from:
            error_message = 'Please select From Date.'

        # Call the model method with filters
        dashboard_data = request.env['predictive.engine'].get_crm_dashboard_data(
            date_filter=date_filter,
            year_filter=year_filter,
            date_from=custom_date_from,
            date_to=custom_date_to
        )

        # Sanitize date_from and date_to for template
        date_from_str = ustr(custom_date_from.strftime('%Y-%m-%d')) if custom_date_from else ''
        date_to_str = ustr(custom_date_to.strftime('%Y-%m-%d')) if custom_date_to else ''
        today_str = datetime.today().strftime('%Y-%m-%d')

        return request.render('DashBoat.predictive_engine_crm_dashboard_page', {
            'dashboard_data': dashboard_data,
            'current_filter': date_filter,
            'selected_year': year_filter,
            'date_from': date_from_str,
            'date_to': date_to_str,
            'error_message': error_message,
            'plotly_js': 'https://cdn.plot.ly/plotly-2.27.0.min.js',
            'today': today_str,
        })

    @http.route('/predictive_engine/chatbot', type='json', auth='user', methods=['POST'])
    def chatbot_response(self, message):
        """
        Handles chatbot messages by calling the process_query method of predictive.engine
        """
        _logger.info(f"Received chatbot message: {message}")
        
        try:
            # Create a new predictive.engine record to process the query
            engine = request.env['predictive.engine'].create({
                'query': message,
                'name': f"Query: {message[:50]}" if message else f"Query {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            })
            
            # Process the query using the existing method
            result = engine.process_query()
            
            # Fetch the processed results
            engine = request.env['predictive.engine'].browse(engine.id)
            
            # Prepare the response
            response = {
                'response': engine.result_data or "No data found.",
                'insights': engine.insights or "No insights available.",
                'charts_html': engine.charts_html or "",
                'sql_query': engine.sql_query or "No SQL query generated.",
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return response
        except Exception as e:
            _logger.error(f"Error processing chatbot message: {str(e)}")
            return {
                'response': f"Error: {str(e)}",
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    @http.route('/predictive_engine/chart_insight', type='json', auth='user', methods=['POST'])
    def chart_insight(self, chart_key=None, date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """
        Return AI-generated insights for a given dashboard chart, respecting current filters.
        Expects: chart_key identifying the chart and optional date filters.
        """
        try:
            # Tolerate different JSON payload shapes and Odoo versions
            try:
                payload = getattr(request, 'jsonrequest', None) or {}
                if not payload:
                    # Fallback: werkzeug request JSON/body
                    try:
                        payload = request.httprequest.get_json(silent=True) or {}
                    except Exception:
                        raw = request.httprequest.data if hasattr(request, 'httprequest') else None
                        payload = json.loads((raw or b'').decode('utf-8') or '{}') if raw else {}
            except Exception:
                payload = {}
            chart_key = chart_key or payload.get('chart_key')
            date_filter = (payload.get('date_filter') or date_filter or '6months')
            year_filter = payload.get('year_filter') if payload.get('year_filter') is not None else year_filter
            date_from = payload.get('date_from') if payload.get('date_from') is not None else date_from
            date_to = payload.get('date_to') if payload.get('date_to') is not None else date_to

            # Normalize dates
            if date_from:
                try:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                except Exception:
                    date_from = None
            if date_to:
                try:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                except Exception:
                    date_to = None

            # Measure latency
            import time, re, html
            t0 = time.perf_counter()
            insight = request.env['predictive.engine'].sudo().get_chart_insight(
                chart_key=chart_key,
                date_filter=date_filter or '6months',
                year_filter=year_filter,
                date_from=date_from,
                date_to=date_to,
            )
            t_ms = int((time.perf_counter() - t0) * 1000)
            # Verbose logging for troubleshooting
            try:
                _logger.info(
                    "----- start ------- chart_insight: key=%s, date_filter=%s, year=%s, date_from=%s, date_to=%s, payload=%s",
                    chart_key, date_filter, year_filter, date_from, date_to, payload
                )
                # Configurable truncation for HTML preview
                try:
                    icp = request.env['ir.config_parameter'].sudo()
                    trunc = int(icp.get_param('dashboat.ai_log_truncate', '2000') or '2000')
                except Exception:
                    trunc = 2000
                # Remove emoji characters for Windows console compatibility
                def remove_emojis(text):
                    """Remove emoji characters that cause Windows console encoding errors"""
                    if not text:
                        return text
                    # Replace common emojis with ASCII equivalents
                    emoji_map = {
                        '📊': '[Chart]',
                        '✅': '[OK]',
                        '⚠️': '[Warning]',
                        '❌': '[Error]',
                        '🎯': '[Target]',
                        '💰': '[Money]',
                        '📈': '[Up]',
                        '📉': '[Down]',
                        '✓': '[Check]',
                        '✗': '[X]',
                    }
                    for emoji, replacement in emoji_map.items():
                        text = text.replace(emoji, replacement)
                    # Remove any remaining emoji characters (Unicode range)
                    try:
                        text = text.encode('ascii', 'ignore').decode('ascii')
                    except:
                        pass
                    return text
                
                preview = (insight[:trunc] + '...') if insight and len(insight) > trunc else insight
                preview_safe = remove_emojis(preview)
                _logger.info("chart_insight result (key=%s): %s", chart_key, preview_safe)
                # Plain-text bullets for readability (mask sensitive numeric values)
                try:
                    text = insight or ''
                    text = text.replace('<br>', '\n')
                    text = re.sub(r'<[^>]+>', '', text)
                    text = html.unescape(text)
                    # Remove emojis for console compatibility
                    text = remove_emojis(text)
                    # Conditional masking via system parameter
                    mask = True
                    try:
                        icp = request.env['ir.config_parameter'].sudo()
                        mask = (icp.get_param('dashboat.ai_log_mask', '1') or '1') not in ('0', 'false', 'False')
                    except Exception:
                        mask = True
                    if mask:
                        # Mask currency-like numbers and qty values (support $ and Rs)
                        text = re.sub(r'\$\s*\d[\d,\.]*', '$***', text)
                        text = re.sub(r'Rs\s*\d[\d,\.]*', 'Rs***', text)
                        text = re.sub(r'qty\s*\d[\d,\.]*', 'qty***', text, flags=re.IGNORECASE)
                    # Collapse excessive whitespace
                    text = re.sub(r'\n{3,}', '\n\n', text).strip()
                    plain_preview = (text[:trunc] + '...') if len(text) > trunc else text
                    _logger.info(
                        "chart_insight latency_ms=%s plain_text (%s):\n%s",
                        t_ms,
                        'masked' if mask else 'unmasked',
                        plain_preview,
                    )
                except Exception:
                    pass
                _logger.info("----- end ------- chart_insight")
            except Exception:
                # Do not break response due to logging failure
                pass
            return {'ok': True, 'html': insight}
        except Exception as e:
            # Log full details and propagate a readable message back to UI
            _logger.exception(f"Chart insight error for {chart_key}")
            msg = ustr(getattr(e, 'name', '') or getattr(e, 'args', [''])[0] or str(e))
            if not msg:
                msg = str(e)
            return {'ok': False, 'error': msg}

    @http.route('/predictive_engine/dashboard_report', type='http', auth='user', website=True)
    def dashboard_report(self, dashboard='sales', date_filter='6months', year_filter=None, date_from=None, date_to=None, **kw):
        """
        Generate a comprehensive PDF report for Sales or CRM dashboard.
        Accepts same filters as dashboards via query params.
        """
        try:
            # Parse dates if present
            if date_from:
                try:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                except Exception:
                    date_from = None
            if date_to:
                try:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                except Exception:
                    date_to = None

            engine = request.env['predictive.engine'].sudo().search([], limit=1)
            if not engine:
                engine = request.env['predictive.engine'].sudo().create({'name': 'Dashboard Report'})

            pdf_buffer = engine.generate_dashboard_report_pdf_fast(
                dashboard='crm' if (dashboard or '').lower() == 'crm' else 'sales',
                date_filter=date_filter or '6months',
                year_filter=year_filter,
                date_from=date_from,
                date_to=date_to,
            )
            pdf_data = pdf_buffer.getvalue()
            filename = f"{('CRM' if (dashboard or '').lower()=='crm' else 'Sales')}_dashboard_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', str(len(pdf_data))),
                ('Content-Disposition', content_disposition(filename)),
            ]
            return request.make_response(pdf_data, headers)
        except Exception as e:
            _logger.error(f"Dashboard report error: {e}")
            return request.make_response(f"Error generating report: {e}".encode('utf-8'), [('Content-Type', 'text/plain; charset=utf-8')])

    @http.route('/DashBoat/download_chat_pdf/<int:chat_id>', type='http', auth='user')
    def download_chat_pdf(self, chat_id, **kwargs):
        Chat = request.env['chatbot.history'].sudo()
        chat = Chat.browse(chat_id)
        if not chat or not chat.exists():
            return request.not_found()
        if chat.is_user:
            return request.make_response(
                b'Cannot generate PDF for a user message.',
                [('Content-Type', 'text/plain; charset=utf-8')],
            )

        engine = chat.engine_id or request.env['predictive.engine'].sudo().search([], limit=1)
        if not engine:
            return request.make_response(
                b'No predictive engine found to generate PDF.',
                [('Content-Type', 'text/plain; charset=utf-8')],
            )

        try:
            pdf_buffer = engine.generate_single_chat_pdf(chat_id)
            if not pdf_buffer:
                return request.not_found()
            pdf_data = pdf_buffer.getvalue()
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', str(len(pdf_data))),
                ('Content-Disposition', content_disposition('chat_message.pdf')),
            ]
            return request.make_response(pdf_data, headers)
        except Exception as e:
            msg = f'Failed to generate PDF: {e}'.encode('utf-8', errors='ignore')
            return request.make_response(
                msg,
                [('Content-Type', 'text/plain; charset=utf-8')],
            )
