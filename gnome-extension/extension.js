import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import GLib from 'gi://GLib';

export default class HideInputSourceExtension extends Extension {
    enable() {
        this._timeout = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            this._hideKeyboardIndicator();
            return GLib.SOURCE_CONTINUE;
        });

        this._hideKeyboardIndicator();
    }

    disable() {
        if (this._timeout) {
            GLib.source_remove(this._timeout);
            this._timeout = null;
        }

        const indicator = Main.panel.statusArea.keyboard;

        if (indicator) {
            const actor = indicator.container || indicator;
            actor.show();
            actor.visible = true;
        }
    }

    _hideKeyboardIndicator() {
        const indicator = Main.panel.statusArea.keyboard;

        if (!indicator)
            return;

        const actor = indicator.container || indicator;

        actor.hide();
        actor.visible = false;
    }
}
