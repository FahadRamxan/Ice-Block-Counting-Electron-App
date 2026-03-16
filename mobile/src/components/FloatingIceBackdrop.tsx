import React, { useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Animated, useWindowDimensions } from 'react-native';

type BlockLayout = { top?: number; bottom?: number; left?: number; right?: number; size: number };

/**
 * Floating ice blocks only in the four corners — never in the center so they don't
 * overlap text or buttons. Drawn on top with pointerEvents: 'none'.
 */
export default function FloatingIceBackdrop() {
  const { width: W, height: H } = useWindowDimensions();
  const [blocks, setBlocks] = useState<BlockLayout[]>([]);

  useEffect(() => {
    if (W === 0 || H === 0) return;
    // Corners only: top/bottom 0–18%, left/right 0–10% — content stays in center
    setBlocks([
      // Top-left
      { top: H * 0.05, left: W * 0.02, size: 18 },
      { top: H * 0.12, left: W * 0.06, size: 16 },
      // Top-right
      { top: H * 0.06, right: W * 0.02, size: 18 },
      { top: H * 0.14, right: W * 0.07, size: 16 },
      // Bottom-left
      { bottom: H * 0.06, left: W * 0.03, size: 18 },
      { bottom: H * 0.14, left: W * 0.07, size: 16 },
      // Bottom-right
      { bottom: H * 0.05, right: W * 0.02, size: 18 },
      { bottom: H * 0.12, right: W * 0.06, size: 16 },
    ]);
  }, [W, H]);

  return (
    <View style={styles.container} pointerEvents="none">
      {blocks.map((layout, i) => (
        <IceBlock key={i} layout={layout} index={i} />
      ))}
    </View>
  );
}

function IceBlock({ layout, index }: { layout: BlockLayout; index: number }) {
  const rotate = useRef(new Animated.Value(0)).current;
  const driftX = useRef(new Animated.Value(0)).current;
  const driftY = useRef(new Animated.Value(0)).current;
  const opacity = useRef(new Animated.Value(0.7)).current;

  useEffect(() => {
    const duration = 8000 + index * 500 + (index % 3) * 800;

    Animated.loop(
      Animated.timing(rotate, {
        toValue: 1,
        duration,
        useNativeDriver: true,
      })
    ).start();

    Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(driftX, { toValue: 1, duration: duration / 2, useNativeDriver: true }),
          Animated.timing(driftY, { toValue: 1, duration: duration / 2, useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(driftX, { toValue: 0, duration: duration / 2, useNativeDriver: true }),
          Animated.timing(driftY, { toValue: 0, duration: duration / 2, useNativeDriver: true }),
        ]),
      ])
    ).start();

    Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.85, duration: 1800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.55, duration: 1800, useNativeDriver: true }),
      ])
    ).start();
  }, [index]);

  const rotateInterp = rotate.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });
  // Small drift so blocks stay in corners and never cross into content (center)
  const driftXInterp = driftX.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 4 - (index % 2) * 2],
  });
  const driftYInterp = driftY.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -4 + (index % 2) * 2],
  });

  const { size } = layout;
  const blockStyle: Record<string, number | string> = {
    position: 'absolute',
    width: size,
    height: size,
    borderRadius: 5,
  };
  if (layout.top != null) blockStyle.top = layout.top;
  if (layout.bottom != null) blockStyle.bottom = layout.bottom;
  if (layout.left != null) blockStyle.left = layout.left;
  if (layout.right != null) blockStyle.right = layout.right;

  return (
    <Animated.View
      style={[
        blockStyle,
        styles.block,
        {
          transform: [
            { translateX: driftXInterp },
            { translateY: driftYInterp },
            { rotate: rotateInterp },
          ],
          opacity,
        },
      ]}
    >
      <View style={styles.blockHighlight} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 9999,
    overflow: 'hidden',
  },
  block: {
    backgroundColor: 'rgba(56, 189, 248, 0.75)',
    shadowColor: '#38bdf8',
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 8,
    shadowOpacity: 0.7,
    elevation: 6,
  },
  blockHighlight: {
    position: 'absolute',
    top: 3,
    left: 3,
    right: 3,
    height: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.35)',
    borderRadius: 2,
  },
});
