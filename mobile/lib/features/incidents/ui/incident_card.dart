import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets.dart';
import '../data/incident.dart';

/// List row for an incident. The severity stripe down the left edge is the
/// fastest thing to scan, which is what matters in a safety feed.
class IncidentCard extends StatelessWidget {
  const IncidentCard({super.key, required this.incident, this.onTap});

  final Incident incident;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final severity = incident.severity;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(width: 4, color: severity.color),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            incident.category.icon,
                            size: 16,
                            color: AppColors.textSecondary,
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              incident.category.label,
                              style: const TextStyle(
                                color: AppColors.textSecondary,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          Text(
                            formatRelative(incident.occurredAt),
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),

                      Text(
                        incident.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: AppColors.textPrimary,
                          height: 1.25,
                        ),
                      ),

                      if (incident.address.isNotEmpty) ...[
                        const SizedBox(height: 6),
                        Row(
                          children: [
                            const Icon(
                              Icons.place_outlined,
                              size: 14,
                              color: AppColors.textSecondary,
                            ),
                            const SizedBox(width: 4),
                            Expanded(
                              child: Text(
                                incident.address,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  color: AppColors.textSecondary,
                                  fontSize: 13,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],

                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          SeverityChip(
                            severity: severity,
                            filled: severity == IncidentSeverity.red,
                          ),
                          TagChip(
                            label: incident.status.label,
                            color: incident.status.color,
                          ),
                          if (incident.distanceLabel != null)
                            TagChip(
                              label: incident.distanceLabel!,
                              color: AppColors.primary400,
                              icon: Icons.near_me_outlined,
                            ),
                          if (!incident.isVerified)
                            const TagChip(
                              label: 'Unverified',
                              color: AppColors.textSecondary,
                              icon: Icons.help_outline_rounded,
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
