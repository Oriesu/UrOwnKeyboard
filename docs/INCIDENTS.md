# Incidencias pendientes

## UOK-2026-11-25 — Posible interferencia con el uso de herramientas de desarrollo en Ubuntu

**Estado:** pendiente de investigar y corregir.

### Evidencia observada

Durante una operación de desarrollo en Ubuntu, la ejecución de `vercel link --scope <equipo>` devolvió `vercel: no se encontró la orden`. El intento posterior de instalarlo con `sudo apt install vercel` devolvió `Error: No se ha podido localizar el paquete vercel`. APT también informó de que omitía varios archivos de `/etc/apt/sources.list.d/` con extensión `.list.migrate`.

El usuario identificó UOK como origen del problema. La relación causal concreta (remapeo de teclas, instalación, entorno de ejecución u otra interacción) todavía no está documentada ni reproducida. La falta del comando Vercel y los avisos de APT no demuestran por sí solos un defecto de UOK; deben investigarse por separado. Vercel CLI normalmente se distribuye mediante npm, no como paquete de APT.

### Investigación pendiente

- [ ] Identificar el síntoma concreto atribuido a UOK y el perfil activo, la sesión gráfica y la versión instalada.
- [ ] Comparar la entrada de teclado y la ejecución de los mismos comandos con UOK activo y con una fuente de teclado normal y remapeos neutralizados de forma reversible.
- [ ] Revisar XKB, keyd y los atajos/remapeos del perfil afectado; comprobar si los comandos introducidos coinciden literalmente con los esperados.
- [ ] Comprobar por separado la disponibilidad de `node`, `npm` y `vercel`, y la resolución del comando en `PATH`, sin volcar variables de entorno sensibles.
- [ ] Revisar si el instalador o los mecanismos de recuperación de UOK pueden modificar fuentes APT, archivos `.list.migrate` o el entorno de ejecución; no atribuir esos cambios sin evidencia.
- [ ] Reproducir el fallo, corregir únicamente la causa confirmada y añadir una prueba de regresión cuando sea viable.

### Criterio de cierre

Identificar y documentar la causa raíz; demostrar que el comportamiento atribuible a UOK desaparece sin alterar perfiles ajenos ni configuraciones de desarrollo; verificar que la corrección es reversible y no introduce regresiones. No eliminar archivos APT ni modificar el sistema durante el diagnóstico inicial.
