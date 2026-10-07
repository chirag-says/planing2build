import Link from 'next/link';
import type { ReactNode } from 'react';
import { footer, type FooterColumn } from '@/marketing/content/sections/footer';
import { site } from '@/marketing/content/site';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { resolveHref } from '@/marketing/lib/routes';
import { telHref } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import { FooterRoot } from './footer/FooterRoot';
import { LiftReveal } from './footer/LiftReveal';
import { Newsletter } from './footer/Newsletter';
import './footer/footer.css';

/** Each letter of the wordmark takes 0.47 of the font size; the beam's type is sized to fit them. */
const LETTER_WIDTH = 0.47;

/** Desktop and tablet grid for the title block: office, link columns, newsletter. */
function titleBlockColumns(columnCount: number): StyleWithVars {
  const links = columnCount ? `minmax(0,${(columnCount * 0.74).toFixed(2)}fr) ` : '';
  return {
    '--tb-cols': `minmax(0,1.5fr) ${links}minmax(0,1.42fr)`,
    '--tb-cols-tab': `minmax(0,1.3fr) minmax(0,${(Math.max(1, columnCount) * 0.62).toFixed(2)}fr)`,
  };
}

function FooterLink({ href, children }: { href: string; children: ReactNode }) {
  const target = resolveHref(href);
  return target.startsWith('/') ? <Link href={target}>{children}</Link> : <a href={target}>{children}</a>;
}

function LinkColumn({ column, index }: { column: FooterColumn; index: number }) {
  return (
    <div className="footer-cell footer-col gd-rv" style={revealDelay(130 + index * 70, 16)}>
      <p className="footer-ch" style={TYPE.mono}>
        {column.title}
      </p>
      <ul>
        {column.links.map((link) => (
          <li key={link.href}>
            <FooterLink href={link.href}>{link.label}</FooterLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Site footer: a ruled title block (office, link columns, site letter), the company name in ink
 * on a yellow beam that is lowered into place on two slings as the footer is uncovered, and the
 * legal line. The page above lifts off it (LiftReveal).
 */
export function Footer() {
  const name = site.name || 'Plan2Build';
  const columns = footer.columns.filter((column) => column.links.length);
  const letters = Array.from(name.toUpperCase()).filter((letter) => letter.trim());
  const legal = footer.legal.replace('{year}', String(new Date().getFullYear())).replace('{name}', name);

  const content = (
    <FooterRoot
      id="contact"
      style={{
        '--fn': Math.max(1, letters.length) * LETTER_WIDTH,
        '--n': columns.length,
      }}
    >
      <div className="gd-wrap footer-wrap">
        <div className="footer-head gd-rv" style={revealDelay(0, 12)}>
          <p className="footer-kick" style={TYPE.mono}>
            <i aria-hidden="true" />
            {[site.descriptor, site.area].filter(Boolean).join(' · ')}
          </p>
          {site.socials.length > 0 && (
            <ul className="footer-soc" aria-label="Social media">
              {site.socials.map((social) => (
                <li key={social.label}>
                  <a href={social.href} target="_blank" rel="noopener" style={TYPE.mono}>
                    {social.label}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="footer-tb" style={titleBlockColumns(columns.length)}>
          <div className="footer-cell footer-office gd-rv" style={revealDelay(60, 16)}>
            <p className="footer-ch" style={TYPE.mono}>
              {footer.officeTitle}
            </p>
            {footer.address && (
              <p className="footer-addr" style={TYPE.display}>
                {footer.address}
              </p>
            )}
            {footer.hours && (
              <p className="footer-hours" style={TYPE.mono}>
                {footer.hours}
              </p>
            )}
            <div className="footer-contact">
              {site.phone && <a href={telHref(site.phone)}>{site.phone}</a>}
              {site.email && <a href={`mailto:${site.email}`}>{site.email}</a>}
            </div>
          </div>

          {columns.length > 0 && (
            <nav className="footer-cols" aria-label="Footer">
              {columns.map((column, index) => (
                <LinkColumn key={column.title} column={column} index={index} />
              ))}
            </nav>
          )}

          <div className="footer-cell footer-news gd-rv" style={revealDelay(340, 16)}>
            <p className="footer-ch" style={TYPE.mono}>
              {footer.newsTitle}
            </p>
            <p className="footer-nt" style={TYPE.display}>
              {footer.newsLine}
            </p>
            <Newsletter label={footer.newsLabel} button={footer.newsButton} done={footer.newsDone} error={footer.newsError} />
          </div>
        </div>
      </div>

      <div className="footer-bay" role="img" aria-label={name}>
        <div className="footer-rig" aria-hidden="true">
          <span className="footer-sl is-l" />
          <span className="footer-sl is-r" />
          <div className="footer-beam">
            <span className="footer-bolts is-l" />
            <span className="footer-bolts is-r" />
            <p className="footer-word" style={TYPE.display}>
              {letters.map((letter, index) => (
                <span key={index}>{letter}</span>
              ))}
            </p>
          </div>
        </div>
      </div>

      <div className="gd-wrap">
        <div className="footer-base" style={TYPE.mono}>
          <span>{legal}</span>
          {site.licence && <span>{site.licence}</span>}
          {footer.builtWith && <span className="footer-built">{footer.builtWith}</span>}
        </div>
      </div>
    </FooterRoot>
  );

  return footer.reveal ? <LiftReveal layer={footer.layer}>{content}</LiftReveal> : content;
}
