# Meridian OSINT — Contexto y continuidad del proyecto

**Última actualización:** 17 de octubre de 2026  
**Repositorio:** https://github.com/nietogomezpablo-stack/geopolitical-osint-platform

> **Propósito de este documento:** permitir retomar el desarrollo sin perder decisiones, repetir trabajo ni modificar componentes que ya funcionan. Antes de proponer cambios, revisar este documento **y el código actual**. Las cifras y estados que aparecen aquí son observaciones de sesiones anteriores; pueden cambiar y deben verificarse.

## 1. Objetivo

Desarrollar **Meridian OSINT**, una plataforma de inteligencia de fuentes abiertas para recopilar, procesar, relacionar y visualizar acontecimientos geopolíticos mediante un dashboard web.

### Alcance acordado (decisión prioritaria)

- **País piloto: Níger, exclusivamente.**
- **No ampliar todavía** la recopilación a otros países.
- Una vez que la recopilación, el procesamiento, la base de datos y la visualización funcionen de forma fiable con Níger, **ampliar gradualmente a otros países del Sahel**.
- Priorizar la fiabilidad de los datos y la ausencia de duplicados frente al número de noticias o países cubiertos.

## 2. Entorno y arquitectura

- Equipo de desarrollo: ThinkPad con Ubuntu.
- Directorio local: `~/Projects/geopolitical-osint-platform`.
- Entorno virtual de Python: `.venv`.
- Backend: Python + Flask.
- Base de datos: SQLite.
- Frontend: HTML, CSS, JavaScript y Leaflet para el mapa.
- Internacionalización: i18next, con español, inglés, francés y árabe (RTL).
- API local: `http://127.0.0.1:5000`.
- Rutas conocidas: `/api/stats`, `/api/events`, `/api/events/<id>` y `/api/graph`.
- El Raspberry Pi **se reserva para un proyecto posterior de monitorización educativa autorizada**, no para Meridian OSINT.

## 3. Estructura de código conocida

### Recopiladores

- `src/collectors/gdelt_collector.py`: consulta GDELT sobre Níger y guarda los resultados en `data/raw/gdelt_niger.json`. La versión revisada utiliza una consulta específica (`"Niger" -Nigeria -"Niger Delta"`), hasta 50 artículos y reintentos limitados ante HTTP 429.
- `src/collectors/acled_collector.py`: solicita credenciales de myACLED, obtiene un token OAuth y consulta acontecimientos de Níger (límite configurado: 10). **No guardar credenciales ni tokens en GitHub.**
- `src/collectors/reliefweb_collector.py`: estaba vacío en la última revisión.

### Procesamiento y base de datos

Archivos existentes observados:

- `src/processing/clean_gdelt.py`
- `src/database/import_articles.py`
- `src/processing/extract_article_text.py`
- `src/processing/extract_entities.py`
- `src/processing/normalize_entities.py`
- `src/processing/resolve_entities.py`
- `src/processing/extract_events.py`
- `src/processing/geocode_events.py`
- `src/processing/store_locations.py`
- `src/processing/calculate_confidence.py`
- `src/database/check_database.py`
- `src/processing/export_events_geojson.py`
- `src/processing/export_intelligence_json.py`
- `src/processing/export_knowledge_graph.py`

También existen otros módulos para detección y resolución de candidatos, fechas, ubicaciones, roles y entidades. **No asumir que todos forman parte del pipeline principal sin comprobarlo.**

### Orquestación

`run_pipeline.py` ejecuta **14 pasos** de limpieza, importación, extracción, resolución, geocodificación, comprobación y exportación. En la versión compartida **no llama a los recopiladores al inicio**: procesa datos previamente descargados. Antes de integrarlos, comprobar el formato esperado por `clean_gdelt.py` y los efectos de volver a ejecutar cada paso.

### Web

- Servidor: `src/api/app.py`.
- Dashboard: `web/map.html`.
- Traducciones: `web/locales/es.json`, `en.json`, `fr.json`, `ar.json`.
- Se instaló un selector de idiomas con `install_meridian_i18n.py`.
- Copia de seguridad creada por el instalador: `web/map_before_languages.html`.

## 4. Funcionalidades demostradas

- Dashboard conectado a Flask y SQLite.
- Mapa interactivo con Leaflet.
- Estadísticas, filtros por texto, país, tipo y fecha, y cronología.
- Informes de acontecimientos con fuentes y confianza heurística.
- Exportaciones CSV y GeoJSON descargables.
- Interfaz en español, inglés, francés y árabe, con disposición RTL para árabe.
- Las noticias y sus títulos mantienen el idioma original.
- En una comprobación anterior había **3 acontecimientos**, de los cuales **2 tenían coordenadas**.
- En una conversación anterior se registró un Knowledge Graph con **104 nodos y 6 relaciones**; verificar estas cifras antes de reutilizarlas.

**Nota:** que una funcionalidad exista no significa que esté validada para grandes volúmenes de datos, múltiples ejecuciones o producción.

## 5. Problema pendiente prioritario

**Idempotencia del pipeline y control de duplicados.** Debemos verificar que ejecutar el procesamiento varias veces sobre las mismas noticias no crea artículos, entidades, acontecimientos ni relaciones duplicadas. No ejecutar repetidamente el pipeline sobre la base de datos principal sin comprobar antes cómo se comportan sus operaciones de inserción.

Plan recomendado:

1. Inspeccionar el esquema SQLite, claves únicas y scripts de importación/persistencia.
2. Hacer copia de seguridad de la base de datos antes de pruebas que escriban datos.
3. Medir recuentos iniciales de artículos, entidades, eventos y relaciones.
4. Ejecutar el pipeline en un entorno de prueba o con una copia de la base de datos.
5. Volver a ejecutarlo con los mismos datos y comparar recuentos e identificadores.
6. Corregir duplicados y operaciones no idempotentes, y añadir una prueba reproducible.
7. Solo entonces integrar el recopilador GDELT como primer paso y automatizar ejecuciones.

## 6. Hoja de ruta

### Versión piloto — Níger

- [x] Estructura de proyecto, API, base de datos y dashboard inicial.
- [x] Mapa, filtros, cronología, informes y exportaciones iniciales.
- [x] Internacionalización a cuatro idiomas.
- [ ] Auditar y garantizar idempotencia y deduplicación.
- [ ] Validar el flujo completo desde la descarga GDELT hasta el dashboard.
- [ ] Integrar recopilación en la orquestación sin romper el procesamiento existente.
- [ ] Incorporar control de errores, registros y límites de peticiones.
- [ ] Automatizar la ejecución periódica de forma segura.
- [ ] Añadir pruebas, documentación y criterios de calidad de datos.

### Ampliación posterior

- [ ] Extender de Níger a otros países del Sahel **solo tras validar el piloto**.
- [ ] Mejorar las relaciones del Knowledge Graph.
- [ ] Añadir alertas, análisis multilingüe, búsqueda semántica y otras capacidades avanzadas si aportan valor.

## 7. Forma de trabajo acordada

- **Revisar el contexto y el código antes de proponer nuevas funciones.**
- No dar por hecho que una parte está pendiente solo porque no aparezca en la conversación reciente.
- Mantener los cambios pequeños, verificables y reversibles.
- Evitar perder datos, duplicar registros o sobrescribir componentes funcionales.
- Explicar los comandos de terminal con claridad y avanzar con instrucciones prácticas.
- Cuando se entregue un archivo para descargar, **comprobar que existe realmente** antes de compartir el enlace.
- No publicar contraseñas, tokens, datos personales ni archivos de configuración sensibles en el repositorio.
- No añadir comentarios `#` en el código Python generado salvo que el usuario lo pida.

## 8. Punto exacto de continuación

**Fecha: 17 de octubre de 2026.**

Se revisaron `gdelt_collector.py`, `acled_collector.py`, `reliefweb_collector.py` y `run_pipeline.py`. El último archivo confirmó que el pipeline contiene 14 pasos de procesamiento pero no incluye una fase de descarga. El usuario recordó el acuerdo de mantener **Níger como único país piloto** y priorizar **idempotencia y deduplicación**.

**Próxima tarea:** revisar el esquema de la base de datos y los scripts que insertan artículos y eventos; diseñar una comprobación segura de idempotencia antes de integrar la recopilación automática.

**Para retomar en otra conversación:** «Lee `PROJECT_CONTEXT.md` del repositorio Meridian OSINT. Respeta las decisiones registradas y continúa desde el apartado 8, verificando primero el estado real del código».
