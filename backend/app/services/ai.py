"""Gemini-backed AI capabilities: embeddings, priority classification, and
resolution suggestion synthesis. All calls go through the free-tier Gemini API.
"""

import asyncio
import base64
import json
import logging
import math

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
EMBEDDING_DIM = 768  # must match the `vector(768)` column in ticket_embeddings
RETRYABLE_STATUS = {429, 503}
MAX_RETRIES = 3
# Screenshots are the whole point of letting a reporter attach one, but an
# unbounded number would blow up the free-tier request size/quota — cap both
# how many we send and how large each one can be.
MAX_IMAGE_ATTACHMENTS = 4
MAX_IMAGE_BYTES = 15 * 1024 * 1024


async def _post_with_retry(url: str, payload: dict) -> httpx.Response:
    """Gemini's free tier returns 503 under load fairly often (seen in
    practice, not hypothetical) and 429 when rate-limited. Both are worth
    a short backoff-retry rather than failing the whole background task."""
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(MAX_RETRIES):
            resp = await client.post(url, json=payload)
            if resp.status_code not in RETRYABLE_STATUS or attempt == MAX_RETRIES - 1:
                resp.raise_for_status()
                return resp
            await asyncio.sleep(2**attempt)
    raise RuntimeError("unreachable")


async def embed_text(text: str) -> list[float]:
    url = f"{GEMINI_BASE}/models/{settings.embedding_model}:embedContent?key={settings.gemini_api_key}"
    payload = {
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": EMBEDDING_DIM,
    }
    resp = await _post_with_retry(url, payload)
    values = resp.json()["embedding"]["values"]

    # Google recommends re-normalizing to unit length when requesting a
    # truncated (non-default) output dimensionality from gemini-embedding-001.
    norm = math.sqrt(sum(v * v for v in values))
    if norm > 0:
        values = [v / norm for v in values]
    return values


async def _fetch_image_parts(attachment_urls: list[str]) -> list[dict]:
    """Downloads a ticket's image attachments and returns them as Gemini
    inline_data parts, so triage/suggestion prompts can see what's actually
    in a screenshot instead of relying on the reporter's typed description
    alone. Skips anything that isn't fetchable or isn't an image rather than
    failing the whole AI stage over one bad attachment."""
    parts: list[dict] = []
    if not attachment_urls:
        return parts
    async with httpx.AsyncClient(timeout=15) as client:
        for url in attachment_urls[:MAX_IMAGE_ATTACHMENTS]:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                logger.warning("Could not fetch ticket attachment for AI analysis: %s", url)
                continue
            mime_type = resp.headers.get("content-type", "").split(";")[0]
            if not mime_type.startswith("image/") or len(resp.content) > MAX_IMAGE_BYTES:
                continue
            parts.append({"inline_data": {"mime_type": mime_type, "data": base64.b64encode(resp.content).decode()}})
    return parts


def _is_unprocessable_image_error(exc: httpx.HTTPStatusError) -> bool:
    """Gemini's response for a corrupted/malformed image it can't decode —
    distinct from a merely unreachable URL, which _fetch_image_parts already
    handles per-image. Matched narrowly on the actual error message (not
    just "any 400") so an unrelated bad-request bug elsewhere in the prompt
    still surfaces as a real failure instead of being silently retried away."""
    if exc.response.status_code != 400:
        return False
    try:
        message = exc.response.json().get("error", {}).get("message", "").lower()
    except ValueError:
        return False
    return "image" in message and "process" in message


async def _generate_json(prompt: str, image_parts: list[dict] | None = None) -> dict:
    url = f"{GEMINI_BASE}/models/{settings.llm_model}:generateContent?key={settings.gemini_api_key}"

    async def call(text: str, parts: list[dict]) -> dict:
        payload = {
            "contents": [{"parts": [{"text": text}, *parts]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        resp = await _post_with_retry(url, payload)
        response_text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(response_text)

    try:
        return await call(prompt, image_parts or [])
    except httpx.HTTPStatusError as e:
        if image_parts and _is_unprocessable_image_error(e):
            # A single corrupted attachment shouldn't take down AI enrichment
            # for the whole ticket — retry text-only rather than failing the
            # stage outright. The prompt text may still reference "the
            # screenshot below" (it was built assuming image_parts would be
            # attached), so correct that explicitly rather than leaving a
            # dangling reference to an image that's no longer there.
            logger.warning("Gemini rejected an attached image as unprocessable — retrying text-only")
            corrected_prompt = (
                prompt
                + "\n\n(Note: an attached image could not be processed and was omitted — "
                "base your answer on the text above only.)"
            )
            return await call(corrected_prompt, [])
        raise


async def classify_priority(
    title: str, description: str, category: str, attachment_urls: list[str] | None = None
) -> tuple[str, float, str]:
    image_parts = await _fetch_image_parts(attachment_urls or [])
    prompt = f"""You are an IT service desk triage assistant. Classify this ticket's priority
using these severity definitions:

LOW:
Minor issue affecting one user with little impact on their work.
Example: a cosmetic glitch, a minor software inconvenience.

MEDIUM:
A user cannot perform an important task, but a workaround exists,
or the impact is limited to a single user.

HIGH:
A user is unable to perform an important work function with little
or no workaround, or multiple users are affected.

CRITICAL:
A major business function or many users are affected. Examples:
company-wide network outage, widespread system outage, a security
incident, or a major service being completely unavailable.

Consider: number of users affected, business/work impact, availability
of a workaround, security implications, and urgency.

Ticket:
Title: {title}
Description: {description}
Category: {category}
{"One or more screenshots the reporter attached are included below — read any error messages, dialogs, or visible context in them and weigh that alongside the description." if image_parts else ""}

Respond with JSON only:
{{"priority": "low"|"medium"|"high"|"critical", "confidence": 0.0-1.0, "reason": "one short sentence explaining the classification"}}"""
    result = await _generate_json(prompt, image_parts)
    return result["priority"], float(result["confidence"]), result["reason"]


async def synthesize_suggestion(
    title: str,
    description: str,
    similar_tickets: list[dict],
    attachment_urls: list[str] | None = None,
) -> tuple[str, float]:
    """similar_tickets: [{"title", "description", "resolution", "similarity"}]"""
    if not similar_tickets:
        return "", 0.0

    image_parts = await _fetch_image_parts(attachment_urls or [])

    evidence_text = "\n\n".join(
        f"Similar ticket (similarity {t['similarity']:.2f}):\n"
        f"Problem: {t['title']} - {t['description']}\n"
        f"Resolution: {t['resolution']}"
        for t in similar_tickets
    )

    prompt = f"""You are an IT service desk assistant. A new ticket has come in:

Title: {title}
Description: {description}
{"One or more screenshots the reporter attached are included below — use any error messages or visible context in them to judge whether a similar ticket's resolution actually applies here." if image_parts else ""}

Here are similar previously resolved tickets:

{evidence_text}

Based on the common pattern in these resolutions, write a short numbered list of concrete
action steps the user can try, formatted as plain text with one step per line, e.g.
"1. Do this\n2. Do that\n3. Then this". Keep each step short and actionable — no preamble
or closing remarks, just the numbered steps. If the similar tickets don't share a
consistent resolution, say so with low confidence instead of guessing.

Respond with JSON only: {{"resolution": "numbered steps as described above", "confidence": 0.0-1.0}}"""
    result = await _generate_json(prompt, image_parts)
    return result["resolution"], float(result["confidence"])


async def summarize_cluster(tickets: list[dict]) -> tuple[str, list[str]]:
    """tickets: [{"title", "description"}] — a sample from a recurring-issue
    cluster. Called only when a cluster grows (see services/issues.py), not
    on every read, to keep this off the free-tier quota's critical path."""
    tickets_text = "\n\n".join(f"Title: {t['title']}\nDescription: {t['description']}" for t in tickets)

    prompt = f"""These IT service desk tickets have been grouped together as the same
recurring problem:

{tickets_text}

Write a short, specific label for this recurring issue (e.g. "VPN Connection Timeout"),
and list 3-5 common symptoms across these tickets, phrased briefly.

Respond with JSON only: {{"label": "short issue name", "symptoms": ["symptom 1", "symptom 2", ...]}}"""
    result = await _generate_json(prompt)
    return result["label"], list(result["symptoms"])


async def generate_kb_article(
    label: str,
    symptoms: list[str],
    confirmed_resolution: str,
    staff_confirmed_count: int,
    admin_resolved_count: int,
    member_count: int,
) -> tuple[str, str]:
    """Drafts a self-service Help Center article for a recurring issue.
    Only called once a cluster has at least one usable resolution to draw
    from (see services/issues.py's gather_evidence) — an admin's own
    resolution counts even before staff confirms it, since otherwise a
    freshly-solved new problem would sit unused until someone happens to
    click confirm. Staff-confirmed evidence is preferred when both exist."""
    symptoms_text = "\n".join(f"- {s}" for s in symptoms) if symptoms else "Not documented."
    evidence_note = (
        f"{staff_confirmed_count} case(s) where staff explicitly confirmed this resolution worked, "
        f"and {admin_resolved_count} case(s) an admin resolved this way without staff confirmation yet."
    )

    prompt = f"""Generate a self-service troubleshooting article using only the provided
historical evidence and resolution below. Do not invent procedures, causes, or solutions
that are not supported by this evidence.

Recurring issue: {label}
Reported in {member_count} similar tickets.

Common symptoms:
{symptoms_text}

Resolution used for this issue (from a similar past ticket):
{confirmed_resolution}

Evidence backing this resolution: {evidence_note}

Write a short, friendly Q&A article for employees (no jargon). Phrase the question the way
an employee would ask it. Present the resolution as numbered steps in the answer.

Respond with JSON only: {{"question": "employee-phrased question", "answer": "numbered steps as plain text"}}"""
    result = await _generate_json(prompt)
    return result["question"], result["answer"]
