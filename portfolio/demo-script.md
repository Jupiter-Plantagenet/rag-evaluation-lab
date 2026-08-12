# Demo script — 60–90 seconds

Show the evidence, not a chatbot conversation.

1. Open development case F-15 and its quote-anchored evidence span.
2. Show the baseline trace: the observed failure class was `unsupported_claim`.
3. Show the diagnosis: fixed-size chunks separated the answer row from its table
   column headers.
4. Show the structure-aware chunking regression assertion that preserves the
   table-context property.
5. Show the corrected-v2 report: configured systems used k=4 versus k=8.
6. Show the post-hoc common-budget table (both k=4): MRR +0.150, CI includes zero.

Say: “The audit prevented additional context budget from being presented as
proven ranking improvement.”

Use `python -m pytest tests/regression -m regression -q` and
`python scripts/verify_frozen.py` on screen. Linux and Windows CI are configured;
verify this corrected revision after it is pushed.
