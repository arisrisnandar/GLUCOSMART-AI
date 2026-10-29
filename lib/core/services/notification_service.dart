import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter/material.dart';
import '../network/api_client.dart';
import '../network/api_endpoints.dart';

// ── Background handler (top-level, wajib) ─────────────────────────────────────
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  debugPrint('[FCM] background: ${message.notification?.title}');
}

class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  final _fcm = FirebaseMessaging.instance;
  final _localNotif = FlutterLocalNotificationsPlugin();

  static const _channelId = 'sobatgula_channel';
  static const _channelName = 'SobatGula Notifikasi';
  static const _channelDesc = 'Pengingat obat, risiko, dan edukasi';

  bool _initialized = false;

  // ── init() dipanggil sekali di main.dart — TANPA kirim token ─────────────
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    // 1. Minta izin notifikasi
    final settings = await _fcm.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    debugPrint('[FCM] permission: ${settings.authorizationStatus}');

    // 2. Setup local notifications untuk foreground
    const androidInit = AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    await _localNotif.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
      onDidReceiveNotificationResponse: _onNotifTapped,
    );

    // 3. Buat Android notification channel
    const channel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      description: _channelDesc,
      importance: Importance.high,
      playSound: true,
      enableVibration: true,
    );
    await _localNotif
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(channel);

    // 4. Background handler
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    // 5. Foreground handler
    FirebaseMessaging.onMessage.listen(_onForegroundMessage);

    // 6. Refresh token otomatis (kirim ulang ke backend jika token berubah)
    _fcm.onTokenRefresh.listen((newToken) async {
      debugPrint('[FCM] token refreshed, sending to backend...');
      await _sendTokenToBackend(newToken);
    });

    debugPrint('[FCM] NotificationService initialized ✓');
  }

  // ── Dipanggil SETELAH login / checkLogin berhasil ─────────────────────────
  Future<void> registerTokenAfterLogin() async {
    try {
      final token = await _fcm.getToken();
      debugPrint('[FCM] FCM token: ${token?.substring(0, 20)}...');
      if (token != null) {
        await _sendTokenToBackend(token);
      }
    } catch (e) {
      debugPrint('[FCM] registerTokenAfterLogin error: $e');
    }
  }

  // ── Kirim token ke backend (JWT sudah tersedia) ────────────────────────────
  Future<void> _sendTokenToBackend(String token) async {
    try {
      final response = await ApiClient().dio.post(
        ApiEndpoints.fcmToken,
        data: {'fcm_token': token},
      );
      debugPrint('[FCM] token sent to backend ✓ status=${response.statusCode}');
    } catch (e) {
      debugPrint('[FCM] _sendTokenToBackend error: $e');
    }
  }

  // ── Tampilkan notif saat app di foreground ─────────────────────────────────
  Future<void> _onForegroundMessage(RemoteMessage message) async {
    debugPrint('[FCM] foreground message: ${message.notification?.title}');
    final notif = message.notification;
    if (notif == null) return;

    await _localNotif.show(
      message.hashCode,
      notif.title,
      notif.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          _channelId,
          _channelName,
          channelDescription: _channelDesc,
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
          largeIcon: const DrawableResourceAndroidBitmap('@mipmap/ic_launcher'),
          styleInformation: BigTextStyleInformation(notif.body ?? ''),
          color: const Color(0xFF4CAF50),
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
        ),
      ),
      payload: message.data['type'],
    );
  }

  void _onNotifTapped(NotificationResponse response) {
    debugPrint('[FCM] tapped payload: ${response.payload}');
  }
}
