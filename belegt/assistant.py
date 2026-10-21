"""Question -> retrieve -> answer with citations -> verify -> show, flag or refuse."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from collections import Counter

from .store import Passage, Retriever, load_passages
from .verify import Verdict, _stems, split_sentences, verify
#my pretty little manager 

QUESTION_WORDS = {w[:5] for w in """what which who when where why how does many much
welche welcher welches wann warum wie viel viele hoch""".split()}

NOT_FOUND = "NOT_IN_SOURCES"

PROMPT = """Answer the question using ONLY the numbered sources below.
Rules:
- End every sentence with the number of the source it comes from, like [2].
- Copy numbers and units exactly as they appear in the source.
- If the sources do not contain the answer, reply with exactly: NOT_IN_SOURCES
- Answer in the language of the question, in at most three sentences.

Sources:
{sources}

Question: {question}"""


@dataclass
class Result:
    question: str
    answer: str
    verdict: Verdict | None
    sources: list[Passage]
    mode: str

    @property
    def refused(self) -> bool:
        return self.answer == NOT_FOUND


class Assistant:
    def __init__(self, folder: str, min_score: float = 0.12, use_llm: bool | None = None):
        self.passages = load_passages(folder)
        self.by_id = {p.id: p for p in self.passages}
        self.retriever = Retriever(self.passages)
        self.min_score = min_score
        if use_llm is None:
            use_llm = bool(os.environ.get("ANTHROPIC_API_KEY"))
        self.mode = "llm" if use_llm else "extractive"

    # answer generation 
    def _keywords(self, question: str) -> set[str]:
        """Content words of the question, minus question words and terms found almost everywhere
        (like the product name), because those match every passage and prove nothing."""
        if not hasattr(self, "_common"):
            df = Counter(s for p in self.passages for s in _stems(f"{p.title} {p.text}"))
            self._common = {s for s, n in df.items() if n > 0.4 * len(self.passages)}
        return _stems(question) - QUESTION_WORDS - self._common

    def _extractive(self, question: str, hits: list[Passage]) -> str:
        """Offline fallback: return the source sentences that share the most key terms with the
        question. If no sentence shares any, the answer is not in the documents."""
        keys = self._keywords(question)
        candidates = []
        for p in hits:
            for s in split_sentences(p.text):
                overlap = len(keys & _stems(s))
                if overlap:
                    candidates.append((overlap, self.retriever.similarity(question, s), s, p.id))
        if not candidates:
            return NOT_FOUND
        candidates.sort(reverse=True)
        top = candidates[0][0]
        best = [c for c in candidates if c[0] == top][:2]
        return " ".join(f"{s.rstrip('.')}. [{pid}]" for _, _, s, pid in best)

    def _llm(self, question: str, hits: list[Passage]) -> str:
        import anthropic
        sources = "\n".join(f"[{p.id}] ({p.doc}) {p.text}" for p in hits)
        msg = anthropic.Anthropic().messages.create(
            model=os.environ.get("BELEGT_MODEL", "claude-sonnet-5-5"),
            max_tokens=400,
            messages=[{"role": "user", "content": PROMPT.format(sources=sources, question=question)}],
        )
        return msg.content[0].text.strip()

    # pipeline 
    def ask(self, question: str) -> Result:
        found = self.retriever.search(question, k=4) # get the 4 best paragraphs  for good margin range 
        hits = [p for p, score in found if score >= self.min_score]
        if not hits: # basically nothing fits this -> refused  my dudes 
            return Result(question, NOT_FOUND, None, [], self.mode)
        answer = self._llm(question, hits) if self.mode == "llm" else self._extractive(question, hits) #all good write answer
        if answer == NOT_FOUND:
            return Result(question, NOT_FOUND, None, hits, self.mode) # also refused 
        return Result(question, answer, verify(answer, self.by_id), hits, self.mode) # check it 

    def check(self, answer: str) -> Verdict: # the bonus round is checking just for the answer of another bot or collegue or those friends who always think their facts are right when they are clearly wrong 
        """Verify an answer written elsewhere (another chatbot, a colleague, a draft report)."""
        return verify(answer, self.by_id) # honest limit is it only checks if u state which paragraph is is exp [2]
#so if retievaal gate is <0.12 we move forward without the answer before the AI is even involved for less cost 
# writer gate : my lovely AI who double checks 
# verfication gate we move forward to verify.py  