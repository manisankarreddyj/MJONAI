from engine.instruments.master import InstrumentMaster
from engine.instruments.providers.angel_provider import (
    AngelInstrumentProvider,
)

from engine.research.universe import UniverseManager


print("=" * 80)
print("Loading Instrument Master")

master = InstrumentMaster()

master.load(
    AngelInstrumentProvider().download()
)

print(f"Loaded : {len(master.all()):,}")

print()

manager = UniverseManager(master)

universe = manager.symbols(
    [
        "RELIANCE",
        "TCS",
        "INFY",
        "HDFCBANK",
        "ICICIBANK",
    ]
)

print("=" * 80)
print("Research Universe")

for instrument in universe:
    print(instrument.symbol)