/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { Component, useRef, useState } from "@odoo/owl";

/**
 * Bulk OMR Multi Upload widget
 * -----------------------------
 * Renders a single button that opens the browser's native file picker
 * with `multiple` enabled, so the user can select as many scanned
 * OMR files (PDF, JPG, PNG, DOC, DOCX ...) as they want in one go
 * (drag & drop onto the zone also works).
 *
 * Each selected file is turned into a new
 * `exam.omr.bulk.scan.wizard.line` record on the wizard, exactly as
 * if the user had clicked "Add a line" and uploaded the file by hand
 * — just automated for every file picked.
 */
class BulkOmrMultiUploadWidget extends Component {
    static template = "university_management.BulkOmrMultiUploadWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInput = useRef("bulkOmrFileInput");
        this.state = useState({
            uploading: false,
            total: 0,
            done: 0,
        });
    }

    get lineFieldName() {
        return "scan_line_ids";
    }

    onPickClick() {
        this.fileInput.el.click();
    }

    onDragOver(ev) {
        ev.preventDefault();
        ev.currentTarget.classList.add("o_bulk_omr_drop_hover");
    }

    onDragLeave(ev) {
        ev.currentTarget.classList.remove("o_bulk_omr_drop_hover");
    }

    async onDrop(ev) {
        ev.preventDefault();
        ev.currentTarget.classList.remove("o_bulk_omr_drop_hover");
        const files = ev.dataTransfer && ev.dataTransfer.files;
        await this._processFiles(files);
    }

    async onFileInputChange(ev) {
        await this._processFiles(ev.target.files);
        // reset so selecting the exact same file(s) again re-triggers change
        ev.target.value = "";
    }

    async _processFiles(fileList) {
        const files = fileList ? [...fileList] : [];
        if (!files.length) {
            return;
        }

        this.state.uploading = true;
        this.state.total = files.length;
        this.state.done = 0;

        try {
            const record = this.props.record;

            // A transient wizard record only gets a real database id once
            // it has been saved at least once. Force that save so the
            // uploaded lines can be attached to a real wizard_id.
            if (!record.resId) {
                const saved = await record.save({ reload: false });
                if (!saved) {
                    this.notification.add(
                        _t("Please fill in the wizard fields before uploading files."),
                        { type: "danger" }
                    );
                    this.state.uploading = false;
                    return;
                }
            }

            const wizardId = record.resId;

            for (const file of files) {
                try {
                    const data = await this._readFileAsBase64(file);
                    await this.orm.create("exam.omr.bulk.scan.wizard.line", [
                        {
                            wizard_id: wizardId,
                            scanned_file: data,
                            scanned_filename: file.name,
                        },
                    ]);
                } catch (error) {
                    console.error("Bulk OMR upload failed for", file.name, error);
                    this.notification.add(
                        _t("Could not upload: ") + file.name,
                        { type: "danger" }
                    );
                } finally {
                    this.state.done += 1;
                }
            }

            // Refresh the wizard so the newly created lines show up
            // in the "Upload Scanned Sheets" list below.
            await record.load();
            this.props.record.model.notify();

            this.notification.add(
                `${this.state.done} ${_t("file(s) added.")}`,
                { type: "success" }
            );
        } finally {
            this.state.uploading = false;
        }
    }

    _readFileAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                // reader.result looks like "data:<mime>;base64,<data>"
                const base64 = reader.result.split(",")[1] || "";
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }
}

registry.category("fields").add("bulk_omr_multi_upload", {
    component: BulkOmrMultiUploadWidget,
});