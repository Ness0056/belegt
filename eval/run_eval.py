"""Measure how trustworthy the assistant is.

  python eval/run_eval.py            (offline, extractive answers)
  python eval/run_eval.py --llm      (uses Claude if ANTHROPIC_API_KEY is set)

Three numbers matter:
  answer accuracy   - answerable questions answered correctly and verified
  refusal accuracy  - unanswerable questions correctly refused instead of made up
  hallucination catch rate - wrong answers the verifier rejects or flags
                             (plus: correct answers it wrongly rejects = false alarms)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from belegt import Assistant  # noqa: E402

# so this is the exam for the whole system can we catch AI Hallucintion ?? 
def norm(s: str) -> str:
    return s.lower().replace(",", "").replace(".", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()
    bot = Assistant(ROOT / "docs", use_llm=args.llm)
    lines = [f"# Evaluation ({bot.mode} mode)\n"]

    questions = json.loads((ROOT / "eval/questions.json").read_text(encoding="utf-8"))
    answerable = [q for q in questions if q["expect"]]
    unanswerable = [q for q in questions if not q["expect"]]
    correct = refused_ok = 0
    lines.append("## Questions\n\n| Question | Result | Answer |\n|---|---|---|")
    for item in questions:
        r = bot.ask(item["q"])
        if item["expect"]:
            ok = (not r.refused and r.verdict.status != "REJECTED"
                  and norm(item["expect"]) in norm(r.answer))
            correct += ok
        else:
            ok = r.refused
            refused_ok += ok
        shown = "refused" if r.refused else r.answer.replace("|", "/")
        lines.append(f"| {item['q']} | {'✅' if ok else '❌'} | {shown} |")

    cases = json.loads((ROOT / "eval/hallucinations.json").read_text(encoding="utf-8"))
    wrong = [c for c in cases if c["wrong"]]
    right = [c for c in cases if not c["wrong"]]
    caught = false_alarms = 0
    lines.append("\n## Verifier on prepared answers\n\n| Answer | Type | Verdict | Reason |\n|---|---|---|---|")
    for c in cases:
        v = bot.check(c["answer"])
        flagged = v.status != "VERIFIED"
        if c["wrong"]:
            caught += flagged
        else:
            false_alarms += v.status == "REJECTED"
        reasons = "; ".join(r for chk in v.checks for r in chk.reasons)
        good = flagged == c["wrong"]
        lines.append(f"| {c['answer']} | {c['type']} | {'✅' if good else '❌'} {v.status} | {reasons} |")

    summary = [
        "\n## Summary\n",
        f"- Answer accuracy: **{correct}/{len(answerable)}**",
        f"- Refusal accuracy: **{refused_ok}/{len(unanswerable)}**",
        f"- Hallucination catch rate: **{caught}/{len(wrong)}**",
        f"- False alarms on correct answers: **{false_alarms}/{len(right)}**",
    ]
    lines[1:1] = summary
    report = "\n".join(lines) + "\n"
    (ROOT / "eval/report.md").write_text(report, encoding="utf-8")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
