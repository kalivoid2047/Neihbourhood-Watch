import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geocoding/geocoding.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../data/incident.dart';

/// Three-step report wizard: what → where → evidence.
///
/// Ordered so the fastest-to-answer question comes first; someone reporting
/// from the scene can get through the first step in two taps.
class ReportIncidentScreen extends ConsumerStatefulWidget {
  const ReportIncidentScreen({super.key});

  @override
  ConsumerState<ReportIncidentScreen> createState() =>
      _ReportIncidentScreenState();
}

class _ReportIncidentScreenState extends ConsumerState<ReportIncidentScreen> {
  final _pageController = PageController();
  final _titleController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _addressController = TextEditingController();

  int _step = 0;

  IncidentCategory? _category;
  IncidentSeverity _severity = IncidentSeverity.yellow;
  DateTime _occurredAt = DateTime.now();
  LatLng? _location;
  final List<XFile> _photos = [];

  bool _submitting = false;
  bool _resolvingAddress = false;
  double _uploadProgress = 0;
  String? _error;

  @override
  void initState() {
    super.initState();
    _prefillLocation();
  }

  @override
  void dispose() {
    _pageController.dispose();
    _titleController.dispose();
    _descriptionController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  Future<void> _prefillLocation() async {
    final position = await ref.read(currentPositionProvider.future);
    if (position == null || !mounted) return;
    setState(() => _location = LatLng(position.latitude, position.longitude));
    unawaited(_resolveAddress());
  }

  /// Turns the pinned coordinates into a street address, as a convenience.
  /// Failure is silent by design — the user can always type the address, and
  /// a geocoding error is not worth interrupting a report for.
  Future<void> _resolveAddress() async {
    final location = _location;
    if (location == null) return;

    setState(() => _resolvingAddress = true);
    try {
      final placemarks = await Geocoding().placemarkFromCoordinates(
        location.latitude,
        location.longitude,
      );
      if (!mounted || placemarks.isEmpty) return;

      final place = placemarks.first;
      final parts = [place.street, place.subLocality, place.locality]
          .where((part) => part != null && part.isNotEmpty)
          .join(', ');

      if (parts.isNotEmpty && _addressController.text.isEmpty) {
        _addressController.text = parts;
      }
    } catch (_) {
      // No geocoder available, or no network — leave the field for the user.
    } finally {
      if (mounted) setState(() => _resolvingAddress = false);
    }
  }

  bool get _canContinue => switch (_step) {
        0 => _category != null && _titleController.text.trim().length >= 4,
        1 => _location != null,
        _ => true,
      };

  void _next() {
    if (_step < 2) {
      setState(() => _step++);
      _pageController.animateToPage(
        _step,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    } else {
      _submit();
    }
  }

  void _back() {
    if (_step == 0) {
      context.pop();
      return;
    }
    setState(() => _step--);
    _pageController.animateToPage(
      _step,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
    );
  }

  Future<void> _addPhoto(ImageSource source) async {
    try {
      final picker = ImagePicker();
      final photo = await picker.pickImage(
        source: source,
        maxWidth: 2000,
        imageQuality: 80,
      );
      if (photo != null && mounted) setState(() => _photos.add(photo));
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not attach that photo: $error')),
      );
    }
  }

  Future<void> _submit() async {
    final location = _location;
    if (location == null || _category == null) return;

    setState(() {
      _submitting = true;
      _error = null;
      _uploadProgress = 0;
    });

    try {
      final repo = ref.read(incidentsRepositoryProvider);
      final incident = await repo.create(
        title: _titleController.text.trim(),
        description: _descriptionController.text.trim(),
        category: _category!,
        severity: _severity,
        latitude: location.latitude,
        longitude: location.longitude,
        address: _addressController.text.trim(),
        occurredAt: _occurredAt,
        neighborhoodId: ref.read(currentUserProvider)?.primaryNeighborhoodId,
      );

      // Upload evidence one at a time so a single failure does not lose the
      // whole report — the incident itself is already saved by this point.
      for (var i = 0; i < _photos.length; i++) {
        try {
          await repo.uploadMedia(
            incidentId: incident.id,
            file: File(_photos[i].path),
            mediaType: 'image',
            onProgress: (progress) {
              if (mounted) {
                setState(() => _uploadProgress = (i + progress) / _photos.length);
              }
            },
          );
        } catch (error) {
          debugPrintStack(label: 'Media upload failed: $error');
        }
      }

      ref.invalidate(incidentFeedProvider);
      ref.invalidate(nearbyIncidentsProvider);

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Report submitted. Thank you.')),
      );
      context.pushReplacement(Routes.incidentDetail(incident.id));
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Could not submit your report. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          switch (_step) {
            0 => 'What happened?',
            1 => 'Where did it happen?',
            _ => 'Add evidence',
          },
        ),
        leading: IconButton(
          onPressed: _submitting ? null : _back,
          icon: const Icon(Icons.arrow_back_rounded),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(4),
          child: LinearProgressIndicator(
            value: (_step + 1) / 3,
            minHeight: 4,
            backgroundColor: AppColors.ink800,
          ),
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                _WhatStep(
                  category: _category,
                  severity: _severity,
                  titleController: _titleController,
                  descriptionController: _descriptionController,
                  occurredAt: _occurredAt,
                  onCategoryChanged: (value) => setState(() => _category = value),
                  onSeverityChanged: (value) => setState(() => _severity = value),
                  onOccurredAtChanged: (value) =>
                      setState(() => _occurredAt = value),
                  onTitleChanged: () => setState(() {}),
                ),
                _WhereStep(
                  location: _location,
                  addressController: _addressController,
                  resolvingAddress: _resolvingAddress,
                  onLocationChanged: (value) {
                    setState(() => _location = value);
                    unawaited(_resolveAddress());
                  },
                  onUseCurrentLocation: _prefillLocation,
                ),
                _EvidenceStep(
                  photos: _photos,
                  onAdd: _addPhoto,
                  onRemove: (index) => setState(() => _photos.removeAt(index)),
                  severity: _severity,
                  category: _category,
                  title: _titleController.text,
                ),
              ],
            ),
          ),

          if (_error != null)
            Container(
              width: double.infinity,
              color: AppColors.danger500.withValues(alpha: 0.12),
              padding: const EdgeInsets.all(14),
              child: Text(
                _error!,
                style: const TextStyle(color: AppColors.danger500),
              ),
            ),

          if (_submitting && _photos.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Column(
                children: [
                  LinearProgressIndicator(value: _uploadProgress),
                  const SizedBox(height: 6),
                  Text(
                    'Uploading evidence… ${(_uploadProgress * 100).round()}%',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ),

          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
              child: FilledButton(
                onPressed: (_canContinue && !_submitting) ? _next : null,
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: AppColors.ink950,
                        ),
                      )
                    : Text(_step == 2 ? 'Submit report' : 'Continue'),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _WhatStep extends StatelessWidget {
  const _WhatStep({
    required this.category,
    required this.severity,
    required this.titleController,
    required this.descriptionController,
    required this.occurredAt,
    required this.onCategoryChanged,
    required this.onSeverityChanged,
    required this.onOccurredAtChanged,
    required this.onTitleChanged,
  });

  final IncidentCategory? category;
  final IncidentSeverity severity;
  final TextEditingController titleController;
  final TextEditingController descriptionController;
  final DateTime occurredAt;
  final ValueChanged<IncidentCategory> onCategoryChanged;
  final ValueChanged<IncidentSeverity> onSeverityChanged;
  final ValueChanged<DateTime> onOccurredAtChanged;
  final VoidCallback onTitleChanged;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      children: [
        const SectionHeader(title: 'Category'),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 2.4,
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          children: IncidentCategory.values.map((value) {
            final selected = category == value;
            return InkWell(
              onTap: () => onCategoryChanged(value),
              borderRadius: BorderRadius.circular(14),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: selected
                      ? AppColors.primary500.withValues(alpha: 0.16)
                      : AppColors.ink800,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(
                    color: selected ? AppColors.primary400 : AppColors.border,
                    width: selected ? 1.6 : 1,
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      value.icon,
                      size: 20,
                      color: selected
                          ? AppColors.primary300
                          : AppColors.textSecondary,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        value.label,
                        style: TextStyle(
                          fontSize: 13,
                          height: 1.2,
                          fontWeight:
                              selected ? FontWeight.w600 : FontWeight.w400,
                          color: selected
                              ? AppColors.textPrimary
                              : AppColors.textSecondary,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          }).toList(),
        ),

        const SectionHeader(
          title: 'How serious is it?',
          subtitle: 'Critical alarms everyone nearby, even during quiet hours.',
        ),
        Row(
          children: IncidentSeverity.values.reversed.map((value) {
            final selected = severity == value;
            return Expanded(
              child: Padding(
                padding: const EdgeInsets.only(right: 8),
                child: InkWell(
                  onTap: () => onSeverityChanged(value),
                  borderRadius: BorderRadius.circular(12),
                  child: Container(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: selected
                          ? value.color.withValues(alpha: 0.2)
                          : AppColors.ink800,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: selected ? value.color : AppColors.border,
                        width: selected ? 1.6 : 1,
                      ),
                    ),
                    child: Column(
                      children: [
                        Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            color: value.color,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          value.label,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 11,
                            color: selected
                                ? AppColors.textPrimary
                                : AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          }).toList(),
        ),

        const SectionHeader(title: 'Details'),
        TextField(
          controller: titleController,
          onChanged: (_) => onTitleChanged(),
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(
            labelText: 'Short summary',
            hintText: 'e.g. Break-in at the corner shop',
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: descriptionController,
          maxLines: 5,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(
            labelText: 'What happened?',
            hintText:
                'Describe what you saw — vehicles, descriptions, direction '
                'of travel. Do not put yourself at risk to gather detail.',
            alignLabelWithHint: true,
          ),
        ),

        const SectionHeader(title: 'When'),
        Card(
          child: ListTile(
            leading: const Icon(Icons.schedule_rounded),
            title: Text(formatDateTime(occurredAt)),
            subtitle: Text(
              formatRelative(occurredAt),
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            trailing: const Icon(Icons.edit_calendar_outlined),
            onTap: () async {
              final date = await showDatePicker(
                context: context,
                initialDate: occurredAt,
                firstDate: DateTime.now().subtract(const Duration(days: 30)),
                lastDate: DateTime.now(),
              );
              if (date == null || !context.mounted) return;

              final time = await showTimePicker(
                context: context,
                initialTime: TimeOfDay.fromDateTime(occurredAt),
              );
              if (time == null) return;

              onOccurredAtChanged(
                DateTime(
                  date.year,
                  date.month,
                  date.day,
                  time.hour,
                  time.minute,
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _WhereStep extends StatelessWidget {
  const _WhereStep({
    required this.location,
    required this.addressController,
    required this.resolvingAddress,
    required this.onLocationChanged,
    required this.onUseCurrentLocation,
  });

  final LatLng? location;
  final TextEditingController addressController;
  final bool resolvingAddress;
  final ValueChanged<LatLng> onLocationChanged;
  final VoidCallback onUseCurrentLocation;

  @override
  Widget build(BuildContext context) {
    if (location == null) {
      return EmptyState(
        icon: Icons.location_searching_rounded,
        title: 'Finding your location',
        message:
            'We need a location for the report so neighbours nearby can be '
            'alerted.',
        action: FilledButton(
          onPressed: onUseCurrentLocation,
          child: const Text('Try again'),
        ),
      );
    }

    return Column(
      children: [
        Expanded(
          child: Stack(
            children: [
              FlutterMap(
                options: MapOptions(
                  initialCenter: location!,
                  initialZoom: 16,
                  onTap: (_, point) => onLocationChanged(point),
                ),
                children: [
                  TileLayer(
                    urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    userAgentPackageName: 'za.co.neighbourhoodwatch.nhw_mobile',
                  ),
                  MarkerLayer(
                    markers: [
                      Marker(
                        point: location!,
                        width: 44,
                        height: 44,
                        child: const Icon(
                          Icons.place_rounded,
                          size: 44,
                          color: AppColors.danger500,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              Positioned(
                top: 12,
                left: 16,
                right: 16,
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: AppColors.ink900.withValues(alpha: 0.92),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: const Text(
                    'Tap the map to move the pin to the exact spot',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
                ),
              ),
              Positioned(
                right: 16,
                bottom: 16,
                child: FloatingActionButton.small(
                  heroTag: 'use-current',
                  onPressed: onUseCurrentLocation,
                  backgroundColor: AppColors.ink800,
                  foregroundColor: AppColors.primary300,
                  child: const Icon(Icons.my_location_rounded),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 4),
          child: TextField(
            controller: addressController,
            textCapitalization: TextCapitalization.words,
            decoration: InputDecoration(
              labelText: 'Address or landmark',
              prefixIcon: const Icon(Icons.place_outlined),
              suffixIcon: resolvingAddress
                  ? const Padding(
                      padding: EdgeInsets.all(14),
                      child: SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    )
                  : null,
            ),
          ),
        ),
      ],
    );
  }
}

class _EvidenceStep extends StatelessWidget {
  const _EvidenceStep({
    required this.photos,
    required this.onAdd,
    required this.onRemove,
    required this.severity,
    required this.category,
    required this.title,
  });

  final List<XFile> photos;
  final ValueChanged<ImageSource> onAdd;
  final ValueChanged<int> onRemove;
  final IncidentSeverity severity;
  final IncidentCategory? category;
  final String title;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      children: [
        Container(
          padding: const EdgeInsets.all(14),
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
                Icons.health_and_safety_outlined,
                color: AppColors.warning400,
                size: 20,
              ),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Only photograph what is safe to photograph. Your safety '
                  'comes before evidence.',
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

        const SectionHeader(title: 'Photos'),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => onAdd(ImageSource.camera),
                icon: const Icon(Icons.photo_camera_outlined),
                label: const Text('Camera'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => onAdd(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('Gallery'),
              ),
            ),
          ],
        ),

        if (photos.isNotEmpty) ...[
          const SizedBox(height: 14),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: List.generate(photos.length, (index) {
              return Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.file(
                      File(photos[index].path),
                      width: 100,
                      height: 100,
                      fit: BoxFit.cover,
                    ),
                  ),
                  Positioned(
                    top: 2,
                    right: 2,
                    child: GestureDetector(
                      onTap: () => onRemove(index),
                      child: Container(
                        padding: const EdgeInsets.all(3),
                        decoration: const BoxDecoration(
                          color: AppColors.ink950,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.close_rounded,
                          size: 15,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                ],
              );
            }),
          ),
        ],

        const SectionHeader(title: 'Review'),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    SeverityChip(severity: severity, filled: true),
                    const SizedBox(width: 8),
                    if (category != null)
                      TagChip(
                        label: category!.label,
                        color: AppColors.textSecondary,
                        icon: category!.icon,
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  title.isEmpty ? 'Untitled report' : title,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  severity == IncidentSeverity.red
                      ? 'This will alarm neighbours nearby immediately, '
                          'including during their quiet hours.'
                      : 'Neighbours nearby will be notified according to their '
                          'own alarm settings.',
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
