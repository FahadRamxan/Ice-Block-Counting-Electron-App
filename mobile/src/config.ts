import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Backend API base URL.
 * - iOS Simulator: http://localhost:5000
 * - Android Emulator: http://10.0.2.2:5000
 * - Physical device (iPhone/Android): use your computer's IP, e.g. http://192.168.8.165:5000
 *   Set it in Account → Backend API URL and ensure Flask is running on that machine.
 */
const STORAGE_KEY = 'ice_app_api_base_url';
const DEFAULT_ANDROID_EMULATOR = 'http://10.0.2.2:5000';
const DEFAULT_OTHER = 'http://localhost:5000';

let API_BASE_URL =
  Platform.OS === 'android' ? DEFAULT_ANDROID_EMULATOR : DEFAULT_OTHER;

export const getApiBaseUrl = (): string => API_BASE_URL;

/** Call once at app start to load saved URL from AsyncStorage. */
export async function initApiBaseUrl(): Promise<void> {
  try {
    const saved = await AsyncStorage.getItem(STORAGE_KEY);
    if (saved && saved.trim()) {
      API_BASE_URL = saved.trim().replace(/\/$/, '');
    }
  } catch (_) {}
}

export const setApiBaseUrl = (url: string): void => {
  const next = url.trim().replace(/\/$/, '');
  API_BASE_URL = next;
  AsyncStorage.setItem(STORAGE_KEY, next).catch(() => {});
};

export const defaultApiBaseUrl = (): string => {
  return Platform.OS === 'android' ? DEFAULT_ANDROID_EMULATOR : DEFAULT_OTHER;
};
