
import json
from datetime import datetime

with open("data/raw/gdelt_niger.json", "r", encoding="utf-8") as file:
    data = json.load(file)

articles = data["articles"]

print("Artículos originales:", len(articles))

titulos_vistos = set()
articles_limpios = []
articles_descartados = []

def es_irrelevante(article):
    titulo = article.get("title", "").casefold()
    url = article.get("url", "").casefold()

    # Nigar es un nombre propio distinto del país Níger.
    if "nigar" in titulo or "nigar" in url:
        return True

    # Niger State y FCT son territorios de Nigeria.
    if "niger state" in titulo or "niger state" in url:
        return True

    if "fct" in titulo and "police" in titulo:
        return True

    return False

for article in articles:
    if es_irrelevante(article):
        articles_descartados.append(article.get("title", ""))
        continue

    titulo = " ".join(article["title"].split())

    if not titulo:
        continue

    titulo_comparacion = titulo.lower()

    if titulo_comparacion in titulos_vistos:
        continue

    titulos_vistos.add(titulo_comparacion)

    fecha_original = article.get("seendate", "")

    if fecha_original:
        fecha = datetime.strptime(
            fecha_original,
            "%Y%m%dT%H%M%SZ"
        ).strftime("%Y-%m-%d %H:%M:%S")
    else:
        fecha = ""

    article_limpio = {
        "title": titulo,
        "date": fecha,
        "url": article.get("url", ""),
        "domain": article.get("domain", ""),
        "language": article.get("language", ""),
        "source_country": article.get("sourcecountry", "")
    }

    articles_limpios.append(article_limpio)

data_limpia = {
    "country": "Niger",
    "source": "GDELT",
    "total_articles": len(articles_limpios),
    "articles": articles_limpios
}

with open(
    "data/processed/gdelt_niger.json",
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        data_limpia,
        file,
        indent=4,
        ensure_ascii=False
    )

print("Artículos después del procesamiento:", len(articles_limpios))
print("Duplicados eliminados:", len(articles) - len(articles_limpios) - len(articles_descartados))
print("Noticias irrelevantes descartadas:", len(articles_descartados))

for titulo in articles_descartados:
    print("DESCARTADA:", titulo)
print("Datos guardados en: data/processed/gdelt_niger.json")
