# UrOwnKeyboard (UOK)

**UrOwnKeyboard** es un gestor de distribuciones de teclado personalizadas para Linux. Combina configuraciones **XKB** con remapeos opcionales de **keyd** y ofrece una CLI, un indicador de escritorio y un editor visual GTK.

El proyecto está en desarrollo. Implementa varias integraciones de escritorio, pero **la presencia de código para un entorno no equivale a compatibilidad verificada en todas sus versiones**.

## Qué permite hacer

- Crear, importar, activar y eliminar perfiles de teclado XKB.
- Editar visualmente las cuatro capas de símbolos (normal, Shift, AltGr y Shift+AltGr) y exportar el resultado.
- Asociar reglas específicas de `keyd` para remapeos físicos y atajos.
- Mostrar tanto las fuentes de entrada detectadas del sistema como los perfiles propios, sin duplicar en el menú los perfiles registrados internamente para GNOME Wayland.
- Gestionar perfiles desde el indicador o desde `uok`; ejecutar diagnósticos y buscar registros UOK obsoletos en GNOME Wayland.
- Intentar ocultar indicadores nativos de teclado/IBus que interfieran con el propio.

## Compatibilidad y limitaciones

| Entorno | Implementación existente | Observaciones |
| --- | --- | --- |
| GNOME en X11 | Fuentes GNOME/XKB, CLI, editor e indicador | Requiere revisar la integración AppIndicator y la extensión en cada versión |
| GNOME en Wayland | Integración **experimental** para perfiles XKB personalizados | Instala una fuente XKB de sistema, modifica el registro XKB; tras la primera instalación puede requerir cerrar sesión |
| KDE Plasma, XFCE, MATE, Cinnamon y LXQt en X11 | Detección de fuentes y adaptadores de panel/ajustes | Compatibilidad práctica dependiente de versión, distribución y configuración del panel |
| Otros escritorios Wayland | Sin soporte general garantizado | No se debe asumir que `setxkbmap` cambia el mapa nativo Wayland |

`keyd` actúa sobre los eventos de entrada a nivel del sistema; su instalación y configuración afectan al teclado más allá de una aplicación concreta. En GNOME Wayland, la activación de fuentes IBus no XKB **no está cubierta** por la ruta especial del indicador.

Más información: [compatibilidad](docs/COMPATIBILITY.md).

## Instalación

**Objetivo del instalador:** Ubuntu, Debian y derivadas con `apt`, sesión gráfica y `systemd`. Antes de ejecutarlo, [lee los cambios de sistema que realiza](docs/OPERATIONS.md): instala paquetes y posiblemente `keyd`, crea un helper y una regla de `sudoers`, habilita autoinicio, y puede modificar preferencias del panel. No es una instalación aislada dentro del directorio del repositorio.

```bash
git clone https://github.com/Oriesu/UrOwnKeyboard.git
cd UrOwnKeyboard
./install.sh
```

El script comprueba sintaxis Python y el registro XKB antes de copiar los componentes. Puede solicitar privilegios administrativos. **Cierra sesión y vuelve a entrar** si utilizas GNOME para que la extensión y las fuentes nuevas se carguen correctamente.

No ejecutes el instalador ni importes disposiciones de terceros sin revisar primero los archivos XKB/`keyd.conf` que van a aplicarse.

## Inicio rápido

```bash
uok list
uok import --name "Mi teclado" --xkb ./mi_teclado
uok import --name "Teclado con atajos" --xkb ./mi_teclado --keyd ./mi_teclado.keyd.conf
uok activate mi_teclado
uok current
uok show-keyd
uok editor
uok doctor
```

El ID real del perfil aparece en `uok list`. También puedes activar una fuente XKB detectada del sistema, por ejemplo `uok activate es` si está disponible.

Para consultar perfiles técnicos de GNOME Wayland que hayan quedado obsoletos, comienza **siempre** por:

```bash
uok cleanup-wayland --dry-run
```

La limpieza real modifica fuentes GNOME y, cuando corresponde, archivos XKB de sistema.

**Referencia completa:** [comandos y ejemplos](docs/CLI.md).

## Indicador y editor visual

El indicador muestra fuentes de sistema y perfiles UOK. Desde él puedes activar una configuración, consultar su estado, abrir el editor, importar perfiles, acceder a los ajustes del escritorio, eliminar un perfil o recargar la lista.

El editor se abre con `uok editor` o desde **New configuration → Open visual editor**. Permite partir de una fuente existente, modificar símbolos por tecla y niveles, capturar teclas adicionales, añadir reglas de `keyd`, exportar XKB/`keyd.conf` y guardar el resultado como perfil UOK.

En **GNOME Wayland** se necesita registrar las distribuciones personalizadas como fuentes GNOME/XKB del sistema. Si acabas de importar una por primera vez, **cierra sesión y vuelve a entrar antes de comprobarla**; una activación solicitada no implica que GNOME Shell ya haya recargado el registro.

## Documentación

- [CLI: comandos, opciones y ejemplos](docs/CLI.md)
- [Compatibilidad: escritorios y GNOME Wayland](docs/COMPATIBILITY.md)
- [Instalación, seguridad, diagnóstico y desinstalación](docs/OPERATIONS.md)
- [Arquitectura, archivos y verificaciones](docs/ARCHITECTURE.md)

## Estado del proyecto

Se trata de una herramienta en evolución, no de un producto validado de forma exhaustiva en todas las combinaciones de sesión y escritorio. La ruta GNOME Wayland, la detección de perfiles del sistema, la gestión de indicadores nativos y la limpieza de fuentes requieren pruebas en entornos reales.

El repositorio no incluye actualmente un archivo `LICENSE`; su disponibilidad pública en GitHub **no establece por sí misma una licencia de reutilización**.
