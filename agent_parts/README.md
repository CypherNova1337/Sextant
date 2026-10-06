# Agent parts under evaluation

Pieces not yet in the submitted agent, kept here until measured.

- `sx_find.py` ranks the repository's non-test Python files by the words
  given on its command line (identifiers and distinctive terms from the
  issue), weighting each word by how rare it is across files and tripling
  it when a file defines a function or class of that name; files under
  scripts/, examples/, docs/, benchmarks/ and tools/ count half. It is
  written without braces so it can be embedded in the prompt, where ADK
  would otherwise read `{...}` as a session-state placeholder.

  Offline, on the 87 scoreable dev tasks, the same ranking applied to the
  whole issue text puts a file of the reference fix in the top 5 for 75% of
  tasks and the top 10 for 84% (`scripts/localize_eval.py`, on the provided
  code graphs). On the 11 local snapshots, with the issue title plus its
  code-like terms as the words, the fix's file is in the top 5 for 8 of 11.
  Not yet tested with the model choosing the words.
