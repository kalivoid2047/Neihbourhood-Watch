import 'package:flutter_test/flutter_test.dart';
import 'package:nhw_mobile/features/alarm/data/alarm_rules.dart';
import 'package:nhw_mobile/features/alarm/data/alarm_settings.dart';
import 'package:nhw_mobile/features/incidents/data/incident.dart';

/// Reference point: Cape Town city centre.
const _userLat = -33.9249;
const _userLon = 18.4241;

/// A point roughly 1.1 km north of the reference point.
const _nearLat = -33.9150;
const _nearLon = 18.4241;

/// Roughly 33 km away — well outside any allowed radius.
const _farLat = -34.2200;
const _farLon = 18.4241;

Incident _incident({
  String id = 'incident-1',
  IncidentSeverity severity = IncidentSeverity.yellow,
  IncidentCategory category = IncidentCategory.burglary,
  double latitude = _nearLat,
  double longitude = _nearLon,
  DateTime? occurredAt,
  DateTime? verifiedAt,
  String? neighborhoodId,
}) {
  return Incident(
    id: id,
    title: 'Test incident',
    category: category,
    severity: severity,
    status: IncidentStatus.pending,
    latitude: latitude,
    longitude: longitude,
    occurredAt: occurredAt ?? DateTime(2026, 9, 22, 12, 0),
    verifiedAt: verifiedAt,
    neighborhoodId: neighborhoodId,
  );
}

/// Fixed "now", so tests never depend on the wall clock.
final _now = DateTime(2026, 9, 22, 12, 5);

AlarmEvaluation _evaluate({
  required Incident incident,
  AlarmSettings settings = const AlarmSettings(),
  DateTime? now,
  double? userLatitude = _userLat,
  double? userLongitude = _userLon,
  String? userNeighborhoodId,
  bool alreadySeen = false,
  DateTime? lastAlarmAt,
}) {
  return AlarmRules.evaluate(
    incident: incident,
    settings: settings,
    now: now ?? _now,
    userLatitude: userLatitude,
    userLongitude: userLongitude,
    userNeighborhoodId: userNeighborhoodId,
    alreadySeen: alreadySeen,
    lastAlarmAt: lastAlarmAt,
  );
}

void main() {
  group('distance', () {
    test('haversine matches a known separation', () {
      final metres = AlarmRules.distanceMetres(
        _userLat,
        _userLon,
        _nearLat,
        _nearLon,
      );
      // ~1.1 km due north; allow a wide tolerance for the earth-radius model.
      expect(metres, greaterThan(1000));
      expect(metres, lessThan(1200));
    });

    test('identical points are zero metres apart', () {
      expect(
        AlarmRules.distanceMetres(_userLat, _userLon, _userLat, _userLon),
        closeTo(0, 0.001),
      );
    });
  });

  group('proximity', () {
    test('alarms for an incident inside the radius', () {
      final result = _evaluate(incident: _incident());
      expect(result.decision, AlarmDecision.alarm);
      expect(result.reason, AlarmReason.alarmed);
    });

    test('ignores an incident outside the radius', () {
      final result = _evaluate(
        incident: _incident(latitude: _farLat, longitude: _farLon),
      );
      expect(result.decision, AlarmDecision.ignore);
      expect(result.reason, AlarmReason.outOfRange);
    });

    test('a tightened radius excludes a previously-alarming incident', () {
      final result = _evaluate(
        incident: _incident(),
        settings: const AlarmSettings(radiusMetres: 500),
      );
      expect(result.reason, AlarmReason.outOfRange);
    });

    test('falls back to neighbourhood membership with no location fix', () {
      final result = _evaluate(
        incident: _incident(
          latitude: _farLat,
          longitude: _farLon,
          neighborhoodId: 'hood-1',
        ),
        userLatitude: null,
        userLongitude: null,
        userNeighborhoodId: 'hood-1',
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('a far incident in the user neighbourhood still alarms', () {
      // Membership is a union with the radius, not an intersection: a large
      // neighbourhood should not be silently clipped by the radius setting.
      final result = _evaluate(
        incident: _incident(
          latitude: _farLat,
          longitude: _farLon,
          neighborhoodId: 'hood-1',
        ),
        userNeighborhoodId: 'hood-1',
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('no location and no membership cannot alarm', () {
      final result = _evaluate(
        incident: _incident(),
        userLatitude: null,
        userLongitude: null,
      );
      expect(result.reason, AlarmReason.outOfRange);
    });
  });

  group('severity threshold', () {
    test('below the threshold notifies silently rather than dropping', () {
      final result = _evaluate(
        incident: _incident(severity: IncidentSeverity.green),
      );
      expect(result.decision, AlarmDecision.notifySilently);
      expect(result.reason, AlarmReason.belowThreshold);
      expect(result.shouldNotify, isTrue);
    });

    test('at the threshold alarms', () {
      final result = _evaluate(
        incident: _incident(severity: IncidentSeverity.yellow),
        settings: const AlarmSettings(minimumSeverity: IncidentSeverity.yellow),
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('a critical-only threshold silences an important incident', () {
      final result = _evaluate(
        incident: _incident(severity: IncidentSeverity.yellow),
        settings: const AlarmSettings(minimumSeverity: IncidentSeverity.red),
      );
      expect(result.reason, AlarmReason.belowThreshold);
    });
  });

  group('dedupe and cooldown', () {
    test('an already-seen incident is ignored', () {
      final result = _evaluate(incident: _incident(), alreadySeen: true);
      expect(result.decision, AlarmDecision.ignore);
      expect(result.reason, AlarmReason.alreadySeen);
    });

    test('a second alarm inside the cooldown downgrades to silent', () {
      final result = _evaluate(
        incident: _incident(),
        lastAlarmAt: _now.subtract(const Duration(seconds: 30)),
      );
      expect(result.decision, AlarmDecision.notifySilently);
      expect(result.reason, AlarmReason.cooldown);
    });

    test('an alarm after the cooldown sounds again', () {
      final result = _evaluate(
        incident: _incident(),
        lastAlarmAt: _now.subtract(const Duration(minutes: 5)),
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('an old incident never alarms', () {
      final result = _evaluate(
        incident: _incident(
          occurredAt: _now.subtract(const Duration(hours: 9)),
        ),
      );
      expect(result.decision, AlarmDecision.ignore);
      expect(result.reason, AlarmReason.tooOld);
    });
  });

  group('quiet hours', () {
    const quietSettings = AlarmSettings(
      quietHoursEnabled: true,
      quietHours: QuietHours(startMinute: 22 * 60, endMinute: 6 * 60),
    );

    test('silences a non-critical incident at 2 a.m.', () {
      final night = DateTime(2026, 9, 22, 2, 0);
      final result = _evaluate(
        // The occurrence time has to track the overridden clock, or the
        // incident is rejected as stale before quiet hours are even consulted.
        incident: _incident(
          occurredAt: night.subtract(const Duration(minutes: 2)),
        ),
        settings: quietSettings,
        now: night,
      );
      expect(result.decision, AlarmDecision.notifySilently);
      expect(result.reason, AlarmReason.quietHours);
    });

    test('critical breaks through quiet hours', () {
      final night = DateTime(2026, 9, 22, 2, 0);
      final result = _evaluate(
        incident: _incident(
          severity: IncidentSeverity.red,
          occurredAt: night.subtract(const Duration(minutes: 2)),
        ),
        settings: quietSettings,
        now: night,
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('critical is silenced when the bypass is turned off', () {
      final night = DateTime(2026, 9, 22, 2, 0);
      final result = _evaluate(
        incident: _incident(
          severity: IncidentSeverity.red,
          occurredAt: night.subtract(const Duration(minutes: 2)),
        ),
        settings: const AlarmSettings(
          quietHoursEnabled: true,
          quietHours: QuietHours(startMinute: 22 * 60, endMinute: 6 * 60),
          criticalBypassesQuietHours: false,
        ),
        now: night,
      );
      expect(result.reason, AlarmReason.quietHours);
    });

    test('outside the quiet window the alarm sounds normally', () {
      final noon = DateTime(2026, 9, 22, 12, 5);
      final result = _evaluate(
        incident: _incident(occurredAt: noon.subtract(const Duration(minutes: 2))),
        settings: quietSettings,
        now: noon,
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('a window wrapping midnight contains times on both sides', () {
      const window = QuietHours(startMinute: 22 * 60, endMinute: 6 * 60);
      expect(window.contains(23 * 60), isTrue);
      expect(window.contains(2 * 60), isTrue);
      expect(window.contains(12 * 60), isFalse);
      expect(window.contains(6 * 60), isFalse);
    });
  });

  group('snooze', () {
    test('snoozing silences a normal incident', () {
      final result = _evaluate(
        incident: _incident(),
        settings: AlarmSettings(
          snoozedUntil: _now.add(const Duration(hours: 1)),
        ),
      );
      expect(result.decision, AlarmDecision.notifySilently);
      expect(result.reason, AlarmReason.snoozed);
    });

    test('critical breaks through a snooze', () {
      final result = _evaluate(
        incident: _incident(severity: IncidentSeverity.red),
        settings: AlarmSettings(
          snoozedUntil: _now.add(const Duration(hours: 1)),
        ),
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('an expired snooze has no effect', () {
      final result = _evaluate(
        incident: _incident(),
        settings: AlarmSettings(
          snoozedUntil: _now.subtract(const Duration(hours: 1)),
        ),
      );
      expect(result.decision, AlarmDecision.alarm);
    });
  });

  group('muting and verification', () {
    test('a muted category is ignored entirely', () {
      final result = _evaluate(
        incident: _incident(category: IncidentCategory.vandalism),
        settings: const AlarmSettings(mutedCategories: {'vandalism'}),
      );
      expect(result.decision, AlarmDecision.ignore);
      expect(result.reason, AlarmReason.categoryMuted);
    });

    test('a muted category is ignored even when critical', () {
      // Muting is an explicit user choice about a whole class of incident, so
      // unlike quiet hours it is not overridden by severity.
      final result = _evaluate(
        incident: _incident(
          category: IncidentCategory.vandalism,
          severity: IncidentSeverity.red,
        ),
        settings: const AlarmSettings(mutedCategories: {'vandalism'}),
      );
      expect(result.reason, AlarmReason.categoryMuted);
    });

    test('unverified incidents are silenced when the user asks for that', () {
      final result = _evaluate(
        incident: _incident(),
        settings: const AlarmSettings(includeUnverified: false),
      );
      expect(result.decision, AlarmDecision.notifySilently);
      expect(result.reason, AlarmReason.unverified);
    });

    test('critical alarms even when unverified reports are excluded', () {
      final result = _evaluate(
        incident: _incident(severity: IncidentSeverity.red),
        settings: const AlarmSettings(includeUnverified: false),
      );
      expect(result.decision, AlarmDecision.alarm);
    });

    test('a verified incident alarms when unverified ones are excluded', () {
      final result = _evaluate(
        incident: _incident(verifiedAt: _now),
        settings: const AlarmSettings(includeUnverified: false),
      );
      expect(result.decision, AlarmDecision.alarm);
    });
  });

  group('master switch', () {
    test('disabled alarms ignore everything, including critical', () {
      final result = _evaluate(
        incident: _incident(severity: IncidentSeverity.red),
        settings: const AlarmSettings(enabled: false),
      );
      expect(result.decision, AlarmDecision.ignore);
      expect(result.reason, AlarmReason.alarmsDisabled);
    });
  });

  group('settings serialisation', () {
    test('round-trips through JSON', () {
      final settings = AlarmSettings(
        radiusMetres: 1500,
        minimumSeverity: IncidentSeverity.red,
        quietHoursEnabled: true,
        quietHours: const QuietHours(startMinute: 1320, endMinute: 420),
        mutedCategories: const {'theft', 'vandalism'},
        snoozedUntil: DateTime(2026, 9, 22, 18, 30),
        includeUnverified: false,
      );

      final restored = AlarmSettings.decode(settings.encode());

      expect(restored.radiusMetres, 1500);
      expect(restored.minimumSeverity, IncidentSeverity.red);
      expect(restored.quietHoursEnabled, isTrue);
      expect(restored.quietHours.startMinute, 1320);
      expect(restored.mutedCategories, {'theft', 'vandalism'});
      expect(restored.snoozedUntil, DateTime(2026, 9, 22, 18, 30));
      expect(restored.includeUnverified, isFalse);
    });

    test('corrupt stored settings fall back to defaults', () {
      final restored = AlarmSettings.decode('not json at all');
      expect(restored.enabled, isTrue);
      expect(restored.radiusMetres, AlarmSettings.defaultRadiusMetres);
    });
  });
}
