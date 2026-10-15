import os
import sys
import json
import pymupdf
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding='utf-8')

ocr = RapidOCR()
doc_dir = r"assignment_workspace/documents"
out_dir = r"assignment_workspace/extracted_cache"
os.makedirs(out_dir, exist_ok=True)

files = sorted(os.listdir(doc_dir))
print(f"Starting extraction for {len(files)} files...", flush=True)

for idx, f in enumerate(files):
    out_file = os.path.join(out_dir, f.replace(".pdf", ".json"))
    if os.path.exists(out_file):
        print(f"[{idx+1}/{len(files)}] Skipping {f} (already cached)", flush=True)
        continue

    path = os.path.join(doc_dir, f)
    doc = pymupdf.open(path)
    file_data = {
        "file": f,
        "page_count": len(doc),
        "pages": []
    }

    for p in range(len(doc)):
        page = doc[p]
        text = page.get_text()
        has_embedded_text = len(text.strip()) > 50

        # Run OCR
        pix = page.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
        if pix.n == 4:
            img = img[:, :, :3]
        
        ocr_res, elapse = ocr(img)
        ocr_boxes = []
        if ocr_res:
            for item in ocr_res:
                box, txt, score = item
                ocr_boxes.append({
                    "box": box,
                    "text": txt,
                    "score": float(score)
                })

        page_data = {
            "page_num": p,
            "width": page.rect.width,
            "height": page.rect.height,
            "has_embedded_text": has_embedded_text,
            "embedded_text": text if has_embedded_text else "",
            "ocr_boxes": ocr_boxes,
            "ocr_text": "\n".join([b["text"] for b in ocr_boxes])
        }
        file_data["pages"].append(page_data)

    with open(out_file, "w", encoding="utf-8") as out_f:
        json.dump(file_data, out_f, indent=2, ensure_ascii=False)
    
    print(f"[{idx+1}/{len(files)}] Processed {f} ({len(doc)} pages)", flush=True)

print("ALL EXTRACTION COMPLETE!", flush=True)
