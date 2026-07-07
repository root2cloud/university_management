from ast import literal_eval
from datetime import datetime
from odoo import api, fields, models
from odoo.osv import expression

class DashboardBlock(models.Model):
    """Class is used to create charts and tiles in dashboard"""
    _name = "dashboard.block"
    _description = "Dashboard Block"

    def get_default_action(self):
        """Function to get values from dashboard if action_id is true return
        id else return false"""
        action_id = self.env.ref(
            'delivery_management_system.dashboard_view_action')
        if action_id:
            return action_id.id
        return False

    name = fields.Char(string="Name", help='Name of the block')
    fa_icon = fields.Char(string="Icon", help="Add icon for tile")
    operation = fields.Selection(
        selection=[("sum", "Sum"), ("avg", "Average"), ("count", "Count")],
        string="Operation",
        help='Tile Operation that needs to bring values for tile',
        required=True)
    graph_type = fields.Selection(
        selection=[("bar", "Bar"), ("radar", "Radar"), ("pie", "Pie"),
                   ("polarArea", "polarArea"), ("line", "Line"),
                   ("doughnut", "Doughnut")],
        string="Chart Type", help='Type of Chart')
    measured_field_id = fields.Many2one("ir.model.fields",
                                        string="Measured Field",
                                        help="Select the Measured")
    client_action_id = fields.Many2one('ir.actions.client',
                                       string="Client action",
                                       default=get_default_action,
                                       help="Client action")
    type = fields.Selection(
        selection=[("graph", "Chart"), ("tile", "Tile")],
        string="Type", help='Type of Block ie, Chart or Tile')
    x_axis = fields.Char(string="X-Axis", help="Chart X-axis")
    y_axis = fields.Char(string="Y-Axis", help="Chart Y-axis")
    height = fields.Char(string="Height ", help="Height of the block", default="412px")
    width = fields.Char(string="Width", help="Width of the block", defualt="466px")
    translate_x = fields.Char(string="Translate_X",
                              help="x value for the style transform translate")
    translate_y = fields.Char(string="Translate_Y",
                              help="y value for the style transform translate")
    data_x = fields.Char(string="Data_X", help="Data x value for resize")
    data_y = fields.Char(string="Data_Y", help="Data y value for resize")
    group_by_id = fields.Many2one("ir.model.fields", store=True,
                                  string="Group by(Y-Axis)",
                                  help='Field value for Y-Axis')
    tile_color = fields.Char(string="Tile Color", help='Primary Color of Tile')
    text_color = fields.Char(string="Text Color", help='Text Color of Tile')
    val_color = fields.Char(string="Value Color", help='Value Color of Tile')
    fa_color = fields.Char(string="Icon Color", help='Icon Color of Tile')
    filter = fields.Char(string="Filter", help="Add filter")
    model_id = fields.Many2one('ir.model', string='Model',
                               help="Select the module name")
    model_name = fields.Char(related='model_id.model', string="Model Name",
                             help="Added model_id model")
    edit_mode = fields.Boolean(string="Edit Mode",
                               help="Enable to edit chart and tile",
                               default=False, invisible=True)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if self.operation or self.measured_field_id:
            self.operation = False
            self.measured_field_id = False

    def get_dashboard_vals(self, action_id, start_date=None, end_date=None):
        """Fetch block values from js and create chart"""
        block_id = []
        for rec in self.env['dashboard.block'].sudo().search(
                [('client_action_id', '=', int(action_id))]):
            if rec.filter is False:
                rec.filter = "[]"
            filter_list = literal_eval(rec.filter)
            filter_list = [filter_item for filter_item in filter_list if not (
                    isinstance(filter_item, tuple) and filter_item[
                0] == 'create_date')]
            rec.filter = repr(filter_list)
            vals = {'id': rec.id, 'name': rec.name, 'type': rec.type,
                    'graph_type': rec.graph_type, 'icon': rec.fa_icon,
                    'model_name': rec.model_name,
                    'color': f'background-color: {rec.tile_color};' if rec.tile_color else '#1f6abb;',
                    'text_color': f'color: {rec.text_color};' if rec.text_color else '#FFFFFF;',
                    'val_color': f'color: {rec.val_color};' if rec.val_color else '#FFFFFF;',
                    'icon_color': f'color: {rec.tile_color};' if rec.tile_color else '#1f6abb;',
                    'height': rec.height,
                    'width': rec.width,
                    'translate_x': rec.translate_x,
                    'translate_y': rec.translate_y,
                    'data_x': rec.data_x,
                    'data_y': rec.data_y,
                    'domain': filter_list,
                    }
            domain = []
            if rec.filter:
                domain = expression.AND([literal_eval(rec.filter)])
                custom_domain = domain[0]
                field, operator, value = custom_domain
            if rec.model_name:
                if rec.type == 'graph':
                    if rec.model_name == 'sale.order':
                        if rec.name == "Order Value":
                            field_column = rec.measured_field_id.name
                            group_by_field = rec.group_by_id.name 
                            query = f'''
                                        SELECT 
                                            TO_CHAR({group_by_field}, 'Day') AS day_of_week,
                                            {rec.operation}({field_column}) AS value
                                        FROM 
                                            sale_order
                                        WHERE 
                                            order_state = 'mark_as_delivered'
                                    '''
                            if start_date and end_date:
                                query += f'''
                                    AND commitment_date >= '{start_date} 00:00:00'
                                    AND commitment_date <= '{end_date} 23:59:59'
                            '''
                            query +=f'''
                                GROUP BY 
                                    TO_CHAR({group_by_field}, 'Day'),
                                    EXTRACT(ISODOW FROM commitment_date)
                                ORDER BY 
                                    EXTRACT(ISODOW FROM commitment_date)
                            '''

                            self._cr.execute(query)

                            records = self._cr.dictfetchall()

                            # Build x_axis and y_axis
                            x_axis = []
                            y_axis = []
                            for record in records:
                                day = record.get('day_of_week').strip()  # remove extra spaces
                                x_axis.append(day)
                                y_axis.append(record.get('value') or 0)

                            vals.update({'x_axis': x_axis, 'y_axis': y_axis})
                    else:
                        query = self.env[rec.model_name].get_query(domain,
                                                                        rec.operation,
                                                                        rec.measured_field_id,
                                                                        start_date,
                                                                        end_date,
                                                                        group_by=rec.group_by_id)
                        if rec.name == "Driver Status":
                            query = self.env[rec.model_name].get_query(domain,
                                                                        rec.operation,
                                                                        rec.measured_field_id,
                                                                        group_by=rec.group_by_id)

                        if rec.name.strip() == 'Top Performer':
                            query = '''SELECT 
                                            COALESCE(COUNT("sale_order"."id"), 0) AS value,
                                            "res_partner"."name"
                                        FROM 
                                            "res_partner"
                                        JOIN 
                                            "sale_order" ON "sale_order"."delivery_boy_id" = "res_partner"."id"
                                        WHERE 
                                            (("res_partner"."active" = 'True')
                                            AND ("res_partner"."is_driver" = TRUE)
                                            AND ("sale_order"."order_state" = 'mark_as_delivered'))'''
                            
                            if start_date and end_date:
                                query+=f'''AND ("sale_order"."commitment_date" >= '{start_date} 00:00:00')  
                                           AND ("sale_order"."commitment_date" <= '{end_date} 12:00:00')
                                        '''  
                            query+='''GROUP BY 
                                            "res_partner"."name"
                                        ORDER BY 
                                            value DESC
                                        LIMIT 7;
                                    '''
                        self._cr.execute(query)
                        
                        records = self._cr.dictfetchall()

                        x_axis = []
                        for record in records:
                            if record.get('name') and type(
                                    record.get('name')) == dict:
                                x_axis.append(record.get('name')[self._context.get(
                                    'lang') or 'en_US'])
                            else:
                                x_axis.append(record.get(rec.group_by_id.name).upper())
                        y_axis = []
                        for record in records:
                            y_axis.append((record.get('value')))
                        vals.update({'x_axis': x_axis, 'y_axis': y_axis})

                   
                else:
                    self._cr.execute(self.env[rec.model_name].get_query(domain,
                                                                        rec.operation,
                                                                        rec.measured_field_id,
                                                                        start_date,
                                                                        end_date))
                    records = self._cr.dictfetchall()
                    magnitude = 0
                    total = records[0].get('value')
                    while abs(total) >= 1000:
                        magnitude += 1
                        total /= 1000.0
                    val = '%.2f%s' % (
                        total, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])
                    records[0]['value'] = val
                    vals.update(records[0])
            block_id.append(vals)
        return block_id
    
    def get_save_layout(self, grid_data_list):
        """Function fetch edited values while edit layout of the chart or tile
         and save values in a database"""
        for data in grid_data_list:
            block = self.browse(int(data['id']))
            if data.get('data-x'):
                block.write({
                    'translate_x': f"{data['data-x']}px",
                    'translate_y': f"{data['data-y']}px",
                    'data_x': data['data-x'],
                    'data_y': data['data-y'],
                })
            if data.get('height'):
                block.write({
                    'height': f"{data['height']}px",
                    'width': f"{data['width']}px",
                })
        return True
    

    