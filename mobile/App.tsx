import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Text, View, StyleSheet, TouchableOpacity } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { initApiBaseUrl } from './src/config';
import { ThemeLanguageProvider, useThemeLanguage } from './src/ThemeLanguageContext';
import { AuthProvider, useAuth } from './src/AuthContext';
import FloatingIceBackdrop from './src/components/FloatingIceBackdrop';
import AuthScreen from './src/screens/AuthScreen';
import AccountScreen from './src/screens/AccountScreen';
import HomeScreen from './src/screens/HomeScreen';
import NvrsScreen from './src/screens/NvrsScreen';
import RecordingsScreen from './src/screens/RecordingsScreen';
import StatisticsScreen from './src/screens/StatisticsScreen';
import TestScreen from './src/screens/TestScreen';

export type TabParamList = {
  Home: undefined;
  Nvrs: undefined;
  Recordings: undefined;
  Test: undefined;
  Statistics: undefined;
};

export type RootStackParamList = {
  Main: undefined;
  Account: undefined;
};

const Tab = createBottomTabNavigator<TabParamList>();
const Stack = createNativeStackNavigator<RootStackParamList>();

function AccountHeaderButton({ colors }: { colors: { text: string; border: string } }) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList, 'Main'>>();
  const parent = navigation.getParent();
  return (
    <TouchableOpacity
      onPress={() => (parent as any)?.navigate('Account')}
      style={[styles.accountIconBtn, { borderColor: colors.border }]}
      activeOpacity={0.7}
    >
      <Text style={[styles.accountIconText, { color: colors.text }]}>A</Text>
    </TouchableOpacity>
  );
}

function TabIcon({ name, focused, colors }: { name: string; focused: boolean; colors: typeof import('./src/ThemeLanguageContext').colors.dark }) {
  return (
    <View style={[styles.tabIcon, { backgroundColor: focused ? colors.accent : colors.border }]}>
      <Text style={[styles.tabIconText, { color: focused ? '#fff' : colors.muted }]}>{name.charAt(0)}</Text>
    </View>
  );
}

function HomeTab() {
  const navigation = useNavigation<BottomTabNavigationProp<TabParamList, 'Home'>>();
  return (
    <HomeScreen
      onNavigate={(tab) => navigation.navigate(tab === 'nvrs' ? 'Nvrs' : tab === 'recordings' ? 'Recordings' : tab === 'test' ? 'Test' : 'Statistics')}
    />
  );
}

function MainTabs() {
  const { t, colors, isDark } = useThemeLanguage();
  return (
    <Tab.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '600', fontSize: 18 },
        headerRight: () => <AccountHeaderButton colors={colors} />,
        tabBarStyle: { backgroundColor: colors.bg, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.muted,
        tabBarLabelStyle: { fontSize: 12 },
      }}
    >
      <Tab.Screen
        name="Home"
        component={HomeTab}
        options={{
          title: t('navHome'),
          tabBarIcon: ({ focused }) => <TabIcon name="Home" focused={focused} colors={colors} />,
        }}
      />
      <Tab.Screen
        name="Nvrs"
        component={NvrsScreen}
        options={{
          title: t('navNvrs'),
          tabBarIcon: ({ focused }) => <TabIcon name="Nvrs" focused={focused} colors={colors} />,
        }}
      />
      <Tab.Screen
        name="Recordings"
        component={RecordingsScreen}
        options={{
          title: t('navRecordings'),
          tabBarIcon: ({ focused }) => <TabIcon name="Recordings" focused={focused} colors={colors} />,
        }}
      />
      <Tab.Screen
        name="Test"
        component={TestScreen}
        options={{
          title: t('navTest'),
          tabBarIcon: ({ focused }) => <TabIcon name="Test" focused={focused} colors={colors} />,
        }}
      />
      <Tab.Screen
        name="Statistics"
        component={StatisticsScreen}
        options={{
          title: t('navStatistics'),
          tabBarIcon: ({ focused }) => <TabIcon name="Statistics" focused={focused} colors={colors} />,
        }}
      />
    </Tab.Navigator>
  );
}

function RootStack() {
  const { t, colors } = useThemeLanguage();
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
      <Stack.Screen
        name="Account"
        component={AccountScreen}
        options={{ title: t('accountTitle'), headerBackTitle: t('cancel') }}
      />
    </Stack.Navigator>
  );
}

function AppContent() {
  const { user, setUser } = useAuth();
  const { isDark } = useThemeLanguage();
  if (!user) {
    return (
      <View style={{ flex: 1 }}>
        <FloatingIceBackdrop />
        <StatusBar style={isDark ? 'light' : 'dark'} />
        <AuthScreen onLogin={setUser} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <FloatingIceBackdrop />
      <NavigationContainer>
        <StatusBar style={isDark ? 'light' : 'dark'} />
        <RootStack />
      </NavigationContainer>
    </View>
  );
}

export default function App() {
  const [apiReady, setApiReady] = React.useState(false);
  React.useEffect(() => {
    initApiBaseUrl().then(() => setApiReady(true));
  }, []);
  if (!apiReady) {
    return (
      <View style={styles.loadingRoot}>
        <Text style={styles.loadingText}>Loading…</Text>
      </View>
    );
  }
  return (
    <ThemeLanguageProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeLanguageProvider>
  );
}

const styles = StyleSheet.create({
  loadingRoot: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
  loadingText: { color: '#94a3b8', fontSize: 16 },
  accountIconBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  accountIconText: { fontSize: 16, fontWeight: '700' },
  tabIcon: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  tabIconText: { fontSize: 12, fontWeight: '700' },
});
