import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/location/location_service.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../../incidents/data/incident.dart';
import '../data/alarm_settings.dart';

/// Every control over when the phone makes a noise, in one place.
class AlarmSettingsScreen extends ConsumerWidget {
  const AlarmSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final settings = ref.watch(alarmSettingsProvider);
    final controller = ref.read(alarmSettingsProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Alarm settings'),
        actions: [
          IconButton(
            tooltip: 'Alarm history',
            onPressed: () => context.push(Routes.alarmHistory),
            icon: const Icon(Icons.history_rounded),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 40),
        children: [
          Card(
            child: SwitchListTile.adaptive(
              value: settings.enabled,
              onChanged: controller.setEnabled,
              title: const Text(
                'Sound an alarm for nearby incidents',
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
              subtitle: Text(
                settings.enabled
                    ? 'Your phone will alert you when something happens close by.'
                    : 'You will not be alerted about incidents near you.',
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              secondary: Icon(
                settings.enabled
                    ? Icons.notifications_active_rounded
                    : Icons.notifications_off_rounded,
                color: settings.enabled
                    ? AppColors.success500
                    : AppColors.textSecondary,
              ),
            ),
          ),

          const _PermissionCard(),

          // ── Radius ────────────────────────────────────────────────────────
          const SectionHeader(
            title: 'Alarm radius',
            subtitle: 'How close an incident must be before you are alarmed.',
          ),
          Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Within'),
                      Text(
                        settings.radiusLabel,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: AppColors.primary300,
                        ),
                      ),
                    ],
                  ),
                  Slider(
                    value: settings.radiusMetres.toDouble().clamp(
                          AlarmSettings.minRadiusMetres.toDouble(),
                          AlarmSettings.maxRadiusMetres.toDouble(),
                        ),
                    min: AlarmSettings.minRadiusMetres.toDouble(),
                    max: AlarmSettings.maxRadiusMetres.toDouble(),
                    divisions: 79,
                    label: settings.radiusLabel,
                    onChanged: (value) =>
                        controller.setRadius((value / 250).round() * 250),
                  ),
                  const Text(
                    'A tighter radius means fewer alarms, but you may miss '
                    'something a few streets over.',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                      height: 1.35,
                    ),
                  ),
                  const SizedBox(height: 8),
                ],
              ),
            ),
          ),

          // ── Severity threshold ────────────────────────────────────────────
          const SectionHeader(
            title: 'What sounds the alarm',
            subtitle:
                'Anything below this still arrives as a notification, just '
                'without noise.',
          ),
          Card(
            child: Column(
              children: IncidentSeverity.values.reversed.map((severity) {
                final selected = settings.minimumSeverity == severity;
                return ListTile(
                  onTap: () => controller.setMinimumSeverity(severity),
                  leading: Icon(
                    selected
                        ? Icons.radio_button_checked_rounded
                        : Icons.radio_button_unchecked_rounded,
                    color: selected ? severity.color : AppColors.textSecondary,
                  ),
                  title: Row(
                    children: [
                      Container(
                        width: 10,
                        height: 10,
                        decoration: BoxDecoration(
                          color: severity.color,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 10),
                      Text('${severity.label} and above'),
                    ],
                  ),
                  subtitle: Text(
                    _severityHint(severity),
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                );
              }).toList(),
            ),
          ),

          // ── Quiet hours ───────────────────────────────────────────────────
          const SectionHeader(title: 'Quiet hours'),
          Card(
            child: Column(
              children: [
                SwitchListTile.adaptive(
                  value: settings.quietHoursEnabled,
                  onChanged: controller.setQuietHoursEnabled,
                  title: const Text('Silence alarms overnight'),
                  subtitle: Text(
                    settings.quietHoursEnabled
                        ? settings.quietHours.label
                        : 'Alarms sound at any hour',
                    style: const TextStyle(color: AppColors.textSecondary),
                  ),
                ),
                if (settings.quietHoursEnabled) ...[
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.bedtime_outlined),
                    title: const Text('Quiet from'),
                    trailing: Text(
                      QuietHours(
                        startMinute: settings.quietHours.startMinute,
                        endMinute: settings.quietHours.endMinute,
                      ).label,
                      style: const TextStyle(color: AppColors.primary300),
                    ),
                    onTap: () => _pickQuietHours(context, ref, settings),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: Icon(
                      Icons.warning_amber_rounded,
                      color: settings.criticalBypassesQuietHours
                          ? AppColors.danger500
                          : AppColors.textSecondary,
                    ),
                    title: const Text('Critical incidents still alarm'),
                    subtitle: const Text(
                      'Recommended. A critical incident metres from your door '
                      'should wake you.',
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                    trailing: Switch.adaptive(
                      value: settings.criticalBypassesQuietHours,
                      onChanged: (value) => controller.update(
                        settings.copyWith(criticalBypassesQuietHours: value),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),

          // ── Snooze ────────────────────────────────────────────────────────
          const SectionHeader(title: 'Snooze'),
          Card(
            child: settings.isSnoozed
                ? ListTile(
                    leading: const Icon(
                      Icons.snooze_rounded,
                      color: AppColors.warning400,
                    ),
                    title: Text(
                      'Snoozed until ${formatDateTime(settings.snoozedUntil!)}',
                    ),
                    subtitle: const Text(
                      'Critical incidents still break through.',
                      style: TextStyle(color: AppColors.textSecondary),
                    ),
                    trailing: TextButton(
                      onPressed: controller.clearSnooze,
                      child: const Text('Resume'),
                    ),
                  )
                : Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () =>
                                controller.snooze(const Duration(hours: 1)),
                            child: const Text('1 hour'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: OutlinedButton(
                            onPressed: () =>
                                controller.snooze(const Duration(hours: 8)),
                            child: const Text('8 hours'),
                          ),
                        ),
                      ],
                    ),
                  ),
          ),

          // ── Categories ────────────────────────────────────────────────────
          const SectionHeader(
            title: 'Mute categories',
            subtitle: 'Muted categories never alarm, whatever their severity.',
          ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: IncidentCategory.values.map((category) {
                  final muted = settings.mutedCategories.contains(category.value);
                  return FilterChip(
                    avatar: Icon(
                      muted ? Icons.volume_off_rounded : category.icon,
                      size: 16,
                    ),
                    label: Text(category.label),
                    selected: muted,
                    selectedColor: AppColors.danger500.withValues(alpha: 0.2),
                    checkmarkColor: AppColors.danger500,
                    onSelected: (_) => controller.toggleCategory(category),
                  );
                }).toList(),
              ),
            ),
          ),

          // ── Advanced ──────────────────────────────────────────────────────
          const SectionHeader(title: 'Advanced'),
          Card(
            child: Column(
              children: [
                SwitchListTile.adaptive(
                  value: settings.includeUnverified,
                  onChanged: controller.setIncludeUnverified,
                  title: const Text('Alarm before a coordinator verifies'),
                  subtitle: const Text(
                    'Faster warnings, with a higher chance of a false alarm.',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  ),
                ),
                const Divider(height: 1),
                SwitchListTile.adaptive(
                  value: settings.vibrate,
                  onChanged: controller.setVibrate,
                  title: const Text('Vibrate with the alarm'),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.timer_outlined),
                  title: const Text('Check for incidents every'),
                  trailing: DropdownButton<int>(
                    value: settings.pollIntervalSeconds,
                    underline: const SizedBox.shrink(),
                    items: const [
                      DropdownMenuItem(value: 30, child: Text('30 seconds')),
                      DropdownMenuItem(value: 60, child: Text('1 minute')),
                      DropdownMenuItem(value: 300, child: Text('5 minutes')),
                      DropdownMenuItem(value: 600, child: Text('10 minutes')),
                    ],
                    onChanged: (value) => value == null
                        ? null
                        : controller.update(
                            settings.copyWith(pollIntervalSeconds: value),
                          ),
                  ),
                ),
              ],
            ),
          ),
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 8, 4, 0),
            child: Text(
              'While the app is closed, your phone can only check every 15 '
              'minutes or so. Push notifications cover the gap when they are '
              'available.',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
                height: 1.4,
              ),
            ),
          ),

          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: () async {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Playing the alarm for a few seconds…'),
                ),
              );
              await ref.read(alarmEngineProvider).testAlarm();
            },
            icon: const Icon(Icons.volume_up_rounded),
            label: const Text('Test the alarm'),
          ),
          const SizedBox(height: 8),
          const Text(
            'Check now that you can hear it — not when it matters.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
          ),
        ],
      ),
    );
  }

  static String _severityHint(IncidentSeverity severity) => switch (severity) {
        IncidentSeverity.red => 'Only life-threatening incidents.',
        IncidentSeverity.yellow => 'Recommended for most people.',
        IncidentSeverity.blue => 'Includes routine reports — expect more noise.',
        IncidentSeverity.green => 'Everything, including minor reports.',
      };

  Future<void> _pickQuietHours(
    BuildContext context,
    WidgetRef ref,
    AlarmSettings settings,
  ) async {
    final start = await showTimePicker(
      context: context,
      helpText: 'Quiet hours start',
      initialTime: TimeOfDay(
        hour: settings.quietHours.startMinute ~/ 60,
        minute: settings.quietHours.startMinute % 60,
      ),
    );
    if (start == null || !context.mounted) return;

    final end = await showTimePicker(
      context: context,
      helpText: 'Quiet hours end',
      initialTime: TimeOfDay(
        hour: settings.quietHours.endMinute ~/ 60,
        minute: settings.quietHours.endMinute % 60,
      ),
    );
    if (end == null) return;

    await ref.read(alarmSettingsProvider.notifier).setQuietHours(
          QuietHours(
            startMinute: start.hour * 60 + start.minute,
            endMinute: end.hour * 60 + end.minute,
          ),
        );
  }
}

/// Nags — once, politely — about the permissions the alarm actually needs.
class _PermissionCard extends ConsumerWidget {
  const _PermissionCard();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final permission = ref.watch(locationPermissionProvider).value;
    if (permission == null || permission == LocationPermissionState.granted) {
      return const SizedBox.shrink();
    }

    final isBlocking = !permission.isUsable;
    final colour = isBlocking ? AppColors.danger500 : AppColors.warning400;

    return Container(
      margin: const EdgeInsets.only(top: 16),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: colour.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: colour.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.location_on_outlined, color: colour, size: 20),
              const SizedBox(width: 8),
              Text(
                isBlocking ? 'Location is off' : 'Background location is off',
                style: TextStyle(color: colour, fontWeight: FontWeight.w700),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            permission.message,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              FilledButton(
                style: FilledButton.styleFrom(
                  minimumSize: const Size(0, 40),
                  backgroundColor: colour,
                ),
                onPressed: () async {
                  await ref.read(locationServiceProvider).requestPermission();
                  ref.invalidate(locationPermissionProvider);
                },
                child: const Text('Fix this'),
              ),
              const SizedBox(width: 8),
              TextButton(
                onPressed: () =>
                    ref.read(locationServiceProvider).openSystemSettings(),
                child: const Text('Open settings'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
