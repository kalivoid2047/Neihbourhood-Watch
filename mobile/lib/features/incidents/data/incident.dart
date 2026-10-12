import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Incident categories, mirroring `apps.incidents.models.Incident.Category`.
enum IncidentCategory {
  theft('theft', 'Theft', Icons.shopping_bag_outlined),
  burglary('burglary', 'Burglary', Icons.meeting_room_outlined),
  assault('assault', 'Assault', Icons.personal_injury_outlined),
  suspiciousActivity('suspicious_activity', 'Suspicious Activity', Icons.visibility_outlined),
  missingPerson('missing_person', 'Missing Person', Icons.person_search_outlined),
  vandalism('vandalism', 'Vandalism', Icons.broken_image_outlined),
  infrastructureDamage('infrastructure_damage', 'Infrastructure Damage', Icons.construction_outlined);

  const IncidentCategory(this.value, this.label, this.icon);

  final String value;
  final String label;
  final IconData icon;

  static IncidentCategory fromValue(String value) {
    return IncidentCategory.values.firstWhere(
      (c) => c.value == value,
      orElse: () => IncidentCategory.suspiciousActivity,
    );
  }
}

/// Severity levels, mirroring `Incident.Severity`. The order matters: it is
/// used to compare an incident against the user's alarm threshold.
enum IncidentSeverity {
  green('green', 'Normal', 0),
  blue('blue', 'Average', 1),
  yellow('yellow', 'Important', 2),
  red('red', 'Critical', 3);

  const IncidentSeverity(this.value, this.label, this.rank);

  final String value;
  final String label;

  /// Higher is more urgent. Compared against [AlarmSettings.minimumSeverity].
  final int rank;

  Color get color => AppColors.forSeverity(value);

  static IncidentSeverity fromValue(String? value) {
    return IncidentSeverity.values.firstWhere(
      (s) => s.value == value,
      orElse: () => IncidentSeverity.green,
    );
  }
}

/// Workflow status, mirroring `Incident.Status`.
enum IncidentStatus {
  pending('pending', 'Pending'),
  verified('verified', 'Verified'),
  investigating('investigating', 'Investigating'),
  resolved('resolved', 'Resolved'),
  closed('closed', 'Closed');

  const IncidentStatus(this.value, this.label);

  final String value;
  final String label;

  bool get isOpen => this != IncidentStatus.resolved && this != IncidentStatus.closed;

  Color get color => switch (this) {
        IncidentStatus.pending => AppColors.textSecondary,
        IncidentStatus.verified => AppColors.primary400,
        IncidentStatus.investigating => AppColors.warning400,
        IncidentStatus.resolved => AppColors.success500,
        IncidentStatus.closed => AppColors.textSecondary,
      };

  static IncidentStatus fromValue(String? value) {
    return IncidentStatus.values.firstWhere(
      (s) => s.value == value,
      orElse: () => IncidentStatus.pending,
    );
  }
}

/// A reported incident.
///
/// The backend has two serializers — a light one for lists and a full one for
/// detail — so most fields here are nullable and [hasDetail] tells the UI
/// whether it needs to fetch the full record.
class Incident {
  const Incident({
    required this.id,
    required this.title,
    required this.category,
    required this.severity,
    required this.status,
    required this.latitude,
    required this.longitude,
    required this.occurredAt,
    this.description,
    this.address = '',
    this.reporterName = '',
    this.reporterId,
    this.neighborhoodId,
    this.verifiedByName,
    this.verifiedAt,
    this.assignedToName,
    this.createdAt,
    this.distanceMetres,
    this.media = const [],
    this.hasDetail = false,
  });

  final String id;
  final String title;
  final String? description;
  final IncidentCategory category;
  final IncidentSeverity severity;
  final IncidentStatus status;
  final double latitude;
  final double longitude;
  final String address;
  final DateTime occurredAt;
  final DateTime? createdAt;
  final String reporterName;
  final String? reporterId;
  final String? neighborhoodId;
  final String? verifiedByName;
  final DateTime? verifiedAt;
  final String? assignedToName;

  /// Present only on results from `/api/incidents/nearby/`.
  final double? distanceMetres;

  final List<IncidentMedia> media;
  final bool hasDetail;

  bool get isVerified => verifiedAt != null;

  /// Human-readable distance, e.g. "480 m" or "2.3 km".
  String? get distanceLabel {
    final metres = distanceMetres;
    if (metres == null) return null;
    if (metres < 1000) return '${metres.round()} m';
    return '${(metres / 1000).toStringAsFixed(1)} km';
  }

  factory Incident.fromJson(Map<String, dynamic> json) {
    final mediaJson = json['media'];
    return Incident(
      id: json['id'].toString(),
      title: json['title'] as String? ?? 'Untitled incident',
      description: json['description'] as String?,
      category: IncidentCategory.fromValue(json['category'] as String? ?? ''),
      severity: IncidentSeverity.fromValue(json['severity'] as String?),
      status: IncidentStatus.fromValue(json['status'] as String?),
      latitude: _toDouble(json['latitude']) ?? 0,
      longitude: _toDouble(json['longitude']) ?? 0,
      address: json['address'] as String? ?? '',
      occurredAt: _toDate(json['occurred_at']) ?? DateTime.now(),
      createdAt: _toDate(json['created_at']),
      reporterName: json['reporter_name'] as String? ?? '',
      reporterId: json['reporter']?.toString(),
      neighborhoodId: json['neighborhood']?.toString(),
      verifiedByName: json['verified_by_name'] as String?,
      verifiedAt: _toDate(json['verified_at']),
      assignedToName: json['assigned_to_name'] as String?,
      distanceMetres: _toDouble(json['distance_m']),
      media: mediaJson is List
          ? mediaJson
              .whereType<Map<String, dynamic>>()
              .map(IncidentMedia.fromJson)
              .toList()
          : const [],
      // `description` only appears on the detail serializer.
      hasDetail: json.containsKey('description'),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'description': description,
        'category': category.value,
        'severity': severity.value,
        'status': status.value,
        'latitude': latitude,
        'longitude': longitude,
        'address': address,
        'occurred_at': occurredAt.toIso8601String(),
        'created_at': createdAt?.toIso8601String(),
        'reporter_name': reporterName,
        'distance_m': distanceMetres,
      };

  Incident copyWith({double? distanceMetres}) {
    return Incident(
      id: id,
      title: title,
      description: description,
      category: category,
      severity: severity,
      status: status,
      latitude: latitude,
      longitude: longitude,
      address: address,
      occurredAt: occurredAt,
      createdAt: createdAt,
      reporterName: reporterName,
      reporterId: reporterId,
      neighborhoodId: neighborhoodId,
      verifiedByName: verifiedByName,
      verifiedAt: verifiedAt,
      assignedToName: assignedToName,
      distanceMetres: distanceMetres ?? this.distanceMetres,
      media: media,
      hasDetail: hasDetail,
    );
  }

  static double? _toDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString());
  }

  static DateTime? _toDate(dynamic value) {
    if (value == null) return null;
    return DateTime.tryParse(value.toString())?.toLocal();
  }
}

class IncidentMedia {
  const IncidentMedia({
    required this.id,
    required this.mediaType,
    required this.originalFilename,
    this.file,
    this.sizeBytes = 0,
    this.uploadedByName = '',
    this.uploadedAt,
  });

  final String id;

  /// One of `image`, `video`, `audio`.
  final String mediaType;
  final String originalFilename;
  final String? file;
  final int sizeBytes;
  final String uploadedByName;
  final DateTime? uploadedAt;

  bool get isImage => mediaType == 'image';

  factory IncidentMedia.fromJson(Map<String, dynamic> json) {
    return IncidentMedia(
      id: json['id'].toString(),
      mediaType: json['media_type'] as String? ?? 'image',
      originalFilename: json['original_filename'] as String? ?? '',
      file: json['file'] as String?,
      sizeBytes: (json['size_bytes'] as num?)?.toInt() ?? 0,
      uploadedByName: json['uploaded_by_name'] as String? ?? '',
      uploadedAt: DateTime.tryParse(json['uploaded_at']?.toString() ?? '')?.toLocal(),
    );
  }
}

/// One cell of the `/api/incidents/heatmap/` grid.
class HeatmapCell {
  const HeatmapCell({
    required this.latitude,
    required this.longitude,
    required this.count,
    this.severityCounts = const {},
  });

  final double latitude;
  final double longitude;
  final int count;
  final Map<String, int> severityCounts;

  factory HeatmapCell.fromJson(Map<String, dynamic> json) {
    final counts = json['severity_counts'];
    return HeatmapCell(
      latitude: (json['latitude'] as num).toDouble(),
      longitude: (json['longitude'] as num).toDouble(),
      count: (json['count'] as num?)?.toInt() ?? 0,
      severityCounts: counts is Map
          ? counts.map((k, v) => MapEntry(k.toString(), (v as num).toInt()))
          : const {},
    );
  }

  /// The most severe level present in this cell, used to colour the dot.
  IncidentSeverity get dominantSeverity {
    for (final severity in [
      IncidentSeverity.red,
      IncidentSeverity.yellow,
      IncidentSeverity.blue,
    ]) {
      if ((severityCounts[severity.value] ?? 0) > 0) return severity;
    }
    return IncidentSeverity.green;
  }
}
