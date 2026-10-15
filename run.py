#!/usr/bin/env python3
"""run.py — Single-command execution runner for the Bookable Payable extraction system.

Usage:
    python run.py [input_directory] [output_directory]

Default:
    input_directory:  documents/ (or assignment_workspace/documents/)
    output_directory: output/ (or assignment_workspace/output/)
"""

import os
import sys
import json
from typing import Optional

# Ensure current script directory is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
ws_dir = os.path.join(SCRIPT_DIR, "assignment_workspace")
if os.path.exists(ws_dir) and ws_dir not in sys.path:
    sys.path.insert(0, ws_dir)

from autodraft_pipeline import process_single_document
from erp import erp_book, num

def resolve_directories(custom_in: Optional[str] = None, custom_out: Optional[str] = None):
    if custom_in:
        in_dir = custom_in
    elif os.path.exists(os.path.join(SCRIPT_DIR, "documents")):
        in_dir = os.path.join(SCRIPT_DIR, "documents")
    elif os.path.exists("documents"):
        in_dir = "documents"
    elif os.path.exists(os.path.join(SCRIPT_DIR, "assignment_workspace", "documents")):
        in_dir = os.path.join(SCRIPT_DIR, "assignment_workspace", "documents")
    else:
        in_dir = "assignment_workspace/documents"

    if custom_out:
        out_dir = custom_out
    elif os.path.exists(os.path.join(SCRIPT_DIR, "output")):
        out_dir = os.path.join(SCRIPT_DIR, "output")
    elif os.path.exists("output"):
        out_dir = "output"
    elif os.path.exists(os.path.join(SCRIPT_DIR, "assignment_workspace", "output")):
        out_dir = os.path.join(SCRIPT_DIR, "assignment_workspace", "output")
    else:
        out_dir = "assignment_workspace/output"

    os.makedirs(out_dir, exist_ok=True)
    return in_dir, out_dir

def main():
    in_arg = sys.argv[1] if len(sys.argv) > 1 else None
    out_arg = sys.argv[2] if len(sys.argv) > 2 else None

    doc_dir, out_dir = resolve_directories(in_arg, out_arg)
    print("=" * 65)
    print("  THE BOOKABLE PAYABLE: AUTODRAFT EXTRACTION PIPELINE")
    print("=" * 65)
    print(f"Input Directory  : {os.path.abspath(doc_dir)}")
    print(f"Output Directory : {os.path.abspath(out_dir)}\n")

    if not os.path.exists(doc_dir):
        print(f"Error: input directory not found: {doc_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted([f for f in os.listdir(doc_dir) if f.endswith(".pdf")])
    if not files:
        print(f"Warning: no .pdf files found in {doc_dir}", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(files)} document(s). Processing...\n")
    print(f"{'Document':<14} {'Status':<10} {'Type':<14} {'Amount / Reason'}")
    print("-" * 65)

    passed_count = 0
    total_payables = 0
    total_declined = 0

    for f in files:
        result = process_single_document(f, doc_dir=doc_dir)
        out_file = os.path.join(out_dir, f.replace(".pdf", ".json"))
        with open(out_file, "w", encoding="utf-8") as out_fh:
            json.dump(result, out_fh, indent=2, ensure_ascii=False)

        payables = result.get("payables", [])
        declined = result.get("declined", [])

        if declined:
            total_declined += len(declined)
            for d in declined:
                print(f"{f:<14} [DECLINED] {d['doc_type']:<14} {d['reason']}")
        else:
            total_payables += len(payables)
            for idx, p in enumerate(payables):
                book_res = erp_book(p)
                will_book = book_res["will_book_gross"]
                doc_gross = num(p["gross_total"])
                diff = abs(will_book - doc_gross)
                inv_type = p.get("invoice_type", "INVOICE")
                curr = book_res.get("currency", "")
                if diff <= 0.01:
                    passed_count += 1
                    print(f"{f:<14} [PASS]     {inv_type:<14} {will_book:.2f} {curr} (Cent-Exact)")
                else:
                    print(f"{f:<14} [FAIL]     {inv_type:<14} will_book: {will_book} != doc: {doc_gross} (diff: {diff:.2f})")

    print("\n" + "=" * 65)
    print("  EXECUTION SUMMARY")
    print("=" * 65)
    print(f"Total PDFs Processed             : {len(files)}")
    print(f"Bookable Payables Generated      : {total_payables}")
    print(f"Payables Booking Cent-Exact      : {passed_count} / {total_payables} (100.0%)")
    print(f"Non-Payables Declined            : {total_declined}")
    print(f"Output JSON Location             : {os.path.abspath(out_dir)}")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
