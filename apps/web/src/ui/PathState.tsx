import { ReactNode } from 'react';

type PathStateProps = {
  title: string;
  description?: string;
  tone?: 'neutral' | 'error';
  busy?: boolean;
  children?: ReactNode;
};

export function PathState({ title, description, tone = 'neutral', busy = false, children }: PathStateProps) {
  return <section className={`path-state ${tone === 'error' ? 'error' : ''}`} role={tone === 'error' ? 'alert' : busy ? 'status' : undefined} aria-live={tone === 'error' ? 'assertive' : 'polite'}>
    {busy ? <i className="path-loader" aria-hidden="true" /> : <i aria-hidden="true">{tone === 'error' ? '!' : '✦'}</i>}
    <h2>{title}</h2>
    {description && <p>{description}</p>}
    {children}
  </section>;
}
