# Sextant

An autonomous coding agent built on Gemma 4, post-trained to read a bug report,
navigate an unfamiliar Python repository, and emit a unified diff that makes the
failing tests pass. Entry for the Gemma 4 Developer Agent Competition on Kaggle.

## Setup after cloning

```sh
git config user.name  "CypherNova1337"
git config user.email "131998711+CypherNova1337@users.noreply.github.com"
git config core.hooksPath .githooks
```

The hooks refuse commits and pushes with the wrong author identity or with
attribution in messages or changes. To sweep every tracked file by hand:

```sh
python3 .githooks/attribution.py tree
```

Competition data goes in `data/` (ignored by git).
