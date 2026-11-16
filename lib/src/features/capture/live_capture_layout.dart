import 'dart:math' as math;
import 'package:flutter/material.dart';

/// The session control stays reachable while enlarged content can scroll.
class LiveCaptureLayout extends StatelessWidget {
  const LiveCaptureLayout({
    super.key,
    required this.header,
    required this.preview,
    required this.captions,
    required this.controls,
    this.recovery = false,
  });
  final Widget header, preview, captions, controls;
  final bool recovery;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Column(
      children: [
        Expanded(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final scale = MediaQuery.textScalerOf(context).scale(1);
              final minCaption =
                  (recovery ? 310.0 : 235.0) + math.max(0, scale - 1) * 230;
              final wide = constraints.maxWidth >= 700;
              final minHeight = wide
                  ? math.max(380.0, minCaption + 100)
                  : (recovery ? 230 : 300) +
                        minCaption +
                        92 * math.max(1, scale);
              final height = math.max(constraints.maxHeight, minHeight);
              return SingleChildScrollView(
                child: SizedBox(
                  height: height,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        header,
                        const SizedBox(height: 16),
                        Expanded(
                          child: wide
                              ? Row(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    Expanded(child: preview),
                                    const SizedBox(width: 20),
                                    Expanded(child: captions),
                                  ],
                                )
                              : Column(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.stretch,
                                  children: [
                                    Expanded(child: preview),
                                    const SizedBox(height: 12),
                                    SizedBox(
                                      height: math.max(
                                        minCaption,
                                        (height - 100) * .39,
                                      ),
                                      child: captions,
                                    ),
                                  ],
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
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          child: controls,
        ),
      ],
    ),
  );
}
