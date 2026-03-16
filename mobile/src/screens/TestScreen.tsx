import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeLanguage } from '../ThemeLanguageContext';

export default function TestScreen() {
  const { t, colors: c } = useThemeLanguage();
  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <View style={styles.inner}>
        <Text style={[styles.title, { color: c.text }]}>{t('testTitle')}</Text>
        <Text style={[styles.sub, { color: c.muted }]}>{t('testSub')}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  inner: { flex: 1, padding: 20, justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: '700', marginBottom: 12 },
  sub: { fontSize: 15, lineHeight: 22 },
});
