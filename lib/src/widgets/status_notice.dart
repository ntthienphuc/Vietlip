import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// A short, accessible state message with an optional recovery action.
class StatusNotice extends StatelessWidget {
  const StatusNotice({
    super.key,
    required this.title,
    this.detail,
    this.error = false,
    this.busy = false,
    this.action,
    this.onAction,
  });

  final String title;
  final String? detail, action;
  final bool error, busy;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final color = error ? AppColors.error : AppColors.primary;
    return Semantics(
      liveRegion: true,
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: error ? const Color(0xFFFFEFED) : AppColors.primarySoft,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: busy
                      ? SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: color,
                          ),
                        )
                      : Icon(
                          error
                              ? Icons.wifi_off_rounded
                              : Icons.check_circle_outline,
                          size: 22,
                          color: color,
                        ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: TextStyle(
                          color: color,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (detail != null) ...[
                        const SizedBox(height: 4),
                        Text(detail!, style: const TextStyle(height: 1.5)),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            if (action != null && onAction != null) ...[
              const SizedBox(height: 8),
              OutlinedButton(onPressed: onAction, child: Text(action!)),
            ],
          ],
        ),
      ),
    );
  }
}
