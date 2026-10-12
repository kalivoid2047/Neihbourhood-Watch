import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../../features/incidents/data/incident.dart';

/// Notification channel ids. Android groups user-facing controls by channel,
/// so the split here is what lets someone silence chatter while keeping the
/// critical siren — without us having to police it in code.
class NotificationChannels {
  const NotificationChannels._();

  /// Full-screen, siren, bypasses Do Not Disturb where the OS allows it.
  static const criticalAlarm = 'nhw_alarm_critical';

  /// Heads-up with a short tone.
  static const importantAlert = 'nhw_alert_important';

  /// Silent, tray only.
  static const quietAlert = 'nhw_alert_quiet';

  /// Ongoing foreground-service notification during an SOS.
  static const sosOngoing = 'nhw_sos_ongoing';
}

/// Payload carried on a notification so a tap can route to the right screen.
class NotificationPayload {
  const NotificationPayload({
    required this.kind,
    this.incidentId,
    this.notificationId,
  });

  /// `alarm`, `alert`, or `sos`.
  final String kind;
  final String? incidentId;
  final String? notificationId;

  String encode() => jsonEncode({
        'kind': kind,
        'incident_id': incidentId,
        'notification_id': notificationId,
      });

  static NotificationPayload? decode(String? raw) {
    if (raw == null || raw.isEmpty) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return NotificationPayload(
        kind: map['kind'] as String? ?? 'alert',
        incidentId: map['incident_id'] as String?,
        notificationId: map['notification_id'] as String?,
      );
    } catch (_) {
      return null;
    }
  }
}

/// Wraps `flutter_local_notifications`.
///
/// Used from **both** isolates: the UI isolate for foreground alerts, and the
/// Workmanager isolate for background ones. Hence [ensureInitialised], which is
/// safe to call repeatedly.
class NotificationService {
  NotificationService({FlutterLocalNotificationsPlugin? plugin})
      : _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;

  bool _initialised = false;

  /// Invoked when the user taps a notification in the foreground isolate.
  void Function(NotificationPayload payload)? onSelected;

  FlutterLocalNotificationsPlugin get plugin => _plugin;

  Future<void> ensureInitialised() async {
    if (_initialised) return;

    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwin = DarwinInitializationSettings(
      // Permissions are requested explicitly in [requestPermissions] once the
      // user has seen the rationale screen, not silently on first launch.
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
      requestCriticalPermission: false,
    );

    await _plugin.initialize(
      settings: const InitializationSettings(android: android, iOS: darwin),
      onDidReceiveNotificationResponse: _handleResponse,
      onDidReceiveBackgroundNotificationResponse: notificationTapBackground,
    );

    await _createAndroidChannels();
    _initialised = true;
  }

  void _handleResponse(NotificationResponse response) {
    final payload = NotificationPayload.decode(response.payload);
    if (payload != null) onSelected?.call(payload);
  }

  Future<void> _createAndroidChannels() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return;

    await android.createNotificationChannel(
      const AndroidNotificationChannel(
        NotificationChannels.criticalAlarm,
        'Critical alarms',
        description:
            'Loud alarm for critical incidents reported close to you. '
            'These can sound even when your phone is silent.',
        importance: Importance.max,
        playSound: true,
        sound: RawResourceAndroidNotificationSound('alarm_siren'),
        enableVibration: true,
        enableLights: true,
      ),
    );

    await android.createNotificationChannel(
      const AndroidNotificationChannel(
        NotificationChannels.importantAlert,
        'Important alerts',
        description: 'Incidents near you that are worth knowing about now.',
        importance: Importance.high,
        playSound: true,
      ),
    );

    await android.createNotificationChannel(
      const AndroidNotificationChannel(
        NotificationChannels.quietAlert,
        'Quiet updates',
        description: 'Lower-priority incident activity in your area.',
        importance: Importance.low,
        playSound: false,
      ),
    );

    await android.createNotificationChannel(
      const AndroidNotificationChannel(
        NotificationChannels.sosOngoing,
        'Active SOS',
        description: 'Shown while your SOS is active and sharing your location.',
        importance: Importance.low,
        playSound: false,
      ),
    );
  }

  /// Asks for notification permission (Android 13+ / iOS).
  ///
  /// [critical] additionally requests the iOS Critical Alerts entitlement,
  /// which only takes effect if Apple has granted it for the app id.
  Future<bool> requestPermissions({bool critical = false}) async {
    await ensureInitialised();

    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android != null) {
      final granted = await android.requestNotificationsPermission();
      return granted ?? false;
    }

    final ios = _plugin.resolvePlatformSpecificImplementation<
        IOSFlutterLocalNotificationsPlugin>();
    if (ios != null) {
      final granted = await ios.requestPermissions(
        alert: true,
        badge: true,
        sound: true,
        critical: critical,
      );
      return granted ?? false;
    }

    return true;
  }

  /// Asks Android 14+ for permission to show a full-screen alarm over the lock
  /// screen. Without it the alarm degrades to a heads-up notification, which
  /// still makes noise but will not light up a locked phone.
  Future<bool> requestFullScreenIntentPermission() async {
    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (android == null) return true;
    return await android.requestFullScreenIntentPermission() ?? false;
  }

  // ── Showing notifications ─────────────────────────────────────────────────

  /// The loud one: full-screen intent, siren, insistent vibration, and no
  /// swipe-away — the user has to acknowledge it.
  Future<void> showCriticalAlarm(Incident incident, {double? distanceMetres}) {
    return _show(
      id: _idFor(incident.id),
      title: '${incident.severity.label}: ${incident.title}',
      body: _bodyFor(incident, distanceMetres),
      channelId: NotificationChannels.criticalAlarm,
      importance: Importance.max,
      priority: Priority.max,
      fullScreenIntent: true,
      ongoing: true,
      autoCancel: false,
      category: AndroidNotificationCategory.alarm,
      sound: const RawResourceAndroidNotificationSound('alarm_siren'),
      interruptionLevel: InterruptionLevel.critical,
      payload: NotificationPayload(kind: 'alarm', incidentId: incident.id),
      actions: const [
        AndroidNotificationAction(
          'acknowledge',
          'I am safe',
          showsUserInterface: true,
          cancelNotification: true,
        ),
        AndroidNotificationAction(
          'view',
          'View details',
          showsUserInterface: true,
        ),
      ],
    );
  }

  /// Heads-up alert with a short tone.
  Future<void> showAlert(Incident incident, {double? distanceMetres}) {
    return _show(
      id: _idFor(incident.id),
      title: incident.title,
      body: _bodyFor(incident, distanceMetres),
      channelId: NotificationChannels.importantAlert,
      importance: Importance.high,
      priority: Priority.high,
      category: AndroidNotificationCategory.event,
      interruptionLevel: InterruptionLevel.timeSensitive,
      payload: NotificationPayload(kind: 'alert', incidentId: incident.id),
    );
  }

  /// Tray-only, no sound.
  Future<void> showQuiet(Incident incident, {double? distanceMetres}) {
    return _show(
      id: _idFor(incident.id),
      title: incident.title,
      body: _bodyFor(incident, distanceMetres),
      channelId: NotificationChannels.quietAlert,
      importance: Importance.low,
      priority: Priority.low,
      playSound: false,
      category: AndroidNotificationCategory.event,
      interruptionLevel: InterruptionLevel.passive,
      payload: NotificationPayload(kind: 'alert', incidentId: incident.id),
    );
  }

  /// A plain informational notification, not tied to an incident.
  ///
  /// Used by the push setup check (`manage.py check_push --send-to …`): a test
  /// push has to be visible on the handset, otherwise "accepted by FCM" is the
  /// last thing anyone can observe and the final hop stays unverified.
  Future<void> showInfo({required String title, required String body}) {
    return _show(
      id: 990001,
      title: title,
      body: body,
      channelId: NotificationChannels.quietAlert,
      importance: Importance.defaultImportance,
      priority: Priority.defaultPriority,
      playSound: false,
      payload: const NotificationPayload(kind: 'info'),
    );
  }

  /// Batches several incidents into one line, used when the cooldown has
  /// collapsed a burst of reports.
  Future<void> showBatched(int count) {
    return _show(
      id: 424242,
      title: '$count new incidents near you',
      body: 'Several incidents were reported in your area. Tap to review them.',
      channelId: NotificationChannels.importantAlert,
      importance: Importance.high,
      priority: Priority.high,
      payload: const NotificationPayload(kind: 'alert'),
    );
  }

  Future<void> cancel(String incidentId) =>
      _plugin.cancel(id: _idFor(incidentId));

  Future<void> cancelAll() => _plugin.cancelAll();

  Future<void> _show({
    required int id,
    required String title,
    required String body,
    required String channelId,
    required NotificationPayload payload,
    Importance importance = Importance.defaultImportance,
    Priority priority = Priority.defaultPriority,
    bool fullScreenIntent = false,
    bool ongoing = false,
    bool autoCancel = true,
    bool playSound = true,
    AndroidNotificationCategory? category,
    RawResourceAndroidNotificationSound? sound,
    InterruptionLevel? interruptionLevel,
    List<AndroidNotificationAction> actions = const [],
  }) async {
    await ensureInitialised();

    final android = AndroidNotificationDetails(
      channelId,
      _channelNameFor(channelId),
      importance: importance,
      priority: priority,
      fullScreenIntent: fullScreenIntent,
      ongoing: ongoing,
      autoCancel: autoCancel,
      playSound: playSound,
      sound: sound,
      category: category,
      visibility: NotificationVisibility.public,
      styleInformation: BigTextStyleInformation(body),
      actions: actions.isEmpty ? null : actions,
    );

    final darwin = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: playSound,
      // iOS plays a sound file bundled with the app, not an asset. The file
      // must be added to the Runner target in Xcode — see docs/FIREBASE_SETUP.md.
      sound: sound != null ? 'alarm_siren.wav' : null,
      interruptionLevel: interruptionLevel,
    );

    await _plugin.show(
      id: id,
      title: title,
      body: body,
      notificationDetails: NotificationDetails(android: android, iOS: darwin),
      payload: payload.encode(),
    );
  }

  static String _channelNameFor(String channelId) => switch (channelId) {
        NotificationChannels.criticalAlarm => 'Critical alarms',
        NotificationChannels.importantAlert => 'Important alerts',
        NotificationChannels.quietAlert => 'Quiet updates',
        NotificationChannels.sosOngoing => 'Active SOS',
        _ => 'Alerts',
      };

  static String _bodyFor(Incident incident, double? distanceMetres) {
    final where = distanceMetres != null
        ? (distanceMetres < 1000
            ? '${distanceMetres.round()} m away'
            : '${(distanceMetres / 1000).toStringAsFixed(1)} km away')
        : (incident.address.isNotEmpty ? incident.address : 'nearby');
    return '${incident.category.label} reported $where.'
        '${incident.isVerified ? '' : ' Not verified yet.'}';
  }

  /// Notification ids must be 32-bit ints, but incidents are UUIDs — hash down
  /// to a stable positive int so re-showing the same incident replaces rather
  /// than stacks.
  static int _idFor(String incidentId) => incidentId.hashCode & 0x7FFFFFFF;
}

/// Entry point for notification taps that arrive while the app is not running.
/// Must be a top-level function annotated for AOT entry-point retention.
@pragma('vm:entry-point')
void notificationTapBackground(NotificationResponse response) {
  // The app is about to be launched by the tap; the foreground handler picks
  // up routing from the pending-alarm record. Nothing to do here but exist.
  debugPrint('Background notification tap: ${response.payload}');
}
