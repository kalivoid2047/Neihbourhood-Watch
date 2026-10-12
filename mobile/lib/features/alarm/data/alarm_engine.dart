import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../core/location/location_service.dart';
import '../../../core/notifications/notification_service.dart';
import '../../incidents/data/incident.dart';
import '../../incidents/data/incidents_repository.dart';
import 'alarm_audio.dart';
import 'alarm_rules.dart';
import 'alarm_settings.dart';
import 'alarm_store.dart';

/// An alarm that has fired and is waiting for the user to acknowledge it.
class ActiveAlarm {
  const ActiveAlarm({
    required this.incident,
    required this.firedAt,
    this.distanceMetres,
  });

  final Incident incident;
  final DateTime firedAt;
  final double? distanceMetres;
}

/// The core of the feature: decides what to do about incidents, and does it.
///
/// It is deliberately unaware of *how* an incident arrived. Push, foreground
/// poll and background poll all funnel into [processIncidents], so the rules,
/// the dedupe and the cooldown apply identically no matter the source. That is
/// what stops a push and a poll from double-alarming for one incident.
class AlarmEngine {
  AlarmEngine({
    required IncidentsRepository incidents,
    required LocationService location,
    required NotificationService notifications,
    required AlarmStore store,
    AlarmAudio? audio,
  })  : _incidents = incidents,
        _location = location,
        _notifications = notifications,
        _store = store,
        _audio = audio ?? AlarmAudio();

  final IncidentsRepository _incidents;
  final LocationService _location;
  final NotificationService _notifications;
  final AlarmStore _store;
  final AlarmAudio _audio;

  Timer? _pollTimer;

  /// Emits when an alarm fires, so the UI can throw up the full-screen alarm.
  final _activeAlarmController = StreamController<ActiveAlarm>.broadcast();

  /// Emits after every poll, so the UI can show "last checked" state.
  final _pollController = StreamController<DateTime>.broadcast();

  Stream<ActiveAlarm> get alarms => _activeAlarmController.stream;
  Stream<DateTime> get polls => _pollController.stream;

  ActiveAlarm? _activeAlarm;
  ActiveAlarm? get activeAlarm => _activeAlarm;

  bool _polling = false;

  /// The user's primary neighbourhood, used as a fallback when there is no
  /// location fix. Set by the auth layer once the profile loads.
  String? userNeighborhoodId;

  // ── Polling lifecycle ─────────────────────────────────────────────────────

  /// Starts the foreground poll loop. Safe to call repeatedly; the interval is
  /// re-read from settings each time.
  void startForegroundPolling() {
    stopForegroundPolling();
    final settings = _store.readSettings();
    if (!settings.enabled) return;

    final interval = Duration(seconds: settings.pollIntervalSeconds.clamp(30, 600));
    _pollTimer = Timer.periodic(interval, (_) => unawaited(pollNow()));
    unawaited(pollNow());
  }

  void stopForegroundPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  /// One poll cycle: get a position, ask the backend what is nearby, evaluate.
  ///
  /// Returns the number of incidents that produced an audible alarm.
  Future<int> pollNow() async {
    if (_polling) return 0;
    _polling = true;

    try {
      await _store.reload();
      final settings = _store.readSettings();
      if (!settings.enabled) return 0;

      final position = await _resolvePosition();
      if (position == null) {
        debugPrint('AlarmEngine: no position available, skipping poll');
        return 0;
      }

      final incidents = await _incidents.nearby(
        latitude: position.latitude,
        longitude: position.longitude,
        radiusMetres: settings.radiusMetres.toDouble(),
      );

      final fired = await processIncidents(
        incidents,
        userLatitude: position.latitude,
        userLongitude: position.longitude,
      );

      final now = DateTime.now();
      await _store.writeLastPollAt(now);
      _pollController.add(now);
      return fired;
    } catch (error) {
      // A failed poll is normal — offline, server restarting, token refresh in
      // flight. The next tick tries again; we must never crash the loop.
      debugPrint('AlarmEngine: poll failed — $error');
      return 0;
    } finally {
      _polling = false;
    }
  }

  /// Runs the rules over [incidents] and acts on the results.
  ///
  /// Shared by every delivery path. Returns how many alarms sounded.
  Future<int> processIncidents(
    List<Incident> incidents, {
    double? userLatitude,
    double? userLongitude,
  }) async {
    if (incidents.isEmpty) return 0;

    final settings = _store.readSettings();
    final now = DateTime.now();
    var lastAlarmAt = _store.readLastAlarmAt();
    var alarmed = 0;
    var quietlyNotified = 0;

    // Most severe first, so that when the cooldown allows only one siren it is
    // for the worst thing happening, not merely the first one in the list.
    final ordered = incidents.toList()
      ..sort((a, b) {
        final bySeverity = b.severity.rank.compareTo(a.severity.rank);
        return bySeverity != 0
            ? bySeverity
            : b.occurredAt.compareTo(a.occurredAt);
      });

    for (final incident in ordered) {
      final evaluation = AlarmRules.evaluate(
        incident: incident,
        settings: settings,
        now: now,
        userLatitude: userLatitude,
        userLongitude: userLongitude,
        userNeighborhoodId: userNeighborhoodId,
        alreadySeen: _store.hasSeen(incident.id),
        lastAlarmAt: lastAlarmAt,
      );

      if (evaluation.decision == AlarmDecision.ignore) {
        // Still mark it seen when it was merely out of range, so moving around
        // later does not replay old incidents as new alarms.
        if (evaluation.reason != AlarmReason.alreadySeen) {
          await _store.markSeen(incident.id);
        }
        continue;
      }

      await _store.markSeen(incident.id);
      await _store.addHistory(
        AlarmHistoryEntry.from(incident, evaluation, now),
      );

      if (evaluation.shouldAlarm) {
        await _raiseAlarm(incident, evaluation, settings);
        lastAlarmAt = now;
        await _store.writeLastAlarmAt(now);
        alarmed++;
      } else {
        quietlyNotified++;
        await _notifyQuietly(incident, evaluation, settings);
      }
    }

    // Collapse a burst into one line rather than a stack of tray entries.
    if (quietlyNotified > 3) {
      await _notifications.showBatched(quietlyNotified);
    }

    return alarmed;
  }

  Future<void> _raiseAlarm(
    Incident incident,
    AlarmEvaluation evaluation,
    AlarmSettings settings,
  ) async {
    await _notifications.showCriticalAlarm(
      incident,
      distanceMetres: evaluation.distanceMetres,
    );

    _activeAlarm = ActiveAlarm(
      incident: incident,
      firedAt: DateTime.now(),
      distanceMetres: evaluation.distanceMetres,
    );

    // The background isolate has no UI to push a route onto, so it parks the
    // id; the foreground picks it up on resume or on notification tap.
    await _store.setPendingAlarm(incident.id);

    if (_activeAlarmController.hasListener) {
      _activeAlarmController.add(_activeAlarm!);
      // The UI owns the siren when it is listening, so it can stop it the
      // moment the user acknowledges.
      return;
    }

    await _audio.startSiren(vibrate: settings.vibrate);
  }

  Future<void> _notifyQuietly(
    Incident incident,
    AlarmEvaluation evaluation,
    AlarmSettings settings,
  ) async {
    // "Quiet" still distinguishes urgency: something that only missed the
    // siren because of a cooldown deserves a heads-up, while low-severity
    // chatter goes to the tray.
    final isUrgent = incident.severity.rank >= settings.minimumSeverity.rank;
    if (isUrgent) {
      await _notifications.showAlert(
        incident,
        distanceMetres: evaluation.distanceMetres,
      );
    } else {
      await _notifications.showQuiet(
        incident,
        distanceMetres: evaluation.distanceMetres,
      );
    }
  }

  // ── Alarm interaction ─────────────────────────────────────────────────────

  /// Starts the siren for an alarm the UI is displaying.
  Future<void> startSiren() async {
    final settings = _store.readSettings();
    await _audio.startSiren(vibrate: settings.vibrate);
  }

  /// The user has seen it. Stop the noise, clear the notification, record it.
  Future<void> acknowledge(String incidentId) async {
    await _audio.stop();
    await _notifications.cancel(incidentId);
    await _store.acknowledge(incidentId, DateTime.now());
    await _store.clearPendingAlarm();
    _activeAlarm = null;
  }

  /// An alarm raised while the app was closed, waiting to be shown.
  Future<Incident?> takePendingAlarm() async {
    await _store.reload();
    final id = _store.readPendingAlarm();
    if (id == null) return null;

    try {
      final incident = await _incidents.detail(id);
      return incident;
    } catch (error) {
      debugPrint('AlarmEngine: could not load pending alarm $id — $error');
      await _store.clearPendingAlarm();
      return null;
    }
  }

  /// Fires the siren on demand so the user can check their volume.
  Future<void> testAlarm() => _audio.playTestTone();

  Future<void> stopSiren() => _audio.stop();

  // ── Helpers ───────────────────────────────────────────────────────────────

  Future<({double latitude, double longitude})?> _resolvePosition() async {
    final position = await _location.currentPosition();
    if (position != null) {
      return (latitude: position.latitude, longitude: position.longitude);
    }

    final cached = await _location.cachedPosition();
    if (cached != null) {
      return (latitude: cached.latitude, longitude: cached.longitude);
    }
    return null;
  }

  Future<void> dispose() async {
    stopForegroundPolling();
    await _audio.dispose();
    await _activeAlarmController.close();
    await _pollController.close();
  }
}
