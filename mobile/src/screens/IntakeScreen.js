import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { api } from '../api';
import { colors } from '../theme';

const SUGGESTIONS = [
  'Register a new patient: Maria Lopez, DOB 1985-04-12, phone 555-0102',
  'New walk-in: James Miller, DOB 1972-11-03',
];

export default function IntakeScreen() {
  const scrollRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);

  async function send(userText) {
    const text = (userText ?? input).trim();
    if (!text || busy) return;
    const next = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setBusy(true);

    try {
      const data = await api.intake(next);
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: data.output || '(no output)' },
      ]);
      if (data.tool_calls?.length) {
        setMessages((m) => [
          ...m,
          {
            role: 'assistant',
            content: `Tools: ${data.tool_calls.map((t) => t.tool).join(', ')}`,
          },
        ]);
      }
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: `Error: ${err.message}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={80}
    >
      <View style={styles.header}>
        <Text style={styles.title}>Intake Agent</Text>
        <Text style={styles.subtitle}>
          Duplicate check enforced before registration.
        </Text>
      </View>

      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.chat}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.length === 0 && (
          <View>
            <Text style={styles.hint}>Try a suggestion:</Text>
            {SUGGESTIONS.map((s) => (
              <TouchableOpacity
                key={s}
                style={styles.chip}
                onPress={() => {
                  setInput(s);
                  send(s);
                }}
              >
                <Text style={styles.chipText}>{s}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {messages.map((m, i) => (
          <View
            key={i}
            style={[
              styles.bubble,
              m.role === 'user' ? styles.bubbleUser : styles.bubbleBot,
            ]}
          >
            <Text
              style={m.role === 'user' ? styles.bubbleUserText : styles.bubbleBotText}
            >
              {m.content}
            </Text>
          </View>
        ))}

        {busy && (
          <View style={[styles.bubble, styles.bubbleBot]}>
            <ActivityIndicator color={colors.brown} size="small" />
            <Text style={styles.bubbleBotText}> Running agent tools…</Text>
          </View>
        )}
      </ScrollView>

      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder="Describe the new patient…"
          placeholderTextColor={colors.muted}
          editable={!busy}
          onSubmitEditing={() => send()}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.send, (!input.trim() || busy) && styles.sendDisabled]}
          onPress={() => send()}
          disabled={busy || !input.trim()}
        >
          <Text style={styles.sendText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.cream },
  header: { paddingHorizontal: 20, paddingTop: 20, paddingBottom: 12 },
  title: { fontSize: 22, fontWeight: '800', color: colors.black },
  subtitle: { fontSize: 13, color: colors.muted, marginTop: 2 },
  scroll: { flex: 1 },
  chat: { padding: 16, paddingTop: 4 },
  hint: { fontSize: 13, color: colors.muted, marginBottom: 8 },
  chip: {
    backgroundColor: colors.yellowSoft,
    borderWidth: 1,
    borderColor: colors.yellow,
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginBottom: 8,
  },
  chipText: { color: colors.brownDark, fontSize: 13 },
  bubble: {
    maxWidth: '85%',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 9,
    marginBottom: 8,
  },
  bubbleUser: { alignSelf: 'flex-end', backgroundColor: colors.yellow },
  bubbleBot: {
    alignSelf: 'flex-start',
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: 'row',
    alignItems: 'center',
  },
  bubbleUserText: { color: colors.black, fontSize: 14 },
  bubbleBotText: { color: colors.brownDark, fontSize: 14 },
  inputRow: {
    flexDirection: 'row',
    gap: 8,
    padding: 12,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.white,
  },
  input: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: colors.black,
    backgroundColor: colors.cream,
  },
  send: {
    backgroundColor: colors.yellow,
    borderRadius: 10,
    paddingHorizontal: 18,
    justifyContent: 'center',
  },
  sendDisabled: { opacity: 0.4 },
  sendText: { color: colors.black, fontWeight: '700' },
});