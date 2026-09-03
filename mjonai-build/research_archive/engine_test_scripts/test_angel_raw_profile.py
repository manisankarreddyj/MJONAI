import json
import urllib.request
from collections import Counter

URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

with urllib.request.urlopen(URL) as response:
    data = json.loads(response.read())

print("=" * 80)
print("TOTAL")
print(len(data))

print("\n" + "=" * 80)
print("EXCHANGE SEGMENTS")

counter = Counter()

for row in data:
    counter[row.get("exch_seg", "")] += 1

for k, v in counter.most_common():
    print(f"{k:15} {v}")

print("\n" + "=" * 80)
print("INSTRUMENT TYPES")

counter = Counter()

for row in data:
    counter[row.get("instrumenttype", "")] += 1

for k, v in counter.most_common():
    print(f"{k:20} {v}")

print("\n" + "=" * 80)
print("SAMPLE ROW")

print(data[0])