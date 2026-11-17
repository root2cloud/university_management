/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchPanel } from "@web/search/search_panel/search_panel";
import { useState } from "@odoo/owl";

/**
 * Collapsible filter groups for the search panel.
 *
 * Opt-in: only search panels declared with class="o_collapsible_groups"
 * (e.g. <searchpanel class="o_collapsible_groups">) are affected.
 * Clicking the group title (department name) expands/collapses its children;
 * clicking the checkbox still selects/unselects every child.
 */
patch(SearchPanel.prototype, {
    setup() {
        super.setup(...arguments);
        // key: `${sectionId}_${groupId}` -> true (expanded) / false (collapsed)
        this.groupFold = useState({});
    },

    get hasCollapsibleGroups() {
        const className = this.env.searchModel.searchPanelInfo.className || "";
        return className.split(/\s+/).includes("o_collapsible_groups");
    },

    isGroupExpanded(sectionId, groupId, group) {
        if (!this.hasCollapsibleGroups) {
            return true;
        }
        const key = `${sectionId}_${groupId}`;
        if (key in this.groupFold) {
            return this.groupFold[key];
        }
        // Not toggled by the user yet: keep groups with a selection open
        // so the selected faculty stay visible, collapse the rest.
        return [...group.values.values()].some((value) => value.checked);
    },

    onGroupLabelClick(ev, sectionId, groupId, group) {
        if (!this.hasCollapsibleGroups) {
            return; // default behaviour: label toggles the checkbox
        }
        // Stop the <label for=...> from ticking the group checkbox.
        ev.preventDefault();
        const key = `${sectionId}_${groupId}`;
        this.groupFold[key] = !this.isGroupExpanded(sectionId, groupId, group);
    },
});