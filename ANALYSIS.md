# Assignment Analysis & Inventory

## 1. Package Inspection and Extraction

### Package Identification
- **Original Source**: The assignment materials were delivered as `candidate_kit-2` (uncompressed directory from `candidate_kit.2` / `candidate_kit (2).zip` created on macOS, containing `__MACOSX` resource forks and standard POSIX permissions).
- **Integrity**: All files were verified intact. The package was duplicated into `assignment_workspace/` for clean development, leaving the original source directory completely unmodified.

### Inventory of Materials
The package contains 49 core files structured as follows:
- **Root Specification and Utilities**:
  - `README.md` (10,896 bytes): Complete problem brief, architectural constraints, grading methodology, output specification, and guiding principles.
  - `AUTODRAFT_SCHEMA.md` (5,667 bytes): Definitive JSON schema contract for payable autodrafts.
  - `erp.py` (5,141 bytes): The fixed reference oracle implementation modeling the downstream ERP booking logic. Standard library only (Python 3.10+).
  - `example_check.py` (987 bytes): Usage harness demonstrating the single required callable: `erp_book(payable: dict) -> {"will_book_gross": float, "currency": str}`.
  - `sample_autodraft.json` (1,578 bytes): Canonical ground-truth worked example (Invoice 265345 from Phocus Direct Communication GmbH).
- **Master Data Files** (`master_data/`):
  - `suppliers.json` (3,880 bytes, 14 entries): Supplier master records containing `supplier_id`, `name`, `vat_id`, `country`, `email`, `address`, `bank_iban`.
  - `chart_of_books.json` (2,452 bytes): Organizational tenant chart for `BOLTGROUP` defining business units (`EE001`, `EE004`, `GH001`, `MY001`, `ZA001`, `GB001`) and locations (`LOC_EE_001`, `LOC_GH_001`, etc.).
  - `payment_terms.json` (1,698 bytes, 10 entries): Standard payment terms (`Immediate`, `Net_7`, `Net_10`, `Net_14`, `Net_21`, `Net_25`, `Net_30`, `Net_60`, `Net_90`, `Monthly_in_advance`) with days and text aliases.
  - `tax_master.json` (5,001 bytes, 33 entries): Tax codes mapped by country, rate, type (`VAT`, `IVA`, `SST`, `NHIL`, `GETFL`, `COVID`, `CST`, `WHT`, `USE`), and formal descriptions across 15+ jurisdictions.
  - `po_master.json` (907 bytes, 2 entries): Purchase order master mapping `po_id`, `supplier_id`, `currency`, and line items for ERP-backed POs (`PO-EE-2026-0044`, `PO-GH-2026-0177`).
  - `README.md` (1,224 bytes): Guidance on scale, exact matching semantics, and refusal to guess.
- **Documents Directory** (`documents/`):
  - 42 PDF files spanning multiple languages (English, German, Estonian, Portuguese, Thai), jurisdictions, and document archetypes.

---

## 2. Document Archetype Analysis

A detailed inspection of all 42 PDF documents revealed the following distinct categories:

| Category | File Identifiers | Characteristics & Handling |
|---|---|---|
| **Standard Single/Multi-page Invoices** | `INV-01` to `INV-07`, `INV-09` to `INV-11`, `INV-13` to `INV-16`, `INV-19` to `INV-21`, `INV-25` to `INV-28`, `INV-31` to `INV-37`, `HLD-01`, `HLD-03`, `HLD-05`, `HLD-08`, `HLD-10`, `DU-05`, `DU-06` | Produce exactly 1 bookable payable per invoice. Resolve supplier, buyer, payment terms, taxes, and line items. |
| **Multi-Invoice Bundles** | `DU-02` (20 pages), `DU-05s` (15 pages) | Bundles containing multiple distinct invoices (e.g. `DU-02` contains 10 separate 2-page invoices, interleaved with packing slips). System must detect document boundaries and emit `payables: [<p1>, <p2>, ...]`. |
| **Invoices with Attached Non-Payable Artifacts** | `DU-03` (12 pages: 2p invoice + Maersk advice, continuation sheets, air waybills, order confirmations) | Extract payable strictly from invoice pages (pages 0–1); do not treat waybills or advice notes as payables. |
| **Credit Memos** | `DU-10` ("CreditNoteNo."), `DU-11` ("Kreeditarve") | Produce payable with `invoice_type: "CREDIT_MEMO"`. All amounts, prices, and quantities are positive magnitudes per `AUTODRAFT_SCHEMA.md`. |
| **Non-Payables (To Decline)** | `DU-08` ("Mahnung" / Dunning Reminder), `DU-09` ("Form: Donations and Charitable Contributions"), `INV-23` ("ESTIMATE #EST-259684") | Must NOT produce payables. Must populate `declined: [{"doc_type": "...", "reason": "..."}]` and set `payables: []`. |

---

## 3. The Core Challenge & The "Shift" in Perspective

As highlighted in the project brief:
> *"A record can mirror the page faithfully and still fail to book. Many of these documents are exactly that record. Understanding how a faithful copy can be a wrong answer is the first door you have to walk through..."*

The fundamental challenge in automated AP/autodrafting is the impedance mismatch between **printed document representations** and **ERP mathematical mechanics**:

1. **Tax-Inclusive Pricing**:
   - In B2C, retail, or certain European/Asian invoices, line items are printed with gross (tax-inclusive) unit prices.
   - `erp.py` explicitly computes: `net_base = qty * unit_price`, and then **adds taxes on top**: `gross = net_base + line_taxes + header_taxes`.
   - If an invoice states gross unit prices, extracting that number literally causes double taxation in ERP recomputation. The system must recognize when unit prices are inclusive and derive the net unit price: `unit_price = gross_price / (1 + rate/100)`.
2. **Tax Placement Fidelity**:
   - Placement is graded independently of gross balance. A tax stated at the line belongs on `line_items[].taxes[]` (or `tax_rate`); a tax stated once over the document belongs in header `taxes[]`. Collapsing line taxes into header tax or vice versa fails the architectural contract.
3. **Withholding Taxes**:
   - In jurisdictions like Thailand (`TH_WHT_003` 3%), withholding tax is deducted from the vendor payable. In `erp.py`, withholding taxes must be submitted with a **negative `tax_amount`** so that `header_tax` or `line_tax` reduces the gross payable.
4. **Self-Assessed / Reverse Charge Taxes**:
   - In EU reverse charge (e.g., German Reverse Charge `DE_000_RC` 0%) or US Use Tax (`US_U1_USE`), tax is accounted for by the buyer directly with the tax authority, not paid to the vendor. The rate or amount in the payable must be 0% so it does not inflate `will_book_gross`.
5. **Compound Levies**:
   - In jurisdictions like Ghana, multiple levies (NHIL 2.5%, GETFund 2.5%, COVID 1%) apply before or alongside VAT 15%. Because `erp.py` applies header rates strictly to `net_base` (`item_discounted_total - header_discount`), compound tax amounts that do not equal `net_base * rate / 100` must provide explicit `tax_amount` strings.
6. **Calendar System Discrepancies**:
   - Thai invoices (`HLD-01`) use the Buddhist Era (BE) calendar (e.g., year 2569 corresponds to Gregorian 2026: `2569 - 543 = 2026`).

---

## 4. Master Data Resolution Strategy

Every autodraft field mapped to master data follows a strict matching policy:
- **`supplier.supplier_id`** (`master_data/suppliers.json`):
  1. Exact VAT ID / Tax PIN normalization and match (e.g., `DE209177122`, `EE101234567`, `MY202001012345`, `ZA4123456789`).
  2. IBAN normalization and exact match.
  3. Normalized name matching and token similarity above 0.85 threshold.
  4. Email address and domain match.
  5. Unmatched -> honest empty string `""`.
- **`buyer.company_code`, `business_unit_code`, `location_code`** (`master_data/chart_of_books.json`):
  - Company is always `BOLTGROUP`.
  - Matched by buyer legal entity name, country code, or address keywords (e.g., `Bolt Technology OU` -> `EE001`, `Bolt Operations UK` -> `GB001`, `Bolt Ghana` -> `GH001`, `Bolt Malaysia` -> `MY001`, `Bolt South Africa` -> `ZA001`).
- **`payment_term_id`** (`master_data/payment_terms.json`):
  1. Direct text alias match (e.g., "net 14", "14 days", "due on receipt").
  2. Date delta calculation: `(due_date - invoice_date).days` mapped to `days` column.
- **`taxes[].tax_type_code`** (`master_data/tax_master.json`):
  - Matched by jurisdiction (`country`), tax type (`tax_type`), and tax rate (`rate`).
- **`po_id`** (`master_data/po_master.json`):
  - Matched against `po_number` in `po_master.json`. If document has a PO not in `po_master.json`, `po_number` keeps the raw string, while `po_id` is set to `""`.

---

## 5. System Execution Contract

- **Input**: `assignment_workspace/documents/` containing arbitrary PDF files.
- **Output**: `output/` directory containing one JSON file per input PDF (`output/X.json`).
- **Orchestration**: Single documented command:
  ```bash
  python run.py
  ```
- **Validation**: Zero modification to `erp.py`. Every payable passed through `erp_book()` and validated against declared document gross.
