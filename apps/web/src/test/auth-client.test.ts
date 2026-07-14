import { describe, expect, it } from 'vitest';
import { safeOidcReturnPath } from '../api';

describe('OIDC interrupted-flow return path', () => {
  it('allows only known same-origin product routes', () => {
    expect(safeOidcReturnPath('/journal')).toBe('/journal');
    expect(safeOidcReturnPath('/app/support')).toBe('/app/support');
    expect(safeOidcReturnPath('/staff')).toBe('/staff');
    expect(safeOidcReturnPath('//evil.example/path')).toBe('/app');
    expect(safeOidcReturnPath('https://evil.example')).toBe('/app');
    expect(safeOidcReturnPath('/unknown')).toBe('/app');
  });
});
