import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../data/incident.dart';

import 'incident_card.dart';

/// The home tab: a status strip for the alarm, then the incident list.
class FeedTab extends ConsumerStatefulWidget {
  const FeedTab({super.key});

  @override
  ConsumerState<FeedTab> createState() => _FeedTabState();
}

class _FeedTabState extends ConsumerState<FeedTab> {
  bool _nearbyOnly = true;

  @override
  Widget build(BuildContext context) {
    final user = ref.watch(currentUserProvider);
    final feed = _nearbyOnly
        ? ref.watch(nearbyIncidentsProvider)
        : ref.watch(incidentFeedProvider);

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_nearbyOnly ? 'Near you' : 'All incidents'),
            if (user != null)
              Text(
                user.primaryNeighborhoodName ?? 'Your area',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w400,
                  color: AppColors.textSecondary,
                ),
              ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: 'Filter',
            onPressed: _openFilters,
            icon: Badge(
              isLabelVisible:
                  ref.watch(incidentFiltersProvider).activeCount > 0,
              label: Text('${ref.watch(incidentFiltersProvider).activeCount}'),
              child: const Icon(Icons.filter_list_rounded),
            ),
          ),
          IconButton(
            tooltip: 'Alarm settings',
            onPressed: () => context.push(Routes.alarmSettings),
            icon: const Icon(Icons.notifications_active_outlined),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(nearbyIncidentsProvider);
          ref.invalidate(incidentFeedProvider);
          await ref.read(alarmEngineProvider).pollNow();
        },
        child: Column(
          children: [
            const _AlarmStatusStrip(),
            _ScopeToggle(
              nearbyOnly: _nearbyOnly,
              onChanged: (value) => setState(() => _nearbyOnly = value),
            ),
            Expanded(
              child: feed.when(
                loading: () => const LoadingState(message: 'Loading incidents…'),
                error: (error, _) => ListView(
                  children: [
                    const SizedBox(height: 80),
                    ErrorState(
                      message: error is ApiException
                          ? error.message
                          : 'Could not load incidents.',
                      isOffline: error is ApiException && error.isConnectivity,
                      onRetry: () {
                        ref.invalidate(nearbyIncidentsProvider);
                        ref.invalidate(incidentFeedProvider);
                      },
                    ),
                  ],
                ),
                data: (incidents) => incidents.isEmpty
                    ? ListView(
                        children: [
                          const SizedBox(height: 80),
                          EmptyState(
                            icon: Icons.verified_user_outlined,
                            title: _nearbyOnly
                                ? 'All quiet nearby'
                                : 'No incidents match',
                            message: _nearbyOnly
                                ? 'Nothing has been reported within '
                                    '${ref.watch(alarmSettingsProvider).radiusLabel} '
                                    'of you.'
                                : 'Try widening your filters.',
                            action: FilledButton.icon(
                              onPressed: () => context.push(Routes.report),
                              icon: const Icon(Icons.add_alert_outlined),
                              label: const Text('Report an incident'),
                            ),
                          ),
                        ],
                      )
                    : ListView.separated(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                        itemCount: incidents.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 12),
                        itemBuilder: (context, index) {
                          final incident = incidents[index];
                          return IncidentCard(
                            incident: incident,
                            onTap: () => context.push(
                              Routes.incidentDetail(incident.id),
                            ),
                          );
                        },
                      ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _openFilters() async {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.ink900,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => const _FilterSheet(),
    );
  }
}

/// Shows at a glance whether the alarm is actually armed — the single most
/// important piece of state in the app, and the one a user will check before
/// going to sleep.
class _AlarmStatusStrip extends ConsumerWidget {
  const _AlarmStatusStrip();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(alarmSettingsProvider);
    final lastPoll = ref.watch(lastPollProvider).value;

    final (icon, color, label) = switch (settings) {
      _ when !settings.enabled => (
          Icons.notifications_off_outlined,
          AppColors.danger500,
          'Alarms are off',
        ),
      _ when settings.isSnoozed => (
          Icons.snooze_rounded,
          AppColors.warning400,
          'Snoozed until ${formatRelative(settings.snoozedUntil!)}',
        ),
      _ => (
          Icons.notifications_active_rounded,
          AppColors.success500,
          'Armed · ${settings.radiusLabel} radius',
        ),
    };

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: TextStyle(color: color, fontWeight: FontWeight.w600),
                ),
                if (lastPoll != null)
                  Text(
                    'Last checked ${formatRelative(lastPoll)}',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
              ],
            ),
          ),
          TextButton(
            onPressed: () => context.push(Routes.alarmSettings),
            child: const Text('Manage'),
          ),
        ],
      ),
    );
  }
}

class _ScopeToggle extends ConsumerWidget {
  const _ScopeToggle({required this.nearbyOnly, required this.onChanged});

  final bool nearbyOnly;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final radius = ref.watch(alarmSettingsProvider).radiusLabel;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: SegmentedButton<bool>(
        segments: [
          ButtonSegment(
            value: true,
            label: Text('Within $radius'),
            icon: const Icon(Icons.my_location_rounded, size: 16),
          ),
          const ButtonSegment(
            value: false,
            label: Text('Everything'),
            icon: Icon(Icons.public_rounded, size: 16),
          ),
        ],
        selected: {nearbyOnly},
        showSelectedIcon: false,
        onSelectionChanged: (values) => onChanged(values.first),
      ),
    );
  }
}

class _FilterSheet extends ConsumerWidget {
  const _FilterSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filters = ref.watch(incidentFiltersProvider);
    final notifier = ref.read(incidentFiltersProvider.notifier);

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Filter incidents',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                ),
                TextButton(
                  onPressed: () =>
                      notifier.clear(),
                  child: const Text('Clear all'),
                ),
              ],
            ),

            const SectionHeader(title: 'Severity'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: IncidentSeverity.values.reversed.map((severity) {
                final selected = filters.severities.contains(severity);
                return FilterChip(
                  label: Text(severity.label),
                  selected: selected,
                  selectedColor: severity.color.withValues(alpha: 0.25),
                  checkmarkColor: severity.color,
                  onSelected: (_) {
                    final next = filters.severities.toSet();
                    if (!next.remove(severity)) next.add(severity);
                    notifier.apply(filters.copyWith(severities: next));
                  },
                );
              }).toList(),
            ),

            const SectionHeader(title: 'Category'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: IncidentCategory.values.map((category) {
                final selected = filters.categories.contains(category);
                return FilterChip(
                  avatar: Icon(category.icon, size: 16),
                  label: Text(category.label),
                  selected: selected,
                  onSelected: (_) {
                    final next = filters.categories.toSet();
                    if (!next.remove(category)) next.add(category);
                    notifier.apply(filters.copyWith(categories: next));
                  },
                );
              }).toList(),
            ),

            const SectionHeader(title: 'Status'),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: IncidentStatus.values.map((status) {
                final selected = filters.statuses.contains(status);
                return FilterChip(
                  label: Text(status.label),
                  selected: selected,
                  onSelected: (_) {
                    final next = filters.statuses.toSet();
                    if (!next.remove(status)) next.add(status);
                    notifier.apply(filters.copyWith(statuses: next));
                  },
                );
              }).toList(),
            ),

            const SizedBox(height: 12),
            CheckboxListTile(
              value: filters.mineOnly,
              contentPadding: EdgeInsets.zero,
              onChanged: (value) =>
                  notifier.apply(filters.copyWith(mineOnly: value ?? false)),
              title: const Text('Only incidents I reported'),
            ),

            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Apply'),
            ),
          ],
        ),
      ),
    );
  }
}
