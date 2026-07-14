import { ReactNode, useEffect, useRef } from 'react';

type PathDialogProps = {
  open: boolean;
  onClose: () => void;
  labelledBy: string;
  className?: string;
  children: ReactNode;
};

const focusableSelector = 'button, input, textarea, select, a[href], [tabindex]:not([tabindex="-1"])';

export function PathDialog({ open, onClose, labelledBy, className = '', children }: PathDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab' || !dialogRef.current) return;
      const focusable = Array.from(dialogRef.current.querySelectorAll<HTMLElement>(focusableSelector))
        .filter(element => !element.hasAttribute('disabled'));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown);
    document.body.style.overflow = 'hidden';
    (dialogRef.current?.querySelector<HTMLElement>('[data-autofocus]') ?? dialogRef.current?.querySelector<HTMLElement>(focusableSelector))?.focus();
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = '';
      previousFocus?.focus();
    };
  }, [open]);

  if (!open) return null;
  return <div className="path-sheet-backdrop" onMouseDown={event => {
    if (event.currentTarget === event.target) onClose();
  }}>
    <section ref={dialogRef} tabIndex={-1} className={`path-support-sheet ${className}`.trim()} role="dialog" aria-modal="true" aria-labelledby={labelledBy}>
      {children}
    </section>
  </div>;
}
