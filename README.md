# Belegt — an AI assistant that only says what it can prove

*"belegt" = German for "backed up by evidence"*

## The problem

Most companies now experiment with generative AI, but few get it into production. In Deloitte's survey of
2,770 leaders, 68% had moved no more than 30% of their gen-AI experiments into production. Only 23% felt
highly prepared for the risk and governance side. The core issue is trust. A chatbot that confidently invents
a number in a test report or datasheet is worse than no chatbot.

## What Belegt does

You ask a question about a set of technical documents (test reports, datasheets, in German or English):

1. **Retrieve.** Find the paragraphs that fit the question (TF-IDF on character n-grams, works offline,
   handles German and English word forms).
2. **Answer with citations.** Every sentence must end with the source it comes from, e.g. `[11]`.
   Uses Claude if an API key is set; otherwise falls back to quoting the best-matching source sentences.
3. **Verify every sentence** against the source it cites:
   - **Numbers:** every number must appear in the cited source (`200,000` and `200000`, `0,2` and `0.2` are matched).
   - **Verdicts:** "passed" vs "failed" / "bestanden" vs "nicht bestanden" must agree with the source.
   - **Wording:** if too little of the claim appears in the source, the answer is flagged for human review.
   - **No citation** means the sentence fails.
4. **Show, flag or refuse.** VERIFIED answers are shown. NEEDS REVIEW answers are shown with a warning.
   REJECTED answers are withheld. If nothing in the documents fits, it says so instead of guessing.

`check` mode verifies an answer written somewhere else, for example by another chatbot or in a draft report.

## Try it

```bash
pip install -r requirements.txt

python -m belegt ask "Which sample failed the overload test?" --offline
python -m belegt ask "Wie hoch war die maximale Erwärmung?" --offline
python -m belegt ask "What does the HVC-400 cost?" --offline          # -> refuses

python -m belegt check "Sample S3 passed the overload test after 18,500 cycles. [17]"
# -> REJECTED: number not in source: 18500; says 'pass' but source says 'fail'

# with an LLM
export ANTHROPIC_API_KEY=...
python -m belegt ask "Which samples passed the endurance test?"
```

Put your own `.md`, `.txt` or `.pdf` files in `docs/` (or pass `--docs path`).
The three sample documents are **fictional** test reports and a datasheet for a high-voltage contactor.

## Evaluation

`python eval/run_eval.py` runs 20 questions and 20 prepared answers (12 of them deliberately wrong)
and writes `eval/report.md`.

| Metric (offline mode) | Result |
|---|---|
| Answerable questions answered correctly | 15 / 15 |
| Unanswerable questions correctly refused | 4 / 5 |
| Wrong answers caught (wrong numbers, flipped verdicts, wrong source, invented claims) | 12 / 12 |
| Correct answers wrongly rejected | 0 / 8 |

**Known limit:** "How many employees does the lab have?" is not refused in offline mode, because the
word "Labor" appears in a report. Keyword matching can't tell that the document doesn't answer the
question. Semantic retrieval or LLM mode would handle this; it's the next step.

## Structure

```
belegt/store.py      load documents, split into passages, retrieve
belegt/assistant.py  pipeline: retrieve -> answer -> verify -> show / flag / refuse
belegt/verify.py     the claim checker (numbers, pass/fail, wording, citations)
eval/                test questions, hallucination cases, evaluation script and report
docs/                fictional sample documents (DE + EN)
```

## Next steps

- Semantic embeddings for retrieval, keeping TF-IDF as an offline fallback
- A small web interface that highlights the cited passage next to each sentence
- Unit checks (mΩ vs Ω, K vs °C) in the verifier
