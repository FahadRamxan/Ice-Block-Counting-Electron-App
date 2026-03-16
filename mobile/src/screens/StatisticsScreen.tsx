import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeLanguage } from '../ThemeLanguageContext';
import { nvrs as nvrsApi } from '../api';
import { runs } from '../api';
import type { RunResult } from '../api';

type Nvr = { id: number; name: string; ip: string };

export default function StatisticsScreen() {
  const { t, colors: c } = useThemeLanguage();
  const [nvrList, setNvrList] = useState<Nvr[]>([]);
  const [nvrId, setNvrId] = useState<number | ''>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totals, setTotals] = useState({ total_blocks: 0, total_runs: 0 });
  const [range, setRange] = useState({ from: '', to: '' });
  const [recent, setRecent] = useState<RunResult[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [stats, results] = await Promise.all([
        runs.statistics({
          granularity: 'day',
          days: 30,
          nvr_id: nvrId === '' ? undefined : Number(nvrId),
        }),
        runs.results(nvrId === '' ? undefined : { nvr_id: Number(nvrId) }),
      ]);
      setTotals(stats.totals);
      setRange({ from: stats.from, to: stats.to });
      setRecent(results.slice(0, 50));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [nvrId]);

  React.useEffect(() => {
    load();
  }, [load]);

  React.useEffect(() => {
    nvrsApi.list().then((list) => {
      setNvrList(list);
      if (list.length > 0 && nvrId === '') setNvrId(list[0].id);
    }).catch(() => setNvrList([]));
  }, []);

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: c.text }]}>{t('statsTitle')}</Text>

        <View style={styles.filterRow}>
          <Text style={[styles.label, { color: c.muted }]}>{t('statsColNvr')}</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipRow}>
            <TouchableOpacity
              style={[styles.chip, { backgroundColor: nvrId === '' ? c.accent : c.card, borderColor: nvrId === '' ? c.accent : c.border }]}
              onPress={() => setNvrId('')}
            >
              <Text style={[styles.chipText, { color: nvrId === '' ? '#fff' : c.muted }]}>All</Text>
            </TouchableOpacity>
            {nvrList.map((n) => (
              <TouchableOpacity
                key={n.id}
                style={[styles.chip, { backgroundColor: nvrId === n.id ? c.accent : c.card, borderColor: nvrId === n.id ? c.accent : c.border }]}
                onPress={() => setNvrId(n.id)}
              >
                <Text style={[styles.chipText, { color: nvrId === n.id ? '#fff' : c.muted }]}>{n.name}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {error ? <Text style={[styles.error, { color: c.error }]}>{error}</Text> : null}

        {loading && recent.length === 0 ? (
          <ActivityIndicator size="large" color={c.accent} style={{ marginTop: 24 }} />
        ) : (
          <>
            <View style={styles.kpis}>
              <View style={[styles.kpi, { backgroundColor: c.card, borderColor: c.border }]}>
                <Text style={[styles.kpiVal, { color: c.text }]}>{totals.total_blocks.toLocaleString()}</Text>
                <Text style={[styles.kpiLabel, { color: c.muted }]}>{t('statsTotalBlocks')}</Text>
              </View>
              <View style={[styles.kpi, { backgroundColor: c.card, borderColor: c.border }]}>
                <Text style={[styles.kpiVal, { color: c.text }]}>{totals.total_runs.toLocaleString()}</Text>
                <Text style={[styles.kpiLabel, { color: c.muted }]}>{t('statsTotalRuns')}</Text>
              </View>
            </View>
            <Text style={[styles.range, { color: c.muted }]}>{range.from} → {range.to}</Text>

            <View style={styles.tableHeader}>
              <Text style={[styles.tableTitle, { color: c.text }]}>{t('statsRecentRuns')}</Text>
              <TouchableOpacity onPress={load} disabled={loading}>
                {loading ? <ActivityIndicator size="small" color={c.accent} /> : <Text style={[styles.refreshText, { color: c.accent }]}>{t('refresh')}</Text>}
              </TouchableOpacity>
            </View>
            {recent.length === 0 ? (
              <Text style={[styles.empty, { color: c.muted }]}>{t('statsNoRuns')}</Text>
            ) : (
              <View style={styles.table}>
                {recent.map((r) => (
                  <View key={r.id} style={[styles.tableRow, { borderBottomColor: c.border }]}>
                    <Text style={[styles.cellWhen, { color: c.muted }]} numberOfLines={1}>{r.created_at?.slice(0, 16) ?? '—'}</Text>
                    <Text style={[styles.cellNvr, { color: c.text }]} numberOfLines={1}>{r.nvr_name ?? '—'}</Text>
                    <Text style={[styles.cellCh, { color: c.text }]}>{r.channel ?? '—'}</Text>
                    <Text style={[styles.cellDate, { color: c.text }]}>{r.run_date ?? '—'}</Text>
                    <Text style={[styles.cellBlocks, { color: c.text }]}>{r.total_unique_blocks ?? r.ice_block_count ?? '—'}</Text>
                    <Text style={[styles.cellSource, { color: c.muted }]} numberOfLines={1}>{r.source ?? '—'}</Text>
                  </View>
                ))}
              </View>
            )}
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
  filterRow: { marginBottom: 16 },
  label: { fontSize: 13, marginBottom: 8 },
  chipRow: { flexDirection: 'row', gap: 8 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, marginRight: 8, borderWidth: 1 },
  chipText: { fontSize: 14 },
  error: { marginBottom: 12, fontSize: 14 },
  kpis: { flexDirection: 'row', gap: 20, marginBottom: 12 },
  kpi: { flex: 1, padding: 16, borderRadius: 12, borderWidth: 1 },
  kpiVal: { fontSize: 22, fontWeight: '700' },
  kpiLabel: { fontSize: 12, marginTop: 4 },
  range: { fontSize: 13, marginBottom: 20 },
  tableHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  tableTitle: { fontSize: 16, fontWeight: '600' },
  refreshText: { fontSize: 14 },
  empty: { fontSize: 14 },
  table: { gap: 0 },
  tableRow: { flexDirection: 'row', paddingVertical: 10, paddingHorizontal: 8, borderBottomWidth: 1, gap: 8 },
  cellWhen: { width: 100, fontSize: 11 },
  cellNvr: { flex: 1, fontSize: 12 },
  cellCh: { width: 28, fontSize: 12 },
  cellDate: { width: 72, fontSize: 12 },
  cellBlocks: { width: 44, fontSize: 12 },
  cellSource: { width: 70, fontSize: 11 },
});
