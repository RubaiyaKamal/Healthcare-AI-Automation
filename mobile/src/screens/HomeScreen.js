import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors } from '../theme';

export default function HomeScreen({ onNavigate }) {
  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.body} showsVerticalScrollIndicator={false}>
        <Text style={styles.logo}>●</Text>
        <Text style={styles.brand}>HealthFlow AI</Text>
        <Text style={styles.tagline}>
          FHIR + OpenAI agentic automation: patient intake and insurance
          eligibility on a secure sandbox.
        </Text>

        <FeatureCard
          title="Patient Intake"
          desc="AI registration chat with duplicate-check guardrails before any record is created."
          onPress={() => onNavigate('intake')}
        />
        <FeatureCard
          title="Eligibility Check"
          desc="Rules-first insurance verification with a full audit trail."
          onPress={() => onNavigate('eligibility')}
        />

        <Text style={styles.footnote}>
          Local sandbox only — synthetic data, no real PHI.
        </Text>
      </ScrollView>
    </View>
  );
}

function FeatureCard({ title, desc, onPress }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.cardDesc}>{desc}</Text>
      <Text style={styles.cardLink} onPress={onPress}>
        Open →
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.cream },
  body: { padding: 24, paddingTop: 64 },
  logo: { fontSize: 40, color: colors.yellow, textAlign: 'center' },
  brand: {
    fontSize: 30,
    fontWeight: '800',
    color: colors.black,
    textAlign: 'center',
    marginTop: 4,
  },
  tagline: {
    fontSize: 15,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 22,
    marginTop: 8,
    marginBottom: 28,
  },
  card: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    padding: 18,
    marginBottom: 16,
  },
  cardTitle: { fontSize: 18, fontWeight: '700', color: colors.brownDark },
  cardDesc: { fontSize: 14, color: colors.muted, marginTop: 6, lineHeight: 20 },
  cardLink: {
    fontSize: 14,
    fontWeight: '700',
    color: colors.brown,
    marginTop: 12,
    paddingVertical: 8,
  },
  footnote: {
    fontSize: 12,
    color: colors.muted,
    textAlign: 'center',
    marginTop: 16,
  },
});