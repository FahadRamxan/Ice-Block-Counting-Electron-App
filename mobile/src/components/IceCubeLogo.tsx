import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated } from 'react-native';

const SIZE = 96;

/**
 * Ice block logo: single face rotating 360° smoothly. Clean ice look with highlight.
 */
export default function IceCubeLogo() {
  const rotate = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.loop(
      Animated.timing(rotate, {
        toValue: 1,
        duration: 10000,
        useNativeDriver: true,
      })
    ).start();
  }, []);

  const rotateInterp = rotate.interpolate({
    inputRange: [0, 1],
    outputRange: ['0deg', '360deg'],
  });

  return (
    <Animated.View
      style={[
        styles.cube,
        {
          transform: [{ rotate: rotateInterp }],
        },
      ]}
    >
      <View style={styles.highlight} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  cube: {
    width: SIZE,
    height: SIZE,
    borderRadius: 10,
    backgroundColor: 'rgba(56, 189, 248, 0.82)',
    borderWidth: 1,
    borderColor: 'rgba(30, 120, 180, 0.5)',
    shadowColor: '#38bdf8',
    shadowOffset: { width: 0, height: 3 },
    shadowRadius: 10,
    shadowOpacity: 0.45,
    elevation: 6,
  },
  highlight: {
    position: 'absolute',
    top: 10,
    left: 10,
    right: 10,
    height: 24,
    backgroundColor: 'rgba(255, 255, 255, 0.38)',
    borderRadius: 5,
  },
});
