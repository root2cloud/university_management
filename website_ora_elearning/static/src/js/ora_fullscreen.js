/** @odoo-module **/

    import { _t } from "@web/core/l10n/translation";
    import { renderToFragment } from "@web/core/utils/render";
    import publicWidget from '@web/legacy/js/public/public_widget';
    import Fullscreen from "@website_slides/js/slides_course_fullscreen_player";
    import { markup } from "@odoo/owl";
    import { loadWysiwygFromTextarea } from "@web_editor/js/frontend/loadWysiwygFromTextarea";
    import { rpc } from "@web/core/network/rpc";

    var findSlide = function (slideList, matcher) {
        return slideList.find((slide) => {
            return Object.keys(matcher).every((key) => matcher[key] === slide[key]);
        });
    };

    Fullscreen.include({
        events: Object.assign({}, Fullscreen.prototype.events, {
            "click .o_wslides_js_lesson_ora_submit": '_submitOra',
            "click .o_submit_peer_response": '_submitPeer',
            "click .o_wslides_fs_toggle_sidebar": '_onClickToggleSidebar',
            "click .o_wslides_ora_continue": '_onClickOraNext'
        }),
        /**
        * @override
        * @param {Object} el
        * @param {Object} slides Contains the list of all slides of the course
        * @param {integer} defaultSlideId Contains the ID of the slide requested by the user
        */
        init: function (parent, slides, defaultSlideId, channelData) {
            var result = this._super.apply(this,arguments);
            this.initialSlideID = defaultSlideId;
            // this.slides = this._preprocessSlideData(slides);
            this.channel = channelData;
            var slide;
            const urlParams = new URL(window.location).searchParams;
            if (defaultSlideId) {
                slide = findSlide(this.slides, {id: defaultSlideId, isQuiz: String(urlParams.get("quiz")) === "1" });
            } else {
                slide = this.slides[0];
            }

            this._slideValue = slide;

            this.sidebar = new NewSidebar(this, this.slides, slide);
            return result;
        },

        _preprocessSlideData: function (slidesDataList) {
            var res = this._super.apply(this, arguments);
            res.forEach(function (slideData, index) {
                slideData.isOra = !!slideData.isOra;
                slideData.hasQuestion = !!slideData.hasQuestion;
                try {
                    if (!(slideData.isOra) && !(slideData.hasQuestion) && slideData.category != 'certification') {
                        slideData._autoSetDone = true;
                    }
                }
                catch {
                    if (!(slideData.hasQuestion) && slideData.category != 'certification') {
                        slideData._autoSetDone = true;
                    }
                }
            });
            return res;
        },
        _onChangeSlideRequest: function (ev) {
            var slideData = ev.data;
            var newSlide = findSlide(this.slides, {
                id: slideData.id,
                isQuiz: slideData.isQuiz || false,
                isOra: slideData.isOra || false,
            });
            this._updateSlideValue(newSlide);
        },
        /**
         * Triggering a event to switch to next slide
         *
         * @private
         * @param OdooEvent ev
         */
        _onClickOraNext: function (ev) {
            var self = this;
            if (this._slideValue.isOra === true) {
                rpc('/slides/slide/get_values', {
                        slide_id: (this._slideValue.id),
                }).then(function (data) {
                    if (data.slide.hasNext && data.slide.next_slide_url && !data.slide.ispro) {
                        var url = data.slide.next_slide_url;
                        window.location.replace(url);
                    }
                    if (data.slide.hasNext && data.slide.next_slide_url && data.slide.ispro) {
                        var slide = $('.o_wslides_fs_sidebar_list_item.active');
                        var $slides = this.$('.o_wslides_fs_sidebar_list_item');
                        var slideListdata = [];
                        var slideList = []
                        $slides.each(function () {
                            var slideData = $(this).data();
                            if (slideData.category == 'video' && slideData.videoSourceType !== 'vimeo' && !slideData.hasQuestion && !slideData.embedCode.includes('iframe')) {
                                slideData.embedCode = '<iframe src=\"' + slideData.embedCode + '\" allowFullScreen=\"true\" frameborder=\"0\"></iframe>'
                            }
                            slideListdata.push(slideData);
                            slideList.push($(this));
                        });
                        var slide_list_data = self._preprocessSlideData(slideListdata);
                        var index = 0;
                        if (slide.data().category == 'quiz') {
                            for (let [i, v] of slideList.entries()) {
                                if (v[0].classList.contains('active')) {
                                    index = i;
                                }
                            }
                        }
                        else if ((slide.data().category != 'quiz' && slide.data().hasQuestion) || slide.data().hasOra) {
                            for (let [i, v] of slideList.entries()) {
                                if (v[0].classList.contains('active')) {
                                    index = i + 1;
                                }
                            }
                        }
                        if (index == slideList.length) {
                            index = index - 1
                        }
                        var next_slide = slide_list_data[index + 1];
                        if (next_slide === self.get('slide')) {
                            next_slide = slide_list_data[index + 2];
                        }
                        next_slide['canAccess'] = 'True';
                        var next_slide_list = slideList[index + 1]
                        if (next_slide_list === self.get('slide')) {
                            next_slide_list = slide_list_data[index + 2];
                        }
                        var next_div = next_slide_list.find('.o_wslides_fs_slide_name');
                        self.slides.push(next_slide);
                        slide.removeClass('active');
                        $('.o_sidebar_link').attr("href", '#');
                        $('.o_btn_set_done').addClass('d-none');
                        $('.o_btn_next_slide').addClass('d-none');
                        next_slide_list.addClass('active');
                        next_slide_list.removeClass('disabled')
                        next_slide_list.removeClass('text-600')
                        next_div.removeClass('text-600');
                        if (slide.data()['hasQuestion'] || slide.data()['isQuiz'] || slide.data()['hasOra']) {
                            var next_quiz = slide.find('.o_wslides_fs_sidebar_list_item a');
                            next_quiz.attr("href", '#');
                            next_quiz.removeClass('text-600');
                            var next_mini = slide.find('.o_wslides_fs_sidebar_list_item span');
                            next_mini.attr("href", '#');
                            next_mini.removeClass('text-600');
                        }
                        self.sidebar.set('slideEntry', {
                            id: next_slide.id,
                            isQuiz: next_slide.isQuiz || false
                        });
                        // }
                    }
                });
            }
        },

        _renderSlide: function () {
            var def = this._super.apply(this, arguments);
            var $content = this.$('.o_wslides_fs_content');
            var self = this;
            if (this._slideValue.isOra === true) {
                rpc('/slides/slide/get_values', {
                    slide_id: (this._slideValue.id),
                }).then(function (data) {
                    if (data.slide_prompts) {
                        for (let i = 0; i < data.slide_prompts.length; i++) {
                            data.slide_prompts[i].question = markup(data.slide_prompts[i].question)
                        }
                    }
                    if (data.total_responses) {
                        for (let i = 0; i < data.total_responses.length; i++) {
                            for (let j = 0; j < (data.total_responses[i].user_response_line).length; j++) {
                                data.total_responses[i].user_response_line[j].value_richtext_box = markup(data.total_responses[i].user_response_line[j].value_richtext_box)
                            }
                        }
                    }
                    if (data.peer_responses) {
                        for (let i = 0; i < data.peer_responses.length; i++) {
                            for (let j = 0; j < (data.peer_responses[i].user_response_line).length; j++) {
                                data.peer_responses[i].user_response_line[j].value_richtext_box = markup(data.peer_responses[i].user_response_line[j].value_richtext_box)
                            }
                        }
                    }
                    $content.empty().append(renderToFragment('slide.ora.assessment', {widget: data}));
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
                });
            }
            return Promise.all([def]);
        },

        _submitPeer: function (ev) {
            var id = ev.currentTarget.id.split('_')[ev.currentTarget.id.split('_').length - 1]
            var data = $('#ora_peer_submit_' + id).serializeArray();
            var self = this;
            ev.preventDefault();
            $.ajax({
                type: "POST",
                url: "/submit/peer/response",
                data: data,
                success: function (data) {
                    self._renderSlide();
                }
            });
        },

        _submitOra: function (ev) {
            var responseData = []
            $('.o_wslides_ora_answer_info').each(function () {
                var response_div_id = `response_div_${this.id}`;
                var $response_div = $(`.${response_div_id}`);
                if ($response_div.length && !$response_div.val()) {
                    var richTextValue = $response_div.find('.note-editable').html();
                    responseData.push({ name: this.id, value: richTextValue });
                }
            });            
            responseData;
            var data = $('#ora_form').serializeArray();
            responseData.forEach(function (item) {
                var existingField = data.find(function (field) {
                    return field.name === item.name;
                });
                if (existingField) {
                    existingField.value = item.value;
                } else {
                    data.push({ name: item.name, value: item.value });
                }
            });        
            data.push({ name: ev.currentTarget.name, value: ev.currentTarget.value });
            ev.preventDefault();
            var self = this;
            $.ajax({
                type: "POST",
                url: "/ora/response/save/",
                data: data,
                success: function (data) {
                    self._renderSlide();
                }
            });
        },
    });
    /**
     * This widget is responsible of navigation for one slide to another:
     *  - by clicking on any slide list entry
     *  - by mouse click (next / prev)
     *  - by recieving the order to go to prev/next slide (`goPrevious` and `goNext` public methods)
     *
     * The widget will trigger an event `change_slide` with
     * the `slideId` and `isMiniQuiz` as data.
     */
    var NewSidebar = publicWidget.Widget.extend({
        events: {
            'click .o_wslides_fs_sidebar_list_item .o_wslides_fs_slide_name': '_onClickTab',
        },
        init: function (parent, slideList, defaultSlide) {
            var result = this._super.apply(this, arguments);
            this.slideEntries = slideList;
            this._slideEntry = defaultSlide;
            return result;
        },
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                $(document).keydown(self._onKeyDown.bind(self));
            });
        },
        destroy: function () {
            $(document).unbind('keydown', this._onKeyDown.bind(this));
            return this._super.apply(this, arguments);
        },
        //--------------------------------------------------------------------------
        // Public
        //--------------------------------------------------------------------------
        /**
         * Change the current slide with the next one (if there is one).
         *
         * @public
         */
        goNext: function () {
            var currentIndex = this._getCurrentIndex();
            if (currentIndex < this.slideEntries.length - 1) {
                this._updateSlideEntry(this.slideEntries[currentIndex + 1]);
            }
        },
        /**
         * Change the current slide with the previous one (if there is one).
         *
         * @public
         */
        goPrevious: function () {
            var currentIndex = this._getCurrentIndex();
            if (currentIndex >= 1) {
                this._updateSlideEntry(this.slideEntries[currentIndex - 1]);
            }
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------
        /**
         * Get the index of the current slide entry (slide and/or quiz)
         */
        _getCurrentIndex: function () {
            const slide = this._slideEntry;
            var currentIndex = this.slideEntries.findIndex(entry => {
                return entry.id === slide.id && entry.isQuiz === slide.isQuiz;
            });
            return currentIndex;
        },
        //--------------------------------------------------------------------------
        // Handler
        //--------------------------------------------------------------------------
        /**
         * Handler called whenever the user clicks on a sub-quiz which is linked to a slide.
         * This does NOT handle the case of a slide of category "quiz".
         * By going through this handler, the widget will be able to determine that it has to render
         * the associated quiz and not the main content.
         *
         * @private
         * @param {*} ev
         */
        _onClickMiniQuiz: function (ev) {
            var slideID = parseInt($(ev.currentTarget).data().slide_id);
            this._updateSlideEntry({
                slideID: slideID,
                isMiniQuiz: true
            });
            this.trigger_up('change_slide', this._slideEntry);
        },
        /**
         * Handler called when the user clicks on a normal slide tab
         *
         * @private
         * @param {*} ev
         */
        _onClickTab: function (ev) {
            ev.stopPropagation();
            const $elem = $(ev.currentTarget).closest('.o_wslides_fs_sidebar_list_item');
            if ($elem.data('canAccess') === 'True') {
                var isQuiz = $elem.data('isQuiz');
                var isOra = $elem.data('isOra');
                var slideID = parseInt($elem.data('id'));
                var slide = findSlide(this.slideEntries, { id: slideID, isQuiz: isQuiz, isOra: isOra });
                this._updateSlideEntry(slide);
            }
        },
        /**
         * Actively changes the active tab in the sidebar so that it corresponds
         * the slide currently displayed
         *
         * @private
         * @param {Object} slide
         */
        _updateSlideEntry: function (slide) {
            if (this._slideEntry === slide) {
                return;
            }
            this._slideEntry = slide;
            this.$('.o_wslides_fs_sidebar_list_item.active').removeClass('active');
            var selector = '.o_wslides_fs_sidebar_list_item[data-id='+slide.id+'][data-is-quiz!="1"]';

            this.$(selector).addClass('active');
            this.trigger_up('change_slide', this._slideEntry);
        },

        /**
         * Binds left and right arrow to allow the user to navigate between slides
         *
         * @param {*} ev
         * @private
         */
        _onKeyDown: function (ev) {
            switch (ev.key) {
                case "ArrowLeft":
                    this.goPrevious();
                    break;
                case "ArrowRight":
                    this.goNext();
                    break;
            }
        },
    });