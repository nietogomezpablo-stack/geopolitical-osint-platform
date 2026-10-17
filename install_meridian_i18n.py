from pathlib import Path
import json
import shutil
import sys

root = Path.cwd()
page = root / 'web/map.html'
if not page.exists():
    sys.exit('Ejecuta este script desde la carpeta del proyecto.')
s = page.read_text(encoding='utf-8')
if 'id="meridian-language"' in s:
    sys.exit('El selector de idiomas ya está instalado.')
shutil.copy2(page, root / 'web/map_before_languages.html')

rows = '''Inteligencia|Intelligence|Renseignement|الاستخبارات
Dashboard|Dashboard|Tableau de bord|لوحة التحكم
Knowledge Graph|Knowledge Graph|Graphe de connaissances|الرسم البياني المعرفي
Intelligence Overview|Intelligence Overview|Vue d’ensemble du renseignement|نظرة عامة على الاستخبارات
Monitorización y análisis de acontecimientos geopolíticos|Monitoring and analysis of geopolitical events|Suivi et analyse des événements géopolitiques|رصد الأحداث الجيوسياسية وتحليلها
Auto-actualizar|Auto-refresh|Actualisation auto|تحديث تلقائي
Actualizar|Refresh|Actualiser|تحديث
Acontecimientos|Events|Événements|الأحداث
Geolocalizados|Geolocated|Géolocalisés|محددة الموقع
Entidades|Entities|Entités|الكيانات
Artículos|Articles|Articles|المقالات
En la base de datos|In the database|Dans la base de données|في قاعدة البيانات
Con coordenadas|With coordinates|Avec coordonnées|ذات إحداثيات
Entidades canónicas|Canonical entities|Entités canoniques|الكيانات الموحّدة
Fuentes recopiladas|Collected sources|Sources collectées|المصادر المجمّعة
Geospatial Intelligence|Geospatial Intelligence|Renseignement géospatial|الاستخبارات الجغرافية المكانية
Distribución geográfica por tipo de evento|Geographic distribution by event type|Répartition géographique par type d’événement|التوزيع الجغرافي حسب نوع الحدث
Buscar|Search|Rechercher|بحث
País|Country|Pays|الدولة
Tipo|Type|Type|النوع
Todos|All|Tous|الكل
Desde|From|Du|من
Hasta|To|Au|إلى
Más recientes primero|Newest first|Plus récents d’abord|الأحدث أولاً
Más antiguos primero|Oldest first|Plus anciens d’abord|الأقدم أولاً
Limpiar filtros|Clear filters|Effacer les filtres|مسح المرشحات
Event Timeline|Event Timeline|Chronologie des événements|الجدول الزمني للأحداث
Actividad por mes · clic para filtrar|Monthly activity · click to filter|Activité mensuelle · cliquer pour filtrer|النشاط الشهري · انقر للتصفية
Intelligence Report|Intelligence Report|Rapport de renseignement|تقرير استخباراتي
Detalles y evidencias|Details and evidence|Détails et preuves|التفاصيل والأدلة
Selecciona un acontecimiento para ver su informe.|Select an event to view its report.|Sélectionnez un événement pour afficher son rapport.|اختر حدثاً لعرض تقريره.
Cargar datos de demostración|Load demo data|Charger les données de démonstration|تحميل بيانات تجريبية
Título, lugar o descripción|Title, location or description|Titre, lieu ou description|العنوان أو الموقع أو الوصف
Meridian OSINT · Información basada en fuentes abiertas. Los indicadores de confianza son heurísticos, no probabilidades de veracidad.|Meridian OSINT · Open-source information. Confidence indicators are heuristic, not probabilities of truth.|Meridian OSINT · Informations de sources ouvertes. Les indicateurs de confiance sont heuristiques, pas des probabilités de véracité.|Meridian OSINT · معلومات من مصادر مفتوحة. مؤشرات الثقة تقديرية وليست احتمالات لصحة المعلومات.
Fecha|Date|Date|التاريخ
Localización|Location|Lieu|الموقع
Confianza heurística|Heuristic confidence|Confiance heuristique|الثقة التقديرية
Entidades vinculadas|Linked entities|Entités associées|الكيانات المرتبطة
Fuentes vinculadas|Linked sources|Sources associées|المصادر المرتبطة
No disponible|Not available|Non disponible|غير متاح
Fecha desconocida|Unknown date|Date inconnue|تاريخ غير معروف
Ver informe|View report|Voir le rapport|عرض التقرير
Ningún acontecimiento coincide. Prueba a limpiar los filtros.|No matching events. Try clearing the filters.|Aucun événement correspondant. Essayez d’effacer les filtres.|لا توجد أحداث مطابقة. جرّب مسح المرشحات.
Reintentar|Retry|Réessayer|إعادة المحاولة
API conectada|API connected|API connectée|واجهة API متصلة
Modo demo|Demo mode|Mode démo|الوضع التجريبي
Cargando…|Loading…|Chargement…|جارٍ التحميل…
Conectando…|Connecting…|Connexion…|جارٍ الاتصال…
Comprobando API…|Checking API…|Vérification de l’API…|جارٍ التحقق من API…
Error de conexión con API|API connection error|Erreur de connexion à l’API|خطأ في الاتصال بواجهة API
No se pudieron cargar los acontecimientos.|Could not load events.|Impossible de charger les événements.|تعذّر تحميل الأحداث.
No se pudo cargar el informe. |Could not load report. |Impossible de charger le rapport. |تعذّر تحميل التقرير. 
No se pudo conectar con |Could not connect to |Connexion impossible à |تعذّر الاتصال بـ 
. Comprueba que el servidor está activo.|. Check that the server is running.|. Vérifiez que le serveur fonctionne.|. تأكد من تشغيل الخادم.
 eventos visibles| visible events| événements visibles| أحداث ظاهرة
 eventos| events| événements| أحداث
 ubicaciones| locations| lieux| مواقع
% del total|% of total|% du total|% من الإجمالي
Fuente sin título|Untitled source|Source sans titre|مصدر بلا عنوان
Evento de demostración en |Demo event in |Événement de démonstration à |حدث تجريبي في 
Datos ficticios para probar la interfaz sin API.|Fictional data to test the interface without the API.|Données fictives pour tester l’interface sans API.|بيانات افتراضية لاختبار الواجهة دون API.
Entidad A|Entity A|Entité A|الكيان أ
Fuente de ejemplo|Sample source|Source d’exemple|مصدر تجريبي
buscar|search|rechercher|بحث
deseleccionar|deselect|désélectionner|إلغاء التحديد
Principal|Main navigation|Navigation principale|التنقل الرئيسي
Resumen|Overview|Résumé|ملخص
Mapa|Map|Carte|الخريطة
Tipos de evento|Event types|Types d’événement|أنواع الأحداث
Ordenar|Sort|Trier|ترتيب
Mapa de acontecimientos|Event map|Carte des événements|خريطة الأحداث
Eventos por mes|Events by month|Événements par mois|الأحداث حسب الشهر
Actualizar cada 60 s|Refresh every 60 s|Actualiser toutes les 60 s|تحديث كل 60 ثانية
Meridian OSINT, inicio|Meridian OSINT, home|Meridian OSINT, accueil|Meridian OSINT، الرئيسية
Idioma|Language|Langue|اللغة'''
translations = {lang: {} for lang in ('es', 'en', 'fr', 'ar')}
for line in rows.splitlines():
    parts = line.split('|')
    if len(parts) != 4:
        sys.exit('Error en una traducción: ' + line)
    for lang, value in zip(translations, parts):
        translations[lang][parts[0]] = value
loc = root / 'web/locales'
loc.mkdir(parents=True, exist_ok=True)
for lang, mapping in translations.items():
    (loc / (lang + '.json')).write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if 'i18next.min.js' not in s:
    anchor = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
    if anchor not in s:
        sys.exit('No se encontró Leaflet.')
    s = s.replace(anchor, anchor + '\n<script src="https://unpkg.com/i18next@23.16.8/dist/umd/i18next.min.js"></script>', 1)

anchor = '<span class="status" id="status"'
if anchor not in s:
    sys.exit('No se encontró la barra de acciones.')
s = s.replace(anchor, '<label class="language-control"><span data-i18n="Idioma">Idioma</span><select id="meridian-language" aria-label="Idioma"><option value="es">Español</option><option value="en">English</option><option value="fr">Français</option><option value="ar">العربية</option></select></label>\n        ' + anchor, 1)
css = '''
.language-control{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--muted)}
.language-control select{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px;cursor:pointer}
html[dir="rtl"] .sidebar{border-right:0;border-left:1px solid var(--border)}
html[dir="rtl"] .stat{border-right:0;border-left:1px solid var(--border)}
html[dir="rtl"] .stat:last-child{border-left:0}
html[dir="rtl"] .nav-item,html[dir="rtl"] .ev{border-left:0;border-right:3px solid transparent}
html[dir="rtl"] .nav-item.active,html[dir="rtl"] .ev.sel{border-right-color:var(--accent)}
html[dir="rtl"] .ev{text-align:right}
html[dir="rtl"] .leaflet-container{direction:ltr}
@media(max-width:850px){html[dir="rtl"] .stat:nth-child(2){border-left:0}}
'''
s = s.replace('</style>', css + '</style>', 1)

js = r'''
const TRANSLATIONS = __DATA__;
const LANG_KEY = "meridian-language";
let currentLanguage = localStorage.getItem(LANG_KEY) || "es";
if (!Object.hasOwn(TRANSLATIONS, currentLanguage)) currentLanguage = "es";
const originalNodes = new WeakMap();
const originalAttributes = new WeakMap();
const t = key => (window.i18next && i18next.isInitialized ? i18next.t(key) : (TRANSLATIONS[currentLanguage][key] ?? key));
function translateTree() {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (!node.parentElement || ["SCRIPT", "STYLE"].includes(node.parentElement.tagName)) continue;
    if (!originalNodes.has(node)) originalNodes.set(node, node.nodeValue);
    const source = originalNodes.get(node);
    const key = source.trim();
    if (Object.hasOwn(TRANSLATIONS.es, key)) {
      const lead = source.match(/^\s*/)[0], tail = source.match(/\s*$/)[0];
      node.nodeValue = lead + t(key) + tail;
    }
  }
  for (const el of document.querySelectorAll("[placeholder],[aria-label],[title]")) {
    if (!originalAttributes.has(el)) {
      originalAttributes.set(el, Object.fromEntries(["placeholder", "aria-label", "title"].map(a => [a, el.getAttribute(a)])));
    }
    for (const [attr, source] of Object.entries(originalAttributes.get(el))) {
      if (source && Object.hasOwn(TRANSLATIONS.es, source)) el.setAttribute(attr, t(source));
    }
  }
  document.documentElement.lang = currentLanguage;
  document.documentElement.dir = currentLanguage === "ar" ? "rtl" : "ltr";
}
function updateLanguage(lang) {
  currentLanguage = lang;
  localStorage.setItem(LANG_KEY, lang);
  if (window.i18next && i18next.isInitialized) i18next.changeLanguage(lang);
  translateTree();
  if (S.events.length) {
    fillSelect("f-country", S.events.map(e => e.country));
    fillSelect("f-type", S.events.map(e => e.event_type));
    renderLegend();
    apply(false);
    if (S.selected != null && cache.has(S.selected)) renderDetails(cache.get(S.selected));
  }
  translateTree();
  const status = document.getElementById("status");
  if (status && S.events.length) setStatus((S.demo ? t("Modo demo") : t("API conectada")) + " · " + visible().length + t(" eventos visibles"), S.demo ? "wait" : "ok");
}
if (window.i18next) i18next.init({ lng: currentLanguage, fallbackLng: "es", resources: Object.fromEntries(Object.entries(TRANSLATIONS).map(([k, v]) => [k, { translation: v }])), interpolation: { escapeValue: false } });
document.getElementById("meridian-language").value = currentLanguage;
document.getElementById("meridian-language").addEventListener("change", e => updateLanguage(e.target.value));
translateTree();
'''.replace('__DATA__', json.dumps(translations, ensure_ascii=False))
s = s.replace('"use strict";', '"use strict";\n' + js, 1)

replacements = {
'const val = v => (v == null || v === "") ? "No disponible" : String(v);': 'const val = v => (v == null || v === "") ? t("No disponible") : String(v);',
'if (!v) return "Fecha desconocida";': 'if (!v) return t("Fecha desconocida");',
'd.toLocaleDateString("es-ES",': 'd.toLocaleDateString(currentLanguage === "ar" ? "ar" : currentLanguage,',
'"Ver informe");': 't("Ver informe"));',
'list.length + " ubicaciones"': 'list.length + t(" ubicaciones")',
'String(a).localeCompare(String(b), "es")': 'String(a).localeCompare(String(b), currentLanguage)',
'counts[k] + " eventos"': 'counts[k] + t(" eventos")',
'events.length + " eventos"': 'events.length + t(" eventos")',
'"Ningún acontecimiento coincide. Prueba a limpiar los filtros."': 't("Ningún acontecimiento coincide. Prueba a limpiar los filtros.")',
'row(box, "Fecha",': 'row(box, t("Fecha"),',
'row(box, "Tipo",': 'row(box, t("Tipo"),',
'row(box, "País",': 'row(box, t("País"),',
'row(box, "Localización",': 'row(box, t("Localización"),',
'"Confianza heurística: "': 't("Confianza heurística") + ": "',
'row(box, "Entidades vinculadas",': 'row(box, t("Entidades vinculadas"),',
'"Fuentes vinculadas: " +': 't("Fuentes vinculadas") + ": " +',
'"Fuente sin título"': 't("Fuente sin título")',
'"No se pudo cargar el informe. "': 't("No se pudo cargar el informe. ")',
'"Reintentar"': 't("Reintentar")',
'"Selecciona un acontecimiento para ver su informe."': 't("Selecciona un acontecimiento para ver su informe.")',
'"Modo demo" : "API conectada"': 't("Modo demo") : t("API conectada")',
'events.length + " eventos visibles"': 'events.length + t(" eventos visibles")',
'pct + "% del total"': 'pct + t("% del total")',
'setStatus("Cargando…",': 'setStatus(t("Cargando…"),',
'setStatus("Error de conexión con API",': 'setStatus(t("Error de conexión con API"),',
'"No se pudieron cargar los acontecimientos."': 't("No se pudieron cargar los acontecimientos.")',
'"No se pudo conectar con " + API.events + ". Comprueba que el servidor está activo."': 't("No se pudo conectar con ") + API.events + t(". Comprueba que el servidor está activo.")',
'"Evento de demostración en " +': 't("Evento de demostración en ") +',
'"Datos ficticios para probar la interfaz sin API."': 't("Datos ficticios para probar la interfaz sin API.")',
'"Entidad A"': 't("Entidad A")',
'"Fuente de ejemplo"': 't("Fuente de ejemplo")'
}
boundary = 'translateTree();\n\n\nconst API ='
if boundary not in s:
    sys.exit('No se encontró el inicio del código principal.')
head, tail = s.split(boundary, 1)
for old, new in replacements.items():
    if old not in tail:
        print('Aviso: patrón no encontrado:', old[:65])
    tail = tail.replace(old, new)
s = head + boundary + tail

s = s.replace('  renderMap(events, fit); renderTimeline(events); renderSpark(); saveHash();', '  renderMap(events, fit); renderTimeline(events); renderSpark(); saveHash();\n  translateTree();')
s = s.replace('  box.appendChild(src);\n}', '  box.appendChild(src);\n  translateTree();\n}')
s = s.replace('  if (S.selected != null) select(S.selected, true);', '  if (S.selected != null) select(S.selected, true);\n  translateTree();')
s = s.replace('  $("status").textContent = text;', '  $("status").textContent = text;')
page.write_text(s, encoding='utf-8')
print('Instalación completada. Idiomas: español, inglés, francés y árabe.')
print('Copia: web/map_before_languages.html')
