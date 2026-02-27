---

name: police-report-extraction

description: Police report PDF extraction using Claude Sonnet 4.6 vision. Use when building, testing, or debugging the AI extraction service that converts police report PDFs into structured JSON data for Clio Manage.

---



\# Police Report Extraction Skill



\## Overview

Extract structured data from scanned police/accident report PDFs using Claude Sonnet 4.6's vision capabilities. Reports are often messy scans with handwritten fields, checkboxes, stamps, and poor OCR quality.



\## PDF → Images Pipeline



\### Step 1: Convert PDF pages to images

```python

import fitz  # PyMuPDF



def pdf\_to\_images(pdf\_bytes: bytes) -> list\[tuple\[bytes, str]]:

&nbsp;   """Convert PDF to list of (image\_bytes, media\_type) tuples."""

&nbsp;   doc = fitz.open(stream=pdf\_bytes, filetype="pdf")

&nbsp;   images = \[]

&nbsp;   for page in doc:

&nbsp;       # Render at 2x resolution for better OCR

&nbsp;       mat = fitz.Matrix(2.0, 2.0)

&nbsp;       pix = page.get\_pixmap(matrix=mat)

&nbsp;       img\_bytes = pix.tobytes("png")

&nbsp;       images.append((img\_bytes, "image/png"))

&nbsp;   doc.close()

&nbsp;   return images

```



\### Step 2: Send to Claude Sonnet 4.6

```python

import anthropic

import base64



async def extract\_from\_pdf(pdf\_bytes: bytes) -> dict:

&nbsp;   client = anthropic.AsyncAnthropic()

&nbsp;   images = pdf\_to\_images(pdf\_bytes)

&nbsp;   

&nbsp;   # Build content blocks: all page images + extraction prompt

&nbsp;   content = \[]

&nbsp;   for img\_bytes, media\_type in images:

&nbsp;       content.append({

&nbsp;           "type": "image",

&nbsp;           "source": {

&nbsp;               "type": "base64",

&nbsp;               "media\_type": media\_type,

&nbsp;               "data": base64.b64encode(img\_bytes).decode(),

&nbsp;           },

&nbsp;       })

&nbsp;   content.append({

&nbsp;       "type": "text",

&nbsp;       "text": EXTRACTION\_PROMPT,

&nbsp;   })

&nbsp;   

&nbsp;   response = await client.messages.create(

&nbsp;       model="claude-sonnet-4-6-20260217",

&nbsp;       max\_tokens=4096,

&nbsp;       messages=\[{"role": "user", "content": content}],

&nbsp;   )

&nbsp;   

&nbsp;   # Parse JSON from response

&nbsp;   raw\_text = response.content\[0].text

&nbsp;   # Handle potential markdown code fences

&nbsp;   if "```json" in raw\_text:

&nbsp;       raw\_text = raw\_text.split("```json")\[1].split("```")\[0]

&nbsp;   elif "```" in raw\_text:

&nbsp;       raw\_text = raw\_text.split("```")\[1].split("```")\[0]

&nbsp;   

&nbsp;   return json.loads(raw\_text.strip())

```



\## The Extraction Prompt



```python

EXTRACTION\_PROMPT = """You are a legal data extraction specialist working for a personal injury law firm. Analyze this police/accident report and extract all relevant information into structured JSON.



IMPORTANT RULES:

\- Return ONLY valid JSON — no explanations, no markdown fences, no preamble

\- If a field cannot be found or is illegible, use null

\- For dates, use ISO format: YYYY-MM-DD

\- For times, use 24h format: HH:MM

\- Handle OCR artifacts gracefully (e.g., "l" vs "1", "O" vs "0")

\- The "plaintiff" is the injured party / our potential client

\- The "defendant" is the at-fault party

\- If fault isn't clear from the report, use context clues (who was cited, who was injured more severely)



Extract this JSON structure:



{

&nbsp; "report\_number": "string or null — the police report / case number",

&nbsp; "accident\_date": "YYYY-MM-DD or null",

&nbsp; "accident\_time": "HH:MM or null",

&nbsp; "accident\_location": "full address or intersection description",

&nbsp; "accident\_description": "2-3 sentence narrative of what happened, written clearly for a legal context",

&nbsp; "weather\_conditions": "string or null",

&nbsp; "road\_conditions": "string or null",

&nbsp; "number\_of\_vehicles": "integer or null",

&nbsp; "reporting\_officer\_name": "string or null",

&nbsp; "reporting\_officer\_badge": "string or null",

&nbsp; "parties": \[

&nbsp;   {

&nbsp;     "role": "plaintiff | defendant | witness | other",

&nbsp;     "full\_name": "string or null",

&nbsp;     "address": "full address string or null",

&nbsp;     "date\_of\_birth": "YYYY-MM-DD or null",

&nbsp;     "phone": "string or null",

&nbsp;     "driver\_license": "string or null",

&nbsp;     "vehicle\_year": "string or null",

&nbsp;     "vehicle\_make": "string or null",

&nbsp;     "vehicle\_model": "string or null",

&nbsp;     "vehicle\_color": "string or null",

&nbsp;     "insurance\_company": "string or null",

&nbsp;     "insurance\_policy\_number": "string or null",

&nbsp;     "injuries": "description of injuries or null",

&nbsp;     "citation\_issued": "string description of any traffic citation or null"

&nbsp;   }

&nbsp; ],

&nbsp; "confidence\_notes": "Brief note about any fields you were uncertain about or had difficulty reading"

}



Analyze every page of the police report carefully. Pay special attention to:

\- The accident narrative/description section

\- Driver information sections (usually one per involved party)

\- Vehicle information sections

\- Insurance information

\- Any injury descriptions or EMS notes

\- Citations or violations noted

\- Weather/road condition checkboxes or fields"""

```



\## Output Pydantic Schema



```python

from pydantic import BaseModel

from typing import Literal



class PartyInfo(BaseModel):

&nbsp;   role: Literal\["plaintiff", "defendant", "witness", "other"]

&nbsp;   full\_name: str | None = None

&nbsp;   address: str | None = None

&nbsp;   date\_of\_birth: str | None = None

&nbsp;   phone: str | None = None

&nbsp;   driver\_license: str | None = None

&nbsp;   vehicle\_year: str | None = None

&nbsp;   vehicle\_make: str | None = None

&nbsp;   vehicle\_model: str | None = None

&nbsp;   vehicle\_color: str | None = None

&nbsp;   insurance\_company: str | None = None

&nbsp;   insurance\_policy\_number: str | None = None

&nbsp;   injuries: str | None = None

&nbsp;   citation\_issued: str | None = None



class ExtractionResult(BaseModel):

&nbsp;   report\_number: str | None = None

&nbsp;   accident\_date: str | None = None

&nbsp;   accident\_time: str | None = None

&nbsp;   accident\_location: str | None = None

&nbsp;   accident\_description: str | None = None

&nbsp;   weather\_conditions: str | None = None

&nbsp;   road\_conditions: str | None = None

&nbsp;   number\_of\_vehicles: int | None = None

&nbsp;   reporting\_officer\_name: str | None = None

&nbsp;   reporting\_officer\_badge: str | None = None

&nbsp;   parties: list\[PartyInfo] = \[]

&nbsp;   confidence\_notes: str | None = None

```



\## Common Extraction Issues



| Issue | Solution |

|-------|---------|

| Handwritten text misread | Claude vision handles this well — 2x resolution helps |

| Checkboxes not detected | Mention "checkboxes" explicitly in prompt |

| Multi-page reports | Send ALL pages as images in one request |

| Plaintiff/defendant confusion | Use context: who was injured? who was cited? |

| Missing insurance info | Some reports have it on a separate page — check all pages |

| Date format varies | Prompt asks for ISO format — Claude normalizes |

| Report number in odd location | Often in header, footer, or watermark |



\## Testing

Test extraction with ALL provided sample police reports. The output for each must:

1\. Parse successfully as `ExtractionResult`

2\. Have non-null `accident\_date`, `accident\_location`, `accident\_description`

3\. Have at least 2 parties (plaintiff + defendant)

4\. Have reasonable `confidence\_notes` flagging any uncertain fields

