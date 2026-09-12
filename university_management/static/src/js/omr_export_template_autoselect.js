/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ExportDataDialog } from "@web/views/view_dialogs/export_data_dialog";

// Model -> name of the saved export template ("ir.exports" record) that
// should be auto-selected the moment the "Export Data" popup opens, so the
// user no longer has to open the Template dropdown and pick it by hand.
const AUTO_SELECT_TEMPLATES = {
    "exam.omr.scanner": "OMR Marks",
};

patch(ExportDataDialog.prototype, {
    async fetchFields() {
        await super.fetchFields(...arguments);

        const templateName = AUTO_SELECT_TEMPLATES[this.props.root.resModel];
        if (!templateName || this.state.templateId) {
            return;
        }

        const template = this.templates.find((tmpl) => tmpl.name === templateName);
        if (template) {
            await this.loadExportList(template.id);
        }
    },
});