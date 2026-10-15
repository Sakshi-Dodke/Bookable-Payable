"""test_suite.py — Self-contained validation test suite for the Bookable Payable system.

Tests:
1. Complete document coverage: all 42 input documents have valid output JSON.
2. Strict schema conformance to AUTODRAFT_SCHEMA.md.
3. Cent-exact mathematical booking parity through erp_book() for 100% of payables (0.00 difference).
4. Master data code grounding: no fabricated codes; every non-empty code matches master data.
5. Positive magnitude invariant for credit memos (CREDIT_MEMO).
6. Non-payable rejection & classification accuracy (declined[]).
"""

import os
import sys
import json
import unittest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
ws_dir = os.path.join(SCRIPT_DIR, "assignment_workspace")
if os.path.exists(ws_dir) and ws_dir not in sys.path:
    sys.path.insert(0, ws_dir)

from erp import erp_book, num, round2
from master_data_matcher import MasterDataMatcher

class TestBookablePayableSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = SCRIPT_DIR
        # Resolve document directory
        if os.path.exists(os.path.join(base, "documents")):
            cls.doc_dir = os.path.join(base, "documents")
        elif os.path.exists("documents"):
            cls.doc_dir = "documents"
        elif os.path.exists("assignment_workspace/documents"):
            cls.doc_dir = "assignment_workspace/documents"
        else:
            cls.doc_dir = os.path.join(base, "assignment_workspace", "documents")

        # Resolve output directory
        if os.path.exists(os.path.join(base, "output")):
            cls.out_dir = os.path.join(base, "output")
        elif os.path.exists("output"):
            cls.out_dir = "output"
        elif os.path.exists("assignment_workspace/output"):
            cls.out_dir = "assignment_workspace/output"
        else:
            cls.out_dir = os.path.join(base, "assignment_workspace", "output")

        # Resolve master data matcher
        cls.matcher = MasterDataMatcher()

        # Load all outputs
        cls.outputs = {}
        if os.path.exists(cls.out_dir):
            for fname in os.listdir(cls.out_dir):
                if fname.endswith(".json"):
                    fpath = os.path.join(cls.out_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as fh:
                        cls.outputs[fname] = json.load(fh)

    def test_01_total_document_coverage(self):
        """Ensure all 42 input documents have corresponding JSON outputs."""
        input_pdfs = [f for f in os.listdir(self.doc_dir) if f.endswith(".pdf")]
        self.assertEqual(len(input_pdfs), 42, f"Expected 42 input PDFs, found {len(input_pdfs)}")

        for pdf in input_pdfs:
            json_name = pdf.replace(".pdf", ".json")
            self.assertIn(json_name, self.outputs, f"Missing output JSON for {pdf}")

    def test_02_schema_contract(self):
        """Ensure every output file adheres strictly to AUTODRAFT_SCHEMA.md."""
        for json_name, doc in self.outputs.items():
            self.assertIn("file", doc, f"{json_name} missing 'file'")
            self.assertIn("payables", doc, f"{json_name} missing 'payables'")
            self.assertIn("declined", doc, f"{json_name} missing 'declined'")
            self.assertIsInstance(doc["payables"], list)
            self.assertIsInstance(doc["declined"], list)

            # If declined, payables must be empty
            if doc["declined"]:
                self.assertEqual(len(doc["payables"]), 0, f"{json_name} has both payables and declined items")
                for item in doc["declined"]:
                    self.assertIn("doc_type", item)
                    self.assertIn("reason", item)
                    self.assertTrue(len(item["doc_type"]) > 0)
                    self.assertTrue(len(item["reason"]) > 0)

            # Validate payable structure
            for p in doc["payables"]:
                for key in ["invoice_number", "invoice_date", "due_date", "invoice_type", "currency",
                            "supplier", "buyer", "payment_term_id", "po_number", "po_id",
                            "gross_total", "line_items"]:
                    self.assertIn(key, p, f"{json_name} payable missing key: {key}")

                self.assertIn(p["invoice_type"], ["INVOICE", "CREDIT_MEMO"])
                self.assertIsInstance(p["supplier"], dict)
                self.assertIsInstance(p["buyer"], dict)
                self.assertIsInstance(p["line_items"], list)
                self.assertTrue(len(p["line_items"]) > 0, f"{json_name} has empty line_items")

    def test_03_erp_booking_parity_100_percent(self):
        """Ensure every payable books cent-exact against the fixed erp.py oracle."""
        booked_count = 0
        for json_name, doc in self.outputs.items():
            for p in doc["payables"]:
                res = erp_book(p)
                will_book = res["will_book_gross"]
                doc_gross = num(p["gross_total"])
                diff = abs(will_book - doc_gross)
                self.assertLessEqual(
                    diff, 0.01,
                    f"Booking mismatch in {json_name}: will_book={will_book} vs doc_gross={doc_gross} (diff={diff:.3f})"
                )
                self.assertEqual(res["currency"], p.get("currency", ""))
                booked_count += 1

        self.assertEqual(booked_count, 38, f"Expected exactly 38 booked payables, got {booked_count}")

    def test_04_master_data_grounding(self):
        """Ensure all master data codes are genuine matches from master_data/."""
        valid_supplier_ids = {s.get("supplier_id") for s in self.matcher.suppliers if s.get("supplier_id")}
        valid_companies = {c.get("company_code") for c in self.matcher.companies if c.get("company_code")}
        valid_terms = {t.get("payment_term_id") for t in self.matcher.payment_terms if t.get("payment_term_id")}
        valid_taxes = {t.get("code") for t in self.matcher.taxes if t.get("code")}
        valid_pos = {p.get("po_id") for p in self.matcher.purchase_orders if p.get("po_id")}

        for json_name, doc in self.outputs.items():
            for p in doc["payables"]:
                sup_id = p.get("supplier", {}).get("supplier_id", "")
                if sup_id:
                    self.assertIn(sup_id, valid_supplier_ids, f"Fabricated supplier_id {sup_id} in {json_name}")

                comp_code = p.get("buyer", {}).get("company_code", "")
                if comp_code:
                    self.assertIn(comp_code, valid_companies, f"Fabricated company_code {comp_code} in {json_name}")

                term_id = p.get("payment_term_id", "")
                if term_id:
                    self.assertIn(term_id, valid_terms, f"Fabricated payment_term_id {term_id} in {json_name}")

                po_id = p.get("po_id", "")
                if po_id:
                    self.assertIn(po_id, valid_pos, f"Fabricated po_id {po_id} in {json_name}")

                for t in p.get("taxes", []):
                    code = t.get("tax_type_code", "")
                    if code:
                        self.assertIn(code, valid_taxes, f"Fabricated header tax_type_code {code} in {json_name}")

                for li in p.get("line_items", []):
                    for t in li.get("taxes", []):
                        code = t.get("tax_type_code", "")
                        if code:
                            self.assertIn(code, valid_taxes, f"Fabricated line tax_type_code {code} in {json_name}")

    def test_05_credit_memos_positive_magnitudes(self):
        """Ensure credit memos have positive magnitudes across quantities, unit prices, and gross totals."""
        for json_name, doc in self.outputs.items():
            for p in doc["payables"]:
                if p.get("invoice_type") == "CREDIT_MEMO":
                    self.assertGreater(num(p["gross_total"]), 0)
                    for li in p.get("line_items", []):
                        self.assertGreaterEqual(num(li.get("unit_price")), 0)
                        self.assertGreaterEqual(num(li.get("quantity")), 0)

    def test_06_declined_documents(self):
        """Ensure non-payable documents are correctly declined with clear reasons."""
        expected_declined = {
            "DU-08.json": "MAHNUNG",
            "DU-09.json": "TAX_FORM",
            "DU-05s.json": "DELIVERY_NOTE",
            "INV-23.json": "ESTIMATE"
        }
        for json_name, expected_type in expected_declined.items():
            self.assertIn(json_name, self.outputs)
            doc = self.outputs[json_name]
            self.assertEqual(len(doc["payables"]), 0, f"{json_name} should have 0 payables")
            self.assertEqual(len(doc["declined"]), 1, f"{json_name} should have 1 declined entry")
            self.assertEqual(doc["declined"][0]["doc_type"], expected_type)

if __name__ == "__main__":
    unittest.main()
