import re


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_requirements(text: str) -> dict:
    clean = normalize_text(text)
    lines = [line.strip(" •-*\t") for line in clean.splitlines() if line.strip()]
    product = None
    for line in lines:
        match = re.search(r"\b(?:supply|procure|purchase)\s+(?:of\s+)?([^,;.\n]{2,100})", line, re.I)
        if match:
            product = re.sub(r"\s+", " ", match.group(1)).strip()
            break
    if not product:
        product = next((line[:100].strip() for line in lines if re.search(r"\b(product|equipment|material)\b", line, re.I)), None)
    quantity_pattern = r"\b(?:quantity|qty|order quantity)\s*[:=\-]?\s*\d[\d,]*(?:\.\d+)?\s*(?:units?|pcs?|pieces?|nos?\.?|sets?|pairs?|kg|tonnes?|litres?|meters?|metres?)?\b|\b\d[\d,]*(?:\.\d+)?\s*(?:units?|pcs?\.?|pieces?|nos?\.?|sets?|pairs?)\b"
    patterns = {
        "quantity": quantity_pattern,
        "materials": r"\b(stainless steel|carbon steel|mild steel|aluminium|aluminum|copper|PVC|polypropylene|rubber|concrete|wood)\b",
        "dimensions": r"\b(?:\d+(?:\.\d+)?\s?(?:mm|cm|m|inch|inches|kg|g|MPa|V|kV|A|W|kW|°C|class\s?\d+(?:\.\d+)?))\b",
        "testing": r"\b(test(?:ing)?|inspection|sampling|laboratory|test report)\b",
        "safety": r"\b(safety|fire|electrical|hazard|protective|impact resistance)\b",
        "performance": r"\b(performance|load|strength|efficiency|耐|capacity|durability|tolerance)\b",
        "application": r"\b(for use in|intended for|application|used for|suitable for)\b",
        "grades": r"\b(?:grade|class)\s*[-:]?\s*(?:\d+[A-Z]?|[IVX]{1,4})\b",
        "referenced_standards": r"\b(?:IS|BIS|ISO|IEC)\s?(?:\d{2,5})(?:\s?\([^)]{1,30}\))?(?::\s?\d{4})?\b",
    }
    fields = {}
    for field, pattern in patterns.items():
        matches = []
        for line in lines:
            for match in re.finditer(pattern, line, re.I):
                matches.append({"value": match.group(0), "evidence": line})
        fields[field] = matches
    keywords = sorted({token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9/-]{2,}", clean)})
    return {"product": {"value": product, "evidence": product} if product else None, **fields, "keywords": keywords, "source_text": clean}
