/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useRef, onMounted, onWillUnmount, markup } from "@odoo/owl";

class UniversityAIAssistant extends Component {
    static template = "university_management.AIAssistant";

    setup() {
        this.messagesRef = useRef("messages");
        this.wrapperRef = useRef("wrapper");

        this.state = useState({
            isOpen: false,
            isLoading: false,
            inputText: "",
            messages: [
                {
                    role: "assistant",
                    content: "👋 Hello! I'm your University AI Assistant. Ask me anything about students, fees, attendance, exam results, scholarships, faculty, and more!\n\nTry asking:\n• *Has John paid his fees?*\n• *Show students with attendance below 75%*\n• *What is the CGPA of student RA001?*",
                    id: 0,
                }
            ],
            conversationHistory: [],
        });

        // Click-outside handler
        this._onDocumentClick = this._onDocumentClick.bind(this);

        onMounted(() => {
            document.addEventListener("mousedown", this._onDocumentClick);
        });

        onWillUnmount(() => {
            document.removeEventListener("mousedown", this._onDocumentClick);
        });
    }

    // ── Click outside to close ────────────────────────────────────────────

    _onDocumentClick(ev) {
        if (!this.state.isOpen) return;
        const wrapper = this.wrapperRef.el;
        if (wrapper && !wrapper.contains(ev.target)) {
            this.state.isOpen = false;
        }
    }

    // ── Open / Close ──────────────────────────────────────────────────────

    toggleChat() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen) {
            setTimeout(() => this._scrollToBottom(), 50);
        }
    }

    closeChat() {
        this.state.isOpen = false;
    }

    clearChat() {
        this.state.messages = [
            {
                role: "assistant",
                content: "Chat cleared. How can I help you?",
                id: Date.now(),
            }
        ];
        this.state.conversationHistory = [];
    }

    // ── Sending messages ──────────────────────────────────────────────────

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    onInput(ev) {
        this.state.inputText = ev.target.value;
    }

    async sendMessage() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isLoading) return;

        this.state.inputText = "";

        this.state.messages.push({
            role: "user",
            content: text,
            id: Date.now(),
        });

        this.state.conversationHistory.push({
            role: "user",
            content: text,
        });

        this.state.isLoading = true;
        this._scrollToBottom();

        try {
            const result = await this._jsonRpc("/university/ai/chat", {
                messages: this.state.conversationHistory,
            });

            if (result.error) {
                this.state.messages.push({
                    role: "assistant",
                    content: "⚠️ Error: " + result.error,
                    id: Date.now(),
                    isError: true,
                });
            } else {
                const responseText = result.response;

                this.state.conversationHistory.push({
                    role: "assistant",
                    content: responseText,
                });

                this.state.messages.push({
                    role: "assistant",
                    content: responseText,
                    id: Date.now(),
                });
            }
        } catch (err) {
            this.state.messages.push({
                role: "assistant",
                content: "⚠️ Error: " + (err.message || "Network error. Please try again."),
                id: Date.now(),
                isError: true,
            });
        } finally {
            this.state.isLoading = false;
            this._scrollToBottom();
        }
    }

    // ── JSON-RPC helper (Odoo 18 compatible) ─────────────────────────────

    async _jsonRpc(url, params) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                id: Date.now(),
                params: params,
            }),
        });

        if (!response.ok) {
            throw new Error("HTTP error: " + response.status);
        }

        const data = await response.json();

        if (data.error) {
            throw new Error(
                (data.error.data && data.error.data.message) ||
                data.error.message ||
                "Server error"
            );
        }

        return data.result;
    }

    // ── Suggested questions ───────────────────────────────────────────────

    askSuggested(question) {
        this.state.inputText = question;
        this.sendMessage();
    }

    get suggestions() {
        return [];
    }

    // ── Formatting ────────────────────────────────────────────────────────

    formatMessage(content) {
        let html = content
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.+?)\*/g, "<em>$1</em>")
            .replace(/`(.+?)`/g, "<code>$1</code>")
            .replace(/^### (.+)$/gm, "<h4>$1</h4>")
            .replace(/^## (.+)$/gm, "<h3>$1</h3>")
            .replace(/^• (.+)$/gm, "<li>$1</li>")
            .replace(/^- (.+)$/gm, "<li>$1</li>")
            .replace(/(<li>.*<\/li>\n?)+/g, function(m) { return "<ul>" + m + "</ul>"; })
            .replace(/\n/g, "<br>");
        return markup(html);
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    _scrollToBottom() {
        const el = this.messagesRef.el;
        if (el) {
            el.scrollTop = el.scrollHeight;
        }
    }
}

registry.category("main_components").add("UniversityAIAssistant", {
    Component: UniversityAIAssistant,
});