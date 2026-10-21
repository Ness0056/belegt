"""Command line:  python -m belegt ask "question"   |   python -m belegt check "answer with [n]" """
import argparse
import sys

from .assistant import NOT_FOUND, Assistant

COLORS = {"VERIFIED": "\033[32m", "NEEDS REVIEW": "\033[33m", "REJECTED": "\033[31m",
          "OK": "\033[32m", "WEAK": "\033[33m", "FAIL": "\033[31m"}
END = "\033[0m"


def show_verdict(verdict):
    print(f"\nVerdict: {COLORS[verdict.status]}{verdict.status}{END}")
    for c in verdict.checks:
        why = f"  ({'; '.join(c.reasons)})" if c.reasons else ""
        print(f"  {COLORS[c.status]}{c.status:<4}{END} {c.sentence}{why}")


def main():
    ap = argparse.ArgumentParser(prog="belegt", description="Answers only what the documents back up.")
    ap.add_argument("command", choices=["ask", "check"])
    ap.add_argument("text")
    ap.add_argument("--docs", default="docs")
    ap.add_argument("--offline", action="store_true", help="never call an LLM")
    args = ap.parse_args()

    bot = Assistant(args.docs, use_llm=False if args.offline else None)
    if args.command == "check":
        show_verdict(bot.check(args.text))
        return

    r = bot.ask(args.text)
    print(f"[mode: {r.mode}]")
    if r.refused:
        print("I can't answer that from the documents. Nothing found that backs up an answer.")
        sys.exit(0)
    if r.verdict.status == "REJECTED":
        print("The draft answer contained claims the sources don't support, so it was withheld.")
    else:
        print(r.answer)
    show_verdict(r.verdict)
    print("\nSources:")
    for p in r.sources:
        print(f"  [{p.id}] {p.doc}: {p.text[:90]}...")


if __name__ == "__main__":
    main()
