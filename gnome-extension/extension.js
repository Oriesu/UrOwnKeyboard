import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Keyboard from 'resource:///org/gnome/shell/ui/status/keyboard.js';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';

function getInputSourceManager() {
    try {
        if (Keyboard && typeof Keyboard.getInputSourceManager === 'function')
            return Keyboard.getInputSourceManager();
    } catch (e) {
    }

    return null;
}

export default class HideInputSourceExtension extends Extension {
    enable() {
        this._hidden = [];
        this._timeoutId = 0;
        this._lastRequest = '';

        this._hideNativeInputIndicator();
        this._startRequestWatcher();
    }

    disable() {
        if (this._timeoutId) {
            GLib.source_remove(this._timeoutId);
            this._timeoutId = 0;
        }

        for (const obj of this._hidden || []) {
            if (obj && typeof obj.show === 'function')
                obj.show();
        }

        this._hidden = [];
    }

    _hideNativeInputIndicator() {
        const possibleNames = [
            'keyboard',
            'inputSource',
            'input-source',
        ];

        for (const name of possibleNames) {
            const item = Main.panel.statusArea[name];
            if (!item)
                continue;

            const objects = [
                item,
                item.container,
                item.actor,
                item._indicator,
            ];

            for (const obj of objects) {
                if (obj && typeof obj.hide === 'function') {
                    obj.hide();
                    this._hidden.push(obj);
                }
            }
        }
    }

    _requestPath() {
        const dir = GLib.build_filenamev([
            GLib.get_home_dir(),
            '.config',
            'teclado-indicador',
        ]);

        return GLib.build_filenamev([
            dir,
            'gnome-wayland-source-request',
        ]);
    }

    _startRequestWatcher() {
        this._timeoutId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            1,
            () => {
                this._processRequest();
                return GLib.SOURCE_CONTINUE;
            }
        );
    }

    _processRequest() {
        const path = this._requestPath();
        const file = Gio.File.new_for_path(path);

        if (!file.query_exists(null))
            return;

        let contents;
        try {
            [, contents] = file.load_contents(null);
        } catch (e) {
            return;
        }

        const text = new TextDecoder().decode(contents).trim();

        if (!text || text === this._lastRequest)
            return;

        this._lastRequest = text;

        const parts = text.split(/\s+/);
        const index = parseInt(parts[0]);

        if (Number.isNaN(index))
            return;

        this._activateInputSource(index);
    }

    _activateInputSource(index) {
        const manager = getInputSourceManager();

        if (!manager || !manager.inputSources)
            return;

        const source = manager.inputSources[index];

        if (source && typeof source.activate === 'function')
            source.activate();
    }
}
