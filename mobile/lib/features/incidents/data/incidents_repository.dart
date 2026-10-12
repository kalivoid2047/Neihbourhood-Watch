import 'dart:io';

import 'package:dio/dio.dart';

import '../../../core/api/api_client.dart';
import 'incident.dart';

/// Filters for the incident feed. Mirrors the query parameters the backend's
/// `IncidentViewSet` understands.
class IncidentFilters {
  const IncidentFilters({
    this.categories = const {},
    this.severities = const {},
    this.statuses = const {},
    this.mineOnly = false,
    this.search,
  });

  final Set<IncidentCategory> categories;
  final Set<IncidentSeverity> severities;
  final Set<IncidentStatus> statuses;
  final bool mineOnly;
  final String? search;

  bool get isEmpty =>
      categories.isEmpty &&
      severities.isEmpty &&
      statuses.isEmpty &&
      !mineOnly &&
      (search == null || search!.isEmpty);

  int get activeCount =>
      categories.length +
      severities.length +
      statuses.length +
      (mineOnly ? 1 : 0);

  Map<String, dynamic> toQuery() => {
        if (categories.isNotEmpty)
          'category': categories.map((c) => c.value).toList(),
        if (severities.isNotEmpty)
          'severity': severities.map((s) => s.value).toList(),
        if (statuses.isNotEmpty) 'status': statuses.map((s) => s.value).toList(),
        if (mineOnly) 'mine': 'true',
        if (search != null && search!.isNotEmpty) 'search': search,
      };

  IncidentFilters copyWith({
    Set<IncidentCategory>? categories,
    Set<IncidentSeverity>? severities,
    Set<IncidentStatus>? statuses,
    bool? mineOnly,
    String? search,
  }) {
    return IncidentFilters(
      categories: categories ?? this.categories,
      severities: severities ?? this.severities,
      statuses: statuses ?? this.statuses,
      mineOnly: mineOnly ?? this.mineOnly,
      search: search ?? this.search,
    );
  }
}

/// A page of results from a DRF paginated list endpoint.
class Page<T> {
  const Page({required this.items, this.next, this.count = 0});

  final List<T> items;
  final String? next;
  final int count;

  bool get hasMore => next != null;
}

class IncidentsRepository {
  IncidentsRepository(this._api);

  final ApiClient _api;

  /// GET /api/incidents/
  Future<Page<Incident>> list({
    IncidentFilters filters = const IncidentFilters(),
    int page = 1,
    int pageSize = 20,
  }) async {
    final data = await _api.get<dynamic>(
      '/incidents/',
      query: {...filters.toQuery(), 'page': page, 'page_size': pageSize},
    );
    return _pageFrom(data, Incident.fromJson);
  }

  /// GET /api/incidents/{id}/
  Future<Incident> detail(String id) async {
    final data = await _api.get<Map<String, dynamic>>('/incidents/$id/');
    return Incident.fromJson(data);
  }

  /// GET /api/incidents/nearby/ — the alarm's polling source.
  ///
  /// [radiusMetres] is clamped to the backend's accepted 1–50 000 m range so a
  /// bad setting produces fewer results rather than a 400.
  Future<List<Incident>> nearby({
    required double latitude,
    required double longitude,
    required double radiusMetres,
    List<IncidentStatus>? statuses,
  }) async {
    final data = await _api.get<dynamic>(
      '/incidents/nearby/',
      query: {
        'latitude': latitude,
        'longitude': longitude,
        'radius_m': radiusMetres.clamp(1, 50000),
        if (statuses != null && statuses.isNotEmpty)
          'status': statuses.map((s) => s.value).toList(),
      },
    );

    final items = data is Map ? (data['results'] as List? ?? const []) : data as List;
    return items
        .whereType<Map>()
        .map((e) => Incident.fromJson(e.cast<String, dynamic>()))
        .toList();
  }

  /// GET /api/incidents/heatmap/
  Future<List<HeatmapCell>> heatmap({
    String? neighborhoodId,
    ({double minLat, double minLon, double maxLat, double maxLon})? bounds,
    int days = 7,
  }) async {
    assert(
      neighborhoodId != null || bounds != null,
      'heatmap requires either a neighborhood id or bounds',
    );

    final data = await _api.get<dynamic>(
      '/incidents/heatmap/',
      query: {
        'neighborhood_id': ?neighborhoodId,
        if (bounds != null)
          'bounds':
              '${bounds.minLat},${bounds.minLon},${bounds.maxLat},${bounds.maxLon}',
        'days': days,
      },
    );

    final items = data is Map ? (data['results'] as List? ?? const []) : data as List;
    return items
        .whereType<Map>()
        .map((e) => HeatmapCell.fromJson(e.cast<String, dynamic>()))
        .toList();
  }

  /// POST /api/incidents/
  Future<Incident> create({
    required String title,
    required String description,
    required IncidentCategory category,
    required IncidentSeverity severity,
    required double latitude,
    required double longitude,
    required DateTime occurredAt,
    String address = '',
    String? neighborhoodId,
    Map<String, dynamic> metadata = const {},
  }) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/incidents/',
      body: {
        'title': title,
        'description': description,
        'category': category.value,
        'severity': severity.value,
        'latitude': latitude,
        'longitude': longitude,
        'address': address,
        'occurred_at': occurredAt.toUtc().toIso8601String(),
        'neighborhood': ?neighborhoodId,
        if (metadata.isNotEmpty) 'metadata': metadata,
      },
    );
    return Incident.fromJson(data);
  }

  /// POST /api/incidents/{id}/upload_media/
  Future<IncidentMedia> uploadMedia({
    required String incidentId,
    required File file,
    required String mediaType,
    void Function(double progress)? onProgress,
  }) async {
    final form = FormData.fromMap({
      'media_type': mediaType,
      'file': await MultipartFile.fromFile(
        file.path,
        filename: file.uri.pathSegments.last,
      ),
    });

    final data = await _api.upload<Map<String, dynamic>>(
      '/incidents/$incidentId/upload_media/',
      form: form,
      onProgress: (sent, total) {
        if (total > 0) onProgress?.call(sent / total);
      },
    );
    return IncidentMedia.fromJson(data);
  }

  // ── Moderation (block captains, coordinators, police) ─────────────────────

  Future<Incident> verify(String id) async {
    final data = await _api.post<Map<String, dynamic>>('/incidents/$id/verify/');
    return Incident.fromJson(data);
  }

  Future<Incident> transitionStatus(String id, IncidentStatus status) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/incidents/$id/transition_status/',
      body: {'new_status': status.value},
    );
    return Incident.fromJson(data);
  }

  static Page<T> _pageFrom<T>(dynamic data, T Function(Map<String, dynamic>) parse) {
    if (data is List) {
      return Page(
        items: data
            .whereType<Map>()
            .map((e) => parse(e.cast<String, dynamic>()))
            .toList(),
      );
    }

    final map = (data as Map).cast<String, dynamic>();
    final results = map['results'] as List? ?? const [];
    return Page(
      items: results
          .whereType<Map>()
          .map((e) => parse(e.cast<String, dynamic>()))
          .toList(),
      next: map['next'] as String?,
      count: (map['count'] as num?)?.toInt() ?? results.length,
    );
  }
}
