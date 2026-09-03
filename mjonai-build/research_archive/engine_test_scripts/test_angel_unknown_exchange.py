import json
import urllib.request
from collections import Counter

URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

with urllib.request.urlopen(URL) as response:
    data = json.loads(response.read())

counter = Counter()

for row in data:

    exch = row["exch_seg"]

    if exch in ("BFO", "NCO"):

        counter[(exch, row["instrumenttype"])] += 1

print("=" * 80)

for item, count in counter.most_common():
    print(item, count)