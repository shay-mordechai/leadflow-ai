# Telecom and KYC Workflows

## Workflow Name & ID: WF-21: Admin WABA & Phone Asset Management
* **Code Path:** `(/src/routers/provisioning.py, /src/routers/phones.py)`
* **Description:** Manages WABA and phone asset inspection and configuration tasks via the **Meta Admin Bot** using `META_ADMIN_ACCESS_TOKEN` (with safe fallback to `META_ACCESS_TOKEN`). 
* **Autonomous Purchasing Policy:** There is no autonomous phone number purchasing or automatic addition of new business phone numbers by any bot; all provisioning and WABA asset management require explicit operator/admin action.
* **Trigger:** Administrative HTTP Endpoint / Operator Action
* **Sequence Flow:** Operator Request $\rightarrow$ Admin Token Validation (`META_ADMIN_ACCESS_TOKEN`) $\rightarrow$ Provider LCR / WABA Inspection $\rightarrow$ Explicit Allocation $\rightarrow$ DB State Update

---

## Workflow Name & ID: WF-22: KYC Document S3 Upload
* **Code Path:** `(/src/routers/phones.py, /src/services/storage/s3_service.py)`
* **Trigger:** HTTP Endpoint (PRO User Upload)
* **Sequence Flow:** Multipart File Upload $\rightarrow$ MIME & Type Verification (JPG/PNG/PDF) $\rightarrow$ Secure S3 Key Generation (`kyc/{user.id}/{uuid}.ext`) $\rightarrow$ Encrypted Storage

