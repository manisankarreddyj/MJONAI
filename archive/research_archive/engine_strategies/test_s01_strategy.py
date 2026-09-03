import numpy as np
import pandas as pd

from engine.strategies.s01_momentum_rsi import S01MomentumRSI


# ---------------------------------------
# Create sample market
# ---------------------------------------

np.random.seed(42)

close = np.linspace(100, 180, 300)

df = pd.DataFrame(
    {
        "Open": close,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.random.randint(1000, 5000, len(close)),
    }
)

strategy = S01MomentumRSI()

signal = strategy.generate_signal(df)

print("=" * 60)

if signal is None:

    print("No Signal")

else:

    print("Signal Generated")

    print(signal)