import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

class MjonaiApiClient {
  final String baseUrl;
  final String wsUrl;
  WebSocketChannel? _channel;
  final _telemetryController = StreamController<Map<String, dynamic>>.broadcast();

  MjonaiApiClient({
    this.baseUrl = 'http://127.0.0.1:8787',
    this.wsUrl = 'ws://127.0.0.1:8787/ws/stream',
  });

  Stream<Map<String, dynamic>> get telemetryStream => _telemetryController.stream;

  void connectWebSocket() {
    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _channel!.stream.listen((message) {
        final data = jsonDecode(message);
        if (data is Map<String, dynamic>) {
          _telemetryController.add(data);
        }
      }, onError: (err) {
        Future.delayed(const Duration(seconds: 3), connectWebSocket);
      }, onDone: () {
        Future.delayed(const Duration(seconds: 3), connectWebSocket);
      });
    } catch (_) {
      Future.delayed(const Duration(seconds: 3), connectWebSocket);
    }
  }

  Future<Map<String, dynamic>> triggerEmergencyKill() async {
    final response = await http.post(Uri.parse('$baseUrl/api/v1/control/kill-all'));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> closeTrade(String tradeId) async {
    final response = await http.post(Uri.parse('$baseUrl/api/v1/control/trade/$tradeId/close'));
    return jsonDecode(response.body);
  }

  Future<Map<String, dynamic>> triggerScan() async {
    final response = await http.post(Uri.parse('$baseUrl/api/v1/control/scanner/trigger'));
    return jsonDecode(response.body);
  }

  void dispose() {
    _channel?.sink.close();
    _telemetryController.close();
  }
}
