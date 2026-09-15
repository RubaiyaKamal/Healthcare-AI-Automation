import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { api } from '../api';
import { colors } from '../theme';

const STATUS_STYLES = {
  Covered: { bg: colors.brownDark, fg: colors.yellowLight },
  'Not Covered': { bg: '#4A2E12', fg: '#D8B48A' },
  'Needs Prior Auth': { bg: colors.yellow, fg: colors.black },
  Unknown: { bg: colors.border, fg: colors.brownDark },
};

export default function EligibilityScreen() {
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .listPatients()
      .then((data) => {
        setPatients(data);
        if (data.length > 0) setSelected(data[0]);
      })
      .catch((e) => setError(e.message));
  }, []);

  async function loadHistory(fhirId) {
    try {
      const data = await api.eligibilityHistory(fhirId);
      setHistory(Array.isArray(data) ? data : []);
    } catch {
      setHistory([]);
    }
  }

  async function check() {
    if (!selected) return;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const data = await api.eligibilityCheck(selected.fhir_id);
      setResult(data);
      await loadHistory(selected.fhir_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={styles.container}>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.body}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.header}>
          <Text style={styles.title}>Eligibility Check</Text>
          <Text style={styles.subtitle}>
            Rules-first classification with audit trail.
          </Text>
        </View>

        {error !== '' && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <Text style={styles.label}>Select patient</Text>
        {patients.map((p) => {
          const active = selected?.fhir_id === p.fhir_id;
          return (
            <TouchableOpacity
              key={p.fhir_id}
              style={[styles.patient, active && styles.patientActive]}
              onPress={() => {
                setSelected(p);
                setResult(null);
              }}
            >
              <Text style={[styles.patientName, active && { color: colors.black }]}>
                {p.last_name}, {p.first_name}
              </Text>
              <Text style={styles.patientMeta}>
                b. {p.dob} · {p.insurer ?? 'no insurer'}
              </Text>
            </TouchableOpacity>
          );
        })}

        <TouchableOpacity
          style={[styles.checkBtn, (!selected || busy) && styles.checkBtnDisabled]}
          onPress={check}
          disabled={busy || !selected}
        >
          {busy ? (
            <ActivityIndicator color={colors.black} size="small" />
          ) : (
            <Text style={styles.checkBtnText}>
              {selected ? 'Check Eligibility' : 'No patient selected'}
            </Text>
          )}
        </TouchableOpacity>

        {result && (
          <View
            style={[
              styles.resultBox,
              {
                backgroundColor: STATUS_STYLES[result.status]?.bg ?? colors.border,
              },
            ]}
          >
            <View style={styles.resultHeader}>
              <Text
                style={[
                  styles.resultStatus,
                  { color: STATUS_STYLES[result.status]?.fg ?? colors.brownDark },
                ]}
              >
                {result.status}
              </Text>
              <Text
                style={[
                  styles.resultBadge,
                  { color: STATUS_STYLES[result.status]?.fg ?? colors.brownDark },
                ]}
              >
                resolved_by={result.resolved_by}
              </Text>
            </View>
            <Text
              style={[
                styles.resultDetail,
                { color: STATUS_STYLES[result.status]?.fg ?? colors.brownDark },
              ]}
            >
              {result.detail}
            </Text>
            {result.plan ? (
              <Text
                style={[
                  styles.resultMeta,
                  { color: STATUS_STYLES[result.status]?.fg ?? colors.brownDark },
                ]}
              >
                Plan: {result.plan}
              </Text>
            ) : null}
          </View>
        )}

        {history.length > 0 && (
          <View style={styles.history}>
            <Text style={styles.historyTitle}>Recent checks</Text>
            {history.map((h, i) => (
              <View key={i} style={styles.historyRow}>
                <Text style={styles.historyStatus}>{h.status}</Text>
                <Text style={styles.historyMeta}>
                  {h.payer ?? '—'} · {h.resolved_by} ·{' '}
                  {new Date(h.checked_at).toLocaleString()}
                </Text>
              </View>
            ))}
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.cream },
  scroll: { flex: 1 },
  body: { padding: 20, paddingBottom: 40 },
  header: { marginBottom: 16 },
  title: { fontSize: 22, fontWeight: '800', color: colors.black },
  subtitle: { fontSize: 13, color: colors.muted, marginTop: 2 },
  errorBox: {
    backgroundColor: '#F3E3D3',
    borderRadius: 10,
    padding: 12,
    marginBottom: 12,
  },
  errorText: { color: colors.brownDark, fontSize: 13 },
  label: { fontSize: 13, fontWeight: '600', color: colors.brownDark, marginBottom: 8 },
  patient: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  patientActive: {
    borderColor: colors.brown,
    backgroundColor: colors.yellowSoft,
  },
  patientName: { fontSize: 15, fontWeight: '700', color: colors.brownDark },
  patientMeta: { fontSize: 12, color: colors.muted, marginTop: 2 },
  checkBtn: {
    backgroundColor: colors.yellow,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 6,
  },
  checkBtnDisabled: { opacity: 0.4 },
  checkBtnText: { color: colors.black, fontWeight: '800', fontSize: 15 },
  resultBox: {
    borderRadius: 14,
    padding: 16,
    marginTop: 16,
  },
  resultHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  resultStatus: { fontSize: 18, fontWeight: '800' },
  resultBadge: { fontSize: 11, fontWeight: '700', opacity: 0.9 },
  resultDetail: { fontSize: 14, marginTop: 6, lineHeight: 20 },
  resultMeta: { fontSize: 12, marginTop: 6, opacity: 0.9 },
  history: { marginTop: 24 },
  historyTitle: { fontSize: 14, fontWeight: '700', color: colors.brownDark, marginBottom: 8 },
  historyRow: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 12,
    marginBottom: 8,
  },
  historyStatus: { fontSize: 14, fontWeight: '700', color: colors.black },
  historyMeta: { fontSize: 12, color: colors.muted, marginTop: 3 },
});