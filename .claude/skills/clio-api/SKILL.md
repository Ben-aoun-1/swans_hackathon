---

name: clio-api

description: Clio Manage API v4 reference and integration patterns. Use when building or debugging any Clio API interaction including OAuth, matters, contacts, custom fields, documents, calendar entries, and webhooks.

---



\# Clio Manage API v4 — Integration Reference



\## Authentication



\### OAuth 2.0 Flow

1\. \*\*Authorize:\*\* Redirect user to `https://app.clio.com/oauth/authorize?response\_type=code\&client\_id={CLIENT\_ID}\&redirect\_uri={REDIRECT\_URI}`

2\. \*\*Callback:\*\* Receive `code` at redirect URI

3\. \*\*Token Exchange:\*\* POST to `https://app.clio.com/oauth/token`:

```json

{

&nbsp; "grant\_type": "authorization\_code",

&nbsp; "code": "{AUTH\_CODE}",

&nbsp; "client\_id": "{CLIENT\_ID}",

&nbsp; "client\_secret": "{CLIENT\_SECRET}",

&nbsp; "redirect\_uri": "{REDIRECT\_URI}"

}

```

4\. \*\*Response:\*\* `{ "access\_token": "...", "refresh\_token": "...", "token\_type": "Bearer", "expires\_in": 86400 }`

5\. \*\*Refresh:\*\* POST to same endpoint with `"grant\_type": "refresh\_token"` and the refresh token



\### Headers for All Requests

```

Authorization: Bearer {ACCESS\_TOKEN}

Content-Type: application/json

X-API-VERSION: 4.0.0

```



\## Important: Fields Parameter

Clio returns ONLY `id` and `etag` by default. You MUST request fields explicitly:

```

GET /api/v4/matters/{id}?fields=id,etag,display\_number,description,status,client{id,name,email\_addresses},custom\_field\_values{id,field\_name,value},responsible\_attorney{id,name}

```



\## Key Endpoints



\### Matters

```

GET    /api/v4/matters                    # List matters

GET    /api/v4/matters/{id}               # Get matter details

PATCH  /api/v4/matters/{id}               # Update matter

POST   /api/v4/matters                    # Create matter

```



\*\*Update matter custom fields:\*\*

```json

PATCH /api/v4/matters/{id}

{

&nbsp; "data": {

&nbsp;   "custom\_field\_values": \[

&nbsp;     {

&nbsp;       "custom\_field": { "id": 123456 },

&nbsp;       "value": "2024-03-15"

&nbsp;     },

&nbsp;     {

&nbsp;       "custom\_field": { "id": 123457 },

&nbsp;       "value": "123 Main St, New York, NY"

&nbsp;     }

&nbsp;   ]

&nbsp; }

}

```



\*\*CRITICAL:\*\* You need the custom field's numeric ID, NOT the name. First call GET /api/v4/custom\_fields to get the mapping.



\*\*Update matter stage (for triggering document automation):\*\*

```json

PATCH /api/v4/matters/{id}

{

&nbsp; "data": {

&nbsp;   "status": "open",

&nbsp;   "matter\_stage": { "id": STAGE\_ID }

&nbsp; }

}

```



\### Contacts

```

GET    /api/v4/contacts                   # List contacts

GET    /api/v4/contacts/{id}              # Get contact

PATCH  /api/v4/contacts/{id}              # Update contact

POST   /api/v4/contacts                   # Create contact

```



\*\*Find contact by email:\*\*

```

GET /api/v4/contacts?query=email@example.com\&fields=id,name,email\_addresses{address}

```



\### Custom Fields

```

GET    /api/v4/custom\_fields              # List all custom fields

GET    /api/v4/custom\_fields/{id}         # Get specific field

```



\*\*Getting the field ID mapping (do this once at startup):\*\*

```

GET /api/v4/custom\_fields?fields=id,name,field\_type,parent\_type\&parent\_type=Matter

```

Response contains objects like:

```json

{ "id": 123456, "name": "Accident Date", "field\_type": "date", "parent\_type": "Matter" }

```

Store this mapping: `{ "Accident Date": 123456, "Accident Location": 123457, ... }`



\### Calendar Entries

```

POST   /api/v4/calendar\_entries           # Create entry

GET    /api/v4/calendar\_entries           # List entries

```



\*\*Create statute of limitations entry:\*\*

```json

POST /api/v4/calendar\_entries

{

&nbsp; "data": {

&nbsp;   "summary": "⚠️ Statute of Limitations - \[Client Name] v \[Defendant Name]",

&nbsp;   "description": "Statute of limitations expires for personal injury matter. Accident date: \[date]. Action required before this date.",

&nbsp;   "start\_at": "2032-03-15T09:00:00-05:00",

&nbsp;   "end\_at": "2032-03-15T10:00:00-05:00",

&nbsp;   "all\_day": true,

&nbsp;   "matter": { "id": MATTER\_ID },

&nbsp;   "attendees": \[

&nbsp;     { "id": ATTORNEY\_USER\_ID, "type": "User" }

&nbsp;   ],

&nbsp;   "reminders": \[

&nbsp;     { "minutes": 10080 }

&nbsp;   ]

&nbsp; }

}

```

Note: `start\_at` = accident\_date + 8 years. Include a reminder (10080 min = 7 days before).



\### Documents

```

GET    /api/v4/documents                  # List documents

GET    /api/v4/documents/{id}             # Get document metadata

GET    /api/v4/documents/{id}/download    # Download document content

POST   /api/v4/documents                  # Upload document

```



\*\*List documents for a matter:\*\*

```

GET /api/v4/documents?matter\_id={id}\&fields=id,name,content\_type,created\_at,latest\_document\_version{id}

```



\*\*Download a document:\*\*

```

GET /api/v4/documents/{id}/download

```

Returns the file content with appropriate Content-Type header.



\### Document Templates

```

GET    /api/v4/document\_templates         # List templates

POST   /api/v4/documents                  # Generate from template

```



\*\*Generate document from template (if API supports it):\*\*

```json

POST /api/v4/documents

{

&nbsp; "data": {

&nbsp;   "name": "Retainer Agreement - \[Client Name]",

&nbsp;   "parent": { "id": MATTER\_ID, "type": "Matter" },

&nbsp;   "document\_template": { "id": TEMPLATE\_ID }

&nbsp; }

}

```



\*\*Note:\*\* If this endpoint doesn't work for template generation, use Clio's built-in Automated Workflows feature (matter stage change → generate document). The API-based approach is a fallback.



\### Users (to get attorney ID)

```

GET /api/v4/users/who\_am\_i?fields=id,name,email

```



\### Matter Stages

```

GET /api/v4/matter\_stages?fields=id,name\&practice\_area\_id={PA\_ID}

```



\## Error Handling



| Status | Meaning | Common Cause |

|--------|---------|-------------|

| 400 | Bad Request | Invalid field names in `?fields=` parameter |

| 401 | Unauthorized | Token expired — refresh it |

| 404 | Not Found | Wrong matter/contact ID |

| 422 | Unprocessable | Wrong custom field ID, missing required field, invalid etag |

| 429 | Rate Limited | Too many requests — implement exponential backoff |



\*\*Always include `etag` when doing PATCH operations.\*\* Get the current etag first with a GET request.



\## Rate Limits

\- Rate limited per access token

\- Implement retry with exponential backoff on 429

\- Cache custom field ID mappings — don't re-fetch every request



\## Pagination

\- Default 200 results per page

\- Use `page` parameter or follow `next` link in response headers

