from collections import Counter

from engine.instruments.providers.angel_provider import AngelInstrumentProvider


provider = AngelInstrumentProvider()

instruments = provider.download()

print("=" * 80)
print("TOTAL INSTRUMENTS")
print(len(instruments))

print("\n" + "=" * 80)
print("EXCHANGES")

exchange_counter = Counter()

for instrument in instruments:
    exchange_counter[instrument.exchange] += 1

for exchange, count in exchange_counter.most_common():
    print(f"{exchange:10} {count}")

print("\n" + "=" * 80)
print("ASSET TYPES")

asset_counter = Counter()

for instrument in instruments:
    asset_counter[instrument.asset_type] += 1

for asset, count in asset_counter.most_common():
    print(f"{asset:15} {count}")

print("\n" + "=" * 80)
print("LOT SIZE DISTRIBUTION (TOP 20)")

lot_counter = Counter()

for instrument in instruments:
    lot_counter[instrument.lot_size] += 1

for lot, count in lot_counter.most_common(20):
    print(f"{str(lot):8} {count}")