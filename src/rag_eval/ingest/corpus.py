"""Corpus loading and the manifest that pins it.

The manifest exists so a run can prove which bytes it was computed against. A
result that cannot name its corpus is not reproducible, only repeatable.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

from rag_eval.errors import CorpusError
from rag_eval.types import Document

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Corpus:
    documents: dict[str, Document]

    def __len__(self) -> int:
        return len(self.documents)

    def __getitem__(self, doc_id: str) -> Document:
        try:
            return self.documents[doc_id]
        except KeyError as e:
            raise CorpusError(f"no such document: {doc_id!r}") from e

    def bodies(self) -> dict[str, str]:
        return {d: doc.body for d, doc in self.documents.items()}

    @property
    def manifest_sha(self) -> str:
        """One hash over every document id and body, order-independent.

        Folded into cache keys and recorded in every trace, so an edit to any
        document invalidates the derived artifacts rather than silently leaving
        an index built from text that no longer exists.
        """
        h = hashlib.sha256()
        for doc_id in sorted(self.documents):
            h.update(doc_id.encode("utf-8"))
            h.update(self.documents[doc_id].sha256.encode("utf-8"))
        return h.hexdigest()

    def manifest(self) -> dict:
        return {
            "manifest_sha": self.manifest_sha,
            "n_documents": len(self.documents),
            "documents": {
                doc_id: {
                    "sha256": d.sha256,
                    "chars": len(d.body),
                    "version": d.front_matter.get("version"),
                    "superseded": d.is_superseded,
                }
                for doc_id, d in sorted(self.documents.items())
            },
        }


def load_corpus(corpus_dir: Path) -> Corpus:
    """Load every Markdown document in a directory.

    Bodies are NFC-normalised and nothing else. Whitespace is deliberately left
    alone: the dataset's evidence offsets index into exactly these characters,
    so collapsing whitespace here would shift every ground-truth span in the
    project by an amount that varies per document.
    """
    documents: dict[str, Document] = {}
    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        if raw.startswith("﻿"):
            raise CorpusError(
                f"{path.name} starts with a BOM. Corpus bytes are hashed into every run "
                f"manifest, so a BOM makes the manifest platform-dependent."
            )
        m = FRONT_MATTER_RE.match(raw)
        if m is None:
            raise CorpusError(f"{path.name}: no YAML front matter")

        fm = yaml.safe_load(m.group(1)) or {}
        body = unicodedata.normalize("NFC", m.group(2))
        doc_id = fm.get("doc_id") or path.stem

        if doc_id in documents:
            raise CorpusError(f"duplicate doc_id {doc_id!r}")

        documents[doc_id] = Document(
            doc_id=doc_id,
            title=fm.get("title", doc_id),
            body=body,
            front_matter=fm,
            sha256=sha256_text(body),
        )

    if not documents:
        raise CorpusError(f"no documents found in {corpus_dir}")
    return Corpus(documents=documents)
