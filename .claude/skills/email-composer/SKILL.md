---

name: email-composer

description: Personalized client email composition with retainer PDF attachment and seasonal booking link logic. Use when building, testing, or debugging the email sending service that contacts potential new clients after their data is processed.

---



\# Email Composer Skill



\## Overview

After the retainer agreement is generated and stored in Clio, the system sends a warm, personalized email to the potential new client. The email must reference the specific accident, attach the retainer PDF, and include a booking link that changes based on the season.



\## Email Requirements (from Andrew's brief)

1\. \*\*Warm and personalized tone\*\* — not corporate/generic

2\. \*\*References what happened to them\*\* — the accident date and brief description

3\. \*\*Retainer agreement attached as PDF\*\* — downloaded from Clio after generation

4\. \*\*Booking link that changes by season:\*\*

&nbsp;  - \*\*March (3) through August (8)\*\* → In-office scheduling link

&nbsp;  - \*\*September (9) through February (2)\*\* → Virtual scheduling link



\## Seasonal Booking Link Logic



```python

from datetime import datetime



def get\_booking\_link(

&nbsp;   in\_office\_url: str,

&nbsp;   virtual\_url: str,

&nbsp;   reference\_date: datetime | None = None

) -> tuple\[str, str]:

&nbsp;   """

&nbsp;   Returns (booking\_url, booking\_type) based on the current month.

&nbsp;   

&nbsp;   March-August: in-office

&nbsp;   September-February: virtual

&nbsp;   """

&nbsp;   date = reference\_date or datetime.now()

&nbsp;   month = date.month

&nbsp;   

&nbsp;   if 3 <= month <= 8:

&nbsp;       return in\_office\_url, "in-office"

&nbsp;   else:

&nbsp;       return virtual\_url, "virtual"

```



\## Email Template (Jinja2)



```

templates/client\_email.html

```



```html

<!DOCTYPE html>

<html>

<body style="font-family: Georgia, serif; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

&nbsp; 

&nbsp; <p>Dear {{ client\_first\_name }},</p>



&nbsp; <p>Thank you for reaching out to Richards \& Law. We understand that the 

&nbsp; incident on <strong>{{ accident\_date\_formatted }}</strong> near 

&nbsp; <strong>{{ accident\_location }}</strong> was a difficult experience — 

&nbsp; {{ accident\_description\_brief }}.</p>



&nbsp; <p>We want you to know that our team is ready to support you every step 

&nbsp; of the way.</p>



&nbsp; <p>Attorney Andrew Richards has reviewed the initial details of your case, 

&nbsp; and we've prepared a retainer agreement for your review. Please find it 

&nbsp; attached to this email as a PDF.</p>



&nbsp; <p>When you're ready, we'd love to schedule a 

&nbsp; {% if booking\_type == "in-office" %}visit to our office{% else %}virtual meeting{% endif %} 

&nbsp; to discuss your case in detail:</p>



&nbsp; <p style="text-align: center; margin: 24px 0;">

&nbsp;   <a href="{{ booking\_link }}" 

&nbsp;      style="background-color: #1a365d; color: white; padding: 12px 28px; 

&nbsp;             text-decoration: none; border-radius: 6px; font-size: 16px;">

&nbsp;     Book Your Consultation

&nbsp;   </a>

&nbsp; </p>



&nbsp; <p>If you have any questions in the meantime, don't hesitate to reply to 

&nbsp; this email or call our office.</p>



&nbsp; <p>Warm regards,</p>



&nbsp; <p><strong>The Richards \& Law Team</strong><br>

&nbsp; Richards \& Law<br>

&nbsp; New York, NY</p>



</body>

</html>

```



\## Email Subject Line

```

Richards \& Law — Your Case Review and Next Steps

```



Do NOT include specific accident details in the subject line — keep it professional and generic for privacy.



\## Plain Text Version

Always include a plain text alternative for email clients that don't render HTML:



```

Dear {{ client\_first\_name }},



Thank you for reaching out to Richards \& Law. We understand that the incident on {{ accident\_date\_formatted }} near {{ accident\_location }} was a difficult experience.



Attorney Andrew Richards has reviewed your case and we've prepared a retainer agreement for your review (attached as PDF).



Book your consultation: {{ booking\_link }}



If you have any questions, reply to this email or call our office.



Warm regards,

The Richards \& Law Team

Richards \& Law, New York, NY

```



\## Template Variables



| Variable | Source | Example |

|----------|--------|---------|

| `client\_first\_name` | Clio Contact first name | "Guillermo" |

| `accident\_date\_formatted` | Extracted, formatted nicely | "March 15, 2024" |

| `accident\_location` | Extracted from police report | "intersection of 5th Ave and 42nd St, New York" |

| `accident\_description\_brief` | Extracted, condensed to 1 sentence | "a rear-end collision that resulted in injuries requiring medical attention" |

| `booking\_link` | Seasonal logic | "https://calendly.com/..." |

| `booking\_type` | "in-office" or "virtual" | "in-office" |



\## Sending via SMTP (aiosmtplib)



```python

import aiosmtplib

from email.mime.multipart import MIMEMultipart

from email.mime.text import MIMEText

from email.mime.application import MIMEApplication



async def send\_client\_email(

&nbsp;   to\_email: str,

&nbsp;   subject: str,

&nbsp;   html\_body: str,

&nbsp;   text\_body: str,

&nbsp;   pdf\_attachment: bytes,

&nbsp;   pdf\_filename: str,

&nbsp;   smtp\_config: dict,

):

&nbsp;   msg = MIMEMultipart("mixed")

&nbsp;   msg\["From"] = smtp\_config\["from\_email"]

&nbsp;   msg\["To"] = to\_email

&nbsp;   msg\["Subject"] = subject

&nbsp;   

&nbsp;   # Attach text/html alternative

&nbsp;   alt = MIMEMultipart("alternative")

&nbsp;   alt.attach(MIMEText(text\_body, "plain"))

&nbsp;   alt.attach(MIMEText(html\_body, "html"))

&nbsp;   msg.attach(alt)

&nbsp;   

&nbsp;   # Attach retainer PDF

&nbsp;   pdf\_part = MIMEApplication(pdf\_attachment, \_subtype="pdf")

&nbsp;   pdf\_part.add\_header(

&nbsp;       "Content-Disposition", "attachment",

&nbsp;       filename=pdf\_filename

&nbsp;   )

&nbsp;   msg.attach(pdf\_part)

&nbsp;   

&nbsp;   await aiosmtplib.send(

&nbsp;       msg,

&nbsp;       hostname=smtp\_config\["host"],

&nbsp;       port=smtp\_config\["port"],

&nbsp;       username=smtp\_config\["user"],

&nbsp;       password=smtp\_config\["password"],

&nbsp;       use\_tls=False,

&nbsp;       start\_tls=True,

&nbsp;   )

```



\## Critical Notes



1\. \*\*The automation email for final delivery\*\* MUST be sent to:

&nbsp;  `talent.legal-engineer.hackathon.automation-email@swans.co`

&nbsp;  This is the contact's email in Clio.



2\. \*\*The retainer PDF attachment\*\* must be downloaded from Clio (after document automation generates it), not generated externally.



3\. \*\*Accident description in email should be brief\*\* — one sentence referencing the incident without excessive detail. This is a warm touch, not a legal summary.



4\. \*\*Test the seasonal logic\*\* for all months — especially edge cases at month 2 (Feb → virtual) and month 3 (Mar → in-office).



5\. \*\*Gmail SMTP\*\* requires an App Password (not your regular password). Generate one at https://myaccount.google.com/apppasswords. Or use a service like Resend.

