import Constants from 'expo-constants';

const FALLBACK_HOST = 'localhost';

function devHost() {
  try {
    const hostUri = Constants.expoConfig?.hostUri;
    if (hostUri) return hostUri.split(':')[0];
  } catch {}
  return FALLBACK_HOST;
}

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? `http://${devHost()}:8000/api`;

async function request(path, options = {}) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), 20000);
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = body?.detail;
      throw new Error(
        typeof detail === 'string' ? detail : `HTTP ${res.status}`,
      );
    }
    return body;
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  listPatients: () => request('/patients'),
  eligibilityCheck: (patientFhirId) =>
    request('/eligibility/check', {
      method: 'POST',
      body: JSON.stringify({ patient_fhir_id: patientFhirId, actor: 'mobile-demo' }),
    }),
  eligibilityHistory: (fhirId) => request(`/eligibility/${fhirId}`),
  intake: (messages) =>
    request('/intake', {
      method: 'POST',
      body: JSON.stringify({ messages, actor: 'mobile-demo' }),
    }),
  rcmMetrics: () => request('/rcm/metrics'),
  rcmClaims: () => request('/rcm/claims'),
  rcmDenials: () => request('/rcm/denials'),
  rcmCoding: () => request('/rcm/coding'),
  rcmPriorAuth: () => request('/rcm/prior-auth'),
  rcmRun: ({ patient_fhir_id, clinical_note, payer = '' }) =>
    request('/rcm/run', {
      method: 'POST',
      body: JSON.stringify({
        patient_fhir_id,
        clinical_note,
        payer,
        actor: 'mobile-demo',
      }),
    }),
  rcmSuggestDenialFix: (denialId) =>
    request('/rcm/suggest-denial-fix', {
      method: 'POST',
      body: JSON.stringify({ denial_id: denialId }),
    }),
};