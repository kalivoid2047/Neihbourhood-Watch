import 'dart:convert';

import '../../incidents/data/incident.dart';

/// A time of day expressed in minutes from midnight, for quiet hours.
class QuietHours {
  const QuietHours({required this.startMinute, required this.endMinute});

  /// Default quiet window: 22:00 → 06:00.
  static const disabledDefault = QuietHours(startMinute: 22 * 60, endMinute: 6 * 60);

  final int startMinute;
  final int endMinute;

  /// True when [minuteOfDay] falls inside the window, handling windows that
  /// wrap past midnight (e.g. 22:00 → 06:00).
  bool contains(int minuteOfDay) {
    if (startMinute == endMinute) return false;
    if (startMinute < endMinute) {
      return minuteOfDay >= startMinute && minuteOfDay < endMinute;
    }
    return minuteOfDay >= startMinute || minuteOfDay < endMinute;
  }

  String get label => '${_fmt(startMinute)} – ${_fmt(endMinute)}';

  static String _fmt(int minutes) {
    final h = (minutes ~/ 60).toString().padLeft(2, '0');
    final m = (minutes % 60).toString().padLeft(2, '0');
    return '$h:$m';
  }

  Map<String, dynamic> toJson() => {'start': startMinute, 'end': endMinute};

  factory QuietHours.fromJson(Map<String, dynamic> json) => QuietHours(
        startMinute: (json['start'] as num?)?.toInt() ?? 22 * 60,
        endMinute: (json['end'] as num?)?.toInt() ?? 6 * 60,
      );
}

/// Everything the user can tune about the alarm.
class AlarmSettings {
  const AlarmSettings({
    this.enabled = true,
    this.radiusMetres = defaultRadiusMetres,
    this.minimumSeverity = IncidentSeverity.yellow,
    this.quietHoursEnabled = false,
    this.quietHours = QuietHours.disabledDefault,
    this.criticalBypassesQuietHours = true,
    this.mutedCategories = const {},
    this.snoozedUntil,
    this.pollIntervalSeconds = 60,
    this.includeUnverified = true,
    this.vibrate = true,
  });

  /// Matches `Neighborhood.alert_radius_m`'s default on the backend.
  static const int defaultRadiusMetres = 5000;
  static const int minRadiusMetres = 250;

  /// The backend caps `/api/incidents/nearby/` at 50 km; we stop well short of
  /// that because anything beyond 20 km is not "your area" in any useful sense.
  static const int maxRadiusMetres = 20000;

  final bool enabled;
  final int radiusMetres;

  /// Incidents below this severity notify silently instead of alarming.
  final IncidentSeverity minimumSeverity;

  final bool quietHoursEnabled;
  final QuietHours quietHours;

  /// When true, `red` (Critical) incidents alarm even during quiet hours.
  /// This is the whole point of a safety app, so it defaults on.
  final bool criticalBypassesQuietHours;

  /// Category values the user never wants to be alarmed about.
  final Set<String> mutedCategories;

  /// While set and in the future, audible alarms are suppressed.
  final DateTime? snoozedUntil;

  final int pollIntervalSeconds;

  /// Whether to alarm on incidents that a coordinator has not verified yet.
  /// Turning this off trades speed for fewer false alarms.
  final bool includeUnverified;

  final bool vibrate;

  /// Whether the snooze is active at [now].
  ///
  /// The rule engine passes its own clock so that alarm decisions stay a pure
  /// function of their inputs — testable, and immune to the device clock
  /// shifting under a long-running poll.
  bool isSnoozedAt(DateTime now) =>
      snoozedUntil != null && snoozedUntil!.isAfter(now);

  /// Wall-clock convenience for the UI, which legitimately wants "right now".
  bool get isSnoozed => isSnoozedAt(DateTime.now());

  String get radiusLabel => radiusMetres >= 1000
      ? '${(radiusMetres / 1000).toStringAsFixed(radiusMetres % 1000 == 0 ? 0 : 1)} km'
      : '$radiusMetres m';

  AlarmSettings copyWith({
    bool? enabled,
    int? radiusMetres,
    IncidentSeverity? minimumSeverity,
    bool? quietHoursEnabled,
    QuietHours? quietHours,
    bool? criticalBypassesQuietHours,
    Set<String>? mutedCategories,
    DateTime? snoozedUntil,
    bool clearSnooze = false,
    int? pollIntervalSeconds,
    bool? includeUnverified,
    bool? vibrate,
  }) {
    return AlarmSettings(
      enabled: enabled ?? this.enabled,
      radiusMetres: radiusMetres ?? this.radiusMetres,
      minimumSeverity: minimumSeverity ?? this.minimumSeverity,
      quietHoursEnabled: quietHoursEnabled ?? this.quietHoursEnabled,
      quietHours: quietHours ?? this.quietHours,
      criticalBypassesQuietHours:
          criticalBypassesQuietHours ?? this.criticalBypassesQuietHours,
      mutedCategories: mutedCategories ?? this.mutedCategories,
      snoozedUntil: clearSnooze ? null : (snoozedUntil ?? this.snoozedUntil),
      pollIntervalSeconds: pollIntervalSeconds ?? this.pollIntervalSeconds,
      includeUnverified: includeUnverified ?? this.includeUnverified,
      vibrate: vibrate ?? this.vibrate,
    );
  }

  Map<String, dynamic> toJson() => {
        'enabled': enabled,
        'radius_m': radiusMetres,
        'min_severity': minimumSeverity.value,
        'quiet_hours_enabled': quietHoursEnabled,
        'quiet_hours': quietHours.toJson(),
        'critical_bypasses_quiet_hours': criticalBypassesQuietHours,
        'muted_categories': mutedCategories.toList(),
        'snoozed_until': snoozedUntil?.toIso8601String(),
        'poll_interval_s': pollIntervalSeconds,
        'include_unverified': includeUnverified,
        'vibrate': vibrate,
      };

  factory AlarmSettings.fromJson(Map<String, dynamic> json) {
    return AlarmSettings(
      enabled: json['enabled'] as bool? ?? true,
      radiusMetres: (json['radius_m'] as num?)?.toInt() ?? defaultRadiusMetres,
      minimumSeverity: IncidentSeverity.fromValue(json['min_severity'] as String?),
      quietHoursEnabled: json['quiet_hours_enabled'] as bool? ?? false,
      quietHours: json['quiet_hours'] is Map
          ? QuietHours.fromJson((json['quiet_hours'] as Map).cast<String, dynamic>())
          : QuietHours.disabledDefault,
      criticalBypassesQuietHours:
          json['critical_bypasses_quiet_hours'] as bool? ?? true,
      mutedCategories:
          (json['muted_categories'] as List?)?.map((e) => e.toString()).toSet() ??
              const {},
      snoozedUntil: DateTime.tryParse(json['snoozed_until']?.toString() ?? ''),
      pollIntervalSeconds: (json['poll_interval_s'] as num?)?.toInt() ?? 60,
      includeUnverified: json['include_unverified'] as bool? ?? true,
      vibrate: json['vibrate'] as bool? ?? true,
    );
  }

  String encode() => jsonEncode(toJson());

  static AlarmSettings decode(String raw) {
    try {
      return AlarmSettings.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return const AlarmSettings();
    }
  }
}
