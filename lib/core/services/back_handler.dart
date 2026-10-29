import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class BackHandlerService {
  static const _channel = MethodChannel('com.example.diabetes_app/back');
  static Future<void> Function()? _currentHandler;

  static void init() {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'onBackPressed') {
        if (_currentHandler != null) {
          await _currentHandler!();
        }
      }
    });
  }

  static void setHandler(Future<void> Function() handler) {
    _currentHandler = handler;
  }

  static void clearHandler() {
    _currentHandler = null;
  }

  static Future<void> exitApp() async {
    try {
      await _channel.invokeMethod('exitApp');
    } catch (_) {
      exit(0);
    }
  }

  static void goBack(BuildContext context) {
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
  }

  /// Tampilkan dialog konfirmasi keluar — void (tidak return bool)
  static Future<void> showExitDialog(BuildContext context) async {
    final shouldExit = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.exit_to_app, color: Colors.red),
            SizedBox(width: 8),
            Text('Keluar Aplikasi?'),
          ],
        ),
        content: const Text('Apakah Anda yakin ingin keluar dari aplikasi?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Tidak'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text(
              'Ya, Keluar',
              style: TextStyle(color: Colors.white),
            ),
          ),
        ],
      ),
    );
    if (shouldExit == true) {
      await exitApp();
    }
  }
}
