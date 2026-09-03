"""
Module: forward_returns.py

Purpose: Calculate and store forward returns for all signals.
         Powers Alphalens IC analysis.
         Runs daily at 4 PM IST via scheduler.

Depends on: db/repository.py, yfinance

Used by: main.py (scheduled job), research/analysis.py

Last modified: 2026-05-06

"""

import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Forward return windows in trading days
FORWARD_WINDOWS = [1, 3, 5, 10, 20]


def calculate_and_store_forward_returns() -> dict:
    """
    Calculate forward returns for all signals that don't have them yet.
    
    For every signal in signal_intelligence_log:
    - Calculate actual forward returns at 1, 3, 5, 10, 20 day windows
    - Store in signal_intelligence_log
    
    This runs REGARDLESS of whether a trade was opened.
    Even rejected signals get forward returns calculated.
    This is the key data for Alphalens.
    
    Returns:
        dict with stats: {
            "signals_processed": int,
            "signals_updated": int,
            "errors": int
        }
    """
    from db.repository import get_signals_needing_forward_returns, update_signal_forward_returns
    
    stats = {
        "signals_processed": 0,
        "signals_updated": 0,
        "errors": 0
    }
    
    # Get signals that need forward returns
    signals = get_signals_needing_forward_returns()
    
    if not signals:
        logger.info("[forward_returns] No signals need forward returns")
        return stats
    
    logger.info(f"[forward_returns] Processing {len(signals)} signals...")
    
    # Group by symbol to minimize yfinance calls
    signals_by_symbol = {}
    for signal in signals:
        symbol = signal.get("symbol")
        if symbol:
            if symbol not in signals_by_symbol:
                signals_by_symbol[symbol] = []
            signals_by_symbol[symbol].append(signal)
    
    logger.info(f"[forward_returns] {len(signals_by_symbol)} unique symbols to process")
    
    for symbol, symbol_signals in signals_by_symbol.items():
        try:
            # Download price data for this symbol
            df = yf.download(
                symbol + ".NS",
                period="3mo",
                interval="1d",
                progress=False
            )
            
            if df.empty or len(df) < 5:
                logger.warning(f"[forward_returns] {symbol} — insufficient data ({len(df)} rows)")
                stats["errors"] += len(symbol_signals)
                continue
            
            close_series = df["Close"].squeeze()
            
            # Process each signal for this symbol
            for signal in symbol_signals:
                stats["signals_processed"] += 1
                
                try:
                    returns = _calculate_returns_for_signal(
                        signal=signal,
                        close_series=close_series,
                        symbol=symbol
                    )
                    
                    if returns:
                        # Update signal with forward returns
                        update_signal_forward_returns(signal["id"], returns)
                        stats["signals_updated"] += 1
                        
                except Exception as e:
                    logger.warning(f"[forward_returns] Error processing signal {signal.get('id')}: {e}")
                    stats["errors"] += 1
                    
        except Exception as e:
            logger.warning(f"[forward_returns] Error downloading {symbol}: {e}")
            stats["errors"] += len(symbol_signals)
    
    logger.info(
        f"[forward_returns] Complete: "
        f"{stats['signals_updated']}/{stats['signals_processed']} updated, "
        f"{stats['errors']} errors"
    )
    
    return stats


def _calculate_returns_for_signal(
    signal: dict,
    close_series: pd.Series,
    symbol: str
) -> dict | None:
    """
    Calculate forward returns for a single signal.
    
    Args:
        signal: Signal dict from database
        close_series: Price series for the symbol
        symbol: Stock symbol
    
    Returns:
        dict with forward return values, or None if calculation fails
    """
    from core.time_utils import today_ist
    
    # Get signal date
    generated_at = signal.get("generated_at")
    if not generated_at:
        return None
    
    # Parse signal date
    if isinstance(generated_at, str):
        try:
            signal_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except:
            return None
    else:
        signal_dt = generated_at
    
    signal_date = signal_dt.date()
    
    # Find the signal date in the price series
    # We need the close price on the signal date as the entry price
    entry_idx = None
    entry_price = None
    
    for i, (date, price) in enumerate(close_series.items()):
        if hasattr(date, 'date'):
            price_date = date.date()
        else:
            price_date = date
        
        if price_date == signal_date:
            entry_idx = i
            entry_price = float(price)
            break
    
    if entry_idx is None or entry_price is None:
        # Signal date not found in price series
        return None
    
    # Calculate forward returns for each window
    returns = {}
    
    for window in FORWARD_WINDOWS:
        future_idx = entry_idx + window
        
        if future_idx < len(close_series):
            future_price = float(close_series.iloc[future_idx])
            
            # Calculate return
            forward_return = (future_price - entry_price) / entry_price
            returns[f"forward_return_{window}d"] = round(forward_return, 6)
            
            # Calculate P&L based on planned quantity
            planned_qty = signal.get("planned_quantity", 1)
            pnl = (future_price - entry_price) * planned_qty
            returns[f"pnl_{window}d"] = round(pnl, 2)
        else:
            # Not enough future data for this window
            returns[f"forward_return_{window}d"] = None
            returns[f"pnl_{window}d"] = None
    
    return returns


def build_alphalens_dataset(
    strategy_id: str = None,
    start_date: str = None,
    end_date: str = None,
) -> tuple:
    """
    Build factor_data and prices DataFrames for Alphalens.
    
    Args:
        strategy_id: Filter by strategy (optional)
        start_date: Start date for data (optional)
        end_date: End date for data (optional)
    
    Returns:
        factor: pd.Series indexed by (date, asset) — signal strength
        prices: pd.DataFrame indexed by date, columns = assets
    """
    from db.repository import get_signals_for_alphalens
    
    signals = get_signals_for_alphalens(
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    if not signals:
        logger.warning("[alphalens] No signals found for dataset")
        return pd.Series(), pd.DataFrame()
    
    # Build factor Series — signal value (RSI, BB%, etc.)
    factor_tuples = []
    
    for sig in signals:
        dt = pd.Timestamp(sig["generated_at"])
        sym = sig["symbol"]
        
        # Use raw_signal_value if available, otherwise final_confidence
        val = sig.get("raw_signal_value") or sig.get("final_confidence")
        
        if val is not None:
            factor_tuples.append(((dt, sym), val))
    
    if not factor_tuples:
        logger.warning("[alphalens] No valid factor values found")
        return pd.Series(), pd.DataFrame()
    
    factor = pd.Series(
        dict(factor_tuples),
        name="factor"
    )
    factor.index = pd.MultiIndex.from_tuples(
        factor.index, names=["date", "asset"]
    )
    
    # Build prices DataFrame
    symbols = list(set(sig["symbol"] for sig in signals))
    
    # Determine date range
    if start_date:
        start = pd.Timestamp(start_date)
    else:
        start = min(pd.Timestamp(sig["generated_at"]) for sig in signals) - timedelta(days=5)
    
    if end_date:
        end = pd.Timestamp(end_date)
    else:
        end = today_ist()
    
    prices = {}
    
    for sym in symbols:
        try:
            df = yf.download(
                sym + ".NS",
                start=start,
                end=end,
                progress=False
            )
            if not df.empty:
                prices[sym] = df["Close"].squeeze()
        except Exception as e:
            logger.warning(f"[alphalens] Failed to download {sym}: {e}")
    
    if not prices:
        logger.warning("[alphalens] No price data available")
        return factor, pd.DataFrame()
    
    prices_df = pd.DataFrame(prices)
    
    logger.info(f"[alphalens] Built dataset: {len(factor)} signals, {len(symbols)} symbols")
    
    return factor, prices_df


def run_alphalens_analysis(
    strategy_id: str = None,
    start_date: str = None,
    end_date: str = None
) -> dict | None:
    """
    Run Alphalens IC analysis on accumulated signals.
    
    Args:
        strategy_id: Filter by strategy (optional)
        start_date: Start date for analysis (optional)
        end_date: End date for analysis (optional)
    
    Returns:
        dict with IC values, or None if insufficient data
    """
    try:
        import alphalens
    except ImportError:
        logger.error("[alphalens] alphalens-reloaded not installed. Run: pip install alphalens-reloaded")
        return None
    
    factor, prices = build_alphalens_dataset(
        strategy_id=strategy_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    if len(factor) < 30:
        logger.warning(f"[alphalens] Insufficient data: {len(factor)} signals. Need 30+.")
        return None
    
    try:
        factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
            factor    = factor,
            prices    = prices,
            periods   = (1, 5, 10, 20),
            quantiles = 5,
        )
        
        # Calculate IC
        ic_summary = alphalens.performance.factor_information_coefficient(factor_data)
        
        result = {
            "strategy_id": strategy_id or "ALL",
            "signals_count": len(factor),
            "ic_1d": round(float(ic_summary.iloc[:, 0].mean()), 4),
            "ic_5d": round(float(ic_summary.iloc[:, 1].mean()), 4),
            "ic_10d": round(float(ic_summary.iloc[:, 2].mean()), 4),
            "ic_20d": round(float(ic_summary.iloc[:, 3].mean()), 4),
            "ic_1d_std": round(float(ic_summary.iloc[:, 0].std()), 4),
            "ic_5d_std": round(float(ic_summary.iloc[:, 1].std()), 4),
            "ic_10d_std": round(float(ic_summary.iloc[:, 2].std()), 4),
            "ic_20d_std": round(float(ic_summary.iloc[:, 3].std()), 4),
        }
        
        logger.info(
            f"[alphalens] {strategy_id or 'ALL'}: "
            f"IC 1d={result['ic_1d']}, 5d={result['ic_5d']}, "
            f"10d={result['ic_10d']}, 20d={result['ic_20d']}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[alphalens] Analysis failed: {e}")
        return None


if __name__ == "__main__":
    # Test the forward returns calculation
    logging.basicConfig(level=logging.INFO)
    
    stats = calculate_and_store_forward_returns()
    print(f"\nForward Returns Stats: {stats}")
