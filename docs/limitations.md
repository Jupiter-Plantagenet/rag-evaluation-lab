# Limitations

- The 14-document NovaPay corpus is synthetic, single-author and controlled;
  this is not external validation on production documentation.
- The study has 50 cases (22 held out), so category-level estimates are small.
- Citation metrics establish that labels resolve to context shown to the model;
  they do not establish semantic entailment.
- The baseline and improved configured systems use k=4 and k=8 respectively.
  Common-budget results are post-hoc sensitivity analysis, not a new endpoint.
- The committed dataset is readable. The documented experimental run path
  requires explicit held-out authorization and logs access; the ledger records
  the two declared experimental accesses, and Git history is consistent with the
  stated chronology. This is procedural evidence, not a physical access barrier.
- The project is not evidence of production-scale serving, security, or load
  characteristics.
