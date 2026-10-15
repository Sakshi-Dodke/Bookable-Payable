import os
import sys
import json
import pymupdf
import numpy as np
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

sys.stdout.reconfigure(encoding='utf-8')

DOC_DIR = r"assignment_workspace/documents"
OUT_DIR = r"assignment_workspace/extracted_cache"

_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine

def process_file(filename):
    out_file = os.path.join(OUT_DIR, filename.replace(".pdf", ".json"))
    if os.path.exists(out_file):
        return f"[CACHED] {filename}"
    
    ocr = get_ocr_engine()
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
            pix = page.get_pixmap(dpi=120)
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

    return f"[DONE] {filename} ({len(doc)} pages)"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(os.listdir(DOC_DIR))
    print(f"Parallel extraction of {len(files)} files using 6 workers...", flush=True)
    
    # Process files with fewer pages first so we get quick turnaround, or sorted
    # Let's sort by file size ascending so quick ones finish immediately!
    files_with_size = [(f, os.path.getsize(os.path.join(DOC_DIR, f))) for f in files]
    files_with_size.sort(key=lambda x: x[1])
    sorted_files = [x[0] for x in files_with_size]

    with ProcessPoolExecutor(max_workers=6) as executor:
        for res in executor.map(process_file, sorted_files):
            print(res, flush=True)

    print("ALL 42 DOCUMENTS EXTRACTED AND CACHED SUCCESSFULLY!", flush=True)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
