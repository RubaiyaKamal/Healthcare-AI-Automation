import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { api } from '../api';
import { colors } from '../theme';

const STATUS_STYLES = {
  PAID: { bg: colors.brownDark, fg: colors.yellowLight },
  PARTIALLY_PAID: { bg: colors.border, fg: colors.brownDark },
  DENIED: { bg: colors.brownDark, fg: colors.yellowLight },
  SUBMITTED: { bg: colors.yellow, fg: colors.black },
  PENDING: { bg: colors.yellow, fg: colors.black },
  DRAFT: { bg: colors.yellowSoft, fg: colors.brownDark },
  ERROR: { bg: colors.yellow, fg: colors.black },
  RESOLVED: { bg: colors.brownDark, fg: colors.yellowLight },
  OPEN: { bg: colors.yellow, fg: colors.black },
  PENDING_REVIEW: { bg: colors.yellowSoft, fg: colors.brownDark },
};

function badgeStyle(status) {
  return (
    STATUS_STYLES[status] ?? { bg: colors.yellowSoft, fg: colors.brownDark }
  );
}

function StatusBadge({ status }) {
  const s = badgeStyle(status);
  return (
    <View style={[styles.badge, { backgroundColor: s.bg }]}>
      <Text style={[styles.badgeText, { color: s.fg }]}>{status}</Text>
    </View>
  );
}

function Metric({ label, value, hint }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={styles.metricValue}>{value}</Text>
      {typeof hint === 'string' || typeof hint === 'number' ? (
        <Text style={styles.metricHint}>{hint}</Text>
      ) : null}
    </View>
  );
}

export default function RcmScreen() {
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [payer, setPayer] = useState('');
  const [note, setNote] = useState('');
  const [metrics, setMetrics] = useState(null);
  const [claims, setClaims] = useState([]);
  const [denials, setDenials] = useState([]);
  const [output, setOutput] = useState('');
  const [toolCalls, setToolCalls] = useState([]);
  const [running, setRunning] = useState(false);
  const [fixingId, setFixingId] = useState(null);
  const [error, setError] = useState('');

  function loadAll() {
    api
      .rcmMetrics()
      .then(setMetrics)
      .catch(() => {});
    api
      .rcmClaims()
      .then((d) => setClaims(Array.isArray(d) ? d : []))
      .catch(() => {});
    api
      .rcmDenials()
      .then((d) => setDenials(Array.isArray(d) ? d : []))
      .catch(() => {});
  }

  useEffect(() => {
    api
      .listPatients()
      .then((data) => {
        setPatients(data);
        if (data.length > 0) {
          setSelected(data[0]);
          setPayer(data[0].insurer ?? '');
        }
      })
      .catch((e) => setError(e.message));
    loadAll();
  }, []);

  async function runCycle() {
    if (!selected || !note.trim()) return;
    setRunning(true);
    setError('');
    setOutput('');
    setToolCalls([]);
    try {
      const data = await api.rcmRun({
        patient_fhir_id: selected.fhir_id,
        clinical_note: note,
        payer,
      });
      setOutput(data.output ?? '');
      setToolCalls(Array.isArray(data.tool_calls) ? data.tool_calls : []);
      loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  async function suggestFix(id) {
    setFixingId(id);
    try {
      await api.rcmSuggestDenialFix(id);
      loadAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setFixingId(null);
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
          <Text style={styles.title}>Revenue Cycle</Text>
          <Text style={styles.subtitle}>
            Eligibility → coding → prior auth → claims → denials.
          </Text>
        </View>

        {error !== '' && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <Text style={styles.label}>Patient</Text>
        {patients.map((p) => {
          const active = selected?.fhir_id === p.fhir_id;
          return (
            <TouchableOpacity
              key={p.fhir_id}
              style={[styles.patient, active && styles.patientActive]}
              onPress={() => {
                setSelected(p);
                setPayer(p.insurer ?? '');
                setOutput('');
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

        <Text style={styles.label}>Payer</Text>
        <TextInput
          style={styles.input}
          value={payer}
          onChangeText={setPayer}
          placeholder="e.g. Acme Health"
          placeholderTextColor={colors.muted}
        />

        <Text style={styles.label}>Clinical note</Text>
        <TextInput
          style={[styles.input, styles.noteInput]}
          value={note}
          onChangeText={setNote}
          placeholder="e.g. 48yo with right knee pain, MRI shows meniscal tear. Plan: arthroscopy. Comorbid: diabetes, hypertension."
          placeholderTextColor={colors.muted}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
        />

        <TouchableOpacity
          style={[
            styles.checkBtn,
            (running || !selected || !note.trim()) && styles.checkBtnDisabled,
          ]}
          onPress={runCycle}
          disabled={running || !selected || !note.trim()}
        >
          {running ? (
            <ActivityIndicator color={colors.black} size="small" />
          ) : (
            <Text style={styles.checkBtnText}>
              {selected ? 'Run Revenue Cycle' : 'No patient selected'}
            </Text>
          )}
        </TouchableOpacity>

        {output !== '' && (
          <View style={styles.outputBox}>
            <Text style={styles.outputTitle}>Agent output</Text>
            <Text style={styles.outputText}>{output}</Text>
            {toolCalls.length > 0 && (
              <View style={styles.toolCalls}>
                <Text style={styles.toolCallsTitle}>
                  {toolCalls.length} tool call{toolCalls.length > 1 ? 's' : ''}
                </Text>
                {toolCalls.map((t, i) => (
                  <Text key={i} style={styles.toolCall}>
                    {t.tool}
                    {Object.keys(t.args ?? {}).length > 0
                      ? ` — ${JSON.stringify(t.args)}`
                      : ''}
                  </Text>
                ))}
              </View>
            )}
          </View>
        )}

        {metrics && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Claim funnel</Text>
            <View style={styles.metricsGrid}>
              <Metric label="Submitted" value={metrics.funnel?.total ?? 0} />
              <Metric label="Paid" value={metrics.funnel?.paid ?? 0} />
              <Metric
                label="Partially paid"
                value={metrics.funnel?.partially_paid ?? 0}
              />
              <Metric
                label="Denied"
                value={metrics.funnel?.denied ?? 0}
                hint={`${metrics.denial_rate ?? 0}% rate`}
              />
              <Metric label="Pending" value={metrics.funnel?.pending ?? 0} />
              <Metric label="Open denials" value={metrics.open_denials ?? 0} />
            </View>
          </View>
        )}

        {claims.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Claims</Text>
            {claims.map((c) => (
              <View key={c.claim_id} style={styles.row}>
                <View style={styles.rowHeader}>
                  <StatusBadge status={c.status} />
                  <Text style={styles.rowMono}>{c.claim_id}</Text>
                </View>
                <Text style={styles.rowText}>
                  {c.patient_fhir_id} · {c.payer ?? '—'} ·{' '}
                  {c.total_amount != null ? `$${c.total_amount.toFixed(2)}` : '—'}
                </Text>
                <Text style={styles.rowMono}>
                  {(c.codes ?? []).map((x) => x.code).join(', ') || '—'}
                </Text>
              </View>
            ))}
          </View>
        )}

        {denials.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Denial queue</Text>
            {denials.map((d) => (
              <View key={d.id} style={styles.row}>
                <View style={styles.rowHeader}>
                  <StatusBadge status={d.fix_status} />
                  <Text style={styles.rowMono}>{d.claim_id}</Text>
                </View>
                <Text style={styles.rowText}>
                  {d.reason_code ? `${d.reason_code} — ` : ''}
                  {d.reason_text ?? 'Denied'}
                </Text>
                {d.suggested_fix ? (
                  <Text style={styles.rowFix}>Suggested fix: {d.suggested_fix}</Text>
                ) : null}
                <TouchableOpacity
                  style={[
                    styles.fixBtn,
                    (fixingId === d.id || d.fix_status === 'RESOLVED') &&
                      styles.fixBtnDisabled,
                  ]}
                  onPress={() => suggestFix(d.id)}
                  disabled={fixingId === d.id || d.fix_status === 'RESOLVED'}
                >
                  <Text style={styles.fixBtnText}>
                    {fixingId === d.id ? 'Suggesting…' : 'Suggest fix'}
                  </Text>
                </TouchableOpacity>
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
  label: { fontSize: 13, fontWeight: '600', color: colors.brownDark, marginBottom: 8, marginTop: 4 },
  patient: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  patientActive: { borderColor: colors.brown, backgroundColor: colors.yellowSoft },
  patientName: { fontSize: 15, fontWeight: '700', color: colors.brownDark },
  patientMeta: { fontSize: 12, color: colors.muted, marginTop: 2 },
  input: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 12,
    fontSize: 14,
    color: colors.black,
    marginBottom: 12,
  },
  noteInput: { minHeight: 88 },
  checkBtn: {
    backgroundColor: colors.yellow,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 6,
  },
  checkBtnDisabled: { opacity: 0.4 },
  checkBtnText: { color: colors.black, fontWeight: '800', fontSize: 15 },
  outputBox: {
    backgroundColor: colors.brownDark,
    borderRadius: 14,
    padding: 16,
    marginTop: 16,
  },
  outputTitle: {
    color: colors.yellowLight,
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  outputText: { color: colors.yellowLight, fontSize: 14, lineHeight: 20 },
  toolCalls: { marginTop: 10 },
  toolCallsTitle: {
    color: colors.yellowLight,
    fontSize: 11,
    fontWeight: '700',
    opacity: 0.8,
    marginBottom: 4,
  },
  toolCall: {
    color: colors.yellowLight,
    fontSize: 11,
    fontFamily: 'monospace',
    marginBottom: 2,
    opacity: 0.9,
  },
  section: { marginTop: 24 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: colors.brownDark, marginBottom: 10 },
  metricsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  metric: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 12,
    minWidth: '47%',
    flexGrow: 1,
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    color: colors.muted,
  },
  metricValue: { fontSize: 22, fontWeight: '800', color: colors.black, marginTop: 2 },
  metricHint: { fontSize: 11, color: colors.muted, marginTop: 2 },
  row: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  rowHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  badge: {
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  badgeText: { fontSize: 11, fontWeight: '700' },
  rowMono: { fontSize: 11, fontFamily: 'monospace', color: colors.muted },
  rowText: { fontSize: 13, color: colors.black, marginTop: 2 },
  rowFix: {
    fontSize: 12,
    color: colors.brownDark,
    backgroundColor: colors.yellowSoft,
    borderRadius: 8,
    padding: 8,
    marginTop: 8,
  },
  fixBtn: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: colors.brown,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 6,
    marginTop: 10,
  },
  fixBtnDisabled: { opacity: 0.4 },
  fixBtnText: { color: colors.brown, fontSize: 12, fontWeight: '700' },
});