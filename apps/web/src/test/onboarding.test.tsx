import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { Onboarding, onboardingDraftKey } from '../features/onboarding/Onboarding';

describe('onboarding draft privacy', () => {
  beforeEach(() => localStorage.clear());

  it('persists only non-sensitive numeric and scheduling fields', async () => {
    const user = userEvent.setup();
    render(<Onboarding onDone={() => undefined} />);

    await user.click(screen.getByRole('button', { name: /Продолжить/ }));
    await user.click(screen.getByRole('button', { name: /Продолжить/ }));
    await user.type(screen.getByRole('textbox', { name: 'Моя причина' }), 'личная медицинская заметка');

    await waitFor(() => expect(localStorage.getItem(onboardingDraftKey)).not.toBeNull());
    const stored = JSON.parse(localStorage.getItem(onboardingDraftKey) || '{}');
    expect(stored).toEqual(expect.objectContaining({ pack: 20, remaining: 20, price: 200, startMode: 'last_pack' }));
    expect(stored).not.toHaveProperty('reasons');
    expect(stored).not.toHaveProperty('age');
    expect(stored).not.toHaveProperty('consent');
    expect(localStorage.getItem(onboardingDraftKey)).not.toContain('медицинская');
  });
});
