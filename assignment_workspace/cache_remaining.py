import os
import sys
import json
import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

DOC_DIR = r"assignment_workspace/documents"
OUT_DIR = r"assignment_workspace/extracted_cache"

remaining = ["INV-06.pdf", "INV-09.pdf", "INV-25.pdf", "DU-06.pdf", "INV-23.pdf", "DU-03.pdf", "DU-05s.pdf", "DU-02.pdf"]

ocr = RapidOCR()

for filename in remaining:
    out_file = os.path.join(OUT_DIR, filename.replace(".pdf", ".json"))
    if os.path.exists(out_file):
        print(f"Skipping {filename} (already cached)", flush=True)
        continue

    print(f"Processing {filename}...", flush=True)
    path = os.path.join(DOC_DIR, filename)
    doc = pymupdf.open(path)
    file_data = {
        "file": filename,
        "page_count": len(doc),
        "pages": []
    }

    for p in range(len(doc)):
        page = doc[p]
        text = page.get_text()
        has_embedded_text = len(text.strip().split()) >= 30

        ocr_boxes = []
        if not has_embedded_text:
            pix = page.get_pixmap(dpi=110)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
            if pix.n == 4:
                img = img[:, :, :3]
            ocr_res, elapse = ocr(img)
            if ocr_res:
                for item in ocr_res:
                    box, txt, score = item
                    ocr_boxes.append({
                        "box": box,
                        "text": txt,
                        "score": float(score)
                    })
            page_text = "\n".join([b["text"] for b in ocr_boxes])
        else:
            page_text = text

        page_data = {
            "page_num": p,
            "width": page.rect.width,
            "height": page.rect.height,
            "has_embedded_text": has_embedded_text,
            "text": page_text,
            "ocr_boxes": ocr_boxes
        }
        file_data["pages"].append(page_data)

    with open(out_file, "w", encoding="utf-8") as out_f:
        json.dump(file_data, out_f, indent=2, ensure_ascii=False)

    print(f"DONE: {filename} ({len(doc)} pages)", flush=True)

print("ALL REMAINING FILES EXTRACTED!", flush=True)
