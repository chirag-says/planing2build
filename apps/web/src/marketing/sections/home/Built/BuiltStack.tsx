'use client';

import { useRef } from 'react';
import type { BuiltContent } from '@/marketing/content/sections/built';
import { Button } from '@/marketing/components/ui/Button';
import { Eyebrow } from '@/marketing/components/ui/Eyebrow';
import { useReveal } from '@/marketing/hooks/useReveal';
import { revealDelay, type StyleWithVars } from '@/marketing/lib/css';
import { cx } from '@/marketing/lib/cx';
import { pad2 } from '@/marketing/lib/text';
import { TYPE } from '@/marketing/lib/typography';
import { BuiltSpecs } from './BuiltSpecs';
import type { BuiltProject } from './model';
import { framerPhoto } from '@/marketing/lib/images';

const PHOTO_SIZES = '(max-width: 809px) 100vw, 50vw';
/** Each card reveals on its own once 12% of it is in view. */
const CARD_REVEAL = 0.12;

type BuiltStackProps = {
  content: BuiltContent;
  projects: BuiltProject[];
  heading: string;
  projectsHref: string;
};

/** Phone and reduced-motion layout: the stages as a list of cards, two columns from 810px. */
export function BuiltStack({ content, projects, heading }: BuiltStackProps) {
  const level = content.levelLetter.trim() || 'L';
  return (
    <div className="gd-wrap built-stackwrap">
      <header className="built-shead">
        <Eyebrow text={content.eyebrow} />
        <h2 className="gd-sr">{heading}</h2>
        <p className="built-count gd-rv" style={{ ...TYPE.mono, ...revealDelay(120) }}>
          {level}01 – {level}
          {pad2(projects.length)}
        </p>
      </header>
      <ol className="built-cards">
        {projects.map((project, index) => (
          <BuiltCard
            key={project.slug}
            project={project}
            index={index}
            count={projects.length}
            level={level}
          />
        ))}
      </ol>
    </div>
  );
}

type BuiltCardProps = { project: BuiltProject; index: number; count: number; level: string };

function BuiltCard({ project, index, count, level }: BuiltCardProps) {
  const ref = useRef<HTMLLIElement>(null);
  const revealed = useReveal(ref, CARD_REVEAL);
  const photo = framerPhoto(project.photo, PHOTO_SIZES);
  // The photo uncovers upward and settles from 1.28x; its box takes the photo's own shape
  // (built.css) so nothing is cropped.
  const photoStyle: StyleWithVars = {
    borderRadius: 6,
    clipPath: revealed ? 'inset(0 0 0 0)' : 'inset(100% 0 0 0)',
    WebkitClipPath: revealed ? 'inset(0 0 0 0)' : 'inset(100% 0 0 0)',
  };

  return (
    <li ref={ref} className={cx('built-card', revealed && 'is-on')}>
      <div className="built-card-ph">
        <div className={cx('gd-um', revealed && 'is-on')} style={photoStyle}>
          <img
            src={photo.src}
            srcSet={photo.srcSet}
            sizes={photo.sizes}
            alt={project.name}
            loading="lazy"
            decoding="async"
            draggable={false}
          />
        </div>
        <span className="built-tag" style={TYPE.mono}>
          {level}
          {pad2(index + 1)} / {pad2(count)}
        </span>
      </div>
      <h3 className="built-name built-rv" style={{ ...TYPE.display, ...revealDelay(120) }}>
        {project.name}
      </h3>
      <p className="built-meta built-rv" style={{ ...TYPE.mono, ...revealDelay(180) }}>
        {project.meta}
      </p>
      {project.summary && (
        <p className="built-sum built-rv" style={revealDelay(220)}>
          {project.summary}
        </p>
      )}
      <div className="built-rv" style={revealDelay(280)}>
        <BuiltSpecs project={project} />
      </div>
      {project.cta && (
        <div className="built-btns built-rv" style={revealDelay(340)}>
          <Button
            href={project.cta.href}
            label={project.cta.label}
            kind="ghost"
            ariaLabel={`${project.cta.label}: ${project.name}`}
          />
        </div>
      )}
    </li>
  );
}
