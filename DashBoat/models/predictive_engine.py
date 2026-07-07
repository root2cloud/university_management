# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import base64
import re
from openai import OpenAI
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer, Image, HRFlowable, ListFlowable, ListItem, PageBreak
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime, timedelta
import logging
import numpy as np
import plotly.graph_objects as go
import psycopg2.errors as pg_errors
import threading

_logger = logging.getLogger(__name__)

SALES_GUIDANCE = """
You are an expert PostgreSQL developer working with an Odoo 18 database.
Return ONLY a single SELECT statement (no comments, no backticks, no code fences).
Use tables and columns from the schema below. Quote identifiers with double quotes when needed.
Always use explicit JOINs via *_id foreign keys to related tables' "id".
Never perform DDL or DML. SELECT only. If aggregation is used, include appropriate GROUP BY.
If the result can be very large, include a LIMIT 200 unless the user asked for a full aggregation.
Always use meaningful table aliases:
- "sale_order" AS so
- "sale_order_line" AS sol
- "res_partner" AS rp (for customers)
- "product_product" AS pp
- "product_template" AS pt
- "res_users" AS ru (for salesperson user)
- "res_partner" AS srp (for salesperson's partner)

IMPORTANT SALES RULES:
- Always filter sales orders with: WHERE "so"."state" IN ('sale','done')
- For "sales performance by salesperson", calculate the sum of "so"."amount_total" for confirmed orders, grouped by salesperson. Join "res_users" AS ru ON "so"."user_id" = "ru"."id" and then "res_partner" AS srp ON "ru"."partner_id" = "srp"."id" to get the salesperson's name ("srp"."name").
- If joining "sale_order_line", it must join through "sale_order" with the same state filter applied.
- For any time-based filtering (year, month, date ranges), always use "so"."date_order" (not create_date).
- Only include other states (e.g., 'draft', 'sent', 'cancel') if the user explicitly asks for them.

IMPORTANT NAME MATCHING RULE:
- If the user asks for a customer by name, use WHERE "rp"."name" ILIKE '%name%'.
- If the user asks for a salesperson by name, join "res_users" AS ru ON "so"."user_id" = "ru"."id",
  then join "res_partner" AS srp ON "ru"."partner_id" = "srp"."id",
  and filter with WHERE "srp"."name" ILIKE '%name%'. To display the salesperson's name, select "srp"."name".
- If the user asks for a product by name, use ONLY WHERE ("pt"."name"::text ILIKE '%name%').
  Never use "pp"."name" for filtering, and never use ILIKE directly on "pt"."name" (must cast to text).
  Example: WHERE "pt"."name"::text ILIKE '%pen%' (not "pt"."name" ILIKE '%pen%' and not "pp"."name" ILIKE '%pen%')

IMPORTANT REGION RULE:
- If the user asks for sales by region, country, or geography, always join "res_country" AS rc ON "rp"."country_id" = "rc"."id"
  and display "rc"."name" AS country_name instead of numeric IDs. 
  Group and order results using "rc"."name" when appropriate.

Schema:
{schema_text}

User request: {prompt}
"""

CRM_GUIDANCE = """
You are an expert PostgreSQL developer working with an Odoo 18 CRM database.
Return ONLY a single SELECT statement (no comments, no backticks, no code fences).
Use tables and columns from the schema below. Quote identifiers with double quotes when needed.
Always use explicit JOINs via *_id foreign keys to related tables' "id".
Never perform DDL or DML. SELECT only. If aggregation is used, include appropriate GROUP BY.
If the result can be very large, include a LIMIT 200 unless the user asked for a full aggregation.
Always use meaningful table aliases:
- "crm_lead" AS cl
- "crm_stage" AS cs
- "crm_lost_reason" AS clr
- "res_users" AS ru (for salesperson)
- "res_partner" AS rp (for customer/partner)
- "utm_source" AS us
- "utm_medium" AS um
- "crm_team" AS ct

IMPORTANT CRM RULES:
- For "sales performance by salesperson", calculate the sum of "cl"."expected_revenue" for opportunities, grouped by salesperson. Join "res_users" AS ru ON "cl"."user_id" = "ru"."id" and then "res_partner" AS srp ON "ru"."partner_id" = "srp"."id" to get the salesperson's name ("srp"."name").
- For queries about "opportunities", "deals", or "pipeline", always filter with: WHERE "cl"."type" = 'opportunity' AND "cl"."active" = true.
- For queries about "leads", filter with: WHERE "cl"."type" = 'lead' AND "cl"."active" = true.
- If the user does not specify, assume they mean "opportunity".
- For any time-based filtering (year, month, date ranges), always use "cl"."create_date".
- For "revenue" or "expected revenue", use the "cl"."expected_revenue" column. When aggregating, use SUM("cl"."expected_revenue").
- For "won revenue", sum "cl"."expected_revenue" for opportunities in a "won" stage. Join "crm_stage" AS cs ON "cl"."stage_id" = "cs"."id" and use WHERE "cs"."is_won" = true.
- For "conversion rate", calculate the percentage of opportunities in a "won" stage. The formula is (COUNT of won opportunities / COUNT of all opportunities) * 100. Use "cs"."is_won" = true to identify won opportunities.
- For "pipeline funnel" or "opportunities by stage", count opportunities for each stage. Join "crm_stage" AS cs ON "cl"."stage_id" = "cs"."id", then GROUP BY "cs"."name", "cs"."sequence" and ORDER BY "cs"."sequence". Select "cs"."name" and COUNT("cl"."id").
- For "lost reason analysis", count lost opportunities for each reason. Filter for `WHERE "cl"."type" = 'opportunity' AND "cl"."active" = false AND "cl"."lost_reason_id" IS NOT NULL`. Join `crm_lost_reason` AS `clr` ON `cl"."lost_reason_id" = "clr"."id"`. Group by `clr"."name` and count `cl"."id`.
- For "Lead Source Effectiveness", analyze both leads and opportunities. Use LEFT JOINs on "utm_source" AS us and "utm_medium" AS um. The source name should be determined using COALESCE("us"."name", "um"."name", 'Unknown Source'). Group by this derived source name and calculate metrics like total count, won opportunities, and revenue.

IMPORTANT JSONB NAME MATCHING RULE:
- For the following jsonb fields, always use this filter format: (field ->> 'en_US') ILIKE '%keyword%' OR field::text ILIKE '%keyword%'.
- This applies to: "crm_stage"."name", "crm_lead"."name", "crm_lead"."contact_name", "crm_lead"."title", "res_users"."name", "res_partner"."name", "res_partner"."title", "utm_source"."name", "utm_medium"."name", "utm_campaign"."name", "crm_team"."name".

IMPORTANT NAME MATCHING RULE:
- If the user asks for a customer by name, use WHERE "rp"."name" ILIKE '%name%'.
- If the user asks for a salesperson by name, join "res_users" AS ru ON "cl"."user_id" = "ru"."id", then join "res_partner" AS srp ON "ru"."partner_id" = "srp"."id", and filter with WHERE "srp"."name" ILIKE '%name%'. To display the salesperson's name, select "srp"."name".
- If the user asks for a stage by name, join "crm_stage" AS cs ON "cl"."stage_id" = "cs"."id" and filter with WHERE "cs"."name"::text ILIKE '%name%'.
- If the user asks for a lost reason, join "crm_lost_reason" AS clr ON "cl"."lost_reason_id" = "clr"."id" and filter with WHERE "clr"."name" ILIKE '%name%'.

IMPORTANT REGION RULE:
- If the user asks for opportunities by region, country, or geography, always join "res_country" AS rc ON "cl"."country_id" = "rc"."id"
  and display "rc"."name" AS country_name instead of numeric IDs. 
  Group and order results using "rc"."name" when appropriate.

Schema:
{schema_text}

User request: {prompt}
"""

class PredictiveEngine(models.Model):
    _name = 'predictive.engine'
    _description = 'DashBoat'
    
    # Class-level cache for API keys (in-memory, fast access)
    _api_key_cache = {}
    _matplotlib_lock = threading.Lock()
    _insight_lock = threading.Lock()

    name = fields.Char(string='Name', required=True, default=lambda self: f"Query {fields.Datetime.now()}")
    input_data = fields.Text(string='Input Data')
    prediction_result = fields.Float(string='Prediction Result')
    date = fields.Date(string='Date', default=fields.Date.today)
    query = fields.Text(string='User Query')
    sql_query = fields.Text(string='SQL Query')
    result_data = fields.Html(string='Result Data')
    charts = fields.Many2many('ir.attachment', string='Charts')
    insights = fields.Text(string='Insights')
    history_ids = fields.One2many('chatbot.history', 'engine_id', string='Chat History')
    charts_html = fields.Html(string="Charts HTML")
    dashboard_name = fields.Char(string="Dashboard Name", default="Sales")
    new_message = fields.Char(string="New Message")
    chat_html = fields.Html(string="Chat History (HTML)", compute="_compute_chat_html")
    conversation_summary = fields.Text(string="Conversation Summary")
    conversation_log = fields.Json(string="Conversation Log (FIFO)")
    use_full_schema = fields.Boolean(string="Use Full DB Schema", default=True, help="If enabled, the engine will introspect the full Odoo database schema and generate queries across all models, not only sales year tables.")
    user_questions = fields.One2many(
        comodel_name='chatbot.history',
        inverse_name='engine_id',
        string='User Questions',
        compute='_compute_user_questions',
        store=False,
    )

    # ---------- Utilities ----------
    def _is_number(self, value) -> bool:
        try:
            float(value)
            return True
        except Exception:
            return False

    @api.depends('history_ids')
    def _compute_user_questions(self):
        for rec in self:
            rec.user_questions = rec.history_ids.filtered(lambda h: h.is_user).sorted('create_date')

    @api.depends('history_ids')
    def _compute_chat_html(self):
        for rec in self:
            html = ""
            for msg in rec.history_ids.sorted('create_date'):
                if msg.is_user:
                    user_msg = (msg.message or "").strip()
                    if user_msg:
                        html += (
                            f'<div class="chat-bubble chat-bubble-user" '
                            f'style="align-self: flex-end; margin-bottom: 8px;">'
                            f'{user_msg}</div>'
                        )
                else:
                    html += (
                        '<div class="chat-bubble chat-bubble-bot" '
                        'style="align-self: flex-start; margin-bottom: 8px;">'
                    )
                    # if msg.sql_query:
                    # # Clean and format SQL query for display
                    #     formatted_sql = (msg.sql_query or "").replace('\n', '<br>').replace(' ', '&nbsp;')
                    #     html += f'<div style="margin-bottom:8px;"><b>SQL Query:</b><br><pre style="background:#f5f5f5;padding:8px;border:1px solid #ccc;border-radius:4px;">{formatted_sql}</pre></div>'
                    # # # if msg.result_data:
                    #     html += f'<div style="margin-bottom:8px;"><b>Table:</b><br>{msg.result_data}</div>'
                    if msg.insights:
                        html += f'<div style="margin-bottom:8px;"><b></b><br>{msg.insights}</div>'
                    # if msg.charts_html:
                    #     html += f'<div style="margin-bottom:8px;"><br>{msg.charts_html}</div>'
                    if not (msg.insights and "not a sales-related question" in msg.insights):
                        html += f'<div style="margin-top:8px;"><a href="/DashBoat/download_chat_pdf/{msg.id}" target="_blank" title="Download PDF" style="text-decoration:none;font-size:18px;vertical-align:middle;"><span class="fa fa-download"></span></a></div>'
                    html += '</div>'
            rec.chat_html = html

    def send_message(self):
        for rec in self:
            if not rec.new_message:
                continue
            # Greeting auto-reply: if the user says hi/hello/hey, send a friendly message
            user_text = (rec.new_message or "").strip()
            user_text_lower = user_text.lower()
            if re.fullmatch(r"\s*(hi+|hello+|hey+)\s*[,!\.]*", user_text_lower):
                user_msg = rec.env['chatbot.history'].create({
                    'engine_id': rec.id,
                    'is_user': True,
                    'message': rec.new_message,
                })
                rec.env['chatbot.history'].create({
                    'engine_id': rec.id,
                    'is_user': False,
                    'insights': 'Hello, I am a <b>Sales &amp; CRM Chatbot</b>. How can I help you?',
                    'user_message_id': user_msg.id,
                })
                rec.new_message = ""
                continue
            if not rec.use_full_schema and not (rec.is_sales_related_query(rec.new_message) or rec.is_crm_related_query(rec.new_message)):
                user_msg = rec.env['chatbot.history'].create({
                    'engine_id': rec.id,
                    'is_user': True,
                    'message': rec.new_message,
                })
                rec.env['chatbot.history'].create({
                    'engine_id': rec.id,
                    'is_user': False,
                    'insights': (
                        "Sorry, this is not a sales/CRM-related question. Please ask questions related to <b>Sales</b> or <b>CRM</b> data.<br><br>"
                        "For example, you can ask:<br>"
                        "- 2024 monthly sales data<br>"
                        "- Top 10 customers by sales in 2023<br>"
                        "- Sales by region last 90 days<br>"
                        "- Opportunities by stage for last 90 days<br>"
                        "- Lost opportunities by reason in 2025<br>"
                        "- Average deal size trend in 2025"
                    ),
                    'user_message_id': user_msg.id,
                })
                rec.new_message = ""
                continue
            user_msg = rec.env['chatbot.history'].create({
                'engine_id': rec.id,
                'is_user': True,
                'message': rec.new_message,
            })
            rec.query = rec.new_message
            # If query looks CRM-related, still run the same pipeline; insights builder will adapt
            rec.process_query()
            rec.env['chatbot.history'].create({
                'engine_id': rec.id,
                'is_user': False,
                'response': rec.result_data,
                'sql_query': rec.sql_query,
                'result_data': rec.result_data,
                'insights': rec.insights,
                'charts_html': rec.charts_html,
                'user_message_id': user_msg.id,
            })
            rec.new_message = ""

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                query = vals.get('query', '')
                vals['name'] = f"Query: {query[:50]}" if query else f"Query {fields.Datetime.now()}"
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and not vals['name']:
            query = vals.get('query', self.query or '')
            vals['name'] = f"Query: {query[:50]}" if query else f"Query {fields.Datetime.now()}"
        return super().write(vals)

    def load_api_key(self):
        """Fetch the OpenAI API key from prediction.analysis.registration model.
        Priority:
        1) Memory cache (fastest - no database query)
        2) By user email (exact match)
        3) Any record with API key (fallback)
        
        Uses in-memory caching to avoid repeated database queries.
        """
        user_email = self.env.user.email or 'No email'
        
        # Check memory cache first (fastest - no database query!)
        if user_email in self._api_key_cache:
            _logger.debug(f"[MEMORY CACHE HIT] Using cached OpenAI API key for user: {user_email}")
            return self._api_key_cache[user_email]
        
        _logger.info(f"[API KEY CHECK] Loading OpenAI API key for user: {user_email}")
        
        # 1) Try to find by user email first
        try:
            if user_email and user_email != 'No email':
                # Try with domain filter first
                data_analysis = self.env['prediction.analysis.registration'].search([
                    ('email', '=', user_email),
                    ('openai_api_key', '!=', False),
                    ('openai_api_key', '!=', '')
                ], limit=1)
                
                # If not found, try without API key filter and check manually
                if not data_analysis:
                    _logger.debug(f"No record found with domain filter for email {user_email}, trying manual check...")
                    data_analysis = self.env['prediction.analysis.registration'].search([
                        ('email', '=', user_email)
                    ], limit=5)
                    for rec in data_analysis:
                        try:
                            key = getattr(rec, 'openai_api_key', None)
                            if key and str(key).strip() and str(key).strip() != 'False':
                                api_key = str(key).strip()
                                _logger.info(f"[OK] Loaded OpenAI API key from prediction.analysis.registration for user: {user_email} (record ID: {rec.id})")
                                # Store in memory cache (fastest!)
                                self._api_key_cache[user_email] = api_key
                                return api_key
                        except Exception as e:
                            _logger.debug(f"Error accessing API key from record {rec.id}: {e}")
                            continue
                else:
                    key = data_analysis.openai_api_key
                    if key and str(key).strip() and str(key).strip() != 'False':
                        api_key = str(key).strip()
                        _logger.info(f"[OK] Loaded OpenAI API key from prediction.analysis.registration for user: {user_email}")
                        # Store in memory cache (fastest!)
                        self._api_key_cache[user_email] = api_key
                        return api_key
        except Exception as e:
            _logger.error(f"Error checking prediction.analysis.registration by email: {e}", exc_info=True)
        
        # 2) Fallback: ANY prediction.analysis.registration record with a key
        try:
            # First, try to find any record with non-empty API key
            any_reg = self.env['prediction.analysis.registration'].search([
                ('openai_api_key', '!=', False),
                ('openai_api_key', '!=', '')
            ], order='id desc', limit=1)
            
            # If no record found with domain filter, try to get all and check manually
            if not any_reg:
                _logger.debug("No record found with domain filter, trying to get all records...")
                all_records = self.env['prediction.analysis.registration'].search([], order='id desc', limit=10)
                _logger.debug(f"Found {len(all_records)} prediction.analysis.registration records")
                for rec in all_records:
                    try:
                        key = getattr(rec, 'openai_api_key', None)
                        if key and str(key).strip() and str(key).strip() != 'False':
                            api_key = str(key).strip()
                            _logger.info(f"[OK] Loaded OpenAI API key from prediction.analysis.registration (record ID: {rec.id}, email: {getattr(rec, 'email', 'N/A')})")
                            # Store in memory cache (fastest!)
                            self._api_key_cache[user_email] = api_key
                            return api_key
                    except Exception as e:
                        _logger.debug(f"Error accessing API key from record {rec.id}: {e}")
                        continue
            else:
                key = any_reg.openai_api_key
                if key and str(key).strip() and str(key).strip() != 'False':
                    api_key = str(key).strip()
                    _logger.info(f"[OK] Loaded OpenAI API key from prediction.analysis.registration (any record, ID: {any_reg.id})")
                    # Store in memory cache (fastest!)
                    self._api_key_cache[user_email] = api_key
                    return api_key
                else:
                    _logger.debug(f"Record {any_reg.id} found but API key is empty or invalid")
        except Exception as e:
            _logger.error(f"Error checking prediction.analysis.registration (any record): {e}", exc_info=True)
        
        # If we reach here, no key was found - provide helpful error
        _logger.error(f"[API KEY ERROR] No OpenAI API key found for user: {user_email}")
        _logger.error("[API KEY ERROR] Checked: prediction.analysis.registration model")
        _logger.error("[API KEY ERROR] SOLUTION: Add API key in Prediction Analysis Registration:")
        _logger.error("  Settings > Prediction Analysis Registration")
        _logger.error("  Create/Edit record with your email")
        _logger.error("  Add OpenAI API Key field")
        _logger.error("  Click 'Validate OpenAI API Key' to test")
        _logger.error("  Save and restart Odoo")
        raise UserError(
            "OpenAI API key missing.\n\n"
            "Please configure your API key:\n\n"
            "1. Go to: Settings > Prediction Analysis Registration\n"
            "2. Create or edit your registration record\n"
            "3. Fill in:\n"
            "   - Name: Your name\n"
            "   - Email: Your email\n"
            "   - OpenAI API Key: your-api-key-here\n"
            "4. Click 'Validate OpenAI API Key' to test (optional)\n"
            "5. Save\n"
            "6. Restart Odoo\n"
            "7. Try AI Analysis button again\n\n"
            "Note: The API key will be loaded based on your logged-in user email."
        )

    def _pick_year_tables(self):
        """[DEPRECATED] Legacy year-based path removed. Full schema introspection is always used."""
        raise UserError("Legacy year-based path has been removed. The engine now always uses full DB schema introspection.")

    def _build_sql(self, prompt, tables):
        """[DEPRECATED] Legacy SQL builder removed. Use _build_sql_full_schema instead."""
        raise UserError("Legacy _build_sql() is removed. Use _build_sql_full_schema with introspected schema.")

    def _introspect_db_schema(self, prompt, limit_tables=30):
        """Inspect installed Odoo models (official tables) and select a relevant subset for the prompt.
        Returns a dict {table_name: [columns...]}
        """
        keywords = set(re.findall(r"[a-zA-Z_]+", (prompt or '').lower()))

        # Blacklist technical/transient prefixes by default
        blacklist_prefixes = (
            'ir_', 'mail_', 'bus_', 'utm_', 'web_', 'digest_', 'queue_', 'report_', 'fetchmail_', 'base_',
            'wkf_', 'barcodes_', 'rating_', 'social_', 'iap_', 'web_tour_', 'auth_', 'http_'
        )

        # Business alias boosts: map common words to preferred Odoo tables
        alias_boost = {
            'invoice': ['account_move', 'account_move_line'],
            'invoices': ['account_move', 'account_move_line'],
            'bill': ['account_move', 'account_move_line'],
            'bills': ['account_move', 'account_move_line'],
            'account': ['account_move', 'account_move_line'],
            'ar': ['account_move', 'account_move_line'],
            'ap': ['account_move', 'account_move_line'],
            'sale': ['sale_order', 'sale_order_line'],
            'sales': ['sale_order', 'sale_order_line'],
            'quotation': ['sale_order'],
            'quotations': ['sale_order'],
            'purchase': ['purchase_order', 'purchase_order_line'],
            'po': ['purchase_order', 'purchase_order_line'],
            'vendor': ['purchase_order', 'res_partner'],
            'stock': ['stock_move', 'stock_picking', 'stock_quant'],
            'delivery': ['stock_picking', 'stock_move'],
            'inventory': ['stock_move', 'stock_quant'],
            'crm': ['crm_lead'],
            'opportunity': ['crm_lead'],
            'opportunities': ['crm_lead'],
            'lead': ['crm_lead'],
            'leads': ['crm_lead'],
            'stage': ['crm_stage'],
            'stages': ['crm_stage'],
            'pipeline': ['crm_lead', 'crm_stage'],
            'lost': ['crm_lead', 'crm_lost_reason'],
            'reason': ['crm_lost_reason'],
            'reasons': ['crm_lost_reason'],
            'activity': ['mail_activity'],
            'activities': ['mail_activity'],
            'source': ['utm_source'],
            'sources': ['utm_source'],
            'utm': ['utm_source', 'utm_medium'],
            'medium': ['utm_medium'],
            'team': ['crm_team'],
            'mrp': ['mrp_production'],
            'manufacturing': ['mrp_production'],
            'employee': ['hr_employee'],
            'attendance': ['hr_attendance'],
            'project': ['project_task'],
            'task': ['project_task'],
            'pos': ['pos_order', 'pos_order_line'],
            'helpdesk': ['helpdesk_ticket'],
            'partner': ['res_partner'],
            'customer': ['res_partner'],
            'product': ['product_product', 'product_template'],
            'category': ['product_category'],
            'user': ['res_users'],
            'country': ['res_country'],
            'countries': ['res_country'],
        }

        # 1) Collect official model tables from Odoo registry
        model_table_map = {}
        for model_name in self.env.registry.models:
            try:
                model = self.env[model_name]
                table = getattr(model, '_table', None)
                if not table or not isinstance(table, str):
                    continue
                # Skip blacklisted prefixes unless the prompt explicitly mentions them
                if table.startswith(blacklist_prefixes) and not any(kw in table for kw in keywords):
                    continue
                model_table_map[model_name] = table
            except Exception:
                # Some registry entries may not be accessible via env
                continue

        official_tables = sorted(set(model_table_map.values()))
        # Optional hard whitelist supplied by user to constrain selection
        preferred_tables = {
            'sale_order', 'sale_order_line', 'res_partner', 'res_country',
            # Extra (extended queries)
            'product_product', 'product_template', 'product_category',
            'res_users', 'account_move', 'stock_picking', 'stock_move',
            # CRM core
            'crm_lead', 'crm_stage', 'crm_lost_reason', 'mail_activity',
            # Marketing attribution (if installed)
            'utm_source', 'utm_medium',
            # Sales team (for CRM team filters)
            'crm_team',
        }
        whitelisted = [t for t in official_tables if t in preferred_tables]
        if whitelisted:
            official_tables = whitelisted
        if not official_tables:
            return {}

        # 2) Fetch columns for official tables only
        cr = self.env.cr
        table_cols = {}
        for table in official_tables:
            try:
                cr.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (table,)
                )
                cols = [r[0] for r in cr.fetchall()]
                if cols:
                    table_cols[table] = cols
            except Exception:
                # Ignore missing tables
                continue

        if not table_cols:
            return {}

        # 3) Scoring: keyword hits + alias boosts + common business table boost
        def score(table, cols):
            s = 0
            tl = table.lower()
            if any(kw in tl for kw in keywords):
                s += 5
            for c in cols:
                cl = c.lower()
                if any(kw == cl or (kw in cl and len(kw) > 2) for kw in keywords):
                    s += 1
            for kw in keywords:
                for preferred in alias_boost.get(kw, []):
                    if preferred == table:
                        s += 4
            if table in (
                'sale_order', 'sale_order_line',
                'account_move', 'account_move_line',
                'res_partner', 'res_users', 'res_country',
                'product_product', 'product_template', 'product_category',
                'stock_move', 'stock_picking', 'stock_quant',
                'purchase_order', 'purchase_order_line',
                'crm_lead', 'mrp_production',
                'hr_employee', 'hr_attendance',
                'project_task', 'pos_order', 'pos_order_line',
                'helpdesk_ticket'
            ):
                s += 3
            return s

        scored = sorted(table_cols.items(), key=lambda kv: score(kv[0], kv[1]), reverse=True)
        selected = dict(scored[:limit_tables]) if scored else {}
        return selected

    def _build_chat_history_messages(self, current_user_prompt, system_preamble=None, max_pairs=6):
        """Construct a messages array including brief conversation memory and recent turns.
        - Includes an optional system preamble plus the rolling conversation_summary
        - Appends up to max_pairs recent (user, assistant) exchanges
        - Ends with the current user prompt
        """
        messages = []
        # System preamble + conversation summary
        sys_parts = []
        if system_preamble:
            sys_parts.append(system_preamble)
        if getattr(self, 'conversation_summary', None):
            sys_parts.append(f"Conversation summary: {self.conversation_summary}")
        if sys_parts:
            messages.append({"role": "system", "content": "\n\n".join(sys_parts)})

        # Prefer compact FIFO conversation_log if available; else fallback to history_ids
        log = getattr(self, 'conversation_log', None) or []
        if isinstance(log, list) and log:
            # Use last max_pairs entries
            for item in log[-max_pairs:]:
                try:
                    u = (item.get('user') or '')[:1000]
                    a_ins = (item.get('assistant') or '')[:1200]
                    a_sql = (item.get('sql') or '')[:1000]
                    if u:
                        messages.append({"role": "user", "content": u})
                    a_parts = []
                    if a_sql:
                        a_parts.append(f"SQL: {a_sql}")
                    if a_ins:
                        a_parts.append(f"Insights: {a_ins}")
                    if a_parts:
                        messages.append({"role": "assistant", "content": "\n".join(a_parts)})
                except Exception:
                    continue
        else:
            # Recent history pairs
            try:
                history = (self.history_ids or self.env['chatbot.history']).sorted('create_date')
                bot_msgs = [m for m in history if not m.is_user][-max_pairs:]
                for bot in bot_msgs:
                    user_q = (getattr(bot, 'user_message_id', False) and bot.user_message_id.message) or ''
                    if user_q:
                        messages.append({"role": "user", "content": str(user_q)[:1000]})
                    assistant_text = []
                    sql_q = (bot.sql_query or '').strip()
                    if sql_q:
                        assistant_text.append(f"SQL: {sql_q[:1000]}")
                    ins = (bot.insights or bot.response or '').strip()
                    if ins:
                        assistant_text.append(f"Insights: {ins[:1200]}")
                    if assistant_text:
                        messages.append({"role": "assistant", "content": "\n".join(assistant_text)})
            except Exception:
                pass

        # Current user prompt at the end
        messages.append({"role": "user", "content": current_user_prompt})
        return messages

    # ---------------- FIFO conversation log helpers ----------------
    def _is_query_relevant(self, user_text):
        """Semantic relevance with LLM fallback to keyword overlap.
        Returns True if current question is related to recent context, else False.
        """
        try:
            if not user_text:
                return False
            # Build a compact context string from summary + last FIFO entry
            ctx_parts = []
            if self.conversation_summary:
                ctx_parts.append(self.conversation_summary[:800])
            log = self.conversation_log or []
            if log:
                last = log[-1]
                ctx_parts.append((last.get('user') or '')[:400])
                ctx_parts.append((last.get('assistant') or '')[:600])
            context_snippet = "\n".join([p for p in ctx_parts if p])

            # If we have enough context, ask the LLM to judge relevance
            if context_snippet:
                judge_prompt = (
                    "You are a classifier. Determine if the NEW_QUESTION is related to the CONTEXT. "
                    "Answer with a single word: YES or NO.\n\n"
                    f"CONTEXT:\n{context_snippet}\n\n"
                    f"NEW_QUESTION:\n{str(user_text)[:600]}\n\n"
                    "Answer:"
                )
                try:
                    result = self._openai_chat(messages=[{"role": "user", "content": judge_prompt}], max_tokens=2)
                    if result.strip().upper().startswith('Y'):
                        return True
                    if result.strip().upper().startswith('N'):
                        return False
                except Exception:
                    # fall through to keyword heuristic
                    pass

            # Heuristic keyword overlap fallback
            text = (str(user_text) or '').lower()
            words = set([w for w in re.findall(r"[a-zA-Z0-9_]+", text) if len(w) > 2])
            if self.conversation_summary:
                sum_words = set(re.findall(r"[a-zA-Z0-9_]+", self.conversation_summary.lower()))
                if len(words & sum_words) >= 2:
                    return True
            if log:
                last = log[-1]
                ctx = ((last.get('user') or '') + ' ' + (last.get('assistant') or '')).lower()
                ctx_words = set([w for w in re.findall(r"[a-zA-Z0-9_]+", ctx) if len(w) > 2])
                if len(words & ctx_words) >= 2:
                    return True
        except Exception:
            pass
        return False

    def _append_to_conversation_log(self, user_text, assistant_text, sql_text=None, max_len=5):
        try:
            log = self.conversation_log or []
            log.append({
                'user': (user_text or '')[:1000],
                'assistant': (assistant_text or '')[:1500],
                'sql': (sql_text or '')[:2000],
            })
            if len(log) > max_len:
                # FIFO trim
                log = log[-max_len:]
            self.conversation_log = log
        except Exception:
            # Non-fatal
            pass

    def _refresh_conversation_summary(self, max_tokens=220):
        """Summarize the recent conversation into key entities, filters, time ranges, and intent."""
        try:
            history = (self.history_ids or self.env['chatbot.history']).sorted('create_date')
            # Build a compact transcript of the last 10 turns (user + assistant)
            lines = []
            for msg in history[-20:]:
                if msg.is_user:
                    lines.append(f"User: {(msg.message or '')[:400]}")
                else:
                    snippet = (msg.insights or msg.response or '')
                    if msg.sql_query:
                        lines.append(f"BotSQL: {msg.sql_query[:400]}")
                    if snippet:
                        lines.append(f"Bot: {snippet[:600]}")
            transcript = "\n".join(lines)
            prompt = (
                "Summarize this conversation for future follow-ups. Capture entities (customers, products, salespersons), "
                "filters (dates, regions), key metrics, and user intent. Be very concise (<= 10 lines).\n\n" + transcript
            )
            summary = self._openai_chat(messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens)
            # Store trimmed summary
            self.conversation_summary = (summary or '')[:2000]
        except Exception:
            # Do not block main flow on summary failures
            pass

    def _build_sql_full_schema(self, prompt, schema_map):
        """Build a SELECT using OpenAI with a provided schema map of tables -> columns.
        Ensures we only accept SELECT statements and quote identifiers.
        """
        # Create a concise schema block
        schema_lines = []
        for t, cols in schema_map.items():
            # cap columns per table to keep prompt size reasonable
            shown_cols = cols[:40]
            schema_lines.append(f"Table: {t} (columns: {', '.join(shown_cols)})")
        schema_text = "\n".join(schema_lines) or "(no tables found)"

        # Determine if the query is sales or CRM related to pick the right guidance
        if self.is_crm_related_query(prompt):
            guidance_template = CRM_GUIDANCE
        else:
            # Default to sales guidance
            guidance_template = SALES_GUIDANCE

        guidance = guidance_template.format(schema_text=schema_text, prompt=prompt)

        # Compose messages with conversation context
        system_preamble = "You are assisting with conversational analytics in Odoo. Use prior turns if relevant."
        messages = self._build_chat_history_messages(guidance, system_preamble=system_preamble, max_pairs=6)

        sql = self._openai_chat(messages=messages, max_tokens=600)
        sql = re.sub(r'^```(?:sql)?\s*|\s*```$', '', sql, flags=re.IGNORECASE).strip()

        if not re.match(r'^\s*SELECT\b', sql, re.IGNORECASE):
            raise UserError("Only SELECT statements are allowed.")
        return sql

    def _clean_numeric_casts(self, sql):
        columns_to_clean = ["total_amount", "total_amount_usd", "subtotal", "tax", "amount"]
        for column in columns_to_clean:
            pattern = rf'CAST\(\s*{column}\s*AS\s+double precision\)'
            replacement = (
                f"CAST(REGEXP_REPLACE({column}, '[^0-9\\.]', '', 'g') AS double precision)"
            )
            sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
        return sql

    def _quote_table_names(self, sql):
        sql = re.sub(
            r'\bFROM\s+(\d{4}_[a-zA-Z0-9_]+)',
            r'FROM "\1"',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'\bJOIN\s+(\d{4}_[a-zA-Z0-9_]+)',
            r'JOIN "\1"',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r'\bUNION\s+ALL\s+SELECT\s+\*\s+FROM\s+(\d{4}_[a-zA-Z0-9_]+)',
            r'UNION ALL SELECT * FROM "\1"',
            sql,
            flags=re.IGNORECASE
        )
        return sql

    def _run_sql(self, sql):
        try:
            self.env.cr.execute(sql)
            cols = [desc[0] for desc in self.env.cr.description]
            rows = self.env.cr.fetchall()
            return cols, rows
        except pg_errors.SyntaxError as e:
            self.env.cr.rollback()
            raise UserError(f"SQL syntax error:\n{e.pgerror}\n\nSQL:\n{sql}")
        except Exception as e:
            self.env.cr.rollback()
            raise UserError(f"Execution error:\n{e}\n\nSQL:\n{sql}")

    def _rows_to_html(self, cols, rows):
        if not rows:
            return "<p>No data.</p>"
        header = "".join(f"<th>{c}</th>" for c in cols)
        body = "".join(
            "<tr>" + "".join(f"<td>{r}</td>" for r in row) + "</tr>" for row in rows
        )
        return (
            f'<div class="table-responsive">'
            f'<table class="table table-sm table-bordered">'
            f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
            f"</div>"
        )

    def _build_insights(self, cols, rows, prompt):
        if not rows:
            return "No data returned."
        summary = str(rows[:10])
        columns_str = ', '.join(cols)
        currency_symbol = self._detect_currency_symbol(cols, rows)

        # Define instruction templates
        SALES_INSIGHTS_INSTRUCTIONS = """
Instructions:
- First, show you understand the user's question by referencing it in the insights.
- Provide only the most important, actionable, and context-aware insights based on the user's question and the columns returned.
- Each insight must be specific to the data and query context, not generic.
- If possible, compare, rank, or highlight trends, anomalies, or key metrics.
- Each insight starts on a new line with a bullet point (-).
- Highlight important terms (e.g., sales, revenue, customer, salesperson, product, amounts, or key metrics) by wrapping them in **bold** markdown.
- For quantity values, prefix with 'qty' (e.g., qty 3.2).
- For amount, total sale, sale, amount, total amount values, prefix with '{currency_symbol}' (e.g., {currency_symbol}1200).
- Do NOT include generic statements like 'No data returned' or 'The table shows sales data.'
- Ensure insights are clear, concise, and highly relevant to the query and the columns shown.
""".format(currency_symbol=currency_symbol)

        CRM_INSIGHTS_INSTRUCTIONS = """
Instructions:
- First, show you understand the user's question by referencing it in the insights.
- Provide only the most important, actionable, and context-aware insights based on the user's question and the columns returned.
- Each insight must be specific to the data and query context, not generic.
- If possible, compare, rank, or highlight trends, anomalies, or key metrics related to opportunities, leads, stages, or revenue.
- Each insight starts on a new line with a bullet point (-).
- Highlight important terms (e.g., opportunity, lead, stage, revenue, salesperson, customer, deal size) by wrapping them in **bold** markdown.
- For monetary values like expected revenue or deal size, prefix with '{currency_symbol}' (e.g., {currency_symbol}1200).
- Do NOT mention "quantity" or "qty" as it is not relevant for CRM.
- Do NOT include generic statements like 'No data returned' or 'The table shows CRM data.'
- Ensure insights are clear, concise, and highly relevant to the query and the columns shown.
""".format(currency_symbol=currency_symbol)

        # Determine which instructions to use
        is_crm = self.is_crm_related_query(prompt)
        if is_crm:
            instructions = CRM_INSIGHTS_INSTRUCTIONS
        else:
            instructions = SALES_INSIGHTS_INSTRUCTIONS

        context_prompt = f"""
Given the following query result (max first 10 rows):
{summary}

User question: {prompt}

Columns available: {columns_str}

{instructions}
"""
        # Compose messages with recent context for insights as well
        system_preamble = "You are assisting with conversational analytics in Odoo. Use prior turns if relevant."
        messages = self._build_chat_history_messages(context_prompt, system_preamble=system_preamble, max_pairs=6)
        insights = self._openai_chat(messages=messages, max_tokens=300)
        # Ensure CRM insights never display 'qty' prefixes
        if is_crm and insights:
            insights = re.sub(r'\bqty\s*(?=(?:[$₹])?\d)', '', insights, flags=re.IGNORECASE)
        # Convert markdown bold (**text**) to HTML bold (<b>text</b>) for HTML rendering
        insights = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', insights)
        # For HTML display, wrap each line in a div for alignment
        insights_lines = [line for line in insights.split('\n') if line.strip()]
        # Remove incomplete sentences from insights
        insights_lines = self._remove_incomplete_sentences(insights_lines)
        formatted_insights = '<br>'.join(
            f'<div style="margin-left: 20px; text-align: left;">{line}</div>'
            for line in insights_lines
        )
        return formatted_insights

    def _openai_chat(self, messages, max_tokens=300, model_candidates=("gpt-4o-mini", "gpt-4o"), timeout=30):
        """Generate chat completion with timeout and fallback models.
        Uses faster model (gpt-4o-mini) first for better performance.
        """
        api_key = self.load_api_key()
        client = OpenAI(api_key=api_key, timeout=timeout)
        last_err = None
        for model_name in model_candidates:
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                last_err = e
                _logger.warning(f"OpenAI call failed for model {model_name}: {e}")
                continue
        raise UserError(f"OpenAI error: {getattr(last_err, 'message', None) or str(last_err) or 'Request failed'}")

    def get_cached_insights(self, chart_title, chart_data, date_range, crm_context=False):
        """Cache AI insights to avoid repeated API calls.
        Falls back to heuristic insights if AI is unavailable or errors occur.
        """
        import json
        import hashlib

        # Ensure minimal structure
        safe_description = (chart_data or {}).get('description') or ''
        safe_labels = (chart_data or {}).get('labels') or []
        safe_values = (chart_data or {}).get('values') or []

        # Create unique cache key
        key_basis = {
            'title': chart_title,
            'desc': safe_description,
            'labels': safe_labels[:12],
            'values': safe_values[:12],
            'range': date_range,
            'crm': crm_context,
        }
        cache_key = f"insights_{hashlib.md5(json.dumps(key_basis, sort_keys=True, default=str).encode()).hexdigest()[:16]}"

        # Check if already cached
        cached = self.env['ir.config_parameter'].sudo().get_param(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        def build_heuristic_insights() -> str:
            # Simple non-AI fallback based on top/bottom values
            pairs = list(zip(safe_labels, safe_values))
            pairs = [(str(l), float(v) if self._is_number(v) else 0.0) for l, v in pairs if l is not None]
            top = sorted(pairs, key=lambda x: x[1], reverse=True)[:5]
            bottom = sorted(pairs, key=lambda x: x[1])[:5]
            def bullets(items):
                return "".join(f"<div style=\"margin-bottom: 8px; line-height: 1.4;\"><b>{l}</b>: {v}</div>" for l, v in items)
            html = ""
            if top:
                html += '<div style="margin-bottom: 20px;"><h4 style="color: #2c3e50; margin-bottom: 10px; font-size: 16px; font-weight: 600;">📊 Key Insights</h4>'
                html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff;">'
                html += bullets(top)
                html += '</div></div>'
            if top:
                html += '<div style="margin-bottom: 20px;"><h4 style="color: #27ae60; margin-bottom: 10px; font-size: 16px; font-weight: 600;">✅ Strengths & Opportunities</h4>'
                html += '<div style="background: #f0f9f0; padding: 15px; border-radius: 6px; border-left: 4px solid #27ae60;">'
                html += bullets(top[:3])
                html += '</div></div>'
            if bottom:
                html += '<div style="margin-bottom: 20px;"><h4 style="color: #e74c3c; margin-bottom: 10px; font-size: 16px; font-weight: 600;">⚠️ Areas for Improvement</h4>'
                html += '<div style="background: #fdf2f2; padding: 15px; border-radius: 6px; border-left: 4px solid #e74c3c;">'
                html += bullets(bottom[:3])
                html += '</div></div>'
            if not html:
                # No data – provide a helpful message to keep the section visible
                html += '<div style="margin-bottom: 20px;"><h4 style="color: #2c3e50; margin-bottom: 10px; font-size: 16px; font-weight: 600;">📊 Key Insights</h4>'
                html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff;">'
                html += '<div style="margin-bottom: 8px; line-height: 1.4;">No data available for the selected period. Try expanding the date range.</div>'
                html += '</div></div>'
            return html

        try:
            # Generate new insights via AI
            insights = self._build_chart_insight(
                chart_title,
                safe_description,
                safe_labels,
                safe_values,
                date_range,
                crm_context,
            )
        except Exception as e:
            _logger.warning(f"AI insights failed for '{chart_title}', using heuristic fallback: {e}")
            insights = build_heuristic_insights()

        # If AI returned empty, fallback to heuristic to ensure content
        if not insights or not str(insights).strip():
            insights = build_heuristic_insights()

        # Cache for 24 hours
        try:
            self.env['ir.config_parameter'].sudo().set_param(cache_key, json.dumps(insights))
        except Exception:
            pass
        return insights

    def _remove_incomplete_sentences(self, lines):
        """Remove incomplete sentences from the end of lines list.
        A sentence is considered incomplete if it doesn't end with proper punctuation.
        """
        if not lines:
            return lines
        
        # Valid sentence endings
        valid_endings = ['.', '!', '?', ':', ';']
        
        # Check the last line
        last_line = lines[-1].strip()
        
        # Remove HTML tags for checking
        clean_last = re.sub(r'<[^>]+>', '', last_line)
        clean_last = clean_last.strip()
        
        # Remove leading bullet points or dashes for checking
        clean_last = re.sub(r'^[-•*]\s*', '', clean_last)
        clean_last = clean_last.strip()
        
        # If last line doesn't end with valid punctuation, it's likely incomplete
        if clean_last:
            # Check if it ends with valid punctuation
            ends_properly = any(clean_last.rstrip().endswith(ending) for ending in valid_endings)
            
            # If it doesn't end properly and has content, it's incomplete
            if not ends_properly and len(clean_last) > 0:
                # Additional check: if it's very short (less than 10 chars) or 
                # doesn't have proper ending, remove it
                words = clean_last.split()
                if len(words) > 0:
                    # Remove the last incomplete line
                    return lines[:-1]
        
        return lines

    def _build_chart_insight(self, chart_title, description, series_labels, series_values, date_range_text, crm_context=False):
        """Generate AI insight text for a chart from label/value series.
        Returns HTML-formatted sections with insights, pros, and cons.
        Uses parallel processing to generate all three sections simultaneously for faster response.
        """
        # Get currency symbol for AI prompts
        currency_symbol = self._get_currency_symbol()
        # Ensure labels and values have same length to avoid zip() errors
        if not series_labels or not series_values:
            _logger.warning(f"Empty data for chart {chart_title}")
            # Return a helpful message instead of empty string
            no_data_msg = (
                '<div style="margin-bottom: 20px; padding: 15px; background: #e3f2fd; border-left: 4px solid #2196f3; border-radius: 6px;">'
                '<h4 style="color: #1976d2; margin-bottom: 10px; font-size: 16px; font-weight: 600;">📊 No Data Available</h4>'
                '<div style="color: #1565c0; line-height: 1.6;">'
                f'<p>No data available for <b>{chart_title}</b> in the selected period.</p>'
                '<p>Please try:</p>'
                '<ul style="margin-left: 20px; margin-top: 10px;">'
                '<li>Expanding the date range</li>'
                '<li>Checking if there are any records in the selected period</li>'
                '<li>Verifying the chart configuration</li>'
                '</ul>'
                '</div>'
                '</div>'
            )
            return no_data_msg
        
        # Match lengths - use minimum length to avoid zip errors
        min_len = min(len(series_labels), len(series_values))
        if min_len == 0:
            _logger.warning(f"No valid data pairs for chart {chart_title}")
            # Return a helpful message instead of empty string
            no_data_msg = (
                '<div style="margin-bottom: 20px; padding: 15px; background: #e3f2fd; border-left: 4px solid #2196f3; border-radius: 6px;">'
                '<h4 style="color: #1976d2; margin-bottom: 10px; font-size: 16px; font-weight: 600;">📊 No Data Available</h4>'
                '<div style="color: #1565c0; line-height: 1.6;">'
                f'<p>No valid data pairs found for <b>{chart_title}</b> in the selected period.</p>'
                '<p>Please try expanding the date range or checking your data.</p>'
                '</div>'
                '</div>'
            )
            return no_data_msg
        
        series_labels = list(series_labels)[:min_len]
        series_values = list(series_values)[:min_len]
        
        # Prepare a compact tabular snapshot (top 12 rows)
        preview_rows = list(zip(series_labels, series_values))[:12]
        table_preview = "\n".join(f"- {lbl}: {val}" for lbl, val in preview_rows)

        # Prepare common context
        insights_guidelines = (
            "- Focus on specific highlights: top/bottom performers, trends, outliers, growth/decline.\n"
            "- Write clear, complete sentences. No preamble or summary.\n"
            "- Use **bold** markdown for key metrics and names.\n"
        )
        if crm_context:
            insights_guidelines += f"- If values are currency-like, prefix with {currency_symbol}. Do NOT mention 'qty'.\n"
        else:
            insights_guidelines += f"- If values are currency-like, prefix with {currency_symbol}. If quantities, prefix with qty.\n"

        # Prepare prompts for parallel execution
        insights_prompt = f"""
You are an expert sales analyst. Create 4-8 concise, actionable insights about the chart.
Context:
- Chart: {chart_title}
- Date range: {date_range_text}
- Description: {description}
- Data (label -> value):
{table_preview}

Guidelines:
{insights_guidelines}
"""

        pros_prompt = f"""
You are an expert business analyst. Analyze the POSITIVE aspects and opportunities from this chart data.
Context:
- Chart: {chart_title}
- Date range: {date_range_text}
- Description: {description}
- Data (label -> value):
{table_preview}

Provide 3-5 key positive insights, opportunities, or strengths. Use **bold** for key terms.
Each insight should be a complete sentence.
{(f"- For monetary values, amounts, revenue, sales, or any currency-like values, ALWAYS prefix with {currency_symbol} (currency symbol) instead of $ (e.g., {currency_symbol}1200, not $1200).\n" if not crm_context else f"- For monetary values like expected revenue or deal size, ALWAYS prefix with {currency_symbol} (currency symbol) instead of $ (e.g., {currency_symbol}1200, not $1200).\n")}
"""

        cons_prompt = f"""
You are an expert business analyst. Analyze the NEGATIVE aspects, risks, and areas for improvement from this chart data.
Context:
- Chart: {chart_title}
- Date range: {date_range_text}
- Description: {description}
- Data (label -> value):
{table_preview}

Provide 3-5 key concerns, risks, or areas needing attention. Use **bold** for key terms.
Each insight should be a complete sentence.
{(f"- For monetary values, amounts, revenue, sales, or any currency-like values, ALWAYS prefix with {currency_symbol} (currency symbol) instead of $ (e.g., {currency_symbol}1200, not $1200).\n" if not crm_context else f"- For monetary values like expected revenue or deal size, ALWAYS prefix with {currency_symbol} (currency symbol) instead of $ (e.g., {currency_symbol}1200, not $1200).\n")}
"""

        # Generate all three sections in parallel for faster response
        def generate_insights():
            try:
                md = self._openai_chat(messages=[{"role": "user", "content": insights_prompt}], max_tokens=220)
                if crm_context and md:
                    md = re.sub(r'\bqty\s*(?=(?:[$₹])?\d)', '', md, flags=re.IGNORECASE)
                # Replace $ with company currency symbol for currency values
                currency_symbol = self._get_currency_symbol()
                md = re.sub(r'\$\s*(\d[\d,\.]*)', rf'{currency_symbol}\1', md)
                html = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', md)
                lines = [ln for ln in html.split('\n') if ln.strip()]
                return self._remove_incomplete_sentences(lines)
            except Exception as e:
                _logger.error(f"Error generating insights: {e}")
                return []

        def generate_pros():
            try:
                md = self._openai_chat(messages=[{"role": "user", "content": pros_prompt}], max_tokens=180)
                if crm_context and md:
                    md = re.sub(r'\bqty\s*(?=(?:[$₹])?\d)', '', md, flags=re.IGNORECASE)
                # Replace $ with company currency symbol for currency values
                currency_symbol = self._get_currency_symbol()
                md = re.sub(r'\$\s*(\d[\d,\.]*)', rf'{currency_symbol}\1', md)
                html = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', md)
                lines = [ln for ln in html.split('\n') if ln.strip()]
                return self._remove_incomplete_sentences(lines)
            except Exception as e:
                _logger.error(f"Error generating pros: {e}")
                return []

        def generate_cons():
            try:
                md = self._openai_chat(messages=[{"role": "user", "content": cons_prompt}], max_tokens=180)
                if crm_context and md:
                    md = re.sub(r'\bqty\s*(?=(?:[$₹])?\d)', '', md, flags=re.IGNORECASE)
                # Replace $ with company currency symbol for currency values
                currency_symbol = self._get_currency_symbol()
                md = re.sub(r'\$\s*(\d[\d,\.]*)', rf'{currency_symbol}\1', md)
                html = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', md)
                lines = [ln for ln in html.split('\n') if ln.strip()]
                return self._remove_incomplete_sentences(lines)
            except Exception as e:
                _logger.error(f"Error generating cons: {e}")
                return []

        # Check if API key is available before attempting AI generation
        api_key_available = False
        api_key_error_msg = ""
        try:
            self.load_api_key()
            api_key_available = True
            _logger.info(f"[OK] OpenAI API key loaded successfully for chart {chart_title}")
        except Exception as e:
            api_key_error_msg = str(e)
            _logger.warning(f"[WARN] OpenAI API key not available, will use heuristic insights: {e}")
            api_key_available = False
        
        # Execute all three in parallel with timeout handling
        insights_lines = []
        pros_lines = []
        cons_lines = []
        
        if api_key_available:
            try:
                # Run with a max of 3 parallel tasks as requested (3-3 parallel)
                with ThreadPoolExecutor(max_workers=3) as executor:
                    future_insights = executor.submit(generate_insights)
                    future_pros = executor.submit(generate_pros)
                    future_cons = executor.submit(generate_cons)
                    
                    # Wait for all to complete with timeout (35 seconds per call)
                    from concurrent.futures import TimeoutError as FutureTimeoutError
                    try:
                        insights_lines = future_insights.result(timeout=35)
                        if not insights_lines:
                            _logger.warning(f"Empty insights generated for chart {chart_title}")
                    except FutureTimeoutError:
                        _logger.error(f"Timeout generating insights for chart {chart_title}")
                        insights_lines = []
                    except Exception as e:
                        _logger.error(f"Error getting insights result for chart {chart_title}: {e}", exc_info=True)
                        insights_lines = []
                    
                    try:
                        pros_lines = future_pros.result(timeout=35)
                        if not pros_lines:
                            _logger.warning(f"Empty pros generated for chart {chart_title}")
                    except FutureTimeoutError:
                        _logger.error(f"Timeout generating pros for chart {chart_title}")
                        pros_lines = []
                    except Exception as e:
                        _logger.error(f"Error getting pros result for chart {chart_title}: {e}", exc_info=True)
                        pros_lines = []
                    
                    try:
                        cons_lines = future_cons.result(timeout=35)
                        if not cons_lines:
                            _logger.warning(f"Empty cons generated for chart {chart_title}")
                    except FutureTimeoutError:
                        _logger.error(f"Timeout generating cons for chart {chart_title}")
                        cons_lines = []
                    except Exception as e:
                        _logger.error(f"Error getting cons result for chart {chart_title}: {e}", exc_info=True)
                        cons_lines = []
            except Exception as e:
                _logger.error(f"Error in parallel execution for chart {chart_title}: {e}", exc_info=True)
                # Fallback: try to get at least insights sequentially
                try:
                    insights_lines = generate_insights()
                    if not insights_lines:
                        _logger.warning(f"Fallback insights also empty for chart {chart_title}")
                except Exception as fallback_err:
                    _logger.error(f"Fallback insights generation failed for chart {chart_title}: {fallback_err}", exc_info=True)
                    insights_lines = []
        
        # If API key not available or all sections empty, generate heuristic insights
        if not api_key_available or (not insights_lines and not pros_lines and not cons_lines):
            _logger.info(f"Generating heuristic insights for {chart_title} (API available: {api_key_available})")
            # Generate simple data-driven insights with currency symbol
            currency_symbol = self._get_currency_symbol()
            pairs = list(zip(series_labels, series_values))
            pairs = [(str(l), float(v) if self._is_number(v) else 0.0) for l, v in pairs if l is not None]
            top = sorted(pairs, key=lambda x: x[1], reverse=True)[:5]
            bottom = sorted(pairs, key=lambda x: x[1])[:3]
            
            if top:
                insights_lines = [f"- <b>{l}</b>: {currency_symbol}{v:,.2f}" for l, v in top[:3]]
            if top:
                pros_lines = [f"- <b>{l}</b> shows strong performance with {currency_symbol}{v:,.2f}" for l, v in top[:2]]
            if bottom and bottom[0][1] > 0:
                cons_lines = [f"- <b>{l}</b> needs attention with {currency_symbol}{v:,.2f}" for l, v in bottom[:2]]
            
            # If still no data, add API key configuration message
            if not insights_lines and not pros_lines and not cons_lines:
                if not api_key_available:
                    insights_lines = [
                        f"- [!] <b>OpenAI API Key Not Configured</b>",
                        f"- Please configure your API key in System Parameters",
                        f"- Go to: Settings > Technical > Parameters > System Parameters",
                        f"- Add key: <b>dashboat.openai_api_key</b> with your OpenAI API key",
                    ]
                else:
                    insights_lines = [
                        f"- No data available for analysis in the selected period",
                        f"- Try expanding the date range or checking your data",
                    ]

        # Combine all sections
        result_html = ""
        
        # Main Insights Section
        if insights_lines:
            result_html += '<div style="margin-bottom: 20px;">'
            result_html += '<h4 style="color: #2c3e50; margin-bottom: 10px; font-size: 16px; font-weight: 600;">📊 Key Insights</h4>'
            result_html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff;">'
            for line in insights_lines:
                result_html += f'<div style="margin-bottom: 8px; line-height: 1.4;">{line}</div>'
            result_html += '</div></div>'

        # Pros Section
        if pros_lines:
            result_html += '<div style="margin-bottom: 20px;">'
            result_html += '<h4 style="color: #27ae60; margin-bottom: 10px; font-size: 16px; font-weight: 600;">✅ Strengths & Opportunities</h4>'
            result_html += '<div style="background: #f0f9f0; padding: 15px; border-radius: 6px; border-left: 4px solid #27ae60;">'
            for line in pros_lines:
                result_html += f'<div style="margin-bottom: 8px; line-height: 1.4;">{line}</div>'
            result_html += '</div></div>'

        # Cons Section
        if cons_lines:
            result_html += '<div style="margin-bottom: 20px;">'
            result_html += '<h4 style="color: #e74c3c; margin-bottom: 10px; font-size: 16px; font-weight: 600;">⚠️ Areas for Improvement</h4>'
            result_html += '<div style="background: #fdf2f2; padding: 15px; border-radius: 6px; border-left: 4px solid #e74c3c;">'
            for line in cons_lines:
                result_html += f'<div style="margin-bottom: 8px; line-height: 1.4;">{line}</div>'
            result_html += '</div></div>'

        # Final post-processing: Replace any remaining $ signs with company currency symbol in currency contexts
        # This catches any $ that might have slipped through
        currency_symbol = self._get_currency_symbol()
        result_html = re.sub(r'\$\s*(\d[\d,\.]*)', rf'{currency_symbol}\1', result_html)

        # If all sections are empty, return helpful message
        if not result_html:
            error_msg = (
                '<div style="margin-bottom: 20px; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 6px;">'
                '<h4 style="color: #856404; margin-bottom: 10px; font-size: 16px; font-weight: 600;">⚠️ Unable to Generate Insights</h4>'
                '<div style="color: #856404; line-height: 1.6;">'
                '<p>Unable to generate AI insights. Possible reasons:</p>'
                '<ul style="margin-left: 20px; margin-top: 10px;">'
                '<li>OpenAI API key is missing or invalid. Please configure your API key in settings.</li>'
                '<li>Network connection issues. Please check your internet connection.</li>'
                '<li>API service temporarily unavailable. Please try again later.</li>'
                '</ul>'
                '<p style="margin-top: 10px;"><b>Note:</b> Please ensure your OpenAI API key is properly configured in the system settings.</p>'
                '</div>'
                '</div>'
            )
            return error_msg

        return result_html

    def generate_insights_parallel(self, series_data, date_range, crm_context=False):
        """Generate insights for multiple charts in parallel"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def process_chart(chart_data):
            try:
                return self.get_cached_insights(
                    chart_data['title'], 
                    chart_data, 
                    date_range, 
                    crm_context
                )
            except Exception as e:
                _logger.error(f"Error generating insights for {chart_data['title']}: {e}")
                return ""
        
        # Process all charts in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_chart = {executor.submit(process_chart, chart): chart for chart in series_data}
            
            results = {}
            for future in as_completed(future_to_chart):
                chart = future_to_chart[future]
                try:
                    results[chart['title']] = future.result()
                except Exception as e:
                    _logger.error(f"Error processing {chart['title']}: {e}")
                    results[chart['title']] = ""
        
        return results

    @api.model
    def get_chart_insight(self, chart_key, date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """Compute the dataset for the requested chart, then ask OpenAI for insights.
        Returns HTML string.
        """
        if not chart_key:
            raise UserError("Missing chart key")

        # Resolve date range text and compute data via existing helpers
        # We'll compute both dashboards' data and then pick the relevant metric.
        sales_data = self.get_dashboard_data(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
        crm_data = self.get_crm_dashboard_data(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
        date_range_text = sales_data.get('date_range') or crm_data.get('date_range') or ''

        # Map chart_key -> extraction callable that returns (title, description, labels, values)
        def extract_plotly_series_from_html(html_snippet):
            """Best-effort: try to parse labels/values from simple Plotly HTML fallbacks.
            If not possible, return empty.
            """
            return [], []

        title, description, labels, values = None, None, [], []
        is_crm_chart = False

        # Sales charts
        if chart_key == 'sales_performance_chart':
            # We can reconstruct from the source computation by re- running the same logic here
            # However, we only have the rendered HTML in sales_data. So extract not trivial.
            # Provide a coarse insight based on monthly buckets by re-deriving like in get_dashboard_data
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            current_date = date_from_resolved
            month_labels = []
            month_values = []
            while current_date <= date_to_resolved:
                month_start = current_date.replace(day=1)
                next_month = month_start.replace(day=28) + timedelta(days=4)
                month_end = next_month - timedelta(days=next_month.day)
                if month_end > date_to_resolved:
                    month_end = date_to_resolved
                orders = self.env['sale.order'].search([
                    ('state', 'in', ['sale','done']),
                    ('date_order', '>=', month_start),
                    ('date_order', '<=', month_end),
                ])
                month_labels.append(month_start.strftime('%b %Y'))
                month_values.append(sum(orders.mapped('amount_total')))
                current_date = month_end + timedelta(days=1)
            title = 'Sales Performance by Month'
            description = 'Monthly sales totals (amount_total) for confirmed/done orders.'
            labels, values = month_labels, month_values

        elif chart_key == 'sales_by_product_chart':
            lines = self.env['sale.order.line'].search([
                ('order_id.state','in',['sale','done']),
                ('order_id.date_order','>=', (date_from or self._get_date_range(date_filter, year_filter, date_from, date_to)[0])),
                ('order_id.date_order','<=', (date_to or self._get_date_range(date_filter, year_filter, date_from, date_to)[1])),
            ])
            prod_to_qty = {}
            for ln in lines:
                name = ln.product_id.name or 'Unknown'
                prod_to_qty[name] = prod_to_qty.get(name, 0.0) + float(ln.product_uom_qty or 0.0)
            top = sorted(prod_to_qty.items(), key=lambda kv: kv[1], reverse=True)[:10]
            title = 'Top Products by Quantity'
            description = 'Sum of sold quantities within the selected period.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'sales_by_region_chart':
            orders = self.env['sale.order'].search([
                ('state','in',['sale','done']),
                ('date_order','>=', (date_from or self._get_date_range(date_filter, year_filter, date_from, date_to)[0])),
                ('date_order','<=', (date_to or self._get_date_range(date_filter, year_filter, date_from, date_to)[1])),
                ('partner_id.country_id','!=', False)
            ])
            region_to_amt = {}
            for so in orders:
                cname = so.partner_id.country_id.name or 'Unknown'
                region_to_amt[cname] = region_to_amt.get(cname, 0.0) + float(so.amount_total or 0.0)
            top = sorted(region_to_amt.items(), key=lambda kv: kv[1], reverse=True)[:12]
            title = 'Sales by Region'
            description = 'Total sales amount grouped by customer country.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'top_customers_chart':
            orders = self.env['sale.order'].search([
                ('state','in',['sale','done']),
                ('date_order','>=', (date_from or self._get_date_range(date_filter, year_filter, date_from, date_to)[0])),
                ('date_order','<=', (date_to or self._get_date_range(date_filter, year_filter, date_from, date_to)[1])),
            ])
            cust_to_amt = {}
            for so in orders:
                cname = (so.partner_id and so.partner_id.name) or 'Unknown'
                cust_to_amt[cname] = cust_to_amt.get(cname, 0.0) + float(so.amount_total or 0.0)
            top = sorted(cust_to_amt.items(), key=lambda kv: kv[1], reverse=True)[:10]
            title = 'Top Customers by Sales'
            description = 'Total sales amount per customer.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'top_salespersons_chart':
            orders = self.env['sale.order'].search([
                ('state','in',['sale','done']),
                ('date_order','>=', (date_from or self._get_date_range(date_filter, year_filter, date_from, date_to)[0])),
                ('date_order','<=', (date_to or self._get_date_range(date_filter, year_filter, date_from, date_to)[1])),
            ])
            sp_to_amt = {}
            for so in orders:
                sname = (so.user_id and so.user_id.name) or 'Unassigned'
                sp_to_amt[sname] = sp_to_amt.get(sname, 0.0) + float(so.amount_total or 0.0)
            top = sorted(sp_to_amt.items(), key=lambda kv: kv[1], reverse=True)[:10]
            title = 'Top Salespersons by Sales'
            description = 'Total sales amount per salesperson.'
            labels, values = zip(*top) if top else ([], [])

        # CRM charts
        elif chart_key == 'pipeline_funnel_chart':
            is_crm_chart = True
            Stage = self.env['crm.stage']
            Lead = self.env['crm.lead']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            opportunities = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
                ('type', '=', 'opportunity')
            ])
            counts = {}
            for opp in opportunities:
                sname = opp.stage_id.name or 'Undefined'
                counts[sname] = counts.get(sname, 0) + 1
            # Sort by stage sequence
            stage_records = Stage.search([], order='sequence asc')
            ordered = [(rec.name or 'Undefined', counts.get(rec.name or 'Undefined', 0)) for rec in stage_records if (rec.name or 'Undefined') in counts]
            if not ordered:
                ordered = list(counts.items())
            title = 'Pipeline Funnel (Count)'
            description = 'Opportunity count per stage.'
            labels, values = zip(*ordered) if ordered else ([], [])

        elif chart_key in ('avg_deal_size_trend_chart', 'won_revenue_trend_chart'):
            is_crm_chart = True
            # Recreate monthly series similar to get_crm_dashboard_data
            Lead = self.env['crm.lead']
            Stage = self.env['crm.stage']
            won_stage_ids = Stage.search([('is_won','=',True)]).ids
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            opportunities = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
                ('type', '=', 'opportunity')
            ])
            month_cursor = date_from_resolved.replace(day=1)
            month_labels, avg_deal_values, won_rev_values = [], [], []
            while month_cursor <= date_to_resolved:
                next_month = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
                month_end = next_month - timedelta(days=1)
                month_labels.append(month_cursor.strftime('%b %Y'))
                month_opps = opportunities.filtered(lambda l: l.create_date.date() >= month_cursor and l.create_date.date() <= month_end)
                avg_deal = 0.0 if not month_opps else float(sum(o.expected_revenue or 0.0 for o in month_opps)) / len(month_opps)
                avg_deal_values.append(avg_deal)
                month_won = month_opps.filtered(lambda l: l.stage_id and l.stage_id.id in won_stage_ids)
                won_rev_values.append(sum(float(o.expected_revenue or 0.0) for o in month_won))
                month_cursor = next_month
            if chart_key == 'avg_deal_size_trend_chart':
                title = 'Average Deal Size Trend'
                description = 'Average expected revenue per opportunity by month.'
                labels, values = month_labels, avg_deal_values
            else:
                title = 'Won Revenue Trend'
                description = 'Sum of expected revenue of won opportunities by month.'
                labels, values = month_labels, won_rev_values

        elif chart_key == 'stage_distribution_chart':
            is_crm_chart = True
            # Use the stacked per-month counts; we will summarize total per stage across range
            Lead = self.env['crm.lead']
            Stage = self.env['crm.stage']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            opportunities = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
                ('type', '=', 'opportunity')
            ])
            counts = {}
            for opp in opportunities:
                sname = opp.stage_id.name or 'Undefined'
                counts[sname] = counts.get(sname, 0) + 1
            top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
            title = 'Stage Distribution'
            description = 'Total opportunities per stage within the selected period.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'lead_source_chart':
            is_crm_chart = True
            Lead = self.env['crm.lead']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            records = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
            ])
            src_counts = {}
            for l in records:
                src = (getattr(l, 'source_id', False) and l.source_id.name) or (getattr(l, 'medium_id', False) and l.medium_id.name) or 'Unknown'
                src_counts[src] = src_counts.get(src, 0) + 1
            top = sorted(src_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
            title = 'Lead Source Effectiveness'
            description = 'Counts by lead/opportunity source.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'revenue_forecast_chart':
            is_crm_chart = True
            Lead = self.env['crm.lead']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            records = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
                ('probability', '>', 0),
                ('expected_revenue', '>', 0)
            ])
            month_to_weighted = {}
            for opp in records:
                m = (fields.Datetime.from_string(opp.create_date).date() if opp.create_date else fields.Date.today()).strftime('%Y-%m')
                month_to_weighted[m] = month_to_weighted.get(m, 0.0) + float(opp.expected_revenue or 0.0) * (float(opp.probability or 0.0)/100.0)
            ordered = sorted(month_to_weighted.items())
            title = 'Weighted Revenue Forecast'
            description = 'Sum of expected_revenue × probability by month.'
            labels, values = zip(*ordered) if ordered else ([], [])

        elif chart_key == 'geo_insights_chart':
            is_crm_chart = True
            Lead = self.env['crm.lead']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            records = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
            ])
            country_counts = {}
            for rec in records:
                country = (rec.country_id and rec.country_id.name) or (rec.partner_id and rec.partner_id.country_id and rec.partner_id.country_id.name) or 'Unknown'
                country_counts[country] = country_counts.get(country, 0) + 1
            top = sorted(country_counts.items(), key=lambda kv: kv[1], reverse=True)[:12]
            title = 'Geographical Insights'
            description = 'Lead/Opportunity counts by country.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'activities_heatmap':
            is_crm_chart = True
            Activity = self.env['mail.activity']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            acts = Activity.search([
                ('res_model', '=', 'crm.lead'),
                ('date_deadline', '>=', date_from_resolved),
                ('date_deadline', '<=', date_to_resolved),
            ])
            # Summarize as two totals: due vs overdue
            today = fields.Date.today()
            due = sum(1 for a in acts if a.date_deadline and a.date_deadline >= today)
            overdue = sum(1 for a in acts if a.date_deadline and a.date_deadline < today)
            title = 'Activities Due/Overdue'
            description = 'Count of activities due vs overdue across the range.'
            labels, values = ['Due', 'Overdue'], [due, overdue]

        elif chart_key == 'sales_perf_chart':
            is_crm_chart = True
            # Sales Performance by Salesperson (from CRM dashboard)
            Lead = self.env['crm.lead']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            opportunities = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
                ('type', '=', 'opportunity')
            ])
            sp_amounts = {}
            for opp in opportunities:
                sp_name = opp.user_id.name or 'Unassigned'
                sp_amounts[sp_name] = sp_amounts.get(sp_name, 0.0) + float(opp.expected_revenue or 0.0)
            top = sorted(sp_amounts.items(), key=lambda kv: kv[1], reverse=True)[:10]
            title = 'Sales Performance by Salesperson'
            description = 'Expected revenue per salesperson from opportunities.'
            labels, values = zip(*top) if top else ([], [])

        elif chart_key == 'lost_reason_chart':
            is_crm_chart = True
            # Lost Reason Analysis
            Lead = self.env['crm.lead']
            date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
            lost_leads = Lead.search([
                ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
                ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
                ('lost_reason_id', '!=', False)
            ])
            reason_counts = {}
            for lead in lost_leads:
                rname = lead.lost_reason_id.name or 'Unknown'
                reason_counts[rname] = reason_counts.get(rname, 0) + 1
            top = sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
            title = 'Lost Reason Analysis'
            description = 'Count of lost opportunities by reason.'
            labels, values = zip(*top) if top else ([], [])

        else:
            _logger.warning(f"Unknown chart key: {chart_key}")
            # Return helpful message for unknown chart
            unknown_chart_msg = (
                '<div style="margin-bottom: 20px; padding: 15px; background: #fff3cd; border-left: 4px solid #ffc107; border-radius: 6px;">'
                '<h4 style="color: #856404; margin-bottom: 10px; font-size: 16px; font-weight: 600;">⚠️ Chart Not Found</h4>'
                '<div style="color: #856404; line-height: 1.6;">'
                f'<p>Chart key <b>{chart_key}</b> is not recognized.</p>'
                '<p>Please check the chart configuration or contact support.</p>'
                '</div>'
                '</div>'
            )
            return unknown_chart_msg

        labels = list(labels) if labels else []
        values = list(values) if values else []
        
        # Wrap in try-except to handle any errors during insight generation
        try:
            return self._build_chart_insight(title or chart_key, description or '', labels, values, date_range_text, crm_context=is_crm_chart)
        except Exception as e:
            _logger.error(f"Error generating insights for chart {chart_key}: {str(e)}", exc_info=True)
            error_msg = (
                '<div style="margin-bottom: 20px; padding: 15px; background: #f8d7da; border-left: 4px solid #dc3545; border-radius: 6px;">'
                '<h4 style="color: #721c24; margin-bottom: 10px; font-size: 16px; font-weight: 600;">❌ Error Generating Insights</h4>'
                '<div style="color: #721c24; line-height: 1.6;">'
                f'<p>An error occurred while generating insights for <b>{title or chart_key}</b>.</p>'
                '<p>Please try again or contact support if the issue persists.</p>'
                '</div>'
                '</div>'
            )
            return error_msg

    def is_sales_related_query(self, user_input):
        if not isinstance(user_input, str):
            user_input = str(user_input)
        
        user_input_lower = user_input.lower().strip()
        
        sales_keywords = [
            'sale', 'sales', 'customer', 'salesperson', 'product', 'revenue', 'income', 'profit', 'margin',
            'order', 'billing', 'payment', 'transaction', 'inventory', 'stock', 'quantity',
            'demand', 'forecast', 'prediction', 'price', 'amount', 'subtotal', 'tax',
            'total', 'status', 'month', 'year', 'date', 'period', 'quarter', 'annual',
            'monthly', 'yearly', 'quarterly', 'trend', 'analysis', 'report', 'dashboard',
            'performance', 'top', 'bottom', 'best', 'worst', 'highest', 'lowest', 'average',
            'sum', 'count', 'total_amount', 'quantity', 'product_name', 'customer_name',
            'salesperson_name', 'product_category'
        ]
        
        excluded_keywords = ['purchase', 'invoice', 'vendor', 'expense', 'employee', 'cost']
        if any(kw in user_input_lower for kw in excluded_keywords):
            return False
        
        for keyword in sales_keywords:
            if keyword in user_input_lower:
                return True
        
        sales_patterns = [
            r'\b(how much|what is|show me|get|find|list|display|show)\b.*\b(sale|sales|revenue|income|profit|order|product|customer|salesperson|quantity|demand|forecast|prediction)\b',
            r'\b(sale|sales|revenue|income|profit|order|product|customer|salesperson|quantity|demand|forecast|prediction)\b.*\b(by|for|in|of|to|from|with|without)\b',
            r'\b(top|bottom|best|worst|highest|lowest|average|total|sum|count)\b.*\b(sale|sales|revenue|income|profit|order|product|customer|salesperson|quantity)\b',
            r'\b(sale|sales|revenue|income|profit|order|product|customer|salesperson|quantity)\b.*\b(top|bottom|best|worst|highest|lowest|average|total|sum|count)\b'
        ]
        
        for pattern in sales_patterns:
            if re.search(pattern, user_input_lower):
                return True
        
        return False

    def is_crm_related_query(self, user_input):
        if not isinstance(user_input, str):
            user_input = str(user_input)
        txt = user_input.lower().strip()
        crm_keywords = [
            'crm', 'lead', 'leads', 'opportunity', 'opportunities', 'pipeline', 'stage', 'stages',
            'won', 'lost', 'lost reason', 'activity', 'activities', 'meeting', 'call', 'task',
            'expected revenue', 'probability', 'source', 'utm', 'medium', 'team', 'sales team',
            'kanban', 'follow up'
        ]
        if any(k in txt for k in crm_keywords):
            return True
        patterns = [
            r'\b(opportunities?|leads?)\b.*\b(stage|won|lost|source|team)\b',
            r'\b(stage|pipeline|won|lost)\b.*\b(opportunities?|leads?)\b',
            r'\baverage deal size|expected revenue|probability\b',
        ]
        for p in patterns:
            if re.search(p, txt):
                return True
        return False
    def generate_charts(self, df, user_input):
        """Generate chart images from the dataframe in a deterministic, thread-safe way.
        Previously this used ThreadPoolExecutor, but matplotlib is not thread-safe which caused
        sporadic missing/replaced charts inside the exported PDF. We now render sequentially.
        """
        if df.empty:
            return []

        numeric_cols = df.select_dtypes(include=[float, int]).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=[float, int]).columns.tolist()

        chart_combinations = []
        for x_col in categorical_cols:
            for y_col in numeric_cols:
                if x_col != y_col:
                    chart_combinations.append((x_col, y_col))
        if not chart_combinations:
            return []

        chart_buffers = []

        for x_col, y_col in chart_combinations:
            plot_df = df[[x_col, y_col]].dropna()
            if plot_df.empty:
                continue
            with self._matplotlib_lock:
                fig = plt.figure(figsize=(10, 6), facecolor='white')
                ax = fig.add_subplot(111)
                ax.set_facecolor('white')
                try:
                    sns.barplot(data=plot_df, x=x_col, y=y_col, palette="Set2", ax=ax)
                    plt.title(f"{x_col} vs {y_col}", fontsize=14, color='black')
                    plt.xlabel(x_col, fontsize=12, color='black')
                    plt.ylabel(y_col, fontsize=12, color='black')
                    plt.xticks(rotation=45, ha='right', color='black')
                    plt.yticks(color='black')
                    plt.grid(True, linestyle='--', alpha=0.7, color='gray')
                    plt.tight_layout()
                    buf = BytesIO()
                    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
                    buf.seek(0)
                    chart_buffers.append((f"{x_col} vs {y_col}", buf))
                except Exception:
                    _logger.exception("Failed to render chart %s vs %s", x_col, y_col)
                finally:
                    plt.close(fig)
                    plt.clf()

        return chart_buffers

    # def generate_charts(self, df, user_input):
    #     if df.empty:
    #         _logger.debug("Empty DataFrame, no charts generated")
    #         return []

    #     if 'month' in df.columns and df['month'].dtype in [np.int64, np.int32]:
    #         df['month'] = df['month'].astype(str)
    #     if 'year' in df.columns and df['year'].dtype in [np.int64, np.int32]:
    #         df['year'] = df['year'].astype(str)
    #         df = df[df['year'].notnull() & (df['year'].str.strip() != '')]
    #         df['year'] = pd.Categorical(df['year'], categories=sorted(df['year'].unique()), ordered=True)

    #     numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    #     categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    #     date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()

    #     sales_numeric_cols = ['total_amount_usd', 'quantity', 'price_unit', 'subtotal', 'amount', 'tax', 'total_amount']
    #     sales_categorical_cols = ['customer_name', 'salesperson_name', 'product_name', 'product_type', 'product_category', 'status']

    #     prioritized_numeric_cols = [col for col in sales_numeric_cols if col in numeric_cols and col not in ['month', 'year']]
    #     prioritized_categorical_cols = [col for col in sales_categorical_cols if col in categorical_cols]

    #     x_axis_candidates = prioritized_categorical_cols + date_cols
    #     if 'month' in df.columns:
    #         x_axis_candidates.append('month')
    #     if 'year' in df.columns:
    #         x_axis_candidates.append('year')

    #     if not x_axis_candidates:
    #         if 'customer_name' in df.columns:
    #             x_axis_candidates = ['customer_name']
    #         elif 'salesperson_name' in df.columns:
    #             x_axis_candidates = ['salesperson_name']
    #         elif 'product_category' in df.columns:
    #             x_axis_candidates = ['product_category']
    #         elif 'product_name' in df.columns:
    #             x_axis_candidates = ['product_name']
    #         elif df.columns[0] in numeric_cols and df.columns[0] not in ['month', 'year']:
    #             x_axis_candidates = [df.columns[0]]
    #             if df.columns[0] in prioritized_numeric_cols:
    #                 prioritized_numeric_cols.remove(df.columns[0])

    #     if not prioritized_numeric_cols or not x_axis_candidates:
    #         return []

    #     chart_combinations = []
    #     seen_pairs = set()
    #     for x_col in x_axis_candidates:
    #         for y_col in prioritized_numeric_cols:
    #             if x_col != y_col and (x_col, y_col) not in seen_pairs:
    #                 chart_combinations.append((x_col, y_col))
    #                 seen_pairs.add((x_col, y_col))

    #     if not chart_combinations:
    #         _logger.debug("No valid chart combinations generated")
    #         return []

    #     chart_buffers = []
    #     sns.set_style("whitegrid")
    #     plt.style.use('default')

    #     for x_col, y_col in chart_combinations:
    #         try:
    #             plot_df = df[[x_col, y_col]].dropna()
    #             if plot_df.empty:
    #                 _logger.debug(f"Skipping chart for {x_col} vs {y_col}: No valid data after dropping NA")
    #                 continue

    #             fig = plt.figure(figsize=(10, 6), facecolor='white')
    #             ax = fig.add_subplot(111)
    #             ax.set_facecolor('white')

    #             if x_col in date_cols:
    #                 sns.lineplot(data=plot_df, x=x_col, y=y_col, palette="Set2", linewidth=2.5, ax=ax)
    #             elif x_col in ['month', 'year']:
    #                 sns.barplot(data=plot_df, x=x_col, y=y_col, palette="Set2", ax=ax, order=sorted(plot_df[x_col].unique()))
    #             else:
    #                 sns.barplot(data=plot_df, x=x_col, y=y_col, palette="Set2", ax=ax)

    #             plt.title(f"{x_col} vs {y_col}", fontsize=14, color='black')
    #             plt.xlabel(x_col, fontsize=12, color='black')
    #             plt.ylabel(y_col, fontsize=12, color='black')
    #             plt.xticks(rotation=45, ha='right', color='black')
    #             plt.yticks(color='black')
    #             plt.grid(True, linestyle='--', alpha=0.7, color='gray')
    #             plt.tight_layout()

    #             buf = BytesIO()
    #             plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
    #             buf.seek(0)
    #             chart_buffers.append((f"{x_col} vs {y_col}", buf))
    #             plt.close(fig)
    #         except Exception as e:
    #             _logger.error(f"Error generating chart for {x_col} vs {y_col}: {str(e)}")
    #             plt.close('all')

    #     return chart_buffers

    def split_combined_query(self, user_input):
        if not isinstance(user_input, str):
            user_input = str(user_input)
        user_input_lower = user_input.lower().strip()
        queries = []

        # Extract full or partial years
        year_match = re.search(r'\b(20\d{2}|\d{2})\b', user_input_lower)
        default_year = None
        if year_match:
            year_str = year_match.group(0)
            default_year = f"20{year_str}" if len(year_str) == 2 and 22 <= int(year_str) <= 50 else year_str
            if default_year and not (2022 <= int(default_year) <= 2050):
                default_year = None

        if " and " in user_input_lower:
            parts = user_input_lower.split(" and ")
            for i, part in enumerate(parts):
                part = part.strip()
                part_year_match = re.search(r'\b(20\d{2}|\d{2})\b', part)
                part_year = None
                if part_year_match:
                    year_str = part_year_match.group(0)
                    part_year = f"20{year_str}" if len(year_str) == 2 and 22 <= int(year_str) <= 50 else year_str
                    if part_year and not (2022 <= int(part_year) <= 2050):
                        part_year = None
                if any(kw in part for kw in ["top", "bottom", "customer", "salesperson", "product", "sale", "sales", "quantity", "revenue", "profit", "product_category", "status"]):
                    if not part_year and default_year and i > 0:
                        part = f"{default_year} {part}"
                    queries.append(part)
        else:
            queries.append(user_input_lower)

        queries = [q for q in queries if q and any(kw in q for kw in ["top", "bottom", "customer", "salesperson", "product", "sale", "sales", "quantity", "revenue", "profit", "product_category", "status"])]
        return queries if queries else [user_input_lower]

    def _get_currency_symbol(self):
        """Get the currency symbol from company's currency"""
        try:
            currency = self.env.company.currency_id
            return currency.symbol or '₹'  # Fallback to ₹ if no currency found
        except:
            return '₹'  # Fallback to ₹ if error
    
    def _format_currency(self, amount, decimal_places=2):
        """Format amount with company currency symbol"""
        try:
            from odoo.tools.misc import format_amount
            currency = self.env.company.currency_id
            return format_amount(self.env, amount, currency)
        except:
            # Fallback formatting
            currency_symbol = self._get_currency_symbol()
            return f"{currency_symbol}{amount:,.{decimal_places}f}"

    def _update_pdf_metadata(self, pdf_buffer, report_title):
        """Update PDF metadata (Creator, Author, Title, Subject) to replace 'anonymous'"""
        try:
            from PyPDF2 import PdfReader, PdfWriter
            pdf_buffer.seek(0)
            reader = PdfReader(pdf_buffer)
            writer = PdfWriter()
            
            # Copy all pages
            for page in reader.pages:
                writer.add_page(page)
            
            # Update metadata
            writer.add_metadata({
                '/Title': report_title,
                '/Author': report_title,
                '/Subject': report_title,
                '/Creator': report_title,
                '/Producer': report_title,
            })
            
            # Write to new buffer
            new_buffer = BytesIO()
            writer.write(new_buffer)
            new_buffer.seek(0)
            return new_buffer
        except Exception as e:
            _logger.warning(f"Could not update PDF metadata using PyPDF2: {e}. Using original PDF.")
            pdf_buffer.seek(0)
            return pdf_buffer

    def generate_pdf_report(self, results):
        start_time = time.time()
        buffer = BytesIO()
        # Set report title for metadata
        report_title = "Sales/CRM Analysis Report"
        
        icp = self.env['ir.config_parameter'].sudo()
        company_name = ''
        try:
            custom_name = icp.get_param('dashboat.report_company_name')
            if custom_name:
                company_name = custom_name
            elif self.env.company and self.env.company.name:
                company_name = self.env.company.name
        except Exception as e:
            _logger.warning(f"Using fallback company name due to error: {e}")
        if not company_name:
            company_name = 'Your Company'
        module_url = icp.get_param('dashboat.module_url', 'https://dashboat.sufalamtech.com')
        powered_by_text = "Powered by Sufalam Technologies"

        # Default base font used for footer until font detection runs
        base_font = 'Helvetica'

        def draw_footer(canvas, doc, is_first_page=False):
            try:
                canvas.saveState()
                width, height = doc.pagesize
                y = 40  # distance from bottom
                
                # Draw grey line
                canvas.setStrokeColor(colors.HexColor('#9E9E9E'))
                canvas.setLineWidth(1)
                canvas.line(0, y + 10, width, y + 10)
                
                # Set font and color
                font_name = 'Helvetica-Bold'
                font_size = 9
                canvas.setFont(font_name, font_size)
                canvas.setFillColor(colors.HexColor('#14213D'))
                
                text_y = y - 6
                
                if is_first_page:
                    # Cover page: Company name on left, Powered by Sufalam Technologies on right
                    # Left side - Company name
                    company_display = str(company_name) if company_name else 'Your Company'
                    canvas.drawString(40, text_y, company_display)
                    
                    # Right side - Powered by Sufalam Technologies (static text)
                    # Use simpler approach - draw directly with fixed margin
                    prefix_text = "Powered by "
                    suffix_text = "Sufalam Technologies"
                    powered_text = prefix_text + suffix_text
                    try:
                        text_width = canvas.stringWidth(powered_text, font_name, font_size)
                        prefix_width = canvas.stringWidth(prefix_text, font_name, font_size)
                        suffix_width = canvas.stringWidth(suffix_text, font_name, font_size)
                        # Account for page margins (30px left/right margin from SimpleDocTemplate)
                        # Letter size is 612 points wide, minus margins
                        usable_width = width - 60  # 30px margin on each side
                        right_x = usable_width - text_width + 30  # Start from right margin
                        # Ensure it's within bounds
                        if right_x < width - 500:  # Make sure it's not too far left
                            right_x = width - text_width - 50
                        canvas.drawString(right_x, text_y, prefix_text)
                        suffix_x = right_x + prefix_width
                        # Draw suffix in light purple
                        suffix_color = colors.HexColor('#8a6cf6')
                        canvas.setFillColor(suffix_color)
                        canvas.drawString(suffix_x, text_y, suffix_text)
                        # Restore default fill color
                        canvas.setFillColor(colors.HexColor('#14213D'))
                        _logger.info(f"Footer cover page: width={width}, text_width={text_width}, right_x={right_x}, text='{powered_text}'")
                    except Exception as e:
                        _logger.error(f"Error calculating/drawing powered_by: {e}", exc_info=True)
                        # Fallback: draw at fixed position from right edge
                        canvas.drawString(width - 280, text_y, powered_text)
                else:
                    # Other pages: match cover page footer (company left, powered-by right)
                    company_display = str(company_name) if company_name else 'Your Company'
                    canvas.drawString(40, text_y, company_display)

                    prefix_text = "Powered by "
                    suffix_text = "Sufalam Technologies"
                    powered_text = prefix_text + suffix_text
                    try:
                        text_width = canvas.stringWidth(powered_text, font_name, font_size)
                        prefix_width = canvas.stringWidth(prefix_text, font_name, font_size)
                        suffix_width = canvas.stringWidth(suffix_text, font_name, font_size)
                        usable_width = width - 60  # 30px margin on each side
                        right_x = usable_width - text_width + 30
                        if right_x < width - 500:
                            right_x = width - text_width - 50
                        canvas.drawString(right_x, text_y, prefix_text)
                        suffix_x = right_x + prefix_width
                        # Draw suffix in light purple
                        suffix_color = colors.HexColor('#8a6cf6')
                        canvas.setFillColor(suffix_color)
                        canvas.drawString(suffix_x, text_y, suffix_text)
                        # Restore default fill color
                        canvas.setFillColor(colors.HexColor('#14213D'))
                        canvas.linkURL(
                            "https://apps.odoo.com/apps/modules/18.0/DashBoat",
                            (suffix_x, text_y - 2, suffix_x + suffix_width, text_y + font_size),
                            relative=0,
                        )
                    except Exception as e:
                        _logger.error(f"Error drawing powered_by on later page: {e}", exc_info=True)
                        canvas.drawString(width - 280, text_y, powered_text)
                
                canvas.restoreState()
            except Exception as e:
                _logger.error(f"Error in draw_footer: {e}", exc_info=True)

        def on_first_page(canvas, doc):
            """Set PDF metadata on first page"""
            canvas.setTitle(report_title)
            canvas.setAuthor(report_title)
            canvas.setSubject(report_title)
            # Draw download date on the top-right corner of the cover
            try:
                canvas.saveState()
                width, height = doc.pagesize
                date_text = datetime.now().strftime('%b %d, %Y')
                font_name = 'Helvetica-Bold'
                font_size = 11
                margin = 30
                canvas.setFont(font_name, font_size)
                canvas.setFillColor(colors.HexColor('#14213D'))
                text_width = canvas.stringWidth(date_text, font_name, font_size)
                x = width - margin - text_width
                y = height - 40  # near the top with a small margin
                canvas.drawString(x, y, date_text)
                canvas.restoreState()
            except Exception as e:
                _logger.debug(f"Could not draw cover date: {e}")
            # Draw footer and Set Creator to replace "anonymous" - use PDF metadata dictionary format
            try:
                draw_footer(canvas, doc, is_first_page=True)
                from reportlab.pdfgen.canvas import Canvas
                if hasattr(canvas, '_doc') and hasattr(canvas._doc, 'info'):
                    # Set Creator field in PDF info dictionary
                    canvas._doc.info['/Creator'] = report_title
                    canvas._doc.info['/Producer'] = report_title
            except Exception as e:
                _logger.debug(f"Could not set Creator metadata: {e}")
        
        def on_later_pages(canvas, doc):
            """Set PDF metadata on later pages"""
            canvas.setTitle(report_title)
            canvas.setAuthor(report_title)
            canvas.setSubject(report_title)
            try:
                draw_header(canvas, doc)
            except Exception:
                pass
            # Draw footer and Set Creator to replace "anonymous" - use PDF metadata dictionary format
            try:
                draw_footer(canvas, doc, is_first_page=False)
                if hasattr(canvas, '_doc') and hasattr(canvas._doc, 'info'):
                    # Set Creator field in PDF info dictionary
                    canvas._doc.info['/Creator'] = report_title
                    canvas._doc.info['/Producer'] = report_title
            except Exception as e:
                _logger.debug(f"Could not set Creator metadata: {e}")
        
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=30, bottomMargin=70, leftMargin=30, rightMargin=30, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        # Ensure a Unicode font (supports ₹) is registered and used
        styles = getSampleStyleSheet()
        chosen_font = None
        try:
            font_candidates = [
                ('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                ('NirmalaUI', r'C:\Windows\Fonts\Nirmala.ttf'),
                ('SegoeUI', r'C:\Windows\Fonts\segoeui.ttf'),
                ('ArialUnicodeMS', r'C:\Windows\Fonts\arialuni.ttf'),
            ]
            for name, path in font_candidates:
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    chosen_font = name
                    break
                except Exception:
                    continue
            if chosen_font:
                for sty_name in ['Normal', 'BodyText']:
                    if sty_name in styles:
                        styles[sty_name].fontName = chosen_font
                # Use chosen font as base_font for footer and headings
                base_font = chosen_font
        except Exception:
            pass
        # Create custom styles with Unicode font support for rupee symbol (₹)
        base_font = chosen_font if chosen_font else 'Helvetica'
        styles.add(ParagraphStyle(name='CoverTitle', fontSize=48, alignment=0, spaceAfter=8, leading=52, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='CoverSubTitle', fontSize=14, alignment=0, textColor=colors.HexColor('#6B7280'), spaceAfter=6, fontName=base_font))
        styles.add(ParagraphStyle(name='CoverDate', fontSize=10, alignment=0, textColor=colors.HexColor('#9AA0A6'), spaceAfter=8, fontName=base_font))
        styles.add(ParagraphStyle(name='ReportTitle', fontSize=18, alignment=1, spaceAfter=20, fontName=base_font))
        styles.add(ParagraphStyle(name='SectionHeader', fontSize=18, spaceBefore=15, spaceAfter=10, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='Footer', fontSize=8, alignment=1, fontName=base_font))
        styles.add(ParagraphStyle(name='CoverFooter', fontSize=10, alignment=0, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='TableText', fontSize=8, leading=10, wordWrap='CJK', fontName=base_font))

        elements = []
        # Cover page (first page)
        try:
            cover_title_text = report_title
        except Exception:
            cover_title_text = 'Report'
        elements.append(Paragraph(cover_title_text, styles['CoverTitle']))
        # Add small date text under subtitle (like 'December 2024') if we have a date range or current month
        try:
            cover_date_text = ''
            if kpis and isinstance(kpis, dict):
                # If the dashboard KPI date_range is available use a simplified month-year or copy date_range
                raw_date = kpis.get('date_range', '')
                if raw_date and isinstance(raw_date, str) and raw_date.strip():
                    cover_date_text = raw_date
            if not cover_date_text:
                cover_date_text = datetime.now().strftime('%B %Y')
        except Exception:
            cover_date_text = datetime.now().strftime('%B %Y')
        # no subtitle text; mimic expected behavior with just the cover date
        if cover_date_text:
            elements.append(Paragraph(cover_date_text, styles['CoverDate']))
        # Add some spacing to push content down
        elements.append(Spacer(1, 520))
        # Keep cover clean; footer will render the branded line
        elements.append(PageBreak())

        elements.append(Paragraph(f"Sales/CRM Analysis Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['ReportTitle']))
        elements.append(Spacer(1, 20))

        for idx, result in enumerate(results, 1):
            section_start = time.time()
            elements.append(Paragraph(f"Query {idx}: {result['query']}", styles['SectionHeader']))
            elements.append(Spacer(1, 15))
            include_table = result.get('include_table', True)
            if include_table and isinstance(result.get('df'), pd.DataFrame) and not result['df'].empty:
                elements.append(Paragraph("Results", styles['SectionHeader']))
                display_df = result['df'].head(10) if len(result['df']) > 10 else result['df']
                data = [display_df.columns.tolist()] + display_df.astype(str).values.tolist()
                col_widths = [min(max(max(len(str(col)), max([len(str(row[i])) for row in display_df.values], default=0)) * 8, 60), 200) for i, col in enumerate(display_df.columns)]
                total_width = sum(col_widths)
                page_width = 552
                if total_width > page_width:
                    scale_factor = page_width / total_width
                    col_widths = [w * scale_factor for w in col_widths]
                table_data = [[Paragraph(str(cell), styles['TableText']) for cell in row] for row in data]
                table = Table(table_data, colWidths=col_widths)
                # Use Unicode font for table header to support rupee symbol (₹)
                table_header_font = chosen_font if chosen_font else 'Helvetica-Bold'
                table.setStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), table_header_font),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F5F6F5')),
                    ('GRID', (1, 1), (-1, -1), 0.5, colors.black),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEADING', (0, 0), (-1, -1), 10),
                    ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
                ])
                elements.append(table)
                if len(result['df']) > 10:
                    elements.append(Paragraph(f"Showing first 10 of {len(result['df'])} rows", styles['BodyText']))
                elements.append(Spacer(1, 15))

            chart_start = time.time()
            if result['chart_buffers']:
                elements.append(Paragraph("Data Visualizations", styles['SectionHeader']))
                for chart_title, chart_buf in result['chart_buffers']:
                    elements.append(Paragraph(chart_title, styles['BodyText']))
                    if hasattr(chart_buf, 'seek'):
                        chart_buf.seek(0)
                    chart_image = Image(chart_buf, width=450, height=300, kind='direct')
                    chart_image.hAlign = 'CENTER'
                    elements.append(chart_image)
                    elements.append(Spacer(1, 10))
            chart_end = time.time()
            _logger.info(f"Chart rendering for Query {idx} took {chart_end - chart_start:.2f} seconds.")

            elements.append(Paragraph("Key Insights", styles['SectionHeader']))
            insights_cleaned = result['insights']
            # Strip HTML tags for PDF, preserving <b> tags
            insights_cleaned = re.sub(r'<div[^>]*>', '', insights_cleaned)  # Remove <div> tags
            insights_cleaned = re.sub(r'</div>', '', insights_cleaned)  # Remove </div> tags
            insights_cleaned = insights_cleaned.replace('<br>', '')  # Remove <br> tags
            insight_lines = [line.strip() for line in insights_cleaned.split('\n') if line.strip()]
            for line in insight_lines:
                try:
                    if line.startswith('- '):
                        bullet_text = line[2:]  # Remove '- ' prefix
                        elements.append(Paragraph(f"• {bullet_text}", styles['BodyText'], bulletText="•"))
                    else:
                        elements.append(Paragraph(line, styles['BodyText']))
                except Exception as e:
                    _logger.error(f"Error parsing insight line '{line}': {str(e)}")
                    elements.append(Paragraph("Error rendering insight", styles['BodyText']))

            elements.append(Spacer(1, 20))
            section_end = time.time()
            _logger.info(f"Section {idx} took {section_end - section_start:.2f} seconds.")

        elements.append(Paragraph(f"Generated by DashBoat", styles['Footer']))
        # Conclusion section (brief AI wrap-up)
        try:
            try:
                elements.append(Spacer(1, 8))
                elements.append(HRFlowable(width="100%", color="#cccccc", thickness=0.8, spaceBefore=6, spaceAfter=8))
            except Exception:
                pass
            elements.append(Paragraph('Conclusion', styles['HL']))
            # ...existing code...
        except Exception:
            pass

        try:
            doc.build(elements, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        except Exception as e:
            _logger.error(f"Error building PDF: {str(e)}")
            raise UserError(f"Failed to generate PDF: {str(e)}")
        buffer.seek(0)
        # Update PDF metadata to replace "anonymous"
        buffer = self._update_pdf_metadata(buffer, report_title)
        total_time = time.time() - start_time
        _logger.info(f"PDF report generated in {total_time:.2f} seconds.")
        return buffer

    def generate_single_chat_pdf(self, chat_id):
        """Generate a PDF for a single chatbot.history message (bot message).
        Returns a BytesIO buffer ready to be streamed.
        """
        Chat = self.env['chatbot.history'].sudo()
        chat = Chat.browse(chat_id)
        if not chat or not chat.exists():
            raise UserError("Chat message not found.")
        if getattr(chat, 'is_user', False):
            raise UserError("Cannot generate PDF for a user message.")

        # Try to build a dataframe from the chat's SQL query if available
        df = pd.DataFrame()
        try:
            sql_q = getattr(chat, 'sql_query', None)
            if sql_q:
                self.env.cr.execute(sql_q)
                columns = [desc[0] for desc in self.env.cr.description]
                result = self.env.cr.fetchall()
                df = pd.DataFrame(result, columns=columns)
        except Exception as e:
            _logger.error(f"Error executing chat SQL for PDF: {str(e)}")
            # Keep df empty; we will still render insights

        # Insights/html from the bot message
        insights_html = getattr(chat, 'insights', None) or getattr(chat, 'response', None) or "No insights available."

        # Derive a title/query text
        query_text = getattr(chat, 'query', None)
        if not query_text:
            try:
                # Use linked user message if available
                user_msg = getattr(chat, 'user_message_id', False)
                query_text = (user_msg and getattr(user_msg, 'message', None)) or (self.query or 'Chat Insight')
            except Exception:
                query_text = self.query or 'Chat Insight'

        # Build payload expected by generate_pdf_report
        results = [{
            'query': query_text,
            'sql_query': getattr(chat, 'sql_query', '') or '',
            'df': df,
            'insights': insights_html,
            'chart_buffers': [],  # charts for single chat are not embedded for now
            'include_table': False,  # only key points for single chat PDF
        }]

        return self.generate_pdf_report(results)

    def download_pdf_report(self):
        if not self.query or not self.result_data:
            raise UserError("No query or results available to generate a PDF report.")

        try:
            df = pd.DataFrame()
            if self.sql_query:
                self.env.cr.execute(self.sql_query)
                columns = [desc[0] for desc in self.env.cr.description]
                result = self.env.cr.fetchall()
                df = pd.DataFrame(result, columns=columns)

            chart_buffers = self.generate_charts(df, self.query)
            results = [{
                'query': self.query,
                'sql_query': self.sql_query,
                'df': df,
                'insights': self.insights or "No insights available.",
                'chart_buffers': chart_buffers
            }]

            pdf_buffer = self.generate_pdf_report(results)
            pdf_data = pdf_buffer.getvalue()

            attachment = self.env['ir.attachment'].create({
                'name': f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                'datas': base64.b64encode(pdf_data),
                'res_model': 'predictive.engine',
                'res_id': self.id,
                'type': 'binary',
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        except Exception as e:
            _logger.error(f"Error generating PDF report: {str(e)}")
            raise UserError(f"Error generating PDF report: {str(e)}")

    def clear_chat_history(self):
        try:
            if self.history_ids:
                self.history_ids.unlink()
                _logger.info(f"Chat history cleared for predictive engine record: {self.id}")
            self.result_data = ""
            self.sql_query = ""
            self.insights = ""
            self.charts = [(6, 0, [])]
            self.charts_html = ""
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'predictive.engine',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'current',
            }
        except Exception as e:
            _logger.error(f"Error clearing chat history: {str(e)}")
            raise UserError(f"Error clearing chat history: {str(e)}")

    def process_query(self, from_chatbot=False):
        query = self.query or ""
        _logger.debug(f"process_query received query: {query}, type: {type(query)}")
        if not query:
            raise UserError("Please enter a query.")

        if not self.name:
            self.name = f"Query: {query[:50]}" if query else f"Query {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        show_table_match = re.match(r'show table (\w+)', query.strip(), re.IGNORECASE)
        if show_table_match:
            table_name = show_table_match.group(1)
            self.env.cr.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE '%_monthly_sale_data'")
            available_tables = [row[0] for row in self.env.cr.fetchall()]
            if table_name not in available_tables:
                self.result_data = f"Table '{table_name}' does not exist."
                self.sql_query = ""
                if not from_chatbot:
                    return {
                        'type': 'ir.actions.act_window',
                        'res_model': 'predictive.engine',
                        'res_id': self.id,
                        'view_mode': 'form',
                        'target': 'current',
                    }
            if not from_chatbot:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'predictive.engine',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            return

        try:
            queries = self.split_combined_query(query)
            all_results = []

            for idx, q in enumerate(queries, 1):
                try:
                    # Always use full schema path
                    schema_map = self._introspect_db_schema(q)
                    if not schema_map:
                        raise UserError("No suitable tables found in database schema for this query.")
                    # If query is not relevant to prior context, reset the FIFO log
                    try:
                        if not self._is_query_relevant(q):
                            self.conversation_log = []
                    except Exception:
                        pass
                    sql_query = self._build_sql_full_schema(q, schema_map)
                    _logger.debug(f"Executing SQL query: {sql_query}")
                    cols, rows = self._run_sql(sql_query)
                    df = pd.DataFrame(rows, columns=cols)

                    insights = self._build_insights(cols, rows, q)
                    chart_buffers = self.generate_charts(df, q)

                    result_data = self._rows_to_html(cols, rows) if rows else "No data found."
                    all_results.append({
                        'query': q,
                        'sql_query': sql_query,
                        'df': df,
                        'insights': insights,
                        'chart_buffers': chart_buffers
                    })

                    if idx == len(queries):
                        self.sql_query = sql_query
                        self.result_data = result_data
                        self.insights = insights
                        chart_attachments = []
                        chart_imgs = []
                        for i, (chart_title, buf) in enumerate(chart_buffers):
                            datas = base64.b64encode(buf.getvalue()).decode()
                            chart_imgs.append(f'<div style="margin-bottom:16px;"><b>{chart_title}</b><br/><img src="data:image/png;base64,{datas}" style="max-width:100%;height:auto;border:1px solid #888;"/></div>')
                            attachment = self.env['ir.attachment'].create({
                                'name': f"{chart_title}.png",
                                'datas': base64.b64encode(buf.getvalue()),
                                'res_model': 'predictive.engine',
                                'res_id': self.id,
                            })
                            chart_attachments.append( attachment.id)
                        self.charts = [(6, 0, chart_attachments)]
                        self.charts_html = '<div style="display: flex; flex-direction: column;">' + ''.join(chart_imgs) + '</div>'
                        self.env['chatbot.history'].create({
                            'engine_id': self.id,
                            'query': q,
                            'sql_query': sql_query,
                            'result_data': result_data,
                            'insights': insights,
                        })

                        # Refresh rolling conversation summary for future turns
                        self._refresh_conversation_summary()

                        # Append to FIFO conversation log
                        self._append_to_conversation_log(user_text=q, assistant_text=insights, sql_text=sql_query)

                except Exception as e:
                    if from_chatbot:
                        friendly_msg = (
                            "Sorry, I couldn't understand your question or generate a valid query.<br><br>"
                            "Please ask questions related to sales data, and make sure to include a year in your question.<br><br>"
                            "For example, you can ask:<br>"
                            "- 2022 monthly sales data<br>"
                            "- 2025 sales data<br>"
                            "- Top 10 customers by sales in 2023<br>"
                                                                                  "- Top 10 salespeople by sales in 2023<br>"
                            "- Monthly sales trend for product X in 2024"
                        )
                        self.result_data = friendly_msg
                        self.insights = friendly_msg
                        self.charts = [(6, 0, [])]
                        self.charts_html = ""
                        return
                    else:
                        raise

            if all_results:
                pdf_buffer = self.generate_pdf_report(all_results)
                self.env['ir.attachment'].create({
                    'name': f"report_{datetime.now().strftime('%Y%m%d')}.pdf",
                    'datas': base64.b64encode(pdf_buffer.getvalue()),
                    'res_model': 'predictive.engine',
                    'res_id': self.id,
                })

            if not from_chatbot:
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'predictive.engine',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            return
        except Exception as e:
            if from_chatbot:
                friendly_msg = (
                    "Sorry, I couldn't understand your question or generate a valid query.<br><br>"
                    "Please ask questions related to sales data, and make sure to include a year in your question.<br><br>"
                    "For example, you can ask:<br>"
                    "- 2022 monthly sales data<br>"
                    "- 2025 sales data<br>"
                    "- Top 10 customers by sales in 2023<br>"
                    "- Top 10 salespeople by sales in 2023<br>"
                    "- Monthly sales trend for product X in 2024"
                )
                self.result_data = friendly_msg
                self.insights = friendly_msg
                self.charts = [(6, 0, [])]
                self.charts_html = ""
                return
            else:
                raise

    def process_chatbot_query(self):
        return self.process_query(from_chatbot=True)

    def _generate_plotly_chart(self, fig, chart_id):
        fig.update_layout(
            font=dict(family="Arial", size=12, color="#333"),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            ),
            margin=dict(l=20, r=20, t=40, b=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig.to_html(
            full_html=False,
            div_id=chart_id,
            config={
                'displayModeBar': True,
                'displaylogo': False,
                'responsive': True,
                'modeBarButtonsToRemove': [
                    'zoom2d', 'zoomIn2d', 'zoomOut2d', 'pan2d', 'select2d', 'lasso2d',
                    'autoScale2d', 'resetScale2d', 'resetViews', 'toImage'
                ]
            }
        )
        
    def _generate_stacked_bar_chart(self, categories, series, title, y_axis_title, chart_id, height=400):
        """
        Generate a stacked bar chart
        
        Args:
            categories: List of category labels for x-axis
            series: List of dicts, each containing 'name', 'data', and 'stack' keys
            title: Chart title
            y_axis_title: Y-axis title
            chart_id: Unique ID for the chart
            height: Chart height in pixels
            
        Returns:
            HTML string containing the chart
        """
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        # Add each series as a bar trace
        for s in series:
            fig.add_trace(go.Bar(
                x=categories,
                y=s['data'],
                name=s['name'],
                text=[f"{x:,.0f}" for x in s['data']],
                textposition='auto',
                textfont=dict(size=10, color='white'),
                hovertemplate='%{x}<br>' + s['name'] + ': %{y:,.2f}<extra></extra>',
                offsetgroup='one',  # Group bars together
                base=None  # Start stacking from the x-axis
            ))
        
        # Update layout for better appearance
        fig.update_layout(
            title=title,
            xaxis_title='',
            yaxis_title=y_axis_title,
            barmode='stack',
            height=height,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=50, r=20, t=60, b=50),
            showlegend=True,
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            ),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        # Format y-axis with commas for thousands
        fig.update_yaxes(tickformat=",.0f")
        
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_lost_reason_chart(self):
        """Generate a donut chart for lost reasons analysis with detailed data."""
        # First, get all lost reasons with their names
        self._cr.execute("""
            SELECT id, name FROM crm_lost_reason
            WHERE active = true
        """)
        reasons = {r[0]: r[1] for r in self._cr.fetchall()}
        
        # Then count lost leads by reason
        self._cr.execute("""
            SELECT 
                lost_reason_id,
                COUNT(id) as count
            FROM crm_lead
            WHERE lost_reason_id IS NOT NULL
            GROUP BY lost_reason_id
            ORDER BY count DESC
        """)
        
        # Process results
        results = []
        for reason_id, count in self._cr.fetchall():
            reason_name = reasons.get(reason_id, 'Unknown')
            if not reason_name:
                reason_name = 'Unknown'
            results.append({
                'lost_reason': reason_name,
                'total_lost_bills': count
            })
        
        if not results:
            return False
            
        # Prepare data for the chart
        labels = [str(item['lost_reason']) for item in results]
        values = [item['total_lost_bills'] for item in results]
        total_lost = sum(values)
        
        # Create donut chart
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            textinfo='label+percent',
            textposition='inside',
            hovertemplate=(
                '<b>%{label}</b><br>' +
                'Count: %{value}<br>' +
                'Percentage: %{percent:.1%}<br>' +
                '<extra></extra>'
            ),
            sort=False
        )])
        
        # Add table with detailed data
        table_data = [
            ["Lost Reason", "Count", "Percentage"]] + [
            [str(item['lost_reason']), 
             item['total_lost_bills'], 
             f"{(item['total_lost_bills']/total_lost*100):.1f}%"] 
            for item in results
        ]
        
        # Update layout with better styling
        fig.update_layout(
            title={
                'text': f'Lost Reason Analysis (Total: {total_lost} Opportunities)',
                'y': 0.95,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': {'size': 14}
            },
            legend={
                'orientation': 'h',
                'y': -0.3,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': {'size': 10}
            },
            margin=dict(l=20, r=20, t=80, b=100, pad=4),
            showlegend=True,
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            ),
            height=500,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        # Format y-axis with commas for thousands
        fig.update_yaxes(tickformat=",.0f")
        
        return self._generate_plotly_chart(fig, 'lost_reason_chart')

    def _generate_sales_performance_chart(self, data):
        months = list(data.keys())
        sales = list(data.values())
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=months,
            y=sales,
            marker_color='#4e79a7',
            text=[self._format_currency(x) for x in sales],
            textposition='auto',
            hovertemplate=f"<b>%{{x}}</b><br>Sales: <b>{self._get_currency_symbol()}%{{y:,.2f}}</b><extra></extra>",
            name=""
        ))
        
        fig.update_layout(
            title_x=0.5,
            title_font=dict(size=18),
            xaxis_title='<b>Month</b>',
            yaxis_title='<b>Sales Amount</b>',
            yaxis=dict(
                tickprefix=self._get_currency_symbol(),
                tickformat=',.2f',
                gridcolor='#f0f0f0'
            ),
            xaxis=dict(
                tickangle=0,
                gridcolor='#f0f0f0'
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=40, r=40, t=60, b=40),
            hoverlabel=dict(
                bgcolor="white",
                font_size=14,
                font_family="Arial"
            )
        )
        
        # Format y-axis with commas for thousands
        fig.update_yaxes(tickformat=",.0f")
        
        return self._generate_plotly_chart(fig, 'sales-performance-chart')

    def _generate_sales_by_product_chart(self, data):
        products = list(data.keys())
        quantities = list(data.values())

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=products,
            y=quantities,
            marker_color='#a3a3ff',
            text=[f"{x:,.2f}" for x in quantities],
            textposition='auto',
            hovertemplate="<b>%{x}</b><br>Quantity: %{y:,.2f}<extra></extra>"
        ))

        fig.update_layout(
            title_x=0.5,
            title_font=dict(size=18),
            xaxis_title='<b>Product</b>',
            yaxis_title='<b>Quantity Sold</b>',
            xaxis_tickangle=-45,
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=400,
            width=633.938
        )

        return self._generate_plotly_chart(fig, 'sales-product-chart')

    def _generate_sales_by_region_chart(self, data):
        regions = list(data.keys())
        sales = list(data.values())
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=regions,
            y=sales,
            marker_color='#ffb366',
            text=[self._format_currency(x) for x in sales],
            textposition='auto',
            hovertemplate=f"<b>%{{x}}</b><br>Sales: {self._get_currency_symbol()}%{{y:,.2f}}<extra></extra>"
        ))
        
        fig.update_layout(
            title_x=0.5,
            title_font=dict(size=18),
            xaxis_title='<b>Region</b>',
            yaxis_title='<b>Sales Amount</b>',
            yaxis_tickprefix=self._get_currency_symbol(),
            yaxis_tickformat=',.2f',
            xaxis_tickangle=-45,
            plot_bgcolor='white',
            paper_bgcolor='white',
        )
        
        return self._generate_plotly_chart(fig, 'sales-region-chart')

    def _generate_top_customers_chart(self, data):
        customers = list(data.keys())
        sales = list(data.values())

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=sales,
            y=customers,
            orientation='h',
            marker_color='#88bde6',
            text=[self._format_currency(x) for x in sales],
            textposition='auto',
            hovertemplate=f"<b>%{{y}}</b><br>Sales: {self._get_currency_symbol()}%{{x:,.2f}}<extra></extra>"
        ))

        fig.update_layout(
            title_x=0.5,
            title_font=dict(size=18),
            xaxis_title='<b>Sales Amount</b>',
            yaxis_title='<b>Customer</b>',
            xaxis_tickprefix=self._get_currency_symbol(),
            xaxis_tickformat=',.2f',
            yaxis_autorange='reversed',
            plot_bgcolor='white',
            paper_bgcolor='white',
        )
        return self._generate_plotly_chart(fig, 'top-customers-chart')

    def _generate_top_salespersons_chart(self, data):
        salespersons = list(data.keys())
        sales = list(data.values())

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=sales,
            y=salespersons,
            orientation='h',
            marker_color='#88bde6',
            text=[self._format_currency(x) for x in sales],
            textposition='auto',
            hovertemplate=f"<b>%{{y}}</b><br>Sales: {self._get_currency_symbol()}%{{x:,.2f}}<extra></extra>"
        ))

        fig.update_layout(
            title_x=0.5,
            title_font=dict(size=18),
            xaxis_title='<b>Sales Amount</b>',
            yaxis_title='<b>Salesperson</b>',
            xaxis_tickprefix=self._get_currency_symbol(),
            xaxis_tickformat=',.2f',
            yaxis_autorange='reversed',
            plot_bgcolor='white',
            paper_bgcolor='white',
        )
        return self._generate_plotly_chart(fig, 'top-salespersons-chart')

    # -------------------- CRM Dashboard Helpers --------------------
    def _generate_donut_chart(self, value, total, title, chart_id, color="#4e79a7", width=300, height=220, hole_size=0.6):
        try:
            percentage = 0 if total in (0, None) else round((value / total) * 100, 2)
        except Exception:
            percentage = 0
        fig = go.Figure(data=[go.Pie(
            labels=[title, "Remaining"],
            values=[value, max(total - value, 0)],
            hole=hole_size,
            marker=dict(colors=[color, '#e9ecef'])
        )])
        fig.update_layout(
            showlegend=False,
            annotations=[dict(text=f"{percentage}%", x=0.5, y=0.5, font_size=14 if height <= 120 else 18, showarrow=False)],
            margin=dict(l=10, r=10, t=10, b=10),
            height=height,
            width=width,
        )
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_due_overdue_heatmap(self, day_labels, due_counts, overdue_counts, chart_id='crm-activities-heatmap'):
        # 2-row heatmap: row 0 = Due (on-time), row 1 = Overdue
        import numpy as np
        z = np.array([
            due_counts,
            overdue_counts,
        ])
        y_labels = ['Due', 'Overdue']
        fig = go.Figure(data=go.Heatmap(
            z=z,
            x=day_labels,
            y=y_labels,
            colorscale='YlOrRd',
            colorbar=dict(title='Count')
        ))
        fig.update_layout(
            xaxis_nticks=min(14, len(day_labels)),
            xaxis_title='<b>Date</b>',
            yaxis_title='',
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=40, r=20, t=10, b=60),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            )
        )
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_geo_bubble_chart(self, labels, values, chart_id='crm-geo-insights'):
        # Create a simple bubble chart: x=countries (categorical), y=count, size scaled by count
        # Scale bubble sizes to a reasonable range
        if not values:
            return '<div style="text-align:center;padding:40px;">No data available</div>'
        min_size, max_size = 12, 48
        vmax = max(values) if values else 1
        sizes = [min_size + (max_size - min_size) * (v / vmax if vmax else 0) for v in values]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=labels,
            y=values,
            mode='markers+text',
            text=[str(v) for v in values],
            textposition='top center',
            marker=dict(size=sizes, color=values, colorscale='Blues', showscale=False, line=dict(width=1, color='white'))
        ))
        fig.update_layout(
            xaxis_title='<b>Country</b>',
            yaxis_title='<b>Leads/Opportunities</b>',
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=40, r=20, t=30, b=60),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            )
        )
        
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_stage_distribution_stacked(self, month_labels, stage_to_series, chart_id='crm-stage-distribution'):
        fig = go.Figure()
        palette = ['#4e79a7', '#f28e2b', '#59a14f', '#e15759', '#edc948', '#b07aa1', '#76b7b2', '#ff9da7', '#9c755f']
        for i, (stage, series) in enumerate(stage_to_series.items()):
            fig.add_trace(go.Bar(name=stage, x=month_labels, y=series, marker_color=palette[i % len(palette)]))
        fig.update_layout(
            barmode='stack',
            xaxis_title='<b>Month</b>',
            yaxis_title='<b>Count</b>',
            plot_bgcolor='white',
            paper_bgcolor='white',
            legend_title_text='Stage',
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            )
        )
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_pipeline_funnel_chart(self, labels, values, chart_id='crm-pipeline-funnel'):
        # Plotly Funnel expects the widest value at the top. We'll pass values as-is.
        fig = go.Figure(go.Funnel(
            y=labels,
            x=values,
            text=[f"{v:,.0f}" for v in values],
            textinfo='value+percent initial',
            marker=dict(
                color=['#4e79a7', '#f28e2b', '#59a14f', '#e15759', '#edc948', '#b07aa1', '#76b7b2', '#ff9da7'][:len(values)],
                line=dict(width=1, color='white')
            )
        ))
        fig.update_layout(
            margin=dict(l=40, r=40, t=30, b=20),
            paper_bgcolor='white',
            plot_bgcolor='white',
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Arial"
            )
        )
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_horizontal_bar(self, labels, values, x_title, y_title, chart_id, color="#88bde6"):
        fig = go.Figure()
        fig.add_trace(go.Bar(x=values, y=labels, orientation='h', marker_color=color, text=[f"{x:,.0f}" for x in values], textposition='auto'))
        fig.update_layout(xaxis_title=f'<b>{x_title}</b>', yaxis_title=f'<b>{y_title}</b>', yaxis_autorange='reversed', plot_bgcolor='white', paper_bgcolor='white')
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_vertical_bar(self, labels, values, x_title, y_title, chart_id, color="#4e79a7", is_money=False):
        fig = go.Figure()
        currency_symbol = self._get_currency_symbol()
        fig.add_trace(go.Bar(x=labels, y=values, marker_color=color, text=[(f"{currency_symbol}{x:,.0f}" if is_money else f"{x:,.0f}") for x in values], textposition='auto'))
        fig.update_layout(xaxis_title=f'<b>{x_title}</b>', yaxis_title=f'<b>{y_title}</b>', plot_bgcolor='white', paper_bgcolor='white')
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_line(self, labels, values, x_title, y_title, chart_id, color="#4e79a7", is_money=False):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=labels, y=values, mode='lines+markers', line=dict(color=color, width=3)))
        currency_symbol = self._get_currency_symbol()
        fig.update_layout(xaxis_title=f'<b>{x_title}</b>', yaxis_title=f'<b>{y_title}</b>', plot_bgcolor='white', paper_bgcolor='white', yaxis_tickprefix=currency_symbol if is_money else None)
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_pie(self, labels, values, chart_id, hole=0.0, colors=None):
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=hole, marker=dict(colors=colors) if colors else None)])
        fig.update_layout(showlegend=True, paper_bgcolor='white', plot_bgcolor='white')
        return self._generate_plotly_chart(fig, chart_id)

    def _generate_sparkline(self, labels, values, chart_id, color="#007bff", width=110, height=38):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(len(values))), y=values, mode='lines', line=dict(color=color, width=2)))
        fig.update_layout(
            margin=dict(l=2, r=2, t=2, b=2),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=height,
            width=width,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return self._generate_plotly_chart(fig, chart_id)

    # -------------------- Dashboard Report Helpers --------------------
    def _collect_sales_chart_series(self, date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """Compute data series for Sales dashboard charts.
        Returns list of dicts: {key, title, description, labels, values}.
        """
        date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
        results = []

        # Sales Performance by Month
        current_date = date_from_resolved
        month_labels, month_values = [], []
        while current_date <= date_to_resolved:
            month_start = current_date.replace(day=1)
            next_month = month_start.replace(day=28) + timedelta(days=4)
            month_end = next_month - timedelta(days=next_month.day)
            if month_end > date_to_resolved:
                month_end = date_to_resolved
            orders = self.env['sale.order'].search([
                ('state', 'in', ['sale','done']),
                ('date_order', '>=', month_start),
                ('date_order', '<=', month_end),
            ])
            month_labels.append(month_start.strftime('%b %Y'))
            month_values.append(sum(orders.mapped('amount_total')))
            current_date = month_end + timedelta(days=1)
        results.append({
            'key': 'sales_performance_chart',
            'title': 'Sales Performance by Month',
            'description': 'Monthly sales totals (amount_total) for confirmed/done orders.',
            'labels': month_labels,
            'values': month_values,
        })

        # Top Products by Quantity
        lines = self.env['sale.order.line'].search([
            ('order_id.state','in',['sale','done']),
            ('order_id.date_order','>=', date_from_resolved),
            ('order_id.date_order','<=', date_to_resolved),
        ])
        prod_to_qty = {}
        for ln in lines:
            name = ln.product_id.name or 'Unknown'
            prod_to_qty[name] = prod_to_qty.get(name, 0.0) + float(ln.product_uom_qty or 0.0)
        top_products = sorted(prod_to_qty.items(), key=lambda kv: kv[1], reverse=True)[:10]
        labels, values = zip(*top_products) if top_products else ([], [])
        results.append({
            'key': 'sales_by_product_chart',
            'title': 'Top Products by Quantity',
            'description': 'Sum of sold quantities within the selected period.',
            'labels': list(labels),
            'values': list(values),
        })

        # Sales by Region
        orders = self.env['sale.order'].search([
            ('state','in',['sale','done']),
            ('date_order','>=', date_from_resolved),
            ('date_order','<=', date_to_resolved),
            ('partner_id.country_id','!=', False)
        ])
        region_to_amt = {}
        for so in orders:
            cname = so.partner_id.country_id.name or 'Unknown'
            region_to_amt[cname] = region_to_amt.get(cname, 0.0) + float(so.amount_total or 0.0)
        top_regions = sorted(region_to_amt.items(), key=lambda kv: kv[1], reverse=True)[:12]
        labels, values = zip(*top_regions) if top_regions else ([], [])
        results.append({
            'key': 'sales_by_region_chart',
            'title': 'Sales by Region',
            'description': 'Total sales amount grouped by customer country.',
            'labels': list(labels),
            'values': list(values),
        })

        # Top Customers
        cust_to_amt = {}
        for so in orders:
            cname = (so.partner_id and so.partner_id.name) or 'Unknown'
            cust_to_amt[cname] = cust_to_amt.get(cname, 0.0) + float(so.amount_total or 0.0)
        top_customers = sorted(cust_to_amt.items(), key=lambda kv: kv[1], reverse=True)[:10]
        labels, values = zip(*top_customers) if top_customers else ([], [])
        results.append({
            'key': 'top_customers_chart',
            'title': 'Top Customers by Sales',
            'description': 'Total sales amount per customer.',
            'labels': list(labels),
            'values': list(values),
        })

        # Top Salespersons
        sp_to_amt = {}
        sp_orders = self.env['sale.order'].search([
            ('state','in',['sale','done']),
            ('date_order','>=', date_from_resolved),
            ('date_order','<=', date_to_resolved),
        ])
        for so in sp_orders:
            sname = (so.user_id and so.user_id.name) or 'Unassigned'
            sp_to_amt[sname] = sp_to_amt.get(sname, 0.0) + float(so.amount_total or 0.0)
        top_salespersons = sorted(sp_to_amt.items(), key=lambda kv: kv[1], reverse=True)[:10]
        labels, values = zip(*top_salespersons) if top_salespersons else ([], [])
        results.append({
            'key': 'top_salespersons_chart',
            'title': 'Top Salespersons by Sales',
            'description': 'Total sales amount per salesperson.',
            'labels': list(labels),
            'values': list(values),
        })

        return results

    def _collect_crm_chart_series(self, date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """Compute data series for CRM dashboard charts.
        Returns list of dicts: {key, title, description, labels, values, crm=True}.
        """
        Lead = self.env['crm.lead']
        Stage = self.env['crm.stage']
        won_stage_ids = Stage.search([('is_won','=',True)]).ids
        date_from_resolved, date_to_resolved = self._get_date_range(date_filter, year_filter, date_from, date_to)
        results = []

        # Pipeline funnel (count by stage)
        opportunities = Lead.search([
            ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
            ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
            ('type', '=', 'opportunity')
        ])
        counts = {}
        for opp in opportunities:
            sname = opp.stage_id.name or 'Undefined'
            counts[sname] = counts.get(sname, 0) + 1
        stage_records = Stage.search([], order='sequence asc')
        ordered = [(rec.name or 'Undefined', counts.get(rec.name or 'Undefined', 0)) for rec in stage_records if (rec.name or 'Undefined') in counts] or list(counts.items())
        labels, values = zip(*ordered) if ordered else ([], [])
        results.append({
            'key': 'pipeline_funnel_chart',
            'title': 'Pipeline Funnel (Count)',
            'description': 'Opportunity count per stage.',
            'labels': list(labels),
            'values': list(values),
            'crm': True,
        })

        # Average deal size trend (monthly)
        month_cursor = date_from_resolved.replace(day=1)
        month_labels, avg_deal_values, won_rev_values = [], [], []
        while month_cursor <= date_to_resolved:
            next_month = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            month_end = next_month - timedelta(days=1)
            month_labels.append(month_cursor.strftime('%b %Y'))
            month_opps = opportunities.filtered(lambda l: l.create_date.date() >= month_cursor and l.create_date.date() <= month_end)
            avg_deal = 0.0 if not month_opps else float(sum(o.expected_revenue or 0.0 for o in month_opps)) / len(month_opps)
            avg_deal_values.append(avg_deal)
            month_won = month_opps.filtered(lambda l: l.stage_id and l.stage_id.id in won_stage_ids)
            won_rev_values.append(sum(float(o.expected_revenue or 0.0) for o in month_won))
            month_cursor = next_month
        results.append({
            'key': 'avg_deal_size_trend_chart',
            'title': 'Average Deal Size Trend',
            'description': 'Average expected revenue per opportunity by month.',
            'labels': month_labels,
            'values': avg_deal_values,
            'crm': True,
        })
        results.append({
            'key': 'won_revenue_trend_chart',
            'title': 'Won Revenue Trend',
            'description': 'Sum of expected revenue of won opportunities by month.',
            'labels': month_labels,
            'values': won_rev_values,
            'crm': True,
        })

        # Stage distribution (total)
        counts = {}
        for opp in opportunities:
            sname = opp.stage_id.name or 'Undefined'
            counts[sname] = counts.get(sname, 0) + 1
        top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
        labels, values = zip(*top) if top else ([], [])
        results.append({
            'key': 'stage_distribution_chart',
            'title': 'Stage Distribution',
            'description': 'Total opportunities per stage within the selected period.',
            'labels': list(labels),
            'values': list(values),
            'crm': True,
        })

        # Lead source effectiveness
        records = Lead.search([
            ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
            ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
        ])
        src_counts = {}
        for l in records:
            src = (getattr(l, 'source_id', False) and l.source_id.name) or (getattr(l, 'medium_id', False) and l.medium_id.name) or 'Unknown'
            src_counts[src] = src_counts.get(src, 0) + 1
        top = sorted(src_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        labels, values = zip(*top) if top else ([], [])
        results.append({
            'key': 'lead_source_chart',
            'title': 'Lead Source Effectiveness',
            'description': 'Counts by lead/opportunity source.',
            'labels': list(labels),
            'values': list(values),
            'crm': True,
        })

        # Sales performance by salesperson (expected revenue)
        sp_amounts = {}
        for opp in opportunities:
            sp_name = opp.user_id.name or 'Unassigned'
            sp_amounts[sp_name] = sp_amounts.get(sp_name, 0.0) + float(opp.expected_revenue or 0.0)
        top = sorted(sp_amounts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        labels, values = zip(*top) if top else ([], [])
        results.append({
            'key': 'sales_perf_chart',
            'title': 'Sales Performance by Salesperson',
            'description': 'Expected revenue per salesperson from opportunities.',
            'labels': list(labels),
            'values': list(values),
            'crm': True,
        })

        # Revenue Forecast by Month (aggregated total weighted revenue per month)
        revenue_forecast = {}
        all_records = Lead.search([
            ('create_date', '>=', fields.Datetime.to_datetime(date_from_resolved)),
            ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to_resolved, datetime.max.time()))),
        ])
        for opp in all_records.filtered(lambda l: l.probability > 0 and l.expected_revenue > 0):
            create_date = fields.Datetime.from_string(opp.create_date).date() if opp.create_date else fields.Date.today()
            month_year = create_date.strftime('%b %Y')
            weighted_revenue = opp.expected_revenue * (opp.probability / 100.0)
            revenue_forecast[month_year] = revenue_forecast.get(month_year, 0.0) + weighted_revenue
        
        if revenue_forecast:
            # Sort by month chronologically
            sorted_months = sorted(revenue_forecast.keys(), key=lambda x: datetime.strptime(x, '%b %Y'))
            forecast_labels = sorted_months
            forecast_values = [revenue_forecast[m] for m in forecast_labels]
            results.append({
                'key': 'revenue_forecast_chart',
                'title': 'Revenue Forecast',
                'description': 'Weighted revenue forecast by month (expected_revenue * probability).',
                'labels': forecast_labels,
                'values': forecast_values,
                'crm': True,
            })

        # Geographical insights (by country)
        geo_counts = {}
        for rec in all_records:
            country = (rec.country_id and rec.country_id.name) or (rec.partner_id and rec.partner_id.country_id and rec.partner_id.country_id.name) or 'Unknown'
            geo_counts[country] = geo_counts.get(country, 0) + 1
        geo_sorted = sorted(geo_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        if geo_sorted:
            glabels, gvals = zip(*geo_sorted)
            results.append({
                'key': 'geo_insights_chart',
                'title': 'Geographical Insights',
                'description': 'Lead and opportunity count by country.',
                'labels': list(glabels),
                'values': list(gvals),
                'crm': True,
            })

        return results

    def _matplotlib_bar(self, labels, values, title):
        """Create a simple bar chart PNG buffer using matplotlib with thread-safe backend."""
        try:
            with self._matplotlib_lock:
                plt.style.use('default')
                fig = plt.figure(figsize=(8, 4.5))
                ax = fig.add_subplot(111)
                ax.bar(range(len(values)), values, color='#4e79a7')
                ax.set_xticks(range(len(labels)))
                ax.set_xticklabels(labels, rotation=45, ha='right')
                ax.set_title(title)
                ax.grid(True, linestyle='--', alpha=0.4)
                fig.tight_layout()
                buf = BytesIO()
                plt.savefig(buf, format='png', dpi=200, bbox_inches='tight')
                buf.seek(0)
                plt.close(fig)
                plt.clf()  # Clear the current figure
            return buf
        except Exception as e:
            _logger.error(f"Error generating matplotlib chart: {e}")
            return None

    def _process_chart_payload_for_pdf(self, payload):
        chart_key = payload['chart_key']
        title = payload['title']
        desc = payload['description']
        labels = payload['labels']
        values = payload['values']
        date_filter = payload['date_filter']
        year_filter = payload['year_filter']
        date_from = payload['date_from']
        date_to = payload['date_to']
        crm_context = payload['crm_context']
        date_range_text = payload['date_range_text']

        insight_html = ""
        try:
            _logger.info(f"[FAST PDF] Generating insight for '{chart_key}' ({title})")
            insight_html = self.get_chart_insight(
                chart_key=chart_key,
                date_filter=date_filter,
                year_filter=year_filter,
                date_from=date_from,
                date_to=date_to
            )
            _logger.info(f"[FAST PDF] Insight ready for '{chart_key}': {len(insight_html) if insight_html else 0} chars")
        except Exception as e:
            _logger.error(f"[FAST PDF] Insight generation failed for '{chart_key}': {e}", exc_info=True)

        if not insight_html:
            try:
                chart_data = {
                    'title': title,
                    'description': desc,
                    'labels': labels,
                    'values': values,
                }
                insight_html = self.get_cached_insights(title, chart_data, date_range_text, crm_context=crm_context)
                _logger.info(f"[FAST PDF] Used cached/heuristic insight for '{chart_key}': {len(insight_html) if insight_html else 0} chars")
            except Exception as e2:
                _logger.error(f"[FAST PDF] Fallback insights failed for '{chart_key}': {e2}", exc_info=True)
                insight_html = ""

        chart_buf = None
        try:
            chart_buf = self._matplotlib_bar(labels, values, title)
        except Exception as e:
            _logger.error(f"[FAST PDF] Chart rendering failed for '{chart_key}': {e}", exc_info=True)

        return insight_html, chart_buf

    def _split_insight_sentences(self, text):
        """Split a text into sentences by period, exclamation, or question mark.
        Returns a list of sentences with punctuation added back.
        Very aggressive splitting - splits after any sentence-ending punctuation.
        """
        if not text or not text.strip():
            return []
        
        # First, split by period followed by space (most common case)
        sentences = text.split('. ')
        
        # Further split each part if it contains period without space (edge cases)
        final_sentences = []
        for part in sentences:
            # Split by period followed by capital letter or dash (no space)
            # This handles cases like "sentence.Another" or "sentence.-"
            sub_parts = re.split(r'\.(?=[A-Z\-•])', part)
            for sub in sub_parts:
                sub = sub.strip()
                if sub and len(sub) > 3:
                    # Add period back if it doesn't already end with punctuation
                    if not sub.endswith(('.', '!', '?', ':', ';')):
                        sub += '.'
                    final_sentences.append(sub)
        
        # Also handle exclamation and question marks
        result = []
        for sentence in final_sentences:
            # Split by exclamation or question mark followed by space
            parts = re.split(r'([!?])\s+', sentence)
            i = 0
            while i < len(parts):
                if i + 1 < len(parts) and parts[i + 1] in '!?':
                    # Combine text with its punctuation
                    combined = parts[i] + parts[i + 1]
                    if combined.strip() and len(combined.strip()) > 3:
                        result.append(combined.strip())
                    i += 2
                else:
                    if parts[i].strip() and len(parts[i].strip()) > 3:
                        result.append(parts[i].strip())
                    i += 1
        
        return result if result else final_sentences

    def _clean_trailing_marker(self, sentence):
        """Remove stray numeric markers like '.2' or '2.' at the end of sentences."""
        if not sentence:
            return sentence
        # Strip spaces then drop trailing numeric markers with optional period
        cleaned = sentence.strip()
        cleaned = re.sub(r'\s*\b\d+\b\.?\s*$', '', cleaned).strip()
        return cleaned

    def _detect_currency_symbol(self, cols, rows):
        """Try to detect a currency symbol from the result rows; fallback to company currency."""
        symbols_pattern = r'[₹$€£¥₽₩₺₫₪₴₦]'
        try:
            for row in rows:
                for cell in row:
                    if isinstance(cell, str):
                        m = re.search(symbols_pattern, cell)
                        if m:
                            return m.group(0)
        except Exception:
            pass
        return self._get_currency_symbol()

    def generate_dashboard_report_pdf_fast(self, dashboard='sales', date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """Fast PDF generation with optimizations - uses same insights as AI Analysis button"""
        import time
        start_time = time.time()
        
        # Get data
        if dashboard == 'crm':
            kpis = self.get_crm_dashboard_data(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            series = self._collect_crm_chart_series(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            crm_context = True
        else:
            kpis = self.get_dashboard_data(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            series = self._collect_sales_chart_series(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            crm_context = False
        
        _logger.info(f"Data collection took {time.time() - start_time:.2f} seconds")
        _logger.info(f"[FAST PDF] Collected {len(series)} chart series: {[s.get('key') or s.get('title') for s in series]}")
        
        # Generate insights and charts in parallel with a max of 3 workers (3-3 parallel)
        insights_start = time.time()
        insights_data = {}
        chart_buffers = {}
        date_range_text = kpis.get('date_range', '')
        chart_payloads = []
        for idx, s in enumerate(series, 1):
            chart_payloads.append({
                'chart_key': s.get('key') or f'chart_{idx}',
                'title': s.get('title') or s.get('key') or f'Chart {idx}',
                'description': s.get('description') or '',
                'labels': list(s.get('labels') or [])[:12],
                'values': list(s.get('values') or [])[:12],
                'date_filter': date_filter,
                'year_filter': year_filter,
                'date_from': date_from,
                'date_to': date_to,
                'crm_context': crm_context,
                'date_range_text': date_range_text,
            })

        registry = self.env.registry
        dbname = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context or {})

        def process_payload(payload):
            with registry.cursor() as cr:
                env = api.Environment(cr, uid, context)
                rec = env[self._name].browse(self.id)
                return rec._process_chart_payload_for_pdf(payload)

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_map = {executor.submit(process_payload, payload): payload for payload in chart_payloads}
            for future in as_completed(future_map):
                payload = future_map[future]
                title = payload['title']
                try:
                    insight_html, chart_buf = future.result()
                    insights_data[title] = insight_html
                    chart_buffers[title] = chart_buf
                except Exception as e:
                    _logger.error(f"[FAST PDF] Parallel task failed for '{title}': {e}", exc_info=True)
                    insights_data[title] = ""
                    chart_buffers[title] = None

        _logger.info(f"[FAST PDF] Insight + chart generation took {time.time() - insights_start:.2f} seconds")
        _logger.info(f"[FAST PDF] Total insights generated: {len([v for v in insights_data.values() if v])}/{len(insights_data)}")
        _logger.info(f"[FAST PDF] Insights keys: {list(insights_data.keys())}")
        
        # Build PDF with cached insights
        pdf_start = time.time()
        buffer = BytesIO()
        report_title = 'CRM Dashboard Report' if crm_context else 'Sales Dashboard Report'

        icp = self.env['ir.config_parameter'].sudo()
        company_name = ''
        try:
            custom_name = icp.get_param('dashboat.report_company_name')
            if custom_name:
                company_name = custom_name
            elif self.env.company and self.env.company.name:
                company_name = self.env.company.name
        except Exception as e:
            _logger.warning(f"Using fallback company name due to error: {e}")
        if not company_name:
            company_name = 'Your Company'
        module_url = icp.get_param('dashboat.module_url', 'https://dashboat.sufalamtech.com')
        powered_by_text = "Powered by Sufalam Technologies"
        base_font = 'Helvetica'

        generated_date_text = datetime.now().strftime('%b %d, %Y')

        def draw_header(canvas, doc):
            """Header on all non-cover pages with title/date and golden line."""
            try:
                canvas.saveState()
                width, height = doc.pagesize
                margin = 40
                title_font = 'Helvetica-Bold'
                title_size = 11
                date_font = 'Helvetica'
                date_size = 10
                title_text = report_title
                date_range_text = kpis.get('date_range', '')
                canvas.setFillColor(colors.HexColor('#14213D'))
                canvas.setFont(title_font, title_size)
                canvas.drawString(margin, height - 30, title_text)
                if date_range_text:
                    title_width = canvas.stringWidth(title_text, title_font, title_size)
                    canvas.setFont(date_font, date_size)
                    canvas.drawString(margin + title_width + 4, height - 30, f" ({date_range_text})")
                canvas.setFont(date_font, date_size)
                date_width = canvas.stringWidth(generated_date_text, date_font, date_size)
                canvas.drawString(width - margin - date_width, height - 30, generated_date_text)
                canvas.setStrokeColor(colors.HexColor('#9E9E9E'))
                canvas.setLineWidth(1)
                canvas.line(0, height - 39, width, height - 39)
                canvas.restoreState()
            except Exception as e:
                _logger.debug(f"Error drawing header: {e}")

        def draw_footer(canvas, doc, is_first_page=False):
            try:
                canvas.saveState()
                width, height = doc.pagesize
                footer_y = 50
                
                # Draw grey line
                canvas.setStrokeColor(colors.HexColor('#9E9E9E'))
                canvas.setLineWidth(1)
                canvas.line(0, footer_y, width, footer_y)
                
                # Set font and color
                font_name = 'Helvetica-Bold'
                font_size = 9
                canvas.setFont(font_name, font_size)
                canvas.setFillColor(colors.HexColor('#14213D'))
                
                text_y = footer_y - 16
                
                if is_first_page:
                    # Cover page: Company name on left, Powered by Sufalam Technologies on right
                    # Left side - Company name
                    company_display = str(company_name) if company_name else 'Your Company'
                    canvas.drawString(40, text_y, company_display)
                    
                    # Right side - Powered by Sufalam Technologies (static text)
                    # Use simpler approach - draw directly with fixed margin
                    prefix_text = "Powered by "
                    suffix_text = "Sufalam Technologies"
                    powered_text = prefix_text + suffix_text
                    try:
                        text_width = canvas.stringWidth(powered_text, font_name, font_size)
                        prefix_width = canvas.stringWidth(prefix_text, font_name, font_size)
                        suffix_width = canvas.stringWidth(suffix_text, font_name, font_size)
                        # Account for page margins (40px left/right margin from SimpleDocTemplate)
                        # Letter size is 612 points wide, minus margins
                        usable_width = width - 80  # 40px margin on each side
                        right_x = usable_width - text_width + 40  # Start from right margin
                        # Ensure it's within bounds
                        if right_x < width - 500:  # Make sure it's not too far left
                            right_x = width - text_width - 50
                        canvas.drawString(right_x, text_y, prefix_text)
                        suffix_x = right_x + prefix_width
                        # Suffix in light purple
                        suffix_color = colors.HexColor('#8a6cf6')
                        canvas.setFillColor(suffix_color)
                        canvas.drawString(suffix_x, text_y, suffix_text)
                        # Restore default color
                        canvas.setFillColor(colors.HexColor('#14213D'))
                        # Make only the vendor name clickable
                        canvas.linkURL(
                            "https://apps.odoo.com/apps/modules/18.0/DashBoat",
                            (suffix_x, text_y - 2, suffix_x + suffix_width, text_y + font_size),
                            relative=0,
                        )
                        _logger.info(f"Footer cover page: width={width}, text_width={text_width}, right_x={right_x}, text='{powered_text}'")
                    except Exception as e:
                        _logger.error(f"Error calculating/drawing powered_by: {e}", exc_info=True)
                        # Fallback: draw at fixed position from right edge
                        canvas.drawString(width - 280, text_y, powered_text)
                else:
                    # Other pages: match cover page footer (company left, powered-by right)
                    company_display = str(company_name) if company_name else 'Your Company'
                    canvas.drawString(40, text_y, company_display)

                    prefix_text = "Powered by "
                    suffix_text = "Sufalam Technologies"
                    powered_text = prefix_text + suffix_text
                    try:
                        text_width = canvas.stringWidth(powered_text, font_name, font_size)
                        prefix_width = canvas.stringWidth(prefix_text, font_name, font_size)
                        suffix_width = canvas.stringWidth(suffix_text, font_name, font_size)
                        usable_width = width - 80  # 40px margin on each side
                        right_x = usable_width - text_width + 40
                        if right_x < width - 500:
                            right_x = width - text_width - 50
                        canvas.drawString(right_x, text_y, prefix_text)
                        suffix_x = right_x + prefix_width
                        suffix_color = colors.HexColor('#8a6cf6')
                        canvas.setFillColor(suffix_color)
                        canvas.drawString(suffix_x, text_y, suffix_text)
                        canvas.setFillColor(colors.HexColor('#14213D'))
                        canvas.linkURL(
                            "https://apps.odoo.com/apps/modules/18.0/DashBoat",
                            (suffix_x, text_y - 2, suffix_x + suffix_width, text_y + font_size),
                            relative=0,
                        )
                    except Exception as e:
                        _logger.error(f"Error drawing powered_by on later page: {e}", exc_info=True)
                        canvas.drawString(width - 280, text_y, powered_text)
                
                canvas.restoreState()
            except Exception as e:
                _logger.error(f"Error drawing footer: {e}", exc_info=True)

        def on_first_page(canvas, doc):
            """Set PDF metadata on first page"""
            canvas.setTitle(report_title)
            canvas.setAuthor(report_title)
            canvas.setSubject(report_title)
            # Draw download date on the top-right corner of the cover
            try:
                canvas.saveState()
                width, height = doc.pagesize
                date_text = datetime.now().strftime('%b %d, %Y')
                font_name = 'Helvetica-Bold'
                font_size = 11
                margin = 30
                canvas.setFont(font_name, font_size)
                canvas.setFillColor(colors.HexColor('#14213D'))
                text_width = canvas.stringWidth(date_text, font_name, font_size)
                x = width - margin - text_width
                y = height - 40
                canvas.drawString(x, y, date_text)
                canvas.restoreState()
            except Exception as e:
                _logger.debug(f"Could not draw cover date: {e}")
            # Draw footer and Set Creator to replace "anonymous" - use PDF metadata dictionary format
            try:
                draw_footer(canvas, doc, is_first_page=True)
                from reportlab.pdfgen.canvas import Canvas
                if hasattr(canvas, '_doc') and hasattr(canvas._doc, 'info'):
                    # Set Creator field in PDF info dictionary
                    canvas._doc.info['/Creator'] = report_title
                    canvas._doc.info['/Producer'] = report_title
            except Exception as e:
                _logger.debug(f"Could not set Creator metadata: {e}")
        
        def on_later_pages(canvas, doc):
            """Set PDF metadata on later pages"""
            canvas.setTitle(report_title)
            canvas.setAuthor(report_title)
            canvas.setSubject(report_title)
            try:
                draw_header(canvas, doc)
            except Exception:
                pass
            # Draw footer and Set Creator to replace "anonymous" - use PDF metadata dictionary format
            try:
                draw_footer(canvas, doc, is_first_page=False)
                if hasattr(canvas, '_doc') and hasattr(canvas._doc, 'info'):
                    # Set Creator field in PDF info dictionary
                    canvas._doc.info['/Creator'] = report_title
                    canvas._doc.info['/Producer'] = report_title
            except Exception as e:
                _logger.debug(f"Could not set Creator metadata: {e}")
        
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=54, bottomMargin=70, leftMargin=40, rightMargin=40, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        styles = getSampleStyleSheet()
        # Ensure a Unicode font (supports ₹) is registered and used
        chosen_font = None
        try:
            font_candidates = [
                ('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                ('NirmalaUI', r'C:\Windows\Fonts\Nirmala.ttf'),
                ('SegoeUI', r'C:\Windows\Fonts\segoeui.ttf'),
                ('ArialUnicodeMS', r'C:\Windows\Fonts\arialuni.ttf'),
            ]
            for name, path in font_candidates:
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    chosen_font = name
                    break
                except Exception:
                    continue
            if chosen_font:
                for sty_name in ['Normal', 'BodyText']:
                    if sty_name in styles:
                        styles[sty_name].fontName = chosen_font
                base_font = chosen_font
        except Exception:
            pass
        # Create custom styles with Unicode font support for rupee symbol (₹)
        base_font = chosen_font if chosen_font else 'Helvetica'
        styles.add(ParagraphStyle(name='CoverTitle', fontSize=48, alignment=0, spaceAfter=8, leading=52, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='CoverSubTitle', fontSize=14, alignment=0, textColor=colors.HexColor('#6B7280'), spaceAfter=6, fontName=base_font))
        styles.add(ParagraphStyle(name='CoverDate', fontSize=10, alignment=0, textColor=colors.HexColor('#9AA0A6'), spaceAfter=8, fontName=base_font))
        styles.add(ParagraphStyle(name='ReportTitle', fontSize=20, alignment=1, spaceAfter=14, leading=22, fontName=base_font))
        styles.add(ParagraphStyle(name='SubTitle', fontSize=11, alignment=1, textColor='#555555', spaceAfter=10, fontName=base_font))
        styles.add(ParagraphStyle(name='SectionHeader', fontSize=18, spaceBefore=0, spaceAfter=8, leading=16, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='HL', fontSize=13, spaceBefore=10, spaceAfter=6, leading=15, underline=True, fontName=base_font))
        styles.add(ParagraphStyle(name='Small', fontSize=9, spaceAfter=6, textColor='#666666', fontName=base_font))
        styles.add(ParagraphStyle(name='DashBullet', fontSize=10, leftIndent=14, spaceBefore=2, spaceAfter=2, leading=14, fontName=base_font))
        styles.add(ParagraphStyle(name='IndexTitle', fontSize=22, alignment=0, spaceAfter=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='IndexEntry', fontSize=11, alignment=0, spaceAfter=4, fontName=base_font, leftIndent=10))

        elements = []
        # Cover page
        elements.append(Paragraph(report_title, styles['CoverTitle']))
        try:
            # Use kpis['date_range'] specifically as the cover date; it's the only date shown on the cover.
            cover_date_text = kpis.get('date_range', '') or datetime.now().strftime('%B %Y')
        except Exception:
            cover_date_text = datetime.now().strftime('%B %Y')
        # Only render the cover date line; no subtitle is used.
        if cover_date_text:
            elements.append(Paragraph(cover_date_text, styles['CoverDate']))
        
        # Add spacing before golden line on cover page
        elements.append(Spacer(1, 480))
        
        # Keep cover clean; footer will render the branded line
        elements.append(PageBreak())

        # TASK 1: Index page removed - go directly to KPI section
        
        # Key Performance Indicators section (simplified card-style like UI)
        kpi_title_style = ParagraphStyle(
            'KPITitle',
            parent=styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#1e3a5f'),
            fontName='Helvetica-Bold',
            spaceAfter=6,
            leading=22
        )
        elements.append(Paragraph('Key Performance Indicators', kpi_title_style))
        try:
                elements.append(HRFlowable(width="92%", hAlign="LEFT", color="#F0B430", thickness=2, spaceBefore=2, spaceAfter=14))
        except Exception:
            pass

        currency_symbol = self._get_currency_symbol()
        label_style = ParagraphStyle(
            'KpiLabel',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#6c7680'),
            fontName=base_font,
            leading=13
        )
        value_style = ParagraphStyle(
            'KpiValue',
            parent=styles['Normal'],
            fontSize=26,
            textColor=colors.HexColor('#14213D'),
            fontName=base_font,
            leading=28
        )

        if crm_context:
            cards = [
                ('Total Leads', kpis.get('kpi_total_leads', '0')),
                ('Total Opportunities', kpis.get('kpi_total_opps', '0')),
                ('Conversion Rate', kpis.get('conversion_rate_kpi', '0%')),
                ('Won Revenue', kpis.get('revenue_target_label', f'{currency_symbol}0')),
            ]
            cols = 2
        else:
            cards = [
                ('Total Sales', kpis.get('total_sales', f'{currency_symbol}0.00')),
                ('Avg. Deal Size', kpis.get('avg_deal_size', f'{currency_symbol}0.00')),
            ]
            cols = 2

        # Build a simple grid of card tables
        def chunk(lst, size):
            for i in range(0, len(lst), size):
                yield lst[i:i + size]

        table_rows = []
        for row_cards in chunk(cards, cols):
            row_cells = []
            for label, val in row_cards:
                inner = Table(
                    [[Paragraph(label, label_style)],
                     [Paragraph(val, value_style)]],
                    colWidths=[220]
                )
                inner.setStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f9fbff')),
                    ('LINEBEFORE', (0, 0), (0, -1), 5, colors.HexColor('#1e3a5f')),
                    ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#d9dee5')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 12),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ])
                row_cells.append(inner)
            # Pad row if uneven
            while len(row_cells) < cols:
                row_cells.append('')
            table_rows.append(row_cells)

        kpi_table = Table(table_rows, colWidths=[260] * cols, hAlign='LEFT')
        kpi_table.setStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ])
        elements.append(kpi_table)
        elements.append(Spacer(1, 18))

        # Per-chart sections with cached insights
        _logger.info(f"[PDF RENDER] Starting to render {len(series)} charts")
        _logger.info(f"[PDF RENDER] Available insights keys: {list(insights_data.keys())}")
        for idx, s in enumerate(series, 1):
            chart_title = s['title']
            _logger.info(f"[PDF RENDER {idx}/{len(series)}] Processing chart: '{chart_title}'")
            # TASK 3: Add page break before each chart (including first)
            if idx >= 1:
                elements.append(PageBreak())
            elements.append(Paragraph(chart_title, styles['SectionHeader']))
            # Add golden line below chart title (same as KPI section)
            try:
                elements.append(HRFlowable(width="92%", hAlign="LEFT", color="#F0B430", thickness=2.5, spaceBefore=2, spaceAfter=12))
            except Exception:
                pass
            
            # Chart image
            buf = chart_buffers.get(chart_title) or self._matplotlib_bar(s['labels'][:12], s['values'][:12], chart_title)
            if buf:
                img = Image(buf, width=450, height=260, kind='direct')
                img.hAlign = 'CENTER'
                elements.append(img)
            
            # Use cached insights
            insight_html = insights_data.get(chart_title, '')
            _logger.info(f"[PDF RENDER {idx}/{len(series)}] Insight found for '{chart_title}': {len(insight_html) if insight_html else 0} chars")
            
            # If no insights found, generate fallback heuristic insights
            if not insight_html:
                _logger.warning(f"[PDF RENDER {idx}/{len(series)}] No insights for '{chart_title}', generating fallback")
                try:
                    chart_data = {
                        'title': chart_title,
                        'description': s.get('description') or '',
                        'labels': list(s.get('labels') or [])[:12],
                        'values': list(s.get('values') or [])[:12],
                    }
                    insight_html = self.get_cached_insights(chart_title, chart_data, kpis.get('date_range', ''), crm_context=crm_context)
                    _logger.info(f"[PDF RENDER {idx}/{len(series)}] Generated fallback insights: {len(insight_html) if insight_html else 0} chars")
                except Exception as e:
                    _logger.error(f"[PDF RENDER {idx}/{len(series)}] Fallback failed: {e}")
                    insight_html = ""
            
            if insight_html:
                tmp = insight_html or ''
                tmp = re.sub(r'<h4[^>]*>.*?Key\s*Insights.*?</h4>', '\n__KEY__\n', tmp, flags=re.IGNORECASE|re.DOTALL)
                tmp = re.sub(r'<h4[^>]*>.*?Strengths\s*&\s*Opportunities.*?</h4>', '\n__PRO__\n', tmp, flags=re.IGNORECASE|re.DOTALL)
                tmp = re.sub(r'<h4[^>]*>.*?Areas\s*for\s*Improvement.*?</h4>', '\n__CON__\n', tmp, flags=re.IGNORECASE|re.DOTALL)
                plain = re.sub(r'<[^>]+>', '', tmp)
                lines = [ln.strip() for ln in plain.split('\n')]
                sections = {'Key Insights': [], 'Strengths & Opportunities': [], 'Areas for Improvement': []}
                current = None
                for ln in lines:
                    if ln == '__KEY__':
                        current = 'Key Insights'
                        continue
                    if ln == '__PRO__':
                        current = 'Strengths & Opportunities'
                        continue
                    if ln == '__CON__':
                        current = 'Areas for Improvement'
                        continue
                    if not ln:
                        continue
                    if current:
                        # Split long lines by sentence-ending punctuation to create separate bullet points
                        cleaned = ln.lstrip('- ').strip()
                        if not cleaned:
                            continue
                        # Use helper function to split sentences
                        sentences = self._split_insight_sentences(cleaned)
                        for sent in sentences:
                            sent_clean = self._clean_trailing_marker(sent)
                            if sent_clean:
                                sections[current].append(sent_clean)
                if sections['Key Insights']:
                    elements.append(Paragraph('Key Insights', styles['HL']))
                    items = [ListItem(Paragraph(b, styles['DashBullet'])) for b in sections['Key Insights'][:10]]
                    elements.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=10))
                if sections['Strengths & Opportunities']:
                    elements.append(Paragraph('Strengths & Opportunities', styles['HL']))
                    items = [ListItem(Paragraph(b, styles['DashBullet'])) for b in sections['Strengths & Opportunities'][:10]]
                    elements.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=10))
                if sections['Areas for Improvement']:
                    elements.append(Paragraph('Areas for Improvement', styles['HL']))
                    items = [ListItem(Paragraph(b, styles['DashBullet'])) for b in sections['Areas for Improvement'][:10]]
                    elements.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=10))

        try:
            doc.build(elements, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        except Exception as e:
            _logger.error(f"Error building dashboard PDF: {str(e)}")
            raise UserError(f"Failed to generate dashboard PDF: {str(e)}")
        
        buffer.seek(0)
        # Update PDF metadata to replace "anonymous"
        buffer = self._update_pdf_metadata(buffer, report_title)
        _logger.info(f"PDF building took {time.time() - pdf_start:.2f} seconds")
        _logger.info(f"Total time: {time.time() - start_time:.2f} seconds")
        return buffer

    def generate_dashboard_report_pdf(self, dashboard='sales', date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """Build a comprehensive PDF for the Sales or CRM dashboard with overview, insights,
        and per-chart images plus insights/pros/cons.
        Returns BytesIO.
        """
        # Gather data and series
        if dashboard == 'crm':
            kpis = self.get_crm_dashboard_data(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            series = self._collect_crm_chart_series(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            crm_context = True
        else:
            kpis = self.get_dashboard_data(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            series = self._collect_sales_chart_series(date_filter=date_filter, year_filter=year_filter, date_from=date_from, date_to=date_to)
            crm_context = False

        buffer = BytesIO()
        report_title = 'CRM Dashboard Report' if crm_context else 'Sales Dashboard Report'

        icp = self.env['ir.config_parameter'].sudo()
        company_name = ''
        try:
            custom_name = icp.get_param('dashboat.report_company_name')
            if custom_name:
                company_name = custom_name
            elif self.env.company and self.env.company.name:
                company_name = self.env.company.name
        except Exception as e:
            _logger.warning(f"Using fallback company name due to error: {e}")
        if not company_name:
            company_name = 'Your Company'
        module_url = icp.get_param('dashboat.module_url', 'https://dashboat.sufalamtech.com')
        powered_by_text = "Powered by Sufalam Technologies"
        base_font = 'Helvetica'

        generated_date_text = datetime.now().strftime('%b %d, %Y')

        def draw_header(canvas, doc):
            """Header on all non-cover pages with title/date and golden line."""
            try:
                canvas.saveState()
                width, height = doc.pagesize
                margin = 40
                title_font = 'Helvetica-Bold'
                title_size = 11
                date_font = 'Helvetica'
                date_size = 10
                title_text = report_title
                date_range_text = kpis.get('date_range', '')
                canvas.setFillColor(colors.HexColor('#14213D'))
                canvas.setFont(title_font, title_size)
                canvas.drawString(margin, height - 30, title_text)
                if date_range_text:
                    title_width = canvas.stringWidth(title_text, title_font, title_size)
                    canvas.setFont(date_font, date_size)
                    canvas.drawString(margin + title_width + 4, height - 30, f" ({date_range_text})")
                canvas.setFont(date_font, date_size)
                date_width = canvas.stringWidth(generated_date_text, date_font, date_size)
                canvas.drawString(width - margin - date_width, height - 30, generated_date_text)
                canvas.setStrokeColor(colors.HexColor('#9E9E9E'))
                canvas.setLineWidth(1)
                canvas.line(0, height - 39, width, height - 39)
                canvas.restoreState()
            except Exception as e:
                _logger.debug(f"Error drawing header: {e}")

        def draw_footer(canvas, doc, is_first_page=False):
            try:
                canvas.saveState()
                width, height = doc.pagesize
                y = 40  # distance from bottom
                
                # Draw golden line
                canvas.setStrokeColor(colors.HexColor('#9E9E9E'))
                canvas.setLineWidth(1)
                canvas.line(0, y + 10, width, y + 10)
                
                # Set font and color
                font_name = 'Helvetica-Bold'
                font_size = 9
                canvas.setFont(font_name, font_size)
                canvas.setFillColor(colors.HexColor('#14213D'))
                
                text_y = y - 6
                
                if is_first_page:
                    # Cover page: Company name on left, Powered by Sufalam Technologies on right
                    # Left side - Company name
                    company_display = str(company_name) if company_name else 'Your Company'
                    canvas.drawString(40, text_y, company_display)
                    
                    # Right side - Powered by Sufalam Technologies (static text)
                    # Use simpler approach - draw directly with fixed margin
                    prefix_text = "Powered by "
                    suffix_text = "Sufalam Technologies"
                    powered_text = prefix_text + suffix_text
                    try:
                        text_width = canvas.stringWidth(powered_text, font_name, font_size)
                        prefix_width = canvas.stringWidth(prefix_text, font_name, font_size)
                        suffix_width = canvas.stringWidth(suffix_text, font_name, font_size)
                        # Account for page margins (40px left/right margin from SimpleDocTemplate)
                        # Letter size is 612 points wide, minus margins
                        usable_width = width - 80  # 40px margin on each side
                        right_x = usable_width - text_width + 40  # Start from right margin
                        # Ensure it's within bounds
                        if right_x < width - 500:  # Make sure it's not too far left
                            right_x = width - text_width - 50
                        canvas.drawString(right_x, text_y, prefix_text)
                        suffix_x = right_x + prefix_width
                        suffix_color = colors.HexColor('#8a6cf6')
                        canvas.setFillColor(suffix_color)
                        canvas.drawString(suffix_x, text_y, suffix_text)
                        canvas.setFillColor(colors.HexColor('#14213D'))
                        canvas.linkURL(
                            "https://apps.odoo.com/apps/modules/18.0/DashBoat",
                            (suffix_x, text_y - 2, suffix_x + suffix_width, text_y + font_size),
                            relative=0,
                        )
                        _logger.info(f"Footer cover page: width={width}, text_width={text_width}, right_x={right_x}, text='{powered_text}'")
                    except Exception as e:
                        _logger.error(f"Error calculating/drawing powered_by: {e}", exc_info=True)
                        # Fallback: draw at fixed position from right edge
                        canvas.drawString(width - 280, text_y, powered_text)
                else:
                    # Other pages: match cover page footer (company left, powered-by right)
                    company_display = str(company_name) if company_name else 'Your Company'
                    canvas.drawString(40, text_y, company_display)

                    prefix_text = "Powered by "
                    suffix_text = "Sufalam Technologies"
                    powered_text = prefix_text + suffix_text
                    try:
                        text_width = canvas.stringWidth(powered_text, font_name, font_size)
                        prefix_width = canvas.stringWidth(prefix_text, font_name, font_size)
                        suffix_width = canvas.stringWidth(suffix_text, font_name, font_size)
                        usable_width = width - 80  # 40px margin on each side
                        right_x = usable_width - text_width + 40
                        if right_x < width - 500:
                            right_x = width - text_width - 50
                        canvas.drawString(right_x, text_y, prefix_text)
                        suffix_x = right_x + prefix_width
                        suffix_color = colors.HexColor('#8a6cf6')
                        canvas.setFillColor(suffix_color)
                        canvas.drawString(suffix_x, text_y, suffix_text)
                        canvas.setFillColor(colors.HexColor('#14213D'))
                        canvas.linkURL(
                            "https://apps.odoo.com/apps/modules/18.0/DashBoat",
                            (suffix_x, text_y - 2, suffix_x + suffix_width, text_y + font_size),
                            relative=0,
                        )
                    except Exception as e:
                        _logger.error(f"Error drawing powered_by on later page: {e}", exc_info=True)
                        canvas.drawString(width - 280, text_y, powered_text)
                
                canvas.restoreState()
            except Exception as e:
                _logger.error(f"Error in draw_footer: {e}", exc_info=True)

        def on_first_page(canvas, doc):
            """Set PDF metadata on first page"""
            canvas.setTitle(report_title)
            canvas.setAuthor(report_title)
            canvas.setSubject(report_title)
            # Draw download date on the top-right corner of the cover
            try:
                canvas.saveState()
                width, height = doc.pagesize
                date_text = datetime.now().strftime('%b %d, %Y')
                font_name = 'Helvetica-Bold'
                font_size = 11
                margin = 30
                canvas.setFont(font_name, font_size)
                canvas.setFillColor(colors.HexColor('#14213D'))
                text_width = canvas.stringWidth(date_text, font_name, font_size)
                x = width - margin - text_width
                y = height - 40
                canvas.drawString(x, y, date_text)
                canvas.restoreState()
            except Exception as e:
                _logger.debug(f"Could not draw cover date: {e}")
            # Draw footer and Set Creator to replace "anonymous" - use PDF metadata dictionary format
            try:
                draw_footer(canvas, doc, is_first_page=True)
                from reportlab.pdfgen.canvas import Canvas
                if hasattr(canvas, '_doc') and hasattr(canvas._doc, 'info'):
                    # Set Creator field in PDF info dictionary
                    canvas._doc.info['/Creator'] = report_title
                    canvas._doc.info['/Producer'] = report_title
            except Exception as e:
                _logger.debug(f"Could not set Creator metadata: {e}")
        
        def on_later_pages(canvas, doc):
            """Set PDF metadata on later pages"""
            canvas.setTitle(report_title)
            canvas.setAuthor(report_title)
            canvas.setSubject(report_title)
            # Draw footer and Set Creator to replace "anonymous" - use PDF metadata dictionary format
            try:
                draw_footer(canvas, doc, is_first_page=False)
                if hasattr(canvas, '_doc') and hasattr(canvas._doc, 'info'):
                    # Set Creator field in PDF info dictionary
                    canvas._doc.info['/Creator'] = report_title
                    canvas._doc.info['/Producer'] = report_title
            except Exception as e:
                _logger.debug(f"Could not set Creator metadata: {e}")
        
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=54, bottomMargin=36, leftMargin=40, rightMargin=40, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        styles = getSampleStyleSheet()
        # Ensure a Unicode font (supports ₹) is registered and used
        chosen_font = None
        try:
            font_candidates = [
                ('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                ('NirmalaUI', r'C:\Windows\Fonts\Nirmala.ttf'),
                ('SegoeUI', r'C:\Windows\Fonts\segoeui.ttf'),
                ('ArialUnicodeMS', r'C:\Windows\Fonts\arialuni.ttf'),
            ]
            for name, path in font_candidates:
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                    chosen_font = name
                    break
                except Exception:
                    continue
            if chosen_font:
                for sty_name in ['Normal', 'BodyText']:
                    if sty_name in styles:
                        styles[sty_name].fontName = chosen_font
        except Exception:
            pass
        # Create custom styles with Unicode font support for rupee symbol (₹)
        base_font = chosen_font if chosen_font else 'Helvetica'
        styles.add(ParagraphStyle(name='CoverTitle', fontSize=48, alignment=0, spaceAfter=8, leading=52, fontName='Helvetica-Bold', textColor=colors.HexColor('#14213D')))
        styles.add(ParagraphStyle(name='CoverSubTitle', fontSize=14, alignment=0, textColor=colors.HexColor('#6B7280'), spaceAfter=6, fontName=base_font))
        styles.add(ParagraphStyle(name='CoverDate', fontSize=10, alignment=0, textColor=colors.HexColor('#9AA0A6'), spaceAfter=8, fontName=base_font))
        styles.add(ParagraphStyle(name='ReportTitle', fontSize=20, alignment=1, spaceAfter=14, leading=22, fontName=base_font))
        styles.add(ParagraphStyle(name='SubTitle', fontSize=11, alignment=1, textColor='#555555', spaceAfter=10, fontName=base_font))
        styles.add(ParagraphStyle(name='SectionHeader', fontSize=18, spaceBefore=0, spaceAfter=8, leading=16, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e3a5f')))
        styles.add(ParagraphStyle(name='HL', fontSize=13, spaceBefore=10, spaceAfter=6, leading=15, underline=True, fontName=base_font))
        styles.add(ParagraphStyle(name='Small', fontSize=9, spaceAfter=6, textColor='#666666', fontName=base_font))
        styles.add(ParagraphStyle(name='DashBullet', fontSize=10, leftIndent=14, spaceBefore=2, spaceAfter=2, leading=14, fontName=base_font))

        elements = []
        # Cover page
        elements.append(Paragraph(report_title, styles['CoverTitle']))
        # subtitle removed; only display report title and date on the cover
        try:
            cover_date_text = kpis.get('date_range', '') or datetime.now().strftime('%B %Y')
        except Exception:
            cover_date_text = datetime.now().strftime('%B %Y')
        if cover_date_text:
            elements.append(Paragraph(cover_date_text, styles['CoverDate']))
        
        # Add spacing before golden line on cover page
        elements.append(Spacer(1, 480))
        
        # Keep cover clean; footer will render the branded line
        elements.append(PageBreak())
        
        # Key Performance Indicators section with exact styling from reference
        from reportlab.platypus import KeepTogether
        
        # Title with exact font and color
        kpi_title_style = ParagraphStyle(
            'KPITitle',
            parent=styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#1e3a5f'),  # Dark blue
            fontName='Helvetica-Bold',
            spaceAfter=4,
            leading=24
        )
        kpi_title = Paragraph('Key Performance Indicators', kpi_title_style)
        elements.append(kpi_title)
        
        # Golden line below title
        try:
            elements.append(HRFlowable(width="92%", hAlign="LEFT", color="#F0B430", thickness=2.5, spaceBefore=2, spaceAfter=20))
        except Exception:
            pass
        
        currency_symbol = self._get_currency_symbol()
        
        # Create KPI boxes with exact styling
        try:
            # Define KPI label and value styles
            kpi_label_style = ParagraphStyle(
                'KPILabel',
                parent=styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#9ca3af'),  # Light gray
                fontName=base_font,
                spaceAfter=4
            )
            
            kpi_value_style = ParagraphStyle(
                'KPIValue',
                parent=styles['Normal'],
                fontSize=36,
                textColor=colors.HexColor('#1e3a5f'),  # Dark blue
                fontName=base_font,  # Use Unicode font for currency symbol support
                leading=32
            )
            
            if crm_context:
                # CRM KPIs - 4 boxes in 2x2 grid
                kpi_data = [
                    [
                        [Paragraph('Total Leads', kpi_label_style), Paragraph(kpis.get('kpi_total_leads','0'), kpi_value_style)],
                        [Paragraph('Total Opportunities', kpi_label_style), Paragraph(kpis.get('kpi_total_opps','0'), kpi_value_style)]
                    ],
                    [
                        [Paragraph('Conversion Rate', kpi_label_style), Paragraph(kpis.get('conversion_rate_kpi','0%'), kpi_value_style)],
                        [Paragraph('Won Revenue', kpi_label_style), Paragraph(kpis.get('revenue_target_label', f'{currency_symbol}0'), kpi_value_style)]
                    ]
                ]
                # Flatten nested structure for Table (with spacer column for 0.2 cm gap)
                kpi_table_data = []
                for ridx, row in enumerate(kpi_data):
                    table_row = []
                    for idx, cell in enumerate(row):
                        # Create a mini-table for each cell to stack label and value
                        cell_content = Table([[c] for c in cell], colWidths=[220])
                        cell_content.setStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 0),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                            ('TOPPADDING', (0, 0), (-1, -1), 0),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                        ])
                        table_row.append(cell_content)
                        # Insert spacer after each cell except the last to create a 0.2 cm gap
                        if idx < len(row) - 1:
                            table_row.append(Spacer(0.2 * cm, 1))
                    kpi_table_data.append(table_row)
                    # Insert spacer row between KPI rows (0.5 cm tall) with matching column count
                    if ridx < len(kpi_data) - 1:
                        kpi_table_data.append([
                            Spacer(1, 0.5 * cm),
                            Spacer(0.2 * cm, 0.5 * cm),
                            Spacer(1, 0.5 * cm),
                        ])
            else:
                # Sales KPIs - 2 boxes in 1x2 grid
                kpi_data = [
                    [
                        [Paragraph('Total Sales', kpi_label_style), Paragraph(kpis.get('total_sales', f'{currency_symbol}0.00'), kpi_value_style)],
                        [Paragraph('Avg. Deal Size', kpi_label_style), Paragraph(kpis.get('avg_deal_size', f'{currency_symbol}0.00'), kpi_value_style)]
                    ]
                ]
                # Flatten for Table (with spacer column for 0.2 cm gap)
                kpi_table_data = []
                for ridx, row in enumerate(kpi_data):
                    table_row = []
                    for idx, cell in enumerate(row):
                        cell_content = Table([[c] for c in cell], colWidths=[220])
                        cell_content.setStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 0),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                            ('TOPPADDING', (0, 0), (-1, -1), 0),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                        ])
                        table_row.append(cell_content)
                        if idx < len(row) - 1:
                            table_row.append(Spacer(0.2 * cm, 1))
                    kpi_table_data.append(table_row)
            
            # Create main KPI table with curved bracket effect (and 0.2 cm gap column)
            kpi_table = Table(kpi_table_data, colWidths=[250, 0.2 * cm, 250])
            kpi_table.setStyle([
                # Backgrounds only on KPI columns
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f9fafb')),
                ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f9fafb')),
                # Alignment
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (2, 0), (2, -1), 'LEFT'),
                ('VALIGN', (0, 0), (0, -1), 'TOP'),
                ('VALIGN', (2, 0), (2, -1), 'TOP'),
                # Padding for KPI columns
                ('LEFTPADDING', (0, 0), (0, -1), 25),
                ('RIGHTPADDING', (0, 0), (0, -1), 25),
                ('TOPPADDING', (0, 0), (0, -1), 20),
                ('BOTTOMPADDING', (0, 0), (0, -1), 20),
                ('LEFTPADDING', (2, 0), (2, -1), 25),
                ('RIGHTPADDING', (2, 0), (2, -1), 25),
                ('TOPPADDING', (2, 0), (2, -1), 20),
                ('BOTTOMPADDING', (2, 0), (2, -1), 20),
                # No padding for spacer column
                ('LEFTPADDING', (1, 0), (1, -1), 0),
                ('RIGHTPADDING', (1, 0), (1, -1), 0),
                ('TOPPADDING', (1, 0), (1, -1), 0),
                ('BOTTOMPADDING', (1, 0), (1, -1), 0),
                # Boxes per KPI column
                ('BOX', (0, 0), (0, -1), 1.5, colors.HexColor('#1e3a5f')),
                ('BOX', (2, 0), (2, -1), 1.5, colors.HexColor('#1e3a5f')),
                # Horizontal divider between rows (for CRM 2x2 grid) applied per KPI column
                ('LINEBELOW', (0, 0), (0, 0), 1, colors.HexColor('#e5e7eb')) if crm_context else ('LINEBELOW', (0, 0), (0, 0), 0, colors.white),
                ('LINEBELOW', (2, 0), (2, 0), 1, colors.HexColor('#e5e7eb')) if crm_context else ('LINEBELOW', (2, 0), (2, 0), 0, colors.white),
                # Thick left border for curved bracket effect (per KPI column)
                ('LINEBEFORE', (0, 0), (0, -1), 4, colors.HexColor('#1e3a5f')),
                ('LINEBEFORE', (2, 0), (2, -1), 4, colors.HexColor('#1e3a5f')),
            ])
            elements.append(kpi_table)
            elements.append(Spacer(1, 25))
        except Exception as e:
            _logger.error(f"Error creating KPI boxes: {e}")
            # Fallback to simple paragraphs if Table styling fails in some environments
            overview_lines = []
            if crm_context:
                overview_lines.append(f"Total Leads: {kpis.get('kpi_total_leads','0')}")
                overview_lines.append(f"Total Opportunities: {kpis.get('kpi_total_opps','0')}")
                overview_lines.append(f"Conversion Rate: {kpis.get('conversion_rate_kpi','0%')}")
                currency_symbol = self._get_currency_symbol()
                overview_lines.append(f"Won Revenue: {kpis.get('revenue_target_label', f'{currency_symbol}0')}")
            else:
                currency_symbol = self._get_currency_symbol()
                overview_lines.append(f"Total Sales: {kpis.get('total_sales', f'{currency_symbol}0.00')}")
                overview_lines.append(f"Avg. Deal Size: {kpis.get('avg_deal_size', f'{currency_symbol}0.00')}")
            for ln in overview_lines:
                elements.append(Paragraph(ln, styles['BodyText']))

        # Generate insights and charts in parallel with a max of 3 workers (3-3 parallel)
        insights_data = {}
        chart_buffers = {}
        
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            date_range_text = kpis.get('date_range', '')
            def process_series(s):
                title = s.get('title') or s.get('key') or 'Chart'
                desc = s.get('description') or ''
                labels = list(s.get('labels') or [])[:12]
                values = list(s.get('values') or [])[:12]
                chart_data = {
                    'title': title,
                    'description': desc,
                    'labels': labels,
                    'values': values,
                }
                insight_html = self.get_cached_insights(title, chart_data, date_range_text, crm_context=crm_context)
                buf = self._matplotlib_bar(labels, values, title)
                return title, insight_html, buf
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(process_series, s): s for s in series}
                for f in as_completed(futures):
                    try:
                        title, insight_html, buf = f.result()
                        insights_data[title] = insight_html
                        chart_buffers[title] = buf
                    except Exception as e:
                        s = futures[f]
                        _logger.error(f"Parallel generation failed for {s.get('key')}: {e}")
                        title = s.get('title') or s.get('key') or 'Chart'
                        insights_data[title] = ""
                        chart_buffers[title] = None
        except Exception as e:
            _logger.error(f"Parallel section failed, falling back to sequential: {e}")
            for s in series:
                try:
                    title = s.get('title') or s.get('key') or 'Chart'
                    desc = s.get('description') or ''
                    labels = list(s.get('labels') or [])[:12]
                    values = list(s.get('values') or [])[:12]
                    chart_data = {
                        'title': title,
                        'description': desc,
                        'labels': labels,
                        'values': values,
                    }
                    insights_data[title] = self.get_cached_insights(title, chart_data, kpis.get('date_range',''), crm_context=crm_context)
                    chart_buffers[title] = self._matplotlib_bar(labels, values, title)
                except Exception as e2:
                    _logger.error(f"Sequential fallback failed for {s.get('key')}: {e2}")
                    insights_data[title] = ""
                    chart_buffers[title] = None

        # Per-chart sections
        for idx, s in enumerate(series, 1):
            # TASK 3: Add page break before each chart (including first)
            if idx >= 1:
                elements.append(PageBreak())
            elements.append(Paragraph(s['title'], styles['SectionHeader']))
            # Add golden line below chart title (same as KPI section)
            try:
                elements.append(HRFlowable(width="92%", hAlign="LEFT", color="#F0B430", thickness=2.5, spaceBefore=2, spaceAfter=12))
            except Exception:
                pass
            # Chart image
            buf = self._matplotlib_bar(s['labels'][:12], s['values'][:12], s['title'])
            if buf:
                img = Image(buf, width=450, height=260, kind='direct')
                img.hAlign = 'CENTER'
                elements.append(img)
            # Use cached insights from the same method as AI Analysis button
            insight_html = insights_data.get(s['title'], '')
            if insight_html:
                tmp = insight_html or ''
                tmp = re.sub(r'<h4[^>]*>.*?Key\s*Insights.*?</h4>', '\n__KEY__\n', tmp, flags=re.IGNORECASE|re.DOTALL)
                tmp = re.sub(r'<h4[^>]*>.*?Strengths\s*&\s*Opportunities.*?</h4>', '\n__PRO__\n', tmp, flags=re.IGNORECASE|re.DOTALL)
                tmp = re.sub(r'<h4[^>]*>.*?Areas\s*for\s*Improvement.*?</h4>', '\n__CON__\n', tmp, flags=re.IGNORECASE|re.DOTALL)
                plain = re.sub(r'<[^>]+>', '', tmp)
                lines = [ln.strip() for ln in plain.split('\n')]
                sections = {'Key Insights': [], 'Strengths & Opportunities': [], 'Areas for Improvement': []}
                current = None
                for ln in lines:
                    if ln == '__KEY__':
                        current = 'Key Insights'
                        continue
                    if ln == '__PRO__':
                        current = 'Strengths & Opportunities'
                        continue
                    if ln == '__CON__':
                        current = 'Areas for Improvement'
                        continue
                    if not ln:
                        continue
                    if current:
                        # Split long lines by sentence-ending punctuation to create separate bullet points
                        cleaned = ln.lstrip('- ').strip()
                        if not cleaned:
                            continue
                        # Use helper function to split sentences
                        sentences = self._split_insight_sentences(cleaned)
                        for sent in sentences:
                            sent_clean = self._clean_trailing_marker(sent)
                            if sent_clean:
                                sections[current].append(sent_clean)
                if sections['Key Insights']:
                    elements.append(Paragraph('Key Insights', styles['HL']))
                    items = [ListItem(Paragraph(b, styles['DashBullet'])) for b in sections['Key Insights'][:10]]
                    elements.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=10))
                if sections['Strengths & Opportunities']:
                    elements.append(Paragraph('Strengths & Opportunities', styles['HL']))
                    items = [ListItem(Paragraph(b, styles['DashBullet'])) for b in sections['Strengths & Opportunities'][:10]]
                    elements.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=10))
                if sections['Areas for Improvement']:
                    elements.append(Paragraph('Areas for Improvement', styles['HL']))
                    items = [ListItem(Paragraph(b, styles['DashBullet'])) for b in sections['Areas for Improvement'][:10]]
                    elements.append(ListFlowable(items, bulletType='bullet', start='•', leftIndent=10))

        try:
            doc.build(elements, onFirstPage=on_first_page, onLaterPages=on_later_pages)
        except Exception as e:
            _logger.error(f"Error building dashboard PDF: {str(e)}")
            raise UserError(f"Failed to generate dashboard PDF: {str(e)}")
        buffer.seek(0)
        # Update PDF metadata to replace "anonymous"
        buffer = self._update_pdf_metadata(buffer, report_title)
        return buffer

    @api.model
    def get_crm_dashboard_data(self, date_filter='6months', year_filter=None, date_from=None, date_to=None):
        """Build CRM KPIs and charts from crm.lead real data within the selected date range."""
        _logger.info(f"Fetching CRM dashboard data for {date_filter}/{year_filter}")
        data = {}

        date_from, date_to = self._get_date_range(date_filter, year_filter, date_from, date_to)
        data['date_range'] = f"{date_from.strftime('%b %d, %Y')} - {date_to.strftime('%b %d, %Y')}"

        Lead = self.env['crm.lead']
        Stage = self.env['crm.stage']

        leads = Lead.search([('create_date', '>=', fields.Datetime.to_datetime(date_from)), ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to, datetime.max.time()))), ('type', '=', 'lead')])
        opportunities = Lead.search([('create_date', '>=', fields.Datetime.to_datetime(date_from)), ('create_date', '<=', fields.Datetime.to_datetime(datetime.combine(date_to, datetime.max.time()))), ('type', '=', 'opportunity')])

        total_leads = len(leads)
        total_opps = len(opportunities)

        # Conversion: won opportunities / total opportunities
        won_stage_ids = Stage.search([('is_won', '=', True)]).ids
        won_opps = opportunities.filtered(lambda l: l.stage_id and l.stage_id.id in won_stage_ids)
        conversion_rate = 0.0 if total_opps == 0 else (len(won_opps) / total_opps) * 100.0

        data['kpi_total_leads'] = f"{total_leads:,}"
        data['kpi_total_opps'] = f"{total_opps:,}"
        # Provide both a compact KPI value and the donut chart (template can choose either)
        data['conversion_rate_kpi'] = f"{conversion_rate:.0f}%"
        # Small donut chart for KPI box
        data['conversion_rate_chart'] = self._generate_donut_chart(
            len(won_opps), total_opps or 1, 'Won', 'crm-conversion-rate',
            color="#28a745", width=90, height=90, hole_size=0.7
        )

        # Revenue vs Target KPI (based on won expected revenue)
        actual_revenue = sum(float(o.expected_revenue or 0.0) for o in won_opps)
        icp = self.env['ir.config_parameter'].sudo()
        try:
            target_revenue = float(icp.get_param('dashboat.crm_target_amount', '100000') or 100000)
        except Exception:
            target_revenue = 100000.0

        currency_symbol = self._get_currency_symbol()
        data['revenue_target_label'] = self._format_currency(actual_revenue, decimal_places=0)  # Show only revenue
        data['revenue_target_pct'] = 0  # Remove or set to 0 if not needed

        # Pipeline funnel by stage (count and value)
        stage_counts = {}
        stage_values = {}
        for opp in opportunities:
            stage_name = opp.stage_id.name or 'Undefined'
            stage_counts[stage_name] = stage_counts.get(stage_name, 0) + 1
            stage_values[stage_name] = stage_values.get(stage_name, 0.0) + float(opp.expected_revenue or 0.0)
        # Sort stages by CRM stage sequence for a natural funnel order
        stage_records = Stage.search([], order='sequence asc')
        stages_sorted = [rec.name or 'Undefined' for rec in stage_records if (rec.name or 'Undefined') in stage_counts]
        if not stages_sorted:
            stages_sorted = list(stage_counts.keys())
        values_sorted = [stage_counts[s] for s in stages_sorted]
        data['pipeline_funnel_chart'] = self._generate_pipeline_funnel_chart(stages_sorted, values_sorted)

        # Sales performance by salesperson (expected revenue)
        sp_amounts = {}
        for opp in opportunities:
            sp_name = opp.user_id.name or 'Unassigned'
            sp_amounts[sp_name] = sp_amounts.get(sp_name, 0.0) + float(opp.expected_revenue or 0.0)
        sp_sorted = sorted(sp_amounts.items(), key=lambda item: item[1], reverse=True)[:10]
        if sp_sorted:
            labels, vals = zip(*sp_sorted)
            data['sales_perf_chart'] = self._generate_horizontal_bar(list(labels), list(vals), 'Expected Revenue', 'Salesperson', 'crm-sales-perf', color="#4e79a7")
        else:
            data['sales_perf_chart'] = '<div style="text-align:center;padding:40px;">No data available</div>'

        # Stage distribution stacked by month (count only simplified as vertical bar of latest months)
        # Build month buckets between date_from and date_to
        month_cursor = date_from.replace(day=1)
        month_labels = []
        avg_deal_values = []
        won_revenue_values = []
        leads_month_counts = []
        opps_month_counts = []
        # Initialize per-stage monthly series dict
        stage_records_all = Stage.search([], order='sequence asc')
        stage_names_ordered = [rec.name or 'Undefined' for rec in stage_records_all]
        stage_month_series = {name: [] for name in stage_names_ordered}
        while month_cursor <= date_to:
            next_month = (month_cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
            month_end = next_month - timedelta(days=1)
            month_name = month_cursor.strftime('%b %Y')
            month_labels.append(month_name)
            month_opps = opportunities.filtered(lambda l: l.create_date.date() >= month_cursor and l.create_date.date() <= month_end)
            month_leads = leads.filtered(lambda l: l.create_date.date() >= month_cursor and l.create_date.date() <= month_end)
            if month_opps:
                avg_deal = float(sum(o.expected_revenue or 0.0 for o in month_opps)) / len(month_opps)
            else:
                avg_deal = 0.0
            avg_deal_values.append(avg_deal)

            month_won = month_opps.filtered(lambda l: l.stage_id and l.stage_id.id in won_stage_ids)
            won_revenue_values.append(sum(float(o.expected_revenue or 0.0) for o in month_won))
            leads_month_counts.append(len(month_leads))
            opps_month_counts.append(len(month_opps))
            # Per-stage counts for this month
            stage_counts_this_month = {}
            for opp in month_opps:
                sname = opp.stage_id.name or 'Undefined'
                stage_counts_this_month[sname] = stage_counts_this_month.get(sname, 0) + 1
            for sname in stage_month_series.keys():
                stage_month_series[sname].append(stage_counts_this_month.get(sname, 0))
            month_cursor = next_month

        data['avg_deal_size_trend_chart'] = self._generate_line(month_labels, avg_deal_values, 'Month', 'Avg Expected Revenue', 'crm-avg-deal-trend', is_money=True)
        data['won_revenue_trend_chart'] = self._generate_line(month_labels, won_revenue_values, 'Month', 'Won Expected Revenue', 'crm-won-revenue-trend', is_money=True)

        # Stacked bar chart for stage distribution over months (only keep stages that appear)
        non_empty_stage_series = {s: series for s, series in stage_month_series.items() if any(v > 0 for v in series)}
        # Optionally limit to top 5 stages by total count
        sorted_stages = sorted(non_empty_stage_series.items(), key=lambda kv: sum(kv[1]), reverse=True)[:6]
        limited_series = dict(sorted_stages)
        data['stage_distribution_chart'] = self._generate_stage_distribution_stacked(month_labels, limited_series, 'crm-stage-distribution')

        # Tiny sparklines for KPI boxes
        data['leads_sparkline'] = self._generate_sparkline(month_labels, leads_month_counts, 'crm-leads-spark', color="#007bff")
        data['opps_sparkline'] = self._generate_sparkline(month_labels, opps_month_counts, 'crm-opps-spark', color="#17a2b8")

        # Lead Source effectiveness (UTM Source/Medium if available)
        # This logic now correctly uses the date-filtered 'leads' and 'opportunities' recordsets
        source_counts = {}
        for l in leads | opportunities:
            src = (getattr(l, 'source_id', False) and l.source_id.name) or \
                  (getattr(l, 'medium_id', False) and l.medium_id.name) or \
                  'Unknown'
            source_counts[src] = source_counts.get(src, 0) + 1
        
        if source_counts:
            # Sort by count and take top 8
            sorted_sources = sorted(source_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]
            labels, vals = zip(*sorted_sources)
            data['lead_source_chart'] = self._generate_pie(list(labels), list(vals), 'crm-lead-source', hole=0.35)
        else:
            data['lead_source_chart'] = '<div style="text-align:center;padding:40px;">No data available</div>'

        # Revenue Forecast by Month (Stacked by Stage)
        revenue_forecast = {}
        for opp in (leads | opportunities).filtered(lambda l: l.probability > 0 and l.expected_revenue > 0):
            create_date = fields.Datetime.from_string(opp.create_date).date() if opp.create_date else fields.Date.today()
            month_year = create_date.strftime('%Y-%m')
            stage_name = opp.stage_id.name or 'New'
            
            if month_year not in revenue_forecast:
                revenue_forecast[month_year] = {}
            
            # Calculate weighted revenue (expected_revenue * probability)
            weighted_revenue = opp.expected_revenue * (opp.probability / 100.0)
            revenue_forecast[month_year][stage_name] = revenue_forecast[month_year].get(stage_name, 0) + weighted_revenue
        
        # Prepare data for stacked bar chart
        if revenue_forecast:
            # Get all unique stages across all months
            all_stages = sorted(list(set(stage for month_data in revenue_forecast.values() for stage in month_data.keys())))
            months = sorted(revenue_forecast.keys())
            
            # Prepare series data for each stage
            series_data = []
            for stage in all_stages:
                stage_data = []
                for month in months:
                    stage_data.append(round(revenue_forecast[month].get(stage, 0), 2))
                series_data.append({
                    'name': stage,
                    'data': stage_data,
                    'stack': 'revenue'
                })
            
            # Generate revenue forecast chart
            data['revenue_forecast_chart'] = self._generate_stacked_bar_chart(
                categories=months,
                series=series_data,
                title='Weighted Revenue Forecast by Stage',
                y_axis_title='Revenue',
                height=400,
                chart_id='revenue-forecast-stacked'
            )
            
            # Add lost reason analysis chart
            data['lost_reason_chart'] = self._generate_lost_reason_chart()
        else:
            data['revenue_forecast_chart'] = '<div style="text-align:center;padding:40px;">No revenue forecast data available</div>'

        # Geographical insights (by country)
        geo_counts = {}
        for rec in leads | opportunities:
            country = (rec.country_id and rec.country_id.name) or (rec.partner_id and rec.partner_id.country_id and rec.partner_id.country_id.name) or 'Unknown'
            geo_counts[country] = geo_counts.get(country, 0) + 1
        geo_sorted = sorted(geo_counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
        if geo_sorted:
            glabels, gvals = zip(*geo_sorted)
            data['geo_insights_chart'] = self._generate_geo_bubble_chart(list(glabels), list(gvals), 'crm-geo-insights')
        else:
            data['geo_insights_chart'] = '<div style="text-align:center;padding:40px;">No data available</div>'

        # Activities Due/Overdue heatmap across date range
        Activity = self.env['mail.activity']
        acts = Activity.search([
            ('res_model', '=', 'crm.lead'),
            ('date_deadline', '>=', date_from),
            ('date_deadline', '<=', date_to),
        ])
        # Build per-day arrays
        day_cursor = date_from
        day_labels = []
        index_by_date = {}
        i = 0
        while day_cursor <= date_to:
            day_labels.append(day_cursor.strftime('%d %b'))
            index_by_date[str(day_cursor)] = i
            i += 1
            day_cursor += timedelta(days=1)
        due_counts = [0] * len(day_labels)
        overdue_counts = [0] * len(day_labels)
        today = fields.Date.today()
        for a in acts:
            dd = a.date_deadline
            if not dd:
                continue
            key = str(dd)
            if key not in index_by_date:
                continue
            idx = index_by_date[key]
            if dd < today:
                overdue_counts[idx] += 1
            else:
                due_counts[idx] += 1
        data['activities_heatmap'] = self._generate_due_overdue_heatmap(day_labels, due_counts, overdue_counts)

        _logger.info("Interactive CRM dashboard data generated successfully")
        return data

    def _get_date_range(self, date_filter, year_filter=None, date_from=None, date_to=None):
        today = fields.Date.today()
        
        if date_filter == 'custom' and date_from and date_to:
            return date_from, date_to
        elif date_filter == 'year' and year_filter:
            year_start = datetime.strptime(f'{year_filter}-01-01', '%Y-%m-%d').date()
            year_end = datetime.strptime(f'{year_filter}-12-31', '%Y-%m-%d').date()
            return year_start, year_end
        elif date_filter == 'today':
            return today, today
        elif date_filter == 'yesterday':
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif date_filter == '7days':
            return today - timedelta(days=7), today
        elif date_filter == '30days':
            return today - timedelta(days=30), today
        elif date_filter == '90days':
            return today - timedelta(days=90), today
        else:  # Default to 6 months
            return today - timedelta(days=180), today

    @api.model
    def get_dashboard_data(self, date_filter='6months', year_filter=None, date_from=None, date_to=None):
        _logger.info(f"Fetching dashboard data for {date_filter}/{year_filter}")
        data = {}
        
        date_from, date_to = self._get_date_range(date_filter, year_filter, date_from, date_to)
        data['date_range'] = f"{date_from.strftime('%b %d, %Y')} - {date_to.strftime('%b %d, %Y')}"

        total_sales_amount = self.env['sale.order'].search([
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to)
        ]).mapped('amount_total')
        currency_symbol = self._get_currency_symbol()
        data['total_sales'] = self._format_currency(sum(total_sales_amount)) if total_sales_amount else f"{currency_symbol}0.00"

        if total_sales_amount:
            data['avg_deal_size'] = self._format_currency(sum(total_sales_amount) / len(total_sales_amount))
        else:
            data['avg_deal_size'] = f"{currency_symbol}0.00"

        sales_performance_raw = {}
        current_date = date_from
        while current_date <= date_to:
            month_start = current_date.replace(day=1)
            next_month = month_start.replace(day=28) + timedelta(days=4)
            month_end = next_month - timedelta(days=next_month.day)

            if month_end > date_to:
                month_end = date_to
                
            sales_in_month = self.env['sale.order'].search([
                ('state', 'in', ['sale', 'done']),
                ('date_order', '>=', month_start),
                ('date_order', '<=', month_end)
            ])
            
            month_name = month_start.strftime('%b %Y')
            sales_performance_raw[month_name] = sum(sales_in_month.mapped('amount_total'))
            
            current_date = month_end + timedelta(days=1)
            
        data['sales_performance_chart'] = self._generate_sales_performance_chart(sales_performance_raw)

        sales_by_product_raw = {}
        order_lines = self.env['sale.order.line'].search([
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.date_order', '>=', date_from),
            ('order_id.date_order', '<=', date_to)
        ])
        for line in order_lines:
            product_name = line.product_id.name
            sales_by_product_raw[product_name] = sales_by_product_raw.get(product_name, 0.0) + float(line.product_uom_qty or 0.0)
        sorted_products = sorted(sales_by_product_raw.items(), key=lambda item: item[1], reverse=True)[:5]
        data['sales_by_product_chart'] = self._generate_sales_by_product_chart(dict(sorted_products))

        salesperson_leaderboard_raw = {}
        sales_orders = self.env['sale.order'].search([
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to)
        ])
        for order in sales_orders:
            if order.user_id:
                salesperson_name = order.user_id.name
                salesperson_leaderboard_raw[salesperson_name] = salesperson_leaderboard_raw.get(salesperson_name, 0.0) + order.amount_total
        sorted_salespersons = sorted(salesperson_leaderboard_raw.items(), key=lambda item: item[1], reverse=True)[:5]
        data['salesperson_leaderboard'] = [{
            "name": sp, 
            "amount": self._format_currency(float(amt) if amt is not None else 0.0)
        } for sp, amt in sorted_salespersons]

        sales_by_region_raw = {}
        sale_orders_with_partner_country = self.env['sale.order'].search([
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
            ('partner_id.country_id', '!=', False)
        ])
        for order in sale_orders_with_partner_country:
            country_name = order.partner_id.country_id.name
            sales_by_region_raw[country_name] = sales_by_region_raw.get(country_name, 0.0) + order.amount_total
        data['sales_by_region_chart'] = self._generate_sales_by_region_chart(sales_by_region_raw)

        top_customers_raw = {}
        customer_orders = self.env['sale.order'].search([
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to)
        ])
        for order in customer_orders:
            if order.partner_id:
                customer_name = order.partner_id.name
                top_customers_raw[customer_name] = top_customers_raw.get(customer_name, 0.0) + order.amount_total
        sorted_customers = sorted(top_customers_raw.items(), key=lambda item: item[1], reverse=True)[:5]
        data['top_customers_chart'] = self._generate_top_customers_chart(dict(sorted_customers))

        top_salespersons_raw = {}
        for order in sales_orders:
            if order.user_id:
                salesperson_name = order.user_id.name
                top_salespersons_raw[salesperson_name] = top_salespersons_raw.get(salesperson_name, 0.0) + order.amount_total
        sorted_salespersons = sorted(top_salespersons_raw.items(), key=lambda item: item[1], reverse=True)[:5]
        data['top_salespersons_chart'] = self._generate_top_salespersons_chart(dict(sorted_salespersons))

        _logger.info("Interactive dashboard data generated successfully")
        return data

    def test_enhanced_chart_insight(self):
        """Test method to verify enhanced chart insight functionality with pros and cons."""
        try:
            # Test with sample data
            test_labels = ['Product A', 'Product B', 'Product C', 'Product D']
            test_values = [15000, 12000, 8000, 5000]
            
            # Test sales context
            sales_insight = self._build_chart_insight(
                chart_title="Top Products by Sales",
                description="Sales performance by product",
                series_labels=test_labels,
                series_values=test_values,
                date_range_text="Jan 2024 - Dec 2024",
                crm_context=False
            )
            
            # Test CRM context
            crm_insight = self._build_chart_insight(
                chart_title="Pipeline Funnel",
                description="Opportunities by stage",
                series_labels=['New', 'Qualified', 'Proposal', 'Negotiation', 'Won'],
                series_values=[100, 80, 60, 40, 25],
                date_range_text="Jan 2024 - Dec 2024",
                crm_context=True
            )
            
            _logger.info("Enhanced chart insight test completed successfully")
            _logger.info(f"Sales insight preview: {sales_insight[:200]}...")
            _logger.info(f"CRM insight preview: {crm_insight[:200]}...")
            
            return {
                'sales_insight': sales_insight,
                'crm_insight': crm_insight,
                'status': 'success'
            }
        except Exception as e:
            _logger.error(f"Enhanced chart insight test failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }