"use client";

import { useState } from "react";
import { ApiError, facilitatorSettings } from "@/lib/api";
import { Button } from "@/components/ui/Button";

export function SettingsControl({
  token,
  onSaved,
}: {
  token: string;
  onSaved: () => void;
}) {
  const [value, setValue] = useState("10");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const save = async () => {
    setError(null);
    setSaved(false);
    const n = Number(value);
    if (!Number.isInteger(n) || n < 2 || n > 120) {
      setError("Must be a whole number from 2 to 120.");
      return;
    }
    setBusy(true);
    try {
      await facilitatorSettings(token, n);
      onSaved();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save that setting.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor="stuck-minutes" className="text-stone-600">
        Stuck threshold
      </label>
      <input
        id="stuck-minutes"
        data-testid="stuck-minutes-input"
        type="number"
        min={2}
        max={120}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="w-16 rounded-lg border border-stone-300 bg-white px-2 py-1 text-sm"
      />
      <span className="text-stone-500">min</span>
      <Button
        variant="secondary"
        size="sm"
        data-testid="stuck-minutes-submit"
        loading={busy}
        onClick={save}
      >
        Save
      </Button>
      {saved && <span className="text-emerald-700">Saved</span>}
      {error && (
        <span role="alert" className="text-red-700">
          {error}
        </span>
      )}
    </div>
  );
}
