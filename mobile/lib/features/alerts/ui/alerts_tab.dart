import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../../alarm/data/alarm_store.dart';

/// The alert inbox: everything the alarm engine has decided about, newest
/// first, with a control strip for the alarm itself.
class AlertsTab extends ConsumerWidget {
  const AlertsTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final entries = ref.watch(alarmHistoryProvider);
    final settings = ref.watch(alarmSettingsProvider);
    final unacknowledged =
        entries.where((e) => e.wasAudible && !e.isAcknowledged).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          IconButton(
            tooltip: 'Alarm settings',
            onPressed: () => context.push(Routes.alarmSettings),
            icon: const Icon(Icons.tune_rounded),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          await ref.read(alarmStoreProvider).reload();
          ref.read(alarmHistoryRefreshProvider.notifier).bump();
          await ref.read(alarmEngineProvider).pollNow();
        },
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
          children: [
            if (unacknowledged > 0)
              Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.danger500.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: AppColors.danger500.withValues(alpha: 0.4),
                  ),
                ),
                child: Row(
                  children: [
                    const Icon(
                      Icons.priority_high_rounded,
                      color: AppColors.danger500,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '$unacknowledged alarm${unacknowledged == 1 ? '' : 's'} '
                        'not acknowledged',
                        style: const TextStyle(
                          color: AppColors.danger500,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

            _QuickControls(settingsSnoozed: settings.isSnoozed),

            const SectionHeader(title: 'Recent activity'),

            if (entries.isEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 40),
                child: EmptyState(
                  icon: Icons.notifications_none_rounded,
                  title: 'Nothing to report',
                  message:
                      'Alerts about incidents near you will appear here, '
                      'whether or not they sounded the alarm.',
                ),
              )
            else
              ...entries.map((entry) => _AlertRow(entry: entry)),
          ],
        ),
      ),
    );
  }
}

class _QuickControls extends ConsumerWidget {
  const _QuickControls({required this.settingsSnoozed});

  final bool settingsSnoozed;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final controller = ref.read(alarmSettingsProvider.notifier);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: settingsSnoozed
                    ? controller.clearSnooze
                    : () => controller.snooze(const Duration(hours: 1)),
                icon: Icon(
                  settingsSnoozed
                      ? Icons.notifications_active_outlined
                      : Icons.snooze_rounded,
                  size: 18,
                ),
                label: Text(settingsSnoozed ? 'Resume alarms' : 'Snooze 1 hour'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => ref.read(alarmEngineProvider).pollNow(),
                icon: const Icon(Icons.refresh_rounded, size: 18),
                label: const Text('Check now'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _AlertRow extends StatelessWidget {
  const _AlertRow({required this.entry});

  final AlarmHistoryEntry entry;

  @override
  Widget build(BuildContext context) {
    final colour = entry.severityLevel.color;

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Card(
        child: ListTile(
          onTap: () => context.push(Routes.incidentDetail(entry.incidentId)),
          leading: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: colour.withValues(alpha: 0.15),
              shape: BoxShape.circle,
            ),
            child: Icon(
              entry.wasAudible
                  ? Icons.notifications_active_rounded
                  : Icons.notifications_none_rounded,
              color: colour,
              size: 20,
            ),
          ),
          title: Text(
            entry.title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
          ),
          subtitle: Text(
            '${formatRelative(entry.firedAt)}'
            '${entry.wasAudible ? ' · Alarm sounded' : ' · ${entry.reason}'}',
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 12,
            ),
          ),
          trailing: const Icon(Icons.chevron_right_rounded, size: 20),
        ),
      ),
    );
  }
}
