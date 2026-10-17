
import re
import unicodedata

LOCATIONS = {
    "Niamey": (13.5116, 2.1254),
    "Agadez": (16.9742, 7.9860),
    "Zinder": (13.8053, 8.9881),
    "Maradi": (13.5000, 7.1017),
    "Tahoua": (14.8888, 5.2692),
    "Diffa": (13.3154, 12.6113),
    "Dosso": (13.0490, 3.1937),
    "Tillabéri": (14.2117, 1.4531),
    "Arlit": (18.7369, 7.3853),
    "Téra": (14.0078, 0.7531),
    "Bankilaré": (14.5829, 0.7252),
    "Séguédine": (20.1962, 12.9666),
}

ALIASES = {
    "niamey": "Niamey",
    "agadez": "Agadez",
    "zinder": "Zinder",
    "maradi": "Maradi",
    "tahoua": "Tahoua",
    "diffa": "Diffa",
    "dosso": "Dosso",
    "tillaberi": "Tillabéri",
    "arlit": "Arlit",
    "tera": "Téra",
    "bankilare": "Bankilaré",
    "seguedine": "Séguédine",
}

def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )
    return text.lower()

def detect_locations(text):
    normalized = normalize(text)
    found = []

    for alias, canonical in ALIASES.items():
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"

        if re.search(pattern, normalized):
            latitude, longitude = LOCATIONS[canonical]

            found.append({
                "name": canonical,
                "latitude": latitude,
                "longitude": longitude,
                "precision": "city_reference",
            })

    return found
