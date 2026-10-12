import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/location/location_service.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../../incidents/data/incident.dart';

/// Map of incidents around the user, with the alarm radius drawn on it so the
/// setting stops being an abstract number.
class MapTab extends ConsumerStatefulWidget {
  const MapTab({super.key});

  @override
  ConsumerState<MapTab> createState() => _MapTabState();
}

class _MapTabState extends ConsumerState<MapTab> {
  final _controller = MapController();

  bool _showHeatmap = false;
  Incident? _selected;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final positionAsync = ref.watch(currentPositionProvider);
    final incidentsAsync = ref.watch(nearbyIncidentsProvider);
    final settings = ref.watch(alarmSettingsProvider);
    final permission = ref.watch(locationPermissionProvider).value;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Map'),
        actions: [
          IconButton(
            tooltip: _showHeatmap ? 'Hide heatmap' : 'Show heatmap',
            onPressed: () => setState(() => _showHeatmap = !_showHeatmap),
            icon: Icon(
              _showHeatmap ? Icons.layers_rounded : Icons.layers_outlined,
            ),
          ),
        ],
      ),
      body: positionAsync.when(
        loading: () => const LoadingState(message: 'Finding your location…'),
        error: (error, _) => ErrorState(
          message: 'Could not determine your location.',
          onRetry: () => ref.invalidate(currentPositionProvider),
        ),
        data: (position) {
          if (position == null) {
            return _LocationPrompt(state: permission);
          }

          final centre = LatLng(position.latitude, position.longitude);
          final incidents = incidentsAsync.value ?? const <Incident>[];

          return Stack(
            children: [
              FlutterMap(
                mapController: _controller,
                options: MapOptions(
                  initialCenter: centre,
                  initialZoom: 14,
                  onTap: (_, _) => setState(() => _selected = null),
                ),
                children: [
                  TileLayer(
                    // Same OSM tiles as the web dashboard's Leaflet map.
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'za.co.neighbourhoodwatch.nhw_mobile',
                    maxZoom: 19,
                  ),

                  // The alarm radius, so "5 km" means something visually.
                  CircleLayer(
                    circles: [
                      CircleMarker(
                        point: centre,
                        radius: settings.radiusMetres.toDouble(),
                        useRadiusInMeter: true,
                        color: AppColors.primary500.withValues(alpha: 0.08),
                        borderColor:
                            AppColors.primary400.withValues(alpha: 0.55),
                        borderStrokeWidth: 1.5,
                      ),
                    ],
                  ),

                  if (_showHeatmap) _HeatmapLayer(),

                  MarkerLayer(
                    markers: [
                      Marker(
                        point: centre,
                        width: 24,
                        height: 24,
                        child: Container(
                          decoration: BoxDecoration(
                            color: AppColors.primary400,
                            shape: BoxShape.circle,
                            border: Border.all(color: Colors.white, width: 3),
                            boxShadow: [
                              BoxShadow(
                                color: AppColors.primary400.withValues(alpha: 0.5),
                                blurRadius: 12,
                                spreadRadius: 2,
                              ),
                            ],
                          ),
                        ),
                      ),
                      ...incidents.map(
                        (incident) => Marker(
                          point: LatLng(incident.latitude, incident.longitude),
                          width: 38,
                          height: 38,
                          child: GestureDetector(
                            onTap: () => setState(() => _selected = incident),
                            child: _IncidentPin(
                              incident: incident,
                              selected: _selected?.id == incident.id,
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),

              if (incidentsAsync.isLoading)
                const Positioned(
                  top: 12,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: Chip(
                      avatar: SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      label: Text('Loading incidents…'),
                    ),
                  ),
                ),

              Positioned(
                right: 16,
                bottom: _selected != null ? 200 : 100,
                child: Column(
                  children: [
                    FloatingActionButton.small(
                      heroTag: 'recentre',
                      onPressed: () => _controller.move(centre, 14),
                      backgroundColor: AppColors.ink800,
                      foregroundColor: AppColors.primary300,
                      child: const Icon(Icons.my_location_rounded),
                    ),
                  ],
                ),
              ),

              if (_selected != null)
                Positioned(
                  left: 16,
                  right: 16,
                  bottom: 100,
                  child: _SelectedIncidentCard(
                    incident: _selected!,
                    onClose: () => setState(() => _selected = null),
                    onOpen: () =>
                        context.push(Routes.incidentDetail(_selected!.id)),
                  ),
                ),

              const Positioned(left: 16, bottom: 100, child: _Legend()),
            ],
          );
        },
      ),
    );
  }
}

class _IncidentPin extends StatelessWidget {
  const _IncidentPin({required this.incident, this.selected = false});

  final Incident incident;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final color = incident.severity.color;
    return AnimatedScale(
      scale: selected ? 1.2 : 1,
      duration: const Duration(milliseconds: 150),
      child: Container(
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          border: Border.all(
            color: selected ? Colors.white : AppColors.ink950,
            width: 2,
          ),
          boxShadow: [
            BoxShadow(
              color: color.withValues(alpha: 0.45),
              blurRadius: 8,
              spreadRadius: 1,
            ),
          ],
        ),
        child: Icon(incident.category.icon, size: 18, color: AppColors.ink950),
      ),
    );
  }
}

class _HeatmapLayer extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final cells = ref.watch(heatmapProvider).value ?? const [];
    if (cells.isEmpty) return const SizedBox.shrink();

    final maxCount = cells
        .map((cell) => cell.count)
        .reduce((a, b) => a > b ? a : b)
        .clamp(1, 1000)
        .toDouble();

    return CircleLayer(
      circles: cells.map((cell) {
        final intensity = (cell.count / maxCount).clamp(0.15, 1.0);
        return CircleMarker(
          point: LatLng(cell.latitude, cell.longitude),
          radius: 220 + (intensity * 380),
          useRadiusInMeter: true,
          color: cell.dominantSeverity.color.withValues(alpha: 0.12 * intensity + 0.06),
          borderColor: Colors.transparent,
          borderStrokeWidth: 0,
        );
      }).toList(),
    );
  }
}

class _SelectedIncidentCard extends StatelessWidget {
  const _SelectedIncidentCard({
    required this.incident,
    required this.onClose,
    required this.onOpen,
  });

  final Incident incident;
  final VoidCallback onClose;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                SeverityChip(severity: incident.severity),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    formatRelative(incident.occurredAt),
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ),
                IconButton(
                  onPressed: onClose,
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.close_rounded, size: 18),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              incident.title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            if (incident.distanceLabel != null) ...[
              const SizedBox(height: 4),
              Text(
                '${incident.distanceLabel} away',
                style: const TextStyle(color: AppColors.textSecondary),
              ),
            ],
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton(
                onPressed: onOpen,
                child: const Text('View details'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.ink900.withValues(alpha: 0.9),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: IncidentSeverity.values.reversed.map((severity) {
          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(
                    color: severity.color,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 6),
                Text(
                  severity.label,
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

/// Shown when we have no position at all — explains why the map is empty and
/// what the user can do about it.
class _LocationPrompt extends ConsumerWidget {
  const _LocationPrompt({this.state});

  final LocationPermissionState? state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final location = ref.read(locationServiceProvider);

    return EmptyState(
      icon: Icons.location_off_outlined,
      title: 'Location needed for the map',
      message: state?.message ??
          'Allow location access so we can show incidents around you.',
      action: Column(
        children: [
          FilledButton(
            onPressed: () async {
              await location.requestPermission();
              ref.invalidate(locationPermissionProvider);
              ref.invalidate(currentPositionProvider);
            },
            child: const Text('Allow location'),
          ),
          if (state == LocationPermissionState.deniedForever ||
              state == LocationPermissionState.servicesDisabled)
            TextButton(
              onPressed: () => state == LocationPermissionState.servicesDisabled
                  ? location.openLocationSettings()
                  : location.openSystemSettings(),
              child: const Text('Open settings'),
            ),
        ],
      ),
    );
  }
}
