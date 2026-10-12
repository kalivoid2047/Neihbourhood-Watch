import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/config/app_config.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = ref.watch(currentUserProvider);
    final settings = ref.watch(alarmSettingsProvider);

    if (user == null) return const LoadingState();

    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: RefreshIndicator(
        onRefresh: () => ref.read(authControllerProvider.notifier).refreshUser(),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 96),
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 32,
                  backgroundColor: AppColors.primary700,
                  child: Text(
                    user.initials,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user.fullName,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        user.email,
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 6,
                        children: [
                          TagChip(
                            label: _roleLabel(user.role),
                            color: AppColors.primary400,
                            icon: Icons.shield_outlined,
                          ),
                          TagChip(
                            label: user.isVerified ? 'Verified' : 'Unverified',
                            color: user.isVerified
                                ? AppColors.success500
                                : AppColors.textSecondary,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),

            const SectionHeader(title: 'Your area'),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.groups_outlined),
                    title: const Text('Neighbourhood'),
                    subtitle: Text(
                      user.primaryNeighborhoodName ?? 'Not assigned yet',
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.home_outlined),
                    title: const Text('Home address'),
                    subtitle: Text(
                      user.address.isEmpty ? 'Not set' : user.address,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.phone_outlined),
                    title: const Text('Phone'),
                    subtitle: Text(
                      user.phoneNumber,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                  ),
                ],
              ),
            ),

            const SectionHeader(title: 'Safety'),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: Icon(
                      settings.enabled
                          ? Icons.notifications_active_rounded
                          : Icons.notifications_off_rounded,
                      color: settings.enabled
                          ? AppColors.success500
                          : AppColors.danger500,
                    ),
                    title: const Text('Alarm settings'),
                    subtitle: Text(
                      settings.enabled
                          ? 'Armed · ${settings.radiusLabel} · '
                              '${settings.minimumSeverity.label} and above'
                          : 'Alarms are switched off',
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => context.push(Routes.alarmSettings),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.contact_phone_outlined),
                    title: const Text('Emergency contacts'),
                    subtitle: const Text(
                      'Who we notify if you raise an SOS',
                      style: TextStyle(color: AppColors.textSecondary),
                    ),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => context.push(Routes.emergencyContacts),
                  ),
                  const Divider(height: 1),
                  ListTile(
                    leading: const Icon(Icons.history_rounded),
                    title: const Text('Alarm history'),
                    trailing: const Icon(Icons.chevron_right_rounded),
                    onTap: () => context.push(Routes.alarmHistory),
                  ),
                ],
              ),
            ),

            const SectionHeader(title: 'About'),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.dns_outlined),
                    title: const Text('Server'),
                    subtitle: Text(
                      AppConfig.apiBaseUrl,
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                    trailing: Text(
                      AppConfig.environment,
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 24),
            OutlinedButton.icon(
              onPressed: () async {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: const Text('Sign out?'),
                    content: const Text(
                      'You will stop receiving alarms about incidents near you '
                      'until you sign back in.',
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.of(context).pop(false),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        onPressed: () => Navigator.of(context).pop(true),
                        style: FilledButton.styleFrom(
                          backgroundColor: AppColors.danger500,
                        ),
                        child: const Text('Sign out'),
                      ),
                    ],
                  ),
                );

                if (confirmed != true) return;
                await ref.read(authControllerProvider.notifier).signOut();
              },
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.danger500,
                side: BorderSide(
                  color: AppColors.danger500.withValues(alpha: 0.5),
                ),
              ),
              icon: const Icon(Icons.logout_rounded),
              label: const Text('Sign out'),
            ),
          ],
        ),
      ),
    );
  }

  static String _roleLabel(String? role) => switch (role) {
        'block_captain' => 'Block Captain',
        'coordinator' => 'Coordinator',
        'police_officer' => 'Police Officer',
        'system_admin' => 'Administrator',
        _ => 'Resident',
      };
}
