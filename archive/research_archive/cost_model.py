def calculate_entry_cost(entry_price, quantity):
    turnover = entry_price * quantity
    brokerage = 20.0
    stt = 0.0
    stamp_duty = turnover * 0.00003
    exchange = turnover * 0.0000297
    gst = brokerage * 0.18
    sebi = turnover * 0.000001
    slippage = turnover * 0.0005
    total = brokerage + stt + stamp_duty + exchange + gst + sebi + slippage
    return {"brokerage": round(brokerage, 2), "stt": round(stt, 2), "stamp_duty": round(stamp_duty, 2), "exchange": round(exchange, 2), "gst": round(gst, 2), "sebi": round(sebi, 2), "slippage": round(slippage, 2), "total": round(total, 2), "total_pct": round(total / turnover * 100, 4) if turnover > 0 else 0}

def calculate_exit_cost(exit_price, quantity):
    turnover = exit_price * quantity
    brokerage = 20.0
    stt = turnover * 0.001
    stamp_duty = 0.0
    exchange = turnover * 0.0000297
    gst = brokerage * 0.18
    sebi = turnover * 0.000001
    slippage = turnover * 0.0005
    total = brokerage + stt + stamp_duty + exchange + gst + sebi + slippage
    return {"brokerage": round(brokerage, 2), "stt": round(stt, 2), "stamp_duty": round(stamp_duty, 2), "exchange": round(exchange, 2), "gst": round(gst, 2), "sebi": round(sebi, 2), "slippage": round(slippage, 2), "total": round(total, 2), "total_pct": round(total / turnover * 100, 4) if turnover > 0 else 0}

def calculate_round_trip_cost(entry_price, exit_price, quantity):
    entry = calculate_entry_cost(entry_price, quantity)
    exit_ = calculate_exit_cost(exit_price, quantity)
    total = entry["total"] + exit_["total"]
    turnover = entry_price * quantity
    return {"entry_cost": entry, "exit_cost": exit_, "total_cost": round(total, 2), "total_cost_pct": round(total / turnover * 100, 4) if turnover > 0 else 0}
