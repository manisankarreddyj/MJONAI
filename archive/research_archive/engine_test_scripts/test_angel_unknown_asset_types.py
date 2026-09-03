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
    instrument_type = row.get("instrumenttype", "").strip()

    if instrument_type not in {
        "",
        "AMXIDX",
        "INDEX",
        "OPTSTK",
        "OPTIDX",
        "OPTFUT",
        "OPTCUR",
        "OPTIRC",
        "OPTBLN",
        "FUTSTK",
        "FUTIDX",
        "FUTCUR",
        "FUTCOM",
        "FUTBLN",
        "FUTIRC",
        "FUTIRT",
        "FUTBAS",
        "FUTENR",
        "COMDTY",
    }:
        counter[instrument_type] += 1

print("=" * 80)

for k, v in counter.most_common():
    print(f"{k:15} {v}")