import 'package:flutter/foundation.dart';
import 'package:workmanager/workmanager.dart';

import '../../../core/api/api_client.dart';
import '../../../core/location/location_service.dart';
import '../../../core/notifications/notification_service.dart';
import '../../../core/storage/token_store.dart';
import '../../incidents/data/incidents_repository.dart';
import 'alarm_engine.dart';
import 'alarm_store.dart';

/// Registers and runs the background alarm check.
///
/// The OS gives us a cold isolate with nothing in it: no providers, no widget
/// tree, no auth state. [callbackDispatcher] therefore rebuilds a minimal
/// object graph from scratch — secure storage for the refresh token, shared
/// preferences for settings and the seen set, and a throwaway API client.
///
/// Android will not run this more often than every 15 minutes, and iOS treats
/// it as a hint. That is why push exists; this is the safety net beneath it.
class BackgroundPoller {
  const BackgroundPoller._();

  static const taskName = 'nhw.alarm.poll';
  static const uniqueName = 'nhw-alarm-poll';

  /// Android's floor for periodic work. Asking for less is silently ignored.
  static const Duration frequency = Duration(minutes: 15);

  static Future<void> initialise() async {
    await Workmanager().initialize(callbackDispatcher);
  }

  static Future<void> register() async {
    await Workmanager().registerPeriodicTask(
      uniqueName,
      taskName,
      frequency: frequency,
      existingWorkPolicy: ExistingPeriodicWorkPolicy.keep,
      constraints: Constraints(
        networkType: NetworkType.connected,
        // No battery or charging constraint: a safety alarm that waits for the
        // charger is not a safety alarm.
        requiresBatteryNotLow: false,
        requiresCharging: false,
        requiresDeviceIdle: false,
      ),
      backoffPolicy: BackoffPolicy.linear,
      backoffPolicyDelay: const Duration(minutes: 5),
    );
  }

  static Future<void> cancel() =>
      Workmanager().cancelByUniqueName(uniqueName);
}

/// Entry point for the background isolate. Must be top-level and annotated so
/// it survives tree-shaking in release builds.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    if (task != BackgroundPoller.taskName) return true;

    try {
      final tokens = TokenStore();

      // Without a session there is nothing to poll for — the user is signed
      // out, so return true to keep the periodic task scheduled for when they
      // sign back in.
      if (!await tokens.hasSession()) return true;

      final api = ApiClient(tokenStore: tokens);
      final store = await AlarmStore.open();
      final settings = store.readSettings();
      if (!settings.enabled) return true;

      final notifications = NotificationService();
      await notifications.ensureInitialised();

      final engine = AlarmEngine(
        incidents: IncidentsRepository(api),
        location: LocationService(),
        notifications: notifications,
        store: store,
      );

      await engine.pollNow();
      return true;
    } catch (error, stack) {
      debugPrint('Background alarm poll failed: $error\n$stack');
      // Returning false asks Workmanager to retry with backoff.
      return false;
    }
  });
}
