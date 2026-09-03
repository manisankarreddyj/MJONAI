from engine.strategies.registry import StrategyRegistry


print("=" * 80)
print("STRATEGY REGISTRY")
print("=" * 80)

print()

print("Available Strategies:")

for strategy in StrategyRegistry.available():
    print("-", strategy)

print()

strategy = StrategyRegistry.load(
    "S01_MomentumRSI",
)

print("Loaded Strategy")

print("Name      :", strategy.name)
print("Version   :", strategy.version)
print("Timeframe :", strategy.timeframe)