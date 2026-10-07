import type { Ref } from 'react';
import { Button } from '@/marketing/components/ui/Button';
import type { HeaderContent } from '@/marketing/content/sections/header';
import type { StyleWithVars } from '@/marketing/lib/css';
import { pad2 } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import { type HeaderProject } from './data';
import { Arrow } from './icons';
import { NavAnchor } from './NavAnchor';
import { framerPhoto } from '@/marketing/lib/images';

type SheetProps = {
  ref: Ref<HTMLDivElement>;
  open: boolean;
  copy: HeaderContent;
  projects: HeaderProject[];
  bidHref: string;
  phone: string;
  phoneHref: string;
  isActive: (href: string) => boolean;
};

/** Stagger slot for the rise-in transition (50ms apart, see header.css). */
const order = (index: number): StyleWithVars => ({ '--i': index });

/** Full-screen menu under 1100px: numbered links, the two newest projects, bid and call. */
export function Sheet({ ref, open, copy, projects, bidHref, phone, phoneHref, isActive }: SheetProps) {
  const tabIndex = open ? 0 : -1;
  const hasHome = copy.links.some((link) => link.href === '/');
  const links = (hasHome ? copy.links : [{ label: copy.homeLabel, href: '/' }, ...copy.links]).filter((link) => link.label);
  return (
    <div
      ref={ref}
      id="header-sheet"
      className="header-sheet gd-dark"
      role="dialog"
      aria-modal="true"
      aria-label={copy.menuLabel}
      aria-hidden={!open}
      // Lenis leaves wheel scrolling inside the sheet to the browser.
      data-lenis-prevent
    >
      <div className="header-sin">
        <nav className="header-slinks" aria-label="Main">
          {links.map((link, index) => {
            const active = isActive(link.href);
            return (
              <NavAnchor
                key={link.href}
                href={link.href}
                className={active ? 'is-act' : ''}
                aria-current={active ? 'page' : undefined}
                style={order(index)}
                tabIndex={tabIndex}
              >
                <small style={TYPE.mono}>{pad2(index)}</small>
                <span className="header-slt" style={TYPE.display}>
                  {link.label}
                </span>
                <Arrow size={18} />
              </NavAnchor>
            );
          })}
        </nav>
        {projects.length > 0 && (
          <div className="header-snew">
            <p style={TYPE.mono}>
              <i aria-hidden="true" />
              {copy.newestLabel}
            </p>
            <div>
              {projects.map((project, index) => (
                // Rows continue the stagger after the links.
                <NavAnchor key={project.slug} className="header-srow" href={`/projects/${project.slug}`} tabIndex={tabIndex} style={order(index + 7)}>
                  <span className="header-sri">
                    <img {...framerPhoto(project.photo, '96px')} alt={project.name} loading="lazy" decoding="async" />
                  </span>
                  <span className="header-srt">
                    <b style={TYPE.display}>{project.name}</b>
                    {project.meta && <small style={TYPE.mono}>{project.meta}</small>}
                  </span>
                </NavAnchor>
              ))}
            </div>
          </div>
        )}
        <div className="header-sfoot">
          {copy.showCta && copy.ctaLabel && <Button href={copy.ctaHref || bidHref} label={copy.ctaLabel} kind="solid" className="header-sbtn" />}
          {phone && (
            <NavAnchor className="header-scall" href={phoneHref} tabIndex={tabIndex}>
              <small style={TYPE.mono}>{copy.callLabel}</small>
              <span style={TYPE.display}>{phone}</span>
            </NavAnchor>
          )}
        </div>
      </div>
    </div>
  );
}
