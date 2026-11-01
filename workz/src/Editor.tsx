import React, { useState, useEffect } from "react";
import { Row } from "./api";
export type Field = {
  key: string;
  label: string;
  type?: string;
  options?: { value: string; label: string }[];
  required?: boolean;
};
export default function Editor({
  title,
  fields,
  initial,
  onSave,
  onClose,
}: {
  title: string;
  fields: Field[];
  initial: Row;
  onSave: (v: Row) => Promise<void>;
  onClose: () => void;
}) {
  const [values, setValues] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const previous = document.activeElement as HTMLElement;
    const dialog = document.querySelector(".dialog")!;
    const controls = () =>
      Array.from(
        dialog.querySelectorAll<HTMLElement>("input,select,button"),
      ).filter((e) => !e.hasAttribute("disabled"));
    controls()[0]?.focus();
    function trap(e: KeyboardEvent) {
      if (e.key !== "Tab") return;
      const list = controls(),
        first = list[0],
        last = list[list.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", trap);
    return () => {
      document.removeEventListener("keydown", trap);
      previous?.focus();
    };
  }, []);
  useEffect(() => {
    const dirty = busy || JSON.stringify(values) !== JSON.stringify(initial);
    const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', beforeUnload);
    if (window.workzBoot?.office_contract === 2)
      window.parent.postMessage({type:'office:workz-dirty', version:2, dirty}, location.origin);
    return () => {
      window.removeEventListener('beforeunload', beforeUnload);
      if (window.workzBoot?.office_contract === 2)
        window.parent.postMessage({type:'office:workz-dirty', version:2, dirty:false}, location.origin);
    };
  }, [values, initial, busy]);
  const close = () => {
    if (
      JSON.stringify(values) === JSON.stringify(initial) ||
      window.confirm("Discard unsaved changes?")
    )
      onClose();
  };
  return (
    <div
      className="overlay"
      onKeyDown={(e) => {
        if (e.key === "Escape" && !busy) close();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-title"
        className="dialog"
      >
        <h2 id="edit-title">{title}</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await onSave(values);
              onClose();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {fields.map((f) => (
            <label key={f.key}>
              {f.label}
              {f.type === "checkbox" ? (
                <input
                  type="checkbox"
                  checked={!!values[f.key]}
                  onChange={(e) =>
                    setValues({ ...values, [f.key]: e.target.checked })
                  }
                />
              ) : f.options ? (
                <select
                  aria-label={f.label}
                  required={f.required !== false}
                  value={values[f.key] ?? ""}
                  onChange={(e) =>
                    setValues({
                      ...values,
                      [f.key]: e.target.value,
                      ...(["plan_start", "check_in_time"].includes(f.key)
                        ? { start_offset: "" }
                        : ["plan_end", "check_out_time"].includes(f.key)
                          ? { end_offset: "" }
                          : {}),
                    })
                  }
                >
                  <option value="">Choose…</option>
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  autoFocus={fields[0] === f}
                  required={f.required !== false}
                  type={f.type || "text"}
                  step={f.type === "number" ? "0.000001" : undefined}
                  value={values[f.key] ?? ""}
                  onChange={(e) =>
                    setValues({
                      ...values,
                      [f.key]: e.target.value,
                      ...(["plan_start", "check_in_time"].includes(f.key)
                        ? { start_offset: "" }
                        : ["plan_end", "check_out_time"].includes(f.key)
                          ? { end_offset: "" }
                          : {}),
                    })
                  }
                />
              )}
            </label>
          ))}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <footer>
            <button type="button" disabled={busy} onClick={close}>
              Cancel
            </button>
            <button className="primary" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}
