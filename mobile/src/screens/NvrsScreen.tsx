import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeLanguage } from '../ThemeLanguageContext';
import { nvrs as nvrsApi } from '../api';

type Nvr = { id: number; name: string; ip: string; port: number; username: string; created_at: string };

export default function NvrsScreen() {
  const { t, colors: c } = useThemeLanguage();
  const [list, setList] = useState<Nvr[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '',
    ip: '',
    port: '37777',
    username: '',
    password: '',
  });
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await nvrsApi.list();
      setList(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const addNvr = async () => {
    if (!form.ip.trim()) {
      setError(t('labelIp') + ' required');
      return;
    }
    setAdding(true);
    setError(null);
    try {
      await nvrsApi.add({
        name: form.name.trim() || form.ip,
        ip: form.ip.trim(),
        port: parseInt(form.port, 10) || 37777,
        username: form.username.trim(),
        password: form.password,
      });
      setForm({ name: '', ip: '', port: '37777', username: '', password: '' });
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAdding(false);
    }
  };

  const removeNvr = (nvr: Nvr) => {
    Alert.alert(t('delete'), `Remove ${nvr.name}?`, [
      { text: t('cancel'), style: 'cancel' },
      {
        text: t('delete'),
        style: 'destructive',
        onPress: async () => {
          try {
            await nvrsApi.delete(nvr.id);
            load();
          } catch (e) {
            setError((e as Error).message);
          }
        },
      },
    ]);
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={[styles.title, { color: c.text }]}>{t('nvrConfigTitle')}</Text>

        <View style={styles.form}>
          <TextInput
            style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
            placeholder={t('labelName')}
            placeholderTextColor={c.muted}
            value={form.name}
            onChangeText={(v) => setForm((f) => ({ ...f, name: v }))}
            autoCapitalize="none"
          />
          <TextInput
            style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
            placeholder={t('labelIp')}
            placeholderTextColor={c.muted}
            value={form.ip}
            onChangeText={(v) => setForm((f) => ({ ...f, ip: v }))}
            autoCapitalize="none"
            keyboardType="url"
          />
          <TextInput
            style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
            placeholder={t('labelPort')}
            placeholderTextColor={c.muted}
            value={form.port}
            onChangeText={(v) => setForm((f) => ({ ...f, port: v }))}
            keyboardType="number-pad"
          />
          <TextInput
            style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
            placeholder={t('labelUsername')}
            placeholderTextColor={c.muted}
            value={form.username}
            onChangeText={(v) => setForm((f) => ({ ...f, username: v }))}
            autoCapitalize="none"
          />
          <TextInput
            style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
            placeholder={t('labelPassword')}
            placeholderTextColor={c.muted}
            value={form.password}
            onChangeText={(v) => setForm((f) => ({ ...f, password: v }))}
            secureTextEntry
            autoCapitalize="none"
          />
          <TouchableOpacity
            style={[styles.btn, { backgroundColor: c.accent }]}
            onPress={addNvr}
            disabled={adding}
          >
            {adding ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>{t('addNvr')}</Text>}
          </TouchableOpacity>
        </View>

        {error ? <Text style={[styles.error, { color: c.error }]}>{error}</Text> : null}

        <View style={styles.listHeader}>
          <Text style={[styles.listTitle, { color: c.text }]}>{t('navNvrs')}</Text>
          <TouchableOpacity onPress={load} disabled={loading}>
            {loading ? <ActivityIndicator size="small" color={c.accent} /> : <Text style={[styles.refreshText, { color: c.accent }]}>{t('refresh')}</Text>}
          </TouchableOpacity>
        </View>
        {list.length === 0 && !loading ? (
          <Text style={[styles.empty, { color: c.muted }]}>{t('noNvrsYet')}</Text>
        ) : (
          list.map((n) => (
            <View key={n.id} style={[styles.row, { backgroundColor: c.card, borderColor: c.border }]}>
              <View style={styles.rowBody}>
                <Text style={[styles.rowName, { color: c.text }]}>{n.name}</Text>
                <Text style={[styles.rowIp, { color: c.muted }]}>{n.ip}:{n.port}</Text>
              </View>
              <TouchableOpacity onPress={() => removeNvr(n)}>
                <Text style={[styles.deleteText, { color: c.error }]}>{t('delete')}</Text>
              </TouchableOpacity>
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  scroll: { padding: 20, paddingBottom: 40 },
  title: { fontSize: 20, fontWeight: '700', marginBottom: 16 },
  form: { marginBottom: 20, gap: 10 },
  input: { borderRadius: 8, padding: 14, fontSize: 16, borderWidth: 1 },
  btn: { padding: 14, borderRadius: 8, alignItems: 'center' },
  btnText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  error: { marginBottom: 12, fontSize: 14 },
  listHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  listTitle: { fontSize: 16, fontWeight: '600' },
  refreshText: { fontSize: 14 },
  empty: { fontSize: 14 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 14, borderRadius: 8, marginBottom: 8, borderWidth: 1 },
  rowBody: { flex: 1 },
  rowName: { fontSize: 16, fontWeight: '500' },
  rowIp: { fontSize: 13, marginTop: 2 },
  deleteText: { fontSize: 14 },
});
