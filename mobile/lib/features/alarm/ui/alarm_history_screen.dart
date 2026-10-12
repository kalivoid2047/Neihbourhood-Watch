import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';

/// A log of every alarm and alert the engine has raised, and why.
///
/// This exists because the commonest question about an alarm feature is the
/// one you cannot answer from the tray: "why did it (not) go off?"
class AlarmHistoryScreen extends ConsumerWidget {
  const AlarmHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final entries = ref.watch(alarmHistoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alarm history'),
        actions: [
          if (entries.isNotEmpty)
            IconButton(
              tooltip: 'Clear history',
              onPressed: () async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Clear alarm history?'),
                    content: const Text(
                      'This only clears the log on this phone. The incidents '
                      'themselves are not affected.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(false),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.of(context).pop(true),
                        child: const Text('Clear'),
                      ),
                    ],
                  ),
                );

                if (confirmed != true) return;
                await ref.read(alarmStoreProvider).clearHistory();
                ref.read(alarmHistoryRefreshProvider.notifier).bump();
              },
              icon: const Icon(Icons.delete_outline_rounded),
            ),
        ],
      ),
      body: entries.isEmpty
          ? const EmptyState(
              icon: Icons.history_toggle_off_rounded,
              title: 'No alarms yet',
              message:
                  'When an incident is reported near you, it will be logged '
                  'here with the reason it did or did not sound.',
            )
          : ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
              itemCount: entries.length,
              separatorBuilder: (_, _) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final entry = entries[index];
                final colour = entry.severityLevel.color;

                return Card(
                  child: ListTile(
                    onTap: () =>
                        context.push(Routes.incidentDetail(entry.incidentId)),
                    leading: Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: colour.withValues(alpha: 0.15),
                        shape: BoxShape.circle,
                        border: Border.all(color: colour.withValues(alpha: 0.5)),
                      ),
                      child: Icon(
                        entry.wasAudible
                            ? Icons.volume_up_rounded
                            : Icons.notifications_none_rounded,
                        color: colour,
                        size: 20,
                      ),
                    ),
                    title: Text(
                      entry.title,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    subtitle: Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${formatRelative(entry.firedAt)} · '
                            '${entry.wasAudible ? 'Alarm sounded' : entry.reason}',
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 12,
                            ),
                          ),
                          if (entry.distanceMetres != null)
                            Text(
                              entry.distanceMetres! < 1000
                                  ? '${entry.distanceMetres!.round()} m away'
                                  : '${(entry.distanceMetres! / 1000).toStringAsFixed(1)} km away',
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 12,
                              ),
                            ),
                        ],
                      ),
                    ),
                    trailing: entry.isAcknowledged
                        ? const Icon(
                            Icons.check_circle_outline_rounded,
                            color: AppColors.success500,
                            size: 20,
                          )
                        : null,
                  ),
                );
              },
            ),
    );
  }
}
