import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../../auth/data/user.dart';

final _contactsProvider = FutureProvider<List<EmergencyContact>>((ref) {
  return ref.watch(authRepositoryProvider).emergencyContacts();
});

/// People the backend SMSes when the user raises an SOS.
class EmergencyContactsScreen extends ConsumerWidget {
  const EmergencyContactsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contactsAsync = ref.watch(_contactsProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Emergency contacts')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _addContact(context, ref),
        backgroundColor: AppColors.primary500,
        foregroundColor: AppColors.ink950,
        icon: const Icon(Icons.person_add_alt_rounded),
        label: const Text('Add contact'),
      ),
      body: contactsAsync.when(
        loading: () => const LoadingState(),
        error: (error, _) => ErrorState(
          message: error is ApiException
              ? error.message
              : 'Could not load your contacts.',
          isOffline: error is ApiException && error.isConnectivity,
          onRetry: () => ref.invalidate(_contactsProvider),
        ),
        data: (contacts) => contacts.isEmpty
            ? const EmptyState(
                icon: Icons.contact_phone_outlined,
                title: 'No emergency contacts',
                message:
                    'Add someone we should text if you raise an SOS. They do '
                    'not need the app.',
              )
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                itemCount: contacts.length,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final contact = contacts[index];
                  return Card(
                    child: ListTile(
                      leading: CircleAvatar(
                        backgroundColor: AppColors.primary700,
                        child: Text('${contact.priority}'),
                      ),
                      title: Text(
                        contact.name,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      subtitle: Text(
                        [
                          contact.phoneNumber,
                          if (contact.relationship.isNotEmpty)
                            contact.relationship,
                        ].join(' · '),
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                      trailing: IconButton(
                        icon: const Icon(
                          Icons.delete_outline_rounded,
                          color: AppColors.danger500,
                        ),
                        onPressed: () async {
                          await ref
                              .read(authRepositoryProvider)
                              .deleteEmergencyContact(contact.id);
                          ref.invalidate(_contactsProvider);
                        },
                      ),
                    ),
                  );
                },
              ),
      ),
    );
  }

  Future<void> _addContact(BuildContext context, WidgetRef ref) async {
    final nameController = TextEditingController();
    final phoneController = TextEditingController();
    final relationshipController = TextEditingController();

    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.ink900,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          left: 20,
          right: 20,
          top: 20,
          bottom: MediaQuery.of(context).viewInsets.bottom + 24,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Add emergency contact',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: nameController,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Name',
                prefixIcon: Icon(Icons.person_outline_rounded),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: phoneController,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Phone number',
                hintText: '+27821234567',
                prefixIcon: Icon(Icons.phone_outlined),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: relationshipController,
              decoration: const InputDecoration(
                labelText: 'Relationship (optional)',
                prefixIcon: Icon(Icons.diversity_3_outlined),
              ),
            ),
            const SizedBox(height: 20),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: const Text('Save contact'),
            ),
          ],
        ),
      ),
    );

    if (saved != true) return;

    final name = nameController.text.trim();
    final phone = phoneController.text.trim();
    if (name.isEmpty || phone.isEmpty) return;

    try {
      final existing = ref.read(_contactsProvider).value ?? const [];
      await ref.read(authRepositoryProvider).addEmergencyContact(
            EmergencyContact(
              id: '',
              name: name,
              phoneNumber: phone,
              relationship: relationshipController.text.trim(),
              // The backend enforces one contact per priority, so take the
              // next free slot rather than colliding on 1.
              priority: existing.length + 1,
            ),
          );
      ref.invalidate(_contactsProvider);
    } on ApiException catch (error) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(error.message)));
    }
  }
}
