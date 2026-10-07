'use client';

import { useState, type FormEvent } from 'react';
import { ButtonFace } from '@/marketing/components/ui/Button';
import { TYPE } from '@/marketing/lib/typography';

/** Something@domain.tld with a TLD of two or more characters. */
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

type NewsletterProps = {
  label: string;
  button: string;
  done: string;
  error: string;
};

/**
 * The sign-up form. The reference had no endpoint configured, so a valid address goes straight
 * to the thank-you state without sending anything; an invalid one shows the error until the
 * field changes. Returns siblings, not a wrapper: on tablet they sit in the cell's grid.
 */
export function Newsletter({ label, button, done, error }: NewsletterProps) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'invalid' | 'done'>('idle');
  const invalid = status === 'invalid';

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatus(EMAIL.test(email.trim()) ? 'done' : 'invalid');
  };

  if (status === 'done') {
    return (
      <p className="footer-ok" role="status">
        <span aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="square">
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </span>
        {done}
      </p>
    );
  }

  return (
    <>
      <form className={invalid ? 'footer-form is-err' : 'footer-form'} onSubmit={onSubmit} noValidate>
        <label className="gd-sr" htmlFor="footer-email">
          {label}
        </label>
        <input
          id="footer-email"
          type="email"
          autoComplete="email"
          placeholder={label}
          value={email}
          onChange={(event) => {
            setEmail(event.target.value);
            if (invalid) setStatus('idle');
          }}
          aria-invalid={invalid}
          aria-describedby={invalid ? 'footer-err' : undefined}
        />
        <button type="submit" className="gd-btn gd-quiet footer-go" data-cur="go">
          <ButtonFace label={button} />
        </button>
      </form>
      {invalid && (
        <p id="footer-err" className="footer-err" role="alert" style={TYPE.mono}>
          {error}
        </p>
      )}
    </>
  );
}
