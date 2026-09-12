/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { actionService } from "@web/webclient/actions/action_service";

// ---------------------------------------------------------------------
// Find the element currently showing the scanned document preview.
// The exact container/class Odoo uses for the docked attachment
// preview differs between versions/layouts, so we try several known
// candidates in order and fall back to "whatever holds the preview
// iframe" before giving up.
// ---------------------------------------------------------------------
function findOmrPreviewContainer() {
    const selectors = [
        ".o_attachment_preview",
        ".o-mail-Attachment",
        ".o-mail-PopoutAttachmentView",
        ".o-mail-Chatter",
    ];
    for (const selector of selectors) {
        const el = document.querySelector(selector);
        if (el) {
            return el;
        }
    }
    // Last resort: locate the iframe/image actually rendering the
    // attachment and use its direct parent as the overlay container.
    const media = document.querySelector(
        '.o_form_view iframe[src*="/web/content"], .o_form_view iframe[src*="/web/image"], .o_form_view #attachment_img'
    );
    if (media && media.parentElement) {
        return media.parentElement;
    }
    return null;
}

function showOmrScanOverlay() {
    const container = findOmrPreviewContainer();
    if (!container) {
        return null;
    }
    if (getComputedStyle(container).position === "static") {
        container.classList.add("o_omr_scan_relative");
    }
    const overlay = document.createElement("div");
    overlay.className = "o_omr_scan_overlay";
    overlay.innerHTML =
        '<div class="o_omr_scan_overlay_backdrop"></div>' +
        '<div class="o_omr_scan_grid"></div>' +
        '<div class="o_omr_scan_line"></div>' +
        '<div class="o_omr_scan_label"><i class="fa fa-barcode me-2" aria-hidden="true"></i>Scanning OMR Sheet…</div>';
    container.appendChild(overlay);
    return { container, overlay };
}

function hideOmrScanOverlay(ref) {
    if (ref && ref.overlay && ref.overlay.parentNode) {
        ref.overlay.parentNode.removeChild(ref.overlay);
    }
}

// ---------------------------------------------------------------------
// Intercept the button click at the action-service level so we can show
// the overlay for the exact duration of the RPC — and hide it again the
// instant the scan finishes (successfully or not), before anything else
// is shown to the user.
// ---------------------------------------------------------------------
patch(actionService, {
    start(env, deps) {
        const result = super.start(env, deps);
        const originalDoActionButton = result.doActionButton.bind(result);
        result.doActionButton = async (clickParams) => {
            const isOmrScan =
                clickParams &&
                clickParams.resModel === "exam.omr.scanner" &&
                clickParams.name === "action_process_all";

            let overlayRef = null;
            let retryTimer = null;
            if (isOmrScan) {
                // The preview element might not be attached to the DOM yet
                // on the very first tick after click, so try immediately and
                // once more shortly after.
                overlayRef = showOmrScanOverlay();
                if (!overlayRef) {
                    retryTimer = setTimeout(() => {
                        overlayRef = showOmrScanOverlay();
                    }, 50);
                }
            }
            try {
                return await originalDoActionButton(clickParams);
            } finally {
                if (isOmrScan) {
                    if (retryTimer) {
                        clearTimeout(retryTimer);
                    }
                    hideOmrScanOverlay(overlayRef);
                }
            }
        };
        return result;
    },
});