import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import { useThemeLanguage } from '../ThemeLanguageContext';
import { nvrs as nvrsApi } from '../api';
import { recordings as recApi, runs } from '../api';
import type { RecordingsByDateResponse } from '../api';
import type { TabParamList } from '../../App';

type Nvr = { id: number; name: string; ip: string };

export default function RecordingsScreen() {
  const { t, colors: c } = useThemeLanguage();
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList, 'Recordings'>>();
  const [nvrList, setNvrList] = useState<Nvr[]>([]);
  const [nvrId, setNvrId] = useState<number | ''>('');
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [channels, setChannels] = useState<number[]>([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<RecordingsByDateResponse | null>(null);
  const [runMsg, setRunMsg] = useState<string | null>(null);

  const loadNvrs = useCallback(async () => {
    try {
      const list = await nvrsApi.list();
      setNvrList(list);
      if (list.length > 0 && nvrId === '') setNvrId(list[0].id);
    } catch {
      setNvrList([]);
    }
  }, [nvrId]);

  React.useEffect(() => {
    loadNvrs();
  }, []);

  const loadRecordings = async () => {
    if (nvrId === '') {
      setError(t('addNvrsFirst'));
      return;
    }
    setLoading(true);
    setError(null);
    setData(null);
    setRunMsg(null);
    try {
      const res = await recApi.byDate(Number(nvrId), date, channels);
      setData(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runModel = async () => {
    if (nvrId === '') return;
    setRunMsg(null);
    setRunning(true);
    try {
      const res = await runs.runForDate({
        date,
        nvr_id: Number(nvrId),
        channels,
      });
      setRunMsg(res.message || t('runRecorded'));
    } catch (e) {
      setRunMsg((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const toggleChannel = (ch: number) => {
    setChannels((prev) =>
      prev.includes(ch) ? prev.filter((n) => n !== ch) : [...prev, ch].sort((a, b) => a - b)
    );
  };

  const channelCount = data?.nvr_channels ?? 15;
  const channelList = Array.from({ length: channelCount }, (_, i) => i + 1);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: c.text }]}>{t('recTitle')}</Text>

        <View style={styles.row}>
          <Text style={[styles.label, { color: c.muted }]}>{t('labelNvr')}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
            {nvrList.length === 0 ? (
              <Text style={[styles.muted, { color: c.muted }]}>{t('noNvrsYet')}</Text>
            ) : (
              nvrList.map((n) => (
                <TouchableOpacity
                  key={n.id}
                  style={[styles.chip, { backgroundColor: nvrId === n.id ? c.accent : c.card, borderColor: nvrId === n.id ? c.accent : c.border }]}
                  onPress={() => setNvrId(n.id)}
                >
                  <Text style={[styles.chipText, { color: nvrId === n.id ? '#fff' : c.muted }]}>{n.name}</Text>
                </TouchableOpacity>
              ))
            )}
          </ScrollView>
        </View>

        <View style={styles.row}>
          <Text style={[styles.label, { color: c.muted }]}>{t('labelDate')}</Text>
          <TextInput
            style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
            value={date}
            onChangeText={setDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={c.muted}
          />
        </View>

        <View style={styles.row}>
          <Text style={[styles.label, { color: c.muted }]}>{t('channels')}</Text>
          <View style={styles.channelWrap}>
            {channelList.map((ch) => (
              <TouchableOpacity
                key={ch}
                style={[styles.channelChip, { backgroundColor: channels.includes(ch) ? c.accent : c.card, borderColor: channels.includes(ch) ? c.accent : c.border }]}
                onPress={() => toggleChannel(ch)}
              >
                <Text style={[styles.chipText, { color: channels.includes(ch) ? '#fff' : c.muted }]}>{ch}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        <TouchableOpacity style={[styles.btn, { backgroundColor: c.accent }]} onPress={loadRecordings} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>{t('loadRecordings')}</Text>}
        </TouchableOpacity>

        {error ? <Text style={[styles.error, { color: c.error }]}>{error}</Text> : null}

        {data && (
          <>
            <Text style={[styles.sectionTitle, { color: c.text }]}>{data.nvr_name} — {data.date}</Text>
            {data.error ? (
              <Text style={[styles.error, { color: c.error }]}>{data.error}</Text>
            ) : (
              <View style={styles.recList}>
                {Object.entries(data.recordings_by_channel).map(([ch, slots]) => {
                  const arr = Array.isArray(slots) ? slots : [];
                  const err = !Array.isArray(slots) && slots && 'error' in slots ? (slots as { error?: string }).error : null;
                  return (
                    <View key={ch} style={styles.recRow}>
                      <Text style={[styles.recCh, { color: c.muted }]}>Ch {ch}</Text>
                      {err ? (
                        <Text style={[styles.muted, { color: c.muted }]}>{err}</Text>
                      ) : arr.length === 0 ? (
                        <Text style={[styles.muted, { color: c.muted }]}>—</Text>
                      ) : (
                        <Text style={[styles.recSlots, { color: c.text }]}>{arr.length} slot(s)</Text>
                      )}
                    </View>
                  );
                })}
              </View>
            )}
            <TouchableOpacity
              style={[styles.btn, styles.btnSecondary, { backgroundColor: c.card, borderColor: c.border }]}
              onPress={runModel}
              disabled={running}
            >
              {running ? <ActivityIndicator color={c.text} /> : <Text style={[styles.btnTextSecondary, { color: c.text }]}>{t('runModelOnSelection')}</Text>}
            </TouchableOpacity>
            {runMsg ? (
              <View style={styles.runMsgWrap}>
                <Text style={[styles.runMsg, { color: c.success }]}>{runMsg}</Text>
                <TouchableOpacity onPress={() => navigation.navigate('Statistics')}>
                  <Text style={[styles.linkStats, { color: c.accent }]}>{t('viewStatistics')}</Text>
                </TouchableOpacity>
              </View>
            ) : null}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 20, fontWeight: '700', marginBottom: 16 },
  row: { marginBottom: 14 },
  label: { fontSize: 13, marginBottom: 6 },
  chipRow: { flexDirection: 'row', gap: 8 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, marginRight: 8, borderWidth: 1 },
  chipText: { fontSize: 14 },
  channelWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  channelChip: { width: 36, height: 36, borderRadius: 18, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  muted: { fontSize: 14 },
  input: { borderRadius: 8, padding: 12, fontSize: 16, borderWidth: 1 },
  btn: { padding: 14, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  btnSecondary: { marginTop: 16, borderWidth: 1 },
  btnText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  btnTextSecondary: { fontWeight: '600', fontSize: 16 },
  error: { marginTop: 12, fontSize: 14 },
  sectionTitle: { fontSize: 16, fontWeight: '600', marginTop: 20, marginBottom: 12 },
  recList: { gap: 8 },
  recRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  recCh: { width: 48, fontSize: 14 },
  recSlots: { fontSize: 14 },
  runMsgWrap: { marginTop: 12 },
  runMsg: { fontSize: 14, marginBottom: 8 },
  linkStats: { fontSize: 14, fontWeight: '600' },
});
