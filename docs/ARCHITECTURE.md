# Architecture

Key technical decisions behind QSolva.

## AI Pipelines

Ticket priority classification and RAG-based resolution assistance run as
independent AI stages.

### Priority Classification

Gemini evaluates the ticket and assigns a priority:

- `low`
- `medium`
- `high`
- `critical`

Admins can review and override the AI classification when necessary.

### RAG Resolution Assistance

The RAG pipeline uses ticket embeddings and pgvector similarity search to
retrieve relevant historical resolutions before Gemini generates a
troubleshooting recommendation.

Each AI stage tracks its own status:

- `pending`
- `success`
- `failed`

RAG also supports `no_match` when no sufficiently similar historical
resolution is found. This is a valid result, not an AI failure.

Failed AI stages can be retried through a single Admin action without
duplicating concurrent AI requests.

## Knowledge & RAG

Historical ticket resolutions provide evidence for future troubleshooting
recommendations.

QSolva distinguishes between:

- **Staff-confirmed resolutions** — the Staff member confirms that the
  solution worked.
- **Admin-resolved tickets** — an Admin provides a resolution and resolves
  the ticket, but Staff confirmation is not available.
- **Unconfirmed tickets** — there is no reliable resolution evidence.

Only usable resolution evidence contributes to AI recommendations and
knowledge generation.

The backend calculates evidence such as successful-resolution counts rather
than relying on the language model to generate these values.

## Recurring Issues

Tickets are grouped using incremental embedding similarity rather than a
traditional offline clustering algorithm.

When similar tickets accumulate, QSolva identifies recurring issues and
tracks their:

- Volume
- Symptoms
- Trends
- Common resolutions
- Resolution success

Gemini can summarize recurring issues and generate Help Center article
drafts. Articles require Admin review before they can be published.

## Knowledge Loop

QSolva turns resolved support cases into reusable organizational knowledge.

```text
Ticket
  ↓
Resolution
  ↓
Staff Feedback
  ↓
Resolution Evidence
  ↓
Recurring Issue
  ↓
Help Center Draft
  ↓
Admin Review
  ↓
Published Knowledge