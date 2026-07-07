/** @odoo-module **/
    
    import publicWidget from '@web/legacy/js/public/public_widget';
    import { loadWysiwygFromTextarea } from "@web_editor/js/frontend/loadWysiwygFromTextarea";
    import { _t } from "@web/core/l10n/translation";
    
    
    publicWidget.registry.websiteORA = publicWidget.Widget.extend({
        selector: '.o_user_response',
        /**
         * @override
         */
        start: function () {
            var def = this._super.apply(this, arguments);
            if (this.editableMode) {
                return def;
            }
            var self = this;
            $('textarea.o_wysiwyg_loader').toArray().forEach((textarea) => {
                var $textarea = $(textarea);
                var options = {
                    resizable: true,
                    userGeneratedContent: true,
                    height: 100,
                };
                loadWysiwygFromTextarea(self, $textarea[0], options)
            });
    
            $('.custom_response').click(function () {
                var id = this.id.split('-')[this.id.split('-').length - 1];
                var button = $(this);
                $('#collapse_div_' + id).on('shown.bs.collapse', function () {
                    button.children().text(_t('Hide Response'));
                });
                $('#collapse_div_' + id).on('hidden.bs.collapse', function () {
                    button.children().text(_t('View Response'));
                });
            });            
            return Promise.all([def]);
        },
    });