/// The authenticated user, mirroring `apps.accounts.models.User`.
class AppUser {
  const AppUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.phoneNumber,
    this.address = '',
    this.latitude,
    this.longitude,
    this.role,
    this.verificationStatus = 'resident',
    this.profilePhoto,
    this.primaryNeighborhoodId,
    this.primaryNeighborhoodName,
  });

  final String id;
  final String email;
  final String fullName;
  final String phoneNumber;
  final String address;
  final double? latitude;
  final double? longitude;

  /// One of `resident`, `block_captain`, `coordinator`, `police_officer`,
  /// `system_admin` — see `apps.accounts.models.Role.Code`.
  final String? role;

  /// One of `resident`, `pending`, `approved`, `rejected`.
  final String verificationStatus;
  final String? profilePhoto;
  final String? primaryNeighborhoodId;
  final String? primaryNeighborhoodName;

  bool get isVerified => verificationStatus == 'approved';

  /// Roles allowed to verify, assign and transition incidents. Mirrors the
  /// backend permission classes so we hide actions the API would reject.
  bool get canModerate => const {
        'block_captain',
        'coordinator',
        'police_officer',
        'system_admin',
      }.contains(role);

  bool get hasHomeLocation => latitude != null && longitude != null;

  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+'));
    if (parts.isEmpty || parts.first.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  factory AppUser.fromJson(Map<String, dynamic> json) {
    // The backend exposes the role either as a nested object or a bare code
    // depending on the serializer, so accept both.
    final rawRole = json['role'];
    final role = rawRole is Map ? rawRole['code'] as String? : rawRole as String?;

    final neighborhood = json['primary_neighborhood'];

    return AppUser(
      id: json['id'].toString(),
      email: json['email'] as String? ?? '',
      fullName: json['full_name'] as String? ?? '',
      phoneNumber: json['phone_number'] as String? ?? '',
      address: json['address'] as String? ?? '',
      latitude: _toDouble(json['latitude']),
      longitude: _toDouble(json['longitude']),
      role: role,
      verificationStatus: json['verification_status'] as String? ?? 'resident',
      profilePhoto: json['profile_photo'] as String?,
      primaryNeighborhoodId: neighborhood is Map
          ? neighborhood['id']?.toString()
          : json['primary_neighborhood_id']?.toString(),
      primaryNeighborhoodName: neighborhood is Map
          ? neighborhood['name'] as String?
          : json['primary_neighborhood_name'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'full_name': fullName,
        'phone_number': phoneNumber,
        'address': address,
        'latitude': latitude,
        'longitude': longitude,
        'role': role,
        'verification_status': verificationStatus,
        'profile_photo': profilePhoto,
        'primary_neighborhood_id': primaryNeighborhoodId,
        'primary_neighborhood_name': primaryNeighborhoodName,
      };

  AppUser copyWith({
    String? fullName,
    String? phoneNumber,
    String? address,
    double? latitude,
    double? longitude,
  }) {
    return AppUser(
      id: id,
      email: email,
      fullName: fullName ?? this.fullName,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      address: address ?? this.address,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      role: role,
      verificationStatus: verificationStatus,
      profilePhoto: profilePhoto,
      primaryNeighborhoodId: primaryNeighborhoodId,
      primaryNeighborhoodName: primaryNeighborhoodName,
    );
  }

  static double? _toDouble(dynamic value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString());
  }
}

/// An emergency contact notified when the user raises an SOS.
class EmergencyContact {
  const EmergencyContact({
    required this.id,
    required this.name,
    required this.phoneNumber,
    this.relationship = '',
    this.priority = 1,
    this.canReceiveSos = true,
  });

  final String id;
  final String name;
  final String phoneNumber;
  final String relationship;
  final int priority;
  final bool canReceiveSos;

  factory EmergencyContact.fromJson(Map<String, dynamic> json) {
    return EmergencyContact(
      id: json['id'].toString(),
      name: json['name'] as String? ?? '',
      phoneNumber: json['phone_number'] as String? ?? '',
      relationship: json['relationship'] as String? ?? '',
      priority: (json['priority'] as num?)?.toInt() ?? 1,
      canReceiveSos: json['can_receive_sos'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
        'name': name,
        'phone_number': phoneNumber,
        'relationship': relationship,
        'priority': priority,
        'can_receive_sos': canReceiveSos,
      };
}
