from engine.instruments.providers.angel_provider import AngelInstrumentProvider


provider = AngelInstrumentProvider()

instruments = provider.download()

print("=" * 80)
print("Provider :", provider.name)
print("Count    :", len(instruments))
print()

for instrument in instruments[:10]:
    print(instrument)