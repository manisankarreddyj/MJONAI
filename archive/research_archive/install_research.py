"""
Module: install_research.py

Purpose: One-time setup script for research infrastructure.
         Installs packages, creates DuckDB schema, verifies setup.

Run once: python research/install_research.py

Last modified: 2026-07-05
"""

import subprocess
import sys

PACKAGES = [
    "nselib",           # Auto-fetch NSE stock lists
    "nsepython",        # NSE data (backup)
    "jugaad-data",      # Historical NSE data, constituents
    "duckdb",           # Fast analytical database
    "statsmodels",      # Statistical tests, multiple testing correction
]

def install_packages():
    """Install missing research packages."""
    print("Installing research packages...")
    for pkg in PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"  ✅ {pkg} — already installed")
        except ImportError:
            print(f"  📦 Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
            print(f"  ✅ {pkg} — installed")

    # TA-Lib — already installed via apt
    try:
        import talib
        print(f"  ✅ TA-Lib — already installed (indicators: {len(talib.get_functions())})")
    except ImportError:
        print(f"  ⚠️ TA-Lib not found — install via: sudo apt install ta-lib && pip install TA-Lib")

    # VectorBT — already installed
    try:
        import vectorbt as vbt
        print(f"  ✅ VectorBT {vbt.__version__} — already installed")
    except ImportError:
        print(f"  ⚠️ VectorBT not found — pip install vectorbt")

    # MLflow — optional for now
    try:
        import mlflow
        print(f"  ✅ MLflow {mlflow.__version__}")
    except ImportError:
        print(f"  📦 Installing mlflow...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "mlflow", "-q"])
            print(f"  ✅ MLflow — installed")
        except Exception:
            print(f"  ⚠️ MLflow install failed — not critical, can add later")

def create_duckdb_schema():
    """Create DuckDB database and tables for research results."""
    import duckdb
    import os

    db_path = os.path.join(os.path.dirname(__file__), "research_data.duckdb")
    con = duckdb.connect(db_path)

    # Table 1: Backtest results (millions of rows)
    con.execute("""
        CREATE TABLE IF NOT EXISTS backtest_results (
            id              INTEGER PRIMARY KEY,
            run_id          VARCHAR,
            stock           VARCHAR,
            indicator       VARCHAR,
            parameters      VARCHAR,
            timeframe       VARCHAR,
            holding_days    INTEGER,
            direction       VARCHAR,
            signal_date     DATE,
            entry_date      DATE,
            exit_date       DATE,
            entry_price     DOUBLE,
            exit_price      DOUBLE,
            gross_return    DOUBLE,
            net_return      DOUBLE,
            total_cost      DOUBLE,
            win             BOOLEAN,
            actual_rr       DOUBLE,
            market_state    VARCHAR,
            vix             DOUBLE,
            sector          VARCHAR,
            forward_return_1d   DOUBLE,
            forward_return_5d   DOUBLE,
            forward_return_20d  DOUBLE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 2: Indicator signal log
    con.execute("""
        CREATE TABLE IF NOT EXISTS indicator_signals (
            id              INTEGER PRIMARY KEY,
            run_id          VARCHAR,
            stock           VARCHAR,
            indicator       VARCHAR,
            parameters      VARCHAR,
            timeframe       VARCHAR,
            direction       VARCHAR,
            signal_date     DATE,
            signal_price    DOUBLE,
            signal_value    DOUBLE,
            rsi             DOUBLE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 3: Composite signals
    con.execute("""
        CREATE TABLE IF NOT EXISTS composite_signals (
            id              INTEGER PRIMARY KEY,
            run_id          VARCHAR,
            stock           VARCHAR,
            indicators      VARCHAR,
            direction       VARCHAR,
            signal_date     DATE,
            entry_price     DOUBLE,
            exit_price      DOUBLE,
            composite_score DOUBLE,
            holding_days    INTEGER,
            gross_return    DOUBLE,
            net_return      DOUBLE,
            win             BOOLEAN,
            actual_rr       DOUBLE,
            market_state    VARCHAR,
            vix             DOUBLE,
            sector          VARCHAR,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table 4: Stock metadata
    con.execute("""
        CREATE TABLE IF NOT EXISTS stock_metadata (
            symbol          VARCHAR PRIMARY KEY,
            sector          VARCHAR,
            market_cap      DOUBLE,
            avg_volume      DOUBLE,
            avg_turnover    DOUBLE,
            volatility_30d  DOUBLE,
            beta            DOUBLE,
            liquidity_score DOUBLE,
            updated_at      DATE
        )
    """)

    # Table 5: Regime history
    con.execute("""
        CREATE TABLE IF NOT EXISTS regime_history (
            date            DATE PRIMARY KEY,
            market_state    VARCHAR,
            vix             DOUBLE,
            mqi_level       VARCHAR,
            fii_net_cr      DOUBLE,
            nifty_price     DOUBLE,
            ema200          DOUBLE,
            breadth_pct     DOUBLE
        )
    """)

    # Table 6: Options results
    con.execute("""
        CREATE TABLE IF NOT EXISTS options_results (
            id              INTEGER PRIMARY KEY,
            run_id          VARCHAR,
            underlying      VARCHAR,
            option_type     VARCHAR,
            strike          DOUBLE,
            expiry          DATE,
            direction       VARCHAR,
            signal_date     DATE,
            entry_date      DATE,
            exit_date       DATE,
            entry_premium   DOUBLE,
            exit_premium    DOUBLE,
            iv_at_entry     DOUBLE,
            iv_at_exit      DOUBLE,
            delta_entry     DOUBLE,
            theta_entry     DOUBLE,
            vega_entry      DOUBLE,
            gross_return    DOUBLE,
            net_return      DOUBLE,
            win             BOOLEAN,
            actual_rr       DOUBLE,
            market_state    VARCHAR,
            vix             DOUBLE,
            iv_rank         DOUBLE,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indexes
    con.execute("CREATE INDEX IF NOT EXISTS idx_br_indicator ON backtest_results(indicator)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_br_stock ON backtest_results(stock)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_br_run ON backtest_results(run_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_br_direction ON backtest_results(direction)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_br_market_state ON backtest_results(market_state)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_is_indicator ON indicator_signals(indicator)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_is_stock ON indicator_signals(stock)")

    # Verify
    tables = con.execute("SHOW TABLES").fetchall()
    print(f"\n✅ DuckDB created: {db_path}")
    print(f"   Tables: {len(tables)}")
    for t in tables:
        count = con.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"   └── {t[0]}: {count} rows")

    con.close()

def verify_setup():
    """Verify all components are working."""
    print("\nVerifying setup...")

    import talib
    print(f"  ✅ TA-Lib — {len(talib.get_functions())} functions available")

    import duckdb
    print(f"  ✅ duckdb {duckdb.__version__}")

    import statsmodels
    print(f"  ✅ statsmodels {statsmodels.__version__}")

    try:
        from nselib import capital_market
        print(f"  ✅ nselib — available")
    except ImportError:
        print(f"  ⚠️ nselib — not available")

    try:
        from jugaad_data.nse import stock_df
        print(f"  ✅ jugaad-data — available")
    except ImportError:
        print(f"  ⚠️ jugaad-data — not available")

    try:
        import mlflow
        print(f"  ✅ mlflow {mlflow.__version__}")
    except ImportError:
        print(f"  ⚠️ mlflow — not available (optional)")

    print("\n✅ Research infrastructure ready!")

if __name__ == "__main__":
    print("=" * 50)
    print("MJONAI Research Infrastructure Setup")
    print("=" * 50)

    install_packages()
    create_duckdb_schema()
    verify_setup()

    print("\n" + "=" * 50)
    print("Setup complete. Ready for Phase A: Equity grid test.")
    print("Run: python research/run_research.py --quick")
    print("=" * 50)