import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Reserves useful space for both the portrait preview and readable captions.
/// Small screens and enlarged text scroll instead of squeezing either panel.
class LiveCaptureLayout extends StatelessWidget {
  const LiveCaptureLayout({
    super.key,
    required this.header,
    required this.preview,
    required this.captions,
    required this.controls,
  });
  final Widget header, preview, captions, controls;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: LayoutBuilder(
      builder: (context, constraints) {
        final scale = MediaQuery.textScalerOf(context).scale(1);
        final minCaption = 220.0 + math.max(0, scale - 1) * 240;
        final minHeight = 300 + minCaption + 160 * math.max(1, scale);
        final height = math.max(constraints.maxHeight, minHeight);
        return SingleChildScrollView(
          child: SizedBox(
            height: height,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 6, 16, 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  header,
                  const SizedBox(height: 10),
                  Expanded(
                    child: constraints.maxWidth >= 700
                        ? Row(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Expanded(child: preview),
                              const SizedBox(width: 16),
                              Expanded(child: captions),
                            ],
                          )
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Expanded(child: preview),
                              const SizedBox(height: 12),
                              SizedBox(
                                height: math.max(
                                  minCaption,
                                  (height - 140) * .36,
                                ),
                                child: captions,
                              ),
                            ],
                          ),
                  ),
                  const SizedBox(height: 12),
                  controls,
                ],
              ),
            ),
          ),
        );
      },
    ),
  );
}
