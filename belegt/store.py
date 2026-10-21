"""Load documents, split them into passages and find the passages that fit a question."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Passage:
    id: int          # number used in citations, e.g. [3]
    doc: str         # file name
    title: str       # document heading
    text: str


def _read(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8")


def load_passages(folder: str | Path) -> list[Passage]:
    """One passage per paragraph, so every citation points to a small, checkable piece of text."""
    passages: list[Passage] = []
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() not in {".md", ".txt", ".pdf"}:
            continue
        text = _read(path)
        title = path.stem
        for block in re.split(r"\n\s*\n", text): # basically so we split them paragraphs first and assign a number so it s easier to adress than the whole report ;) 
            block = " ".join(block.split())
            if not block:
                continue
            if block.startswith("#"):
                title = block.lstrip("# ")
                continue
            passages.append(Passage(len(passages) + 1, path.name, title, block))
    return passages


class Retriever:
    """TF(term frequency)and IDF(inverse document ftrequency far more important ) on character n-grams: no download needed, and it copes with German and English
    word forms (Prüfung / Prüfungen, test / tested) and short IDs like S3."""

    def __init__(self, passages: list[Passage]):
        self.passages = passages
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                          sublinear_tf=True, lowercase=True) # so like we use not whole words also but words ranges so Prüfung would be prü rüf ect 
        self.matrix = self.vectorizer.fit_transform(
            [f"{p.title} {p.text}" for p in passages])

    def search(self, question: str, k: int = 4) -> list[tuple[Passage, float]]:
        scores = cosine_similarity(self.vectorizer.transform([question]), self.matrix)[0] # finally the cosine similarity 1 being same 0 not related we love math ;) 
        ranked = sorted(zip(self.passages, scores), key=lambda x: x[1], reverse=True)
        return [(p, float(s)) for p, s in ranked[:k]]

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.vectorizer.transform([a, b])
        return float(cosine_similarity(va, vb)[0][0])
