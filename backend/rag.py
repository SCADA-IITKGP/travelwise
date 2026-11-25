import re
import csv
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import DATA_DIR, INGESTION_DIR, POLICY_DIR

_indexes = {}
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
        return "\n".join("".join(node.itertext()) for node in root.iter() if node.tag.endswith("}p"))
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
                                 ("title", "description", "batch", "category", "jurisdiction", "version", "effective_date")]
                docs.append({"id": f"{document_id}{suffix}", "document_id": document_id,
                             "organization_id": org, "grade": "ALL", "text": chunk,
                             "source_file": path.name, "title": metadata.get("title", path.stem),
                             "batch": metadata.get("batch"), "category": metadata.get("category"),
                             "jurisdiction": metadata.get("jurisdiction"), "version": metadata.get("version"),
                             "effective_date": metadata.get("effective_date"),
                             "synthetic": str(metadata.get("synthetic", "")).lower() == "true",
                             "search_text": " ".join([chunk, *search_fields])})
    return docs


def tokens(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def _index_for(organization_id):
    org, files = _source_files(organization_id)
    signature = tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in files)
    cached = _indexes.get(org)
    if cached and cached[0] == signature:
        return cached[1:]
    docs = load_docs(org)
    if not docs:
        _indexes.pop(org, None)
        return [], None, None
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
    matrix = vectorizer.fit_transform([d.get("search_text", d["text"]) for d in docs])
    _indexes[org] = (signature, docs, vectorizer, matrix)
    return docs, vectorizer, matrix


def retrieve(query, grade="M6", top_k=4, organization_id="default"):
    docs, vectorizer, matrix = _index_for(organization_id)
    if not docs:
        return []
    qset = set(tokens(query))
    qvec = vectorizer.transform([query])
    vs = cosine_similarity(qvec, matrix)[0]
    ranked = []
    for i, doc in enumerate(docs):
        dt = tokens(doc.get("search_text", doc["text"]))
        overlap = sum(1 for t in qset if t in dt)
        lexical = overlap / (overlap + 1.2 + 0.25 * len(dt) / 20) if overlap else 0
        bonus = 0.12 if doc["grade"] in (grade, "ALL") else -0.2
        score = 0.55 * float(vs[i]) + 0.35 * lexical + bonus
        ranked.append((score, doc))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [{"score": round(score, 4), **doc} for score, doc in ranked[:top_k] if score > 0]
