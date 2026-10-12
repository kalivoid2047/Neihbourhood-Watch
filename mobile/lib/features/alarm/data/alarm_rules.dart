import 'dart:math' as math;

import '../../incidents/data/incident.dart';
import 'alarm_settings.dart';

/// What the app should do about an incident it has just learned about.
enum AlarmDecision {
  /// Sound the siren and show the full-screen alarm.
  alarm,

  /// Post a heads-up notification, no sound.
  notifySilently,

  /// Do nothing — out of range, muted, already seen, or below threshold.
  ignore,
}

/// Why the engine decided what it decided. Surfaced in alarm history and in
/// the debug panel, so a user asking "why didn't it alarm?" gets an answer.
enum AlarmReason {
  alarmed,
  alreadySeen,
  alarmsDisabled,
  outOfRange,
  belowThreshold,
  categoryMuted,
  quietHours,
  snoozed,
  cooldown,
  unverified,
  tooOld,
}

class AlarmEvaluation {
  const AlarmEvaluation(this.decision, this.reason, {this.distanceMetres});

  final AlarmDecision decision;
  final AlarmReason reason;
  final double? distanceMetres;

  bool get shouldAlarm => decision == AlarmDecision.alarm;
  bool get shouldNotify => decision != AlarmDecision.ignore;

  String get explanation => switch (reason) {
        AlarmReason.alarmed => 'Alarm raised',
        AlarmReason.alreadySeen => 'Already seen',
        AlarmReason.alarmsDisabled => 'Alarms are switched off',
        AlarmReason.outOfRange => 'Outside your alarm radius',
        AlarmReason.belowThreshold => 'Below your severity threshold',
        AlarmReason.categoryMuted => 'This category is muted',
        AlarmReason.quietHours => 'Quiet hours',
        AlarmReason.snoozed => 'Alarms snoozed',
        AlarmReason.cooldown => 'Another alarm sounded moments ago',
        AlarmReason.unverified => 'Not verified yet',
        AlarmReason.tooOld => 'Reported too long ago',
      };
}

/// The alarm decision logic, deliberately pure: no plugins, no I/O, no clock
/// of its own. Everything it needs is passed in, which is what makes the whole
/// rule matrix unit-testable without a device.
class AlarmRules {
  const AlarmRules._();

  /// Minimum gap between two audible alarms. Without this, a cluster of
  /// reports about one event turns into a siren that never stops.
  static const Duration cooldown = Duration(seconds: 90);

  /// Incidents older than this never alarm, however they arrive. Protects
  /// against a backlog replaying as a wall of sirens after time offline.
  static const Duration maxAge = Duration(hours: 6);

  /// Decides what to do about [incident].
  ///
  /// [userLatitude]/[userLongitude] are the user's last known position, or
  /// null if location is unavailable — in which case distance cannot be
  /// checked and we fall back to neighbourhood membership.
  static AlarmEvaluation evaluate({
    required Incident incident,
    required AlarmSettings settings,
    required DateTime now,
    double? userLatitude,
    double? userLongitude,
    String? userNeighborhoodId,
    bool alreadySeen = false,
    DateTime? lastAlarmAt,
  }) {
    if (alreadySeen) {
      return const AlarmEvaluation(AlarmDecision.ignore, AlarmReason.alreadySeen);
    }

    if (!settings.enabled) {
      return const AlarmEvaluation(AlarmDecision.ignore, AlarmReason.alarmsDisabled);
    }

    // Distance first: an incident on the other side of the city is not this
    // user's business regardless of how severe it is.
    final distance = (userLatitude != null && userLongitude != null)
        ? distanceMetres(
            userLatitude,
            userLongitude,
            incident.latitude,
            incident.longitude,
          )
        : null;

    final inNeighborhood = userNeighborhoodId != null &&
        incident.neighborhoodId != null &&
        userNeighborhoodId == incident.neighborhoodId;

    final inRange = switch (distance) {
      final d? => d <= settings.radiusMetres,
      // No fix available — fall back to membership so the alarm still works
      // with location permission denied.
      _ => inNeighborhood,
    };

    if (!inRange && !inNeighborhood) {
      return AlarmEvaluation(
        AlarmDecision.ignore,
        AlarmReason.outOfRange,
        distanceMetres: distance,
      );
    }

    if (now.difference(incident.occurredAt) > maxAge) {
      return AlarmEvaluation(
        AlarmDecision.ignore,
        AlarmReason.tooOld,
        distanceMetres: distance,
      );
    }

    if (settings.mutedCategories.contains(incident.category.value)) {
      return AlarmEvaluation(
        AlarmDecision.ignore,
        AlarmReason.categoryMuted,
        distanceMetres: distance,
      );
    }

    // From here the incident is relevant — the only question is whether it
    // makes a noise. Everything below downgrades to a silent notification
    // rather than dropping the incident entirely.
    final isCritical = incident.severity == IncidentSeverity.red;

    if (incident.severity.rank < settings.minimumSeverity.rank) {
      return AlarmEvaluation(
        AlarmDecision.notifySilently,
        AlarmReason.belowThreshold,
        distanceMetres: distance,
      );
    }

    if (!settings.includeUnverified && !incident.isVerified && !isCritical) {
      return AlarmEvaluation(
        AlarmDecision.notifySilently,
        AlarmReason.unverified,
        distanceMetres: distance,
      );
    }

    // Critical incidents break through quiet hours and snooze — that override
    // is the difference between a safety app and a news feed.
    final bypass = isCritical && settings.criticalBypassesQuietHours;

    if (!bypass && settings.isSnoozedAt(now)) {
      return AlarmEvaluation(
        AlarmDecision.notifySilently,
        AlarmReason.snoozed,
        distanceMetres: distance,
      );
    }

    if (!bypass && settings.quietHoursEnabled) {
      final minuteOfDay = now.hour * 60 + now.minute;
      if (settings.quietHours.contains(minuteOfDay)) {
        return AlarmEvaluation(
          AlarmDecision.notifySilently,
          AlarmReason.quietHours,
          distanceMetres: distance,
        );
      }
    }

    if (lastAlarmAt != null && now.difference(lastAlarmAt) < cooldown) {
      return AlarmEvaluation(
        AlarmDecision.notifySilently,
        AlarmReason.cooldown,
        distanceMetres: distance,
      );
    }

    return AlarmEvaluation(
      AlarmDecision.alarm,
      AlarmReason.alarmed,
      distanceMetres: distance,
    );
  }

  /// Great-circle distance in metres (haversine).
  ///
  /// This mirrors `IncidentGeospatialService` on the backend so the client and
  /// server agree on what "within 5 km" means.
  static double distanceMetres(
    double lat1,
    double lon1,
    double lat2,
    double lon2,
  ) {
    const earthRadius = 6371000.0;
    final dLat = _toRadians(lat2 - lat1);
    final dLon = _toRadians(lon2 - lon1);
    final a = math.pow(math.sin(dLat / 2), 2) +
        math.cos(_toRadians(lat1)) *
            math.cos(_toRadians(lat2)) *
            math.pow(math.sin(dLon / 2), 2);
    return earthRadius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
  }

  static double _toRadians(double degrees) => degrees * math.pi / 180.0;
}
