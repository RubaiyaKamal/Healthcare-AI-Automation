import { useState } from 'react';
import {
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { colors } from './src/theme';
import HomeScreen from './src/screens/HomeScreen';
import IntakeScreen from './src/screens/IntakeScreen';
import EligibilityScreen from './src/screens/EligibilityScreen';
import RcmScreen from './src/screens/RcmScreen';

const TABS = [
  { key: 'home', label: 'Home' },
  { key: 'intake', label: 'Intake' },
  { key: 'eligibility', label: 'Eligibility' },
  { key: 'rcm', label: 'RCM' },
];

export default function App() {
  const [tab, setTab] = useState('home');

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.content}>
        {tab === 'home' && <HomeScreen onNavigate={setTab} />}
        {tab === 'intake' && <IntakeScreen />}
        {tab === 'eligibility' && <EligibilityScreen />}
        {tab === 'rcm' && <RcmScreen />}
      </View>

      <View style={styles.tabBar}>
        {TABS.map((t) => {
          const active = tab === t.key;
          return (
            <Pressable
              key={t.key}
              style={[styles.tab, active && styles.tabActive]}
              onPress={() => setTab(t.key)}
            >
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>
                {t.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.cream },
  content: { flex: 1 },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: colors.black,
    borderTopWidth: 1,
    borderTopColor: colors.yellow,
    paddingBottom: 6,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 12,
    paddingBottom: 6,
  },
  tabActive: {
    backgroundColor: colors.yellow,
  },
  tabLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.yellowLight,
  },
  tabLabelActive: {
    color: colors.black,
    fontWeight: '800',
  },
});