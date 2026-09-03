import 'package:flutter/material.dart';

class DynamicIslandHUD extends StatefulWidget {
  final String symbol;
  final double currentPrice;
  final double pnl;
  final double trailingStop;
  final VoidCallback onEmergencyExit;

  const DynamicIslandHUD({
    Key? key,
    this.symbol = "INFY",
    this.currentPrice = 1915.0,
    this.pnl = 1750.0,
    this.trailingStop = 1895.0,
    required this.onEmergencyExit,
  }) : super(key: key);

  @override
  State<DynamicIslandHUD> createState() => _DynamicIslandHUDState();
}

class _DynamicIslandHUDState extends State<DynamicIslandHUD> with SingleTickerProviderStateMixin {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final isPositive = widget.pnl >= 0;

    return GestureDetector(
      onTap: () {
        setState(() {
          _isExpanded = !_isExpanded;
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOutCubic,
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        width: _isExpanded ? double.infinity : 260,
        height: _isExpanded ? 110 : 38,
        decoration: BoxDecoration(
          color: Colors.black,
          borderRadius: BorderRadius.circular(_isExpanded ? 24 : 19),
          border: Border.all(color: isPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F), width: 1.2),
          boxShadow: [
            BoxShadow(
              color: (isPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F)).withOpacity(0.25),
              blurRadius: 16,
              spreadRadius: 2,
            ),
          ],
        ),
        child: _isExpanded ? _buildExpandedHUD(isPositive) : _buildCompactHUD(isPositive),
      ),
    );
  }

  Widget _buildCompactHUD(bool isPositive) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              widget.symbol,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12),
            ),
          ],
        ),
        Text(
          '${isPositive ? '+' : ''}₹${widget.pnl.toStringAsFixed(2)}',
          style: TextStyle(
            color: isPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F),
            fontWeight: FontWeight.w900,
            fontSize: 12,
          ),
        ),
      ],
    );
  }

  Widget _buildExpandedHUD(bool isPositive) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                const Icon(Icons.flash_on, color: Color(0xFF00F0FF), size: 16),
                const SizedBox(width: 6),
                Text(
                  '${widget.symbol} • ACTIVE POSITION',
                  style: const TextStyle(color: Color(0xFF00F0FF), fontWeight: FontWeight.bold, fontSize: 12),
                ),
              ],
            ),
            Text(
              '${isPositive ? '+' : ''}₹${widget.pnl.toStringAsFixed(2)}',
              style: TextStyle(
                color: isPositive ? const Color(0xFF05FFA1) : const Color(0xFFFF2A5F),
                fontWeight: FontWeight.w900,
                fontSize: 16,
              ),
            ),
          ],
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('LTP: ₹${widget.currentPrice.toStringAsFixed(2)}', style: const TextStyle(color: Colors.white70, fontSize: 11)),
            Text('Stop Loss: ₹${widget.trailingStop.toStringAsFixed(2)} (🔒 Locked)', style: const TextStyle(color: Color(0xFFFFB800), fontSize: 11)),
          ],
        ),
        GestureDetector(
          onTap: widget.onEmergencyExit,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFFFF2A5F).withOpacity(0.2),
              borderRadius: BorderRadius.circular(6),
              border: Border.all(color: const Color(0xFFFF2A5F), width: 0.8),
            ),
            child: const Center(
              child: Text(
                'TAP TO INSTANT SQUARE OFF',
                style: TextStyle(color: Color(0xFFFF2A5F), fontWeight: FontWeight.w800, fontSize: 10, letterSpacing: 1),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
