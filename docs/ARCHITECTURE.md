# Arquitectura y mantenimiento

## Componentes principales

| Ruta | Responsabilidad |
| --- | --- |
| `uok` | CLI, importación, activación, limpieza de registros Wayland, diagnósticos |
| `teclado-indicador.py` | Indicador GTK/AppIndicator, menú, selección y actualización de perfiles |
| `uok-layout-editor.py` | Edición visual XKB y reglas de keyd; exportación/importación |
| `uok_xkb_symbols.py`, `uok_xkb_sources.py` | Utilidades XKB y lectura de fuentes |
| `uok_backends/profile_store.py` | Identificadores, persistencia y duplicados de perfiles |
| `uok_backends/system_sources.py` | Fuentes de escritorio GNOME, KDE, XFCE, LXQt e IBus |
| `uok_backends/system_xkb_install.py` | Registro XKB privilegiado y fuentes GNOME Wayland |
| `uok_backends/gnome_wayland.py`, `overrides.py` | Selección GNOME Wayland e integración con el indicador |
| `uok_backends/{kde,xfce,mate,cinnamon,lxqt}.py` | Adaptadores de escritorio X11 y panel |
| `uok_backends/native_indicators.py` | Ocultación de indicadores de teclado nativos |
| `uok_backends/keyd.py`, `helpers/keyd-aplicar-conf` | Aplicación y neutralización de keyd |
| `gnome-extension/` | Ocultar el indicador GNOME y procesar solicitudes de fuente |
| `install.sh`, `uninstall.sh`, `make-release.sh` | Instalación, desinstalación y empaquetado |

## Flujo de datos

1. **Importar:** `uok import` copia símbolos XKB a `~/.xkb/symbols`, valida la compilación y guarda el JSON en `~/.config/teclado-indicador/profiles`.
2. **Activar en X11:** si procede, se aplica un archivo keyd; luego se ejecuta XKB. Los fallos keyd no impiden necesariamente aplicar XKB.
3. **Activar en GNOME Wayland:** UOK asegura la instalación privilegiada de una fuente XKB reconocible por GNOME; solicita la activación al compositor, intenta sincronizar Xwayland y aplica keyd.
4. **Estado visible:** `current-profile.json` almacena la selección registrada y el indicador filtra fuentes técnicas duplicadas de UOK.
5. **Eliminar:** UOK borra los archivos propios y trata de retirar los símbolos y las entradas de registro asociadas en GNOME Wayland.

La extensión GNOME Shell observa `~/.config/teclado-indicador/gnome-wayland-source-request` y gestiona solicitudes de cambio de fuente. Esto no equivale a compatibilidad universal con otros compositores Wayland.

## Privilegios y alcance

El helper `/usr/local/sbin/keyd-aplicar-conf` se ejecuta como administrador mediante una regla sudoers específica. Modifica `/etc/keyd/default.conf` y recarga/reinicia keyd. El registro XKB para GNOME Wayland usa `pkexec`/`sudo` y escribe bajo `/usr/share/X11/xkb/`.

Algunas integraciones también cambian archivos de configuración del panel o preferencias de IBus. Son efectos de sistema/usuario, no solo cambios de interfaz.

## Comprobaciones de desarrollo

Verificaciones estáticas, ejecutadas desde la raíz del repositorio:

```bash
python3 -m py_compile uok teclado-indicador.py uok-layout-editor.py uok_xkb_symbols.py uok_xkb_sources.py
find uok_backends -type f -name '*.py' -exec python3 -m py_compile {} \;
bash -n install.sh uninstall.sh make-release.sh helpers/keyd-aplicar-conf
python3 uok --help
```

Comprobaciones no destructivas en un entorno Linux apropiado:

```bash
python3 uok list
python3 uok doctor --system-only
python3 uok cleanup-wayland --dry-run
```

Las pruebas de **importación, activación, eliminación y recuperación** sí cambian archivos o el estado del teclado. Hazlas en una sesión o máquina de pruebas con un segundo método de entrada y copias de seguridad. No se incluye aquí una afirmación de que exista una matriz de CI automatizada o de que todos los escritorios hayan sido validados.

## Empaquetado

```bash
./make-release.sh dev
```

Genera un archivo `release/UrOwnKeyboard-dev.tar.gz` con los scripts, los backends y la documentación del proyecto. El script comprueba compilación Python y sintaxis de algunos scripts de shell antes de empaquetar.

## Trabajos técnicos pendientes

- Añadir pruebas automatizadas y una matriz de escritorios/servidores gráficos en CI.
- Verificar las versiones declaradas de GNOME Shell y documentar resultados reales por distribución.
- Comprobar que la desinstalación y la ocultación de indicadores respetan las preferencias previas del usuario.
- Validar en distintas sesiones GNOME Wayland la activación inmediatamente después de registrar una fuente.
