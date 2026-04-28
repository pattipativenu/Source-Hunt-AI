---
name: whatsapp-formatter
description: Use this skill when building WhatsApp message formatters — including 4096-character splitting, citation alignment in plain text, reply button generation, markdown conversion, multi-part message handling, and Meta Cloud API delivery. Also trigger for: WhatsApp Business API, interactive message buttons, typing indicators, message deduplication, delivery receipts. Applies to any WhatsApp-delivered application.
---

# WhatsApp Formatter — Delivering Complex Content in 4,096 Characters

WhatsApp is a text-first, mobile-first, attention-scarce channel. Every formatting decision must serve a doctor reading between patients on a 6-inch screen.

---

## The 4,096-Character Law

WhatsApp truncates messages silently at 4,096 characters. You don't get an error. The doctor just gets an incomplete answer. Split before you send.

```python
MAX_CHARS = 4096
SAFE_LIMIT = 3800  # Buffer for formatting overhead
```

---

## WhatsApp Markdown Cheat Sheet

```
*bold text*          → **bold**
_italic text_        → _italic_
~strikethrough~      → ~~strikethrough~~
```monospace```     → code block
> blockquote         → quote

NOT SUPPORTED:
# Headers           (renders as plain text)
- Bullet points     (renders as plain dash)
[link text](url)    (renders raw URL instead)
```

**Key implication:** Citations must be numbered inline `[1]`, not hyperlinked. DOIs must be plain URLs.

---

## Message Templates

### Standard Evidence Response

```python
def format_evidence_response(
    query_topic: str,
    answer: str,
    references: list[dict],
    evidence_quality: str,
    clinical_bottom_line: str,
) -> str:
    """
    Format a complete evidence response for WhatsApp delivery.
    """
    quality_emoji = {"high": "🟢", "moderate": "🟡", "low": "🟠", "insufficient": "🔴"}.get(
        evidence_quality, "⚪"
    )
    
    parts = []
    
    # Header
    parts.append(f"*{query_topic.upper()}*")
    parts.append("")  # Blank line
    
    # Answer body (already contains inline [N] citations)
    parts.append(answer)
    parts.append("")
    
    # Clinical Bottom Line
    parts.append(f"*Clinical Bottom Line*")
    parts.append(clinical_bottom_line)
    parts.append("")
    
    # Evidence quality
    parts.append(f"{quality_emoji} Evidence Quality: *{evidence_quality.capitalize()}*")
    parts.append("")
    
    # References
    parts.append("*References*")
    for ref in references:
        authors = ref.get("authors", "Unknown")
        title = ref.get("title", "")[:60] + "..." if len(ref.get("title", "")) > 60 else ref.get("title", "")
        journal = ref.get("journal", "")
        year = ref.get("year", "")
        doi = ref.get("doi", "")
        
        ref_line = f"[{ref['id']}] {authors}. _{title}._ {journal} {year}."
        if doi:
            ref_line += f"\nhttps://doi.org/{doi}"
        parts.append(ref_line)
    
    # Footer
    parts.append("")
    parts.append("_⚠️ For clinical guidance only. Verify with current guidelines._")
    
    return "\n".join(parts)
```

### Emergency Response (Always First)

```python
EMERGENCY_TEMPLATE = """⚠️ *MEDICAL EMERGENCY DETECTED*

*Call 108 immediately* (or 102 for ambulance).

{evidence_section}

_Evidence provided for reference while awaiting emergency services._"""

def format_emergency_response(evidence_text: str) -> str:
    return EMERGENCY_TEMPLATE.format(evidence_section=evidence_text)
```

---

## Message Splitting

```python
from dataclasses import dataclass

@dataclass
class MessagePart:
    text: str
    is_final: bool
    part_number: int
    total_parts: int

def split_for_whatsapp(
    full_message: str,
    max_chars: int = SAFE_LIMIT,
) -> list[MessagePart]:
    """
    Split a long response into WhatsApp-safe chunks.
    
    Rules:
    - Never split mid-word or mid-sentence
    - References always go in the FINAL part
    - Each part except the last gets a "continued" marker
    """
    if len(full_message) <= max_chars:
        return [MessagePart(
            text=full_message,
            is_final=True,
            part_number=1,
            total_parts=1,
        )]
    
    # Separate references from main body
    ref_marker = "\n*References*\n"
    if ref_marker in full_message:
        body, references = full_message.split(ref_marker, 1)
        references = ref_marker + references
    else:
        body = full_message
        references = ""
    
    parts = []
    remaining = body
    
    while remaining:
        if len(remaining) + len(references if not parts else "") <= max_chars:
            # Last part — add references
            chunk = remaining + (references if not references.strip() == ref_marker.strip() else references)
            parts.append(chunk)
            break
        
        # Find split point at paragraph boundary
        split_at = remaining.rfind("\n\n", 0, max_chars)
        if split_at == -1:
            # No paragraph boundary — split at sentence
            split_at = remaining.rfind(". ", 0, max_chars)
        if split_at == -1:
            # No sentence boundary — split at word
            split_at = remaining.rfind(" ", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        
        chunk = remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()
        parts.append(chunk)
    
    total = len(parts)
    return [
        MessagePart(
            text=f"_{part_number}/{total}_\n\n{text}" if total > 1 else text,
            is_final=(i == total - 1),
            part_number=i + 1,
            total_parts=total,
        )
        for i, text in enumerate(parts)
    ]
```

---

## Interactive Reply Buttons

```python
def build_quick_reply_buttons(query_type: str) -> list[dict]:
    """
    Build WhatsApp interactive reply buttons.
    Maximum 3 buttons. Button text max 20 characters.
    """
    base_buttons = [
        {"type": "reply", "reply": {"id": "full_evidence", "title": "📋 Full Evidence"}},
        {"type": "reply", "reply": {"id": "related", "title": "🔄 Related Topics"}},
    ]
    
    if query_type == "drug_lookup":
        base_buttons.append(
            {"type": "reply", "reply": {"id": "drug_info", "title": "💊 Drug Details"}}
        )
    elif query_type == "guideline":
        base_buttons.append(
            {"type": "reply", "reply": {"id": "india_context", "title": "🇮🇳 India Context"}}
        )
    
    return base_buttons[:3]  # WhatsApp max 3 buttons


def build_interactive_message(
    body_text: str,
    buttons: list[dict],
    phone_number: str,
) -> dict:
    """Build WhatsApp interactive message payload for Meta Cloud API."""
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text[:1024]},  # Body max 1024 chars for interactive
            "action": {"buttons": buttons},
        },
    }
```

---

## Delivery via Meta Cloud API

```python
import httpx
import os

WHATSAPP_API_URL = "https://graph.facebook.com/v21.0/{phone_number_id}/messages"

async def send_whatsapp_message(
    to: str,
    text: str,
    buttons: list[dict] | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Send a WhatsApp message via Meta Cloud API.
    
    Uses interactive message if buttons provided, text message otherwise.
    """
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    token = os.environ["WHATSAPP_ACCESS_TOKEN"]
    
    url = WHATSAPP_API_URL.format(phone_number_id=phone_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    if buttons:
        payload = build_interactive_message(text, buttons, to)
    else:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": False},
        }
    
    if client is None:
        async with httpx.AsyncClient() as c:
            response = await c.post(url, json=payload, headers=headers, timeout=10.0)
    else:
        response = await client.post(url, json=payload, headers=headers, timeout=10.0)
    
    response.raise_for_status()
    return response.json()


async def send_multi_part_response(
    to: str,
    full_message: str,
    buttons: list[dict] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[dict]:
    """
    Send a full response, splitting across multiple messages if needed.
    Buttons only appear on the FINAL message.
    """
    parts = split_for_whatsapp(full_message)
    results = []
    
    for part in parts:
        part_buttons = buttons if (part.is_final and buttons) else None
        result = await send_whatsapp_message(
            to=to,
            text=part.text,
            buttons=part_buttons,
            client=client,
        )
        results.append(result)
        
        if not part.is_final:
            await asyncio.sleep(0.5)  # Small delay between parts to preserve order
    
    return results
```

---

## Sending Typing Indicators

```python
async def send_typing_indicator(
    to: str,
    client: httpx.AsyncClient,
    duration_seconds: float = 2.0,
) -> None:
    """Send typing indicator while RAG pipeline runs."""
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "...",  # Mark last message as read
    }
    # Note: WhatsApp doesn't have a native "typing..." API
    # Instead: send read receipt immediately, then send actual message
    # The gap between read receipt and response looks like "typing"
```

---

## Common Mistakes

```python
# ❌ Not counting characters before sending — 4096 is silently truncated
message = "\n".join(long_parts)  # Could be 6,000 chars
await send(message)  # Truncated, doctor gets incomplete answer

# ❌ Using HTML formatting — WhatsApp doesn't render it
text = "<b>Treatment</b>: fidaxomicin"  # Sends as literal "<b>Treatment</b>"

# ❌ Putting references in Part 1 when there will be multiple parts
# Doctor reads Part 1, references aren't there, can't verify

# ❌ Buttons on non-final parts
# Clicking a button on Part 1 triggers before they've read Part 2

# ❌ Sending all parts simultaneously — WhatsApp may reorder them
# Always await each send before sending the next
```
