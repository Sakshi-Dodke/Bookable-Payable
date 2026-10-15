import os
import json
import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

class MasterDataMatcher:
    def __init__(self, master_data_dir: Optional[str] = None):
        if master_data_dir is None:
            if os.path.exists("master_data"):
                master_data_dir = "master_data"
            elif os.path.exists("assignment_workspace/master_data"):
                master_data_dir = "assignment_workspace/master_data"
            else:
                base = os.path.dirname(os.path.abspath(__file__))
                master_data_dir = os.path.join(base, "master_data")
        self.master_data_dir = master_data_dir
        self.suppliers = self._load_json("suppliers.json").get("suppliers", [])
        self.companies = self._load_json("chart_of_books.json").get("companies", [])
        self.payment_terms = self._load_json("payment_terms.json").get("payment_terms", [])
        self.taxes = self._load_json("tax_master.json").get("taxes", [])
        self.purchase_orders = self._load_json("po_master.json").get("purchase_orders", [])

        # Build index lookups for high performance and scale
        self.vat_index = {}
        self.iban_index = {}
        for s in self.suppliers:
            vat = self._norm_alphanumeric(s.get("vat_id", ""))
            if vat:
                self.vat_index[vat] = s
            iban = self._norm_alphanumeric(s.get("bank_iban", ""))
            if iban:
                self.iban_index[iban] = s

        self.po_index = {}
        for po in self.purchase_orders:
            po_num = po.get("po_number", "").strip().upper()
            if po_num:
                self.po_index[po_num] = po

    def _load_json(self, filename: str) -> dict:
        path = os.path.join(self.master_data_dir, filename)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    @staticmethod
    def _norm_alphanumeric(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", text).upper()

    def match_supplier(self, text: str) -> Optional[Dict[str, Any]]:
        """Match supplier by VAT ID, IBAN, exact or normalized name, or email."""
        norm_text = self._norm_alphanumeric(text)

        # 1. VAT match
        for vat_key, supp in self.vat_index.items():
            if len(vat_key) >= 6 and vat_key in norm_text:
                return supp

        # 2. IBAN match
        for iban_key, supp in self.iban_index.items():
            if len(iban_key) >= 12 and iban_key in norm_text:
                return supp

        # 3. Name match
        lower_text = text.lower()
        for supp in self.suppliers:
            name = supp.get("name", "").strip().lower()
            if name and name in lower_text:
                return supp
            # Check key tokens if name is long enough
            name_tokens = [t for t in re.split(r"[^\w]+", name) if len(t) > 3]
            if len(name_tokens) >= 2 and all(tok in lower_text for tok in name_tokens):
                return supp

        # 4. Email match
        for supp in self.suppliers:
            email = supp.get("email", "").strip().lower()
            if email and email in lower_text:
                return supp

        return None

    def match_buyer(self, text: str) -> Dict[str, str]:
        """Resolve tenant buyer structure from master data."""
        lower_text = text.lower()
        
        # Check specific business units under BOLTGROUP
        # GB001 - UK
        if "bolt operations uk" in lower_text or ("bolt" in lower_text and ("london" in lower_text or "uk" in lower_text or "gb001" in lower_text)):
            return {
                "company_code": "BOLTGROUP",
                "business_unit_code": "GB001",
                "location_code": "LOC_GB_001"
            }
        # GH001 - Ghana
        if "bolt ghana" in lower_text or ("bolt" in lower_text and ("accra" in lower_text or "ghana" in lower_text or "gh001" in lower_text)):
            return {
                "company_code": "BOLTGROUP",
                "business_unit_code": "GH001",
                "location_code": "LOC_GH_001"
            }
        # MY001 - Malaysia
        if "bolt malaysia" in lower_text or ("bolt" in lower_text and ("kuala lumpur" in lower_text or "malaysia" in lower_text or "my001" in lower_text)):
            return {
                "company_code": "BOLTGROUP",
                "business_unit_code": "MY001",
                "location_code": "LOC_MY_001"
            }
        # ZA001 - South Africa
        if "bolt south africa" in lower_text or ("bolt" in lower_text and ("sandton" in lower_text or "johannesburg" in lower_text or "south africa" in lower_text or "za001" in lower_text)):
            return {
                "company_code": "BOLTGROUP",
                "business_unit_code": "ZA001",
                "location_code": "LOC_ZA_001"
            }
        # EE004 - Bolt Holdings
        if "bolt holdings" in lower_text:
            return {
                "company_code": "BOLTGROUP",
                "business_unit_code": "EE004",
                "location_code": "LOC_EE_001"
            }
        # Default Estonia HQ
        if "bolt" in lower_text or "tallinn" in lower_text or "vana-louna" in lower_text:
            return {
                "company_code": "BOLTGROUP",
                "business_unit_code": "EE001",
                "location_code": "LOC_EE_001"
            }

        return {
            "company_code": "BOLTGROUP",
            "business_unit_code": "",
            "location_code": ""
        }

    def match_payment_term(self, text: str, invoice_date: str = "", due_date: str = "") -> str:
        """Resolve payment term ID via text alias matching or date arithmetic."""
        lower_text = text.lower()

        # Check aliases in descending order of specificity
        for pt in sorted(self.payment_terms, key=lambda x: max(len(a) for a in x.get("text_aliases", [""])), reverse=True):
            for alias in pt.get("text_aliases", []):
                pattern = r"\b" + re.escape(alias.lower()) + r"\b"
                if re.search(pattern, lower_text):
                    return pt.get("payment_term_id", "")

        # Try date arithmetic if both dates are provided
        if invoice_date and due_date:
            try:
                d1 = datetime.fromisoformat(invoice_date)
                d2 = datetime.fromisoformat(due_date)
                delta_days = (d2 - d1).days
                if delta_days >= 0:
                    for pt in self.payment_terms:
                        if pt.get("days") == delta_days and pt.get("payment_term_id") not in ["Immediate", "Monthly_in_advance"]:
                            return pt.get("payment_term_id", "")
                    if delta_days == 0:
                        return "Immediate"
            except Exception:
                pass

        return ""

    def match_tax(self, country: str, rate: float, tax_type: str = "") -> str:
        """Resolve tax code against tax_master.json."""
        c_upper = country.strip().upper()
        t_upper = tax_type.strip().upper()

        # Exact match on country, rate, and tax_type
        for t in self.taxes:
            if t.get("country") == c_upper and abs(float(t.get("rate", 0)) - rate) < 0.05:
                if t_upper and t.get("tax_type") == t_upper:
                    return t.get("code", "")
        
        # Match on country and rate
        for t in self.taxes:
            if t.get("country") == c_upper and abs(float(t.get("rate", 0)) - rate) < 0.05:
                return t.get("code", "")

        # Fallback by rate only if unique
        candidates = [t for t in self.taxes if abs(float(t.get("rate", 0)) - rate) < 0.05]
        if len(candidates) == 1:
            return candidates[0].get("code", "")

        return ""

    def match_po(self, po_raw: str) -> str:
        """Resolve PO against po_master.json."""
        if not po_raw:
            return ""
        norm_po = po_raw.strip().upper()
        if norm_po in self.po_index:
            return self.po_index[norm_po].get("po_id", "")
        return ""
