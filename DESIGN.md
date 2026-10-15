# System Design: The Bookable Payable Architecture

## 1. System Architecture & Component Responsibilities

The document-to-payable pipeline is structured as an end-to-end, multi-stage pipeline designed for high fidelity, structural grounding, and strict adherence to the downstream ERP contract (`erp.py`).

```
                    ┌───────────────────────────┐
                    │       Input PDF           │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ Page Extraction & Hybrid  │
                    │   OCR (PyMuPDF + RapidOCR)│
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │ Document Classifier &     │
                    │ Multi-Invoice Segmentation│
                    └───────┬───────────┬───────┘
          Non-Payable       │           │ Valid Payable Page(s)
       ┌────────────────────┘           ▼
       ▼                        ┌───────────────────────────┐
┌──────────────┐                │ Line & Token Extractor    │
│ Decline      │                │ (Table, Layout, Regex)    │
│ Handler      │                └─────────────┬─────────────┘
└──────┬───────┘                              │
       │                                      ▼
       │                        ┌───────────────────────────┐
       │                        │ Master Data Matcher       │
       │                        │ (Suppliers, Books, Tax,   │
       │                        │  Payment Terms, PO)       │
       │                        └─────────────┬─────────────┘
       │                                      │
       │                                      ▼
       │                        ┌───────────────────────────┐
       │                        │ Canonical Autodraft       │
       │                        │ Builder & Normalizer      │
       │                        └─────────────┬─────────────┘
       │                                      │
       │                                      ▼
       │                        ┌───────────────────────────┐
       │                        │ ERP Oracle Verification   │
       │                        │ (erp.py will_book_gross)  │
       │                        └─────────────┬─────────────┘
       │                                      │
       ▼                                      ▼
┌───────────────────────────────────────────────────────────┐
│              Output JSON (output/<file>.json)             │
│            payables: [...]  |  declined: [...]            │
└───────────────────────────────────────────────────────────┘
```

### Component Breakdown
1. **Document Classifier & Segmenter**:
   - Classifies document type. Detects whether a document is non-payable (`Mahnung` / payment reminder, `Form`, `Estimate` / quotation, or pure shipping notes).
   - Segments multi-page documents: identifies multiple invoices within a single file (e.g., `DU-02` contains 10 separate 2-page invoices; `DU-05s` contains 12 invoices), while filtering out non-payable attached pages (waybills, packing slips, terms of carriage).
2. **Field & Line-Item Extractor**:
   - Extracts header fields: invoice number, invoice date, due date, invoice type (`INVOICE` vs `CREDIT_MEMO`), currency, declared subtotal, total tax, and gross total.
   - Extracts line items: description, item type (`GOODS`, `SERVICE`, `FREIGHT`, `TAX`), UOM, quantity, unit price, line extension total, line discount, and line taxes.
   - Resolves tax placement: places taxes strictly where the document declares them (line-level vs header-level).
3. **Master Data Matcher**:
   - High-precision matching against `master_data/`:
     - `suppliers.json`: VAT ID / PIN normalization, IBAN matching, supplier legal name similarity, and email domain matching.
     - `chart_of_books.json`: Buyer legal entity resolution into `company_code`, `business_unit_code`, and `location_code`.
     - `payment_terms.json`: Alias matching and date delta `(due_date - invoice_date).days`.
     - `tax_master.json`: Country + tax type + rate resolution to `tax_type_code`.
     - `po_master.json`: Exact matching on `po_number`.
   - Leaves codes as honest blanks `""` when no genuine match exists.
4. **Canonical Normalizer & Pricing Engine**:
   - Detects tax-inclusive unit pricing and converts to net unit price: `net_price = gross_price / (1 + rate/100)`.
   - Handles negative withholding taxes (`TH_WHT_003`) and 0% reverse charge / self-assessed taxes.
   - Ensures credit memos use positive magnitudes under `CREDIT_MEMO`.
5. **ERP Validation Harness**:
   - Verifies each candidate payable through `erp.py`'s `erp_book()` to ensure `will_book_gross == gross_total` before emission.

---

## 2. Answers to the Three Core Architectural Questions

### Question 1: What did you eventually understand about these documents that you did not understand on day one?
On day one, the problem appeared to be an OCR and key-value information extraction task: locate labels like "Invoice #", "Total", "Tax", extract table rows, and write JSON.

What became clear through deep analysis is that **AP document processing is an accounting alignment problem, not an extraction problem**. A record that faithfully copies every printed character from the page can be 100% syntactically correct and yet 100% mathematically wrong to an ERP. Specifically:
1. **The Net Price Invariant**: `erp.py` models standard ERP behavior where `unit_price` is strictly net of tax, and tax is computed on top. Many supplier documents (especially retail, B2C, or European trade invoices) display gross prices. Copying the gross price into `unit_price` causes the ERP to apply tax twice. The system must recognize this accounting model and derive net prices.
2. **Structural Placement vs Numerical Balancing**: An ERP's tax ledger distinguishes between line-level taxes (which attach to individual inventory/cost centers) and header-level taxes. Forcing line taxes into a single blended header tax might balance the gross total arithmetically, but it violates accounting integrity and audit trails.
3. **Documents as Bundles and Multi-Payable Units**: A single PDF is not an invoice; it is a communication container. It can contain zero payables (a dunning reminder or tax form), one payable with accompanying shipping documents (bills of lading, customs slips), or ten distinct payables concatenated together.

---

### Question 2: When your system meets a document unlike any it has seen, what does it actually do — and why does that generalise instead of guessing?
When our system encounters an unseen document, it follows a principled, constraint-driven evaluation hierarchy rather than heuristic guessing:

1. **Document Classification Filter**: It checks document typology against formal non-payable indicators (dunning/reminder markers like `Mahnung` or `Reminder`, quotation markers like `Estimate` or `Quote`, and administrative forms). If any non-payable indicator is dominant and no payable obligation is stated, the document is moved to `declined[]` with an explicit reason.
2. **Boundary and Header Anchoring**: It searches for invoice/credit memo anchor tokens (`Invoice`, `Factura`, `Arve`, `Rechnung`, `Credit Note`, `Kreeditarve`) along with dates, identifying the start and span of each payable unit.
3. **Strict Master-Data Gating**: For every master-data code (`supplier_id`, `company_code`, `tax_type_code`, `payment_term_id`, `po_id`), the matcher requires unambiguous evidence (e.g. valid VAT ID regex, high-confidence entity matching, or matching date arithmetic). If a code cannot be proven, the system emits `""`. It never fabricates a code to "fill" the record.
4. **Conservation of Value (No Balancing Numbers)**: The extractor derives components directly from text tokens. If the components do not sum to the declared gross under `erp.py`, the system tests for known systematic accounting conventions (e.g., tax-inclusive unit pricing, header discount base reduction, explicit line taxes) rather than synthesizing arbitrary "adjustment" charges. If the record cannot be reconciled with grounded facts, the discrepancy is surfaced honestly.

This generalises because the underlying rules are based on double-entry accounting fundamentals and tax law, not overfitting to template geometries.

---

### Question 3: Was there a document you concluded could not be solved the way the others were? If so, which, and how did you know?
Yes: **`INV-23.pdf`**, **`DU-08.pdf`**, and **`DU-09.pdf`**.

- **`INV-23.pdf`**: This document looks visually like an invoice with line items, tables, and currency amounts. However, its title is explicitly **`ESTIMATE #EST-259684`**, and the bill-to is marked `CASH CUSTOMER`. An estimate is a pre-sale price quotation, not an invoice or an accounts payable liability. Booking an estimate as a payable would lead to duplicate payments and false liabilities in an ERP.
- **`DU-08.pdf`**: Titled **`Mahnung`** (German for dunning letter / late payment reminder) referencing an existing invoice. A dunning notice reminds the customer to pay an already-issued invoice; booking the Mahnung itself would double-book the expense.
- **`DU-09.pdf`**: A two-page statutory tax disclosure form (**`FORM: Donations and Charitable Contributions`**), completely lacking invoice headers, vendor banking details, or payable line items.

We knew these could not be solved as payables because accounting systems explicitly forbid booking non-payable records. Refusing to force these into `payables[]` and placing them into `declined[]` is the only correct accounting outcome.
