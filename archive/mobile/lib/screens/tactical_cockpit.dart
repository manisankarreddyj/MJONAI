import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/mjonai_api_client.dart';
import '../widgets/haptic_kill_slider.dart';

class TacticalCockpitScreen extends StatefulWidget {
  final MjonaiApiClient client;

  const TacticalCockpitScreen({Key? key, required this.client}) : super(key: key);

  @override
  State<TacticalCockpitScreen> createState() => _TacticalCockpitScreenState();
}

class _TacticalCockpitScreenState extends State<TacticalCockpitScreen> {
  final currencyFormat = NumberFormat.currency(locale: 'en_IN', symbol: '₹');

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF030712),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0A0F1D),
        elevation: 0,
        title: Row(
          children: [
            const Icon(Icons.flash_on, color: Color(0xFF00F0FF), size: 20),
            const SizedBox(width: 8),
            const Text(
              'MJONAI COMMANDER',
              style: TextStyle(
                color: Color(0xFF00F0FF),
                fontWeight: FontWeight.w900,
                letterSpacing: 1.5,
                fontSize: 16,
              ),
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: const Color(0xFF05FFA1).withOpacity(0.15),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: const Color(0xFF05FFA1)),
              ),
              child: const Text(
                'LIVE',
                style: TextStyle(
                  color: Color(0xFF05FFA1),
                  fontWeight: FontWeight.bold,
                  fontSize: 11,
                ),
              ),
            ),
          ],
        ),
      ),
      body: StreamBuilder<Map<String, dynamic>>(
        stream: widget.client.telemetryStream,
        builder: (context, snapshot) {
          final data = snapshot.data ?? {};
          final pnl = (data['total_unrealized_pnl'] as num?)?.toDouble() ?? 0.0;
          final isPositive = pnl >= 0;
          final openTrades = (data['open_trades'] as List?) ?? [];

          return Column(
            children: [
              // Top PnL Banner
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 24, horizontal: 20),
                decoration: const BoxDecoration(
                  color: Color(0xFF0A0F1D),
                  border: Border(bottom: BorderSide(color: Colors.white12)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'TOTAL UNREALIZED PnL',
                      style: TextStyle(
                        color: Colors.white54,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${isPositive ? '+' : ''}${currencyFormat.format(pnl)}',
                      style: TextStyle(
                        color: isPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F),
                        fontSize: 36,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${openTrades.length} Active Positions • Session: ${data['session_state'] ?? 'REGULAR_MARKET'}',
                      style: const TextStyle(color: Colors.white38, fontSize: 12),
                    ),
                  ],
                ),
              ),

              // Active Position Cards
              Expanded(
                child: openTrades.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: const [
                            Icon(Icons.radar, color: Colors.white24, size: 48),
                            SizedBox(height: 12),
                            Text(
                              'Algorithmic Scanners Active\nNo open positions right now',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: Colors.white38, height: 1.5),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: openTrades.length,
                        itemBuilder: (context, idx) {
                          final t = openTrades[idx];
                          final tradePnl = (t['pnl'] as num?)?.toDouble() ?? 0.0;
                          final tPositive = tradePnl >= 0;

                          return Container(
                            margin: const EdgeInsets.only(bottom: 12),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0F172A),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.white12),
                            ),
                            child: Column(
                              children: [
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      t['symbol'] ?? 'SYMBOL',
                                      style: const TextStyle(
                                        color: Color(0xFF00F0FF),
                                        fontWeight: FontWeight.w900,
                                        fontSize: 16,
                                      ),
                                    ),
                                    Text(
                                      '${tPositive ? '+' : ''}${currencyFormat.format(tradePnl)}',
                                      style: TextStyle(
                                        color: tPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F),
                                        fontWeight: FontWeight.w900,
                                        fontSize: 15,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text('Entry: ₹${t['entry_price']}', style: const TextStyle(color: Colors.white60, fontSize: 12)),
                                    Text('LTP: ₹${t['current_price']}', style: const TextStyle(color: Colors.white, fontSize: 12)),
                                    Text('Stop: ₹${t['trailing_stop']}', style: const TextStyle(color: Color(0xFFFFB800), fontSize: 12)),
                                  ],
                                ),
                                const SizedBox(height: 12),
                                ElevatedButton(
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: const Color(0xFFFF2A5F).withOpacity(0.15),
                                    side: const BorderSide(color: Color(0xFFFF2A5F)),
                                    minimumSize: const Size(double.infinity, 36),
                                  ),
                                  onPressed: () async {
                                    await widget.client.closeTrade(t['id']);
                                  },
                                  child: const Text('LIQUIDATE POSITION', style: TextStyle(color: Color(0xFFFF2A5F), fontSize: 11, fontWeight: FontWeight.bold)),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
              ),

              // Emergency Haptic Kill Switch at the bottom
              HapticKillSlider(
                onEmergencyKill: () async {
                  await widget.client.triggerEmergencyKill();
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('🚨 MASTER KILL-SWITCH ENGAGED! ALL TRADES SQUARED OFF.'),
                        backgroundColor: Color(0xFFFF2A5F),
                      ),
                    );
                  }
                },
              ),
            ],
          );
        },
      ),
    );
  }
}
