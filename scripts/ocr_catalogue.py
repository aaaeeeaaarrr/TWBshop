"""Batch-classify every archived report photo with the PRODUCTION OCR function
(shared.ai_client.assess_receipt_photo) and write one JSONL row per photo.

Dogfoods the real P1 pipeline on 3 weeks of real receipts. Idempotent + resumable
(skips files already in the catalogue), gentle concurrency, never crashes the batch
on one bad image. Run ON THE SERVER (where ANTHROPIC_API_KEY + the archive live).

    /root/venv/bin/python scripts/ocr_catalogue.py
"""
import asyncio
import glob
import json
import os
import sys

sys.path.insert(0, "/root/TWBshop")

from shared.ai_client import assess_receipt_photo

SRC = "/root/TWBshop/receipts_archive/TWB_REPORT"
OUT = "/root/TWBshop/receipts_archive/ocr_catalogue.jsonl"
CONCURRENCY = 6


async def classify(sem, path):
    fn = os.path.basename(path)
    async with sem:
        try:
            with open(path, "rb") as f:
                r = await assess_receipt_photo(f.read())
        except Exception as e:  # one bad image must not kill the run
            r = {"error": str(e)}
    r["file"] = fn
    r["date"] = fn[:10]
    return r


async def run():
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["file"])
                except Exception:
                    pass
    files = [p for p in sorted(glob.glob(SRC + "/*.jpg"))
             if os.path.basename(p) not in done]
    print(f"{len(done)} already catalogued; {len(files)} to do.")

    sem = asyncio.Semaphore(CONCURRENCY)
    n = 0
    with open(OUT, "a", encoding="utf-8") as out:
        for fut in asyncio.as_completed([classify(sem, p) for p in files]):
            r = await fut
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(files)} ...")
    print(f"OCR complete: {n} new rows, catalogue total {len(done) + n}.")


if __name__ == "__main__":
    asyncio.run(run())
