/** @odoo-module **/


import { Component , xml} from "@odoo/owl";
export class OrderStatsTile extends Component {}

OrderStatsTile.template = xml`
<div class="order-stats-container p-3">
    <div class="row text-center">
        <!-- Total Orders -->
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="stat-item bg-info text-white p-4 border rounded shadow-lg">
                <h5>Total Systems</h5>
                <p class="h4"><t t-esc="props.total_systems"/></p>
            </div>
        </div>
        
        <!-- Pending Orders -->
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="stat-item bg-warning-light text-dark p-4 border rounded shadow-lg">
                <h5>Total Assets</h5>
                <p class="h4"><t t-esc="props.total_assets"/></p>
            </div>
        </div>
        
        <!-- Delivered Orders -->
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="stat-item bg-success-light text-dark p-4 border rounded shadow-lg">
                <h5>Total Components</h5>
                <p class="h4"><t t-esc="props.total_components"/></p>
            </div>
        </div>
        
        <!-- Cancelled Orders -->
        <div class="col-md-3 col-sm-6 mb-3">
            <div class="stat-item bg-danger-light text-dark p-4 border rounded shadow-lg">
                <h5>Repairing Components</h5>
                <p class="h4"><t t-esc="props.repairing_components"/></p>
            </div>
        </div>
    </div>
</div>
` 
