# Plan2Build: UI design system (frontend implementation contract)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/UI_DESIGN_SYSTEM.md` |
| Version | 1.1 (2026-10-04: approved by Chirag as the frontend standard for all three hosts; desktop step row; desktop axe; page titles; raw-colour check) |
| Status | APPROVED (Chirag, 2026-10-04) as the frontend implementation standard for every homeowner, professional and operations screen. A change to a rule here is a change to this document, with a reason |
| Decided by | Chirag, 2026-10-04: shadcn/ui on Radix, Tailwind CSS, Lucide; no other component library; restrained construction look; light theme only |
| Code | `apps/web/src/app/globals.css` (tokens), `apps/web/src/components/ui/` (primitives), `apps/web/src/components/plan2build/` (Plan2Build components), `apps/web/components.json` (shadcn configuration) |
| Checks | `python tools/check_contrast.py` (token contrast), `python tools/check_ui_tokens.py` (no raw colours outside the token file), axe in the Playwright suite on a phone and a desktop viewport (WCAG 2.0, 2.1 and 2.2 A/AA), `pnpm lint:web` |

## 1. Foundation

| Part | Choice | Version (pinned) |
|---|---|---|
| Component system | shadcn/ui, style `radix-vega`, base `radix` | CLI `shadcn` 4.21.1 |
| Primitives | Radix, through the `radix-ui` package | 1.6.7 |
| Styling | Tailwind CSS 4 with CSS variables; `tw-animate-css` for enter and exit animations | Tailwind 4, tw-animate-css 1.4.0 |
| Class merging | `cn` (shadcn's own package, replaces clsx with tailwind-merge) and `class-variance-authority` for variants | cn 0.4.0, cva 0.7.1 |
| Icons | Lucide (`lucide-react`) only | 1.51.0 |
| Framework | Next.js 16 App Router, React 19, TypeScript strict | as in `package.json` |

Adding a primitive: `pnpm dlx shadcn@4.21.1 add <name> -y` in `apps/web`, then adapt it to section 3 (tokens, touch sizes, no decoration) before use, and list it in section 13.

Forbidden: Material UI, Chakra UI, Ant Design, Mantine, Bootstrap, Headless UI, other UI kits, other icon sets, CSS-in-JS libraries, component-scoped colour values.

## 2. Structure

| Folder | Holds | Rules |
|---|---|---|
| `components/ui/` | shadcn primitives (Button, Input, Field, RadioGroup, Card, Badge, Alert, Dialog and so on) | No business words, no API calls, no message keys. They may be edited to match the tokens; every edit is listed in section 13 |
| `components/plan2build/` | Plan2Build composites built from the primitives (FormField, ChoiceGroup, StatusBadge, PageHeader, WizardProgress, FileRow and so on) and feature components (sign-in form, estimator, requirement wizard) | Compose primitives; never restyle a primitive locally to look different. Domain vocabulary (states, question types) lives here |
| `lib/` | Pure logic: question-set helpers, formatting, navigation | No React; unit-tested |
| `messages/en.json` | Every visible string | No copy in components (ADR-022) |

A composite earns its place when the same pattern appears on two screens or carries a rule (accessibility, state mapping). One-off layout stays in the page.

## 3. Tokens

All values live in `globals.css` as CSS variables in OKLCH, mapped to Tailwind through `@theme inline`. Components use the Tailwind names (`bg-primary`, `text-muted-foreground`, `border-input`); raw colours (`#hex`, `neutral-700`, `blue-700`) are not allowed outside `globals.css`.

### 3.1 Colour

Warm stone neutrals and a charcoal primary. Colour carries state, selection and focus; it is never decoration. No brand colour and no brand typeface until the brand specification is approved (UI-01); `tools/check_ui_tokens.py` fails on any colour value outside `globals.css`.

| Token | Use | Contrast (checked) |
|---|---|---|
| `background`, `foreground` | Page and body text | 17.5:1 |
| `muted`, `muted-foreground` | Panels; secondary text, help text, captions | 7.6:1 on background, 7.0:1 on muted |
| `primary`, `primary-foreground` | Primary actions, selected choice, rank numbers | 14.6:1 |
| `secondary`, `accent` | Secondary buttons; hover and selected backgrounds | text on accent 15.3:1 |
| `border` | Dividers and card outlines (decorative) | not a boundary of a control |
| `input` | Every control border (inputs, choice cards, checkboxes) | 4.3:1 (WCAG 1.4.11 needs 3:1) |
| `ring` | Focus indicator (blue) | 6.7:1 |
| `destructive`, `destructive-muted` | Errors, failed and rejected states | 6.4:1; 5.9:1 on its background |
| `success`, `success-muted` | Done, available, accepted | 6.8:1 on its background |
| `warning`, `warning-muted` | Needs attention, demo data, on hold | 6.9:1 on its background |
| `info`, `info-muted` | In review, in progress, neutral notices | 6.2:1 on its background |

State colours come in pairs: the strong value for text, icons and borders, `-muted` for the background. `python tools/check_contrast.py` checks every pair in this table and fails below the minimum.

### 3.2 Typography

System font stack (`ui-sans-serif, system-ui, Segoe UI, Roboto`) until brand typography is chosen; nothing is fetched from font services. Body text is 16 px everywhere, including inputs (no zoom on iOS).

| Role | Classes |
|---|---|
| Page title (h1, `PageHeader`) | `text-2xl sm:text-3xl font-semibold tracking-tight`; home hero `text-3xl sm:text-5xl` |
| Section (h2, `SectionHeader`, wizard step) | `text-xl` (step `sm:text-2xl`) `font-semibold` |
| Sub-section (h3, card titles) | `text-base` or `text-lg font-semibold` |
| Body | `text-base` |
| Secondary, help, table cells | `text-sm`, help in `text-muted-foreground` |
| Badges, captions | `text-xs font-medium` |
| Numbers that compare (money, areas, percentages) | add `tabular-nums` |

Headings follow document order (one h1 per page, no skipped levels).

### 3.3 Spacing and layout

Tailwind's 4 px scale only; no arbitrary pixel values.

| Use | Value |
|---|---|
| Page padding | `px-4 py-8`, from `sm` `px-6 py-12` (`PageContainer`) |
| Page content width | `narrow` 28 rem (sign-in, capture forms), `default` 48 rem (forms, project pages), `wide` 64 rem (home, estimator); header 64 rem |
| Between page blocks | `gap-8` |
| Between questions in a form step | `gap-10`; between fields in a short form `gap-6` |
| Label to control | `gap-2`; legend to choices `gap-3` |
| Choice cards, buttons in a row | `gap-2` |
| Card padding | 24 px, `size="sm"` 16 px |

### 3.4 Radius, borders, elevation

`--radius` is 0.375 rem (6 px): `rounded-md` for controls, `rounded-lg` for cards, `rounded-sm` for badges. Pills and large radii are not used.

Cards have a 1 px `border` outline and no shadow. Shadows are reserved for surfaces that float above the page (dropdown menus, dialogs, sheets). Overlays dim the page (`bg-foreground/40`) and do not blur it.

### 3.5 Breakpoints

Tailwind defaults: `sm` 640, `md` 768, `lg` 1024, `xl` 1280. Mobile first: write the phone layout, add `sm:` and `lg:` for wider screens. Choice-card columns use container queries (`@container`, `@md:`, `@lg:`), so a group fits a narrow card and a full-width step alike.

## 4. States

| State | Rule |
|---|---|
| Focus | One global `:focus-visible` outline (2 px `ring`, 2 px offset) outside the CSS layers, so no component can remove it; shadcn rings add to it |
| Disabled | `disabled` attribute and 50% opacity; never the only signal that something is unavailable (say why in text when it matters) |
| Loading | A button that started work shows `Spinner` and a verb ("Saving…") and is disabled. The spinner is decorative (`aria-hidden`); the text says what is happening. Page-level waits use `LoadingState` (role `status`) or `Skeleton` with text |
| Error | `Notice tone="error"`: role `alert` for a new problem. Field errors sit under the control, are linked with `aria-describedby`, and mark the control `aria-invalid`; red borders on invalid controls |
| Success | `Notice tone="success"` with role `status` for a result |
| Info and standing notices | `Notice tone="info"` or `"warning"` with no live role (for example the demo-data warning) |
| Empty | `EmptyState`: icon, title, optional description and one action |
| Server data missing | Pages throw to `app/error.tsx` (title, explanation, Try again); 404 for projects that are not the family's |

## 5. Forms

Order inside every field: label, help text, control, error. Requirements are never only in placeholder text.

| Need | Component |
|---|---|
| One control with a label | `FormField` (render prop gives `id`, `aria-describedby`, `aria-invalid`, `aria-required`) |
| A question with several controls | `FormFieldset` (fieldset named by its legend) |
| One answer from a list | `ChoiceGroup`: Radix RadioGroup as full-width choice cards, at least 44 px tall, arrow-key navigation |
| Several answers | `CheckboxGroup`: checkbox cards |
| Dropdown with few fixed options where space is short | `Select` |
| Free text | `Input`, `Textarea` with a character counter when there is a limit |
| Form buttons | `FormActions`: status text on the left, Back then the primary action; sticky at the bottom on phones |

Required and optional: optional questions show "(optional)" after the label; required controls carry `aria-required`. Most questions are required, so marking the exceptions is clearer than starring the rule.

Validation runs twice. In the browser, immediately and before advancing, from the rules the API publishes (the question set's `required`, `min`, `max`, `max_length`, sides and options; `lib/questions.ts`). On the server, always, as the authority. The browser never holds a business rule that is not in the API contract.

After a failed save or submit, a summary `Notice` (role `alert`) lists every problem with a link to its question; the fields show their own messages.

## 6. Multi-step flows (wizard)

| Element | Rule |
|---|---|
| Progress | `WizardProgress`: "Step n of m" always. Phones: one progress bar. From `sm`: one equal column per step on a single row, each with its own bar (filled when done or current) and a done, current or not-started mark; long titles wrap inside their column. The state is spoken once through hidden text ("Your house, completed"). Reached steps can be reopened; later steps cannot be skipped to |
| Step heading | h2, focused on every step change (screen readers hear where they are) |
| Advance | "Save and continue" checks the step, saves the draft, then moves on. Unanswered questions block moving on but are saved first, so nothing entered is lost. Values the API would reject are not sent |
| Save state | "Draft saved" with a tick, or "You have unsaved answers", in the action bar; the browser warns before leaving with unsaved answers |
| Review | Every answer by section in cards, with Edit per section |
| Submit | The primary button checks every step, then opens `ConfirmationDialog` (AlertDialog: focus inside, Escape cancels). Confirm shows the loading state; success leads to the project page with a success notice |
| Errors | Version conflicts and rate limits show as recoverable notices; server field errors reopen the first step with a problem |
| Input changes | Choosing an answer never navigates or submits (WCAG 3.2.2); the family presses a button or follows a link |

## 7. Complex controls

The map stays Leaflet (tiles from configuration); the surrounding field, buttons, coordinates and notices use the design system. The map container is its own stacking context (`z-0`) so Leaflet's panes cannot cover dialogs or the action bar. Leaflet's attribution links are underlined by a global rule (WCAG 1.4.1).

Uploads: a dashed drop area with an "Add files" button (the keyboard path), limits stated as help text, then `FileRow` per file with type icon, name, type and size, a progress bar while sending (XMLHttpRequest upload progress), the file's `StatusBadge` after, and a remove button named after the file. Problems (wrong type, too big, too many, failed) appear in an error notice.

## 8. Status vocabulary

`StatusBadge` is the only way to show a business state. Each state has a label, a tone and an icon, so it reads without colour; `withLabel` adds a hidden "Status:" where the badge stands alone.

| Project state | Label | Tone | Icon |
|---|---|---|---|
| DRAFT | Draft | neutral | pencil |
| SUBMITTED | Submitted | info | send |
| NEEDS_INFO | Needs information | warning | alert circle |
| ACCEPTED | Accepted | success | check circle |
| PLANNING, PLAN_ISSUED, SOURCING, CONTRACTED, BUILDING | Planning; Build Plan issued; Choosing a contractor; Contractor chosen; Building | info | dashed circle, clipboard, search, check, hammer |
| HANDOVER_PENDING | Handover pending | warning | key |
| COMPLETED | Completed | success | check circle |
| ARCHIVED | Archived | neutral | archive |
| ON_HOLD | On hold | warning | pause |
| CANCELLED | Cancelled | neutral | ban |

| File state | Label | Tone |
|---|---|---|
| PENDING_UPLOAD | Not uploaded | neutral |
| UPLOADED, SCANNING | Checking… (spinner) | info |
| AVAILABLE | Ready | success |
| QUARANTINED | Not accepted: the file failed our safety checks | danger |
| FAILED | Upload failed | danger |
| DELETED | Removed | neutral |

Labels for states after SUBMITTED are provisional: those screens do not exist yet, and each label is confirmed when its slice is built. A new state needs a row here before it ships.

## 9. Shell and navigation

Homeowner host: `HomeownerHeader` (server, reads `/me`) with `HeaderNav` (client). A skip link to `#main`; the brand links home; "Cost estimate" and "My projects" with `aria-current="page"`; signed in, an Account menu (DropdownMenu: My projects, Sign out); signed out, Sign in. Below `sm` everything is in a Sheet behind a menu button. Project pages add a breadcrumb (My projects, project, page).

The professional and operations hosts use the same tokens and primitives with their own header and navigation when their slices start; until then they render `FoundationShell`.

## 10. Icons

Lucide only, imported by name. Size 16 px in buttons and badges (`size-4`, default in the primitives), 20 px in file rows, 24 px for empty and drop areas. Icons next to text are `aria-hidden`; an icon-only button has an `aria-label` that names the action and its object ("Remove site.png", "Move Quality of work up"). Icons support meaning; they never replace a word the user needs.

## 11. Motion

Only for feedback: dialog and sheet enter and exit, menu open, spinners, progress bars. No decorative or looping animation. `prefers-reduced-motion: reduce` turns transitions and animations off globally.

## 12. Accessibility standard

WCAG 2.2 AA. Every new screen gets an axe check in Playwright, and the whole suite runs on two projects: a phone (Pixel 7, below `sm`) and a desktop browser (1280 px). Beyond axe:

- Every control has a visible label; groups are fieldsets with a legend.
- Touch targets are at least 44 px tall on phones (buttons `h-11`, inputs `h-11`, choice cards `min-h-11`), 40 px from `sm`.
- Keyboard: Radix keyboard models (arrow keys in radio groups, Escape in dialogs and menus); focus moves to the step heading on step change and into dialogs on open, and returns after.
- Live regions: errors `alert`, results `status`, background progress `aria-live="polite"`; no live region for content that is already there on load.
- State never depends on colour alone (icon and text on every badge and notice).
- Every page has its own title naming the page, then "| Plan2Build" (WCAG 2.4.2; axe only checks that a title exists).
- Menus that open from a button (the Account menu) are non-modal, as in the WAI-ARIA menu button pattern; a modal menu hides the page with `aria-hidden` while its links stay focusable. Dialogs and sheets stay modal.
- `aria-label` only on elements with a role; plain text elements use visually hidden text instead.

## 13. Component inventory

Primitives in `components/ui/` (from shadcn 4.21.1, `radix-vega`): alert, alert-dialog, badge, breadcrumb, button, card, checkbox, dropdown-menu, empty, field, input, label, progress, radio-group, select, separator, sheet, skeleton, spinner, table, textarea.

Edits made to the generated primitives:

| Primitive | Edit | Why |
|---|---|---|
| button | Heights `h-11` (phone) and `h-10` (`sm`); `lg` `h-12`/`h-11`; icon sizes to match; outline uses `border-input`, no shadow | Touch targets; control borders at 3:1 |
| input, select, textarea | Same heights; 16 px text at every width; `bg-background`; no shadow | Touch, legibility, no iOS zoom |
| card | `rounded-lg`, outline in `border`, no shadow | Restrained elevation |
| badge | `rounded-sm`, 24 px tall; variants `success`, `warning`, `info`, `neutral`; destructive uses its muted pair | State vocabulary |
| alert | Variants `warning`, `success`, `info`, stronger `destructive`; no default `role="alert"` (the caller chooses) | Correct live-region use |
| spinner | Decorative (`aria-hidden`) instead of a hard-coded English "Loading" status | Text carries meaning; i18n |
| progress | Track in `border` colour, 8 px | Visible track |
| alert-dialog, sheet | Overlay `bg-foreground/40`, no backdrop blur | No glass effects |

Plan2Build components in `components/plan2build/`: PageContainer, PageHeader, SectionHeader; FormField, FormFieldset, ChoiceGroup, CheckboxGroup, OptionalMark; FormActions; WizardProgress; ConfirmationDialog; Notice, EmptyState, LoadingState; StatusBadge; FileRow; AnswerSummary; ProjectSummaryCard; ProjectBreadcrumb; HomeownerHeader and HeaderNav; feature components (sign-in form, entry questions, enquiry form and page, estimator, create-project button, download button, requirement wizard with its location, ranking, question and uploads fields).

## 14. Forbidden patterns

- Another component library, icon set or font service.
- Raw colour values or Tailwind palette colours in components; colour used as decoration; gradients; glows; glass and blur effects; decorative blobs or illustrations.
- Large radii and pills on cards and controls; shadows on cards; stacked shadows.
- Decorative or looping animation; animation that ignores reduced motion.
- Changing page, submitting or saving when an option is chosen.
- Placeholder text as the only statement of a requirement; asterisks without explanation.
- Business rules written into components when the API contract publishes them.
- Marketing copy not supplied by the client.
- A separate mobile interface; duplicate JSX for the same pattern on two screens.
- Dark mode or theme variants before one is approved.

## 15. Open points

| ID | Point | Owner |
|---|---|---|
| UI-01 | Brand typography and any brand colour; until then system fonts and the charcoal primary | Chirag with the client |
| UI-02 | Labels for project states after SUBMITTED (section 8) are provisional | With each slice |
| UI-03 | Nonce-based Content Security Policy (FOUNDATION_PLAN section 6 item 4) | Before Handover 1 |
| UI-04 | Public pages render on request because the header reads the session (N-29) | Later performance work |
