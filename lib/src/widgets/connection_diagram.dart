import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

/// Explains the local connection without implying that either device is ready.
class ConnectionDiagram extends StatelessWidget {
  const ConnectionDiagram({super.key});
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
    decoration: BoxDecoration(
      color: AppColors.primarySoft,
      borderRadius: BorderRadius.circular(24),
    ),
    child: const Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Flexible(
          child: _Device(icon: Icons.smartphone_rounded, label: 'Điện thoại'),
        ),
        Expanded(
          child: Padding(
            padding: EdgeInsets.only(bottom: 20),
            child: Row(
              children: [
                Expanded(child: Divider(color: Color(0xFFBDC9F8))),
                Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12),
                  child: Icon(
                    Icons.wifi_rounded,
                    color: AppColors.primary,
                    size: 24,
                  ),
                ),
                Expanded(child: Divider(color: Color(0xFFBDC9F8))),
              ],
            ),
          ),
        ),
        Flexible(
          child: _Device(icon: Icons.laptop_mac_rounded, label: 'Máy tính'),
        ),
      ],
    ),
  );
}

class _Device extends StatelessWidget {
  const _Device({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 36, color: AppColors.primary),
      const SizedBox(height: 10),
      Text(
        label,
        textAlign: TextAlign.center,
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: AppColors.ink,
        ),
      ),
    ],
  );
}
