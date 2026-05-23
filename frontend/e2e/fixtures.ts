// Shared fixtures for E2E tests.
//
// Keep the test user credentials stable across runs so seeded state (feedback
// persistence) can be re-verified. If you change these, also wipe the user
// from the test database.

export const API_URL = process.env.PLAYWRIGHT_API_URL || 'http://localhost:8000';

export const TEST_USER = {
  name: 'E2E Test User',
  email: 'e2e@mahiks.local',
  password: 'E2eTest!2026',
};

// A known-good Turkish question from data/eval_questions.json. Picked
// because it consistently returns multiple citations on the baseline corpus.
export const TEST_QUESTION =
  'Yurt dışında yapılacak tetkikler için avans ödemesi nasıl yapılabilir?';
