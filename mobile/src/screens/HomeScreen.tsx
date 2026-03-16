import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeLanguage } from '../ThemeLanguageContext';

type Props = {
  onNavigate: (tab: 'nvrs' | 'recordings' | 'test' | 'statistics') => void;
};

export default function HomeScreen({ onNavigate }: Props) {
  const { t, colors: c } = useThemeLanguage();

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <Text style={[styles.title, { color: c.text }]}>{t('homeTitle')}</Text>
          <Text style={[styles.subtitle, { color: c.muted }]}>{t('homeSubtitle')}</Text>
        </View>
        <View style={styles.tiles}>
          <TouchableOpacity style={[styles.tile, { backgroundColor: c.card, borderColor: c.border }]} onPress={() => onNavigate('nvrs')} activeOpacity={0.7}>
            <Text style={[styles.tileTitle, { color: c.text }]}>{t('configureNvrs')}</Text>
            <Text style={[styles.tileDesc, { color: c.muted }]}>{t('navNvrs')}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.tile, { backgroundColor: c.card, borderColor: c.border }]} onPress={() => onNavigate('recordings')} activeOpacity={0.7}>
            <Text style={[styles.tileTitle, { color: c.text }]}>{t('viewRecordings')}</Text>
            <Text style={[styles.tileDesc, { color: c.muted }]}>{t('navRecordings')}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.tile, { backgroundColor: c.card, borderColor: c.border }]} onPress={() => onNavigate('test')} activeOpacity={0.7}>
            <Text style={[styles.tileTitle, { color: c.text }]}>{t('testModel')}</Text>
            <Text style={[styles.tileDesc, { color: c.muted }]}>{t('navTest')}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.tile, { backgroundColor: c.card, borderColor: c.border }]} onPress={() => onNavigate('statistics')} activeOpacity={0.7}>
            <Text style={[styles.tileTitle, { color: c.text }]}>{t('viewStatistics')}</Text>
            <Text style={[styles.tileDesc, { color: c.muted }]}>{t('navStatistics')}</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 24 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 8 },
  subtitle: { fontSize: 14 },
  tiles: { gap: 12 },
  tile: { borderRadius: 12, padding: 18, borderWidth: 1 },
  tileTitle: { fontSize: 16, fontWeight: '600', marginBottom: 4 },
  tileDesc: { fontSize: 13 },
});
