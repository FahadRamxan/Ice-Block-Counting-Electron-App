import React, { useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeLanguage } from '../ThemeLanguageContext';
import { useAuth } from '../AuthContext';
import { getApiBaseUrl, setApiBaseUrl, defaultApiBaseUrl } from '../config';

export default function AccountScreen() {
  const { t, colors: c, theme, toggleTheme, locale, toggleLocale } = useThemeLanguage();
  const { logout } = useAuth();
  const [apiUrl, setApiUrl] = useState(getApiBaseUrl());
  const [apiUrlSaved, setApiUrlSaved] = useState(false);

  const saveApiUrl = () => {
    if (apiUrl.trim()) {
      setApiBaseUrl(apiUrl.trim());
      setApiUrlSaved(true);
      setTimeout(() => setApiUrlSaved(false), 2500);
    }
  };

  const resetApiUrl = () => {
    const def = defaultApiBaseUrl();
    setApiUrl(def);
    setApiBaseUrl(def);
    setApiUrlSaved(true);
    setTimeout(() => setApiUrlSaved(false), 2500);
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <View style={styles.section}>
        <Text style={[styles.label, { color: c.muted }]}>{t('apiUrlLabel')}</Text>
        <TextInput
          style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
          value={apiUrl}
          onChangeText={setApiUrl}
          placeholder={t('apiUrlPlaceholder')}
          placeholderTextColor={c.muted}
          autoCapitalize="none"
          autoCorrect={false}
        />
        <View style={styles.apiUrlRow}>
          <TouchableOpacity style={[styles.apiUrlBtn, { backgroundColor: c.accent }]} onPress={saveApiUrl}>
            <Text style={styles.apiUrlBtnText}>{t('apiUrlSave')}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.apiUrlBtn, styles.apiUrlBtnSecondary, { borderColor: c.border }]} onPress={resetApiUrl}>
            <Text style={[styles.apiUrlBtnTextSecondary, { color: c.text }]}>{t('apiUrlReset')}</Text>
          </TouchableOpacity>
        </View>
        {apiUrlSaved ? <Text style={[styles.savedHint, { color: c.success }]}>{t('apiUrlSaved')}</Text> : null}
      </View>
      <View style={styles.section}>
        <Text style={[styles.label, { color: c.muted }]}>{t('themeDark')} / {t('themeLight')}</Text>
        <TouchableOpacity
          style={[styles.option, { backgroundColor: c.card, borderColor: c.border }]}
          onPress={toggleTheme}
        >
          <Text style={[styles.optionText, { color: c.text }]}>
            {theme === 'dark' ? t('themeLight') : t('themeDark')}
          </Text>
        </TouchableOpacity>
      </View>
      <View style={styles.section}>
        <Text style={[styles.label, { color: c.muted }]}>{t('langEnglish')} / {t('langUrdu')}</Text>
        <TouchableOpacity
          style={[styles.option, { backgroundColor: c.card, borderColor: c.border }]}
          onPress={toggleLocale}
        >
          <Text style={[styles.optionText, { color: c.text }]}>
            {locale === 'en' ? t('langUrdu') : t('langEnglish')}
          </Text>
        </TouchableOpacity>
      </View>
      <TouchableOpacity
        style={[styles.logoutBtn, { backgroundColor: c.error }]}
        onPress={logout}
      >
        <Text style={styles.logoutText}>{t('logOut')}</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, padding: 20 },
  section: { marginBottom: 24 },
  label: { fontSize: 12, marginBottom: 8 },
  input: { padding: 12, borderRadius: 8, fontSize: 14, borderWidth: 1 },
  apiUrlRow: { flexDirection: 'row', gap: 10, marginTop: 10 },
  apiUrlBtn: { padding: 12, borderRadius: 8, minWidth: 100, alignItems: 'center' },
  apiUrlBtnSecondary: { backgroundColor: 'transparent', borderWidth: 1 },
  apiUrlBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  apiUrlBtnTextSecondary: { fontSize: 14 },
  savedHint: { marginTop: 8, fontSize: 13 },
  option: {
    padding: 16,
    minHeight: 48,
    justifyContent: 'center',
    borderRadius: 8,
    borderWidth: 1,
  },
  optionText: { fontSize: 16, fontWeight: '500' },
  logoutBtn: { marginTop: 24, padding: 16, borderRadius: 8, alignItems: 'center' },
  logoutText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
