# Incidencias pendientes

## UOK-2026-11-25 — Bloqueo crítico de la actualización de xkb-data 2.46

**Estado:** causa del bloqueo confirmada; reparación local verificada incluso tras reiniciar; corrección de UOK y recuperación funcional de los perfiles pendientes.
**Severidad:** crítica (bloqueo del gestor de paquetes y de la actualización de componentes esenciales).
**Entorno:** Ubuntu 26.04.1 LTS (Resolute), actualización de xkb-data 2.41-2ubuntu1.1 a 2.46-2.

### Desencadenante y causa raíz

El usuario precisa que los fallos aparecieron después de determinadas actualizaciones del sistema, no necesariamente durante una instalación o actualización de UOK. La transición de XKB es el desencadenante concreto demostrado. Los archivos personalizados y backups ya presentes en la raíz XKB constituían una incompatibilidad latente: una instalación que funcionaba con el árbol anterior podía dejar de ser compatible al cambiar el empaquetado del sistema. No se conoce la secuencia completa de actualizaciones anteriores, la fecha exacta de la primera aparición ni la versión instalada de UOK que generó cada archivo.

Distinguir el desencadenante externo (actualización de xkb-data y cambio de estructura de directorios) de la contribución de UOK (archivos adicionales en un árbol administrado por el gestor de paquetes). No atribuir a UOK todas las incidencias concurrentes de Ubuntu.


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

5. Tras reiniciar el 25 de noviembre de 2026 con el kernel 7.0.0-44-generic, se verificó que xkb-data seguía en 2.46-2 y que la ruta XKB resolvía a /usr/share/xkeyboard-config-2. `dpkg --audit` no listó incidencias, `apt-get check` terminó sin errores y `systemctl --failed` mostró cero unidades de sistema fallidas. Esto confirma la persistencia de la reparación de APT y XKB, no la activación ni el funcionamiento de los perfiles UOK, que no se probaron en ese registro.

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

### Riesgos derivados de actualizaciones del sistema (pendientes de reproducir)

- Una actualización ordinaria de xkb-data puede reemplazar reglas oficiales modificadas, dejar referencias a símbolos inexistentes o invalidar backups de otra versión. La pérdida de perfiles visibles o un mapa de teclas incorrecto son riesgos a verificar, no síntomas nuevos confirmados.
- Las actualizaciones de libxkbcommon, Xorg, GNOME, KDE/Plasma, Cinnamon, keyd, Python o dependencias del indicador pueden cambiar los mecanismos de descubrimiento, compilación, selección de fuentes y arranque. Validar por separado; no se ha probado un fallo en cada componente.
- El arranque o la recuperación automática de UOK no deben reintroducir archivos obsoletos durante una transacción APT/dpkg, seguir enlaces hacia un árbol no previsto ni escribir sobre registros oficiales de otra versión. Una incompatibilidad debe producir diagnóstico explícito y una salida segura, sin inutilizar la distribución estándar.
- La simulación posterior de autoremove propuso, entre otros, libxkbcommon-dev y componentes de KDE/Wayland. No se ejecutó la retirada. Comprobar si UOK necesita alguno para instalación, compilación o ejecución y declarar sus dependencias correctamente; no se ha establecido que su retirada afecte a UOK ni que UOK haya causado la lista de paquetes huérfanos.

### Matriz mínima de regresión y recuperación

| Escenario | Resultado exigido |
| --- | --- |
| Instalación limpia con XKB anterior y con XKB 2.46+ | Instalar y activar perfiles sin generar residuos que bloqueen el gestor de paquetes. |
| Actualización de xkb-data con UOK instalado, tanto dentro de una versión de Ubuntu como durante un cambio de distribución | Completar la transacción, sin paquetes sin configurar; preservar datos y poder reconstruir integraciones compatibles. |
| Transición de directorio a enlace simbólico con residuos heredados | Detectar y ofrecer migración selectiva y reversible antes de la actualización; preservar archivos de terceros. |
| Actualización que reemplaza reglas/símbolos oficiales | No restaurar ciegamente backups antiguos; regenerar solo integraciones propias a partir del estado vigente. |
| Actualización interrumpida y posterior reparación de dpkg | No ejecutar escrituras concurrentes ni agravar el estado; permitir diagnóstico y recuperación manual segura. |
| Reinicio, cierre de sesión y cambio de escritorio tras actualización | Verificar perfiles, fuentes estándar, remapeos y persistencia en GNOME, KDE y Cinnamon, en X11 y Wayland cuando estén disponibles. |
| Desinstalación, reinstalación y migración repetidas | Operaciones idempotentes; no eliminar datos ajenos ni dejar residuos en el árbol oficial. |

Para las pruebas registrar versiones antes/después de UOK, distribución, xkb-data, libxkbcommon, escritorio, tipo de sesión y keyd; identificar archivos mediante manifiestos y propietarios de dpkg, conservar logs sanitizados y comprobar el resultado de dpkg --audit y apt-get check. Probar con perfiles reales en un entorno aislado y comprobar recuperación de una distribución estándar antes de declarar compatibilidad.

### Criterio de cierre

UOK debe permitir actualizar xkb-data sin bloquear dpkg, conservar perfiles y remapeos, y evitar modificar o restaurar archivos oficiales incompatibles. El arreglo local no equivale a una corrección del producto.

### Síntomas independientes

La falta inicial de Vercel CLI se resolvió mediante npx; los avisos de APT por archivos .list.migrate desaparecieron al respaldarlos fuera de sources.list.d. No hay evidencia de que UOK causara esos síntomas ni el error de conexión Git de Vercel. Se observó además una discrepancia entre el módulo NVIDIA 580.178.04 y las bibliotecas 580.196.07; se resolvió instalando NVIDIA 595.99.02 y retirando selectivamente bibliotecas EGL incompatibles; nvidia-smi confirmó el controlador operativo tras reiniciar. El módulo DKMS r8168 también figuró instalado para el nuevo kernel. Estos problemas y las actualizaciones restantes de Ubuntu quedan fuera de esta incidencia: no existe evidencia de causalidad con UOK.
