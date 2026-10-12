import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'app/providers.dart';
import 'app/router.dart';
import 'core/theme/app_theme.dart';
import 'features/alarm/data/background_poller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Loaded before runApp so the alarm store is available synchronously — the
  // settings must be readable the instant the engine starts.
  final prefs = await SharedPreferences.getInstance();

  // Registering the Workmanager callback has to happen in the main isolate
  // before any task can be scheduled.
  await BackgroundPoller.initialise();

  runApp(
    ProviderScope(
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const NeighbourhoodWatchApp(),
    ),
  );
}

class NeighbourhoodWatchApp extends ConsumerStatefulWidget {
  const NeighbourhoodWatchApp({super.key});

  @override
  ConsumerState<NeighbourhoodWatchApp> createState() =>
      _NeighbourhoodWatchAppState();
}

class _NeighbourhoodWatchAppState extends ConsumerState<NeighbourhoodWatchApp> {
  @override
  void initState() {
    super.initState();
    unawaited(_bootstrap());
  }

  /// Wires the notification and push plumbing into the alarm engine.
  ///
  /// Everything here is best-effort: if notifications are denied or Firebase
  /// is not configured, the app still runs and still polls.
  Future<void> _bootstrap() async {
    final notifications = ref.read(notificationServiceProvider);
    await notifications.ensureInitialised();

    // Tapping an alarm notification jumps straight to the alarm screen.
    notifications.onSelected = (payload) {
      final incidentId = payload.incidentId;
      if (incidentId == null) return;

      final router = ref.read(routerProvider);
      router.push(
        payload.kind == 'alarm'
            ? '${Routes.alarm}/$incidentId'
            : Routes.incidentDetail(incidentId),
      );
    };

    final push = ref.read(pushServiceProvider);
    push.onAlarmHint = (hint) {
      // A setup check from `manage.py check_push`. Show it so the person
      // configuring push can see the message land on the handset, but never
      // alarm for it.
      if (hint.isTest) {
        unawaited(
          notifications.showInfo(
            title: hint.title ?? 'Test push',
            body: hint.body ?? 'Push delivery is working.',
          ),
        );
        return;
      }

      final incidentId = hint.incidentId;
      if (incidentId == null) return;

      // Re-fetch rather than trusting the payload, then let the normal rules
      // decide whether this actually warrants a siren.
      unawaited(_handlePushHint(incidentId));
    };
    await push.initialise();
  }

  Future<void> _handlePushHint(String incidentId) async {
    try {
      final incident =
          await ref.read(incidentsRepositoryProvider).detail(incidentId);
      final position = await ref.read(currentPositionProvider.future);

      await ref.read(alarmEngineProvider).processIncidents(
        [incident],
        userLatitude: position?.latitude,
        userLongitude: position?.longitude,
      );
    } catch (error) {
      debugPrint('Could not process pushed incident $incidentId: $error');
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Neighbourhood Watch',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.dark,
      routerConfig: ref.watch(routerProvider),
    );
  }
}
