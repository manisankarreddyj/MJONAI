from engine.instruments.master import InstrumentMaster
from engine.instruments.providers.angel_provider import (
    AngelInstrumentProvider,
)


provider = AngelInstrumentProvider()

master = InstrumentMaster()

print("=" * 80)
print("Downloading Angel Instrument Master...")

instruments = provider.download()

print(f"Downloaded : {len(instruments):,}")

print("=" * 80)
print("Loading Instrument Master...")

master.load(instruments)

print("Loaded Successfully")

print()

print("=" * 80)
print("TOTAL")

print(len(master.all()))

print()

print("=" * 80)
print("RELIANCE")

results = master.get_by_symbol("RELIANCE")

print(f"Found : {len(results)}")

for instrument in results[:5]:
    print(instrument)

print()

print("=" * 80)
print("NSE")

print(len(master.by_exchange("NSE")))

print()

print("=" * 80)
print("OPTION")

print(len(master.by_asset_type("OPTION")))

print()

print("=" * 80)
print("ANGEL")

print(len(master.by_provider("ANGEL")))

print()

print("=" * 80)
print("SEARCH : BANK")

results = master.search("BANK")

print(f"Found : {len(results)}")

for instrument in results[:10]:
    print(instrument)

print()

print("=" * 80)
print("TOKEN LOOKUP")

if results:

    token = results[0].token

    lookup = master.get_by_token(
        "ANGEL",
        token,
    )

    print(lookup)