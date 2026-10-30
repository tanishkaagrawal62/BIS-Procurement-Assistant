import os
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import Standard

TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
SEARCH_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "shall", "must", "should", "are", "was", "were",
    "has", "have", "had", "not", "into", "onto", "their", "they", "them", "which", "when", "where", "what",
    "of", "in", "an", "a", "to", "by", "on", "at", "as", "it", "or", "be", "is", "out", "up", "down",
    "does", "do", "did", "can", "will", "may", "must", "both", "all", "any", "some", "such", "solely",
    "all", "any", "each", "such", "than", "then", "also", "only", "other", "more", "most", "less",
    "supply", "procure", "procurement", "purchase", "tender", "required", "requirement", "requirements",
    "standard", "standards", "specification", "specifications", "product", "products", "item", "items",
    "test", "tests", "testing", "method", "methods", "code", "practice", "part", "section", "general",
    "including", "provide", "minimum", "maximum", "applicable", "application", "conformity", "compliance",
    "bid", "bids", "bidder", "bidders", "manufacturer", "authorized", "authorised", "shall", "within",
    "based", "following", "ensure", "used", "use", "suitable", "intended", "details", "information",
    "accordance", "set", "out", "document", "documents", "invites", "inviting", "sample", "fictional",
}


def tokens(text: str) -> list[str]:
    normalized = []
    for token in TOKEN_RE.findall(text.lower()):
        if token.endswith("s") and not token.endswith("ss") and len(token) > 5:
            token = token[:-1]
        if token not in SEARCH_STOP_WORDS:
            normalized.append(token)
    return normalized


def bm25_scores(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Small dependency-free BM25 implementation for the local catalogue."""
    corpus = [tokens(doc) for doc in documents]
    query_terms = set(tokens(query))
    if not corpus or not query_terms:
        return [0.0] * len(corpus)
    average_length = sum(map(len, corpus)) / len(corpus) or 1
    document_frequency = Counter(term for doc in corpus for term in set(doc))
    scores = []
    for doc in corpus:
        counts = Counter(doc)
        score = 0.0
        for term in query_terms:
            frequency = counts[term]
            if not frequency:
                continue
            inverse = __import__("math").log(1 + (len(corpus) - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
            denominator = frequency + k1 * (1 - b + b * len(doc) / average_length)
            score += inverse * frequency * (k1 + 1) / denominator
        scores.append(score)
    maximum = max(scores, default=0)
    return [score / maximum if maximum else 0.0 for score in scores]


def local_semantic_scores(query: str, documents: list[str]) -> tuple[list[float] | None, str | None]:
    model_path = os.getenv("BIS_SBERT_MODEL_PATH")
    if not model_path:
        return None, "Not configured. Set BIS_SBERT_MODEL_PATH to an already downloaded local model."
    try:
        from sentence_transformers import SentenceTransformer
        from sklearn.metrics.pairwise import cosine_similarity

        model = SentenceTransformer(model_path, local_files_only=True)
        vectors = model.encode([query, *documents], normalize_embeddings=True)
        similarities = cosine_similarity([vectors[0]], vectors[1:])[0]
        return [max(0.0, float(value)) for value in similarities], None
    except Exception as exc:  # model loading must never masquerade as a successful semantic search
        return None, f"Local SBERT unavailable: {type(exc).__name__}: {exc}"


def recommend(db: Session, requirement_text: str, live_standard_numbers: list[str] | None = None, anchor_terms: set[str] | None = None) -> tuple[list[dict], dict]:
    statement = select(Standard)
    if live_standard_numbers is not None:
        statement = statement.where((Standard.verification_state != "live_search") | (Standard.is_number.in_(live_standard_numbers))) if live_standard_numbers else statement.where(Standard.verification_state != "live_search")
    standards = list(db.scalars(statement).all())
    documents = [f"{s.is_number} {s.title} {s.scope or ''} {s.keywords}" for s in standards]
    keyword = bm25_scores(requirement_text, documents)
    semantic, semantic_error = local_semantic_scores(requirement_text, documents) if standards else (None, "No standards are loaded in the catalogue.")
    ranked = []
    for index, standard in enumerate(standards):
        document_terms = set(tokens(documents[index]))
        if anchor_terms and not anchor_terms.intersection(document_terms):
            continue
        semantic_score = semantic[index] if semantic is not None else None
        combined = 0.55 * keyword[index] + 0.45 * semantic_score if semantic_score is not None else keyword[index]
        requirement_terms = set(tokens(requirement_text))
        evidence = list(dict.fromkeys(term for term in tokens(documents[index]) if len(term) > 3 and term in requirement_terms))[:5]
        if combined < 0.08 or not evidence:
            continue
        ranked.append({
            "standard": standard,
            "keyword_score": keyword[index],
            "semantic_score": semantic_score,
            "combined_score": combined,
            "evidence": evidence[:5],
            "uncertainty": [],
        })
    ranked.sort(key=lambda row: row["combined_score"], reverse=True)
    for rank, item in enumerate(ranked[:3], 1):
        item["rank"] = rank
    return ranked[:3], {"keyword_search": "bm25", "semantic_search": "sbert" if semantic is not None else "unavailable", "semantic_error": semantic_error, "catalogue_records": len(standards)}
