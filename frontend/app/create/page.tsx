"use client";

/**
 * Public, keyless workshop creation — spec/capabilities.md C6.
 *
 * Compose → (last step) email → reveal. The email card sits at the very bottom
 * of the compose page, after everything else and immediately before the link
 * reveal: nothing at all is persisted until it is given and valid.
 *
 * The composer is the SAME component the admin console uses
 * (`@/components/create/WorkshopComposer`) — never a fork. On any failure the
 * composed workshop is preserved: we only ever move forward out of composing.
 */

import { useState } from "react";
import { ApiError, createPublicWorkshop, type WorkshopFull } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { CopyButton } from "@/components/ui/CopyButton";
import { useToast } from "@/components/ui/Toast";
import { saveLocalWorkshop } from "@/lib/localWorkshops";
import {
  WorkshopComposer,
  emptyComposerValue,
  validateComposer,
  type ComposerValue,
} from "@/components/create/WorkshopComposer";

/** Mirrors the server rule in spec/api.md §Phase 6 exactly. */
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function emailProblem(raw: string): string | null {
  const email = raw.trim();
  if (email === "") {
    return "Enter your email address so we can reach you about your workshop.";
  }
  if (email.length < 3 || email.length > 254) return "That email address is too long.";
  if (!EMAIL_RE.test(email)) {
    return "That doesn't look like an email address — check it and try again.";
  }
  return null;
}

export default function PublicCreatePage() {
  const toast = useToast();
  const [value, setValue] = useState<ComposerValue>(emptyComposerValue);
  const [composeError, setComposeError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [created, setCreated] = useState<WorkshopFull | null>(null);

  const submit = async () => {
    // Compose first, email last — but never lose either error.
    const checked = validateComposer(value);
    setComposeError(checked.ok ? null : checked.error);

    const problem = emailProblem(email);
    setEmailError(problem);

    // An invalid email sends nothing: no request, therefore no row.
    if (!checked.ok || problem) return;

    setSubmitting(true);
    try {
      const { workshop } = await createPublicWorkshop({
        ...checked.body,
        creator_email: email.trim().toLowerCase(),
      });
      saveLocalWorkshop({
        name: workshop.name,
        facilitator_url: workshop.facilitator_url,
        join_url: workshop.join_url,
        created_at: workshop.created_at,
      });
      setCreated(workshop);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        // The composer already mirrors every body rule, so a 422 here is
        // effectively always the email — show it on the field.
        setEmailError(err.message);
      } else {
        toast.show("Couldn't create your workshop — try again.", "error");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const shell = (children: React.ReactNode) => (
    <div className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
          <a
            href="/"
            className="flex items-center gap-2 font-semibold tracking-tight text-stone-900"
          >
            <span aria-hidden="true" className="text-xl">
              ⛵
            </span>
            Workshop Helmsman
          </a>
          <p className="text-sm text-stone-500">Free · no signup</p>
        </div>
      </header>
      <main data-testid="create-page" className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        {children}
      </main>
    </div>
  );

  // ------------------------------------------------------------ the reveal
  if (created) {
    return shell(
      <div data-testid="create-success">
        <p className="text-sm font-semibold tracking-wide text-emerald-600 uppercase">
          Your workshop is live
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-stone-900">
          “{created.name}” is ready.
        </h1>

        <section className="mt-8 rounded-xl border-2 border-amber-300 bg-amber-50 p-5">
          <h2 className="text-base font-semibold text-amber-900">
            Save this link now — it is the only key to your dashboard
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            There is no account and no password reset. If you lose this link, you lose
            access to your dashboard. Bookmark it, or paste it somewhere safe.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-amber-200 bg-white px-3 py-2">
            <span
              data-testid="success-dashboard-link"
              className="min-w-0 flex-1 break-all font-mono text-sm text-stone-800"
            >
              {created.facilitator_url}
            </span>
            <CopyButton
              data-testid="success-copy-dashboard"
              text={created.facilitator_url}
              label="Copy link"
              className="px-2.5 py-1.5 text-sm"
              aria-label="Copy your dashboard link"
            />
          </div>
        </section>

        <section className="mt-6 rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
          <h2 className="text-base font-semibold text-stone-900">
            Share this link with the room
          </h2>
          <p className="mt-1 text-sm text-stone-600">
            Participants open it, type their first name, and are straight into the
            first milestone. Nothing to install.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
            <span
              data-testid="success-join-link"
              className="min-w-0 flex-1 break-all font-mono text-sm text-stone-800"
            >
              {created.join_url}
            </span>
            <CopyButton
              text={created.join_url}
              label="Copy link"
              className="px-2.5 py-1.5 text-sm"
              aria-label="Copy the join link"
            />
          </div>
        </section>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <a
            href={created.facilitator_url}
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-base font-semibold text-white shadow-sm transition-colors hover:bg-brand-700"
          >
            Open my dashboard
            <svg aria-hidden="true" viewBox="0 0 20 20" fill="currentColor" className="size-5">
              <path fillRule="evenodd" d="M3 10a.75.75 0 0 1 .75-.75h10.638L10.23 5.29a.75.75 0 1 1 1.04-1.08l5.5 5.25a.75.75 0 0 1 0 1.08l-5.5 5.25a.75.75 0 1 1-1.04-1.08l4.158-3.96H3.75A.75.75 0 0 1 3 10Z" clipRule="evenodd" />
            </svg>
          </a>
          <a
            href="/"
            className="text-sm font-medium text-stone-600 underline underline-offset-4 hover:text-stone-900"
          >
            Back to the home page
          </a>
        </div>

        <p className="mt-6 text-sm text-stone-500">
          This browser will remember the workshop under “Your workshops” on the home
          page. That is a convenience, not an account — clearing your browser loses the
          shortcut, so keep the dashboard link above.
        </p>
      </div>,
    );
  }

  // ----------------------------------------------------------- the composer
  return shell(
    <div>
      <h1 className="text-3xl font-semibold tracking-tight text-stone-900">
        Compose your workshop
      </h1>
      <p className="mt-3 max-w-xl text-stone-600">
        Name it, then add the milestones your room will work through — markdown,
        links and fenced code blocks all render. You can edit everything later from
        your dashboard. No account needed, and nothing is created until you press
        Create workshop.
      </p>

      <div className="mt-8 rounded-xl border border-stone-200 bg-white p-5 shadow-sm sm:p-6">
        <WorkshopComposer
          value={value}
          onChange={setValue}
          disabled={submitting}
          idPrefix="pc"
        />
      </div>

      {composeError && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {composeError}
        </p>
      )}

      {/* Last step — email, then the reveal. */}
      <section
        aria-labelledby="last-step-heading"
        className="mt-8 rounded-xl border border-brand-200 bg-brand-50/60 p-5 sm:p-6"
      >
        <p className="text-xs font-semibold tracking-wide text-brand-700 uppercase">
          Last step
        </p>
        <h2
          id="last-step-heading"
          className="mt-1 text-lg font-semibold text-stone-900"
        >
          Where can we reach you?
        </h2>
        <p className="mt-1 max-w-xl text-sm text-stone-600">
          So we can reach you about your workshop. We never send you mail and never
          share it — your dashboard link is shown on the next screen, not emailed.
        </p>

        <form
          className="mt-4 max-w-md"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void submit();
          }}
        >
          <label
            htmlFor="creator-email"
            className="mb-1 block text-sm font-medium text-stone-700"
          >
            Your email address
          </label>
          <input
            id="creator-email"
            data-testid="creator-email-input"
            type="email"
            inputMode="email"
            autoComplete="email"
            maxLength={254}
            value={email}
            disabled={submitting}
            aria-invalid={emailError ? true : undefined}
            aria-describedby={emailError ? "creator-email-error" : undefined}
            onChange={(e) => {
              setEmail(e.target.value);
              if (emailError) setEmailError(null);
            }}
            placeholder="you@example.com"
            className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder:text-stone-400 focus:border-brand-500"
          />
          {emailError && (
            <p
              id="creator-email-error"
              data-testid="email-error"
              role="alert"
              className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            >
              {emailError}
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button type="submit" data-testid="create-submit" loading={submitting}>
              Create workshop
            </Button>
            <a
              href="/"
              className="text-sm font-medium text-stone-600 underline underline-offset-4 hover:text-stone-900"
            >
              Cancel
            </a>
          </div>
        </form>
      </section>
    </div>,
  );
}
