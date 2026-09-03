from engine.instruments.providers.angel_provider import AngelInstrumentProvider


provider = AngelInstrumentProvider()

instruments = provider.download()

print("=" * 80)

print("Provider :", provider.name)

print("Total Instruments :", len(instruments))

print()

print("First Instrument")

print(instruments[0])

print()

print("Last Instrument")

print(instruments[-1])