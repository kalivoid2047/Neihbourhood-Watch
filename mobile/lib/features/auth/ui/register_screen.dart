import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../app/router.dart';
import '../../../core/api/api_exception.dart';
import '../../../core/location/location_service.dart';
import '../../../core/theme/app_theme.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _fullName = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _nationalId = TextEditingController();
  final _address = TextEditingController();
  final _password = TextEditingController();
  final _confirmPassword = TextEditingController();

  bool _submitting = false;
  bool _obscure = true;
  bool _useCurrentLocation = true;
  String? _error;
  Map<String, String> _fieldErrors = const {};

  @override
  void dispose() {
    for (final controller in [
      _fullName,
      _email,
      _phone,
      _nationalId,
      _address,
      _password,
      _confirmPassword,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _submitting = true;
      _error = null;
      _fieldErrors = const {};
    });

    try {
      // Registering with coordinates lets the backend place the user in a
      // neighbourhood, which is what the alarm falls back to when GPS is off.
      double? latitude;
      double? longitude;
      if (_useCurrentLocation) {
        final location = ref.read(locationServiceProvider);
        final state = await location.requestPermission();
        if (state.isUsable) {
          final position = await location.currentPosition();
          latitude = position?.latitude;
          longitude = position?.longitude;
        }
      }

      await ref.read(authRepositoryProvider).register(
            email: _email.text.trim(),
            fullName: _fullName.text.trim(),
            phoneNumber: _phone.text.trim(),
            nationalId: _nationalId.text.trim(),
            password: _password.text,
            address: _address.text.trim(),
            latitude: latitude,
            longitude: longitude,
          );

      // The backend issues an OTP challenge on registration.
      await ref.read(authRepositoryProvider).requestOtp(
            email: _email.text.trim(),
            purpose: 'registration',
          );

      if (!mounted) return;
      // The pushed route's result is irrelevant here — the OTP screen either
      // signs the user in itself or sends them to the login screen.
      unawaited(
        context.push(
          Routes.otp,
          extra: {'email': _email.text.trim(), 'purpose': 'registration'},
        ),
      );
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error.message;
        _fieldErrors = error.fieldErrors;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = 'Could not create your account. Please try again.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_error != null)
                    Container(
                      margin: const EdgeInsets.only(bottom: 16),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppColors.danger500.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: AppColors.danger500.withValues(alpha: 0.4),
                        ),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: AppColors.danger500),
                      ),
                    ),

                  _field(
                    controller: _fullName,
                    label: 'Full name',
                    icon: Icons.person_outline_rounded,
                    errorKey: 'full_name',
                    validator: (v) =>
                        (v == null || v.trim().length < 3) ? 'Enter your full name' : null,
                  ),
                  _field(
                    controller: _email,
                    label: 'Email address',
                    icon: Icons.mail_outline_rounded,
                    errorKey: 'email',
                    keyboardType: TextInputType.emailAddress,
                    validator: (v) {
                      final text = v?.trim() ?? '';
                      if (text.isEmpty) return 'Enter your email address';
                      if (!text.contains('@')) return 'Enter a valid email address';
                      return null;
                    },
                  ),
                  _field(
                    controller: _phone,
                    label: 'Phone number',
                    hint: '+27821234567',
                    icon: Icons.phone_outlined,
                    errorKey: 'phone_number',
                    keyboardType: TextInputType.phone,
                    validator: (v) {
                      final text = (v ?? '').trim();
                      // Matches the backend's phone_validator.
                      if (!RegExp(r'^\+?[0-9]{9,15}$').hasMatch(text)) {
                        return 'Use an international format, e.g. +27821234567';
                      }
                      return null;
                    },
                  ),
                  _field(
                    controller: _nationalId,
                    label: 'ID number',
                    icon: Icons.badge_outlined,
                    errorKey: 'national_id',
                    validator: (v) => (v == null || v.trim().isEmpty)
                        ? 'Enter your ID number'
                        : null,
                  ),
                  _field(
                    controller: _address,
                    label: 'Home address',
                    icon: Icons.home_outlined,
                    errorKey: 'address',
                    maxLines: 2,
                    validator: (v) => null,
                  ),
                  _field(
                    controller: _password,
                    label: 'Password',
                    icon: Icons.lock_outline_rounded,
                    errorKey: 'password',
                    obscure: _obscure,
                    suffix: IconButton(
                      onPressed: () => setState(() => _obscure = !_obscure),
                      icon: Icon(
                        _obscure
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                    ),
                    validator: (v) => (v == null || v.length < 8)
                        ? 'Use at least 8 characters'
                        : null,
                  ),
                  _field(
                    controller: _confirmPassword,
                    label: 'Confirm password',
                    icon: Icons.lock_outline_rounded,
                    obscure: _obscure,
                    validator: (v) =>
                        v != _password.text ? 'Passwords do not match' : null,
                  ),

                  SwitchListTile.adaptive(
                    value: _useCurrentLocation,
                    onChanged: (value) =>
                        setState(() => _useCurrentLocation = value),
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Use my current location'),
                    subtitle: const Text(
                      'Helps us alarm you about incidents near home, even when '
                      'GPS is off later.',
                      style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                    ),
                  ),
                  const SizedBox(height: 16),

                  FilledButton(
                    onPressed: _submitting ? null : _submit,
                    child: _submitting
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.2,
                              color: AppColors.ink950,
                            ),
                          )
                        : const Text('Create account'),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'We will send a one-time code to verify your email.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    String? hint,
    String? errorKey,
    TextInputType? keyboardType,
    bool obscure = false,
    int maxLines = 1,
    Widget? suffix,
    String? Function(String?)? validator,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: TextFormField(
        controller: controller,
        keyboardType: keyboardType,
        obscureText: obscure,
        maxLines: obscure ? 1 : maxLines,
        autocorrect: false,
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          prefixIcon: Icon(icon),
          suffixIcon: suffix,
          errorText: errorKey == null ? null : _fieldErrors[errorKey],
        ),
        validator: validator,
      ),
    );
  }
}
