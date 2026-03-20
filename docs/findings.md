Some emails have HTML data under the mime type text/plain.
<<<<<<< HEAD

Forwarded Emails aren't being parsed correctly (need to find out how to identify these - TREATMENT)
    - For now just treat forwarded messages as the first-level message if none exist, ignore it.
=======
Forwarded Emails aren't being parsed correctly (need to find out how to identify these)
>>>>>>> main



## TODO: 
1) SQL Query for emails by normalized text LENGTH by buckets of size 100 (incrementally)
2) Run Parser on sample of emails (take distribution of 200 emails over the buckets uniformly)
3) Evaluate parser performance & run normaliser on emails to evaluate performance.

TODO: Ensure normaliser uses regional block score instead of individual, due to block identification not being robust.
TODO: Store emails that are dropped with appropriate reason (perhaps not occupies to much storage)



## Optimization Checklist

### Preprocessing / Normalization

- Improve footer/compliance/disclaimer stripping
- Handle forwarded emails more deliberately
- Preserve useful contact/business info while removing legal noise
- Review cases where normalization strips too much
- Review cases where normalization leaves too much junk

### Chunking

- Revisit chunking strategy after retrieval testing
- Add proper tokenizer-based counts (`tiktoken`) instead of word-based approximation
- Re-evaluate overlap behavior
- Review very long threads/messages that explode into many chunks
- Decide whether single-message vs multi-message threads should be chunked differently

### Missing-Content Handling

- Review emails within threads that have no `normalized_text`
- Decide whether message numbering should reflect:
  - original thread positions, or
  - only embeddable messages
- Consider whether embedding text should omit “Message X of Y” if skipped messages make numbering awkward

### Metadata / Embedding Text

- Reassess what metadata should be embedded vs stored only for filtering
- Consider normalized subject in embedding text
- Consider storing token count once tokenizer is correct
- Review whether sender/subject/date formatting is helping retrieval

### Pipeline / Scalability

- Parallelize thread chunk preparation (e.g., with Celery)
- Batch embedding requests efficiently
- Add idempotent chunk/vector upserts
- Add better observability around skipped emails/chunks

### Retrieval / RAG Quality

- Test real queries before changing preprocessing
- Inspect bad retrievals and trace whether the issue arose from:
  - normalization
  - chunking
  - metadata
  - embedding text
  - retrieval logic itself

---

### Cases Identified

- **16adbdec8aa7c2c8** (threadId): Forwarded Messages