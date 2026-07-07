/** @odoo-module **/

document.addEventListener("DOMContentLoaded", () => {
    function handleSend(input, chatHtmlDiv) {
        const userMsg = input.value.trim();
        if (userMsg) {
            const tempId = `temp-${Date.now()}`;
            const div = document.createElement("div");
            div.className = "chat-bubble chat-bubble-user temp-user-bubble";
            div.setAttribute("data-temp-id", tempId);
            div.innerText = userMsg;
            chatHtmlDiv.appendChild(div);
            chatHtmlDiv.scrollTop = chatHtmlDiv.scrollHeight;
            setTimeout(() => {
                input.value = '';
            }, 100);
        }
    }

    function attachEnterListener() {
        // Support both textarea (Odoo 16+/OWL) and input fallback
        const input = document.querySelector("textarea[name='new_message'], .new-message-input input");
        const sendBtn = document.querySelector("button[name='send_message']");
        const chatHtmlDiv = document.querySelector("div[name='chat_html'] .o_readonly");
        if (input && !input._enterListenerAttached) {
            input._enterListenerAttached = true;
            input.addEventListener("keydown", function (e) {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (sendBtn) sendBtn.click();
                }
            });
        }
        // Ensure clicking send always renders the temp bubble immediately
        if (sendBtn && chatHtmlDiv && input && !sendBtn._clickListenerAttached) {
            sendBtn._clickListenerAttached = true;
            sendBtn.addEventListener("click", function () {
                if (input.value && input.value.trim()) {
                    handleSend(input, chatHtmlDiv);
                }
            });
        }
    }

    // Use MutationObserver to re-attach listener when DOM changes (menu switch, panel open, etc)
    const observer = new MutationObserver(() => {
        attachEnterListener();
        // Agar backend se wahi question aa gaya hai, toh temp bubble hata do
        const chatHtmlDiv = document.querySelector("div[name='chat_html'] .o_readonly");
        if (chatHtmlDiv) {
            const tempBubbles = chatHtmlDiv.querySelectorAll('.temp-user-bubble');
            tempBubbles.forEach(tempBubble => {
                const tempText = tempBubble.innerText.trim();
                // Real bubble (not temp) with same text
                const realBubble = Array.from(chatHtmlDiv.querySelectorAll('.chat-bubble-user:not(.temp-user-bubble)')).find(b => b.innerText.trim() === tempText);
                if (realBubble) {
                    tempBubble.remove();
                }
            });
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Initial attach in case already present
    attachEnterListener();
});