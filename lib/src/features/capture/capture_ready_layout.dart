import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Preview and caption destination are visible together before capture starts.
/// Controls stay reachable; larger text can scroll without shrinking the text.
class CaptureReadyLayout extends StatelessWidget {
  const CaptureReadyLayout({
    super.key,
    required this.header,
    required this.connection,
    required this.preview,
    required this.captions,
    required this.controls,
    this.notice,
    this.recovery = false,
  });

  final Widget header, connection, preview, captions, controls;
  final Widget? notice;
  final bool recovery;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Column(
      children: [
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final scale = MediaQuery.textScalerOf(context).scale(1);
              final minHeight = scale > 1.2
                  ? 640 + (scale - 1) * 400
                  : recovery
                  ? 570.0
                  : 440.0;
              final height = math.max(
                constraints.maxHeight,
                minHeight + (notice == null ? 0 : 200 * scale),
              );
              return SingleChildScrollView(
                child: SizedBox(
                  height: height,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(18, 8, 18, 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        header,
                        const SizedBox(height: 10),
                        connection,
                        if (notice != null) ...[
                          const SizedBox(height: 12),
                          notice!,
                        ],
                        const SizedBox(height: 12),
                        Expanded(
                          child: LayoutBuilder(
                            builder: (context, panel) {
                              if (constraints.maxWidth >= 700) {
                                return Row(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    Expanded(child: preview),
                                    const SizedBox(width: 20),
                                    Expanded(child: captions),
                                  ],
                                );
                              }
                              final captionHeight = recovery
                                  ? 280 + math.max(0.0, scale - 1) * 230
                                  : scale > 1.2
                                  ? 220 + (scale - 1) * 230
                                  : (panel.maxHeight * .36).clamp(172.0, 195.0);
                              return Column(
                                crossAxisAlignment: CrossAxisAlignment.stretch,
                                children: [
                                  Expanded(child: preview),
                                  const SizedBox(height: 12),
                                  SizedBox(
                                    height: captionHeight,
                                    child: captions,
                                  ),
                                ],
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 10),
          child: controls,
        ),
      ],
    ),
  );
}
