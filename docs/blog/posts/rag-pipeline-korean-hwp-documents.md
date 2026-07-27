---
date: 2026-06-09
authors: [ebenworks]
categories:
  - Tutorials
description: >-
  Build a Retrieval-Augmented Generation (RAG) pipeline over Korean HWP / HWPX
  documents in Python — from text extraction through chunking and embeddings.
---

# Building a RAG pipeline over Korean HWP documents

Most Retrieval-Augmented Generation (RAG) tutorials assume your corpus is PDFs
or Markdown. But if you're building AI over **Korean** enterprise or government
data, your corpus is **HWP** — the `.hwp` / `.hwpx` formats from Hancom Office.
And that's where pipelines quietly break: the standard ingestion stack
(`pdfplumber`, `python-docx`, `unstructured`) can't read HWP at all, so the
documents never make it into your vector store.

This guide walks through a complete RAG ingestion pipeline over Korean HWP
documents in Python, using [`hwpkit`](https://github.com/psychofict/hwpkit) as
the extraction step — pure Python, no Hancom, no Windows.

<!-- more -->

## The pipeline

```
HWP / HWPX  →  extract text (hwpkit)  →  chunk  →  embed  →  vector store  →  retrieve
```

The only Korean-specific part is the first arrow. Everything after it is your
normal RAG stack.

```bash
pip install hwpkit[full] sentence-transformers
```

## 1. Extract text from the HWP corpus

`extract_text_from_file` reads both `.hwp` and `.hwpx`, auto-detecting the
format, and returns clean paragraph text (table cells included, inline controls
stripped):

```python
import glob
from hwpkit import extract_text_from_file

def load_corpus(root: str):
    for path in glob.glob(f"{root}/**/*.hwp*", recursive=True):   # .hwp + .hwpx
        try:
            text = extract_text_from_file(path)
        except Exception as e:
            print(f"skip {path}: {e}")
            continue
        if text.strip():
            yield path, text
```

## 2. Chunk

Korean text chunks well on paragraph boundaries (which `hwpkit` preserves as
newlines), with a token/character cap per chunk and a little overlap:

```python
def chunk(text: str, max_chars: int = 800, overlap: int = 100):
    paras = [p for p in text.split("\n") if p.strip()]
    buf, out = "", []
    for p in paras:
        if len(buf) + len(p) > max_chars and buf:
            out.append(buf)
            buf = buf[-overlap:]
        buf += ("\n" if buf else "") + p
    if buf.strip():
        out.append(buf)
    return out
```

## 3. Embed

Use a multilingual or Korean-tuned embedding model so Korean queries match
Korean passages:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("intfloat/multilingual-e5-base")  # handles Korean well

def embed(chunks: list[str]):
    # e5 models expect a "passage: " / "query: " prefix
    return model.encode([f"passage: {c}" for c in chunks], normalize_embeddings=True)
```

## 4. Store, with provenance

Keep the source path and chunk index as metadata so answers can cite the
original document:

```python
records = []
for path, text in load_corpus("corpus"):
    chunks = chunk(text)
    vectors = embed(chunks)
    for i, (c, v) in enumerate(zip(chunks, vectors)):
        records.append({
            "id": f"{path}#{i}",
            "vector": v,
            "text": c,
            "metadata": {"source": path, "chunk": i},
        })

vector_db.upsert(records)   # Qdrant / pgvector / Chroma / FAISS — your choice
```

## 5. Retrieve and answer

```python
def search(question: str, k: int = 5):
    qv = model.encode(f"query: {question}", normalize_embeddings=True)
    hits = vector_db.query(qv, top_k=k)
    context = "\n\n".join(h["text"] for h in hits)
    sources = {h["metadata"]["source"] for h in hits}
    return context, sources

context, sources = search("계약 해지 조건이 어떻게 되나요?")
# feed `context` + the question to your LLM; cite `sources`
```

## Why this matters

If your retrieval pipeline can't read HWP, it can't index Korean enterprise
data — period. `hwpkit` is the missing ingestion step: a clean, dependency-light
Korean-text source that drops into any RAG stack, on any platform, with no
Hancom dependency. Pair it with a multilingual embedding model and you have a
RAG system that actually covers the documents Korean organizations run on.

See the [quickstart](../../quickstart.md) for more, or
[how to read HWP files in Python](read-korean-hwp-files-in-python.md)
for the extraction basics.

```bash
pip install hwpkit[full]
```

- **GitHub:** [github.com/psychofict/hwpkit](https://github.com/psychofict/hwpkit)
- **Docs:** [hwpkit.ebenworks.co](https://hwpkit.ebenworks.co)
