import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/providers.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/config/app_config.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../data/incident.dart';

class IncidentDetailScreen extends ConsumerWidget {
  const IncidentDetailScreen({super.key, required this.incidentId});

  final String incidentId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final incidentAsync = ref.watch(incidentDetailProvider(incidentId));
    final user = ref.watch(currentUserProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Incident')),
      body: incidentAsync.when(
        loading: () => const LoadingState(),
        error: (error, _) => ErrorState(
          message: error is ApiException
              ? error.message
              : 'Could not load this incident.',
          isOffline: error is ApiException && error.isConnectivity,
          onRetry: () => ref.invalidate(incidentDetailProvider(incidentId)),
        ),
        data: (incident) => RefreshIndicator(
          onRefresh: () async =>
              ref.invalidate(incidentDetailProvider(incidentId)),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 40),
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  SeverityChip(
                    severity: incident.severity,
                    filled: incident.severity == IncidentSeverity.red,
                  ),
                  TagChip(
                    label: incident.status.label,
                    color: incident.status.color,
                  ),
                  TagChip(
                    label: incident.category.label,
                    color: AppColors.textSecondary,
                    icon: incident.category.icon,
                  ),
                  if (incident.distanceLabel != null)
                    TagChip(
                      label: '${incident.distanceLabel} away',
                      color: AppColors.primary400,
                      icon: Icons.near_me_outlined,
                    ),
                ],
              ),
              const SizedBox(height: 16),

              Text(
                incident.title,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w700,
                  height: 1.25,
                ),
              ),
              const SizedBox(height: 10),

              _MetaRow(
                icon: Icons.schedule_rounded,
                label: 'Occurred',
                value:
                    '${formatDateTime(incident.occurredAt)} (${formatRelative(incident.occurredAt)})',
              ),
              if (incident.address.isNotEmpty)
                _MetaRow(
                  icon: Icons.place_outlined,
                  label: 'Location',
                  value: incident.address,
                ),
              if (incident.reporterName.isNotEmpty)
                _MetaRow(
                  icon: Icons.person_outline_rounded,
                  label: 'Reported by',
                  value: incident.reporterName,
                ),
              if (incident.verifiedByName != null)
                _MetaRow(
                  icon: Icons.verified_outlined,
                  label: 'Verified by',
                  value: incident.verifiedByName!,
                  valueColor: AppColors.success500,
                ),
              if (incident.assignedToName != null)
                _MetaRow(
                  icon: Icons.assignment_ind_outlined,
                  label: 'Assigned to',
                  value: incident.assignedToName!,
                ),

              if (!incident.isVerified) ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.warning400.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: AppColors.warning400.withValues(alpha: 0.35),
                    ),
                  ),
                  child: const Row(
                    children: [
                      Icon(
                        Icons.info_outline_rounded,
                        color: AppColors.warning400,
                        size: 18,
                      ),
                      SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          'This report has not been verified by a coordinator '
                          'yet. Treat the details with care.',
                          style: TextStyle(
                            color: AppColors.warning400,
                            fontSize: 13,
                            height: 1.35,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              if (incident.description != null &&
                  incident.description!.isNotEmpty) ...[
                const SectionHeader(title: 'What happened'),
                Text(
                  incident.description!,
                  style: const TextStyle(
                    fontSize: 15,
                    height: 1.55,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],

              const SectionHeader(title: 'Where'),
              _LocationMap(incident: incident),

              if (incident.media.isNotEmpty) ...[
                const SectionHeader(title: 'Evidence'),
                _MediaStrip(media: incident.media),
              ],

              if (user?.canModerate ?? false) ...[
                const SectionHeader(title: 'Coordinator actions'),
                _ModerationActions(incident: incident),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({
    required this.icon,
    required this.label,
    required this.value,
    this.valueColor,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: AppColors.textSecondary),
          const SizedBox(width: 8),
          SizedBox(
            width: 92,
            child: Text(
              label,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 13,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                color: valueColor ?? AppColors.textPrimary,
                fontSize: 14,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _LocationMap extends StatelessWidget {
  const _LocationMap({required this.incident});

  final Incident incident;

  @override
  Widget build(BuildContext context) {
    final point = LatLng(incident.latitude, incident.longitude);

    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: SizedBox(
        height: 200,
        child: FlutterMap(
          options: MapOptions(
            initialCenter: point,
            initialZoom: 15,
            interactionOptions: const InteractionOptions(
              // A static preview: panning here would fight the parent scroll.
              flags: InteractiveFlag.none,
            ),
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              userAgentPackageName: 'za.co.neighbourhoodwatch.nhw_mobile',
            ),
            MarkerLayer(
              markers: [
                Marker(
                  point: point,
                  width: 40,
                  height: 40,
                  child: Container(
                    decoration: BoxDecoration(
                      color: incident.severity.color,
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white, width: 2),
                    ),
                    child: Icon(
                      incident.category.icon,
                      size: 20,
                      color: AppColors.ink950,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MediaStrip extends StatelessWidget {
  const _MediaStrip({required this.media});

  final List<IncidentMedia> media;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 130,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: media.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final item = media[index];
          return ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: Container(
              width: 130,
              color: AppColors.ink800,
              child: item.isImage && item.file != null
                  ? Image.network(
                      _absoluteUrl(item.file!),
                      fit: BoxFit.cover,
                      errorBuilder: (_, _, _) => const _MediaPlaceholder(
                        icon: Icons.broken_image_outlined,
                        label: 'Unavailable',
                      ),
                      loadingBuilder: (context, child, progress) =>
                          progress == null
                              ? child
                              : const Center(
                                  child: SizedBox(
                                    width: 20,
                                    height: 20,
                                    child:
                                        CircularProgressIndicator(strokeWidth: 2),
                                  ),
                                ),
                    )
                  : _MediaPlaceholder(
                      icon: item.mediaType == 'video'
                          ? Icons.videocam_outlined
                          : Icons.mic_none_rounded,
                      label: item.mediaType == 'video' ? 'Video' : 'Audio',
                    ),
            ),
          );
        },
      ),
    );
  }

  /// Media URLs come back relative on some deployments; make them absolute.
  static String _absoluteUrl(String path) =>
      path.startsWith('http') ? path : '${AppConfig.apiBaseUrl}$path';
}

class _MediaPlaceholder extends StatelessWidget {
  const _MediaPlaceholder({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, size: 30, color: AppColors.textSecondary),
        const SizedBox(height: 6),
        Text(
          label,
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
        ),
      ],
    );
  }
}

/// Verify / status actions, shown only to roles the backend would accept.
class _ModerationActions extends ConsumerStatefulWidget {
  const _ModerationActions({required this.incident});

  final Incident incident;

  @override
  ConsumerState<_ModerationActions> createState() => _ModerationActionsState();
}

class _ModerationActionsState extends ConsumerState<_ModerationActions> {
  bool _busy = false;

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
      ref.invalidate(incidentDetailProvider(widget.incident.id));
      ref.invalidate(incidentFeedProvider);
      ref.invalidate(nearbyIncidentsProvider);
    } on ApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.read(incidentsRepositoryProvider);
    final incident = widget.incident;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!incident.isVerified)
          FilledButton.icon(
            onPressed: _busy ? null : () => _run(() => repo.verify(incident.id)),
            icon: const Icon(Icons.verified_outlined),
            label: const Text('Verify this incident'),
          ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: IncidentStatus.values
              .where((status) => status != incident.status)
              .map(
                (status) => OutlinedButton(
                  onPressed: _busy
                      ? null
                      : () => _run(
                            () => repo.transitionStatus(incident.id, status),
                          ),
                  style: OutlinedButton.styleFrom(
                    minimumSize: const Size(0, 40),
                    foregroundColor: status.color,
                  ),
                  child: Text('Mark ${status.label.toLowerCase()}'),
                ),
              )
              .toList(),
        ),
      ],
    );
  }
}
