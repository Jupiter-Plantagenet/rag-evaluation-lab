"""RAG Evaluation Lab -- an evaluation and regression-testing harness for
document-grounded retrieval-augmented generation.

Not a chatbot library. The pipelines exist so there is something to measure.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Bumped whenever the TraceRecord shape changes incompatibly. Recorded in every
# trace so a reader can tell which contract a stored run was written against --
# without it, old runs silently misparse against new code.
TRACE_SCHEMA_VERSION = 1

# Bumped whenever a change alters what a pipeline produces for identical input.
# Distinct from __version__, which tracks the package as a distributable.
PIPELINE_SCHEMA_VERSION = 1

__all__ = ["__version__", "TRACE_SCHEMA_VERSION", "PIPELINE_SCHEMA_VERSION"]
