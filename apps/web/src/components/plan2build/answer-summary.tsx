// The family's answers by section, as label and value rows. Shared by the review step (with an
// edit action per section) and the project page (read only). Formatting comes from the question set.
import type { Question, QuestionSet } from "@p2b/contracts";
import type { ReactNode } from "react";

import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  answerable,
  formatAnswer,
  isVisible,
  questionsByKey,
  type Answers,
  type FormatLabels,
} from "@/lib/questions";

export function AnswerSummary({
  set,
  answers,
  labels,
  notAnswered,
  sectionAction,
  hideUnanswered = false,
}: {
  set: QuestionSet;
  answers: Answers;
  labels: FormatLabels;
  notAnswered: string;
  sectionAction?: (index: number, title: string) => ReactNode;
  hideUnanswered?: boolean;
}) {
  const byKey = questionsByKey(set);
  return (
    <div className="flex flex-col gap-4">
      {set.sections.map((section, index) => {
        const rows = section.questions
          .map((key) => byKey.get(key))
          .filter((q): q is Question => !!q && answerable(q) && isVisible(q, answers))
          .map((question) => ({
            question,
            text: formatAnswer(question, answers[question.key], labels),
          }))
          .filter((row) => !hideUnanswered || row.text !== "");
        if (rows.length === 0) return null;
        return (
          <Card key={section.key} size="sm">
            <CardHeader className="border-b">
              <CardTitle className="text-base">
                <h3>{section.title}</h3>
              </CardTitle>
              {sectionAction && <CardAction>{sectionAction(index, section.title)}</CardAction>}
            </CardHeader>
            <CardContent>
              <dl className="divide-y divide-border">
                {rows.map(({ question, text }) => (
                  <div
                    key={question.key}
                    className="grid gap-1 py-2.5 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] sm:gap-4"
                  >
                    <dt className="text-sm text-muted-foreground">{question.label}</dt>
                    <dd className="text-sm font-medium break-words">
                      {text || <span className="font-normal text-muted-foreground">{notAnswered}</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
