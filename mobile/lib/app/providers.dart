import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api/api_client.dart';
import '../core/location/location_service.dart';
import '../core/notifications/notification_service.dart';
import '../core/notifications/push_service.dart';
import '../core/storage/token_store.dart';
import '../features/alarm/data/alarm_engine.dart';
import '../features/alarm/data/alarm_settings.dart';
import '../features/alarm/data/alarm_store.dart';
import '../features/alarm/data/background_poller.dart';
import '../features/auth/data/auth_repository.dart';
import '../features/auth/data/user.dart';
import '../features/incidents/data/incident.dart';
import '../features/incidents/data/incidents_repository.dart';

// ── Infrastructure ──────────────────────────────────────────────────────────

/// Overridden in `main()` with the instance loaded before `runApp`.
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('sharedPreferencesProvider must be overridden'),
);

final tokenStoreProvider = Provider<TokenStore>((ref) => TokenStore());

final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient(tokenStore: ref.watch(tokenStoreProvider));
  // When the refresh token is rejected there is nothing left to do but sign
  // the user out; the router redirects on the resulting state change.
  client.onSessionExpired = () => ref.read(authControllerProvider.notifier).forceSignOut();
  return client;
});

final locationServiceProvider = Provider<LocationService>((ref) => LocationService());

final notificationServiceProvider = Provider<NotificationService>(
  (ref) => NotificationService(),
);

final alarmStoreProvider = Provider<AlarmStore>(
  (ref) => AlarmStore(ref.watch(sharedPreferencesProvider)),
);

final pushServiceProvider = Provider<PushService>(
  (ref) => PushService(api: ref.watch(apiClientProvider)),
);

// ── Repositories ────────────────────────────────────────────────────────────

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => AuthRepository(
    api: ref.watch(apiClientProvider),
    tokens: ref.watch(tokenStoreProvider),
  ),
);

final incidentsRepositoryProvider = Provider<IncidentsRepository>(
  (ref) => IncidentsRepository(ref.watch(apiClientProvider)),
);

// ── Auth state ──────────────────────────────────────────────────────────────

sealed class AuthState {
  const AuthState();
}

class AuthUnknown extends AuthState {
  const AuthUnknown();
}

class AuthSignedOut extends AuthState {
  const AuthSignedOut({this.message});
  final String? message;
}

class AuthSignedIn extends AuthState {
  const AuthSignedIn(this.user);
  final AppUser user;
}

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    // Kick off session restoration; the router shows a splash until it lands.
    unawaited(_restore());
    return const AuthUnknown();
  }

  Future<void> _restore() async {
    final repo = ref.read(authRepositoryProvider);
    try {
      if (!await repo.restoreSession()) {
        state = const AuthSignedOut();
        return;
      }
      final user = await repo.currentUser();
      _onSignedIn(user);
    } catch (_) {
      state = const AuthSignedOut();
    }
  }

  Future<void> signIn({required String email, required String password}) async {
    final repo = ref.read(authRepositoryProvider);
    final user = await repo.login(email: email, password: password);
    _onSignedIn(user);
  }

  /// Used after OTP verification, which may already have issued tokens.
  Future<void> completeSignIn(AppUser user) async {
    _onSignedIn(user);
  }

  Future<void> refreshUser() async {
    if (state is! AuthSignedIn) return;
    try {
      final user = await ref.read(authRepositoryProvider).currentUser();
      _onSignedIn(user);
    } catch (_) {
      // Keep the cached user; a failed refresh is not a sign-out.
    }
  }

  Future<void> signOut() async {
    await ref.read(pushServiceProvider).unregisterToken();
    await ref.read(authRepositoryProvider).logout();
    await BackgroundPoller.cancel();
    ref.read(alarmEngineProvider).stopForegroundPolling();
    state = const AuthSignedOut();
  }

  /// Called by the API client when the refresh token is rejected.
  Future<void> forceSignOut() async {
    if (state is AuthSignedOut) return;
    await ref.read(tokenStoreProvider).clear();
    ref.read(alarmEngineProvider).stopForegroundPolling();
    state = const AuthSignedOut(
      message: 'Your session expired. Please sign in again.',
    );
  }

  void _onSignedIn(AppUser user) {
    state = AuthSignedIn(user);

    final engine = ref.read(alarmEngineProvider)
      ..userNeighborhoodId = user.primaryNeighborhoodId;

    // Start every alarm delivery path now that we have a session.
    engine.startForegroundPolling();
    unawaited(BackgroundPoller.register());
    unawaited(ref.read(pushServiceProvider).registerToken());
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);

/// Convenience view of the signed-in user, or null.
final currentUserProvider = Provider<AppUser?>((ref) {
  final state = ref.watch(authControllerProvider);
  return state is AuthSignedIn ? state.user : null;
});

// ── Alarm ───────────────────────────────────────────────────────────────────

final alarmEngineProvider = Provider<AlarmEngine>((ref) {
  final engine = AlarmEngine(
    incidents: ref.watch(incidentsRepositoryProvider),
    location: ref.watch(locationServiceProvider),
    notifications: ref.watch(notificationServiceProvider),
    store: ref.watch(alarmStoreProvider),
  );
  ref.onDispose(() => unawaited(engine.dispose()));
  return engine;
});

/// The user's alarm settings, persisted to shared preferences on every change
/// so the background isolate sees them immediately.
class AlarmSettingsController extends Notifier<AlarmSettings> {
  @override
  AlarmSettings build() => ref.watch(alarmStoreProvider).readSettings();

  Future<void> update(AlarmSettings settings) async {
    state = settings;
    await ref.read(alarmStoreProvider).writeSettings(settings);

    final engine = ref.read(alarmEngineProvider);
    if (settings.enabled) {
      engine.startForegroundPolling();
      unawaited(BackgroundPoller.register());
    } else {
      engine.stopForegroundPolling();
      unawaited(BackgroundPoller.cancel());
    }
  }

  Future<void> setEnabled(bool value) => update(state.copyWith(enabled: value));

  Future<void> setRadius(int metres) => update(state.copyWith(radiusMetres: metres));

  Future<void> setMinimumSeverity(IncidentSeverity severity) =>
      update(state.copyWith(minimumSeverity: severity));

  Future<void> setQuietHoursEnabled(bool value) =>
      update(state.copyWith(quietHoursEnabled: value));

  Future<void> setQuietHours(QuietHours hours) =>
      update(state.copyWith(quietHours: hours));

  Future<void> toggleCategory(IncidentCategory category) {
    final muted = state.mutedCategories.toSet();
    if (!muted.remove(category.value)) muted.add(category.value);
    return update(state.copyWith(mutedCategories: muted));
  }

  Future<void> snooze(Duration duration) =>
      update(state.copyWith(snoozedUntil: DateTime.now().add(duration)));

  Future<void> clearSnooze() => update(state.copyWith(clearSnooze: true));

  Future<void> setIncludeUnverified(bool value) =>
      update(state.copyWith(includeUnverified: value));

  Future<void> setVibrate(bool value) => update(state.copyWith(vibrate: value));
}

final alarmSettingsProvider =
    NotifierProvider<AlarmSettingsController, AlarmSettings>(
  AlarmSettingsController.new,
);

/// The alarm currently demanding attention, if any.
final activeAlarmProvider = StreamProvider<ActiveAlarm>((ref) {
  return ref.watch(alarmEngineProvider).alarms;
});

/// Alarm history, re-read whenever [alarmHistoryRefreshProvider] is bumped.
final alarmHistoryProvider = Provider<List<AlarmHistoryEntry>>((ref) {
  ref.watch(alarmHistoryRefreshProvider);
  return ref.watch(alarmStoreProvider).readHistory();
});

/// A revision counter. The history lives in shared preferences, which the
/// background isolate writes to, so there is nothing to subscribe to —
/// bumping this is how the UI says "re-read from disk".
class AlarmHistoryRevision extends Notifier<int> {
  @override
  int build() => 0;

  void bump() => state++;
}

final alarmHistoryRefreshProvider =
    NotifierProvider<AlarmHistoryRevision, int>(AlarmHistoryRevision.new);

/// Timestamp of the most recent successful poll, for the "last checked" line.
final lastPollProvider = StreamProvider<DateTime>((ref) {
  return ref.watch(alarmEngineProvider).polls;
});

// ── Location ────────────────────────────────────────────────────────────────

final locationPermissionProvider = FutureProvider<LocationPermissionState>((ref) {
  return ref.watch(locationServiceProvider).checkPermission();
});

/// Best-known position: a live fix if possible, otherwise the cached one,
/// otherwise the user's registered home coordinates.
final currentPositionProvider =
    FutureProvider<({double latitude, double longitude})?>((ref) async {
  final location = ref.watch(locationServiceProvider);

  final position = await location.currentPosition();
  if (position != null) {
    return (latitude: position.latitude, longitude: position.longitude);
  }

  final cached = await location.cachedPosition();
  if (cached != null) {
    return (latitude: cached.latitude, longitude: cached.longitude);
  }

  final user = ref.watch(currentUserProvider);
  if (user != null && user.hasHomeLocation) {
    return (latitude: user.latitude!, longitude: user.longitude!);
  }
  return null;
});

// ── Incident feed ───────────────────────────────────────────────────────────

class IncidentFiltersController extends Notifier<IncidentFilters> {
  @override
  IncidentFilters build() => const IncidentFilters();

  void apply(IncidentFilters filters) => state = filters;

  void clear() => state = const IncidentFilters();
}

final incidentFiltersProvider =
    NotifierProvider<IncidentFiltersController, IncidentFilters>(
  IncidentFiltersController.new,
);

final incidentFeedProvider = FutureProvider<List<Incident>>((ref) async {
  final filters = ref.watch(incidentFiltersProvider);
  final page = await ref.watch(incidentsRepositoryProvider).list(filters: filters);
  return page.items;
});

final incidentDetailProvider =
    FutureProvider.family<Incident, String>((ref, id) async {
  return ref.watch(incidentsRepositoryProvider).detail(id);
});

/// Incidents inside the user's alarm radius — powers the "Near me" list and
/// the map's proximity circle.
final nearbyIncidentsProvider = FutureProvider<List<Incident>>((ref) async {
  final position = await ref.watch(currentPositionProvider.future);
  if (position == null) return const [];

  final settings = ref.watch(alarmSettingsProvider);
  return ref.watch(incidentsRepositoryProvider).nearby(
        latitude: position.latitude,
        longitude: position.longitude,
        radiusMetres: settings.radiusMetres.toDouble(),
      );
});

final heatmapProvider = FutureProvider<List<HeatmapCell>>((ref) async {
  final position = await ref.watch(currentPositionProvider.future);
  if (position == null) return const [];

  // A bounding box roughly one degree across centred on the user. Coarse on
  // purpose: the heatmap is an overview, not a precise query.
  const delta = 0.15;
  try {
    return await ref.watch(incidentsRepositoryProvider).heatmap(
          bounds: (
            minLat: position.latitude - delta,
            minLon: position.longitude - delta,
            maxLat: position.latitude + delta,
            maxLon: position.longitude + delta,
          ),
        );
  } catch (error) {
    debugPrint('Heatmap unavailable: $error');
    return const [];
  }
});
