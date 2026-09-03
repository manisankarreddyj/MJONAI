import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class HapticKillSlider extends StatefulWidget {
  final VoidCallback onEmergencyKill;

  const HapticKillSlider({Key? key, required this.onEmergencyKill}) : super(key: key);

  @override
  State<HapticKillSlider> createState() => _HapticKillSliderState();
}

class _HapticKillSliderState extends State<HapticKillSlider> {
  double _dragPosition = 0.0;
  final double _maxDrag = 240.0;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: 56,
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1E0911),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: const Color(0xFFFF2A5F), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFFF2A5F).withOpacity(0.2),
            blurRadius: 12,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Stack(
        alignment: Alignment.centerLeft,
        children: [
          const Center(
            child: Text(
              'SLIDE TO EMERGENCY EXIT >>>',
              style: TextStyle(
                color: Color(0xFFFF2A5F),
                fontWeight: FontWeight.w900,
                fontSize: 13,
                letterSpacing: 2,
              ),
            ),
          ),
          Positioned(
            left: _dragPosition,
            child: GestureDetector(
              onHorizontalDragUpdate: (details) {
                setState(() {
                  _dragPosition = (_dragPosition + details.delta.dx).clamp(0.0, _maxDrag);
                });
                if (_dragPosition >= _maxDrag * 0.5) {
                  HapticFeedback.selectionClick();
                }
              },
              onHorizontalDragEnd: (details) {
                if (_dragPosition >= _maxDrag * 0.9) {
                  HapticFeedback.heavyImpact();
                  widget.onEmergencyKill();
                }
                setState(() {
                  _dragPosition = 0.0;
                });
              },
              child: Container(
                width: 50,
                height: 50,
                margin: const EdgeInsets.all(3),
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  color: Color(0xFFFF2A5F),
                  boxShadow: [
                    BoxShadow(
                      color: Color(0xFFFF2A5F),
                      blurRadius: 10,
                      spreadRadius: 1,
                    ),
                  ],
                ),
                child: const Icon(Icons.bolt, color: Colors.white, size: 28),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
