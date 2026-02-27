---

name: retainer-template

description: Retainer agreement template design with Clio Manage merge fields and document automation setup. Use when creating, editing, or debugging the retainer agreement Word template or Clio's document automation workflow.

---



\# Retainer Agreement Template Skill



\## Overview

The retainer agreement MUST be generated using Clio Manage's built-in document automation feature. This means creating a Word (.docx) template with Clio merge field tags, uploading it to Clio as a document template, and triggering generation either via Automated Workflows or API.



\## Clio Merge Field Syntax

In Word documents, merge fields use double angle brackets:

```

<<FieldPath>>

```



\### Standard Merge Fields

| Merge Field | Description |

|-------------|-------------|

| `<<Matter.Client.Name>>` | Client full name |

| `<<Matter.Client.FirstName>>` | Client first name |

| `<<Matter.Client.LastName>>` | Client last name |

| `<<Matter.Client.Address>>` | Client address |

| `<<Matter.Client.Email>>` | Client email |

| `<<Matter.Client.Phone>>` | Client phone |

| `<<Matter.Description>>` | Matter description |

| `<<Matter.DisplayNumber>>` | Matter number |

| `<<Matter.OpenDate>>` | When the matter was opened |

| `<<Matter.ResponsibleAttorney.Name>>` | Responsible attorney name |

| `<<Firm.Name>>` | Firm name |

| `<<Firm.Address>>` | Firm address |

| `<<Firm.Phone>>` | Firm phone |

| `<<Today>>` | Current date |



\### Custom Field Merge Fields

For custom fields created on the matter, the merge field format is:

```

<<Matter.CustomField.FIELD\_NAME>>

```



Where FIELD\_NAME matches EXACTLY what you named the custom field in Clio.



| Merge Field | Maps To |

|-------------|---------|

| `<<Matter.CustomField.Accident Date>>` | Date of the accident |

| `<<Matter.CustomField.Accident Location>>` | Where it happened |

| `<<Matter.CustomField.Accident Description>>` | What happened |

| `<<Matter.CustomField.Police Report Number>>` | Report case number |

| `<<Matter.CustomField.Plaintiff Name>>` | Client's full name from report |

| `<<Matter.CustomField.Plaintiff Address>>` | Client's address |

| `<<Matter.CustomField.Plaintiff DOB>>` | Client's date of birth |

| `<<Matter.CustomField.Plaintiff Phone>>` | Client's phone |

| `<<Matter.CustomField.Defendant Name>>` | At-fault party |

| `<<Matter.CustomField.Defendant Address>>` | Defendant's address |

| `<<Matter.CustomField.Defendant Insurance>>` | Insurance company |

| `<<Matter.CustomField.Defendant Policy Number>>` | Policy number |

| `<<Matter.CustomField.Defendant Vehicle>>` | Year/Make/Model |

| `<<Matter.CustomField.Plaintiff Vehicle>>` | Year/Make/Model |

| `<<Matter.CustomField.Injuries Reported>>` | Injuries from report |

| `<<Matter.CustomField.Statute of Limitations Date>>` | Accident + 8 years |



\## Retainer Agreement Structure



The Word document should follow this structure (adapt from the client's template notes):



```

RETAINER AGREEMENT



This Retainer Agreement ("Agreement") is entered into on <<Today>>

between:



ATTORNEY:

<<Matter.ResponsibleAttorney.Name>>

Richards \& Law

\[Firm Address]

New York, NY



CLIENT:

<<Matter.CustomField.Plaintiff Name>>

<<Matter.CustomField.Plaintiff Address>>

Date of Birth: <<Matter.CustomField.Plaintiff DOB>>

Phone: <<Matter.CustomField.Plaintiff Phone>>

Email: <<Matter.Client.Email>>



1\. SCOPE OF REPRESENTATION



The Client hereby retains the Attorney to represent the Client in

connection with a personal injury claim arising from a motor vehicle

accident that occurred on <<Matter.CustomField.Accident Date>> at

<<Matter.CustomField.Accident Location>>.



Accident Description:

<<Matter.CustomField.Accident Description>>



Police Report Number: <<Matter.CustomField.Police Report Number>>



2\. PARTIES INVOLVED



Adverse Party: <<Matter.CustomField.Defendant Name>>

Address: <<Matter.CustomField.Defendant Address>>

Insurance: <<Matter.CustomField.Defendant Insurance>>

Policy Number: <<Matter.CustomField.Defendant Policy Number>>

Vehicle: <<Matter.CustomField.Defendant Vehicle>>



Client Vehicle: <<Matter.CustomField.Plaintiff Vehicle>>

Injuries Reported: <<Matter.CustomField.Injuries Reported>>



3\. ATTORNEY'S FEES



The Attorney's fee shall be 33⅓% (one-third) of the gross recovery

obtained on behalf of the Client, whether by settlement, judgment,

or otherwise.



4\. STATUTE OF LIMITATIONS



The applicable statute of limitations for this claim expires on

<<Matter.CustomField.Statute of Limitations Date>>. The Attorney

shall take all necessary actions to preserve the Client's claims

within this period.



\[... additional standard legal clauses ...]



SIGNATURES:



\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_     Date: \_\_\_\_\_\_\_\_\_\_\_

<<Matter.CustomField.Plaintiff Name>> (Client)



\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_     Date: \_\_\_\_\_\_\_\_\_\_\_

<<Matter.ResponsibleAttorney.Name>> (Attorney)

Richards \& Law

```



\## Creating the Template in Clio



\### Step 1: Create the Word Document

1\. Create a .docx file in Word with the retainer text above

2\. Replace all client/case-specific text with the appropriate merge field tags

3\. Keep formatting professional — use consistent fonts, spacing, headers

4\. Save as `Retainer\_Agreement\_Template.docx`



\### Step 2: Upload to Clio

1\. Go to Clio Manage → Documents → Categories and Templates → Templates

2\. Click "Add Template"

3\. Upload the .docx file

4\. Name it "Personal Injury Retainer Agreement"

5\. Save



\### Step 3: Test Manually First

1\. Go to a matter with custom fields filled in

2\. Documents tab → New → Create from template

3\. Select the retainer template

4\. Choose to generate as PDF

5\. Verify all merge fields populated correctly



\## Triggering Document Generation Automatically



\### Option A: Clio Automated Workflows (Preferred)

1\. Go to Settings → Automated Workflows

2\. Create new: "When matter stage changes to Data Verified → Generate document from Retainer Agreement template"

3\. This fires automatically when the backend changes the matter stage



\### Option B: Via API (Fallback)

```json

POST /api/v4/documents

{

&nbsp; "data": {

&nbsp;   "name": "Retainer Agreement - \[Client Name].pdf",

&nbsp;   "parent": { "id": MATTER\_ID, "type": "Matter" },

&nbsp;   "document\_template": { "id": TEMPLATE\_ID }

&nbsp; }

}

```



\### Option C: Generate Externally (Last Resort)

If Clio's template system doesn't work on the free plan:

1\. Use `python-docx` to open the template and replace merge field placeholders

2\. Convert to PDF using `docx2pdf` or LibreOffice CLI

3\. Upload the generated PDF to the matter's documents via Clio API



\*\*Note:\*\* The hackathon brief explicitly requires Clio's document automation, so exhaust Options A and B first.



\## Generating the Template Programmatically



If you need to create the .docx template via code (for reproducibility):



```python

from docx import Document

from docx.shared import Pt, Inches

from docx.enum.text import WD\_ALIGN\_PARAGRAPH



def create\_retainer\_template():

&nbsp;   doc = Document()

&nbsp;   

&nbsp;   # Title

&nbsp;   title = doc.add\_heading("RETAINER AGREEMENT", level=1)

&nbsp;   title.alignment = WD\_ALIGN\_PARAGRAPH.CENTER

&nbsp;   

&nbsp;   # Opening paragraph with merge fields

&nbsp;   doc.add\_paragraph(

&nbsp;       'This Retainer Agreement ("Agreement") is entered into on '

&nbsp;       '<<Today>> between:'

&nbsp;   )

&nbsp;   

&nbsp;   # ... build out the full document with merge fields ...

&nbsp;   

&nbsp;   doc.save("templates/retainer\_agreement.docx")

```



This approach lets Claude Code generate the template automatically, ensuring all merge fields are correct.

