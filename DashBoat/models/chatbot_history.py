from odoo import models, fields, api
from odoo.tools import html_sanitize  # For safely handling HTML

class ChatbotHistory(models.Model):
    _name = 'chatbot.history'
    _description = 'Chatbot History'

    engine_id = fields.Many2one('predictive.engine', string="DashBoat")
    query = fields.Text(string="Query")
    sql_query = fields.Text(string="SQL Query")
    result_data = fields.Html(string="Result Data")
    charts = fields.Many2many('ir.attachment', string='Charts')
    charts_html = fields.Html(string="Charts HTML")
    insights = fields.Html(string="Insights")  # Changed from Text to Html

    # ChatGPT-style chat fields
    is_user = fields.Boolean(string="Is User Message", default=True)
    message = fields.Text(string="Message")  # User message
    response = fields.Text(string="Response")  # Bot response
    display_text = fields.Html(string="Display Text", compute='_compute_display_text', store=True)
    # Update the user_message_id field to be optional
    user_message_id = fields.Many2one(
        'chatbot.history', 
        string='User Message', 
        domain="[('is_user','=',True)]", 
        help="The user message this bot answer is responding to.",
        ondelete='cascade'
    )
    bot_insights = fields.Html(string="Insights", compute="_compute_bot_insights", store=False)  # Changed to Html

    @api.depends('is_user', 'message', 'response', 'sql_query', 'result_data', 'insights', 'charts_html', 'create_date')
    def _compute_display_text(self):
        for rec in self:
            if rec.is_user:
                rec.display_text = f'<div class="chat-bubble-user">{rec.message or ""}</div>'
            else:
                # Show SQL, result, insights, charts for bot
                sql_html = f'<div style="margin-bottom:8px;"><b>SQL Query:</b><br><code style="background:#f5f5f5;padding:4px 8px;border-radius:4px;">{rec.sql_query or "-"}</code></div>' if rec.sql_query else ''
                result_html = f'<div style="margin-bottom:8px;"><b>Result:</b><br>{rec.result_data or "-"}</div>' if rec.result_data else ''
                # Use html_sanitize to safely render insights as HTML
                insights_html = f'<div style="margin-bottom:8px;"><b>Insights:</b><br>{html_sanitize(rec.insights) if rec.insights else "-"}</div>' if rec.insights else ''
                charts_html = f'<div style="margin-bottom:8px;"><b>Charts:</b><br>{rec.charts_html or "-"}</div>' if rec.charts_html else ''
                rec.display_text = (
                    '<div class="chat-bubble-bot">'
                    f'{sql_html}{result_html}{insights_html}{charts_html}'
                    '</div>'
                )

    @api.depends('is_user')
    def _compute_bot_insights(self):
        for rec in self:
            if rec.is_user:
                bot_answer = self.env['chatbot.history'].search([
                    ('user_message_id', '=', rec.id),
                    ('is_user', '=', False)
                ], limit=1)
                rec.bot_insights = bot_answer.insights if bot_answer else ''
            else:
                rec.bot_insights = rec.insights or ''