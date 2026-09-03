"""Resumable HF dataset puller -> mjonai-build/storage/temp/hf/. Disposable spike tooling."""
import os, json, sys
import requests

REPO = "thetrademarkk/india-index-options-1m"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
ROOT = r"D:\MJONAI\mjonai-build\storage\temp\hf"
INV = json.load(open(r"D:\MJONAI\planning\supabase\_hf_inventory.json"))

only_prefix = sys.argv[1] if len(sys.argv) > 1 else ""
done = skipped = failed = bytes_written = 0

for item in INV:
    rel, size = item["path"], item["size"]
    if only_prefix and not rel.startswith(only_prefix):
        continue
    dest = os.path.join(ROOT, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and abs(os.path.getsize(dest) - size) < 1024:
        skipped += 1
        continue
    try:
        with requests.get(BASE + rel, stream=True, timeout=120) as r:
            r.raise_for_status()
            tmp = dest + ".part"
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.replace(tmp, dest)
        done += 1
        bytes_written += size
        if (done % 25) == 0:
            print(f"  pulled {done} files ({bytes_written/1e6:.0f} MB this session)", flush=True)
    except Exception as e:
        failed += 1
        print(f"  FAIL {rel}: {str(e)[:80]}", flush=True)

print(f"DONE pulled={done} skipped={skipped} failed={failed} wrote={bytes_written/1e6:.0f}MB")
