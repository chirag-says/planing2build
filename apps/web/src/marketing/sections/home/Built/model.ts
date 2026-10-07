import type { BuiltContent } from '@/marketing/content/sections/built';
import { PHOTO_PLACEHOLDER } from '@/marketing/lib/images';
import { pad2 } from '@/marketing/lib/text';

export type BuiltSpec = { label: string; value: string };

/** What the showcase needs from one stage, prepared on the server. */
export type BuiltProject = {
  slug: string;
  name: string;
  /** "Before the first quote" */
  meta: string;
  summary: string;
  /** Tag on the photo: "Next · Find". */
  status: string;
  /** Dimension line above the photo: "Stage 01 · Plan". */
  size: string;
  /** Short figures, skipping empty ones. Values that hold a number count up. */
  specs: BuiltSpec[];
  result: BuiltSpec | null;
  /** Photo URL; a drawn placeholder when the stage has none. */
  photo: string;
  /** The stage's button; null when it has no label. */
  cta: { label: string; href: string } | null;
};

/** The stages in content order, every one shown. */
export function toBuiltProjects(content: BuiltContent): BuiltProject[] {
  const stages = content.stages.filter((stage) => stage.name);
  return stages.map((stage, index) => {
    const next = stages[index + 1];
    return {
      slug: stage.slug,
      name: stage.name,
      meta: stage.meta,
      summary: stage.summary,
      status: next ? `${content.nextWord} · ${next.name}` : content.lastTag,
      size: `${content.stageWord} ${pad2(index + 1)} · ${stage.name}`,
      specs: stage.specs.filter((spec) => spec.value),
      result: stage.result.label ? stage.result : null,
      photo: stage.photo || PHOTO_PLACEHOLDER,
      cta: stage.cta.label ? stage.cta : null,
    };
  });
}
