/** @odoo-module **/
import { registry } from "@web/core/registry";
import { loadJS } from '@web/core/assets';
import { DynamicDashboardTile} from './dynamic_dashboard_tile';
import { DynamicDashboardChart} from './dynamic_dashboard_chart';
import { OrderStatsTile } from './order_stats_tile'; 
import { useService } from "@web/core/utils/hooks";

import { Component, useRef, useState, onWillStart, onMounted , mount} from "@odoo/owl";

export class OdooDynamicDashboardAsset extends Component {
    // Setup function to run when the template of the class OdooDynamicDashboardAsset renders
    setup() {
        this.ThemeSelector = useRef('ThemeSelector');
        this.action = useService("action");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.actionId = this.props.actionId
        this.isAdmin = useState({ value: false });
    
        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/jspdf/1.5.3/jspdf.min.js")
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js")
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.9.3/html2pdf.bundle.min.js")
            await loadJS("https://cdn.jsdelivr.net/npm/interactjs@latest/dist/interact.min.js")
            await loadJS("https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js")
            // const result  = await this.orm.call("res.partner", "is_user_admin", []);
            // this.isAdmin.value = result ;
        });
    
        onMounted(()=>{
            this.renderDashboard();
        })
       
    }

    onChangeTheme(){
        /* Function for changing color of the theme of the dashboard */
        $(".container").attr('style', this.ThemeSelector.el.value + 'min-height:-webkit-fill-available;')
    }

    ResizeDrag() {
        // Apply interact.js resizing and dragging
        document.querySelectorAll('.items .resize-drag').forEach(function (element) {
            interact(element).resizable({
                edges: { left: true, right: true, bottom: true, top: true },
                listeners: {
                    move(event) {
                        const target = event.target;
    
                        // Calculate new position
                        let x = (parseFloat(target.getAttribute('data-x')) || 0) + event.deltaRect.left;
                        let y = (parseFloat(target.getAttribute('data-y')) || 0) + event.deltaRect.top;
    
                        // Apply new width and height to the element
                        target.style.width = event.rect.width + 'px';
                        target.style.height = event.rect.height + 'px';
    
                        // Apply new position
                        target.style.transform = 'translate(' + x + 'px, ' + y + 'px)';
                        target.setAttribute('data-x', x);
                        target.setAttribute('data-y', y);
    
                        // 🔧 Resize the canvas inside the element
                        const canvas = target.querySelector('canvas');
                        if (canvas) {
                            // Set canvas dimensions to match the container
                            canvas.width = target.clientWidth;
                            canvas.height = target.clientHeight;
    
                            // ✅ If Chart.js instance is attached, call resize
                            if (canvas.chartInstance && typeof canvas.chartInstance.resize === 'function') {
                                canvas.chartInstance.resize();
                            }
                        }
                    }
                },
                modifiers: [
                    interact.modifiers.restrictEdges({
                        outer: 'parent'
                    }),
                    interact.modifiers.restrictSize({
                        min: { width: 100, height: 50 }
                    })
                ],
                inertia: true
            }).draggable({
                listeners: { move: dragMoveListener },
                inertia: true,
                modifiers: [
                    interact.modifiers.restrictRect({
                        restriction: 'parent',
                        endOnly: true
                    })
                ]
            });
    
            function dragMoveListener(event) {
                const target = event.target;
                const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
                const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
    
                target.style.transform = 'translate(' + x + 'px, ' + y + 'px)';
                target.setAttribute('data-x', x);
                target.setAttribute('data-y', y);
            }
    
            // Save dragMoveListener globally if needed elsewhere
            window.dragMoveListener = dragMoveListener;
        });
    }

    async renderDashboard(){
    /* Function for rendering the dashboard */
        var self = this;
        document.getElementById('save_layout').hidden = true;

        await this.orm.call('it.assets', 'getAssetAndComponentCount', [[]]).then(function(response) {
            let cart = document.getElementsByClassName('cart');
            mount(OrderStatsTile, cart[0], {
                props: {
                    total_assets: response.total_assets,
                    total_systems: response.total_systems,
                    total_components: response.total_components,
                    repairing_components: response.repairing_components,
                }
            });
        });     
        
        await this.orm.call("dashboard.block", "get_dashboard_vals", [[], this.actionId]).then( function (response){
            for (let i = 0; i < response.length; i++) {
                if (response[i].type === 'tile'){
                    component = document.getElementsByClassName('items');
                    mount(DynamicDashboardTile, component[0], { props: {
                        widget: response[i], doAction: self.action, dialog:self.dialog, orm: self.orm
                    }});
                }
                else{
                    let component = document.getElementsByClassName('items');
                    mount(DynamicDashboardChart, component[0], { props: {
                        widget: response[i], doAction: self.action, rpc: self.rpc, dialog:self.dialog, orm: self.orm
                    }});
                }
            }
        })
        
    }

    editLayout(ev) {
    /* Function for editing the layout , it enables resizing and dragging functionality */
        $('.items .resize-drag').each(function(index, element) {
            interact(element).draggable(true)
            interact(element).resizable(true)
        });
        ev.stopPropagation();
        ev.preventDefault();
        $("#edit_layout").hide();
        var save_layout  = document.getElementById('save_layout');
        save_layout.removeAttribute("hidden");
        save_layout.style.display = "inline-block"; 
        this.ResizeDrag()
    }

    
    saveLayout(ev){
    /* Function for saving the layout */
        var self = this;
        ev.stopPropagation();
        ev.preventDefault();
        $("#edit_layout").show();
        $("#save_layout").hide();
        var data_list = []
        $('.items .resize-drag').each(function(index, element) {
            interact(element).draggable(false)
            interact(element).resizable(false)
            data_list.push({
                'id' : element.dataset['id'],
                'data-x': element.dataset['x'],
                'data-y': element.dataset['y'],
                'height': element.clientHeight,
                'width': element.clientWidth,
            })
        });
        self.orm.call('dashboard.block','get_save_layout', [[], data_list]).then( function (response){
            window.location.reload();
        });
    }


    changeViewMode(ev){
    /* Function for changing the mode of the view */
        ev.stopPropagation();
        ev.preventDefault();
        const currentMode = $(".mode").attr("mode");
        if (currentMode == "light"){
            $('.theme').attr('style','display: none;')
            $(".container").attr('style', 'background-color: #383E45;min-height:-webkit-fill-available; !important')
            $(".mode").attr("mode", "dark")
            $(".bi-moon-stars-fill").attr('class', 'bi bi-cloud-sun-fill view-mode-icon')
            $(".bi-cloud-sun-fill").attr('style', 'color:black;margin-left:10px;')
            $(".mode").attr('style','display: none !important');
            $("#search-input-chart").attr('style', 'background-color: white; !important')
            $("#search-button").attr('style', 'background-color: #BB86FC; !important')
            $("#dropdownMenuButton").attr('style', 'background-color: #03DAC5;margin-top:-4px; !important')
            $("#text_add").attr('style', 'color: black; !important')
            $(".date-label").attr('style', 'color: black;font-family:monospace; !important')
            $(".block_setting").attr('style', 'color: white; !important')
            $(".block_delete").attr('style', 'color: white; !important')
            $(".block_image").attr('style', 'color: #03DAC5; !important')
            $(".block_pdf").attr('style', 'color: #03DAC5; !important')
            $(".block_csv").attr('style', 'color: #03DAC5; !important')
            $(".block_xlsx").attr('style', 'color: #03DAC5; !important')
        }
        else {
            $('.theme').attr('style','display: block;')
            $(".container").attr('style', this.ThemeSelector.el.value + 'min-height:-webkit-fill-available;')
            $(".mode").attr("mode", "light")
            $(".bi-cloud-sun-fill").attr('class', 'bi bi-moon-stars-fill view-mode-icon')
            $(".view-mode-icon").attr('style', 'color:black;margin-left:10px; !important')
            $(".mode").attr('style','display: none !important');
            $(".mode").attr('style','color: white !important');
            $("#search-input-chart").attr('style', 'background-color: none; !important')
            $("#search-button").attr('style', 'background-color: none; !important')
            $("#dropdownMenuButton").attr('style', 'background-color: none;margin-top:-4px; !important')
            $("#text_add").attr('style', 'color: white; !important')
            $(".date-label").attr('style', 'color: black; !important;font-family:monospace; !important')
            $(".block_setting").attr('style', 'color: black; !important')
            $(".block_delete").attr('style', 'color: black; !important')
            $(".block_image").attr('style', 'color: black; !important')
            $(".block_pdf").attr('style', 'color: black; !important')
            $(".block_csv").attr('style', 'color: black; !important')
            $(".block_xlsx").attr('style', 'color: black; !important')
        }
    }
    onClickAdd(event){
    /* For enabling the toggle button */
        event.stopPropagation();
        event.preventDefault();
        $(".dropdown-addblock").toggle()
    }
    onClickAddItem(event){
    /* Function for adding tiles and charts */
        event.stopPropagation();
        event.preventDefault();
        self = this;
        var type = event.target.getAttribute('data-type');
        if (type == 'graph'){
            var chart_type = event.target.getAttribute('data-chart_type');
        }
        if (type == 'tile'){
            var randomColor = '#' + ('000000' + Math.floor(Math.random() * 16777216).toString(16)).slice(-6);
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'dashboard.block',
                view_mode: 'form',
                views: [[false, 'form']],
                context: {
                    'form_view_initial_mode': 'edit',
                    'default_name': 'New Tile',
                    'default_type': type,
                    'default_height': '155px',
                    'default_width': '300px',
                    'default_tile_color': randomColor,
                    'default_text_color': '#FFFFFF',
                    'default_val_color': '#F3F3F3',
                    'default_fa_icon': 'fa fa-bar-chart',
                    'default_client_action_id': parseInt(self.actionId)
                }
            })
        }
        else{
            this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'dashboard.block',
                view_mode: 'form',
                views: [[false, 'form']],
                context: {
                    'form_view_initial_mode': 'edit',
                    'default_name': 'New ' + chart_type,
                    'default_type': type,
                    'default_height': '565px',
                    'default_width': '588px',
                    'default_graph_type': chart_type,
                    'default_fa_icon': 'fa fa-bar-chart',
                    'default_client_action_id': parseInt(self.actionId)
                },
            })
        }
    }

    dateFilter(){
    /* Function for filtering the data based on the creation date */
        document.querySelectorAll('.items').forEach(el => {
            el.innerHTML = '';
        });
        var start_date = document.getElementById('start-date').value;
        var end_date = document.getElementById('end-date').value;
        var self = this;
        if (!start_date){
            start_date = "null"
        }
        if (!end_date){
            end_date = "null"
        }

        this.orm.call("dashboard.block", "get_dashboard_vals", [[], this.actionId, start_date, end_date]).then( function (response){
            for (let i = 0; i < response.length; i++) {
                if (response[i].type === 'tile'){
                    let component = document.getElementsByClassName('items')[0];
                    mount(DynamicDashboardTile, component, { props: {
                        widget: response[i], doAction: self.action, dialog:self.dialog, orm: self.orm
                    }});
                }
                else{
                    let component = document.getElementsByClassName('items')[0];
                    mount(DynamicDashboardChart,component, { props: {
                        widget: response[i], doAction: self.action, rpc: self.rpc, dialog:self.dialog, orm: self.orm
                    }});
                }
            }
        })

        this.orm.call('sale.order', 'get_order_stats', [[], start_date, end_date]).then(function(response) {
            const cart = document.querySelector('.cart');
            const existingComponent = cart.querySelector('.order-stats-container');

            if (existingComponent) {
                existingComponent.remove();
            }
            let component = document.getElementsByClassName('cart')[0]
            mount(OrderStatsTile,component, {
                props: {
                    total: response.total,
                    pending: response.pending,
                    delivered: response.delivered,
                    cancelled: response.cancelled,
                }
            });
        });
    }

    async clickSearch(){
    /* Function for searching the blocks with their names */
        var input = $("#search-input-chart").val();
        await this.rpc('/custom_dashboard/search_input_chart', {'search_input': input}).then(function (response) {
            var blocks = $(".items .resize-drag");
            blocks.each(function(index, element){
                var dataId = $(element).data('id');
                if (response.includes(dataId)){
                    $(element).css("visibility", "visible");
                }
                else{
                    $(element).css("visibility", "hidden");
                }
            })
        })
    }

    showViewMode(ev){
    /* Function for showing the mode text */
        const currentMode = $(".mode").attr("mode");
        if (currentMode == "light"){
            $(".mode").text("Dark Mode")
            $(".mode").attr('style','display: inline-block !important; color: black !important');
        }
        else{
            $(".mode").text("Light Mode")
            $(".mode").attr('style','display: inline-block !important; color: black !important');
        }
    }

    hideViewMode(ev){
        const modeElement = document.querySelector(".mode");

        if(!modeElement) return;

        modeElement.style.transition = "opacity 2s";
        modeElement.style.opacity = "0";

        setTimeout(()=>{
            modeElement.style.display = "none";

        }, 2000);
    }
    clearSearch(){
    /* Function for clearing the search input */
        $("#search-input-chart").val('');
        var blocks = $(".items .resize-drag");
        blocks.each(function(index, element){
            $(element).css("visibility", "visible");
        })
    }

    onDateRangeSelect(ev) {
        const sel   = ev.target.value;
        const today = new Date();
        let startDate, endDate;
        const customDateDiv = document.getElementById('custom-date-inputs');

        if (sel === "custom") {
            if (customDateDiv) customDateDiv.style.display = "flex";
            return;  
        }else {
            if (customDateDiv) customDateDiv.style.display = "none";
        }
     
    
        // Local‐time formatter to avoid UTC shift
        const fmtLocal = date => {
            const Y = date.getFullYear();
            const M = String(date.getMonth() + 1).padStart(2, '0');
            const D = String(date.getDate()).padStart(2, '0');
            return `${Y}-${M}-${D}`;
        };
    
        switch (sel) {
            case "today":
                startDate = endDate = fmtLocal(today);
                break;
            case "this_week": {
                const dow = today.getDay(); // 0=Sun…6=Sat
                const mon = new Date(today);
                mon.setDate(today.getDate() - dow + (dow === 0 ? -6 : 1));
                const sun = new Date(mon);
                sun.setDate(mon.getDate() + 6);
                startDate = fmtLocal(mon);
                endDate   = fmtLocal(sun);
                break;
            }
            case "last_week": {
                const now = new Date(today);
                const dow = now.getDay();
                const thisMon = new Date(now);
                thisMon.setDate(now.getDate() - dow + (dow === 0 ? -6 : 1));
                const lastSun = new Date(thisMon);
                lastSun.setDate(thisMon.getDate() - 1);
                const lastMon = new Date(lastSun);
                lastMon.setDate(lastSun.getDate() - 6);
                startDate = fmtLocal(lastMon);
                endDate   = fmtLocal(lastSun);
                break;
            }
            case "this_month":
                // if you want 1st → today:
                startDate = fmtLocal(new Date(today.getFullYear(), today.getMonth(), 1));
                endDate   = fmtLocal(today);
                break;
            case "last_month":
                startDate = fmtLocal(new Date(today.getFullYear(), today.getMonth() - 1, 1));
                endDate   = fmtLocal(new Date(today.getFullYear(), today.getMonth(), 0));
                break;
            
                case "this_year":
                    // Jan 1 of this year → today
                    startDate = fmtLocal(new Date(today.getFullYear(), 0, 1));
                    endDate   = fmtLocal(today);
                    break;

                case "last_year":
                    // Jan 1 → Dec 31 of previous year
                    const prevYear = today.getFullYear() - 1;
                    startDate = fmtLocal(new Date(prevYear, 0, 1));
                    endDate   = fmtLocal(new Date(prevYear, 11, 31));
                    break;
            // … other cases …
            default:
                return;
        }
    
        // Update your inputs by ID
        const startIn = document.getElementById("start-date");
        const endIn   = document.getElementById("end-date");
        if (startIn && endIn) {
            startIn.value = startDate;
            endIn.value   = endDate;
            this.dateFilter();
        }
    }
}
OdooDynamicDashboardAsset.template = "owl.OdooDynamicDashboardAsset"
registry.category("actions").add("OdooDynamicDashboardAsset", OdooDynamicDashboardAsset)
