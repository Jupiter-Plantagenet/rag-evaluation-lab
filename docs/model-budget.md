# Model budget

The frozen experimental runs used `gemini-3.1-flash-lite` for both arms at
temperature 0. The model name is recorded in the immutable traces.

Provider execution is optional and is not required to inspect, validate, or
re-score the experiment. The repository does not contain a committed response
cache that replays the original provider calls. Frozen outputs are instead
preserved in traces and can be re-scored without provider access.

CI integration tests use deterministic scripted responses. Semantic
model-assisted grading is not part of this release.
