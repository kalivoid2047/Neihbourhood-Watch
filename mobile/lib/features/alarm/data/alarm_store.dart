import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../../incidents/data/incident.dart';
import 'alarm_rules.dart';
import 'alarm_settings.dart';

/// One entry in the alarm history.
class AlarmHistoryEntry {
  const AlarmHistoryEntry({
    required this.incidentId,
    required this.title,
    required this.severity,
    required this.category,
    required this.firedAt,
    required this.wasAudible,
    this.distanceMetres,
    this.reason = '',
    this.acknowledgedAt,
  });

  final String incidentId;
  final String title;
  final String severity;
  final String category;
  final DateTime firedAt;
  final bool wasAudible;
  final double? distanceMetres;
  final String reason;
  final DateTime? acknowledgedAt;

  bool get isAcknowledged => acknowledgedAt != null;

  IncidentSeverity get severityLevel => IncidentSeverity.fromValue(severity);

  AlarmHistoryEntry acknowledge(DateTime at) => AlarmHistoryEntry(
        incidentId: incidentId,
        title: title,
        severity: severity,
        category: category,
        firedAt: firedAt,
        wasAudible: wasAudible,
        distanceMetres: distanceMetres,
        reason: reason,
        acknowledgedAt: at,
      );

  Map<String, dynamic> toJson() => {
        'incident_id': incidentId,
        'title': title,
        'severity': severity,
        'category': category,
        'fired_at': firedAt.toIso8601String(),
        'was_audible': wasAudible,
        'distance_m': distanceMetres,
        'reason': reason,
        'acknowledged_at': acknowledgedAt?.toIso8601String(),
      };

  factory AlarmHistoryEntry.fromJson(Map<String, dynamic> json) {
    return AlarmHistoryEntry(
      incidentId: json['incident_id'].toString(),
      title: json['title'] as String? ?? '',
      severity: json['severity'] as String? ?? 'green',
      category: json['category'] as String? ?? '',
      firedAt: DateTime.tryParse(json['fired_at']?.toString() ?? '') ?? DateTime.now(),
      wasAudible: json['was_audible'] as bool? ?? false,
      distanceMetres: (json['distance_m'] as num?)?.toDouble(),
      reason: json['reason'] as String? ?? '',
      acknowledgedAt: DateTime.tryParse(json['acknowledged_at']?.toString() ?? ''),
    );
  }

  factory AlarmHistoryEntry.from(
    Incident incident,
    AlarmEvaluation evaluation,
    DateTime firedAt,
  ) {
    return AlarmHistoryEntry(
      incidentId: incident.id,
      title: incident.title,
      severity: incident.severity.value,
      category: incident.category.value,
      firedAt: firedAt,
      wasAudible: evaluation.shouldAlarm,
      distanceMetres: evaluation.distanceMetres,
      reason: evaluation.explanation,
    );
  }
}

/// Persistent state for the alarm engine.
///
/// Deliberately built on `shared_preferences` rather than the app's in-memory
/// providers: the background poller runs in a **separate isolate** with no
/// access to the UI's object graph, so the seen-incident set and the settings
/// have to live somewhere both isolates can reach.
class AlarmStore {
  AlarmStore(this._prefs);

  static const _settingsKey = 'nhw.alarm.settings';
  static const _seenKey = 'nhw.alarm.seen';
  static const _historyKey = 'nhw.alarm.history';
  static const _lastAlarmKey = 'nhw.alarm.last_fired_at';
  static const _lastPollKey = 'nhw.alarm.last_poll_at';
  static const _pendingKey = 'nhw.alarm.pending';

  /// Cap on the seen-incident set. Older ids fall off; combined with
  /// [AlarmRules.maxAge] they can never alarm again anyway.
  static const _maxSeen = 500;
  static const _maxHistory = 100;

  final SharedPreferences _prefs;

  static Future<AlarmStore> open() async =>
      AlarmStore(await SharedPreferences.getInstance());

  /// Re-reads from disk. The background isolate writes behind the UI's back,
  /// so the UI calls this when it resumes.
  Future<void> reload() => _prefs.reload();

  // ── Settings ──────────────────────────────────────────────────────────────

  AlarmSettings readSettings() {
    final raw = _prefs.getString(_settingsKey);
    return raw == null ? const AlarmSettings() : AlarmSettings.decode(raw);
  }

  Future<void> writeSettings(AlarmSettings settings) =>
      _prefs.setString(_settingsKey, settings.encode());

  // ── Seen incidents (dedupe) ───────────────────────────────────────────────

  List<String> readSeen() => _prefs.getStringList(_seenKey) ?? const [];

  bool hasSeen(String incidentId) => readSeen().contains(incidentId);

  Future<void> markSeen(String incidentId) async {
    final seen = readSeen().toList()..remove(incidentId);
    seen.add(incidentId);
    if (seen.length > _maxSeen) {
      seen.removeRange(0, seen.length - _maxSeen);
    }
    await _prefs.setStringList(_seenKey, seen);
  }

  Future<void> markAllSeen(Iterable<String> ids) async {
    final seen = readSeen().toList();
    for (final id in ids) {
      seen
        ..remove(id)
        ..add(id);
    }
    if (seen.length > _maxSeen) {
      seen.removeRange(0, seen.length - _maxSeen);
    }
    await _prefs.setStringList(_seenKey, seen);
  }

  Future<void> clearSeen() => _prefs.remove(_seenKey);

  // ── Cooldown bookkeeping ──────────────────────────────────────────────────

  DateTime? readLastAlarmAt() {
    final raw = _prefs.getString(_lastAlarmKey);
    return raw == null ? null : DateTime.tryParse(raw);
  }

  Future<void> writeLastAlarmAt(DateTime at) =>
      _prefs.setString(_lastAlarmKey, at.toIso8601String());

  DateTime? readLastPollAt() {
    final raw = _prefs.getString(_lastPollKey);
    return raw == null ? null : DateTime.tryParse(raw);
  }

  Future<void> writeLastPollAt(DateTime at) =>
      _prefs.setString(_lastPollKey, at.toIso8601String());

  // ── History ───────────────────────────────────────────────────────────────

  List<AlarmHistoryEntry> readHistory() {
    final raw = _prefs.getStringList(_historyKey) ?? const [];
    return raw
        .map((entry) {
          try {
            return AlarmHistoryEntry.fromJson(
              jsonDecode(entry) as Map<String, dynamic>,
            );
          } catch (_) {
            return null;
          }
        })
        .whereType<AlarmHistoryEntry>()
        .toList()
      ..sort((a, b) => b.firedAt.compareTo(a.firedAt));
  }

  Future<void> addHistory(AlarmHistoryEntry entry) async {
    final entries = readHistory()..insert(0, entry);
    if (entries.length > _maxHistory) {
      entries.removeRange(_maxHistory, entries.length);
    }
    await _writeHistory(entries);
  }

  Future<void> acknowledge(String incidentId, DateTime at) async {
    final entries = readHistory()
        .map((e) => e.incidentId == incidentId && !e.isAcknowledged
            ? e.acknowledge(at)
            : e)
        .toList();
    await _writeHistory(entries);
  }

  Future<void> clearHistory() => _prefs.remove(_historyKey);

  Future<void> _writeHistory(List<AlarmHistoryEntry> entries) {
    return _prefs.setStringList(
      _historyKey,
      entries.map((e) => jsonEncode(e.toJson())).toList(),
    );
  }

  // ── Isolate hand-off ──────────────────────────────────────────────────────

  /// The background isolate cannot show the full-screen alarm UI directly, so
  /// it parks the incident id here. The UI picks it up when the user taps the
  /// notification or the app next resumes.
  Future<void> setPendingAlarm(String incidentId) =>
      _prefs.setString(_pendingKey, incidentId);

  String? readPendingAlarm() => _prefs.getString(_pendingKey);

  Future<void> clearPendingAlarm() => _prefs.remove(_pendingKey);
}
