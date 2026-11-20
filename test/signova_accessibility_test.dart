import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:lip_reader/shared/signova_style.dart';

double contrast(Color first, Color second) {
  final light = math.max(first.computeLuminance(), second.computeLuminance());
  final dark = math.min(first.computeLuminance(), second.computeLuminance());
  return (light + .05) / (dark + .05);
}

void main() {
  test('small text remains readable on canvas, selected source and CTA', () {
    final theme = SignovaStyle.theme;
    expect(
      contrast(
        theme.textTheme.bodySmall!.color!,
        theme.scaffoldBackgroundColor,
      ),
      greaterThanOrEqualTo(4.5),
    );
    expect(
      contrast(theme.colorScheme.primary, theme.colorScheme.primaryContainer),
      greaterThanOrEqualTo(4.5),
    );
    final button = theme.filledButtonTheme.style!;
    expect(
      contrast(
        button.foregroundColor!.resolve({})!,
        button.backgroundColor!.resolve({})!,
      ),
      greaterThanOrEqualTo(4.5),
    );
  });

  testWidgets(
    'header and primary action fit a narrow phone with 200 percent text',
    (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final semantics = tester.ensureSemantics();
      int taps = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: SignovaStyle.theme,
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(context).copyWith(
              textScaler: const TextScaler.linear(2),
              disableAnimations: true,
            ),
            child: child!,
          ),
          home: Scaffold(
            body: Column(
              children: [
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 16),
                  child: SizedBox(
                    height: 72,
                    child: SignovaHeader(
                      title: 'VSL Stream',
                      subtitle: 'Camera and captions',
                    ),
                  ),
                ),
                Expanded(
                  child: Center(
                    child: FilledButton(
                      onPressed: () => taps++,
                      child: const Text('Start'),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Camera and captions'), findsNothing);
      expect(find.text('VSL Stream'), findsOneWidget);
      await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
      await tester.tap(find.text('Start'));
      semantics.dispose();
      expect(taps, 1);
    },
  );
}
