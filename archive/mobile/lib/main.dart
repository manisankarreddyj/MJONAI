import 'package:flutter/material.dart';
import 'screens/tactical_cockpit.dart';
import 'services/mjonai_api_client.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final client = MjonaiApiClient();
  client.connectWebSocket();

  runApp(MjonaiMobileApp(client: client));
}

class MjonaiMobileApp extends StatelessWidget {
  final MjonaiApiClient client;

  const MjonaiMobileApp({Key? key, required this.client}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MJONAI Mobile Commander',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF030712),
      ),
      home: TacticalCockpitScreen(client: client),
    );
  }
}
