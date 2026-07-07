from . import models
def create_dashboard_block(env):

    components = env['ir.model'].search([('name','=','it.components')])
    asset = env['ir.model'].search([('name','=','it.assets')])
    system = env['ir.model'].search([('name','=','system.system')])
    
    components_measured_field = env['ir.model.fields'].search([('name','=', 'id'),('model_id','=',components.id)],limit=1)
    components_group_by_id = env['ir.model.fields'].search([('name','=','state'),('model_id','=',components.id)],limit=1)
    
    env['dashboard.block'].create({
    'name': 'Component Status',
    'model_id': components.id,
    'operation': 'count',
    'measured_field_id': components_measured_field.id,
    'type':'graph',
    'graph_type': 'bar',
    'group_by_id': components_group_by_id.id,
    'client_action_id':  env.ref('it_inventory_and_asset_management.dashboard_view_action').id
    })
    
    
    asset_measured_field = env['ir.model.fields'].search([('name','=','id'),('model_id','=',asset.id)],limit=1)
    asset_group_by_id = env['ir.model.fields'].search([('name','=','asset_type'),('model_id','=',asset.id)],limit=1)
    env['dashboard.block'].create({
    'name': 'Asset Dashboard ',
    'model_id': asset.id,
    'operation': 'count',
    'measured_field_id': asset_measured_field.id,
    'type':'graph',
    'graph_type': 'line',
    'group_by_id': asset_group_by_id.id,
    'client_action_id':  env.ref('it_inventory_and_asset_management.dashboard_view_action').id
    })

    system_measured_field = env['ir.model.fields'].search([('name','=','id'),('model_id','=',system.id)],limit=1)
    system_group_by_id = env['ir.model.fields'].search([('name','=','state'),('model_id','=',system.id)],limit=1)

    
    env['dashboard.block'].create({
    'name': 'System Dashboard',
    'model_id': system.id,
    'operation': 'count',
    'measured_field_id': system_measured_field.id,
    'type':'graph',
    'graph_type': 'doughnut',
    'group_by_id': system_group_by_id.id,
    'client_action_id':  env.ref('it_inventory_and_asset_management.dashboard_view_action').id
    })


