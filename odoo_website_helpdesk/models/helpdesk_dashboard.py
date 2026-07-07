# filename: models/helpdesk_dashboard.py
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HelpdeskDashboard(models.TransientModel):
    _name = 'helpdesk.dashboard'
    _description = 'Helpdesk Management Dashboard'

    # Interactive Selectors
    team_id = fields.Many2one('team.helpdesk', string='Support Team')
    ticket_id = fields.Many2one('ticket.helpdesk', string='Select Ticket',
                                domain="[('team_id', '=', team_id)]" if team_id else [])

    # KPIs
    kpi_total_tickets = fields.Integer(string="Total Tickets")
    kpi_open_tickets = fields.Integer(string="Open Tickets")
    kpi_solved_tickets = fields.Integer(string="Solved Tickets")
    kpi_avg_rating = fields.Float(string="Avg Customer Rating")

    # Dynamic UI Elements
    explorer_html = fields.Html(string='Explorer Content')

    @api.onchange('team_id')
    def _onchange_team(self):
        self.ticket_id = False
        self._compute_explorer_data()

    @api.onchange('ticket_id')
    def _onchange_ticket(self):
        self._compute_explorer_data()

    def _compute_explorer_data(self):
        domain = []
        if self.team_id:
            domain.append(('team_id', '=', self.team_id.id))

        tickets = self.env['ticket.helpdesk'].search(domain)

        # Calculate KPIs
        self.kpi_total_tickets = len(tickets)

        # Heuristic for solved (assuming stage_id name contains these keywords)
        solved = tickets.filtered(lambda t: t.stage_id and t.stage_id.name.lower() in ['solved', 'closed', 'done'])
        open_t = tickets - solved

        self.kpi_solved_tickets = len(solved)
        self.kpi_open_tickets = len(open_t)

        # SAFELY Calculate Average Rating (checks if the 'rating' field actually exists)
        if 'rating' in self.env['ticket.helpdesk']._fields:
            rated = tickets.filtered(lambda t: getattr(t, 'rating') and str(getattr(t, 'rating')).isdigit() and int(
                getattr(t, 'rating')) > 0)
            self.kpi_avg_rating = (sum(int(getattr(t, 'rating')) for t in rated) / len(rated)) if rated else 0.0
        else:
            self.kpi_avg_rating = 0.0

        # Build Premium HTML Explorer
        html_output = ""

        if not self.team_id and not self.ticket_id:
            self.explorer_html = "<div style='text-align:center; padding: 50px; color: #94a3b8;'><i class='fa fa-life-ring fa-4x mb-3'></i><h2>Select a Support Team to begin.</h2></div>"
            return

        # SCENARIO 1: A specific TICKET is selected
        if self.ticket_id:
            t = self.ticket_id

            # Map Priority to colors safely
            p_val = getattr(t, 'priority', '2')
            p_map = {'0': 'Very Low', '1': 'Low', '2': 'Normal', '3': 'High', '4': 'Very High'}
            p_text = p_map.get(str(p_val), 'Normal')
            p_color = '#3b82f6' if str(p_val) in ['0', '1'] else '#10b981' if str(p_val) == '2' else '#f59e0b' if str(
                p_val) == '3' else '#ef4444'

            # Safe data extraction
            cust_name = t.customer_id.name if getattr(t, 'customer_id', False) else 'Unregistered Customer'
            cust_email = getattr(t.customer_id, 'email', 'No email provided') if getattr(t, 'customer_id',
                                                                                         False) else 'No email provided'
            cust_phone = getattr(t.customer_id, 'phone', 'No phone provided') if getattr(t, 'customer_id',
                                                                                         False) else 'No phone provided'

            tasks = len(t.task_ids) if hasattr(t, 'task_ids') else 0
            invs = len(t.invoice_ids) if hasattr(t, 'invoice_ids') else 0
            prods = len(t.product_ids) if hasattr(t, 'product_ids') else 0

            html_output += f"""
            <div style="background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; display: flex; gap: 30px;">
                <div style="flex: 1.5; border-right: 2px dashed #e2e8f0; padding-right: 30px;">
                    <div style="display:inline-block; padding: 8px 16px; background: {p_color}20; color: {p_color}; border-radius: 20px; font-weight: 800; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 15px;">Priority: {p_text}</div>
                    <h1 style="font-size: 2.2rem; font-weight: 900; color: #0f172a; margin: 0;"><i class="fa fa-ticket text-primary"></i> {getattr(t, 'subject', 'Untitled Ticket')}</h1>
                    <p style="color: #64748b; font-size: 1.1rem; font-weight: 600; margin-top: 5px;">Stage: <span style="color:#10b981;">{t.stage_id.name if getattr(t, 'stage_id', False) else 'New'}</span> • Logged: {t.create_date.strftime('%d %b %Y') if getattr(t, 'create_date', False) else 'N/A'}</p>

                    <div style="margin-top: 30px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                        <div style="background: #f8fafc; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0; text-align:center;">
                            <i class="fa fa-tasks text-info fa-2x mb-2"></i>
                            <span style="display:block; color: #0f172a; font-size: 1.8rem; font-weight: 900;">{tasks}</span>
                            <span style="display:block; color: #64748b; font-size: 0.8rem; font-weight: 700; text-transform:uppercase;">Linked Tasks</span>
                        </div>
                        <div style="background: #f8fafc; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0; text-align:center;">
                            <i class="fa fa-file-invoice-dollar text-success fa-2x mb-2"></i>
                            <span style="display:block; color: #0f172a; font-size: 1.8rem; font-weight: 900;">{invs}</span>
                            <span style="display:block; color: #64748b; font-size: 0.8rem; font-weight: 700; text-transform:uppercase;">Invoices</span>
                        </div>
                        <div style="background: #f8fafc; padding: 20px; border-radius: 16px; border: 1px solid #e2e8f0; text-align:center;">
                            <i class="fa fa-box text-warning fa-2x mb-2"></i>
                            <span style="display:block; color: #0f172a; font-size: 1.8rem; font-weight: 900;">{prods}</span>
                            <span style="display:block; color: #64748b; font-size: 0.8rem; font-weight: 700; text-transform:uppercase;">Products</span>
                        </div>
                    </div>
                </div>

                <div style="flex: 1; padding-left: 10px;">
                    <h3 style="color: #0f172a; font-weight: 800; margin-bottom: 20px;"><i class="fa fa-user-circle text-purple mr-2" style="color:#8b5cf6;"></i> Customer Profile</h3>
                    <div style="display: flex; flex-direction: column; gap: 15px;">
                        <div style="background: #f1f5f9; padding: 15px 20px; border-radius: 12px; border-left: 4px solid #8b5cf6;">
                            <small style="color:#64748b; font-weight:700; text-transform:uppercase;"><i class="fa fa-user mr-1"></i> Name</small><br/>
                            <strong style="font-size:1.1rem; color:#0f172a;">{cust_name}</strong>
                        </div>
                        <div style="background: #f1f5f9; padding: 15px 20px; border-radius: 12px; border-left: 4px solid #3b82f6;">
                            <small style="color:#64748b; font-weight:700; text-transform:uppercase;"><i class="fa fa-envelope mr-1"></i> Email</small><br/>
                            <strong style="font-size:1.1rem; color:#0f172a;">{cust_email}</strong>
                        </div>
                        <div style="background: #f1f5f9; padding: 15px 20px; border-radius: 12px; border-left: 4px solid #10b981;">
                            <small style="color:#64748b; font-weight:700; text-transform:uppercase;"><i class="fa fa-phone mr-1"></i> Phone</small><br/>
                            <strong style="font-size:1.1rem; color:#0f172a;">{cust_phone}</strong>
                        </div>
                    </div>
                </div>
            </div>
            """

        # SCENARIO 2: Viewing Team Data (No specific ticket)
        else:
            html_output += "<div style='display: grid; grid-template-columns: 1fr 1fr; gap: 20px;'>"

            # Priority Distribution Chart safely
            if 'priority' in self.env['ticket.helpdesk']._fields:
                p_high = len(tickets.filtered(lambda x: str(getattr(x, 'priority', '')) in ['3', '4']))
                p_norm = len(tickets.filtered(lambda x: str(getattr(x, 'priority', '')) == '2'))
                p_low = len(tickets.filtered(lambda x: str(getattr(x, 'priority', '')) in ['0', '1']))
            else:
                p_high = p_norm = p_low = 0

            tot_p = len(tickets) or 1

            html_output += f"""
            <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
                <h3 style="margin-top:0; font-weight: 800; color: #1e293b; margin-bottom: 25px;"><i class="fa fa-pie-chart text-primary mr-2"></i> Priority Workload</h3>
                <div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 8px; font-weight: 700; font-size: 0.85rem; color: #475569;">
                        <span><i class="fa fa-circle" style="color:#ef4444;"></i> Urgent ({p_high})</span>
                        <span><i class="fa fa-circle" style="color:#f59e0b;"></i> Normal ({p_norm})</span>
                        <span><i class="fa fa-circle" style="color:#3b82f6;"></i> Low ({p_low})</span>
                    </div>
                    <div style="height: 24px; width: 100%; background: #e2e8f0; border-radius: 12px; overflow: hidden; display: flex; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);">
                        <div style="width: {(p_high / tot_p) * 100}%; background: #ef4444; transition: 1s ease;"></div>
                        <div style="width: {(p_norm / tot_p) * 100}%; background: #f59e0b; transition: 1s ease;"></div>
                        <div style="width: {(p_low / tot_p) * 100}%; background: #3b82f6; transition: 1s ease;"></div>
                    </div>
                </div>
            </div>
            """

            # Recent Tickets Table
            recent_tickets = tickets.sorted(key=lambda r: r.create_date, reverse=True)[:5] if tickets else []
            t_html = "<div style='display:flex; flex-direction:column; gap:10px;'>"
            for rt in recent_tickets:
                is_solved = getattr(rt, 'stage_id', False) and rt.stage_id.name.lower() in ['solved', 'done', 'closed']
                s_color = '#10b981' if is_solved else '#f59e0b'

                cust_name_rt = rt.customer_id.name if getattr(rt, 'customer_id', False) else 'Unknown'
                subj_rt = getattr(rt, 'subject', 'No Subject')
                date_rt = rt.create_date.strftime('%d %b') if getattr(rt, 'create_date', False) else ''
                stage_rt = rt.stage_id.name if getattr(rt, 'stage_id', False) else 'New'

                t_html += f"""
                <div style="padding: 12px 15px; background: #f8fafc; border-radius: 10px; border: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; transition: background 0.2s;">
                    <div>
                        <strong style="color: #0f172a; display: block; font-size:0.95rem;">{subj_rt}</strong>
                        <small style="color: #64748b; font-weight:600;"><i class="fa fa-user mr-1"></i> {cust_name_rt} • {date_rt}</small>
                    </div>
                    <span style="background: {s_color}20; color: {s_color}; padding: 4px 10px; border-radius: 20px; font-size: 0.7rem; font-weight: 800; text-transform: uppercase;">{stage_rt}</span>
                </div>
                """
            t_html += "</div>"

            html_output += f"""
            <div style="background: white; border: 1px solid #e2e8f0; border-radius: 16px; padding: 25px; box-shadow: 0 4px 6px rgba(0,0,0,0.02);">
                <h3 style="margin-top:0; font-weight: 800; color: #1e293b; margin-bottom: 20px;"><i class="fa fa-inbox text-success mr-2"></i> Recent Feed</h3>
                {t_html if recent_tickets else '<p style="color:#94a3b8; font-weight:600;">No recent tickets found.</p>'}
            </div>
            </div>
            """

        self.explorer_html = html_output

    @api.model
    def action_open_dashboard(self):
        dashboard = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Helpdesk Support Dashboard',
            'res_model': 'helpdesk.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'inline',
            'flags': {'mode': 'readonly'},
        }
# # filename: models/helpdesk_dashboard.py
# from odoo import models, fields, api
#
# # Define the constants here (they were missing!)
# PRIORITIES = [
#     ('0', 'Very Low'),
#     ('1', 'Low'),
#     ('2', 'Normal'),
#     ('3', 'High'),
#     ('4', 'Very High'),
# ]
#
# RATING = [
#     ('0', 'Very Low'),
#     ('1', 'Low'),
#     ('2', 'Normal'),
#     ('3', 'High'),
#     ('4', 'Very High'),
#     ('5', 'Extreme High')
# ]
#
#
# class HelpdeskDashboard(models.Model):
#     _name = 'helpdesk.dashboard'
#     _description = 'Helpdesk Management Dashboard'
#     _rec_name = 'name'
#
#     name = fields.Char(string='Dashboard Name', default='Helpdesk Overview Dashboard', required=True)
#     last_refresh = fields.Datetime(string='Last Refresh', default=fields.Datetime.now)
#
#     # Selection fields for interactive filtering
#     team_id = fields.Many2one('team.helpdesk', string='Select Team', tracking=True)
#     ticket_id = fields.Many2one('ticket.helpdesk', string='Select Ticket',
#                                 domain="[('team_id', '=', team_id)]", tracking=True)
#
#     dashboard_html = fields.Html(
#         string='Dashboard Content',
#         compute='_compute_dashboard_html',
#         sanitize=False,
#     )
#
#     @api.depends('team_id', 'ticket_id', 'last_refresh')
#     def _compute_dashboard_html(self):
#         for record in self:
#             html_content = """
#             <div class="o_dashboard_helpdesk" style="font-family: Arial, sans-serif; padding: 20px; background: linear-gradient(to bottom, #f0f4f8, #ffffff); border-radius: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
#                 <h1 style="text-align: center; color: #4a90e2; font-size: 28px; margin-bottom: 20px;">
#                     Helpdesk Management Dashboard
#                 </h1>
#                 {summary_html}
#                 {hierarchy_html}
#             </div>
#             """.strip()
#
#             # Overall Summary
#             teams = self.env['team.helpdesk'].search([])
#             total_teams = len(teams)
#             tickets = self.env['ticket.helpdesk'].search([])
#             total_tickets = len(tickets)
#             open_tickets = len(tickets.filtered(lambda t: not t.stage_id.closing_stage and not t.stage_id.cancel_stage))
#             closed_tickets = len(tickets.filtered(lambda t: t.stage_id.closing_stage))
#             cancelled_tickets = len(tickets.filtered(lambda t: t.stage_id.cancel_stage))
#             high_priority_tickets = len(tickets.filtered(lambda t: t.priority in ['3', '4']))
#
#             summary_html = f"""
#             <div style="margin-bottom: 30px; text-align: center; background: linear-gradient(to right, #4a90e2, #50c878); color: white; padding: 15px; border-radius: 10px;">
#                 <h2 style="color: white; margin-bottom: 10px;">Overall Summary</h2>
#                 <p style="font-size: 16px;">
#                     Teams: <strong>{total_teams}</strong> |
#                     Tickets: <strong>{total_tickets}</strong>
#                     (<span style="color: #d4f4e2;">Open: {open_tickets}</span> |
#                     <span style="color: #f4d4d4;">Closed: {closed_tickets}</span> |
#                     <span style="color: #ffd4d4;">Cancelled: {cancelled_tickets}</span>) |
#                     High Priority: <strong>{high_priority_tickets}</strong>
#                 </p>
#             </div>
#             """
#
#             hierarchy_html = '<h2 style="color: #4a90e2; text-align: center; margin-top: 30px;">Helpdesk View</h2>'
#
#             if not record.team_id:
#                 # Show all teams
#                 hierarchy_html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">'
#                 for team in teams.sorted('name'):
#                     team_tickets = tickets.filtered(lambda t: t.team_id == team)
#                     team_open = len(team_tickets.filtered(lambda t: not t.stage_id.closing_stage and not t.stage_id.cancel_stage))
#                     hierarchy_html += f"""
#                     <div style="background: linear-gradient(to bottom, #ffffff, #f8f9fc); padding: 18px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center;">
#                         <strong style="font-size: 20px; color: #4a90e2;">{team.name}</strong><br>
#                         <small>Lead: {team.team_lead_id.name or '—'} • Members: {len(team.member_ids)}</small><br>
#                         <strong>Tickets: {len(team_tickets)} (Open: {team_open})</strong>
#                     </div>
#                     """
#                 hierarchy_html += '</div>'
#
#             elif not record.ticket_id:
#                 # Show tickets in selected team
#                 team_tickets = tickets.filtered(lambda t: t.team_id == record.team_id).sorted('name')
#                 hierarchy_html += f'<h3 style="text-align: center; color: #50c878;">Team: {record.team_id.name}</h3>'
#                 hierarchy_html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px;">'
#                 for ticket in team_tickets:
#                     status = 'Open'
#                     if ticket.stage_id.closing_stage:
#                         status = 'Closed'
#                     elif ticket.stage_id.cancel_stage:
#                         status = 'Cancelled'
#
#                     priority_text = dict(PRIORITIES).get(ticket.priority, 'Normal')
#                     priority_color = 'red' if ticket.priority in ['3','4'] else '#666'
#
#                     hierarchy_html += f"""
#                     <div style="background: white; padding: 18px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
#                         <strong>{ticket.name}</strong><br>
#                         <small>{ticket.subject[:60]}{'...' if len(ticket.subject or '') > 60 else ''}</small><br><br>
#                         <span style="background:#e3f2fd; padding:4px 10px; border-radius:15px; font-size:13px;">{status}</span>
#                         <span style="color:{priority_color}; margin-left:10px; font-weight:bold;">Priority: {priority_text}</span>
#                     </div>
#                     """
#                 hierarchy_html += '</div>'
#
#             else:
#                 # Detailed ticket view
#                 ticket = record.ticket_id
#                 customer = ticket.customer_id
#                 stage = ticket.stage_id.name or '—'
#                 priority_text = dict(PRIORITIES).get(ticket.priority, 'N/A')
#
#                 hierarchy_html += f'<h3 style="text-align: center; color: #e94e77;">Ticket: {ticket.name} • Team: {ticket.team_id.name}</h3>'
#                 hierarchy_html += '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px; margin-top: 20px;">'
#
#                 hierarchy_html += f"""
#                 <div style="background:white; padding:20px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
#                     <h4 style="color:#1cc88a;">Customer</h4>
#                     <p><strong>{customer.name or ticket.customer_name or '—'}</strong></p>
#                     <p>{ticket.email or customer.email or '—'}</p>
#                     <p>{ticket.phone or customer.phone or '—'}</p>
#                 </div>
#
#                 <div style="background:white; padding:20px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
#                     <h4 style="color:#f6c23e;">Ticket Info</h4>
#                     <p><strong>Subject:</strong> {ticket.subject}</p>
#                     <p><strong>Stage:</strong> {stage}</p>
#                     <p><strong>Priority:</strong> {priority_text}</p>
#                     <p><strong>Created:</strong> {ticket.create_date.strftime('%d %b %Y %H:%M') if ticket.create_date else '—'}</p>
#                 </div>
#
#                 <div style="background:white; padding:20px; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
#                     <h4 style="color:#e74a3b;">Quick Stats</h4>
#                     <p>Tasks: <strong>{len(ticket.task_ids)}</strong></p>
#                     <p>Invoices: <strong>{len(ticket.invoice_ids)}</strong></p>
#                     <p>Products: <strong>{len(ticket.product_ids)}</strong></p>
#                 </div>
#                 """
#                 hierarchy_html += '</div>'
#
#             record.dashboard_html = html_content.format(
#                 summary_html=summary_html,
#                 hierarchy_html=hierarchy_html
#             )
#
#     @api.onchange('team_id')
#     def _onchange_team_id(self):
#         self.ticket_id = False
#
#     def action_refresh_dashboard(self):
#         self.write({'last_refresh': fields.Datetime.now()})
#         return True
