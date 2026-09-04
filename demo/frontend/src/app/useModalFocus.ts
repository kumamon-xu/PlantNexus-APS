import { useEffect, useRef } from "react";

const focusableSelector = [
  "button:not([disabled])",
  "[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

interface ModalFocusOptions {
  readonly onEscape: () => void;
  readonly escapeDisabled?: boolean;
}

/** Keep keyboard focus inside a modal and return it to the invoking control. */
export function useModalFocus<T extends HTMLElement>(
  open: boolean,
  { onEscape, escapeDisabled = false }: ModalFocusOptions,
) {
  const dialogRef = useRef<T>(null);
  const escapeRef = useRef(onEscape);
  const escapeDisabledRef = useRef(escapeDisabled);

  useEffect(() => {
    escapeRef.current = onEscape;
    escapeDisabledRef.current = escapeDisabled;
  }, [escapeDisabled, onEscape]);

  useEffect(() => {
    if (!open) return;
    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const dialog = dialogRef.current;
    if (dialog === null) return;

    const focusable = () =>
      [...dialog.querySelectorAll<HTMLElement>(focusableSelector)].filter(
        (element) =>
          !element.hidden && element.getAttribute("aria-hidden") !== "true",
      );
    const initial =
      dialog.querySelector<HTMLElement>("[data-autofocus]") ?? focusable()[0];
    initial?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !escapeDisabledRef.current) {
        event.preventDefault();
        escapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const candidates = focusable();
      if (candidates.length === 0) {
        event.preventDefault();
        dialog.focus();
        return;
      }
      const first = candidates[0]!;
      const last = candidates[candidates.length - 1]!;
      if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === dialog)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      queueMicrotask(() => previouslyFocused?.focus());
    };
  }, [open]);

  return dialogRef;
}
