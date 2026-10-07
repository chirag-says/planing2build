import type { ReactNode } from 'react';
import { Footer } from '@/marketing/components/layout/Footer';
import { Header } from '@/marketing/components/layout/Header';
import { Loader } from '@/marketing/components/layout/Loader';
import './styles/document.css';

/**
 * The public website's frame: first-visit loader, the site header, and the page column the
 * footer lifts off. The page transition and smooth scrolling live one level up (the homeowner
 * host's layout), so they keep running when a visitor moves on to sign-in and their projects.
 */
export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <>
      {/* First: its inline script must cover the page before anything else is parsed. */}
      <Loader />
      <Header />
      <div className="mk site">
        {children}
        <Footer />
      </div>
    </>
  );
}
