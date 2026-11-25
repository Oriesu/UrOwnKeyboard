# Incidencias pendientes

## UOK-2026-11-25 — Bloqueo crítico de la actualización de xkb-data 2.46

**Estado:** causa del bloqueo confirmada; sistema local reparado; corrección de UOK pendiente.
**Entorno:** Ubuntu 26.04.1 LTS (Resolute), actualización de xkb-data 2.41-2ubuntu1.1 a 2.46-2.

### Causa y alcance

El preinst de xkb-data 2.46-2 utiliza dpkg-maintscript-helper para convertir /usr/share/X11/xkb de directorio a enlace simbólico. El helper rechaza la migración si encuentra archivos ajenos al paquete. El registro de APT del 25 de noviembre de 2026 muestra:

    dpkg-maintscript-helper: error: directory '/usr/share/X11/xkb' contains files not owned by package xkb-data:all, cannot switch to symlink

La actualización se abortó antes de desempaquetar el paquete. keyboard-configuration exigía xkb-data >= 2.46~, dejando 24 paquetes sin configurar, incluidos Xorg, Cinnamon, KWin y ubuntu-minimal. No había paquetes retenidos, desviaciones XKB registradas ni atributos de inmutabilidad en los archivos de reglas inspeccionados.

Archivos señalados por el helper (rutas relativas a /usr/share/X11/xkb):

- rules/evdev.uok-backup
- rules/evdev.lst.bak
- rules/evdev.xml.uok-backup
- rules/base.xml.bak
- rules/base.lst.bak
- rules/evdev.xml.bak
- symbols/uok_test_wayland
- symbols/uok_kde_test
- symbols/dvorak_esprog
- symbols/esprog.bak.altgr
- symbols/esprog
- symbols/dvorak
- symbols/es.bak

Hay copias y símbolos claramente asociados a UOK, junto con otros archivos personalizados cuyo origen individual todavía no está establecido. La modificación de evdev.xml también fue detectada por dpkg -V. No se debe deducir que todos los archivos ajenos a dpkg pertenecen a UOK.

### Recuperación local realizada y verificada

1. Se respaldaron el árbol XKB, los perfiles UOK, keyd y las fuentes de entrada GNOME fuera del árbol de XKB.
2. Se trasladaron los 13 archivos indicados a un directorio de respaldo externo, conservando su estructura rules/ y symbols/. No se eliminaron los perfiles originales ni se forzó dpkg.
3. Se ejecutó `sudo apt-get --no-remove --fix-broken install`.
4. Se verificó xkb-data 2.46-2 y keyboard-configuration 1.237ubuntu3.1; los 24 paquetes pendientes se configuraron correctamente. /usr/share/X11/xkb pasó a ser un enlace simbólico a /usr/share/xkeyboard-config-2. `sudo dpkg --audit` y `sudo apt-get check` terminaron sin errores.

No restaurar íntegramente el árbol XKB anterior ni reintroducir las copias .bak o .uok-backup en el árbol gestionado por el paquete. La recuperación de los perfiles y la compatibilidad de UOK con la nueva versión aún requieren validación. En otros equipos, inspeccionar primero el registro del fallo y los propietarios de los archivos; no retirar archivos indiscriminadamente.

### Correcciones de UOK pendientes

- [ ] Auditar todas las escrituras en árboles XKB de sistema: instalación, importación, activación, limpieza, recuperación, desinstalación y copias de seguridad.
- [ ] Guardar backups y metadatos en una ubicación externa al árbol gestionado por el paquete.
- [ ] Detectar dinámicamente la raíz XKB y los cambios de versión, incluidos enlaces simbólicos, sin reemplazarlos.
- [ ] Investigar ubicaciones XKB externas compatibles con cada compositor y escritorio; validar activación, enumeración y persistencia, especialmente en GNOME Wayland. No asumir que las rutas de usuario son suficientes en todos los entornos.
- [ ] Diseñar una migración reversible de registros heredados, con comprobación de propiedad, manifiesto de archivos UOK y modo dry-run. No retirar archivos personalizados de terceros ni restaurar reglas oficiales antiguas sobre una versión nueva.
- [ ] Añadir diagnóstico no destructivo a uok doctor para detectar residuos que puedan bloquear actualizaciones.
- [ ] Añadir pruebas de regresión de la transición directorio a symlink, actualización de paquete, conservación de perfiles y ausencia de escrituras de backups dentro de XKB; comprobar también X11 y Wayland.
- [ ] Verificar la actualización en un entorno aislado con paquetes reales antes de considerar resuelta la incidencia.

### Criterio de cierre

UOK debe permitir actualizar xkb-data sin bloquear dpkg, conservar perfiles y remapeos, y evitar modificar o restaurar archivos oficiales incompatibles. El arreglo local no equivale a una corrección del producto.

### Síntomas independientes

La falta inicial de Vercel CLI se resolvió mediante npx; los avisos de APT por archivos .list.migrate desaparecieron al respaldarlos fuera de sources.list.d. No hay evidencia de que UOK causara esos síntomas ni el error de conexión Git de Vercel. Se observó además una discrepancia entre el módulo NVIDIA 580.178.04 y las bibliotecas 580.196.07; su reparación queda fuera de esta incidencia y no se atribuye a UOK.
