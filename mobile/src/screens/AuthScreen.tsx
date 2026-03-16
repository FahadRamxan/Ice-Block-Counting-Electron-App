import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useThemeLanguage } from '../ThemeLanguageContext';
import IceCubeLogo from '../components/IceCubeLogo';

type Mode = 'login' | 'signup';

type Props = {
  onLogin: (user: { name: string; email: string }) => void;
};

export default function AuthScreen({ onLogin }: Props) {
  const { t, colors: c, theme, toggleTheme, locale, toggleLocale } = useThemeLanguage();
  const [mode, setMode] = useState<Mode>('login');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [signName, setSignName] = useState('');
  const [signEmail, setSignEmail] = useState('');
  const [signPassword, setSignPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    setError('');
    if (!loginEmail.trim()) {
      setError(t('errEmail'));
      return;
    }
    if (!loginPassword) {
      setError(t('errPassword'));
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    onLogin({ name: loginEmail.split('@')[0], email: loginEmail.trim() });
  };

  const handleSignup = async () => {
    setError('');
    if (!signName.trim()) {
      setError(t('errName'));
      return;
    }
    if (!signEmail.trim()) {
      setError(t('errEmail'));
      return;
    }
    if (!signPassword || signPassword.length < 6) {
      setError(t('errPasswordLen'));
      return;
    }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 500));
    setLoading(false);
    onLogin({ name: signName.trim(), email: signEmail.trim() });
  };

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: c.bg }]} edges={['top']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.kav}
      >
        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.toolbar}>
            <TouchableOpacity onPress={toggleTheme} style={[styles.toolBtn, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.toolBtnText, { color: c.text }]}>
                {theme === 'dark' ? t('themeLight') : t('themeDark')}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={toggleLocale} style={[styles.toolBtn, { backgroundColor: c.card, borderColor: c.border }]}>
              <Text style={[styles.toolBtnText, { color: c.text }]}>
                {locale === 'en' ? t('langUrdu') : t('langEnglish')}
              </Text>
            </TouchableOpacity>
          </View>

          <View style={styles.logoWrap}>
            <IceCubeLogo />
          </View>
          <Text style={[styles.title, { color: c.text }]}>{t('authTitle')}</Text>
          <Text style={[styles.tagline, { color: c.muted }]}>{t('authTagline')}</Text>

          <View style={styles.tabs}>
            <TouchableOpacity
              style={[styles.tab, mode === 'login' && { borderBottomColor: c.accent, borderBottomWidth: 2 }]}
              onPress={() => { setMode('login'); setError(''); }}
            >
              <Text style={[styles.tabText, { color: c.text }]}>{t('logIn')}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.tab, mode === 'signup' && { borderBottomColor: c.accent, borderBottomWidth: 2 }]}
              onPress={() => { setMode('signup'); setError(''); }}
            >
              <Text style={[styles.tabText, { color: c.text }]}>{t('signUp')}</Text>
            </TouchableOpacity>
          </View>

          {mode === 'login' ? (
            <View style={styles.form}>
              <TextInput
                style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
                placeholder={t('email')}
                placeholderTextColor={c.muted}
                value={loginEmail}
                onChangeText={setLoginEmail}
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <TextInput
                style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
                placeholder={t('password')}
                placeholderTextColor={c.muted}
                value={loginPassword}
                onChangeText={setLoginPassword}
                secureTextEntry
              />
              <TouchableOpacity
                style={[styles.btn, { backgroundColor: c.accent }]}
                onPress={handleLogin}
                disabled={loading}
              >
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>{t('logIn')}</Text>}
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.form}>
              <TextInput
                style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
                placeholder={t('name')}
                placeholderTextColor={c.muted}
                value={signName}
                onChangeText={setSignName}
              />
              <TextInput
                style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
                placeholder={t('email')}
                placeholderTextColor={c.muted}
                value={signEmail}
                onChangeText={setSignEmail}
                autoCapitalize="none"
                keyboardType="email-address"
              />
              <TextInput
                style={[styles.input, { backgroundColor: c.card, borderColor: c.border, color: c.text }]}
                placeholder={t('password')}
                placeholderTextColor={c.muted}
                value={signPassword}
                onChangeText={setSignPassword}
                secureTextEntry
              />
              <TouchableOpacity
                style={[styles.btn, { backgroundColor: c.accent }]}
                onPress={handleSignup}
                disabled={loading}
              >
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>{t('signUp')}</Text>}
              </TouchableOpacity>
            </View>
          )}

          {error ? <Text style={[styles.error, { color: c.error }]}>{error}</Text> : null}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  kav: { flex: 1 },
  scroll: { padding: 24, paddingTop: 16 },
  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 32,
  },
  toolBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    minHeight: 40,
    justifyContent: 'center',
    borderRadius: 8,
    borderWidth: 1,
  },
  toolBtnText: { fontSize: 14, fontWeight: '600' },
  logoWrap: { alignItems: 'center', marginBottom: 36 },
  title: { fontSize: 24, fontWeight: '700', marginBottom: 8 },
  tagline: { fontSize: 14, marginBottom: 24 },
  tabs: { flexDirection: 'row', marginBottom: 20 },
  tab: { marginRight: 24, paddingBottom: 8 },
  tabText: { fontSize: 16, fontWeight: '600' },
  form: { gap: 14 },
  input: { padding: 14, borderRadius: 8, fontSize: 16, borderWidth: 1 },
  btn: { padding: 16, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  btnText: { color: '#fff', fontWeight: '600', fontSize: 16 },
  error: { marginTop: 16, fontSize: 14 },
});
