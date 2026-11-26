import re
import csv
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import DATA_DIR, INGESTION_DIR, POLICY_DIR
from . import embeddings

_indexes = {}
_embedding_cache = {}
_metadata_cache = {}
_ORG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
SUPPORTED_EXTENSIONS = {".txt", ".md", ".html", ".htm", ".pdf", ".docx"}


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        elif tag in {"p", "br", "li", "div", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "li", "div", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def extract_text(path):
    """Extract readable text from supported offline policy source files."""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8-sig")
    if suffix in {".html", ".htm"}:
        parser = _HTMLText()
        parser.feed(path.read_text(encoding="utf-8-sig"))
        return "\n".join(" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("PDF extraction is unavailable: install the pypdf dependency.") from exc
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix == ".docx":
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        w_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        lines = []
        for node in root.iter(f"{w_ns}p"):
            text = "".join(t.text or "" for t in node.iter(f"{w_ns}t")).strip()
            if not text:
                continue
            pstyle = node.find(f"{w_ns}pPr/{w_ns}pStyle")
            style_val = pstyle.attrib.get(f"{w_ns}val", "") if pstyle is not None else ""
            if style_val.lower().startswith(("heading", "title")):
                lines.append(f"\n# {text}\n")
            elif "list" in style_val.lower():
                lines.append(f"- {text}")
            else:
                lines.append(text)
        return "\n".join(lines)
    raise ValueError(f"Unsupported document type: {suffix or 'no extension'}")


def normalize_organization(organization_id="default"):
    value = (organization_id or "default").strip().lower()
    if not _ORG_RE.fullmatch(value) or value in {".", ".."}:
        raise ValueError("organization_id must be a 1-64 character identifier using letters, numbers, '.', '_' or '-'.")
    return value


def organizations():
    """List configured organization folders, including legacy flat files as default."""
    found = set()
    if POLICY_DIR.exists():
        for base in (POLICY_DIR, INGESTION_DIR):
            if base.exists():
                for path in base.iterdir():
                    if path.is_dir() and _ORG_RE.fullmatch(path.name) and any(
                        f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
                        for f in path.rglob("*")
                    ):
                        found.add(path.name.lower())
                if any(p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS and p.stem.lower() != "readme"
                       for p in base.iterdir()):
                    found.add("default")
    return sorted(found or {"default"})


def _organization_path(organization_id):
    org = normalize_organization(organization_id)
    return org, POLICY_DIR / org


def _split_clauses(text):
    """Split policy text into retrievable clauses using headings, lists, or paragraphs."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    blocks = []
    current = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        is_heading = line.startswith("#")
        is_list_item = bool(re.match(r"^(?:[-*+]\s+|\d+(?:\.\d+)*[.)]?\s+)", line))
        if (is_heading or is_list_item) and current:
            blocks.append(" ".join(current))
            current = []
        if is_heading:
            line = re.sub(r"^#+\s*", "", line)
        current.append(line)
        if is_list_item:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return [b for b in blocks if b.strip()]


def _chunk_clause(text, chunk_size=1200, overlap=160):
    """Bound long clauses while keeping a small overlap for retrieval context."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start
        chars = 0
        while end < len(words) and chars + len(words[end]) + (1 if end > start else 0) <= chunk_size:
            chars += len(words[end]) + (1 if end > start else 0)
            end += 1
        if end == start:
            end += 1
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        overlap_chars = 0
        next_start = end
        while next_start > start and overlap_chars < overlap:
            next_start -= 1
            overlap_chars += len(words[next_start]) + 1
        start = max(start + 1, next_start)
    return chunks


def _source_files(organization_id):
    org, org_path = _organization_path(organization_id)
    files = []
    for base in (POLICY_DIR, INGESTION_DIR):
        scoped = base / org
        if scoped.exists():
            files.extend(p for p in scoped.rglob("*") if p.is_file()
                         and p.suffix.lower() in SUPPORTED_EXTENSIONS and p.stem.lower() != "readme")
        # Keep supporting legacy source documents stored flat for the default org.
        if org == "default" and base.exists():
            files.extend(p for p in base.iterdir() if p.is_file()
                         and p.suffix.lower() in SUPPORTED_EXTENSIONS and p.stem.lower() != "readme")
    return org, sorted(set(files))


def _metadata_for(organization_id):
    """Load the curated CSV catalogue for an organization, when available."""
    org = normalize_organization(organization_id)
    path = DATA_DIR / "corpus_metadata" / org / "master_metadata.csv"
    if not path.is_file():
        _metadata_cache.pop(org, None)
        return {}
    signature = (path.stat().st_mtime_ns, path.stat().st_size)
    cached = _metadata_cache.get(org)
    if cached and cached[0] == signature:
        return cached[1]
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            for field in ("pdf_file", "docx_file"):
                if row.get(field):
                    rows[row[field]] = row
    _metadata_cache[org] = (signature, rows)
    return rows


def load_docs(organization_id="default"):
    org, files = _source_files(organization_id)
    metadata_rows = _metadata_for(org)
    docs = []
    for path in files:
        text = extract_text(path)
        metadata = metadata_rows.get(path.name, {})
        rel_id = path.stem
        for base in (POLICY_DIR, INGESTION_DIR):
            scoped = base / org
            if path.is_relative_to(scoped):
                rel_id = f"{org}/{path.relative_to(scoped).with_suffix('').as_posix()}"
                break
            if org == "default" and path.is_relative_to(base):
                rel_id = path.relative_to(base).with_suffix("").as_posix()
                break
        for index, clause in enumerate(_split_clauses(text), start=1):
            for chunk_index, chunk in enumerate(_chunk_clause(clause), start=1):
                suffix = f"#clause-{index}" + (f"-chunk-{chunk_index}" if len(clause) > 1200 else "")
                document_id = metadata.get("document_id") or rel_id
                search_fields = [metadata.get(field, "") for field in
                                 ("document_id", "title", "description", "batch", "category", "jurisdiction", "version", "effective_date", "parent_or_related_series")]
                docs.append({"id": f"{document_id}{suffix}", "document_id": document_id,
                             "organization_id": org, "grade": "ALL", "text": chunk,
                             "source_file": path.name, "title": metadata.get("title", path.stem),
                             "description": metadata.get("description", ""),
                             "batch": metadata.get("batch"), "category": metadata.get("category"),
                             "jurisdiction": metadata.get("jurisdiction"), "version": metadata.get("version"),
                             "effective_date": metadata.get("effective_date"),
                             "synthetic": str(metadata.get("synthetic", "")).lower() == "true",
                             "title_text": " ".join(filter(None, [metadata.get("document_id", ""), metadata.get("title", ""), metadata.get("description", ""), metadata.get("jurisdiction", "")])),
                             "search_text": " ".join(filter(None, [chunk, *search_fields]))})
    return docs


def tokens(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def _index_for(organization_id):
    org, files = _source_files(organization_id)
    signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    cached = _indexes.get(org)
    if cached and cached[0] == signature:
        return (signature, *cached[1:])
    docs = load_docs(org)
    if not docs:
        _indexes.pop(org, None)
        _embedding_cache.pop(org, None)
        return signature, [], None, None, None, None
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
    matrix = vectorizer.fit_transform([d.get("search_text", d["text"]) for d in docs])
    char_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
    char_matrix = char_vec.fit_transform([d.get("title_text") or d.get("title", "") for d in docs])
    _indexes[org] = (signature, docs, vectorizer, matrix, char_vec, char_matrix)
    return signature, docs, vectorizer, matrix, char_vec, char_matrix


def _embedding_scores(org, signature, docs, query):
    """Return 384-d cosine similarity scores from bge-small-en-v1.5 when configured."""
    if not embeddings.is_configured():
        return None
    model = embeddings.current_model()
    cache_key = (org, model)
    cached = _embedding_cache.get(cache_key)
    try:
        if cached and cached[0] == signature:
            doc_vectors = cached[1]
        else:
            doc_vectors = embeddings.embed_texts([d.get("search_text", d["text"]) for d in docs])
            _embedding_cache[cache_key] = (signature, doc_vectors)
        query_vector = embeddings.embed_texts([query])[0]
        return cosine_similarity([query_vector], doc_vectors)[0]
    except embeddings.EmbeddingError:
        return None


def cache_status():
    return {
        "tfidf_organizations_cached": len(_indexes),
        "embedding_caches": len(_embedding_cache),
        "metadata_caches": len(_metadata_cache),
    }


_COUNTRY_ALIASES = {
    "australia": "Australia",
    "sydney": "Australia",
    "melbourne": "Australia",
    "brazil": "Brazil",
    "canada": "Canada",
    "toronto": "Canada",
    "china": "China",
    "beijing": "China",
    "shanghai": "China",
    "denmark": "Denmark",
    "france": "France",
    "paris": "France",
    "germany": "Germany",
    "berlin": "Germany",
    "munich": "Germany",
    "india": "India",
    "delhi": "India",
    "bengaluru": "India",
    "mumbai": "India",
    "indonesia": "Indonesia",
    "ireland": "Ireland",
    "dublin": "Ireland",
    "italy": "Italy",
    "milan": "Italy",
    "rome": "Italy",
    "japan": "Japan",
    "tokyo": "Japan",
    "malaysia": "Malaysia",
    "mexico": "Mexico",
    "netherlands": "Netherlands",
    "amsterdam": "Netherlands",
    "new zealand": "New Zealand",
    "poland": "Poland",
    "singapore": "Singapore",
    "south africa": "South Africa",
    "south korea": "South Korea",
    "korea": "South Korea",
    "seoul": "South Korea",
    "spain": "Spain",
    "madrid": "Spain",
    "sweden": "Sweden",
    "switzerland": "Switzerland",
    "zurich": "Switzerland",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "london": "United Kingdom",
    "united states": "United States",
    "usa": "United States",
    "new york": "United States",
}

_QUERY_EXPANSIONS = (
    (r"\brent\b", "rental car vehicle"),
    (r"\b(dinner|lunch|breakfast)\b", "meal hospitality food"),
    (r"\bunavailable\b", "outage continuity fallback unavailable"),
    (r"\b(later|after)\b", "retrospective after-the-fact"),
    (r"\b(chest pain|sick|ill|hospital)\b", "medical emergency assistance repatriation"),
    (r"\b(24/7|phone number|travel desk)\b", "after-hours support emergency contact"),
    (r"\b(pretend|fake)\b", "approval confirmation segregation integrity"),
    (r"\b(atlantis|country x)\b", "country addendum silent unlisted missing coverage"),
    (r"\b(contacted|reach|uncontactable)\b", "missing uncontactable traveller escalation"),
    (r"\b(book|booking)\b", "intake request completeness channel"),
    (r"\b(contractor|subcontractor|vendor)\b", "external third-party contractor"),
    (r"\b(five-star|client says|customer says)\b", "customer-requested customer-billable conflict precedence"),
    (r"\b(approve|approver|who can approve)\b", "approval matrix authority tier segregation"),
    (r"\bcabin class\b", "cabin class grade entitlement overlay"),
    (r"\b(provided lunch|provided meal|already provided)\b", "actuals per diem duplicate meal deduction"),
)


def _expand_query(query):
    extras = []
    qlow = query.lower()
    for pattern, addition in _QUERY_EXPANSIONS:
        if re.search(pattern, qlow):
            extras.append(addition)
    return f"{query} {' '.join(extras)}" if extras else query


def _detect_query_countries(qlow):
    found = set()
    for alias, canonical in _COUNTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", qlow):
            found.add(canonical)
    return found


def _rerank(query, candidates, top_k):
    """Rerank candidates using phrase matching, metadata alignment, historical-version demotion, and document diversity."""
    expanded = _expand_query(query)
    qlow = expanded.lower()
    qtokens = tokens(expanded)
    bigrams = {f"{qtokens[i]} {qtokens[i + 1]}" for i in range(len(qtokens) - 1)}
    asks_historical = any(w in qlow for w in ("historical", "archived", "superseded", "2025", "v0.", "previous version", "old version", "booked before", "amendment", "latest policy", "before the latest"))
    countries = _detect_query_countries(qlow)

    rescored = []
    for base_score, doc in candidates:
        title_low = (doc.get("title") or "").lower()
        desc_low = (doc.get("description") or "").lower()
        text_low = (doc.get("text") or "").lower()
        search_low = (doc.get("search_text") or doc.get("text") or "").lower()
        doc_id = (doc.get("document_id") or doc["id"]).upper()

        phrase_hits = sum(1 for bg in bigrams if bg in title_low or bg in desc_low or bg in search_low)
        phrase_boost = min(0.28, 0.09 * phrase_hits)

        is_historical = "historical" in title_low or "archived" in search_low or "superseded" in search_low
        version_adj = 0.08 if (asks_historical and is_historical) else (-0.12 if (is_historical and not asks_historical) else 0.0)
        if asks_historical and "-AMD-" in doc_id:
            version_adj += 0.14

        meta_adj = 0.0
        jur = doc.get("jurisdiction") or "Global"
        if countries:
            if jur in countries:
                meta_adj += 0.08
            elif jur != "Global":
                meta_adj -= 0.30
        elif jur != "Global":
            # Prevent 25 country-addendum clones from crowding out Global/EXP/EXC/OPS/SAFE rules when no country is named.
            meta_adj -= 0.30

        if (len(countries) >= 2 or any(w in qlow for w in ("several countries", "multi-country", "three countries", "cross-border", "spans"))) and "-XBR-" in doc_id:
            meta_adj += 0.18
        if any(w in text_low for w in ("synthetic-data notice", "synthetic illustration only", "fictional globaltech technologies travel-policy corpus")):
            meta_adj -= 0.15
        if doc_id.lower() in qlow:
            meta_adj += 0.5

        rescored.append((base_score + phrase_boost + version_adj + meta_adj, doc))

    rescored.sort(key=lambda x: x[0], reverse=True)
    selected = []
    seen_docs = set()
    overflow = []
    country_slots = 0
    max_country_slots = 2 if countries else 1
    for score, doc in rescored:
        if score <= 0:
            continue
        doc_key = doc.get("document_id") or doc["id"]
        jur = doc.get("jurisdiction") or "Global"
        if doc_key not in seen_docs:
            if jur != "Global" and country_slots >= max_country_slots:
                overflow.append({"score": round(score, 4), **doc})
                continue
            seen_docs.add(doc_key)
            if jur != "Global":
                country_slots += 1
            selected.append({"score": round(score, 4), **doc})
            if len(selected) >= top_k:
                break
        else:
            overflow.append({"score": round(score, 4), **doc})
    if len(selected) < top_k:
        for item in overflow:
            if len(selected) >= top_k:
                break
            doc_key = item.get("document_id") or item["id"]
            if doc_key not in seen_docs:
                seen_docs.add(doc_key)
                selected.append(item)
    if len(selected) < top_k:
        selected.extend(overflow[: top_k - len(selected)])
    return selected[:top_k]


def retrieve(query, grade="M6", top_k=6, organization_id="default"):
    org = normalize_organization(organization_id)
    signature, docs, vectorizer, matrix, char_vec, char_matrix = _index_for(org)
    if not docs:
        return []
    expanded = _expand_query(query)
    qlow = expanded.lower()
    qset = set(tokens(expanded))
    countries = _detect_query_countries(qlow)
    qvec = vectorizer.transform([expanded])
    vs = cosine_similarity(qvec, matrix)[0]
    cs = cosine_similarity(char_vec.transform([expanded]), char_matrix)[0]
    sem = _embedding_scores(org, signature, docs, query)
    emb_mode = embeddings.current_mode()
    ranked = []
    for i, doc in enumerate(docs):
        dt = set(tokens(doc.get("search_text", doc["text"])))
        overlap = sum(1 for t in qset if t in dt)
        lexical = overlap / (overlap + 1.2 + 0.25 * len(dt) / 20) if overlap else 0
        tt = set(tokens(doc.get("title_text") or doc.get("title", "")))
        title_overlap = sum(1 for t in qset if t in tt)
        title_boost = 0.25 * (title_overlap / len(qset)) if qset and title_overlap else 0
        jur = doc.get("jurisdiction") or "Global"
        jur_boost = 0.12 if (countries and jur in countries) else (-0.22 if (not countries and jur != "Global") else 0.0)
        bonus = 0.12 if doc["grade"] in (grade, "ALL") else -0.2
        if sem is not None and emb_mode == "hosted":
            score = 0.70 * float(sem[i]) + 0.30 * float(cs[i]) + title_boost + jur_boost + bonus
        elif sem is not None:
            score = 0.35 * float(sem[i]) + 0.25 * float(vs[i]) + 0.25 * float(cs[i]) + 0.15 * lexical + title_boost + jur_boost + bonus
        else:
            score = 0.40 * float(vs[i]) + 0.35 * float(cs[i]) + 0.25 * lexical + title_boost + jur_boost + bonus
        ranked.append((score, doc))
    ranked.sort(key=lambda x: x[0], reverse=True)
    # Cap chunks per document before reranking so one long document cannot crowd out other policies.
    candidate_pool = []
    doc_chunk_counts = {}
    pool_limit = max(top_k * 10, 60)
    for item in ranked:
        doc_key = item[1].get("document_id") or item[1]["id"]
        count = doc_chunk_counts.get(doc_key, 0)
        if count >= 2:
            continue
        doc_chunk_counts[doc_key] = count + 1
        candidate_pool.append(item)
        if len(candidate_pool) >= pool_limit:
            break
    return _rerank(query, candidate_pool, top_k)
